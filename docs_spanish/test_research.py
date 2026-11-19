########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de tests/test_research.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su
# propósito es enseñar, no ejecutarse (pytest solo busca tests en tests/,
# como indica pytest.ini). El archivo real y "limpio" (sin nada de este
# comentario) es tests/test_research.py.
#
# Lee antes estos; lo que explican NO se repite aquí:
#   - docs_spanish/test_extract_csv.py   lo básico de pytest (los nombres
#                                        test_, assert, cómo ejecutar los
#                                        tests)
#   - docs_spanish/test_pipeline.py      pequeñas funciones auxiliares en
#                                        un archivo de tests, argumentos
#                                        con nombre
#   - los tres scripts que se prueban: docs_spanish/choose_starts.py,
#     docs_spanish/traversal.py y docs_spanish/measure.py
#
# Lo que es NUEVO aquí: pytest.raises (comprobar que una función RECHAZA
# una entrada incorrecta), comprobar que un resultado NO depende del
# orden de la entrada, y dos FIXTURES de pytest, tmp_path y monkeypatch
# (en el último test). Los tests sirven además como una descripción
# precisa, y ejecutable, de las reglas de la investigación: qué actores
# se eligen, qué aspecto tienen los textos Cypher, en qué orden se
# ejecutan los lados, cómo se resumen las cifras de un lado, quién cuenta
# como más rápido, y la forma y los nombres de los archivos CSV de
# resultados.
#
# Su papel en el proyecto: comprobar la lógica propia de los scripts de
# la investigación — las partes que no necesitan base de datos — para
# que un error en una regla se detecte en un segundo, y no después de
# horas de mediciones.
#
# Cómo ejecutar los tests reales:   python -m pytest
########################################################################

"""Unit tests for the research scripts' own logic (no network, no databases).

choose_starts.py (which actors), traversal.py (the query texts) and
measure.py (the order of the sides, the data window, the comparison).

Run with:  python -m pytest
"""

# Esta vez se importa el propio pytest (los archivos de tests anteriores
# no lo necesitaban): solo para pytest.raises, en los tests del recorrido
# de más abajo.
import pytest

# ---------------------------------------------------------------------
# Las funciones que se prueban. `from measure import ...` funciona porque
# pytest.ini añade scripts/ a la ruta de búsqueda de Python
# (pythonpath = scripts). Todas son funciones PURAS — reciben datos
# normales y devuelven datos normales — así que se pueden probar sin
# tener PostgreSQL ni Neo4j en marcha. Outcome (el resultado de una
# ejecución, docs_spanish/traversal.py) se importa para construir
# ejecuciones falsas.
# ---------------------------------------------------------------------
from choose_starts import choose, pick_median, pick_top
from measure import compare, data_window, run_order, side_summary, sides
from traversal import Outcome, cypher_hops, cypher_reach, sql_joins


# ---------------------------------------------------------------------
# Una función auxiliar (no es un test: no empieza por test_) que
# construye un actor falso como diccionario, con las mismas claves que
# los reales (ver choose_starts.py):
#   reached   a cuántos otros actores llega en un salto
#   repos     con cuántos repos ha interactuado
# `login=None` + `login or f"user{actor_id}"`: si no se da ningún login,
# se inventa uno ("user7"). `or` da el lado derecho cuando el izquierdo
# es None.
# ---------------------------------------------------------------------
def actor(actor_id, reached, repos, login=None):
    return {"actor_id": actor_id, "login": login or f"user{actor_id}", "reached": reached, "repos": repos}


# ---------- choose_starts: the top group ----------

# El grupo top son "los actores que llegan a más actores", de más a menos.
def test_top_is_ordered_by_actors_reached():
    actors = [actor(1, 2, 1), actor(2, 9, 1), actor(3, 5, 1)]
    # La list comprehension se queda solo con los ids, para comparar el
    # ORDEN: 9 alcanzados (id 2), después 5 (id 3), después 2 (id 1).
    assert [a["actor_id"] for a in pick_top(actors, size=3)] == [2, 3, 1]


# Los empates se tienen que deshacer con una regla fija; si no, la
# elección podría cambiar de una ejecución a otra (o entre PostgreSQL y
# Neo4j).
def test_top_tie_is_broken_by_more_repos_then_smaller_id():
    actors = [actor(30, 5, 1), actor(20, 5, 4), actor(10, 5, 1)]
    # same "reached": 20 has more repos; then 10 before 30 (smaller id)
    assert [a["actor_id"] for a in pick_top(actors, size=3)] == [20, 10, 30]


