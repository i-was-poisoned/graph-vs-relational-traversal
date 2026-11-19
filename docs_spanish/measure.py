########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/measure.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su propósito
# es enseñar, no ejecutarse. El script real y "limpio" (sin nada de este
# comentario) es scripts/measure.py.
#
# Lee primero estas copias anotadas; lo que explican NO se repite aquí:
#   - download_gharchive.py   argparse, Path, main() y la protección __name__,
#                             try/except y lanzar errores
#   - extract_csv.py          el módulo csv, open(..., newline=""),
#                             mkdir(parents=True, exist_ok=True), sorted(...),
#                             conjuntos (sets)
#   - load_neo4j.py           csv.DictReader, driver.execute_query(..., database_=...)
#   - check_connections.py    conexiones de psycopg / neo4j, `with`, sys.exit
#   - pipeline.py             RawDescriptionHelpFormatter
#   - build_hours.py          datetime, timedelta, strptime, y cómo se
#                             LLAMAN las bases de datos
#                             (gharchive-<fecha>-<hora>[-<n>h])
#   - summarize_data.py       las dict comprehensions, los anchos de
#                             columna en las f-strings
#   - test_build_hours.py     lambda, iter() y next()
#   - traversal.py            las consultas de recorrido (SQL, Cypher "paths"
#                             y "levels"), el objeto Outcome (status /
#                             seconds / count / error), los límites de
#                             tiempo, y las cifras de TRABAJO (datos
#                             procesados, memoria) de EXPLAIN
#                             (ANALYZE, BUFFERS) y PROFILE
#   - choose_starts.py        cómo se eligen los 20 actores de partida
#                             (choose_in_both), statistics.median
#
# Lo que es NUEVO aquí — este es el script que produce de verdad los números
# de la investigación, así que la mayoría de las explicaciones tratan de
# MEDIR DE FORMA JUSTA y del archivo de resultados:
#   - UN archivo CSV por medición, results/<base de datos>_<fecha>_<hora>.csv.
#     Una línea = una pregunta respondida por las dos bases de datos
#     (csv.DictWriter);
#   - su disposición en tres partes: las columnas del test, después un
#     bloque de PostgreSQL y un bloque de Neo4j con columnas IDÉNTICAS, y
#     después la comparación;
#   - las cuatro cosas que se comparan: datos procesados, tiempo, espacio
#     (memoria y disco), y potencia de cálculo (segundos de CPU de los
#     procesos del SERVIDOR de cada base de datos, medidos con psutil);
#   - el módulo `re`: leer la ventana de tiempo de los datos a partir del
#     nombre de la base de datos;
#   - la "primera ejecución": no es un resultado, pero sirve para comprobar
#     que TODOS los lados dan el MISMO recuento;
#   - repeticiones cronometradas que van ROTANDO qué lado va primero;
#   - la mediana, "fiable", y quién fue "más rápido" (y cuántas veces);
#   - dejar de medir profundidades mayores en un lado cuando se queda sin
#     tiempo;
#   - reutilizar los actores de partida del último CSV de la misma base de
#     datos (--new-starts para volver a elegirlos).
#
# Cómo está pensado para ejecutarse — normalmente a través de research.sh,
# que comprueba las conexiones, pregunta qué base de datos medir y después
# ejecuta este script:
#     ./research.sh --database gharchive-2026-10-08-9-24h
# o solo, a través de run.sh (que carga .venv y las contraseñas):
#     ./run.sh scripts/measure.py --database gharchive-2026-10-08-9-24h
########################################################################

"""Measure the traversal in PostgreSQL and Neo4j, and write the results to ONE CSV file.

Every measurement (every analysis) writes its own file,
results/<database>_<date>_<time>.csv. One line of it = one question answered
by both databases: "from this starting actor, at this depth, in this volume of
data, how many actors are reached?". First the test, then PostgreSQL's figures
and Neo4j's figures side by side, with the same columns. Every column is
explained in the README ("What is measured, and why").

For the database given, it:

    1. chooses the 20 starting actors (choose_starts.py), or reuses the ones
       in the latest CSV of that database, so a repeated measurement
       starts from the same actors;
    2. for every actor and every depth from 1 to --max-depth:
       a. runs the traversal once on each side ("first run": it includes
          preparing the query) and checks that ALL sides give the same count;
       b. runs it --repeats more times, changing which side goes first each
          time, recording the time and the CPU used by each database server;
       c. runs it once more with EXPLAIN (ANALYZE, BUFFERS) / PROFILE, for the
          data read and the memory used inside each database;
    3. writes one line per actor, depth and Cypher version, and prints a summary.

If a side runs out of time at some depth, the deeper depths are skipped for that
side and actor (they can only be slower); their lines say so.

Usage:
    ./run.sh scripts/measure.py --database gharchive-2026-10-08-9-24h
    ./run.sh scripts/measure.py --database ... --max-depth 4 --repeats 5 --timeout 60 --cypher both
"""

# ---------------------------------------------------------------------
# Importaciones de la biblioteca estándar. Ya conocidas: argparse, csv,
# statistics, sys, datetime, timedelta, Path.
# Una nueva:
#   re  — EXPRESIONES REGULARES: patrones que describen la forma de un
#         texto (ver NAME y data_window() más abajo).
# ---------------------------------------------------------------------
import argparse
import csv
import re
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------
# import psutil
#
# Un paquete EXTERNO (instalado desde requirements.txt, como psycopg y
# neo4j): "process and system utilities" (utilidades de procesos y del
# sistema). Puede listar los programas (PROCESOS) que se están ejecutando
# en el ordenador, decir cuánto tiempo de procesador ha usado cada uno, y
# lo ocupado que está el ordenador entero.
#
# ¿Para qué necesita eso un benchmark? Por dos motivos:
#   - POTENCIA DE CÁLCULO: cuánta CPU gastó el SERVIDOR de cada base de
#     datos en una consulta (ver server_processes() y cpu_seconds() más
#     abajo);
#   - EQUIDAD: el portátil también se está usando para otras cosas
#     mientras corre la medición (un navegador, un análisis del antivirus,
#     actualizaciones de Windows...). Si una ejecución fue lenta porque el
#     ordenador estaba ocupado, queremos VERLO, en lugar de echarle la
#     culpa a la base de datos.
# ---------------------------------------------------------------------
import psutil

# ---------------------------------------------------------------------
# import choose_starts / import traversal
#
# Los scripts PROPIOS del proyecto, importados como paquetes (funciona
# porque están todos en la misma carpeta scripts/). Este script reutiliza:
#   choose_starts.choose_in_both                       los actores de partida
#   traversal.connect_postgres / connect_neo4j
#   traversal.run_postgres_reach / run_neo4j_reach     un recorrido cronometrado
#   traversal.postgres_work / neo4j_work               las cifras de trabajo
#   traversal.sql_joins / cypher_hops / CYPHER_VERSIONS
# Todos se explican en docs_spanish/traversal.py y
# docs_spanish/choose_starts.py.
# ---------------------------------------------------------------------
import choose_starts
import traversal

