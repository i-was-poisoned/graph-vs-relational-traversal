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
#   - los cuatro scripts que se prueban: docs_spanish/choose_starts.py,
#     docs_spanish/measure.py, docs_spanish/traversal.py y
#     docs_spanish/analyze.py
#
# Lo que es NUEVO aquí: pytest.raises (comprobar que una función RECHAZA
# una entrada incorrecta), y comprobar que un resultado NO depende del
# orden de la entrada. Los tests sirven además como una descripción
# precisa, y ejecutable, de las reglas de la investigación: qué actores
# se eligen, en qué orden se ejecutan los dos lados y cómo se resumen los
# tiempos.
#
# Su papel en el proyecto: comprobar la lógica propia de los scripts de
# la investigación — las partes que no necesitan base de datos — para
# que un error en una regla se detecte en un segundo, y no después de
# horas de mediciones.
#
# Cómo ejecutar los tests reales:   python -m pytest
########################################################################

"""Unit tests for the research scripts' own logic (no network, no databases).

choose_starts.py (which actors), measure.py (the alternating order),
traversal.py (the Cypher text) and analyze.py (the summaries).

Run with:  python -m pytest
"""

# Esta vez se importa el propio pytest (los archivos de tests anteriores
# no lo necesitaban): solo para pytest.raises, en los tests del recorrido
# de más abajo.
import pytest

# ---------------------------------------------------------------------
# Las funciones que se prueban. `from analyze import ...` funciona porque
# pytest.ini añade scripts/ a la ruta de búsqueda de Python
# (pythonpath = scripts). Todas son funciones PURAS — reciben datos
# normales y devuelven datos normales — así que se pueden probar sin
# tener PostgreSQL ni Neo4j en marcha.
# ---------------------------------------------------------------------
from analyze import summarise_actor, summary
from choose_starts import choose, pick_median, pick_top
from measure import run_order
from traversal import cypher_reach


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
# choose() junta los dos grupos, como las filas de starts.csv.
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


# ---------- measure: alternating order ----------

# La regla de equidad de measure.py (ver docs_spanish/measure.py,
# run_order): en las repeticiones impares va primero PostgreSQL, en las
# pares Neo4j.
def test_run_order_alternates_which_side_goes_first():
    assert run_order(1) == ("postgresql", "neo4j")
    assert run_order(2) == ("neo4j", "postgresql")
    assert run_order(3) == ("postgresql", "neo4j")


# ---------- traversal: the Cypher text ----------

# cypher_reach(3) debe contener el patrón de longitud variable {1,3} ("de
# 1 a 3 saltos") y el parámetro $start. `"..." in texto` es True si el
# fragmento aparece en cualquier parte del texto.
def test_cypher_reach_writes_the_depth_into_the_pattern():
    assert "{1,3}" in cypher_reach(3)
    assert "$start" in cypher_reach(3)


# ---------------------------------------------------------------------
# pytest.raises — COMPROBAR QUE ALGO FALLA
#
# A veces el comportamiento correcto ES un error: una profundidad de 0 no
# tiene sentido, y cypher_reach debe rechazarla con un ValueError en lugar
# de construir una consulta rota.
#     with pytest.raises(ValueError):
#         <código>
# significa "el código de dentro debe lanzar un ValueError". Si lo hace,
# pytest lo captura y el test PASA. Si no lanza nada (o lanza otro tipo
# de error), el test FALLA.
# ---------------------------------------------------------------------
def test_cypher_reach_refuses_depth_zero():
    with pytest.raises(ValueError):
        cypher_reach(0)


# ---------- analyze ----------

# ---------------------------------------------------------------------
# Una función auxiliar que construye una línea de runs.csv tal como la
# daría csv.DictReader: todos los valores son TEXTO (str(...)), igual que
# en el archivo real. Los valores por defecto describen una ejecución
# normal que ha terminado: status "ok", respuesta "7", CPU al 10 %.
# ---------------------------------------------------------------------
def run(run_number, seconds, status="ok", count="7", cpu="10"):
    return {"run": str(run_number), "seconds": str(seconds), "status": status, "count": count,
            "machine_cpu_percent": cpu}


# ---------------------------------------------------------------------
# La ejecución 0 tardó 9 s (la primera ejecución, mientras se prepara el
# plan). Si se contara, el máximo sería 9.0 y la mediana 0.35. Sin ella:
# las ejecuciones cronometradas son 0.2, 0.4, 0.3 -> mediana 0.3, mínimo
# 0.2, máximo 0.4, tres terminadas, y la respuesta 7 (ahora un número, no
# texto).
# ---------------------------------------------------------------------
def test_summary_of_an_actor_ignores_the_first_run():
    result = summarise_actor([run(0, 9.0), run(1, 0.2), run(2, 0.4), run(3, 0.3)])
    assert result["median_s"] == 0.3 and result["min_s"] == 0.2 and result["max_s"] == 0.4
    assert result["finished"] == 3 and result["count"] == 7


# Solo la ejecución 0, y agotó el tiempo (así que measure.py se saltó las
# repeticiones): el timeout tiene que contarse igualmente, y no hay ningún
# tiempo.
def test_summary_of_an_actor_counts_timeouts():
    result = summarise_actor([run(0, 60, "timeout", "")])
    assert result["timeouts"] == 1 and result["median_s"] is None


# ---------------------------------------------------------------------
# Las dos reglas de "ruidoso" (ver docs_spanish/analyze.py), más un caso
# que NO debe ser ruidoso:
#   0.1 s y 0.5 s             dispersión de 5x, más de 3x     -> ruidoso
#   0.1 s dos veces, CPU 95 % ordenador ocupado, más de 80 % -> ruidoso
#   0.1 s y 0.12 s            1.2x, CPU 10 %                  -> no ruidoso
# `assert not x` — pasa cuando x es False.
# ---------------------------------------------------------------------
def test_noisy_when_spread_is_large_or_computer_busy():
    assert summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.5)])["noisy"]          # 5x spread
    assert summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.1, cpu="95")])["noisy"]  # busy
    assert not summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.12)])["noisy"]


# ---------------------------------------------------------------------
# El cociente principal: mediana de PostgreSQL 0.4 s, la de Neo4j 0.1 s,
# mismo grupo y profundidad -> 0.4 / 0.1 = 4.0, "PostgreSQL 4 veces más
# lento" (Neo4j más rápido). Las filas imitan la salida de per_actor().
# by_system: las líneas del resumen en un diccionario con el lado como
# clave, para elegir la de PostgreSQL.
# ---------------------------------------------------------------------
def test_group_summary_gives_postgresql_vs_neo4j():
    rows = [
        {"group": "top", "actor_id": 1, "depth": 2, "system": "postgresql", "median_s": 0.4, "timeouts": 0,
         "errors": 0, "noisy": False},
        {"group": "top", "actor_id": 1, "depth": 2, "system": "neo4j", "median_s": 0.1, "timeouts": 0,
         "errors": 0, "noisy": False},
    ]
    by_system = {r["system"]: r for r in summary(rows)}
    assert by_system["postgresql"]["postgresql_vs_neo4j"] == 4.0