# Sin size=..., se aplica el tamaño de grupo por defecto (10).
def test_top_keeps_only_ten():
    actors = [actor(i, i, 1) for i in range(1, 30)]
    assert len(pick_top(actors)) == 10


# ---------- choose_starts: the median group ----------

# El grupo "median" son los actores TÍPICOS: aquellos cuyo "reached" está
# más cerca de la mediana. Los actores que no llegan a nadie
# (reached = 0) se descartan primero: empezar un recorrido desde ellos no
# mediría nada.
def test_median_leaves_out_actors_that_reach_nobody():
    actors = [actor(1, 0, 1), actor(2, 0, 1), actor(3, 2, 1), actor(4, 2, 1), actor(5, 2, 1)]
    chosen = pick_median(actors, exclude=set(), size=3)
    # Una SET comprehension { } — aquí el orden no importa, solo qué ids
    # se eligieron. Al comparar dos conjuntos se ignora el orden.
    assert {a["actor_id"] for a in chosen} == {3, 4, 5}


def test_median_takes_the_closest_to_the_median():
    # reached 1..9 -> median 5; closest: 5, then 4 and 6 (tie: more repos first, then id)
    actors = [actor(i, i, 1) for i in range(1, 10)]
    # La posición 5 de la lista (contando desde 0) es el actor con id 6.
    # Se sustituye por el mismo actor con 3 repos, así que gana el empate
    # contra el id 4 (los dos están a 1 de la mediana).
    actors[5] = actor(6, 6, 3)
    chosen = pick_median(actors, exclude=set(), size=3)
    assert [a["actor_id"] for a in chosen] == [5, 6, 4]


# exclude= los ids que ya están en el grupo top: un actor nunca está en
# los dos.
def test_median_never_repeats_a_top_actor():
    actors = [actor(i, 3, 1) for i in range(1, 6)]
    chosen = pick_median(actors, exclude={1, 2}, size=5)
    assert {a["actor_id"] for a in chosen} == {3, 4, 5}


# ---------------------------------------------------------------------
# choose() junta los dos grupos, como una lista de filas.
# ["top"] * 10 + ["median"] * 10 — `*` repite una lista y `+` une dos:
# diez "top" seguidos de diez "median". Las posiciones (ranks) vuelven a
# empezar en 1 en cada grupo: rows[0] es el primer actor top y rows[10]
# el primer actor median. Con reached = 1..30, el actor que llega a más
# es el id 30.
# ---------------------------------------------------------------------
def test_choose_gives_groups_and_ranks():
    rows = choose([actor(i, i, 1) for i in range(1, 31)])
    assert [r["group"] for r in rows] == ["top"] * 10 + ["median"] * 10
    assert rows[0]["rank"] == 1 and rows[0]["actor_id"] == 30
    assert rows[10]["rank"] == 1


# ---------------------------------------------------------------------
# COMPROBAR QUE EL ORDEN DE LA ENTRADA NO IMPORTA
#
# Los actores vienen de una consulta a la base de datos, y las bases de
# datos no garantizan ningún orden concreto de las filas. Si la elección
# dependiera de él, la misma base de datos podría dar actores de partida
# distintos de un día para otro. Por eso el test le da a choose() los
# mismos actores en dos órdenes opuestos y exige exactamente el mismo
# resultado. `i % 7` e `i % 3` (restos de la división) crean muchos
# empates a propósito, para poner a prueba la regla de desempate.
# ---------------------------------------------------------------------
def test_choose_is_the_same_whatever_the_input_order():
    # PostgreSQL and Neo4j return rows in different orders; the choice must not depend on it.
    actors = [actor(i, i % 7, i % 3) for i in range(1, 50)]
    assert choose(actors) == choose(list(reversed(actors)))


# ---------- traversal: the query texts ----------

# cypher_reach(3, "paths") debe contener el patrón de longitud variable
# {1,3} ("de 1 a 3 saltos") y el parámetro $start. `"..." in texto` es
# True si el fragmento aparece en cualquier parte del texto.
def test_cypher_paths_writes_the_depth_into_the_pattern():
    assert "{1,3}" in cypher_reach(3, "paths")
    assert "$start" in cypher_reach(3, "paths")