# ---------------------------------------------------------------------
# RESULTS_DIR — la carpeta de los archivos de resultados: <proyecto>/results
#
# (La misma receta con Path que PROJECT_DIR en load_postgres.py.) Cada
# medición escribe ahí UN archivo CSV, cuyo nombre lleva la base de datos
# y el momento en que empezó (ver results_file()), p. ej.
#     results/gharchive-2026-10-08-9-24h_2026-11-19_14-05-31.csv
# Un archivo contiene todo lo de una medición, y una medición nueva nunca
# toca una anterior. (Las versiones anteriores escribían varios archivos
# por medición — ejecuciones, trabajo, por actor, resumen — y resultaron
# demasiado difíciles de leer.)
# ---------------------------------------------------------------------
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# ---------------------------------------------------------------------
# LAS COLUMNAS DE UN CSV DE RESULTADOS — TRES PARTES
#
# El usuario pidió esta disposición: primero la información del TEST,
# después una tabla de PostgreSQL y una de Neo4j, una al lado de la otra,
# con las MISMAS columnas, para que cada base de datos se pueda leer por
# separado Y comparar columna por columna (pg_time_s junto a... el mismo
# sitio en el bloque de Neo4j: neo4j_time_s).
#
# 1. TEST_COLUMNS — qué datos, cuándo, y qué pregunta:
#   measured_at          cuándo empezó la medición (el mismo valor en
#                        todas sus líneas, para poder combinar archivos
#                        más adelante)
#   database             la base de datos medida
#   data_from_utc, data_to_utc, volume_hours
#                        la ventana de tiempo de los datos, leída del
#                        nombre de la base de datos (ver data_window())
#   graph_actors, graph_repos, graph_connections
#                        el tamaño del grafo (idéntico en los dos lados:
#                        se comprueba en graph_facts())
#   start_group, start_rank, start_actor_id, start_login, start_reach_1_hop
#                        el actor de partida (de choose_starts.py)
#   depth                cuántos saltos
#   cypher_version       qué versión de Cypher compara esta línea con el
#                        SQL: "paths" o "levels" (docs_spanish/traversal.py)
#   actors_reached       la respuesta, si todos los lados coinciden
#   answers_match        yes / no / unknown (no terminó nadie)
#   runs, timeout_s      cuántas ejecuciones cronometradas, y el límite de
#                        tiempo
#
# 2. SIDE_COLUMNS — la misma lista, usada DOS veces: una con el prefijo
#    "pg_" y otra con "neo4j_". Aquí están las cuatro cosas que se
#    comparan:
#   joins_or_hops        cuánto camino supone una profundidad: JOINs en
#                        SQL, relaciones recorridas en Cypher (2 por
#                        profundidad, ver traversal.sql_joins /
#                        cypher_hops)
#   status               finished / timeout / error / skipped (...)
#   time_s               TIEMPO: la MEDIANA de las ejecuciones
#                        cronometradas, en segundos
#   first_run_s          la primera ejecución (con la preparación de la
#                        consulta)
#   data_processed_mb    DATOS PROCESADOS: MB de páginas de 8 KB tocadas
#                        (una página usada dos veces cuenta dos veces)
#   data_from_disk_mb    la parte leída del disco
#   memory_mb            ESPACIO: la memoria que usó la consulta
#   temp_disk_mb         ESPACIO: archivos temporales en disco (solo
#                        PostgreSQL; queda VACÍA para Neo4j, que no tiene
#                        equivalente)
#   database_mb          ESPACIO: el tamaño de toda la base de datos en
#                        disco
#   cpu_s                POTENCIA DE CÁLCULO: segundos de CPU que usó el
#                        servidor de la base de datos (mediana de las
#                        ejecuciones cronometradas)
#   cores_used           cpu_s / time_s: cuántos núcleos del procesador
#                        estuvieron ocupados de media (2.0 = dos núcleos
#                        todo el tiempo)
#   reliable             yes / no, para ESTE lado (ver side_summary())
#
# 3. COMPARISON_COLUMNS — al final:
#   faster, times_faster quién fue más rápido, y cuántas veces (compare())
#
# COLUMNS — la lista completa, en orden, unida con `+` (lista + lista =
# una lista más larga). [f"pg_{c}" for c in SIDE_COLUMNS] es una list
# comprehension que pone el prefijo delante de cada nombre: "pg_status",
# "pg_time_s"... Los paréntesis ( ... ) alrededor de la expresión
# permiten que continúe en la línea siguiente.
#
# Tener las columnas como constantes hace que la cabecera y las filas
# nunca puedan discrepar (ver csv.DictWriter en main()), que todos los
# archivos tengan las mismas columnas, y
# tests/test_research.py comprueba la forma en tres partes.
# ---------------------------------------------------------------------
# The columns of every results CSV, in order: first the test (which data, when, which question),
# then two blocks with THE SAME columns, one for PostgreSQL ("pg_...") and one for Neo4j
# ("neo4j_..."), and at the end the comparison. Their meaning is explained in the README.
TEST_COLUMNS = [
    "measured_at", "database", "data_from_utc", "data_to_utc", "volume_hours",
    "graph_actors", "graph_repos", "graph_connections",
    "start_group", "start_rank", "start_actor_id", "start_login", "start_reach_1_hop",
    "depth", "cypher_version", "actors_reached", "answers_match", "runs", "timeout_s",
]
SIDE_COLUMNS = [
    "joins_or_hops", "status", "time_s", "first_run_s", "data_processed_mb", "data_from_disk_mb",
    "memory_mb", "temp_disk_mb", "database_mb", "cpu_s", "cores_used", "reliable",
]
COMPARISON_COLUMNS = ["faster", "times_faster"]
COLUMNS = (TEST_COLUMNS + [f"pg_{c}" for c in SIDE_COLUMNS] + [f"neo4j_{c}" for c in SIDE_COLUMNS]
           + COMPARISON_COLUMNS)

# ---------------------------------------------------------------------
# Los dos umbrales de "no fiable" (se usan en side_summary()):
#   BUSY_CPU      el ordenador entero por encima del 80 % de CPU durante
#                 una ejecución: la base de datos tuvo que compartir el
#                 procesador.
#   NOISY_SPREAD  la ejecución cronometrada más lenta tardó más de 3 veces
#                 lo que la más rápida: algo perturbó las ejecuciones.
#
# NAME — una EXPRESIÓN REGULAR (el módulo `re`)
#
# Una expresión regular es un pequeño lenguaje de patrones que describe
# la FORMA de un texto. re.compile(...) prepara el patrón una sola vez,
# para poder usarlo muchas veces. r"..." es una cadena RAW ("en bruto"):
# las barras invertidas se quedan tal como se escriben (si no, Python
# intentaría interpretar \d él mismo).
#
#   ^ ... $                 el principio y el final del texto: TODO el
#                           nombre debe coincidir, no solo un trozo
#   gharchive-              exactamente estos caracteres
#   (\d{4}-\d{2}-\d{2})     \d = un dígito; {4} = exactamente 4. Así,
#                           "2026-10-08". Los paréntesis forman un GRUPO:
#                           la parte que coincide se guarda, como grupo 1.
#   -(\d{1,2})              un guion, y después 1 o 2 dígitos: la hora
#                           (grupo 2)
#   (?:-(\d+)h)?            (?: ... ) es un grupo que NO se guarda, solo
#                           sirve para agrupar "-<n>h"; el ? de detrás
#                           hace OPCIONAL todo el conjunto. Dentro, \d+ =
#                           uno o más dígitos, guardados como grupo 3.
# Así, tanto "gharchive-2026-10-08-9-24h" como "gharchive-2026-10-08-23"
# coinciden (el segundo sin grupo 3). Los nombres son los que crea
# build_hours.py (database_name(), ver docs_spanish/build_hours.py).
# (La misma idea que el [[ =~ ]] de bash en docs_spanish/research.sh.)
# ---------------------------------------------------------------------
BUSY_CPU = 80.0       # computer CPU above this (percent) during a run: not reliable
NOISY_SPREAD = 3.0    # slowest run more than 3 times the fastest: not reliable
NAME = re.compile(r"^gharchive-(\d{4}-\d{2}-\d{2})-(\d{1,2})(?:-(\d+)h)?$")


# ---------- which data ----------

