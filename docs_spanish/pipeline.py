########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/pipeline.py.
# NO está pensado para ejecutarse como parte del pipeline del proyecto — vive
# en docs_spanish/ porque su propósito es enseñar, no ejecutarse. El script
# real y "limpio" (sin nada de este comentario) es scripts/pipeline.py.
#
# Este archivo asume que ya has leído los scripts anotados anteriores —
# download_gharchive.py (fetch_gz), extract_csv.py (extract, write_all),
# load_postgres.py y load_neo4j.py (load), y check_connections.py.
# pipeline.py es el primer script que no hace un trabajo por sí mismo:
# COORDINA a los demás. Lo que es NUEVO aquí es sobre todo práctica de
# ingeniería de datos: trabajar con fechas y horas en UTC (datetime,
# timedelta, timezone), importar nuestros propios scripts como MÓDULOS,
# escribir un REGISTRO (log) en un archivo, un ARCHIVO DE BLOQUEO (lock)
# para que dos ejecuciones nunca se solapen, crear las bases de datos con
# IDEMPOTENCIA, try/except/finally alrededor de una ejecución entera, y
# CÓDIGOS DE SALIDA para un programador de tareas.
#
# NOVEDADES DE ESTA VERSIÓN — el modo --scheduled ("una vez al día, por sí
# solo"): already_ran_today(), servers_not_ready(), skip_scheduled_run(), y
# dos pequeños ARCHIVOS DE ESTADO (last_success_date.txt,
# scheduled_status.txt). También es nuevo: `date` (un día sin hora), la
# fecha local frente a la fecha UTC, los TIEMPOS DE ESPERA (timeouts) de
# conexión, y anotaciones de tipo como `str | None` ("un str, o None").
#
# POR QUÉ EXISTE — el proyecto tiene DOS tipos de datos:
#   1. datos FIJOS para la investigación: la hora congelada del benchmark
#      en las bases de datos "gharchive", más las horas que TÚ eliges,
#      cargadas a mano con build_hours.py en sus propias bases de datos
#      "gharchive-..." (ver docs_spanish/build_hours.py). Nunca se cambian
#      automáticamente, para que las mediciones se puedan repetir siempre
#      sobre los mismos datos;
#   2. este PIPELINE EN VIVO: una ventana móvil de 24 horas en bases de
#      datos SEPARADAS llamadas "gharchive24h", reconstruida una vez al día.
#
# CÓMO SE PONE EN MARCHA — el Programador de tareas de Windows ejecuta
#     ./run.sh scripts/pipeline.py --scheduled
# cuando inicias sesión y después cada 15 minutos, de forma OCULTA (sin
# ventana) a través de `conhost.exe --headless`. La mayoría de esos
# arranques no encuentran nada que hacer (la ejecución de hoy ya salió
# bien, o Neo4j Desktop todavía no está abierto) y paran en una fracción de
# segundo — ver skip_scheduled_run(). De momento el pipeline automático
# está APLAZADO: la fase de investigación usa los datos fijos del punto 1.
# El código queda listo para cuando se active.
########################################################################

"""Live pipeline: rebuild the "gharchive24h" databases from a rolling 24-hour window.

This is the project's second process, separate from the frozen benchmark data in
the "gharchive" databases (which it never touches). Each run:

    1. works out the window: the last WINDOW_HOURS complete UTC hours, shifted
       LAG_HOURS into the past (default: 24 hours, ending 24 hours ago), so that
       every hour in it has surely been published by GH Archive;
    2. downloads only the hours it doesn't have yet, and deletes those that have
       left the window;
    3. extracts the CSV files from the window's hours (extract_csv.py);
    4. rebuilds PostgreSQL and Neo4j from those same CSVs (load_postgres.py,
       load_neo4j.py), in the "gharchive24h" database on both sides;
    5. writes what happened to logs/pipeline.log.

If anything fails before loading (a missing hour, a database that isn't
running), the databases keep the previous window: nothing is half-replaced.
It runs on its own, once a day: Windows Task Scheduler starts it with --scheduled
every 15 minutes, and it only does the work if today's run hasn't succeeded yet
and both servers are answering (see README, step 6). It never asks anything.

Usage:
    ./run.sh scripts/pipeline.py
    ./run.sh scripts/pipeline.py --dry-run
    ./run.sh scripts/pipeline.py --window-hours 6 --lag-hours 2
    ./run.sh scripts/pipeline.py --scheduled     # what Task Scheduler runs
"""