# ---------------------------------------------------------------------
# La versión "levels" une un STEP por cada salto (ver
# docs_spanish/traversal.py). texto.count("fragmento") dice cuántas veces
# aparece el fragmento: profundidad 4 -> exactamente 4 subconsultas CALL.
# El segundo assert comprueba que el paso descarta de verdad los actores
# ya vistos, y que el de partida sigue siendo un parámetro.
# ---------------------------------------------------------------------
def test_cypher_levels_has_one_step_per_hop():
    query = cypher_reach(4, "levels")
    assert query.count("CALL (seen, frontier)") == 4
    assert "NOT b IN seen" in query and "$start" in query


# ---------------------------------------------------------------------
# pytest.raises — COMPROBAR QUE ALGO FALLA
#
# A veces el comportamiento correcto ES un error: una profundidad de 0 no
# tiene sentido, y cypher_reach debe rechazarla con un ValueError en lugar
# de construir una consulta rota. Lo mismo con un nombre de versión que
# no conoce.
#     with pytest.raises(ValueError):
#         <código>
# significa "el código de dentro debe lanzar un ValueError". Si lo hace,
# pytest lo captura y el test PASA. Si no lanza nada (o lanza otro tipo
# de error), el test FALLA. Cada bloque `with` comprueba UNA llamada: el
# primer error termina su bloque.
# ---------------------------------------------------------------------
def test_cypher_refuses_depth_zero_and_unknown_versions():
    with pytest.raises(ValueError):
        cypher_reach(0)
    with pytest.raises(ValueError):
        cypher_reach(2, "shortcut")


# Un salto = 2 joins en SQL, 2 relaciones en Cypher: profundidad 3 -> 6
# en cada lado (las columnas joins_or_hops del CSV de resultados).
def test_joins_and_hops_are_two_per_depth():
    assert sql_joins(3) == 6 and cypher_hops(3) == 6


# ---------- measure ----------

# --cypher both -> PostgreSQL y las dos versiones de Cypher; --cypher
# levels -> PostgreSQL y solo esa versión. PostgreSQL va siempre primero.
def test_sides_are_postgresql_then_the_cypher_versions():
    assert sides("both") == ["postgresql", "neo4j-paths", "neo4j-levels"]
    assert sides("levels") == ["postgresql", "neo4j-levels"]


# ---------------------------------------------------------------------
# La regla de equidad de measure.py (ver docs_spanish/measure.py,
# run_order): los lados se van ROTANDO, así que cada repetición empieza
# con un lado distinto. Con tres lados, la repetición 4 vuelve al
# principio (la rotación da la vuelta); con dos lados, simplemente se
# alternan.
# ---------------------------------------------------------------------
def test_run_order_changes_which_side_goes_first():
    three = ["postgresql", "neo4j-paths", "neo4j-levels"]
    assert run_order(three, 1) == three
    assert run_order(three, 2) == ["neo4j-paths", "neo4j-levels", "postgresql"]
    assert run_order(three, 4) == three
    assert run_order(["postgresql", "neo4j-paths"], 2) == ["neo4j-paths", "postgresql"]


# ---------------------------------------------------------------------
# data_window lee la ventana de tiempo de los datos a partir del NOMBRE
# de la base de datos:
#   ...-2026-10-08-9-24h   desde las 09:00, 24 horas -> termina al día
#                          siguiente a las 09:00
#   ...-2026-10-08-23      sin parte "-<n>h": UNA hora, de 23:00 a 00:00
#                          del día siguiente (la fecha también cambia)
#   gharchive24h           no es un nombre que cree build_hours.py:
#                          valores vacíos, no un fallo
# ---------------------------------------------------------------------
def test_data_window_is_read_from_the_database_name():
    assert data_window("gharchive-2026-10-08-9-24h") == ("2026-10-08 09:00", "2026-10-09 09:00", 24)
    assert data_window("gharchive-2026-10-08-23") == ("2026-10-08 23:00", "2026-10-09 00:00", 1)
    assert data_window("gharchive24h") == ("", "", None)


# Una función auxiliar: las dos claves que compare() lee de un lado que
# ha terminado.
def finished(time_s):
    return {"status": "finished", "time_s": time_s}


# PostgreSQL 0.4 s, Neo4j 0.1 s -> Neo4j, 0.4 / 0.1 = 4 veces más rápido.
# Y al revés: 0.5 / 0.1 = 5 veces, PostgreSQL más rápido.
def test_compare_says_who_was_faster_and_how_many_times():
    assert compare(finished(0.4), finished(0.1), 60) == ("neo4j", 4.0)
    assert compare(finished(0.1), finished(0.5), 60) == ("postgresql", 5.0)