# ---------------------------------------------------------------------
# def data_window(database) -> tuple[str, str, int | None]:
#
# Convierte el nombre de una base de datos en la ventana de tiempo de sus
# datos, p. ej.
#   "gharchive-2026-10-08-9-24h" -> ("2026-10-08 09:00", "2026-10-09 09:00", 24)
#
# NAME.match(database) prueba el patrón sobre el texto: da un objeto
# MATCH (coincidencia) si el texto tiene esa forma, o None si no. Un
# nombre que no coincide (creado a mano, por ejemplo) no es un error: las
# tres columnas quedan vacías ("", "", None).
#
# match.group(1), (2), (3) — el texto con el que coincidió cada grupo
# guardado. Un grupo OPCIONAL que no coincidió con nada da None, así que
#   int(match.group(3) or 1)    sin parte "-<n>h" -> 1 hora.
# Los valores son TEXTO: int(...) los convierte en números.
#
# datetime.strptime(date, "%Y-%m-%d") lee la fecha (build_hours.py), a
# medianoche; + timedelta(hours=hour) la lleva a la hora de inicio; sumar
# `hours` más da el final. strftime("%Y-%m-%d %H:%M") los vuelve a
# escribir como texto. Las horas de GH Archive están en UTC, de ahí los
# nombres de columna _utc.
# ---------------------------------------------------------------------
def data_window(database: str) -> tuple[str, str, int | None]:
    # build_hours.py names each database after its data: gharchive-<date>-<hour>[-<n>h].
    match = NAME.match(database)
    if not match:
        return "", "", None
    date, hour, hours = match.group(1), int(match.group(2)), int(match.group(3) or 1)
    begin = datetime.strptime(date, "%Y-%m-%d") + timedelta(hours=hour)
    end = begin + timedelta(hours=hours)
    return begin.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M"), hours


# ---------------------------------------------------------------------
# def folder_size_mb(path) -> float | None:  — el tamaño de una carpeta en disco
#
#   path.is_dir()          ¿existe esa carpeta? Si no: None (desconocido).
#   path.rglob("*")        todos los archivos y carpetas que hay DENTRO, a
#                          cualquier profundidad (la "r" es de recursivo).
#   f.is_file()            se queda con los archivos (las carpetas no
#                          tienen tamaño propio).
#   f.stat().st_size       el tamaño de un archivo, en bytes.
#   sum(...) / 1024 ** 2   todo sumado, en MB.
# Se usa para el tamaño de la base de datos de Neo4j (graph_facts()).
# ---------------------------------------------------------------------
def folder_size_mb(path: Path) -> float | None:
    if not path.is_dir():
        return None
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024 ** 2


# ---------------------------------------------------------------------
# def graph_facts(conn, driver, database) -> dict:  — LOS DATOS, Y UNA COMPROBACIÓN
#
# Reúne las cifras que son iguales en todas las líneas de esta medición:
# el tamaño del grafo, y el de cada base de datos en disco.
#
# count = lambda q: ... — una función de una línea (lambda:
# test_build_hours.py) que ejecuta un recuento en Cypher y devuelve el
# número (records[0][0]: la primera columna de la primera fila).
#
# El lado de PostgreSQL: se cuentan las tres tablas, y
# pg_database_size(current_database()) — el tamaño en bytes de toda la
# base de datos en disco (tablas E índices), / 1024 ** 2 -> MB.
#
# LOS MISMOS DATOS EN LOS DOS LADOS: los recuentos de Neo4j (actores,
# repos, conexiones) se meten en una tupla y se comparan con los de
# PostgreSQL. Si difieren, las dos bases de datos no contienen el mismo
# grafo, y comparar su velocidad no tendría sentido: raise RuntimeError,
# que se captura al final del archivo (no se mide nada).
#
# EL TAMAÑO DE NEO4J EN DISCO: Neo4j no tiene pg_database_size. Sus bases
# de datos son carpetas dentro del directorio de datos del servidor, así
# que el script le pregunta al servidor dónde está (SHOW SETTINGS ...
# 'server.directories.data', en la base de datos especial "system") y
# mide la carpeta <data>/databases/<database> con folder_size_mb().
# `if records else None`: si no se puede leer el ajuste, el tamaño queda
# desconocido. (Esto funciona porque Neo4j Desktop corre en el mismo
# ordenador.)
#
# Las claves "pg_database_mb" y "neo4j_database_mb" son exactamente los
# nombres de columna de los dos bloques, así que van directamente a cada
# línea.
# ---------------------------------------------------------------------
def graph_facts(conn, driver, database: str) -> dict:
    count = lambda q: driver.execute_query(q, database_=database).records[0][0]
    facts = {
        "graph_actors": conn.execute("SELECT count(*) FROM actor").fetchone()[0],
        "graph_repos": conn.execute("SELECT count(*) FROM repo").fetchone()[0],
        "graph_connections": conn.execute("SELECT count(*) FROM actor_repo").fetchone()[0],
        "pg_database_mb": conn.execute("SELECT pg_database_size(current_database())").fetchone()[0] / 1024 ** 2,
    }
    neo4j = (count("MATCH (a:Actor) RETURN count(a)"), count("MATCH (r:Repo) RETURN count(r)"),
             count("MATCH ()-[c:INTERACTED_WITH]->() RETURN count(c)"))
    if neo4j != (facts["graph_actors"], facts["graph_repos"], facts["graph_connections"]):
        raise RuntimeError(f"The two databases don't hold the same data: PostgreSQL "
                           f"{facts['graph_actors']}/{facts['graph_repos']}/{facts['graph_connections']}, "
                           f"Neo4j {neo4j[0]}/{neo4j[1]}/{neo4j[2]} (actors/repos/connections)")
    # Neo4j's size on disk: the database's folder under the server's data directory.
    records = driver.execute_query("SHOW SETTINGS YIELD name, value WHERE name = 'server.directories.data' "
                                   "RETURN value", database_="system").records
    facts["neo4j_database_mb"] = folder_size_mb(Path(records[0]["value"]) / "databases" / database) if records else None
    return facts


# ---------- the CPU used by each database server ----------

# ---------------------------------------------------------------------
# def server_processes(system) -> list[psutil.Process]:  — ENCONTRAR LOS SERVIDORES
#
# La POTENCIA DE CÁLCULO se mide en el SERVIDOR de la base de datos, no
# en Python: los servidores son programas aparte (PROCESOS) que se
# ejecutan en el mismo ordenador.
#   PostgreSQL   se ejecuta como VARIOS procesos llamados postgres (uno
#                principal, uno por conexión, y algunos auxiliares).
#                Cuentan todos.
#   Neo4j        se ejecuta como UN programa Java (java.exe). Pero puede
#                haber otros programas Java en marcha, así que el proceso
#                solo se guarda si su LÍNEA DE COMANDOS (el programa y sus
#                argumentos, process.cmdline()) menciona neo4j.
#
# psutil.process_iter(["name"]) recorre todos los procesos del
# ordenador, con su nombre ya leído (process.info["name"]).
# `(... or "").lower()`: un nombre que falta pasa a ser "", y lower() hace
# que la comparación no distinga mayúsculas. name.startswith("postgres")
# es True para "postgres" y para "postgres.exe".
#
# try / except (psutil.Error, OSError): pass — algunos procesos pertenecen
# a Windows o a otro usuario, y preguntar por ellos se RECHAZA; otros
# terminan mientras los miramos. Esos simplemente se saltan (`pass` = no
# hacer nada). Una tupla de clases de error captura cualquiera de ellas.
# ---------------------------------------------------------------------
def server_processes(system: str) -> list[psutil.Process]:
    # PostgreSQL runs as several postgres processes; Neo4j as one Java process.
    found = []
    for process in psutil.process_iter(["name"]):
        name = (process.info["name"] or "").lower()
        try:
            if system == "postgresql" and name.startswith("postgres"):
                found.append(process)
            elif system == "neo4j" and name.startswith("java") and "neo4j" in " ".join(process.cmdline()).lower():
                found.append(process)
        except (psutil.Error, OSError):
            pass
    return found


