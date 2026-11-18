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
#                             try/except y lanzar FileNotFoundError
#   - extract_csv.py          csv.writer, open(..., newline=""), mkdir(parents=True),
#                             sorted(...), conjuntos (sets)
#   - load_neo4j.py           csv.DictReader, driver.execute_query(..., database_=...)
#   - check_connections.py    conexiones de psycopg / neo4j, `with`, sys.exit
#   - pipeline.py             RawDescriptionHelpFormatter
#   - traversal.py            las dos consultas de recorrido, el objeto Outcome
#                             (status / seconds / count / error), los límites de
#                             tiempo, EXPLAIN (ANALYZE, BUFFERS) y PROFILE
#   - choose_starts.py        cómo se eligen los 20 actores de partida, RESULTS_DIR
#                             y results/<database>/starts.csv
#
# Lo que es NUEVO aquí — este es el script que produce de verdad los números
# de la investigación, así que la mayoría de las explicaciones tratan de
# MEDIR DE FORMA JUSTA:
#   - la ejecución 0, la "primera ejecución": no es un resultado (incluye la
#     preparación del plan de la consulta), pero sirve para comprobar que los
#     dos lados dan el MISMO recuento;
#   - repeticiones cronometradas que ALTERNAN qué lado va primero;
#   - anotar lo ocupado que estaba el ordenador (psutil) junto a cada ejecución;
#   - dejar de medir profundidades mayores en un lado cuando se queda sin
#     tiempo;
#   - conditions.json: versiones, ajustes de memoria y tamaños, guardados para
#     que los resultados se puedan leer en su contexto más adelante;
#   - flush(), una carpeta de salida por fecha y hora (csv.DictWriter se
#     explica en docs_spanish/choose_starts.py; más abajo hay un recordatorio).
#
# Cómo está pensado para ejecutarse — normalmente a través de research.sh,
# que ejecuta choose_starts.py, después este script y después analyze.py:
#     ./research.sh --database gharchive-2026-08-27-12-6h
# o solo, a través de run.sh (que carga .venv y las contraseñas):
#     ./run.sh scripts/measure.py --database gharchive-2026-08-27-12-6h
########################################################################

"""Measure the traversal in PostgreSQL and Neo4j, from the chosen starting actors.

For every starting actor (results/<database>/starts.csv, from choose_starts.py)
and every depth from 1 to --max-depth, it:

    1. runs the traversal once on each side, not timed as a result ("first run":
       it includes preparing the query plan), and checks that BOTH SIDES GIVE
       THE SAME COUNT;
    2. runs it --repeats more times, alternating which side goes first, so that
       anything else happening on the computer affects both sides alike; each
       run records its time, its answer, whether it finished, failed or ran out
       of time (--timeout), and how busy the computer was (CPU and memory);
    3. runs it once more with EXPLAIN (ANALYZE, BUFFERS) / PROFILE, to record
       the work done inside each database.

If a side runs out of time at some depth, the deeper depths are skipped for that
side and actor (they can only be slower). The conditions (versions, memory
settings, data size) are saved too, so every result can be read later in context.

Everything goes to results/<database>/<date-time>/:
    conditions.json   versions, settings, sizes, options used
    runs.csv          one line per timed run
    work.csv          one line per actor, depth and side: the database's own figures

Usage:
    ./run.sh scripts/measure.py --database gharchive-2026-08-27-12-6h
    ./run.sh scripts/measure.py --database ... --max-depth 4 --repeats 5 --timeout 60
"""

# ---------------------------------------------------------------------
# Importaciones de la biblioteca estándar. Ya conocidas: argparse, csv,
# json, sys, Path. Nuevas:
#   platform  — describe el ordenador y el propio Python: nombre del
#               procesador, sistema operativo, versión de Python. Se usa
#               en conditions().
#   datetime  — la fecha y hora actuales: datetime.now(). Se usa para
#               poner nombre a la carpeta de salida y para fechar
#               conditions.json.
# ---------------------------------------------------------------------
import argparse
import csv
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------
# import psutil
#
# Un paquete EXTERNO (instalado desde requirements.txt, como psycopg y
# neo4j): "process and system utilities" (utilidades de procesos y del
# sistema). Lee lo ocupado que está el ordenador — uso de CPU, memoria en
# uso, número de procesadores, memoria total.
#
# ¿Para qué necesita eso un benchmark? El portátil también se está usando
# para otras cosas mientras corre la medición (un navegador, un análisis
# del antivirus, actualizaciones de Windows...). Si una ejecución fue
# lenta porque el ordenador estaba ocupado, queremos VERLO junto al
# tiempo, en lugar de echarle la culpa a la base de datos.
# ---------------------------------------------------------------------
import psutil