# ---------------------------------------------------------------------
# Importaciones de la biblioteca estándar
#   logging   NUEVO: escribir mensajes con fecha y hora en un archivo y
#             en pantalla (ver setup_logging()).
#   datetime, timedelta, timezone   NUEVO: fechas/horas y cálculos con
#             ellas (ver compute_window()).
#   date      NUEVO: un DÍA del calendario, sin hora (p. ej. 2026-11-12).
#             date.today() es la fecha de hoy según el reloj de TU
#             ordenador (hora local, no UTC) — la usa el modo --scheduled
#             para decidir "¿ya se ha hecho la ejecución de hoy?" (ver
#             already_ran_today()).
#   os        para os.getpid() y os.environ (como en
#             check_connections.py).
#   argparse, sys, time, Path: ya explicados en los scripts anteriores.
# ---------------------------------------------------------------------
import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# psycopg y GraphDatabase: los dos conectores de bases de datos (ver
# check_connections.py). `sql` es la ayuda de psycopg para construir SQL
# de forma segura cuando lo que hay que meter en la consulta es un NOMBRE
# (no un valor) — ver ensure_databases().
import psycopg
from neo4j import GraphDatabase
from psycopg import sql

# ---------------------------------------------------------------------
# import download_gharchive, extract_csv, load_neo4j, load_postgres
#
# NUEVO: importar NUESTROS PROPIOS scripts. Todo archivo .py es también
# un MÓDULO que otros archivos de Python pueden importar. Cuando ejecutas
# scripts/pipeline.py, Python busca las importaciones en la carpeta en la
# que está el script (scripts/), así que encuentra ahí los otros scripts.
#
# Importar un script ejecuta su código de nivel superior (constantes,
# definiciones de funciones) pero NO su main(): justo para eso está la
# protección `if __name__ == "__main__":` al final de cada script. Así el
# pipeline obtiene sus funciones — download_gharchive.fetch_gz(),
# extract_csv.extract(), load_postgres.load()... — sin ejecutarlos como
# programas. Eso es REUTILIZAR: el pipeline no copia su código, así que
# el benchmark y el pipeline usan siempre exactamente la misma lógica.
# ---------------------------------------------------------------------
import download_gharchive
import extract_csv
import load_neo4j
import load_postgres

# ---------------------------------------------------------------------
# Dónde vive cada cosa. Todo lo que hay en data/ y logs/ lo ignora git:
#   data/live/raw/               los archivos .json.gz por hora de la ventana
#   data/live/csv/               los tres CSV para las bases de datos de 24 horas
#   data/live/pipeline.lock      solo existe mientras hay una ejecución en marcha
#   data/live/current_window.txt la última ventana cargada con éxito
#   logs/pipeline.log            el historial de todas las ejecuciones
# Los archivos del benchmark (data/2026-08-27-15.json, data/csv/) y los de
# build_hours.py (data/hours/) están aparte y nunca se tocan.
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
LIVE_DIR = PROJECT_DIR / "data" / "live"
RAW_DIR = LIVE_DIR / "raw"
CSV_DIR = LIVE_DIR / "csv"
LOCK_FILE = LIVE_DIR / "pipeline.lock"
WINDOW_FILE = LIVE_DIR / "current_window.txt"
LOG_FILE = PROJECT_DIR / "logs" / "pipeline.log"
# ---------------------------------------------------------------------
# Dos ARCHIVOS DE ESTADO, que solo usa el modo --scheduled. Cada uno
# contiene una sola línea y se SOBRESCRIBE cada vez (no es un historial —
# el historial es el registro):
#   last_success_date.txt   la fecha de la última ejecución con éxito,
#                           p. ej. "2026-11-12". Es la MEMORIA del
#                           pipeline entre arranques: cada arranque es un
#                           proceso de Python completamente nuevo que no
#                           recuerda nada, así que "¿ya me he ejecutado
#                           hoy?" tiene que quedar apuntado en un archivo.
#   scheduled_status.txt    lo que encontró el ÚLTIMO arranque, p. ej.
#                           "2026-11-12 10:15 (your time): Neo4j isn't
#                           answering (...); will try again at the next
#                           check" o "... run SUCCEEDED". Como la tarea se
#                           ejecuta oculta, esta es la forma más rápida de
#                           ver qué está haciendo.
# ---------------------------------------------------------------------
# --scheduled only: the local date of the last successful run, and what the last attempt found.
LAST_SUCCESS_FILE = LIVE_DIR / "last_success_date.txt"
SCHEDULED_STATUS_FILE = LIVE_DIR / "scheduled_status.txt"

# ---------------------------------------------------------------------
# DEFAULT_DATABASE = "gharchive24h"
#   No "gharchive_24h": los nombres de base de datos de Neo4j solo pueden
#   contener letras, dígitos, puntos y guiones — nada de guiones bajos.
#   Se usa el mismo nombre en los dos lados, igual que con el "gharchive"
#   del benchmark.
# DEFAULT_WINDOW_HOURS / DEFAULT_LAG_HOURS — 24 horas de datos, que
#   terminan hace 24 horas (ver compute_window()). Los dos se pueden
#   cambiar desde la línea de comandos.
# STALE_LOCK_HOURS — qué antigüedad tiene que tener un archivo de bloqueo
#   para considerarlo abandonado (ver acquire_lock()).
# ---------------------------------------------------------------------
DEFAULT_DATABASE = "gharchive24h"  # Neo4j doesn't allow "_" in database names
DEFAULT_WINDOW_HOURS = 24
DEFAULT_LAG_HOURS = 24
STALE_LOCK_HOURS = 3