# ---------------------------------------------------------------------
# def cpu_seconds(processes) -> dict[int, float]:
#
# Para cada proceso, el tiempo de CPU que ha usado DESDE QUE ARRANCÓ:
#   cpu.user     segundos que el procesador pasó ejecutando su propio
#                código
#   cpu.system   segundos que pasó Windows trabajando para él (leyendo
#                archivos...)
# La suma se guarda bajo el id del proceso (pid: "process id", un número
# que identifica a un programa en ejecución).
#
# Una lectura no significa nada por sí sola; timed_run() la lee ANTES y
# DESPUÉS de una consulta, y la diferencia es lo que costó la consulta. Un
# proceso que ha terminado (o que lo rechaza) se salta.
# ---------------------------------------------------------------------
def cpu_seconds(processes: list[psutil.Process]) -> dict[int, float]:
    times = {}
    for process in processes:
        try:
            cpu = process.cpu_times()
            times[process.pid] = cpu.user + cpu.system
        except (psutil.Error, OSError):
            pass
    return times


# ---------- running ----------

# ---------------------------------------------------------------------
# def sides(cypher) -> list[str]:  — QUÉ SE MIDE
#
# Un "lado" es una forma de responder a la pregunta:
#   "postgresql"     el SQL
#   "neo4j-paths"    Cypher, versión "paths"
#   "neo4j-levels"   Cypher, versión "levels"
# --cypher both da los tres; --cypher levels da PostgreSQL y solo esa
# versión. (cypher,) es una tupla con un solo elemento (la coma es lo que
# la convierte en tupla), así que las dos ramas dan algo que recorrer.
# ---------------------------------------------------------------------
def sides(cypher: str) -> list[str]:
    # The "sides" measured: PostgreSQL and one or two Cypher versions.
    versions = traversal.CYPHER_VERSIONS if cypher == "both" else (cypher,)
    return ["postgresql"] + [f"neo4j-{v}" for v in versions]


# ---------------------------------------------------------------------
# def run_order(all_sides, repeat) -> list[str]:  — QUÉ LADO VA PRIMERO
#
# ¿Por qué cambiar el orden? Cualquier cosa que cambie durante la
# medición afecta a quien esté ejecutándose en ese momento: abres una
# pestaña del navegador, el antivirus se despierta, el portátil se
# calienta y va más lento, Windows escribe en el disco... Si PostgreSQL se
# ejecutara SIEMPRE primero, cada una de esas perturbaciones caería en el
# mismo lado, en la misma posición. Rotar las reparte para que afecten a
# todos los lados por igual, y ninguno tenga una ventaja sistemática (por
# ejemplo, "el que se ejecuta segundo siempre encuentra los datos ya en
# la memoria del sistema operativo").
#
# LA ROTACIÓN, con tres lados [A, B, C]:
#   repeat 1 -> shift 0 -> [A, B, C]
#   repeat 2 -> shift 1 -> [B, C, A]
#   repeat 3 -> shift 2 -> [C, A, B]
#   repeat 4 -> shift 0 -> [A, B, C] otra vez
# `%` es el RESTO de una división: (repeat - 1) % 3 da 0, 1, 2, 0...
# all_sides[shift:] + all_sides[:shift] — dos SLICES (porciones) unidos:
# desde la posición `shift` hasta el final, y después el principio hasta
# `shift`.
# tests/test_research.py comprueba esta función (docs_spanish/test_research.py).
# ---------------------------------------------------------------------
def run_order(all_sides: list[str], repeat: int) -> list[str]:
    # Repetition 1 starts with the first side, repetition 2 with the second, and so on, so
    # anything else happening on the computer affects every side alike.
    shift = (repeat - 1) % len(all_sides)
    return all_sides[shift:] + all_sides[:shift]


# ---------------------------------------------------------------------
# def run_once(side, ...) — un recorrido en UN lado
#
# Un pequeño conmutador para que el resto del código pueda decir
# simplemente "ejecútalo en este lado" sin preocuparse de qué lado es. Las
# dos funciones devuelven un Outcome (status, seconds, count, error): ver
# docs_spanish/traversal.py.
#
# side.split("-", 1)[1] — parte el texto solo por el PRIMER "-" (el 1), y
# toma el segundo trozo: "neo4j-levels" -> ["neo4j", "levels"] ->
# "levels", la versión de Cypher.
# ---------------------------------------------------------------------
def run_once(side: str, conn, driver, database: str, start: int, depth: int, timeout: int):
    if side == "postgresql":
        return traversal.run_postgres_reach(conn, start, depth, timeout)
    return traversal.run_neo4j_reach(driver, database, start, depth, timeout, side.split("-", 1)[1])


# ---------------------------------------------------------------------
# def timed_run(...) -> dict:  — UNA EJECUCIÓN CRONOMETRADA, CON SU CPU
#
# 1. psutil.cpu_percent(interval=0.2) — observa el procesador durante
#    0,2 s y devuelve cuánto se ha usado, en porcentaje, contando TODOS
#    los programas. Se mide justo ANTES de la ejecución (no puede ser
#    durante: espera sus 0,2 s antes de volver). Dice lo ocupado que
#    estaba el ordenador.
#
# 2. procs = los procesos del servidor de este lado ("neo4j-paths" y
#    "neo4j-levels" usan los dos el servidor Neo4j). `A if condición
#    else B`: un if/else en una línea que da un valor.
#
# 3. Segundos de CPU ANTES, la ejecución, segundos de CPU DESPUÉS. El
#    tiempo de la propia ejecución se mide dentro de run_once() (el
#    Outcome), así que las lecturas de CPU no se le suman.
#
# 4. used = la CPU que gastó el servidor en esta ejecución: para cada
#    proceso, después menos antes, todo sumado. `if pid in before`: un
#    proceso que apareció entre medias no tiene "antes" y se deja fuera.
#    `if procs else None`: si no se encontró ningún proceso del servidor,
#    la CPU es DESCONOCIDA (None — no 0, que sería un valor real, y
#    erróneo).
#
# Nota: esto cuenta TODO lo que hizo el servidor durante la ejecución, así
# que la investigación supone que nadie más está usando las bases de datos
# en ese momento.
# ---------------------------------------------------------------------
def timed_run(side, processes, conn, driver, database, start, depth, timeout) -> dict:
    machine_cpu = psutil.cpu_percent(interval=0.2)
    procs = processes["postgresql" if side == "postgresql" else "neo4j"]
    before = cpu_seconds(procs)
    outcome = run_once(side, conn, driver, database, start, depth, timeout)
    after = cpu_seconds(procs)
    used = sum(after[pid] - before[pid] for pid in after if pid in before) if procs else None
    return {"outcome": outcome, "cpu_s": used, "machine_cpu": machine_cpu}


# ---------------------------------------------------------------------
# def work_figures(...) -> dict:  — LAS CIFRAS DE TRABAJO DE UN LADO
#
# Una ejecución extra, esta vez pidiendo a la base de datos que informe
# de lo que ha hecho: EXPLAIN (ANALYZE, BUFFERS) en PostgreSQL, PROFILE
# en Neo4j (explicados en docs_spanish/traversal.py). Devuelve un dict
# como
#   {"data_processed_mb": ..., "data_from_disk_mb": ..., "memory_mb": ...}
# (más "temp_disk_mb" en PostgreSQL). Va aparte de las ejecuciones
# cronometradas porque recoger esas cifras ya cuesta tiempo por sí mismo.
#
# try / except: si falla la recogida de las cifras, no merece la pena
# perder toda la medición: un dict vacío deja esas columnas vacías, y se
# imprime una nota breve. str(error)[:80] — los primeros 80 caracteres
# del mensaje (un SLICE del texto). end=" " mantiene la misma línea en
# pantalla.
# ---------------------------------------------------------------------
def work_figures(side, conn, driver, database, start, depth, timeout) -> dict:
    try:
        if side == "postgresql":
            return traversal.postgres_work(conn, start, depth, timeout)
        return traversal.neo4j_work(driver, database, start, depth, timeout, side.split("-", 1)[1])
    except Exception as error:
        print(f"(no work figures for {side}: {str(error)[:80]})", end=" ")
        return {}