# ---------------------------------------------------------------------
# Cuando un lado no ha terminado, su tiempo es desconocido — pero es como
# mínimo el límite de tiempo. Así que times_faster = límite / tiempo del
# otro lado es un MÍNIMO ("al menos 30 veces"). Cuando ninguno ha
# terminado: "neither" (ninguno), y ningún número (None).
# ---------------------------------------------------------------------
def test_compare_with_a_timeout_gives_a_minimum():
    # Neo4j didn't finish in 60 s: PostgreSQL was at least 60 / 2 = 30 times faster.
    assert compare(finished(2.0), {"status": "timeout"}, 60) == ("postgresql", 30.0)
    assert compare({"status": "timeout"}, {"status": "skipped (timed out at a smaller depth)"}, 60) == ("neither", None)


# ---------------------------------------------------------------------
# Una función auxiliar que construye una ejecución cronometrada tal como
# la devuelve timed_run() en measure.py: el Outcome
# (docs_spanish/traversal.py), los segundos de CPU que usó el servidor de
# la base de datos, y lo ocupado que estaba el ordenador entero. Los
# valores por defecto describen una ejecución normal: 0.1 s de CPU,
# ordenador al 10 %.
# ---------------------------------------------------------------------
def run(seconds, cpu_s=0.1, machine_cpu=10.0):
    return {"outcome": Outcome("ok", seconds, 7), "cpu_s": cpu_s, "machine_cpu": machine_cpu}


# ---------------------------------------------------------------------
# La primera ejecución tardó 9 s (mientras se preparaba el plan). Se
# informa como first_run_s, pero NO se usa para el tiempo: las
# ejecuciones cronometradas son 0.2, 0.4, 0.3 s -> mediana 0.3. Sus
# segundos de CPU son 0.1, 0.4, 0.3 -> mediana 0.3, y
# cores_used = 0.3 / 0.3 = 1.0 (un núcleo ocupado durante toda la
# ejecución). Las cifras de trabajo ({"memory_mb": 1.5}) se copian tal
# cual.
# ---------------------------------------------------------------------
def test_side_summary_uses_the_median_and_ignores_the_first_run():
    summary = side_summary(Outcome("ok", 9.0, 7), [run(0.2), run(0.4, 0.4), run(0.3, 0.3)], {"memory_mb": 1.5}, "finished")
    assert summary["time_s"] == 0.3 and summary["first_run_s"] == 9.0
    assert summary["cpu_s"] == 0.3 and summary["cores_used"] == 1.0
    assert summary["memory_mb"] == 1.5


# ---------------------------------------------------------------------
# Las dos reglas de "no fiable" (ver side_summary en
# docs_spanish/measure.py), más un caso que no debe ser ninguna de las
# dos:
#   0.1 s y 0.5 s             dispersión de 5x, más de 3x     -> noisy
#   0.1 s dos veces, CPU 95 % ordenador ocupado, más de 80 % -> busy
#   0.1 s y 0.12 s            1.2x, CPU 10 %                  -> tranquilo
# `assert not x` — pasa cuando x es False.
# ---------------------------------------------------------------------
def test_side_summary_flags_noisy_or_busy_runs():
    assert side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.5)], {}, "finished")["noisy"]          # 5x spread
    assert side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.1, machine_cpu=95)], {}, "finished")["busy"]
    calm = side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.12)], {}, "finished")
    assert not calm["noisy"] and not calm["busy"]


# ---------------------------------------------------------------------
# LA FORMA DE UN CSV DE RESULTADOS
#
# El usuario pidió esta disposición: primero la información del test,
# después un bloque de PostgreSQL y un bloque de Neo4j con las MISMAS
# columnas, uno al lado del otro, y después la comparación. Este test se
# asegura de que la disposición no pueda ir cambiando sin querer:
#
# 1. from measure import ... DENTRO de la función: un import se puede
#    escribir en cualquier sitio; aquí deja estos tres nombres junto al
#    único test que los necesita.
#
# 2. COLUMNS[:len(TEST_COLUMNS)] == TEST_COLUMNS
#    Las primeras columnas son exactamente las del test, en orden.
#
# 3. pg = [c[len("pg_"):] for c in COLUMNS if c.startswith("pg_")]
#    Todas las columnas que empiezan por "pg_", sin ese prefijo
#    (c[3:] = el texto desde la posición 3: "pg_time_s" -> "time_s").
#    Lo mismo con "neo4j_". `pg == neo4j == SIDE_COLUMNS` es una
#    comparación ENCADENADA: las dos deben ser iguales a SIDE_COLUMNS,
#    así que los dos bloques contienen las mismas columnas EN EL MISMO
#    ORDEN.
#
# 4. El último assert comprueba que los bloques están uno junto al otro:
#    la primera columna de Neo4j va JUSTO DESPUÉS de la última de
#    PostgreSQL (su posición, .index(), es uno más), así que no hay
#    ninguna otra columna entre ellos.
# ---------------------------------------------------------------------
def test_results_columns_are_the_test_then_two_identical_blocks():
    from measure import COLUMNS, SIDE_COLUMNS, TEST_COLUMNS
    assert COLUMNS[:len(TEST_COLUMNS)] == TEST_COLUMNS
    pg = [c[len("pg_"):] for c in COLUMNS if c.startswith("pg_")]
    neo4j = [c[len("neo4j_"):] for c in COLUMNS if c.startswith("neo4j_")]
    assert pg == neo4j == SIDE_COLUMNS
    assert COLUMNS.index("neo4j_" + SIDE_COLUMNS[0]) == COLUMNS.index("pg_" + SIDE_COLUMNS[-1]) + 1