# ---------------------------------------------------------------------
# import choose_starts / import traversal
#
# Los scripts PROPIOS del proyecto, importados como paquetes (funciona
# porque están todos en la misma carpeta scripts/). Este script reutiliza:
#   choose_starts.RESULTS_DIR            la carpeta results/
#   traversal.connect_postgres / connect_neo4j
#   traversal.run_postgres_reach / run_neo4j_reach     un recorrido cronometrado
#   traversal.postgres_work / neo4j_work               las cifras de trabajo
# Todos se explican en docs_spanish/traversal.py y
# docs_spanish/choose_starts.py.
# ---------------------------------------------------------------------
import choose_starts
import traversal

# ---------------------------------------------------------------------
# Los nombres de columna de los dos archivos CSV que escribe este script.
#
# RUN_FIELDS — runs.csv, UNA LÍNEA POR EJECUCIÓN:
#   actor_id, group    qué actor de partida (grupo "top" o "median")
#   depth              cuántos saltos
#   system             "postgresql" o "neo4j"
#   run                0 para la primera ejecución (no es un resultado),
#                      después 1, 2, ...
#   status             "ok", "timeout" o "error"
#   seconds            cuánto tardó, medido desde Python
#   count              la respuesta: a cuántos actores se llegó
#   machine_cpu_percent, machine_memory_percent
#                      lo ocupado que estaba el ordenador entero justo antes
#                      de la ejecución
#   error              el mensaje de error, si lo hay
#
# WORK_FIELDS — work.csv, las cifras que cada BASE DE DATOS da sobre su
# propio trabajo (de EXPLAIN / PROFILE, ver docs_spanish/traversal.py):
#   server_ms                         tiempo medido dentro del servidor
#   blocks_from_memory / from_disk    PostgreSQL: páginas de datos
#                                     encontradas en su memoria frente a
#                                     leídas del disco
#   temp_blocks_written               PostgreSQL: volcado a archivos
#                                     temporales porque work_mem se quedó
#                                     corto
#   db_hits                           Neo4j: su unidad de "trabajo hecho"
#   page_cache_hits / misses          Neo4j: la misma idea que los bloques
#                                     de PostgreSQL
#   memory_bytes                      Neo4j: memoria que usó la consulta
#
# Tener las listas de columnas como constantes hace que la cabecera y las
# filas nunca puedan discrepar (ver csv.DictWriter en main()).
#
# SYSTEMS — los dos lados, como tupla, siempre en este orden.
# ---------------------------------------------------------------------
RUN_FIELDS = ["actor_id", "group", "depth", "system", "run", "status", "seconds", "count",
              "machine_cpu_percent", "machine_memory_percent", "error"]
WORK_FIELDS = ["actor_id", "group", "depth", "system", "server_ms", "blocks_from_memory", "blocks_from_disk",
               "temp_blocks_written", "db_hits", "page_cache_hits", "page_cache_misses", "memory_bytes"]
SYSTEMS = ("postgresql", "neo4j")


# ---------------------------------------------------------------------
# def run_order(repeat) — QUÉ LADO VA PRIMERO
#
# ¿Por qué alternar? Cualquier cosa que cambie durante la medición afecta
# a quien esté ejecutándose en ese momento: abres una pestaña del
# navegador, el antivirus se despierta, el portátil se calienta y va más
# lento, Windows escribe en el disco... Si PostgreSQL se ejecutara SIEMPRE
# primero, cada una de esas perturbaciones caería en el mismo lado, en la
# misma posición. Alternar las reparte para que afecten a los dos lados
# por igual, y ninguno tenga una ventaja sistemática (por ejemplo, "el
# segundo en ejecutarse siempre encuentra los datos ya en la memoria del
# sistema operativo").
#
# repeat % 2 — `%` es el RESTO de una división: 1 % 2 es 1, 2 % 2 es 0,
# 3 % 2 es 1... así que `repeat % 2 == 1` significa "repeat es impar".
#
# SYSTEMS[::-1] — un slice (corte) con paso -1 da la tupla AL REVÉS:
# ("neo4j", "postgresql").
#
# `A if condición else B` — un if/else en una línea que da un VALOR: A
# cuando la condición es True, B en caso contrario.
#
# -> tuple[str, str]: la función devuelve una tupla de dos cadenas.
# tests/test_research.py comprueba esta función (docs_spanish/test_research.py).
# ---------------------------------------------------------------------
def run_order(repeat: int) -> tuple[str, str]:
    # Repetition 1: PostgreSQL first; repetition 2: Neo4j first; and so on.
    return SYSTEMS if repeat % 2 == 1 else SYSTEMS[::-1]