# ---------------------------------------------------------------------
# def side_summary(first, runs, work, status) -> dict:  — LAS CIFRAS DE UN LADO
#
# Convierte las ejecuciones de un lado, para un actor y una profundidad,
# en los valores de su bloque de columnas (time_s, cpu_s, ...).
#
# Un lado que NO terminó (timeout, error, o saltado) no tiene tiempos:
# solo su estado, y el tiempo de la primera ejecución si la hubo (`if
# first else None`: un lado saltado no llegó a ejecutarse).
#
# Un lado que terminó:
#   time_s       statistics.median de las ejecuciones cronometradas. ¿Por
#                qué la MEDIANA y no la media? Una ejecución perturbada (el
#                antivirus...) puede ser 10 veces más lenta; tiraría de la
#                media hacia arriba, pero apenas mueve la mediana (el valor
#                del medio).
#   first_run_s  la primera ejecución, guardada aparte: incluye la
#                preparación del plan de la consulta, así que NO forma
#                parte de time_s.
#   cpu_s        la mediana de los segundos de CPU (de las ejecuciones en
#                las que se conoce).
#   cores_used   cpu_s / time_s. Ejemplo: 0,6 segundos de CPU en una
#                ejecución de 0,3 segundos = 2.0 — de media hubo dos
#                núcleos del procesador ocupados (una base de datos puede
#                trabajar en varios núcleos a la vez). No se calcula si la
#                CPU es desconocida o el tiempo es 0 (una división por
#                cero haría fallar el programa).
#   **{k: round(v, 3) for k, v in work.items() if v is not None}
#                las cifras de trabajo, redondeadas a 3 decimales; `**`
#                las copia en este dict (el mismo `**` que en
#                choose_starts.py). Un None (p. ej. Neo4j no informó de su
#                memoria) se deja fuera, así que su columna queda vacía.
#   noisy        la ejecución más lenta tardó más de NOISY_SPREAD (3) veces
#                lo que la más rápida. (`if min(times) > 0`: evita dividir
#                por 0.)
#   busy         any(...) es True si al menos UNA ejecución tuvo el
#                ordenador por encima de BUSY_CPU (80 %).
#   reliable     "no" si es noisy o busy, si no "yes" — la columna del
#                bloque de ESTE lado. Un "no" no significa que la cifra
#                esté mal; significa: cuidado, vuelve a medir si importa.
# round(..., 4): 4 decimales de segundo = una décima de milisegundo.
# tests/test_research.py comprueba esta función.
# ---------------------------------------------------------------------
def side_summary(first, runs: list[dict], work: dict, status: str) -> dict:
    # The figures of one side, for one actor and depth.
    if status != "finished":
        return {"status": status, "first_run_s": round(first.seconds, 4) if first else None}
    times = [r["outcome"].seconds for r in runs]
    cpus = [r["cpu_s"] for r in runs if r["cpu_s"] is not None]
    time_s = statistics.median(times)
    cpu_s = statistics.median(cpus) if cpus else None
    noisy = max(times) / min(times) > NOISY_SPREAD if min(times) > 0 else False
    busy = any(r["machine_cpu"] > BUSY_CPU for r in runs)
    return {
        "status": "finished",
        "time_s": round(time_s, 4),
        "first_run_s": round(first.seconds, 4),
        "cpu_s": round(cpu_s, 4) if cpu_s is not None else None,
        "cores_used": round(cpu_s / time_s, 2) if cpu_s is not None and time_s > 0 else None,
        **{k: round(v, 3) for k, v in work.items() if v is not None},
        "noisy": noisy,
        "busy": busy,
        "reliable": "no" if noisy or busy else "yes",
    }


# ---------------------------------------------------------------------
# def compare(pg, neo, timeout) -> tuple[str, float | None]:  — QUIÉN FUE MÁS RÁPIDO
#
# Da las dos columnas de la comparación, faster y times_faster:
#   los dos terminaron  gana el tiempo menor; times_faster = el tiempo más
#                       lento / el más rápido (0,4 s frente a 0,1 s ->
#                       4.0). Un empate es para PostgreSQL (<=).
#   solo uno terminó    el otro tardó COMO MÍNIMO el límite de tiempo (se
#                       le detuvo), así que timeout / el tiempo del
#                       ganador es un MÍNIMO: "al menos 30 veces más
#                       rápido".
#   ninguno terminó     "neither" (ninguno), y ningún número.
# Cada `... if pg["time_s"] else None` evita dividir por un tiempo de 0.
# ---------------------------------------------------------------------
def compare(pg: dict, neo: dict, timeout: int) -> tuple[str, float | None]:
    # Who was faster, and how many times. If only one side finished, the other took at
    # least the time limit, so "times_faster" is a minimum.
    if pg["status"] == "finished" and neo["status"] == "finished":
        if pg["time_s"] <= neo["time_s"]:
            return "postgresql", round(neo["time_s"] / pg["time_s"], 2) if pg["time_s"] else None
        return "neo4j", round(pg["time_s"] / neo["time_s"], 2) if neo["time_s"] else None
    if pg["status"] == "finished":
        return "postgresql", round(timeout / pg["time_s"], 2) if pg["time_s"] else None
    if neo["status"] == "finished":
        return "neo4j", round(timeout / neo["time_s"], 2) if neo["time_s"] else None
    return "neither", None