# ---------------------------------------------------------------------
# UN ARCHIVO POR MEDICIÓN, Y REUTILIZAR LOS ÚLTIMOS ACTORES
#
# El usuario quería que cada análisis dejara exactamente UN CSV, fácil de
# abrir y de entender. Este test comprueba las dos reglas que van con
# ello: el NOMBRE del archivo, y que los actores de partida se toman del
# ÚLTIMO archivo de la base de datos.
#
# FIXTURES — tmp_path y monkeypatch entre los paréntesis
#   Cuando una función de test tiene parámetros con estos nombres
#   especiales, pytest los PREPARA y se los pasa (una "fixture"):
#   tmp_path     una carpeta temporal nueva y VACÍA (un Path), distinta
#                para cada test, que pytest limpia después. El test puede
#                escribir archivos ahí sin tocar el results/ real.
#   monkeypatch  una ayuda para cambiar algo TEMPORALMENTE:
#                monkeypatch.setattr(measure, "RESULTS_DIR", tmp_path)
#                sustituye measure.RESULTS_DIR por la carpeta temporal
#                solo mientras dura este test; después pytest vuelve a
#                poner el valor real. Así, results_file() y
#                previous_starts() buscan en la carpeta temporal.
#
# Los imports se escriben dentro del test: `import measure` (el módulo
# entero, para poder sustituir su RESULTS_DIR), csv y datetime.
#
# 1. results_file(...) con 2026-11-19 10:30:00 debe dar el nombre
#    "<base de datos>_2026-11-19_10-30-00.csv" (.name: solo el nombre del
#    archivo, sin la carpeta).
# 2. En la carpeta, todavía vacía, previous_starts() no encuentra ningún
#    archivo: [].
# 3. Se escriben dos archivos de medición falsos con csv.DictWriter (ver
#    docs_spanish/measure.py), uno del 18 de noviembre con el actor 1, y
#    otro del 19 de noviembre con el actor 2. Cada uno contiene la
#    cabecera y UNA línea; las columnas que no se dan quedan vacías.
# 4. previous_starts() debe devolver solo el actor del ÚLTIMO archivo:
#    [2]. (Los nombres de archivo se ordenan por orden temporal, ver
#    results_file().)
# ---------------------------------------------------------------------
def test_each_measurement_gets_its_own_file_and_reuses_the_latest_actors(tmp_path, monkeypatch):
    import csv
    from datetime import datetime

    import measure
    monkeypatch.setattr(measure, "RESULTS_DIR", tmp_path)
    path = measure.results_file("gharchive-2026-10-08-9-24h", datetime(2026, 11, 19, 10, 30, 0))
    assert path.name == "gharchive-2026-10-08-9-24h_2026-11-19_10-30-00.csv"
    assert measure.previous_starts("gharchive-2026-10-08-9-24h") == []

    for name, actor_id in (("2026-11-18_09-00-00", 1), ("2026-11-19_10-30-00", 2)):
        with open(tmp_path / f"gharchive-2026-10-08-9-24h_{name}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=measure.COLUMNS)
            writer.writeheader()
            writer.writerow({"database": "gharchive-2026-10-08-9-24h", "start_group": "top", "start_rank": 1,
                             "start_actor_id": actor_id, "start_login": "x", "start_reach_1_hop": 3})
    # The latest measurement wins.
    assert [a["actor_id"] for a in measure.previous_starts("gharchive-2026-10-08-9-24h")] == [2]
