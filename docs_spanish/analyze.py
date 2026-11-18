########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/analyze.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su
# propósito es enseñar, no ejecutarse. El script real y "limpio" (sin nada
# de este comentario) es scripts/analyze.py.
#
# Lee antes estas copias anotadas; lo que explican NO se repite aquí:
#   - download_gharchive.py   argparse, Path, main() y la protección __name__
#   - extract_csv.py          open(..., newline=""), sorted(...), conjuntos
#   - load_neo4j.py           csv.DictReader
#   - summarize_data.py       collections.defaultdict (la idea básica)
#   - pipeline.py             RawDescriptionHelpFormatter
#   - measure.py              qué contiene runs.csv (la ejecución 0, las
#                             ejecuciones cronometradas, status, la carga
#                             del ordenador), csv.DictWriter, lambda, dict
#                             comprehensions, `**` dentro de un dict, y la
#                             organización de results/ en una carpeta por
#                             fecha y hora
#
# Lo que es NUEVO aquí — convertir un montón de ejecuciones cronometradas
# en unos pocos números en los que se pueda confiar:
#   - la MEDIANA (y por qué no la media), el mínimo y el máximo;
#   - ignorar la ejecución 0;
#   - marcar las ejecuciones RUIDOSAS (dispersión de más de 3x, o el
#     ordenador por encima del 80 % de CPU);
#   - agrupar líneas por una clave que es una tupla, con defaultdict(list);
#   - el COCIENTE PostgreSQL / Neo4j (por encima de 1: Neo4j más rápido);
#   - results/all_databases.csv, para comparar VOLÚMENES de datos uno al
#     lado del otro.
#
# Cómo está pensado para ejecutarse — normalmente como último paso de
# research.sh:
#     ./research.sh --database gharchive-2026-08-27-12-6h
# o por sí solo, a través de run.sh:
#     ./run.sh scripts/analyze.py --database gharchive-2026-08-27-12-6h
#     ./run.sh scripts/analyze.py --all
# (No necesita conectarse a ninguna base de datos: solo lee archivos CSV.)
########################################################################

"""Summarise the measurements made by measure.py.

For one database, it reads its latest measurement (results/<database>/<date-time>/)
and writes, in that same folder:

    per_actor.csv   for every actor, depth and side: median, minimum and maximum
                    time of the timed runs, how many finished, timed out or
                    failed, the answer, and a warning if the runs were noisy
    summary.csv     the same per group (top / median) and depth: the median over
                    the actors, and how many times slower PostgreSQL was than
                    Neo4j (above 1: Neo4j faster; below 1: PostgreSQL faster)

It also rebuilds results/all_databases.csv: one line per database, group, depth
and side, from the latest measurement of every database, to compare volumes.

A run is "noisy" if its slowest timed run took more than NOISY_SPREAD times its
fastest, or if the computer was very busy (CPU above BUSY_CPU %) during it.

Usage:
    ./run.sh scripts/analyze.py --database gharchive-2026-08-27-12-6h
    ./run.sh scripts/analyze.py --all
"""

# ---------------------------------------------------------------------
# statistics — un módulo de la biblioteca estándar con los resúmenes
# numéricos habituales (media, mediana, desviación típica...). Aquí solo
# se usa statistics.median().
#
# defaultdict — ver docs_spanish/summarize_data.py. Aquí se usa como
# defaultdict(list): un diccionario en el que una clave que no existe
# empieza como una LISTA VACÍA, así que `grouped[key].append(x)` funciona
# incluso la primera vez que aparece una clave.
#
# Ni psycopg ni neo4j: este script solo lee los archivos CSV que escribió
# measure.py.
# ---------------------------------------------------------------------
import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import choose_starts

# ---------------------------------------------------------------------
# Los dos umbrales para considerar una medición "ruidosa" (poco fiable):
#
#   NOISY_SPREAD = 3.0   la ejecución cronometrada más lenta tardó más de
#                        3 veces lo que la más rápida. La misma consulta
#                        sobre los mismos datos debería tardar más o menos
#                        lo mismo en cada ejecución; una diferencia de 3x
#                        significa que algo más ha interferido.
#   BUSY_CPU = 80.0      la CPU del ordenador estaba por encima del 80 %
#                        justo antes de una ejecución (machine_cpu_percent,
#                        de measure.py): otros programas competían por el
#                        procesador.
#
# Una línea ruidosa se conserva y se resume igualmente — solo se MARCA,
# para que sepas qué números hay que tomar con cuidado (o volver a medir).
# ---------------------------------------------------------------------
NOISY_SPREAD = 3.0
BUSY_CPU = 80.0
SYSTEMS = ("postgresql", "neo4j")