# ---------------------------------------------------------------------
# def measure_actor(actor, context, args, writer) — TODO LO DE UN ACTOR DE PARTIDA
#
# Para la profundidad 1, 2, 3 ... hasta --max-depth: los pasos a, b, c
# (los mismos del docstring del principio), y después d, que escribe las
# líneas. `context` es un dict construido en main() (las conexiones, los
# procesos de los servidores, los datos fijos), para que la función no
# necesite una larga lista de argumentos. `writer` es el csv.DictWriter
# del archivo CSV de esta medición.
#
# stopped — SALTARSE LAS PROFUNDIDADES MAYORES
#   Un dict {lado: el estado que recibe en las profundidades mayores}.
#   Bajar un salto más solo puede alcanzar MÁS actores, así que solo puede
#   tardar más: si la profundidad 4 no terminó en 60 s, la 5 tampoco
#   terminará. Saltársela ahorra 60 s x (1 + repeticiones) de espera
#   inútil por profundidad. Los OTROS lados siguen, mientras sigan
#   terminando; las líneas del lado saltado se escriben igualmente, con el
#   estado "skipped (...)".
# ---------------------------------------------------------------------
def measure_actor(actor: dict, context: dict, args, writer: csv.DictWriter) -> None:
    conn, driver, database = context["conn"], context["driver"], args.database
    all_sides = sides(args.cypher)
    stopped = {}   # side -> the status it gets at deeper depths
    # range(1, args.max_depth + 1): 1, 2, ..., max_depth (el final de un
    # range NO se incluye, de ahí el + 1).
    for depth in range(1, args.max_depth + 1):
        # Los lados que todavía se están midiendo en esta profundidad.
        active = [s for s in all_sides if s not in stopped]
        # end=" " — imprimir sin pasar a una línea nueva, para que el resto
        # del informe de esta profundidad aparezca después en la misma
        # línea.
        # flush=True — mostrarlo YA. Normalmente Python guarda el texto
        # impreso en un búfer durante un rato; sin flush, te quedarías
        # mirando una línea vacía durante una ejecución larga sin saber qué
        # profundidad se está midiendo.
        print(f"  depth {depth}:", end=" ", flush=True)

        # -------------------------------------------------------------
        # PASO a — LA "PRIMERA EJECUCIÓN": NO ES UN RESULTADO
        #
        # La primerísima vez que una base de datos ve una consulta con una
        # forma nueva, hace un trabajo extra, una sola vez, antes de
        # ejecutarla: analiza el texto y prepara (compila) un PLAN de
        # consulta. Neo4j en concreto puede tardar unos segundos en
        # planificar una consulta nueva; después el plan se guarda en su
        # caché y se reutiliza. La primera ejecución además trae los datos
        # a memoria. Contar ese tiempo mediría "la primera vez" en lugar
        # del propio recorrido, así que se informa aparte (first_run_s).
        #
        # SÍ se usa para algo importante: la COMPROBACIÓN DEL RECUENTO.
        # Cada lado responde "a cuántos actores se puede llegar"; si los
        # números difieren, una de las consultas (o los datos cargados)
        # está mal, y comparar su velocidad no tendría sentido.
        #
        # first = {s: run_once(...) for s in active} — una dict
        # comprehension: {"postgresql": Outcome, "neo4j-paths": Outcome...}.
        # counts = {o.count for ...} — un CONJUNTO con las respuestas de
        # los lados que terminaron: un conjunto guarda cada valor una sola
        # vez, así que si todos coinciden contiene UN número; dos o más
        # números = no coinciden.
        #
        # Un lado cuya primera ejecución no terminó va a `stopped`, con el
        # estado que recibirán sus profundidades MAYORES. (La `\` al final
        # de la línea continúa la sentencia en la línea siguiente.)
        # -------------------------------------------------------------
        # a. First run (not a result) and the count check.
        first = {s: run_once(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in active}
        counts = {o.count for o in first.values() if o.status == "ok"}
        for side, outcome in first.items():
            if outcome.status != "ok":
                stopped[side] = "skipped (timed out at a smaller depth)" if outcome.status == "timeout" \
                    else "skipped (failed at a smaller depth)"
        finished = [s for s in active if s not in stopped]

        # -------------------------------------------------------------
        # PASO b — LAS REPETICIONES CRONOMETRADAS
        #
        # ¿Por qué repetir? Un único tiempo no es fiable: la misma consulta
        # puede tardar 0,30 s, luego 0,45 s, luego 0,31 s, según lo que
        # esté haciendo el ordenador. Con varias ejecuciones se puede tomar
        # la MEDIANA, y ver cuánto se dispersan (side_summary()).
        #
        # runs = {s: [] for s in finished} — una lista vacía por lado; cada
        # ejecución cronometrada se añade a la lista de su lado.
        # run_order() va rotando qué lado va primero en cada repetición.
        # -------------------------------------------------------------
        # b. Timed repetitions, changing which side goes first.
        runs = {s: [] for s in finished}
        for repeat in range(1, args.repeats + 1):
            for side in run_order(finished, repeat):
                runs[side].append(timed_run(side, context["processes"], conn, driver, database,
                                            actor["actor_id"], depth, args.timeout))

        # PASO c — las cifras de trabajo, una ejecución extra por cada lado
        # que terminó (ver work_figures()).
        # c. The work done inside each database.
        work = {s: work_figures(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in finished}

        # -------------------------------------------------------------
        # Un resumen por lado, en tres casos:
        #   terminó                    todas sus cifras (side_summary())
        #   está en `first` pero no ok se ejecutó ahora y falló: su estado
        #                              ("timeout" o "error") y el tiempo de
        #                              la primera ejecución
        #   no está en `first`         saltado: se había parado en una
        #                              profundidad menor; el estado
        #                              guardado en `stopped`
        # -------------------------------------------------------------
        summaries = {}
        for side in all_sides:
            if side in finished:
                summaries[side] = side_summary(first[side], runs[side], work[side], "finished")
            elif side in first:
                summaries[side] = side_summary(first[side], [], {}, first[side].status)
            else:
                summaries[side] = side_summary(None, [], {}, stopped[side])

        # -------------------------------------------------------------
        # PASO d — ESCRIBIR LAS LÍNEAS
        #
        # Una línea por VERSIÓN DE CYPHER: cada línea compara PostgreSQL
        # con una versión de Cypher, así que las cifras de PostgreSQL
        # aparecen en las dos líneas (las mismas cifras, medidas una vez).
        #
        # pg / neo — el resumen, más joins_or_hops: {**dict, "clave": v}
        # copia el dict y añade una clave. El SQL cuenta joins, Cypher
        # relaciones recorridas (traversal.sql_joins / cypher_hops).
        #
        # all_sides[1:] — todos los lados salvo el primero (PostgreSQL).
        #
        # line = { ... } — las columnas del TEST:
        #   **context["facts"]   cuándo, qué datos, el tamaño del grafo, y
        #                        los tamaños de las dos bases de datos (ver
        #                        main())
        #   start_...            el actor de partida
        #   actors_reached       next(iter(counts)): el único número del
        #                        conjunto (iter + next toman su primer
        #                        elemento: test_build_hours.py), o "" si no
        #                        coinciden o no terminó nadie
        #   answers_match        "yes" (una respuesta), "no" (varias),
        #                        "unknown" (ninguna: el conjunto está vacío)
        #   faster, times_faster de compare()
        #
        # Después los dos BLOQUES, con el mismo bucle para los dos lados:
        # para cada nombre de SIDE_COLUMNS, la columna "pg_<nombre>" (o
        # "neo4j_<nombre>") recibe el valor de ese lado.
        # figures.get(key, "") — una celda vacía si el lado no tiene ese
        # valor (temp_disk_mb en Neo4j, todo salvo el estado en un lado que
        # no terminó). database_mb se salta aquí porque ya vino con los
        # datos fijos (facts).
        #
        # writer.writerow(line) — una línea del CSV. DictWriter pone cada
        # valor en la columna del mismo nombre, sea cual sea el orden del
        # dict (ver main()).
        # -------------------------------------------------------------
        # d. One line per Cypher version: the test, then PostgreSQL's block, then Neo4j's.
        pg = {**summaries["postgresql"], "joins_or_hops": traversal.sql_joins(depth)}
        for side in all_sides[1:]:
            neo = {**summaries[side], "joins_or_hops": traversal.cypher_hops(depth)}
            faster, times = compare(pg, neo, args.timeout)
            line = {
                **context["facts"],
                "start_group": actor["group"], "start_rank": actor["rank"], "start_actor_id": actor["actor_id"],
                "start_login": actor["login"], "start_reach_1_hop": actor["reached"],
                "depth": depth, "cypher_version": side.split("-", 1)[1],
                "actors_reached": next(iter(counts)) if len(counts) == 1 else "",
                "answers_match": "yes" if len(counts) == 1 else ("no" if counts else "unknown"),
                "runs": args.repeats, "timeout_s": args.timeout,
                "faster": faster, "times_faster": times,
            }
            for prefix, figures in (("pg", pg), ("neo4j", neo)):
                for key in SIDE_COLUMNS:
                    if key != "database_mb":   # the database sizes are already in the facts
                        line[f"{prefix}_{key}"] = figures.get(key, "")
            writer.writerow(line)

        # -------------------------------------------------------------
        # Terminar en pantalla la línea de esta profundidad.
        #
        # Si las respuestas difieren, las líneas ya se han escrito (con
        # answers_match = "no", para que el problema se vea en el
        # archivo), y `return` deja de medir este actor por completo;
        # main() sigue con el siguiente. sorted(counts) muestra el
        # conjunto ordenado.
        #
        # notes: los lados cuya primera ejecución NO fue "ok", p. ej.
        # "neo4j-paths timeout". ", ".join(...) une los trozos con comas;
        # los trozos los produce una EXPRESIÓN GENERADORA
        # (drop_databases.py). (f"..." if notes else "") añade la parte
        # entre paréntesis solo cuando hay algo que decir.
        #
        # all(...) — True si TODOS los lados se han parado: no queda nada
        # que medir para este actor, y `break` sale del bucle de
        # profundidades.
        # -------------------------------------------------------------
        if len(counts) > 1:
            print(f"ANSWERS DIFFER {sorted(counts)}; stopping this actor")
            return
        shown = next(iter(counts)) if counts else "?"
        notes = ", ".join(f"{s} {first[s].status}" for s in active if first[s].status != "ok")
        print(f"{shown} actors reached" + (f" ({notes})" if notes else ""))
        if all(s in stopped for s in all_sides):
            break


# ---------- starting actors, and the summary ----------

# ---------------------------------------------------------------------
# def results_file(database, measured_at) -> Path:  — EL ARCHIVO DE ESTA MEDICIÓN
#
# El nombre es la base de datos, "_", y después el momento en que empezó
# la medición. Dentro de la f-string, strftime('%Y-%m-%d_%H-%M-%S') usa
# comillas SIMPLES porque la propia f-string va entre comillas dobles.
# Sin ":" en la hora: Windows no lo permite en los nombres de archivo.
# Como el nombre empieza por el año, ordenar los nombres alfabéticamente
# también los ordena por TIEMPO — previous_starts() se apoya en eso.
# ---------------------------------------------------------------------
def results_file(database: str, measured_at: datetime) -> Path:
    # One file per measurement, named after the database and the moment it started.
    return RESULTS_DIR / f"{database}_{measured_at.strftime('%Y-%m-%d_%H-%M-%S')}.csv"


# ---------------------------------------------------------------------
# def previous_starts(database) -> list[dict]:  — REUTILIZAR LOS MISMOS ACTORES
#
# La investigación compara mediciones: la misma base de datos medida de
# nuevo otro día debe usar los MISMOS 20 actores, o las dos mediciones no
# serían comparables. Los actores no se guardan en un archivo propio:
# cada línea de un CSV de resultados ya dice desde qué actor partió (las
# columnas start_...). Así que esta función VUELVE A LEER el ÚLTIMO CSV
# de esta base de datos y recoge sus actores.
#
# RESULTS_DIR.glob(f"{database}_*.csv") — todos los archivos cuyo nombre
# encaja con el patrón: `*` significa "cualquier carácter" (aquí, la
# fecha y la hora). sorted(...) los pone en orden temporal (ver
# results_file()), así que earlier[-1] — el ÚLTIMO elemento de la lista —
# es el más reciente. Si todavía no hay ningún archivo: una lista vacía
# (main() elige entonces los actores).
#
# csv.DictReader (load_neo4j.py) da cada línea como un dict, con los
# valores como TEXTO. row.get("database") (en lugar de row["database"])
# da None en vez de fallar si un archivo no tiene esa columna. El mismo
# actor aparece en muchas líneas (una por profundidad y versión), así que
# `seen` (un conjunto de ids) guarda cada actor una sola vez. int(...)
# vuelve a convertir los números en números.
#
# La clave de ordenación, una lambda que devuelve una tupla
# (choose_starts.py):
#   a["group"] != "top"   False para "top", True para "median"; False va
#                         antes que True, así que el grupo top va primero;
#   a["rank"]             después por posición, de 1 a 10.
# ---------------------------------------------------------------------
def previous_starts(database: str) -> list[dict]:
    # The actors used in the latest measurement of this database, in their order.
    # (The date-time in the file names sorts in time order.)
    earlier = sorted(RESULTS_DIR.glob(f"{database}_*.csv"))
    if not earlier:
        return []
    seen, actors = set(), []
    with open(earlier[-1], encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("database") == database and row["start_actor_id"] not in seen:
                seen.add(row["start_actor_id"])
                actors.append({"group": row["start_group"], "rank": int(row["start_rank"]),
                               "actor_id": int(row["start_actor_id"]), "login": row["start_login"],
                               "reached": int(row["start_reach_1_hop"])})
    return sorted(actors, key=lambda a: (a["group"] != "top", a["rank"]))


# ---------------------------------------------------------------------
# def print_summary(database, path) -> None:  — UNA TABLA EN PANTALLA
#
# Después de la medición, una tabla breve de lo que se acaba de medir.
# Vuelve a leer el archivo CSV de esta medición (`path`); todas sus
# líneas pertenecen a esta medición, así que list(...) se queda con
# todas.
#
# keys — las distintas combinaciones (grupo, profundidad, versión): una
# SET comprehension (cada combinación una vez), después ordenada: top
# antes que median (el mismo truco que en previous_starts), luego por
# profundidad, luego por versión.
#
# Para cada combinación:
#   lines    sus líneas (una por actor).
#   cells    una celda por lado: la mediana del tiempo de los actores que
#            TERMINARON, en milisegundos (* 1000); `:,.1f` = separador de
#            miles y un decimal. "+3t/o" dice que 3 actores no terminaron
#            (timeout o saltados). "-" si no terminó ninguno.
#   wins     para cuántos actores fue más rápido cada lado.
#            sum(True, False, True...) cuenta los valores True (True
#            cuenta como 1).
# Anchos de columna (:<7, :>11): summarize_data.py.
# ---------------------------------------------------------------------
def print_summary(database: str, path: Path) -> None:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f'\nSummary of "{database}" (median over the actors that finished; t/o = timed out or skipped):')
    print(f"  {'group':<7} {'depth':>5}  {'cypher':<7} {'PostgreSQL':>11} {'Neo4j':>11}  faster (count of actors)")
    keys = sorted({(r["start_group"], int(r["depth"]), r["cypher_version"]) for r in rows},
                  key=lambda k: (k[0] != "top", k[1], k[2]))
    for group, depth, version in keys:
        lines = [r for r in rows if (r["start_group"], int(r["depth"]), r["cypher_version"]) == (group, depth, version)]
        cells = []
        for prefix in ("pg", "neo4j"):
            times = [float(r[f"{prefix}_time_s"]) for r in lines if r[f"{prefix}_status"] == "finished"]
            missing = len(lines) - len(times)
            cell = f"{statistics.median(times) * 1000:,.1f} ms" if times else "-"
            cells.append(cell + (f" +{missing}t/o" if missing else ""))
        wins = {name: sum(r["faster"] == name for r in lines) for name in ("postgresql", "neo4j")}
        print(f"  {group:<7} {depth:>5}  {version:<7} {cells[0]:>11} {cells[1]:>11}  "
              f"PG {wins['postgresql']}, Neo4j {wins['neo4j']}")


def main() -> None:
    # -----------------------------------------------------------------
    # Las opciones. argparse convierte "--max-depth" en args.max_depth (el
    # guion pasa a ser un guion bajo). required=True: el script se niega a
    # ejecutarse sin --database. type=int convierte el texto en un número.
    #   --cypher       choices=... : argparse rechaza cualquier otro valor.
    #                  ("both",) + traversal.CYPHER_VERSIONS une dos
    #                  tuplas: ("both", "paths", "levels").
    #   --new-starts   action="store_true": un interruptor de
    #                  encendido/apagado sin valor (choose_starts.py).
    #
    # Los valores por defecto (profundidad 6, 5 repeticiones, 60 s) son un
    # término medio: 5 ejecuciones cronometradas bastan para una mediana
    # con sentido; 60 s corta las ejecuciones profundas sin esperanza sin
    # cortar las que simplemente son lentas.
    #
    # parser.error("...") imprime el uso y el mensaje, y detiene el script
    # con un error — la forma estándar en que argparse rechaza un valor
    # que no puede comprobar por sí solo (aquí: números menores que 1).
    # -----------------------------------------------------------------
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", required=True, help="The database to measure (same name on both sides)")
    parser.add_argument("--max-depth", type=int, default=6, help="Deepest traversal, in hops (default: 6)")
    parser.add_argument("--repeats", type=int, default=5, help="Timed runs per depth and side (default: 5)")
    parser.add_argument("--timeout", type=int, default=60, help="Seconds before a run is stopped (default: 60)")
    parser.add_argument("--cypher", choices=("both",) + traversal.CYPHER_VERSIONS, default="both",
                        help="Which Cypher version(s) to measure (default: both)")
    parser.add_argument("--new-starts", action="store_true",
                        help="Choose the starting actors again instead of reusing the ones of the latest measurement")
    args = parser.parse_args()
    if args.max_depth < 1 or args.repeats < 1 or args.timeout < 1:
        parser.error("--max-depth, --repeats and --timeout must be at least 1")

    # -----------------------------------------------------------------
    # LOS ACTORES DE PARTIDA: reutilizados, o elegidos.
    #
    # `[] if args.new_starts else previous_starts(...)`: con --new-starts,
    # se hace como si no hubiera ninguno. Una lista vacía cuenta como
    # False, así que si no se encontró nada, choose_starts.choose_in_both()
    # los elige (en LAS DOS bases de datos, que deben coincidir — si no,
    # lanza RuntimeError).
    # \" dentro de la f-string es una comilla doble escapada.
    # -----------------------------------------------------------------
    starts = [] if args.new_starts else previous_starts(args.database)
    if starts:
        print(f"Reusing the {len(starts)} starting actors already measured for \"{args.database}\" (from their latest measurement).")
    else:
        starts = choose_starts.choose_in_both(args.database)
        print(f"Both databases choose the same {len(starts)} actors.")

    # La ventana de los datos (data_window()), y el momento en que empezó
    # esta medición (datetime.now()), que se usa dos veces:
    #   measured_at   como texto, "%H:%M:%S" = horas, minutos, segundos; va
    #                 en cada línea del archivo;
    #   path          el nombre del archivo de esta medición
    #                 (results_file()).
    data_from, data_to, hours = data_window(args.database)
    started = datetime.now()
    measured_at = started.strftime("%Y-%m-%d %H:%M:%S")
    path = results_file(args.database, started)
    # -----------------------------------------------------------------
    # Dos conexiones en UNA sola sentencia `with`, separadas por una coma:
    # las dos se cierran al final, pase lo que pase. Una conexión de
    # PostgreSQL y un driver de Neo4j se reutilizan en todas las
    # ejecuciones — abrir una conexión nueva en cada ejecución añadiría su
    # propio coste a cada tiempo medido.
    #
    # processes: los procesos del servidor de cada base de datos, que se
    # buscan UNA sola vez. Si no se encuentra ninguno (p. ej. el servidor
    # corre en otro ordenador, o con un nombre que no se reconoce), la
    # medición se hace igualmente: solo las columnas de CPU quedan vacías,
    # y una nota lo dice.
    #
    # context: todo lo que necesita measure_actor(), en un solo dict.
    #   "facts"   las columnas del TEST que son iguales en todas las
    #             líneas: measured_at, database, la ventana de los datos, y
    #             además graph_facts() (el tamaño del grafo y los dos
    #             database_mb). La dict comprehension redondea los números
    #             decimales (floats: los tamaños en MB) a un decimal;
    #             isinstance(v, float) comprueba el tipo
    #             (profile_schema.py); los recuentos se quedan como están.
    #
    # El print: `:,` añade separadores de miles (1,234,567). Tres
    # f-strings una al lado de otra se juntan en una.
    # -----------------------------------------------------------------
    with traversal.connect_postgres(args.database) as conn, traversal.connect_neo4j() as driver:
        facts = graph_facts(conn, driver, args.database)
        processes = {"postgresql": server_processes("postgresql"), "neo4j": server_processes("neo4j")}
        for system, found in processes.items():
            if not found:
                print(f"Note: no {system} server process found on this computer; its CPU columns stay empty.")
        context = {"conn": conn, "driver": driver, "processes": processes,
                   "facts": {"measured_at": measured_at, "database": args.database, "data_from_utc": data_from,
                             "data_to_utc": data_to, "volume_hours": hours,
                             **{k: round(v, 1) if isinstance(v, float) else v for k, v in facts.items()}}}
        print(f'\nMeasuring "{args.database}" ({facts["graph_actors"]:,} actors, {facts["graph_repos"]:,} repos, '
              f'{facts["graph_connections"]:,} connections): {len(starts)} starting actors, depths 1-{args.max_depth}, '
              f"{args.repeats} timed runs each, time limit {args.timeout} s, Cypher: {args.cypher}")

        # -------------------------------------------------------------
        # ESCRIBIR EL ARCHIVO CSV DE ESTA MEDICIÓN
        #
        # Primero se imprime el nombre del archivo, para que sepas dónde
        # mirar mientras se ejecuta. mkdir(parents=True, exist_ok=True):
        # crea results/ si hace falta (extract_csv.py).
        #
        # open(path, "w", ...) — "w" abre un archivo NUEVO para escribir
        # (un archivo existente con el mismo nombre se vaciaría; la fecha y
        # la hora del nombre hacen que eso sea prácticamente imposible).
        #
        # csv.DictWriter — escribir filas que son DICTS
        #   csv.writer (docs_spanish/extract_csv.py) escribe listas, en las
        #   que el orden de los valores tiene que coincidir con la cabecera
        #   a mano. DictWriter recibe fieldnames= (los nombres de columna,
        #   aquí COLUMNS) y después filas como dicts: cada valor va a la
        #   columna con el MISMO NOMBRE, sea cual sea el orden del dict, y
        #   una clave que falta da una celda vacía. Es el gemelo, para
        #   escribir, de csv.DictReader (load_neo4j.py).
        #     writeheader()    escribe la línea de cabecera (los fieldnames)
        #     writerow(dict)   escribe una línea (en measure_actor())
        #
        # enumerate(starts, start=1) numera los actores desde 1 (no desde
        # 0) para mostrar el progreso como "[3/20]".
        #
        # f.flush() después de cada actor — una medición entera puede durar
        # HORAS. Python guarda en memoria las líneas escritas durante un
        # rato antes de que lleguen de verdad al archivo. flush() las manda
        # al archivo ya, así que si algo va mal en el actor 15 (un fallo,
        # Ctrl+C, el portátil que se suspende), las líneas de los actores
        # 1-14 están a salvo en el disco.
        # -------------------------------------------------------------
        print(f"Results: {path}")
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            for number, actor in enumerate(starts, start=1):
                print(f"[{number}/{len(starts)}] {actor['group']} #{actor['rank']}: {actor['login']} "
                      f"(reaches {actor['reached']} in one hop)")
                measure_actor(actor, context, args, writer)
                f.flush()

    # Después de los bloques `with` (archivo cerrado, conexiones
    # cerradas): la tabla en pantalla, y dónde están las líneas.
    print_summary(args.database, path)
    print(f"\nDone. The results of this measurement are in {path}")


# ---------------------------------------------------------------------
# La protección __name__ (ver docs_spanish/download_gharchive.py), con un
# añadido: main() se ejecuta dentro de try / except, y captura DOS tipos
# de error, escritos como una tupla (FileNotFoundError, RuntimeError):
#   RuntimeError        las dos bases de datos no contienen los mismos
#                       datos (graph_facts()) o no eligen los mismos
#                       actores (choose_starts.choose_in_both());
#   FileNotFoundError   un archivo que falta.
# Sus mensajes ya dicen qué está mal, así que se imprimen solos, sin el
# traceback largo de Python, y sys.exit(1) informa del fallo — lo que hace
# que research.sh se detenga ahí (set -e, ver docs_spanish/research.sh).
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError) as error:
        print(error)
        sys.exit(1)