# ---------------------------------------------------------------------
# log = logging.getLogger("pipeline")
#
# Un LOGGER es un objeto para escribir mensajes con un NIVEL, que indica
# lo importante que es cada uno:
#   log.info("...")       progreso normal ("Window: ...", "Status: ...")
#   log.warning("...")    algo raro, pero la ejecución sigue
#   log.error("...")      algo ha ido mal
#   log.exception("...")  un error, más el traceback completo de la
#                         excepción que se está gestionando
# Comparado con print(), cada mensaje lleva fecha y hora y un nivel, y
# puede ir a varios sitios a la vez (aquí: un archivo y la pantalla).
# ---------------------------------------------------------------------
log = logging.getLogger("pipeline")


# ---------------------------------------------------------------------
# def setup_logging() -> None:
#
# Configura DÓNDE van los mensajes y CÓMO se ven:
#
#   Formatter("%(asctime)s UTC  %(levelname)-7s  %(message)s", ...)
#     cada línea queda, p. ej.
#     2026-10-22 12:44:14 UTC  INFO     Window: 2026-10-20 12:00 -> ...
#   formatter.converter = time.gmtime
#     escribe las horas en UTC en lugar de en la hora local del
#     ordenador — el mismo reloj que usan los nombres de archivo de GH
#     Archive, así que el registro y la ventana se pueden comparar
#     directamente (Portugal va una hora por delante de UTC en verano, y
#     esa hora de diferencia causaría confusión).
#   FileHandler(LOG_FILE)    añade cada mensaje al final de logs/pipeline.log
#   StreamHandler(sys.stdout) y también lo muestra en pantalla
#
# Los handlers se ponen en el logger RAÍZ (logging.getLogger() sin
# nombre), el padre de todos los loggers. Los mensajes de cualquier
# logger "suben" hasta él, así que la advertencia que extract_csv.py
# escribe con su propio logger (p. ej. "Skipped 2 event(s) without an
# actor or repo id") acaba en el mismo archivo.
#
# logging.getLogger("neo4j").setLevel(logging.WARNING)
#   El driver de Neo4j tiene su propio logger y avisa de notificaciones
#   INFORMATIVAS del servidor con nivel INFO. La primera ejecución real
#   imprimió una larga ("server has caught up") justo después de CREATE
#   DATABASE — inofensiva, pero ruido. Esto deja solo las advertencias y
#   errores del driver.
# ---------------------------------------------------------------------
def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Log times in UTC, like GH Archive's file names, so the window and the log line up.
    formatter = logging.Formatter("%(asctime)s UTC  %(levelname)-7s  %(message)s", "%Y-%m-%d %H:%M:%S")
    formatter.converter = time.gmtime
    # Handlers go on the root logger, so warnings from the other scripts (e.g. extract_csv)
    # end up in the same log file.
    root = logging.getLogger()
    for handler in (logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    # The Neo4j driver logs informational server notifications (e.g. "server has caught up"
    # after CREATE DATABASE); only its warnings and errors belong in this log.
    logging.getLogger("neo4j").setLevel(logging.WARNING)


# ---------------------------------------------------------------------
# def compute_window(now, window_hours, lag_hours) -> list[datetime]:
#
# Calcula QUÉ HORAS contiene la ventana. Un `datetime` es una fecha y una
# hora juntas; un `timedelta` es una duración, y puedes sumarla o
# restarla a un datetime ("esta hora menos 24 horas").
#
# Paso a paso, con now = 2026-10-22 11:15 UTC y los valores por defecto:
#   now.replace(minute=0, second=0, microsecond=0)
#       -> 2026-10-22 11:00   (redondear HACIA ABAJO al inicio de la hora)
#   - timedelta(hours=lag_hours)        (24)
#       -> end   = 2026-10-21 11:00   la ventana TERMINA aquí
#   end - timedelta(hours=window_hours) (24)
#       -> start = 2026-10-20 11:00   la ventana EMPIEZA aquí
#   [start + timedelta(hours=i) for i in range(24)]
#       -> 2026-10-20 11:00, 12:00, ..., 2026-10-21 10:00   (24 horas)
#
# Cada elemento es el INICIO de un archivo por hora: el último, 10:00,
# cubre de 10:00 a 11:00, así que la ventana termina exactamente a las
# 11:00. La hora `end` en sí NO se incluye.
#
# Por qué el retraso (lag): GH Archive publica cada hora un poco después
# de que termine, y de vez en cuando más tarde. Terminar la ventana hace
# un día significa que todas sus horas están publicadas con seguridad. El
# retraso es un parámetro (--lag-hours), así que se puede reducir más
# adelante.
#
# `now` es un parámetro (en lugar de leer el reloj dentro) para que la
# función se pueda PROBAR con cualquier hora, como en el ejemplo de
# arriba.
# ---------------------------------------------------------------------
def compute_window(now: datetime, window_hours: int, lag_hours: int) -> list[datetime]:
    # Example (24 h, lag 24 h): now 2026-10-22 11:15 UTC -> hours 2026-10-20 11:00 ... 2026-10-21 10:00,
    # i.e. the window 2026-10-20 11:00 -> 2026-10-21 11:00.
    end = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=lag_hours)
    start = end - timedelta(hours=window_hours)
    return [start + timedelta(hours=i) for i in range(window_hours)]