# ---------------------------------------------------------------------
# def machine_load() — LO OCUPADO QUE ESTÁ EL ORDENADOR AHORA MISMO
#
# psutil.cpu_percent(interval=0.2)
#   Observa el procesador durante 0,2 segundos y devuelve cuánto se ha
#   usado, en porcentaje (0-100), contando TODOS los programas, no solo el
#   nuestro. El intervalo es necesario: el "uso de CPU" solo tiene sentido
#   a lo largo de un periodo de tiempo. 0,2 s es lo bastante corto para no
#   ralentizar mucho la medición.
#
# psutil.virtual_memory().percent
#   Cuánta memoria (RAM) del ordenador está en uso, en porcentaje.
#
# Se llama justo ANTES de cada ejecución cronometrada (ver
# measure_actor()), así que cada línea de runs.csv dice lo ocupado que
# estaba el ordenador en ese momento. Después, analyze.py marca como
# "ruidosas" las ejecuciones en las que la CPU superaba el 80 %.
# ---------------------------------------------------------------------
def machine_load() -> tuple[float, float]:
    # CPU use of the whole computer over a short moment, and memory in use (percent).
    return psutil.cpu_percent(interval=0.2), psutil.virtual_memory().percent


# ---------------------------------------------------------------------
# def read_starts(database) — leer los actores de partida
#
# starts.csv lo escribió choose_starts.py (ver
# docs_spanish/choose_starts.py). Si no está, medir no tiene sentido, así
# que la función lanza FileNotFoundError con un mensaje que dice qué hay
# que ejecutar antes. El error se captura al final del todo del archivo
# (en la protección __name__) y se imprime de forma limpia, sin un
# traceback largo.
#
# {**row, "actor_id": int(row["actor_id"])}
#   csv.DictReader da todos los valores como TEXTO. `**row` copia todos
#   los pares clave/valor de row en un dict NUEVO, y después
#   "actor_id": ... va detrás y SUSTITUYE esa clave por un entero de
#   verdad. La misma idea que `**` desempaquetando un dict en argumentos
#   con nombre en check_connections.py, pero usada dentro de un dict
#   { }. Todo lo demás (group, rank, login, reached) se queda como texto
#   — solo se imprime.
# ---------------------------------------------------------------------
def read_starts(database: str) -> list[dict]:
    path = choose_starts.RESULTS_DIR / database / "starts.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} doesn't exist: run choose_starts.py --database {database} first")
    with open(path, encoding="utf-8") as f:
        return [{**row, "actor_id": int(row["actor_id"])} for row in csv.DictReader(f)]