# ---------------------------------------------------------------------
# def latest_measurement(database) — la carpeta de resultados más reciente
#
# folder.glob("*") lista todo lo que hay dentro de results/<database>/.
# Solo las carpetas que contienen un runs.csv son mediciones (starts.csv
# también vive ahí, y no lo es).
#
# sorted(...) — los nombres de las carpetas son fechas como
# 2026-11-18_14-05-31, así que el orden alfabético ES el orden temporal;
# measurements[-1] es la más reciente.
#
# `... if folder.exists() else []` — si la base de datos no se ha medido
# nunca, puede que la carpeta ni exista: se usa una lista vacía en lugar
# de fallar. En cualquier caso, una lista vacía da un mensaje
# FileNotFoundError claro.
# \" dentro de un texto "..." es un carácter de comillas dobles literal.
# ---------------------------------------------------------------------
def latest_measurement(database: str) -> Path:
    folder = choose_starts.RESULTS_DIR / database
    measurements = sorted(p for p in folder.glob("*") if (p / "runs.csv").exists()) if folder.exists() else []
    if not measurements:
        raise FileNotFoundError(f"No measurement of \"{database}\" yet: run measure.py --database {database}")
    return measurements[-1]


# Todas las líneas de runs.csv, como una lista de diccionarios (los valores son TEXTO).
def read_runs(folder: Path) -> list[dict]:
    with open(folder / "runs.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------
# def summarise_actor(runs) — UN actor, UNA profundidad, UN lado -> una línea
#
# `runs` contiene las líneas de runs.csv de esa combinación: la ejecución
# 0 más las ejecuciones cronometradas 1..5. Recuerda que todos los valores
# son texto, de ahí int(...) y float(...).
# ---------------------------------------------------------------------
def summarise_actor(runs: list[dict]) -> dict:
    # -----------------------------------------------------------------
    # timed — solo las ejecuciones 1, 2, 3...: la ejecución 0 se IGNORA
    # para los tiempos. Incluye trabajo que se hace una sola vez (preparar
    # el plan de la consulta — unos 5 s para la primera consulta de una
    # forma nueva en Neo4j — y traer los datos a memoria), así que
    # describiría "la primera vez", no el recorrido. Ver
    # docs_spanish/measure.py, paso 1.
    #
    # ok — los tiempos (como números) de las ejecuciones cronometradas que
    # TERMINARON. Una ejecución que agotó el tiempo también tiene un
    # "seconds" (el tiempo hasta que se detuvo), pero no es un tiempo real
    # y no se debe mezclar con los demás.
    # -----------------------------------------------------------------
    # runs: the lines of ONE actor, depth and side. Run 0 is the first run: not a result.
    timed = [r for r in runs if int(r["run"]) >= 1]
    ok = [float(r["seconds"]) for r in timed if r["status"] == "ok"]
    # -----------------------------------------------------------------
    # statuses — "ok" / "timeout" / "error" de las ejecuciones
    # cronometradas, para contarlos más abajo. `A or B` da A si A no está
    # vacío, y B si lo está: cuando NO hay ejecuciones cronometradas (ese
    # lado ya agotó el tiempo en la ejecución 0, así que measure.py se
    # saltó las repeticiones), se usa el status de la ejecución 0, para
    # que el timeout aparezca igualmente en los recuentos.
    #
    # counts — un CONJUNTO con las respuestas que dieron las ejecuciones
    # que terminaron. Un conjunto guarda cada valor una sola vez: si todas
    # las ejecuciones dijeron 1234, el conjunto es {1234}. Más de un valor
    # significaría que la misma consulta dio respuestas distintas — un
    # error. (r["count"] != "": se salta una celda vacía.)
    #
    # busy — any(...) es True si AL MENOS UN elemento es True. Para cada
    # ejecución cronometrada: ¿hay un dato de CPU (`r[...] and`: una celda
    # vacía cuenta como falso, así que nunca se intenta float("")) y está
    # por encima de BUSY_CPU?
    #
    # spread — la más lenta / la más rápida. Solo tiene sentido con al
    # menos 2 ejecuciones terminadas, y sin dividir entre 0; si no, None
    # ("no hay dispersión de la que hablar").
    # -----------------------------------------------------------------
    statuses = [r["status"] for r in timed] or [r["status"] for r in runs]
    counts = {int(r["count"]) for r in runs if r["status"] == "ok" and r["count"] != ""}
    busy = any(r["machine_cpu_percent"] and float(r["machine_cpu_percent"]) > BUSY_CPU for r in timed)
    spread = (max(ok) / min(ok)) if len(ok) >= 2 and min(ok) > 0 else None
    # -----------------------------------------------------------------
    # La línea para per_actor.csv.
    #
    # median_s — LA MEDIANA, NO LA MEDIA. Se ordenan los tiempos y se toma
    # el del medio (con un número par de valores, la media de los dos del
    # medio). ¿Por qué no la media? Porque las perturbaciones de un
    # benchmark solo hacen las ejecuciones MÁS LENTAS, nunca más rápidas:
    # una ejecución afectada por un análisis del antivirus, p. ej. 0.30,
    # 0.31, 0.29, 0.30, 3.00 s, sube la media a 0.84 s — un tiempo que no
    # tardó ninguna ejecución — mientras que la mediana se queda en
    # 0.30 s. La mediana ignora unos pocos valores atípicos.
    #
    # min_s / max_s — las ejecuciones terminadas más rápida y más lenta:
    # muestran cuánto se dispersan las ejecuciones alrededor de la mediana.
    #
    # `... if ok else None` — si ninguna ejecución terminó, no hay ningún
    # tiempo; None se convierte en una celda vacía en el CSV.
    #
    # statuses.count("ok") — list.count(x) cuenta cuántos elementos son
    # iguales a x.
    #
    # count — next(iter(counts)) saca el único valor del conjunto (un
    # conjunto no tiene [0]: iter() lo recorre y next() toma el primer
    # elemento). Solo cuando hay exactamente UNA respuesta; si no, None,
    # que analyse() muestra como advertencia.
    #
    # noisy — True si el ordenador estaba ocupado O la dispersión superó
    # 3x. bool(...) asegura que el valor sea exactamente True/False.
    # -----------------------------------------------------------------
    return {
        "median_s": statistics.median(ok) if ok else None,
        "min_s": min(ok) if ok else None,
        "max_s": max(ok) if ok else None,
        "finished": statuses.count("ok"),
        "timeouts": statuses.count("timeout"),
        "errors": statuses.count("error"),
        "count": next(iter(counts)) if len(counts) == 1 else None,
        "noisy": bool(busy or (spread is not None and spread > NOISY_SPREAD)),
    }


# ---------------------------------------------------------------------
# def per_actor(runs) — AGRUPAR las líneas y después resumir cada grupo
#
# grouped[(group, actor_id, depth, system)].append(r)
#   La clave es una TUPLA de cuatro valores: una tupla puede ser clave de
#   un diccionario, así que todas las líneas con el mismo actor,
#   profundidad y lado acaban en la misma lista. defaultdict(list) crea
#   esa lista la primera vez que aparece una clave. actor_id y depth se
#   convierten a int para que al ordenar la profundidad 10 vaya después
#   de la 9 (como texto, "10" < "9").
#
# for (group, actor_id, depth, system), lines in sorted(grouped.items()):
#   .items() da pares (clave, valor); la tupla de la clave se DESEMPAQUETA
#   en cuatro nombres en la propia línea del for. sorted() los ordena por
#   grupo, después actor, después profundidad, después lado.
#
# {..., **summarise_actor(lines)} — las cuatro columnas que identifican la
# línea, seguidas de todas las columnas del resumen (`**` como en
# measure.py).
# ---------------------------------------------------------------------
def per_actor(runs: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in runs:
        grouped[(r["group"], int(r["actor_id"]), int(r["depth"]), r["system"])].append(r)
    rows = []
    for (group, actor_id, depth, system), lines in sorted(grouped.items()):
        rows.append({"group": group, "actor_id": actor_id, "depth": depth, "system": system, **summarise_actor(lines)})
    return rows


# ---------------------------------------------------------------------
# def summary(actor_rows) — DE LOS ACTORES A LOS GRUPOS
#
# Los 10 actores de un grupo (top o median) se combinan en una línea por
# grupo, profundidad y lado. La misma técnica de agrupación que en
# per_actor(), esta vez con una clave de tres valores (sin actor_id).
# ---------------------------------------------------------------------
def summary(actor_rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in actor_rows:
        grouped[(r["group"], r["depth"], r["system"])].append(r)
    # medians guarda la mediana de cada grupo, para poder calcular el
    # cociente después, cuando se conocen los dos lados.
    medians = {}
    rows = []
    # -----------------------------------------------------------------
    # El orden: "top" antes que "median", después por profundidad,
    # después por lado.
    #
    # El orden alfabético normal pondría "median" antes que "top". La
    # función key construye, para cada par (clave, valor) kv:
    #     (kv[0][0] != "top",) + kv[0][1:]
    #   kv[0] es la tupla de la clave (group, depth, system); kv[0][0] es
    #   el grupo. `kv[0][0] != "top"` es False para top y True para
    #   median, y False va antes que True al ordenar. `(x,)` — con la
    #   coma — es una tupla de un solo elemento, y `+` la une a
    #   (depth, system). Así top va primero y, dentro de cada grupo, la
    #   profundidad 1, 2, 3...
    # -----------------------------------------------------------------
    for (group, depth, system), lines in sorted(grouped.items(), key=lambda kv: (kv[0][0] != "top",) + kv[0][1:]):
        # -------------------------------------------------------------
        # El tiempo del grupo = la MEDIANA DE LAS MEDIANAS de los actores,
        # por la misma razón que antes: un actor poco habitual no arrastra
        # a todo el grupo. Los actores sin ninguna ejecución terminada
        # (median_s None) quedan fuera del tiempo, pero sí se cuentan en
        # "actors" — compara "actors" con "actors_finished" para ver
        # cuántos agotaron el tiempo.
        #
        # sum(r["noisy"] for r in lines) — True cuenta como 1 y False como
        # 0, así que sumar valores True/False cuenta los actores ruidosos.
        # -------------------------------------------------------------
        times = [r["median_s"] for r in lines if r["median_s"] is not None]
        medians[(group, depth, system)] = statistics.median(times) if times else None
        rows.append({"group": group, "depth": depth, "system": system, "actors": len(lines),
                     "actors_finished": len(times), "median_s": medians[(group, depth, system)],
                     "timeouts": sum(r["timeouts"] for r in lines), "errors": sum(r["errors"] for r in lines),
                     "noisy_actors": sum(r["noisy"] for r in lines)})
    # -----------------------------------------------------------------
    # EL COCIENTE — el número principal de la investigación.
    #
    # postgresql_vs_neo4j = tiempo mediano de PostgreSQL / tiempo mediano
    # de Neo4j, para el mismo grupo y profundidad. Es "cuántas veces más
    # lento fue PostgreSQL":
    #     4.0   PostgreSQL tardó 4 veces más -> Neo4j más rápido
    #     1.0   lo mismo
    #     0.25  PostgreSQL tardó una cuarta parte -> PostgreSQL más rápido
    # Ver cómo este número cruza el 1 a medida que crece la profundidad (o
    # el volumen de datos) responde a la pregunta de la investigación:
    # ¿DÓNDE empieza a ganar Neo4j?
    #
    # El mismo valor se escribe en las líneas de los dos lados (postgresql
    # y neo4j). medians.get(...) da None si un lado no tiene línea; `if pg
    # and neo` — solo cuando los dos tienen un tiempo (None, o un 0 que
    # haría fallar la división, dan None). round(..., 3): tres decimales.
    # -----------------------------------------------------------------
    for row in rows:
        pg, neo = medians.get((row["group"], row["depth"], "postgresql")), medians.get((row["group"], row["depth"], "neo4j"))
        row["postgresql_vs_neo4j"] = round(pg / neo, 3) if pg and neo else None
    return rows


# ---------------------------------------------------------------------
# def write_csv(rows, path) — una lista de diccionarios a un archivo CSV
#
# csv.DictWriter (docs_spanish/measure.py) con fieldnames=list(rows[0]):
# list(un_dict) da sus CLAVES, en el orden en que se añadieron, así que la
# cabecera se toma de la propia primera fila. (Si no hay nada que
# escribir -> se vuelve enseguida, porque no existiría rows[0].)
# writer.writerows(rows) escribe todas las líneas de una sola vez.
# ---------------------------------------------------------------------
def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------
# def fmt(seconds) — un tiempo, legible en pantalla
#
# Dos if/else de una línea encadenados:  A if cond1 else B if cond2 else C
#   None          -> "-"
#   menos de 1 s  -> en milisegundos: 0.0123 -> "12.3 ms"
#   si no         -> en segundos:     12.3456 -> "12.35 s"
# Especificaciones de formato dentro de { }: `,` añade un separador de
# miles (1,234.5) y `.1f` / `.2f` significan "1 / 2 decimales".
# ---------------------------------------------------------------------
def fmt(seconds) -> str:
    return "-" if seconds is None else f"{seconds * 1000:,.1f} ms" if seconds < 1 else f"{seconds:,.2f} s"


# ---------------------------------------------------------------------
# def analyse(database) — todo el trabajo para UNA base de datos
#
# Busca la medición más reciente, resume por actor y después por grupo,
# escribe los dos archivos CSV junto a runs.csv e imprime una tabla.
# ---------------------------------------------------------------------
def analyse(database: str) -> list[dict]:
    folder = latest_measurement(database)
    actor_rows = per_actor(read_runs(folder))
    summary_rows = summary(actor_rows)
    write_csv(actor_rows, folder / "per_actor.csv")
    write_csv(summary_rows, folder / "summary.csv")

    # -----------------------------------------------------------------
    # La tabla en pantalla: una línea por grupo y profundidad, con los dos
    # lados uno al lado del otro. Anchos de columna: `:<7` rellena hasta 7
    # caracteres, alineado a la izquierda; `:>12` rellena hasta 12,
    # alineado a la derecha (los números quedan alineados por la derecha).
    #
    # by_key — las filas del resumen en un diccionario con clave
    # (group, depth, system), para elegir la línea de PostgreSQL y la de
    # Neo4j del mismo grupo y profundidad. {(..., ...) for r in
    # summary_rows} es una SET comprehension: cada (group, depth) una sola
    # vez. Se ordena con "top" primero, como en summary().
    # .get(..., {}) da un diccionario vacío si falta un lado, así que
    # pg.get() / neo.get() de más abajo siguen funcionando (y dan None).
    # -----------------------------------------------------------------
    print(f'"{database}" (measurement {folder.name})')
    print(f"  {'group':<7} {'depth':>5}  {'PostgreSQL':>12}  {'Neo4j':>12}  {'PG / Neo4j':>10}  notes")
    by_key = {(r["group"], r["depth"], r["system"]): r for r in summary_rows}
    for group, depth in sorted({(r["group"], r["depth"]) for r in summary_rows}, key=lambda k: (k[0] != "top", k[1])):
        pg, neo = by_key.get((group, depth, "postgresql"), {}), by_key.get((group, depth, "neo4j"), {})
        # La columna "notes": timeouts y actores ruidosos, por lado, solo
        # cuando los hay (0 cuenta como falso, así que `if r.get(...)` lo
        # salta). `notes += [...]` añade los elementos de la segunda lista
        # a la primera.
        notes = [f"{s}: {r['timeouts']} timeouts" for s, r in (("PG", pg), ("Neo4j", neo)) if r.get("timeouts")]
        notes += [f"{s}: {r['noisy_actors']} noisy" for s, r in (("PG", pg), ("Neo4j", neo)) if r.get("noisy_actors")]
        ratio = pg.get("postgresql_vs_neo4j")
        # Una f-string DENTRO de una f-string: primero se da formato al
        # cociente, p. ej. "4.00x", y después ese texto se alinea a la
        # derecha en 10 caracteres. '; '.join(notes) pone las notas en una
        # línea, separadas por "; ".
        print(f"  {group:<7} {depth:>5}  {fmt(pg.get('median_s')):>12}  {fmt(neo.get('median_s')):>12}  "
              f"{'-' if ratio is None else f'{ratio:,.2f}x':>10}  {'; '.join(notes)}")
    # -----------------------------------------------------------------
    # Una advertencia de seguridad: líneas en las que las ejecuciones
    # TERMINARON pero no dieron una única respuesta (count es None).
    # measure.py ya comprueba que los dos lados coinciden en la ejecución
    # 0; esto detecta una consulta que da respuestas distintas de una
    # ejecución a otra. sum(1 for ...) cuenta las líneas que cumplen la
    # condición.
    # -----------------------------------------------------------------
    mismatches = sum(1 for r in actor_rows if r["count"] is None and r["finished"])
    if mismatches:
        print(f"  WARNING: {mismatches} actor/depth lines didn't give one single answer")
    print(f"  Written: {folder / 'per_actor.csv'} and {folder / 'summary.csv'}\n")
    # Las filas del resumen, cada una con el nombre de la base de datos y
    # la carpeta de la medición delante: las líneas que van a
    # all_databases.csv.
    return [{"database": database, "measurement": folder.name, **r} for r in summary_rows]


def main() -> None:
    # --database NOMBRE: resumir una base de datos. --all: todas las
    # medidas hasta ahora. action="store_true" hace de --all un
    # interruptor de encendido/apagado (True si se indica, False si no),
    # sin ningún valor detrás.
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", help="Summarise the latest measurement of this database")
    parser.add_argument("--all", action="store_true", help="Summarise every measured database")
    args = parser.parse_args()

    # -----------------------------------------------------------------
    # measured — los nombres de todas las bases de datos que tienen al
    # menos una medición: las carpetas de results/ (p.is_dir()) que
    # contienen algún <fecha-hora>/runs.csv. any(p.glob("*/runs.csv")) es
    # True si el patrón coincide con al menos un archivo.
    #
    # Con --database, se analiza esa; sin ninguna de las dos opciones,
    # parser.error se detiene con un mensaje (ver docs_spanish/measure.py).
    # -----------------------------------------------------------------
    root = choose_starts.RESULTS_DIR
    measured = sorted(p.name for p in root.glob("*") if p.is_dir() and any(p.glob("*/runs.csv"))) if root.exists() else []
    if args.database:
        analyse(args.database)
    elif not args.all:
        parser.error("give --database NAME or --all")

    # -----------------------------------------------------------------
    # results/all_databases.csv — COMPARAR VOLÚMENES
    #
    # Cada volumen de datos (6 horas, 1 día, una semana...) es su propia
    # base de datos (construida con build_hours.py) y se mide por
    # separado. Este archivo reúne las líneas de resumen de TODAS ellas en
    # una tabla, con una columna "database", para que puedas seguir p. ej.
    # "grupo top, profundidad 3" a medida que crece el volumen y ver dónde
    # el cociente cruza el 1.
    #
    # Se reconstruye cada vez, incluso después de analizar una sola base
    # de datos, así que siempre refleja la medición más reciente de cada
    # una.
    #
    # El cuerpo del bucle es UNA sola instrucción repartida en tres líneas
    # gracias a la `\` al final de la primera:
    #     all_rows += (analyse(database)) if args.all else (las mismas
    #                                     filas, construidas en silencio)
    # Con --all, analyse() imprime la tabla de cada base de datos y
    # escribe sus archivos. Si no, las mismas filas del resumen se
    # recalculan en silencio (sin imprimir y sin archivos por base de
    # datos), solo para rellenar all_databases.csv.
    # -----------------------------------------------------------------
    # Always refresh the comparison of all volumes measured so far.
    all_rows = []
    for database in measured:
        all_rows += analyse(database) if args.all else \
            [{"database": database, "measurement": latest_measurement(database).name, **r}
             for r in summary(per_actor(read_runs(latest_measurement(database))))]
    write_csv(all_rows, root / "all_databases.csv")
    if all_rows:
        print(f"Comparison of all {len(measured)} measured database(s): {root / 'all_databases.csv'}")


# La protección __name__: ver docs_spanish/download_gharchive.py.
if __name__ == "__main__":
    main()