# ---------------------------------------------------------------------
# def hour_file_name(hour) -> str:
#
# f"{hour:%Y-%m-%d}" da formato al datetime con un patrón de fecha:
#   %Y año (2026), %m mes (10), %d día (20)  ->  "2026-10-20"
# hour.hour es solo la hora como número (5), así que no lleva cero a la
# izquierda — exactamente como GH Archive nombra sus archivos:
# 2026-10-20-5.json.gz.
# ---------------------------------------------------------------------
def hour_file_name(hour: datetime) -> str:
    # Same naming as GH Archive: UTC hour without a leading zero, e.g. 2026-10-20-5.json.gz
    return f"{hour:%Y-%m-%d}-{hour.hour}.json.gz"


# ---------------------------------------------------------------------
# def acquire_lock() -> bool:
#
# Un ARCHIVO DE BLOQUEO impide que dos ejecuciones trabajen a la vez. El
# Programador de tareas arranca el pipeline cada 15 minutos; si una
# ejecución tardara más que eso (una descarga lenta, una ventana grande),
# el siguiente arranque podría empezar mientras la primera todavía está
# cargando — y las dos vaciarían y llenarían las mismas bases de datos a
# la vez. (Alguien que lo ejecutara a mano durante una ejecución
# programada causaría el mismo problema.)
#
#   - ¿No hay archivo de bloqueo?        -> crearlo y seguir (True).
#   - ¿Bloqueo con menos de 3 h?         -> hay otra ejecución en marcha:
#                                           no empezar (False).
#   - ¿Bloqueo con más de 3 h?           -> una ejecución anterior falló
#                                           sin borrarlo ("caducado"):
#                                           borrarlo, registrar una
#                                           advertencia y seguir.
#
# LOCK_FILE.stat().st_mtime es cuándo se escribió el archivo por última
# vez (en segundos desde 1970); time.time() es ahora, en la misma unidad,
# así que la diferencia dividida entre 3600 es su antigüedad en horas. El
# contenido del archivo (el id del proceso y la hora de inicio) solo está
# ahí para quien lo mire a mano.
# ---------------------------------------------------------------------
def acquire_lock() -> bool:
    # If a previous run is still going (or crashed without cleaning up), don't start a second one.
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        age_hours = (time.time() - LOCK_FILE.stat().st_mtime) / 3600
        if age_hours < STALE_LOCK_HOURS:
            return False
        log.warning("Removing stale lock file (%.1f hours old)", age_hours)
        LOCK_FILE.unlink()
    LOCK_FILE.write_text(f"pid {os.getpid()} started {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC\n")
    return True