# ---------------------------------------------------------------------
# def conditions(...) — LAS CONDICIONES DE LA MEDICIÓN
#
# Un tiempo como "0,8 s" significa poco por sí solo. Depende de las
# versiones del software, de cuánta memoria se PERMITÍA usar a cada base
# de datos, de lo grandes que eran los datos, del ordenador. Esta función
# reúne todo eso en un único dict, que main() guarda como conditions.json
# junto a los resultados. Meses después, los números se pueden seguir
# leyendo en su contexto ("esto se midió con los 128 MB de shared_buffers
# por defecto de PostgreSQL").
#
# Nota: los ajustes se ANOTAN, no se cambian. Las dos bases de datos
# corren con los valores por defecto de su instalación; la idea es saber
# cuáles eran.
# ---------------------------------------------------------------------
def conditions(conn, driver, database: str, args: argparse.Namespace) -> dict:
    # -----------------------------------------------------------------
    # Ajustes de PostgreSQL, leídos con el comando SQL `SHOW <name>`:
    #   shared_buffers        la memoria propia de PostgreSQL para páginas
    #                         de datos (por defecto 128MB — poca; la caché
    #                         de archivos del sistema operativo ayuda por
    #                         encima)
    #   work_mem              memoria por paso de ordenación / hash antes
    #                         de volcar a archivos temporales en disco (por
    #                         defecto 4MB)
    #   effective_cache_size  lo que el planificador SUPONE que hay en
    #                         caché en total (por defecto 4GB); solo influye
    #                         en la elección de planes
    #   max_parallel_workers_per_gather
    #                         cuántos procesos extra puede usar una consulta
    #                         (por defecto 2)
    #   jit                   compilar partes de consultas grandes a código
    #                         máquina (activado por defecto)
    #
    # f"SHOW {name}" construye el texto SQL con una f-string. Eso es seguro
    # AQUÍ solo porque los nombres vienen de nuestra propia tupla fija de
    # arriba, nunca de un usuario (ver docs_spanish/traversal.py sobre
    # sql.Literal).
    #
    # {name: ... for name in settings} es una DICT COMPREHENSION: como una
    # list comprehension, pero construye un dict, un clave: valor por
    # elemento.
    # -----------------------------------------------------------------
    settings = ("shared_buffers", "work_mem", "effective_cache_size", "max_parallel_workers_per_gather", "jit")
    postgres = {name: conn.execute(f"SHOW {name}").fetchone()[0] for name in settings}
    # La versión del servidor, el tamaño de toda la base de datos en disco
    # en bytes (pg_database_size de la base de datos a la que estamos
    # conectados), y cuántas filas tiene cada una de las tres tablas.
    postgres["version"] = conn.execute("SHOW server_version").fetchone()[0]
    postgres["database_size_bytes"] = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    postgres["rows"] = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("actor", "repo", "actor_repo")}

    # -----------------------------------------------------------------
    # Ajustes de memoria de Neo4j, leídos con el comando Cypher SHOW SETTINGS:
    #   server.memory.heap.initial_size / max_size
    #                         el "heap" de Java: memoria para ejecutar
    #                         consultas
    #   server.memory.pagecache.size
    #                         la memoria de Neo4j para páginas de datos (el
    #                         equivalente del shared_buffers de PostgreSQL)
    #   dbms.memory.transaction.total.max
    #                         el tope de memoria que pueden usar todas las
    #                         consultas a la vez
    # Los ajustes del servidor viven en la base de datos especial "system",
    # de ahí database_="system". `.records` es la lista de filas del
    # resultado (la primera de las tres cosas que devuelve execute_query,
    # ver check_connections.py).
    #
    # El texto de la consulta está partido en varios trozos "...": Python
    # junta en una sola las cadenas escritas una al lado de otra.
    # -----------------------------------------------------------------
    records = driver.execute_query(
        "SHOW SETTINGS YIELD name, value WHERE name IN ['server.memory.heap.initial_size', "
        "'server.memory.heap.max_size', 'server.memory.pagecache.size', 'dbms.memory.transaction.total.max'] "
        "RETURN name, value", database_="system").records
    neo4j = {r["name"]: r["value"] for r in records}
    # La versión, como en check_connections.py; `AS v` le pone nombre a la
    # columna. .records[0] es la primera (única) fila.
    version = driver.execute_query("CALL dbms.components() YIELD versions, edition RETURN versions[0] AS v, edition",
                                   database_="system").records[0]
    neo4j["version"] = f"{version['v']} {version['edition']}"
    # -----------------------------------------------------------------
    # count = lambda q: ...
    #
    # Una LAMBDA es una función diminuta sin nombre, escrita en una línea:
    #     lambda q: <expresión>
    # es lo mismo que
    #     def count(q):
    #         return <expresión>
    # Aquí evita repetir tres veces la larga llamada execute_query(...).
    # records[0][0] es la primera columna de la primera fila: el número.
    #
    # Los tres recuentos son el equivalente en el grafo de las tres tablas,
    # así que conditions.json puede mostrar que los dos lados tienen los
    # mismos datos.
    # -----------------------------------------------------------------
    count = lambda q: driver.execute_query(q, database_=database).records[0][0]
    neo4j["rows"] = {"actors": count("MATCH (a:Actor) RETURN count(a)"),
                     "repos": count("MATCH (r:Repo) RETURN count(r)"),
                     "connections": count("MATCH ()-[c:INTERACTED_WITH]->() RETURN count(c)")}

    # -----------------------------------------------------------------
    # La foto completa, como un dict anidado (dicts dentro de un dict), que
    # json.dumps() puede convertir en un archivo tal cual.
    #   started      datetime.now().isoformat(timespec="seconds") da la
    #                fecha y la hora como texto, p. ej. "2026-11-18T14:05:31"
    #   options      lo que se le pidió hacer a la medición
    #   machine      nombre del procesador, número de procesadores LÓGICOS
    #                (núcleos, contando hyper-threads), memoria total en GB
    #                (bytes / 1024**3, donde `**` es "elevado a";
    #                redondeado a un decimal), sistema operativo y versión
    #                de Python
    # -----------------------------------------------------------------
    return {
        "database": database,
        "started": datetime.now().isoformat(timespec="seconds"),
        "options": {"max_depth": args.max_depth, "repeats": args.repeats, "timeout_s": args.timeout},
        "machine": {"cpu": platform.processor(), "logical_cpus": psutil.cpu_count(),
                    "memory_gb": round(psutil.virtual_memory().total / 1024 ** 3, 1),
                    "os": platform.platform(), "python": platform.python_version()},
        "postgresql": postgres,
        "neo4j": neo4j,
    }


