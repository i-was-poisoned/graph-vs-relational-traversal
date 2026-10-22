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
# POR QUÉ EXISTE — el proyecto tiene ahora DOS procesos:
#   1. el BENCHMARK: una hora fija y congelada en las bases de datos
#      "gharchive", cargada a mano y nunca cambiada automáticamente (para
#      que las mediciones se puedan repetir siempre sobre los mismos
#      datos);
#   2. este PIPELINE EN VIVO: una ventana móvil de 24 horas en bases de
#      datos SEPARADAS llamadas "gharchive24h", reconstruida cada vez que
#      se ejecuta (pensado para ejecutarse cada hora, programado con el
#      Programador de tareas de Windows).
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
It's meant to be run every hour by Windows Task Scheduler (see project notes).

Usage:
    ./run.sh scripts/pipeline.py
    ./run.sh scripts/pipeline.py --dry-run
    ./run.sh scripts/pipeline.py --window-hours 6 --lag-hours 2
"""

# ---------------------------------------------------------------------
# Importaciones de la biblioteca estándar
#   logging   NUEVO: escribir mensajes con fecha y hora en un archivo y
#             en pantalla (ver setup_logging()).
#   datetime, timedelta, timezone   NUEVO: fechas/horas y cálculos con
#             ellas (ver compute_window()).
#   os        para os.getpid() y os.environ (como en
#             check_connections.py).
#   argparse, sys, time, Path: ya explicados en los scripts anteriores.
# ---------------------------------------------------------------------
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
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
# Los archivos del benchmark (data/2026-08-27-15.json, data/csv/) están
# aparte y nunca se tocan.
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
LIVE_DIR = PROJECT_DIR / "data" / "live"
RAW_DIR = LIVE_DIR / "raw"
CSV_DIR = LIVE_DIR / "csv"
LOCK_FILE = LIVE_DIR / "pipeline.lock"
WINDOW_FILE = LIVE_DIR / "current_window.txt"
LOG_FILE = PROJECT_DIR / "logs" / "pipeline.log"

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
DEFAULT_DATABASE = "gharchive24h"  # Neo4j no permite "_" en los nombres de base de datos
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
    # Horas del registro en UTC, como los nombres de archivo de GH Archive, para que la
    # ventana y el registro cuadren.
    formatter = logging.Formatter("%(asctime)s UTC  %(levelname)-7s  %(message)s", "%Y-%m-%d %H:%M:%S")
    formatter.converter = time.gmtime
    # Los handlers van en el logger raíz, así que las advertencias de los otros scripts
    # (p. ej. extract_csv) acaban en el mismo archivo de registro.
    root = logging.getLogger()
    for handler in (logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    # El driver de Neo4j registra notificaciones informativas del servidor (p. ej. "server
    # has caught up" tras CREATE DATABASE); en este registro solo caben sus advertencias y
    # errores.
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
    # Ejemplo (24 h, retraso 24 h): now 2026-10-22 11:15 UTC -> horas 2026-10-20 11:00 ... 2026-10-21 10:00,
    # es decir, la ventana 2026-10-20 11:00 -> 2026-10-21 11:00.
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
    # El mismo nombre que GH Archive: hora UTC sin cero a la izquierda, p. ej. 2026-10-20-5.json.gz
    return f"{hour:%Y-%m-%d}-{hour.hour}.json.gz"


# ---------------------------------------------------------------------
# def acquire_lock() -> bool:
#
# Un ARCHIVO DE BLOQUEO impide que dos ejecuciones trabajen a la vez. Si
# una ejecución tardara más de una hora, el programador de tareas
# lanzaría la siguiente mientras la primera todavía está cargando — y las
# dos vaciarían y llenarían las mismas bases de datos a la vez.
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
    # Si una ejecución anterior sigue en marcha (o falló sin limpiar), no empezar una segunda.
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
    # También es una comprobación previa: si algún servidor no responde, parar antes de cambiar nada.
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
#      current_window.txt.
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
# formatter_class=RawDescriptionHelpFormatter conserva los saltos de
# línea del docstring cuando --help lo imprime.
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
    return parser.parse_args()


# ---------------------------------------------------------------------
# def main() -> None:
#
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
# 4. CÓDIGO DE SALIDA: sys.exit(0) si hay éxito, sys.exit(1) si hay
#    fallo. Un programador de tareas como el de Windows muestra este
#    código como el "resultado de la última ejecución" de la tarea, así
#    que una ejecución fallida se detecta sin abrir el registro.
# ---------------------------------------------------------------------
def main() -> None:
    args = parse_args()
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
    sys.exit(0 if ok else 1)


# Ver la copia anotada de download_gharchive.py para la protección
# __name__ — aquí importa por partida doble: también es lo que permite
# que OTROS scripts importen las funciones de un script sin ejecutar su
# main().
if __name__ == "__main__":
    main()