# ---------------------------------------------------------------------
# def sync_raw_files(hours) -> None:
#
# Hace que data/live/raw/ contenga EXACTAMENTE los archivos de las horas
# de la ventana:
#
#   1. wanted = el conjunto de nombres de archivo que deberían estar ahí.
#   2. Cualquier archivo de la carpeta que no esté en wanted (una hora
#      que ha salido de la ventana, o un ".part" sobrante de una descarga
#      interrumpida) se borra. RAW_DIR.iterdir() lista el contenido de la
#      carpeta.
#   3. missing = las horas de la ventana cuyo archivo todavía no está, y
#      solo esas se descargan, con download_gharchive.fetch_gz().
#
# Así, la primera ejecución descarga las 24 horas, y cada ejecución
# posterior descarga solo la hora nueva y borra la que ha salido — esto
# es lo que hace que ejecutarlo cada hora salga barato.
#
# log.info("%d of %d ...", a, b, c) — logging rellena los huecos %d con
# los argumentos extra, por orden (%d = número entero).
# ---------------------------------------------------------------------
def sync_raw_files(hours: list[datetime]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    wanted = {hour_file_name(hour) for hour in hours}

    for path in RAW_DIR.iterdir():
        if path.name not in wanted:
            path.unlink()
            log.info("Removed %s (outside the window)", path.name)

    missing = [hour for hour in hours if not (RAW_DIR / hour_file_name(hour)).exists()]
    log.info("%d of %d hour files already present; downloading %d", len(hours) - len(missing), len(hours), len(missing))
    for hour in missing:
        download_gharchive.fetch_gz(f"{hour:%Y-%m-%d}", hour.hour, RAW_DIR)


# ---------------------------------------------------------------------
# def ensure_databases(database) -> None:
#
# Se asegura de que la base de datos de destino existe en LOS DOS lados,
# y solo la crea si no existe. Eso es IDEMPOTENCIA: ejecutarlo una vez o
# diez deja el mismo resultado, así que la primera ejecución de todas se
# prepara sola, y una base de datos borrada por error simplemente se
# vuelve a crear en la siguiente ejecución.
#
# PostgreSQL:
#   - Se conecta a la base de datos "postgres", que siempre existe (no
#     puedes crear una base de datos mientras estás conectado a ella).
#   - autocommit=True: CREATE DATABASE no se puede ejecutar dentro de una
#     transacción.
#   - pg_database es el catálogo de bases de datos de PostgreSQL: el
#     SELECT pregunta "¿hay alguna con este nombre?". %s es un PARÁMETRO:
#     psycopg inserta el valor de forma segura.
#   - El NOMBRE de una base de datos no se puede pasar como parámetro,
#     así que se construye con
#     sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)),
#     que pone las comillas al nombre correctamente en lugar de pegar
#     texto crudo en el SQL.
#
# Neo4j:
#   CREATE DATABASE `gharchive24h` IF NOT EXISTS WAIT
#     IF NOT EXISTS  no hace nada si ya existe
#     WAIT           no vuelve hasta que la nueva base de datos está en línea
#   Se envía a la base de datos "system", donde Neo4j gestiona las bases
#   de datos y los usuarios. (Crear bases de datos adicionales necesita la
#   Enterprise Edition de Neo4j — la que incluye Neo4j Desktop.)
#
# También es una COMPROBACIÓN PREVIA: se llama antes de cualquier carga,
# así que si alguno de los dos servidores está caído, la ejecución falla
# aquí, antes de que se haya vaciado nada.
# ---------------------------------------------------------------------
def ensure_databases(database: str) -> None:
    # Also a pre-flight check: if either server isn't reachable, stop before changing anything.
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone() is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            log.info("Created PostgreSQL database %s", database)

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        driver.verify_connectivity()
        driver.execute_query(f"CREATE DATABASE `{database}` IF NOT EXISTS WAIT", database_="system")


# ---------------------------------------------------------------------
# def run(window_hours, lag_hours, database, dry_run) -> bool:
#
# Una ejecución completa, paso a paso, cada uno cronometrado y
# registrado:
#   1. calcular la ventana a partir de la hora UTC actual;
#   2. (ensayo (dry run): solo listar los archivos y parar — no cambia
#      nada);
#   3. sincronizar los archivos por hora (descargar lo que falte);
#   4. extraer los CSV, reutilizando las funciones de extract_csv;
#   5. asegurarse de que las dos bases de datos existen (y de que los dos
#      servidores responden);
#   6. cargar PostgreSQL y después Neo4j, reutilizando los cargadores,
#      pasándoles el nombre de la base de datos;
#   7. si las dos cargas coinciden con sus CSV, apuntar la ventana en
#      current_window.txt — y, para la base de datos real
#      "gharchive24h", la fecha de hoy en last_success_date.txt (ver más
#      abajo).
# Devuelve True solo si las comprobaciones de las dos cargas salieron OK.
#
# El ORDEN es deliberado: todo lo que puede fallar sin causar daño
# (descargar, extraer, conectar) ocurre ANTES de vaciar ninguna base de
# datos. Si falta una hora o un servidor está caído, las bases de datos
# conservan la ventana anterior.
#
# hours[-1] + timedelta(hours=1) es el FINAL de la ventana: el inicio de
# la última hora más una hora.
# ---------------------------------------------------------------------
def run(window_hours: int, lag_hours: int, database: str, dry_run: bool) -> bool:
    hours = compute_window(datetime.now(timezone.utc), window_hours, lag_hours)
    window = f"{hours[0]:%Y-%m-%d %H:00} -> {hours[-1] + timedelta(hours=1):%Y-%m-%d %H:00} UTC"
    log.info("Window: %s (%d hours, lag %d h), database %s", window, window_hours, lag_hours, database)

    if dry_run:
        for hour in hours:
            present = (RAW_DIR / hour_file_name(hour)).exists()
            log.info("  %s  %s", hour_file_name(hour), "present" if present else "to download")
        return True

    run_start = time.perf_counter()

    step = time.perf_counter()
    sync_raw_files(hours)
    log.info("Download step done in %.1f s", time.perf_counter() - step)

    step = time.perf_counter()
    files = [RAW_DIR / hour_file_name(hour) for hour in hours]
    actors, repos, pairs, skipped_bot_events = extract_csv.extract(files)
    extract_csv.write_all(CSV_DIR, actors, repos, pairs)
    log.info("Extracted %d actors, %d repos, %d connections (%d bot events skipped) in %.1f s",
             len(actors), len(repos), len(pairs), skipped_bot_events, time.perf_counter() - step)

    ensure_databases(database)

    step = time.perf_counter()
    postgres_ok = load_postgres.load(CSV_DIR, database)
    log.info("PostgreSQL load %s in %.1f s", "OK" if postgres_ok else "MISMATCH", time.perf_counter() - step)

    step = time.perf_counter()
    neo4j_ok = load_neo4j.load(CSV_DIR, database)
    log.info("Neo4j load %s in %.1f s", "OK" if neo4j_ok else "MISMATCH", time.perf_counter() - step)

    if postgres_ok and neo4j_ok:
        WINDOW_FILE.write_text(f"{window}\n{len(actors)} actors, {len(repos)} repos, {len(pairs)} connections\n")
        # -------------------------------------------------------------
        # Recordar "la ejecución de hoy ha salido bien" — pero solo
        # cuando se ha reconstruido la base de datos REAL. Una ejecución
        # de prueba como --database gharchivetest no debe hacer creer a
        # la tarea programada que el trabajo del día ya está hecho.
        #
        # date.today() es la fecha LOCAL (el calendario de tu ordenador),
        # a propósito, aunque todo lo demás aquí está en UTC: "una vez al
        # día" se entiende desde tu punto de vista. Cerca de la
        # medianoche las dos pueden ser distintas — a las 00:30 en Madrid
        # en invierno todavía es ayer en UTC — y una fecha UTC haría que
        # la ejecución diaria "cambiara de día" a una hora local extraña.
        #
        # f"{date.today():%Y-%m-%d}" le da el formato "2026-11-12" (el
        # mismo patrón de fecha que en hour_file_name()); "\n" termina la
        # línea.
        # -------------------------------------------------------------
        if database == DEFAULT_DATABASE:
            # Your computer's date, not UTC: "once a day" means once per day of yours.
            LAST_SUCCESS_FILE.write_text(f"{date.today():%Y-%m-%d}\n")
    log.info("Run finished in %.1f s", time.perf_counter() - run_start)
    return postgres_ok and neo4j_ok


# ---------------------------------------------------------------------
# parse_args(): las opciones del pipeline. Todas tienen valor por
# defecto, así que el programador de tareas puede ejecutarlo sin ninguna
# opción.
#   --window-hours   tamaño de la ventana (p. ej. 6 para una prueba rápida)
#   --lag-hours      cuánto hacia atrás termina
#   --database       qué base de datos reconstruir en los dos lados
#   --dry-run        solo mostrar el plan (un INDICADOR, como lo era
#                    --exclude-bots)
#   --scheduled      NUEVO: otro indicador, el que pasa el Programador de
#                    tareas. Añade las comprobaciones de "¿hay algo que
#                    hacer?" de skip_scheduled_run() antes de la
#                    ejecución (ver main()). Si lo ejecutas a mano sin
#                    él, el pipeline se ejecuta siempre.
# formatter_class=RawDescriptionHelpFormatter conserva los saltos de
# línea del docstring cuando --help lo imprime.
#
# Fíjate en el texto help= de --scheduled: dos literales de cadena uno
# junto al otro ("... run " "already ...") Python los UNE en uno solo. Es
# una forma de partir un texto largo en dos líneas sin usar el signo +.
# ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS,
                         help=f"How many hours the window covers (default: {DEFAULT_WINDOW_HOURS})")
    parser.add_argument("--lag-hours", type=int, default=DEFAULT_LAG_HOURS,
                         help=f"How far back the window ends, in hours (default: {DEFAULT_LAG_HOURS})")
    parser.add_argument("--database", default=DEFAULT_DATABASE,
                         help=f"Database to rebuild on both sides (default: {DEFAULT_DATABASE})")
    parser.add_argument("--dry-run", action="store_true",
                         help="Only show the window and which files would be downloaded; change nothing")
    parser.add_argument("--scheduled", action="store_true",
                         help="For Task Scheduler, which starts it every 15 minutes: do nothing if today's run "
                              "already succeeded, or if PostgreSQL or Neo4j isn't answering yet")
    return parser.parse_args()