# ---------------------------------------------------------------------
# def run_once(system, ...) — un recorrido en UN lado
#
# Un pequeño conmutador para que el resto del código pueda decir
# simplemente "ejecútalo en este lado" sin preocuparse de qué lado es. Las
# dos funciones devuelven un Outcome (status, seconds, count, error): ver
# docs_spanish/traversal.py.
# ---------------------------------------------------------------------
def run_once(system: str, conn, driver, database: str, start: int, depth: int, timeout: int):
    if system == "postgresql":
        return traversal.run_postgres_reach(conn, start, depth, timeout)
    return traversal.run_neo4j_reach(driver, database, start, depth, timeout)


# ---------------------------------------------------------------------
# def measure_actor(...) — TODO LO DE UN ACTOR DE PARTIDA
#
# Para la profundidad 1, 2, 3 ... hasta --max-depth, tres pasos (los
# mismos tres del docstring del principio). `runs` y `work` son los dos
# escritores de CSV creados en main(): esta función escribe sus líneas en
# ellos.
# ---------------------------------------------------------------------
def measure_actor(actor: dict, conn, driver, database: str, args, runs: csv.DictWriter, work: csv.DictWriter) -> None:
    # -----------------------------------------------------------------
    # stopped — SALTARSE LAS PROFUNDIDADES MAYORES
    #
    # Un conjunto con los lados que ya se quedaron sin tiempo (--timeout)
    # para este actor. Bajar un salto más solo puede alcanzar MÁS actores,
    # así que solo puede tardar más: si la profundidad 4 no terminó en
    # 60 s, la 5 tampoco terminará. Saltársela ahorra 60 s x (1 + repeticiones)
    # de espera inútil por profundidad. El OTRO lado sigue, mientras siga
    # terminando.
    # -----------------------------------------------------------------
    stopped = set()   # sides that ran out of time at a smaller depth
    # range(1, args.max_depth + 1): 1, 2, ..., max_depth (el final de un
    # range NO se incluye, de ahí el + 1).
    for depth in range(1, args.max_depth + 1):
        # Los lados que todavía se están midiendo. Si los dos se han
        # parado, no queda nada que hacer con este actor: `break` sale del
        # bucle.
        active = [s for s in SYSTEMS if s not in stopped]
        if not active:
            break
        # end=" " — imprimir sin pasar a una línea nueva, para que el resto
        # del informe de esta profundidad aparezca después en la misma
        # línea.
        # flush=True — mostrarlo YA. Normalmente Python guarda el texto
        # impreso en un búfer durante un rato; sin flush, te quedarías
        # mirando una línea vacía durante una ejecución larga sin saber qué
        # profundidad se está midiendo.
        print(f"  depth {depth}:", end=" ", flush=True)

        # -------------------------------------------------------------
        # PASO 1 — LA EJECUCIÓN 0, LA "PRIMERA EJECUCIÓN": NO ES UN RESULTADO
        #
        # La primerísima vez que una base de datos ve una consulta con una
        # forma nueva, hace un trabajo extra, una sola vez, antes de
        # ejecutarla: analiza el texto y prepara (compila) un PLAN de
        # consulta. Neo4j en concreto tarda unos segundos (unos 5 s) en
        # planificar la primera consulta de longitud variable de una
        # profundidad nueva; después el plan se guarda en su caché y se
        # reutiliza. La primera ejecución además trae los datos a memoria.
        # Contar ese tiempo mediría "la primera vez" en lugar del propio
        # recorrido.
        #
        # Por eso la ejecución 0 se escribe en runs.csv (con run = 0, y sin
        # carga de la máquina: (None, None)) para que quede constancia,
        # pero analyze.py la ignora al calcular los tiempos.
        #
        # SÍ se usa para algo importante: la COMPROBACIÓN DEL RECUENTO. Los
        # dos lados responden "a cuántos actores se puede llegar"; si los
        # dos números difieren, una de las dos consultas (o los datos
        # cargados) está mal, y comparar su velocidad no tendría sentido.
        #
        # first = {s: run_once(...) for s in active}
        #   Una dict comprehension: {"postgresql": Outcome, "neo4j": Outcome}.
        # -------------------------------------------------------------
        # 1. First run (not a result) and the count check.
        first = {s: run_once(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in active}
        for system, outcome in first.items():
            runs.writerow(row(actor, depth, system, 0, outcome, (None, None)))
        # Los recuentos de los lados que terminaron ("ok"). Solo cuando
        # terminaron LOS DOS (len(counts) == 2) se pueden comparar. Si
        # difieren, imprimir un mensaje bien visible y `return`: dejar de
        # medir este actor por completo (main() sigue con el siguiente
        # actor).
        counts = {s: o.count for s, o in first.items() if o.status == "ok"}
        if len(counts) == 2 and counts["postgresql"] != counts["neo4j"]:
            print(f"COUNTS DIFFER (PostgreSQL {counts['postgresql']}, Neo4j {counts['neo4j']}); stopping this actor")
            return
        # Un lado cuya primera ejecución no terminó (timeout o error) se
        # añade a `stopped`: sin ejecuciones cronometradas en esta
        # profundidad, y sin profundidades mayores.
        for system, outcome in first.items():
            if outcome.status != "ok":
                stopped.add(system)
        timed = [s for s in active if s not in stopped]

        # -------------------------------------------------------------
        # PASO 2 — LAS REPETICIONES CRONOMETRADAS
        #
        # ¿Por qué repetir? Un único tiempo no es fiable: la misma consulta
        # puede tardar 0,30 s, luego 0,45 s, luego 0,31 s, según lo que
        # esté haciendo el ordenador. Con varias ejecuciones, analyze.py
        # puede tomar la MEDIANA y ver cuánto se dispersan.
        #
        # Repetición 1: PostgreSQL y después Neo4j; repetición 2: Neo4j y
        # después PostgreSQL; ... (run_order, más arriba). `if system in
        # timed` se salta un lado que se paró en el paso 1.
        #
        # machine_load() se mide justo ANTES de la ejecución (no puede ser
        # durante: cpu_percent() espera sus 0,2 s antes de volver), y se
        # escribe en la misma línea de runs.csv. Esos 0,2 s no forman parte
        # del tiempo de la ejecución: el reloj arranca dentro de
        # run_once().
        # -------------------------------------------------------------
        # 2. Timed repetitions, alternating which side goes first.
        for repeat in range(1, args.repeats + 1):
            for system in run_order(repeat):
                if system in timed:
                    load = machine_load()
                    outcome = run_once(system, conn, driver, database, actor["actor_id"], depth, args.timeout)
                    runs.writerow(row(actor, depth, system, repeat, outcome, load))

        # -------------------------------------------------------------
        # PASO 3 — LAS CIFRAS DE TRABAJO
        #
        # Una ejecución extra por lado, esta vez pidiendo a la base de
        # datos que informe de lo que ha hecho: EXPLAIN (ANALYZE, BUFFERS)
        # en PostgreSQL, PROFILE en Neo4j (explicados en
        # docs_spanish/traversal.py). Va aparte de las ejecuciones
        # cronometradas porque recoger esas cifras ya cuesta tiempo por sí
        # mismo.
        #
        # Estas cifras explican los tiempos: p. ej. "Neo4j hizo 2 millones
        # de db_hits" o "PostgreSQL leyó 9.000 bloques del disco".
        #
        # try / except: si falla la recogida de las cifras, no merece la
        # pena perder toda la medición. figures = {} escribe una línea con
        # las columnas vacías, y se imprime una nota breve.
        # str(error)[:80] — los primeros 80 caracteres del mensaje (un
        # SLICE del texto), para que no llene la pantalla.
        #
        # {"actor_id": ..., **figures} — `**` copia las claves de las
        # cifras en la fila (la misma idea que en read_starts()).
        # DictWriter deja vacía cualquier columna de WORK_FIELDS que el
        # dict no tenga: PostgreSQL no tiene db_hits, Neo4j no tiene
        # blocks_from_disk.
        # -------------------------------------------------------------
        # 3. The work done inside each database (one extra run each).
        for system in timed:
            try:
                if system == "postgresql":
                    figures = traversal.postgres_work(conn, actor["actor_id"], depth, args.timeout)
                else:
                    figures = traversal.neo4j_work(driver, database, actor["actor_id"], depth, args.timeout)
            except Exception as error:
                figures = {}
                print(f"(no work figures for {system}: {str(error)[:80]})", end=" ")
            work.writerow({"actor_id": actor["actor_id"], "group": actor["group"], "depth": depth,
                           "system": system, **figures})

        # -------------------------------------------------------------
        # Terminar en pantalla la línea de esta profundidad.
        #
        # counts.get("postgresql", counts.get("neo4j"))
        #   dict.get(clave, por_defecto): el recuento de PostgreSQL si
        #   terminó; si no, el de Neo4j (o None si no terminó ninguno).
        #
        # status: los lados cuya primera ejecución NO fue "ok", p. ej.
        # "neo4j timeout". ", ".join(...) une los trozos con comas. Los
        # trozos los produce una EXPRESIÓN GENERADORA — una list
        # comprehension sin los [ ], pasada directamente a join().
        #
        # (f"..." if status else "") añade la parte entre paréntesis solo
        # cuando hay algo que decir.
        # -------------------------------------------------------------
        shown = counts.get("postgresql", counts.get("neo4j"))
        status = ", ".join(f"{s} {first[s].status}" for s in active if first[s].status != "ok")
        print(f"{shown} actors reached" + (f" ({status})" if status else ""))


# ---------------------------------------------------------------------
# def row(...) — una línea de runs.csv, como dict
#
# Las claves son exactamente RUN_FIELDS. round(outcome.seconds, 6)
# conserva los microsegundos (6 decimales): más cifras que eso son solo
# ruido. load es la tupla (cpu, memoria) de machine_load(), o
# (None, None) para la ejecución 0; load[0] y load[1] toman sus dos
# valores. None se escribe como una celda vacía en el CSV.
# ---------------------------------------------------------------------
def row(actor: dict, depth: int, system: str, run: int, outcome, load) -> dict:
    return {"actor_id": actor["actor_id"], "group": actor["group"], "depth": depth, "system": system, "run": run,
            "status": outcome.status, "seconds": round(outcome.seconds, 6), "count": outcome.count,
            "machine_cpu_percent": load[0], "machine_memory_percent": load[1], "error": outcome.error}


def main() -> None:
    # -----------------------------------------------------------------
    # Las opciones. argparse convierte "--max-depth" en args.max_depth (el
    # guion pasa a ser un guion bajo). required=True: el script se niega a
    # ejecutarse sin --database. type=int convierte el texto en un número.
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
    args = parser.parse_args()
    if args.max_depth < 1 or args.repeats < 1 or args.timeout < 1:
        parser.error("--max-depth, --repeats and --timeout must be at least 1")

    # -----------------------------------------------------------------
    # UNA CARPETA DE SALIDA POR FECHA Y HORA
    #
    # datetime.now().strftime("%Y-%m-%d_%H-%M-%S") da formato de texto a la
    # hora actual: "%Y" año, "%m" mes, "%d" día, "%H" hora, "%M" minuto,
    # "%S" segundo -> p. ej. "2026-11-18_14-05-31". (Sin ":" porque Windows
    # no lo permite en los nombres de archivo.)
    #
    # Cada medición tiene su propia carpeta, así que volver a medir la
    # misma base de datos nunca sobrescribe un resultado anterior. Como el
    # nombre empieza por el año, ordenar los nombres de las carpetas
    # alfabéticamente también las ordena por tiempo — analyze.py se apoya
    # en eso para encontrar la más reciente.
    #
    # mkdir(parents=True) SIN exist_ok=True: si por algún motivo la carpeta
    # ya existía, es un error — a propósito, para no mezclar nunca dos
    # ejecuciones.
    # -----------------------------------------------------------------
    starts = read_starts(args.database)
    out_dir = choose_starts.RESULTS_DIR / args.database / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir.mkdir(parents=True)

    # -----------------------------------------------------------------
    # Dos conexiones en UNA sola sentencia `with`, separadas por una coma:
    # las dos se cierran al final, pase lo que pase. Una conexión de
    # PostgreSQL y un driver de Neo4j se reutilizan en todas las
    # ejecuciones — abrir una conexión nueva en cada ejecución añadiría su
    # propio coste a cada tiempo medido.
    #
    # json.dumps(info, indent=2) convierte el dict en texto JSON, sangrado
    # con 2 espacios para que se lea fácilmente; Path.write_text() escribe
    # ese texto en el archivo de una vez (open + write + close).
    # -----------------------------------------------------------------
    with traversal.connect_postgres(args.database) as conn, traversal.connect_neo4j() as driver:
        info = conditions(conn, driver, args.database, args)
        (out_dir / "conditions.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        # f'...' con comillas SIMPLES, para que el texto pueda contener
        # comillas "dobles" alrededor del nombre de la base de datos. Dos
        # f-strings una al lado de otra se juntan en una (ver
        # conditions()). "\n" es un salto de línea.
        print(f'Measuring "{args.database}": {len(starts)} starting actors, depths 1-{args.max_depth}, '
              f"{args.repeats} timed runs each, time limit {args.timeout} s")
        print(f"Results: {out_dir}\n")

        # -------------------------------------------------------------
        # csv.DictWriter — escribir filas que son DICTS (un recordatorio;
        # visto por primera vez en docs_spanish/choose_starts.py)
        #
        # csv.writer (docs_spanish/extract_csv.py) escribe listas, en las
        # que el orden de los valores tiene que coincidir con la cabecera a
        # mano. DictWriter recibe fieldnames= (la cabecera) y después filas
        # como dicts: cada valor va a la columna con el MISMO NOMBRE, sea
        # cual sea el orden del dict, y una clave que falta da una celda
        # vacía. Es el gemelo, para escribir, de csv.DictReader.
        #   writeheader()   escribe la línea de cabecera (los fieldnames)
        #   writerow(dict)  escribe una línea
        #
        # La línea `with open(...) as a, \` termina con una barra invertida:
        # CONTINÚA la sentencia en la línea siguiente (si no, la línea
        # quedaría demasiado larga). Los dos archivos se cierran al final
        # del bloque.
        # -------------------------------------------------------------
        with open(out_dir / "runs.csv", "w", newline="", encoding="utf-8") as runs_file, \
             open(out_dir / "work.csv", "w", newline="", encoding="utf-8") as work_file:
            runs = csv.DictWriter(runs_file, fieldnames=RUN_FIELDS)
            work = csv.DictWriter(work_file, fieldnames=WORK_FIELDS)
            runs.writeheader()
            work.writeheader()
            # ---------------------------------------------------------
            # enumerate(starts, start=1) numera los actores desde 1 (no
            # desde 0) para mostrar el progreso como "[3/20]".
            #
            # flush() después de cada actor — una medición entera puede
            # durar HORAS. Python guarda en memoria las líneas escritas
            # durante un rato antes de que lleguen de verdad al archivo.
            # flush() las manda al archivo ya, así que si algo va mal en
            # el actor 15 (un fallo, Ctrl+C, el portátil que se suspende),
            # los resultados de los actores 1-14 están a salvo en el disco
            # y se pueden analizar.
            # ---------------------------------------------------------
            for number, actor in enumerate(starts, start=1):
                print(f"[{number}/{len(starts)}] {actor['group']} #{actor['rank']}: {actor['login']} "
                      f"(reaches {actor['reached']} in one hop)")
                measure_actor(actor, conn, driver, args.database, args, runs, work)
                runs_file.flush()
                work_file.flush()

    print(f"\nDone. Results in {out_dir}")


# ---------------------------------------------------------------------
# La protección __name__ (ver docs_spanish/download_gharchive.py), con un
# añadido: main() se ejecuta dentro de try / except FileNotFoundError. El
# único "archivo no encontrado" esperado es que falte starts.csv
# (read_starts()); su mensaje ya dice qué hacer, así que se imprime solo,
# sin el traceback largo de Python, y sys.exit(1) informa del fallo — lo
# que hace que research.sh se detenga ahí (set -e, ver
# docs_spanish/research.sh).
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(error)
        sys.exit(1)