# ---------------------------------------------------------------------
# def already_ran_today(last_success, today) -> bool:
#
# Responde a "¿la ejecución de hoy ya ha salido bien?", a partir de:
#   last_success   el TEXTO de last_success_date.txt, p. ej.
#                  "2026-11-12\n", o None si el archivo todavía no existe
#                  (nunca se ha ejecutado);
#   today          la fecha de hoy.
#
# `str | None` es una anotación de tipo que significa "un str O None". La
# `|` se lee como "o". Es solo una nota para quien lee el código (Python
# no la obliga a cumplir), pero avisa de que la función tiene que saber
# tratar None.
#
# Cómo decide, de izquierda a derecha:
#   last_success is not None   — si ES None, `and` se para justo aquí y
#                                la respuesta es False. (Eso también
#                                evita llamar a .strip() sobre None, que
#                                daría un error.)
#   last_success.strip()       — quita el "\n" (y cualquier espacio) de
#                                los extremos, así que "2026-11-12\n" se
#                                convierte en "2026-11-12";
#   == f"{today:%Y-%m-%d}"     — lo compara con la fecha de hoy escrita
#                                de la misma forma.
#
# ¿Por qué es tan pequeña y va aparte? Es una función PURA: recibe el
# texto del archivo y la fecha como PARÁMETROS, en lugar de leer ella
# misma el archivo y el reloj. Así se puede PROBAR con cualquier fecha,
# sin archivos — la misma razón por la que compute_window() recibe `now`
# como parámetro (ver docs_spanish/test_pipeline.py).
# ---------------------------------------------------------------------
def already_ran_today(last_success: str | None, today: date) -> bool:
    # last_success is the text of LAST_SUCCESS_FILE (None if it doesn't exist yet).
    return last_success is not None and last_success.strip() == f"{today:%Y-%m-%d}"


# ---------------------------------------------------------------------
# def servers_not_ready() -> str | None:
#
# Pregunta a los dos servidores "¿estás ahí?", de la forma más barata
# posible, y responde con:
#   None                 los dos han respondido — listo para trabajar;
#   un texto corto       el MOTIVO por el que uno no ha respondido
#                        (p. ej. "Neo4j isn't answering (...)").
# Devolver "el problema, o None si no hay ninguno" es un patrón habitual:
# quien llama comprueba `if reason is not None:` y ya tiene el mensaje
# listo para mostrar.
#
# Es el mismo tipo de conexión que en check_connections.py, con dos
# diferencias:
#   - TIEMPOS DE ESPERA: connect_timeout=5 (psycopg) y
#     connection_timeout=5 (Neo4j) se rinden a los 5 segundos. Cuando un
#     servidor no está en marcha, la comprobación debe fallar RÁPIDO, no
#     quedarse colgada — se repite cada 15 minutos en segundo plano.
#   - Las excepciones se CAPTURAN y se convierten en un mensaje en lugar
#     de detener el programa: aquí, un servidor que no responde es una
#     situación normal (p. ej. todavía no has abierto Neo4j Desktop), no
#     un error.
#
# "SELECT 1" es la consulta SQL más pequeña posible: solo demuestra que
# la conexión funciona. verify_connectivity() hace lo mismo para Neo4j
# (ver check_connections.py).
#
# La contraseña: la de PostgreSQL sale de PGPASSWORD por sí sola, la de
# Neo4j se lee de os.environ — exactamente como en check_connections.py.
# Las dos vienen de secrets.sh a través de run.sh; ninguna se escribe
# nunca en el código.
#
# build_hours.py reutiliza esta función como su "paso 0" (ver
# docs_spanish/build_hours.py).
# ---------------------------------------------------------------------
def servers_not_ready() -> str | None:
    # Returns None if both servers answer, or a short reason if one doesn't (it isn't running yet).
    try:
        with psycopg.connect(host="localhost", user="postgres", dbname="postgres", connect_timeout=5) as conn:
            conn.execute("SELECT 1")
    except Exception:
        return "PostgreSQL isn't answering"
    try:
        auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
        with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth, connection_timeout=5) as driver:
            driver.verify_connectivity()
    except Exception:
        return "Neo4j isn't answering (is Neo4j Desktop open, with the instance started?)"
    return None


# ---------------------------------------------------------------------
# def skip_scheduled_run() -> bool:
#
# La PUERTA del modo --scheduled. Devuelve True si este arranque no debe
# hacer nada, y False si la ejecución real debe seguir adelante. Hay dos
# motivos para saltársela, comprobados en este orden:
#   1. la ejecución de hoy ya ha salido bien  -> nada que hacer hasta
#                                               mañana;
#   2. un servidor no responde                -> volver a intentarlo en
#                                               15 minutos.
# La comprobación barata (leer un archivo de una línea) va primero, así
# que en la mayoría de los arranques ni siquiera se contacta con los
# servidores.
#
# Línea a línea:
#   X if condición else Y   (ya visto) — leer el texto del archivo si
#       existe, y si no, None, que already_ran_today() entiende.
#   reason += "; will try ..."   `+=` añade texto al FINAL de una cadena
#       ("a" += "b" da "ab"). Solo se hace si reason no es None — añadir
#       a None daría un error.
#   if reason is None: return False   nada impide la ejecución.
#   Si no: escribir UNA línea en scheduled_status.txt (write_text
#       sustituye el archivo entero, así que siempre muestra la ÚLTIMA
#       comprobación), imprimirla también, y devolver True.
#
# datetime.now() SIN timezone.utc da la hora LOCAL de tu ordenador — de
# ahí "(your time)" en el texto. Ese archivo está pensado para que lo
# leas tú, así que la hora local es más clara; el registro sigue usando
# UTC.
#
# POR QUÉ SE EJECUTA ANTES DE setup_logging(): se puede llamar hasta 96
# veces al día (cada 15 minutos) y casi siempre no encuentra nada que
# hacer. Si cada una de esas comprobaciones escribiera en
# logs/pipeline.log, las ejecuciones reales quedarían enterradas entre
# miles de líneas de "nada que hacer". Por eso las comprobaciones solo
# sobrescriben su archivo de estado de una línea, y el registro solo
# recibe las ejecuciones reales.
# ---------------------------------------------------------------------
def skip_scheduled_run() -> bool:
    # Runs before logging is set up, so the frequent "nothing to do" checks don't fill
    # logs/pipeline.log: their result only goes to SCHEDULED_STATUS_FILE (overwritten each time).
    last_success = LAST_SUCCESS_FILE.read_text() if LAST_SUCCESS_FILE.exists() else None
    if already_ran_today(last_success, date.today()):
        reason = "today's run already succeeded; nothing to do"
    else:
        reason = servers_not_ready()
        if reason is not None:
            reason += "; will try again at the next check"
    if reason is None:
        return False
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULED_STATUS_FILE.write_text(f"{datetime.now():%Y-%m-%d %H:%M} (your time): {reason}\n")
    print(reason)
    return True


# ---------------------------------------------------------------------
# def main() -> None:
#
# 0. NUEVO — PUERTA PROGRAMADA: con --scheduled (y sin --dry-run),
#    preguntar primero a skip_scheduled_run(); si no hay nada que hacer,
#    parar enseguida con sys.exit(0) — éxito, porque "nada que hacer" es
#    normal. Esto ocurre ANTES de setup_logging(), así que estas salidas
#    rápidas nunca tocan el registro (ver skip_scheduled_run()).
# 1. PROTECCIÓN DE SEGURIDAD: negarse a tocar "gharchive", la base de
#    datos congelada del benchmark — aunque alguien escriba
#    --database gharchive por error.
# 2. BLOQUEO: si hay otra ejecución en marcha, saltarse esta.
#    sys.exit(0) (éxito) a propósito: saltarse una ejecución es normal,
#    no un error.
# 3. try / except / finally:
#      try      ejecutar el pipeline entero;
#      except   si CUALQUIER cosa lanza una excepción, registrarla con su
#               traceback completo (log.exception) y marcar la ejecución
#               como fallida, en lugar de caerse sin dejar rastro en el
#               registro;
#      finally  se ejecuta en TODOS los casos, éxito o fallo: borrar el
#               archivo de bloqueo, para que la siguiente ejecución no se
#               quede bloqueada.
# 4. NUEVO — con --scheduled, escribir el RESULTADO de la ejecución en
#    scheduled_status.txt, para que el archivo diga siempre qué hizo el
#    último arranque: si se la saltó, si salió bien o si falló.
# 5. CÓDIGO DE SALIDA: sys.exit(0) si hay éxito, sys.exit(1) si hay
#    fallo. Es útil cuando lo ejecutas a mano o desde otro script. PERO:
#    el "Resultado de la última ejecución" del Programador de tareas
#    muestra siempre 0x0 en este caso, incluso después de un fallo,
#    porque el lanzador oculto (conhost.exe --headless) no transmite el
#    código de salida. Por eso existe el archivo de estado del paso 4: es
#    donde se puede ver un fallo de una ejecución programada.
# ---------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    # Paso 0. `and` se evalúa de izquierda a derecha y se para en el
    # primer False, así que skip_scheduled_run() (que puede contactar con
    # los servidores) solo se llama cuando se ha pasado --scheduled y no
    # es un ensayo.
    if args.scheduled and not args.dry_run and skip_scheduled_run():
        sys.exit(0)
    setup_logging()

    if args.database == "gharchive":
        log.error("Refusing to rebuild 'gharchive': that database holds the frozen benchmark data")
        sys.exit(1)
    if not args.dry_run and not acquire_lock():
        log.warning("Another pipeline run is still in progress; skipping this one")
        sys.exit(0)

    try:
        ok = run(args.window_hours, args.lag_hours, args.database, args.dry_run)
    except Exception:
        log.exception("Run FAILED; the databases keep their previous contents unless a load had already started")
        ok = False
    finally:
        if not args.dry_run:
            LOCK_FILE.unlink(missing_ok=True)

    log.info("Status: %s", "SUCCESS" if ok else "FAILURE")
    # Paso 4: el resultado, en tu hora local, para quien abra
    # data/live/scheduled_status.txt. Si hay un fallo, remite al
    # registro, donde log.exception() escribió todos los detalles.
    if args.scheduled and not args.dry_run:
        outcome = "run SUCCEEDED" if ok else "run FAILED (see logs/pipeline.log); will try again at the next check"
        SCHEDULED_STATUS_FILE.write_text(f"{datetime.now():%Y-%m-%d %H:%M} (your time): {outcome}\n")
    sys.exit(0 if ok else 1)


# Ver la copia anotada de download_gharchive.py para la protección
# __name__ — aquí importa por partida doble: también es lo que permite
# que OTROS scripts importen las funciones de un script sin ejecutar su
# main().
if __name__ == "__main__":
    main()
