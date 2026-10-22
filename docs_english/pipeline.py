########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/pipeline.py.
# It is NOT meant to be run as part of the project pipeline — it lives in
# docs_english/ because its purpose is to teach, not to execute. The real, "clean"
# script (with none of this commentary) is scripts/pipeline.py.
#
# This file assumes you've already read the earlier annotated scripts —
# download_gharchive.py (fetch_gz), extract_csv.py (extract, write_all),
# load_postgres.py and load_neo4j.py (load), and check_connections.py.
# pipeline.py is the first script that doesn't do one job itself: it
# COORDINATES the others. What's NEW here is mostly data-engineering
# practice: working with dates and times in UTC (datetime, timedelta,
# timezone), importing our own scripts as MODULES, LOGGING to a file,
# a LOCK FILE so two runs never overlap, IDEMPOTENT database creation,
# try/except/finally around a whole run, and EXIT CODES for a scheduler.
#
# WHY IT EXISTS — the project now has TWO processes:
#   1. the BENCHMARK: one fixed, frozen hour in the "gharchive" databases,
#      loaded by hand, never changed automatically (so measurements can
#      always be repeated on the same data);
#   2. this LIVE PIPELINE: a rolling 24-hour window in SEPARATE databases
#      called "gharchive24h", rebuilt every time it runs (meant to run
#      every hour, scheduled by Windows Task Scheduler).
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
# Standard-library imports
#   logging   NEW: writing timestamped messages to a file and the screen
#             (see setup_logging()).
#   datetime, timedelta, timezone   NEW: dates/times and arithmetic on
#             them (see compute_window()).
#   os        for os.getpid() and os.environ (as in check_connections.py).
#   argparse, sys, time, Path: already explained in earlier scripts.
# ---------------------------------------------------------------------
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# psycopg and GraphDatabase: the two database connectors (see
# check_connections.py). `sql` is psycopg's helper for building SQL safely
# when a NAME (not a value) has to go into the query — see
# ensure_databases().
import psycopg
from neo4j import GraphDatabase
from psycopg import sql

# ---------------------------------------------------------------------
# import download_gharchive, extract_csv, load_neo4j, load_postgres
#
# NEW: importing OUR OWN scripts. Every .py file is also a MODULE that
# other Python files can import. When you run scripts/pipeline.py, Python
# looks for imports in the folder the script is in (scripts/), so it
# finds the other scripts there.
#
# Importing a script runs its top-level code (constants, function
# definitions) but NOT its main(): that's exactly what the
# `if __name__ == "__main__":` guard at the bottom of each script is for.
# So the pipeline gets their functions — download_gharchive.fetch_gz(),
# extract_csv.extract(), load_postgres.load()... — without running them as
# programs. That's REUSE: the pipeline doesn't copy their code, so the
# benchmark and the pipeline always use exactly the same logic.
# ---------------------------------------------------------------------
import download_gharchive
import extract_csv
import load_neo4j
import load_postgres

# ---------------------------------------------------------------------
# Where things live. Everything under data/ and logs/ is git-ignored:
#   data/live/raw/               the window's hourly .json.gz files
#   data/live/csv/               the three CSVs for the 24-hour databases
#   data/live/pipeline.lock      exists only while a run is in progress
#   data/live/current_window.txt the last window loaded successfully
#   logs/pipeline.log            the history of every run
# The benchmark's files (data/2026-08-27-15.json, data/csv/) are separate
# and never touched.
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
#   Not "gharchive_24h": Neo4j database names may only contain letters,
#   digits, dots and dashes — no underscores. The same name is used on
#   both sides, as with the benchmark's "gharchive".
# DEFAULT_WINDOW_HOURS / DEFAULT_LAG_HOURS — 24 hours of data, ending 24
#   hours ago (see compute_window()). Both can be changed from the
#   command line.
# STALE_LOCK_HOURS — how old a lock file must be before it's considered
#   abandoned (see acquire_lock()).
# ---------------------------------------------------------------------
DEFAULT_DATABASE = "gharchive24h"  # Neo4j doesn't allow "_" in database names
DEFAULT_WINDOW_HOURS = 24
DEFAULT_LAG_HOURS = 24
STALE_LOCK_HOURS = 3

# ---------------------------------------------------------------------
# log = logging.getLogger("pipeline")
#
# A LOGGER is an object for writing messages with a LEVEL, which says how
# important each one is:
#   log.info("...")       normal progress ("Window: ...", "Status: ...")
#   log.warning("...")    something odd, but the run goes on
#   log.error("...")      something went wrong
#   log.exception("...")  an error, plus the full traceback of the
#                         exception being handled
# Compared with print(), each message gets a timestamp and a level, and
# can go to several places at once (here: a file and the screen).
# ---------------------------------------------------------------------
log = logging.getLogger("pipeline")


# ---------------------------------------------------------------------
# def setup_logging() -> None:
#
# Configures WHERE messages go and HOW they look:
#
#   Formatter("%(asctime)s UTC  %(levelname)-7s  %(message)s", ...)
#     every line becomes e.g.
#     2026-10-22 12:44:14 UTC  INFO     Window: 2026-10-20 12:00 -> ...
#   formatter.converter = time.gmtime
#     write the times in UTC instead of the computer's local time — the
#     same clock GH Archive's file names use, so the log and the window
#     can be compared directly (Portugal is one hour ahead of UTC in
#     summer, and that one hour would otherwise cause confusion).
#   FileHandler(LOG_FILE)    append each message to logs/pipeline.log
#   StreamHandler(sys.stdout) and also show it on screen
#
# The handlers go on the ROOT logger (logging.getLogger() with no name),
# the parent of every logger. Messages from any logger "bubble up" to
# it, so the warning extract_csv.py writes with its own logger (e.g.
# "Skipped 2 event(s) without an actor or repo id") ends up in the same
# file.
#
# logging.getLogger("neo4j").setLevel(logging.WARNING)
#   The Neo4j driver has its own logger and reports INFORMATIONAL server
#   notifications at INFO level. The first real run printed a long one
#   ("server has caught up") right after CREATE DATABASE — harmless, but
#   noise. This keeps only the driver's warnings and errors.
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
# Works out WHICH HOURS the window contains. A `datetime` is a date and
# time together; a `timedelta` is a duration, and you can add or subtract
# one from a datetime ("this time minus 24 hours").
#
# Step by step, with now = 2026-10-22 11:15 UTC and the defaults:
#   now.replace(minute=0, second=0, microsecond=0)
#       -> 2026-10-22 11:00   (round DOWN to the start of the hour)
#   - timedelta(hours=lag_hours)        (24)
#       -> end   = 2026-10-21 11:00   the window ENDS here
#   end - timedelta(hours=window_hours) (24)
#       -> start = 2026-10-20 11:00   the window STARTS here
#   [start + timedelta(hours=i) for i in range(24)]
#       -> 2026-10-20 11:00, 12:00, ..., 2026-10-21 10:00   (24 hours)
#
# Each item is the START of one hourly file: the last one, 10:00, covers
# 10:00-11:00, so the window ends exactly at 11:00. The `end` hour itself
# is NOT included.
#
# Why the lag: GH Archive publishes each hour a little after it ends, and
# occasionally later. Ending the window a day ago means every hour in it
# has surely been published. The lag is a parameter (--lag-hours), so it
# can be made smaller later.
#
# `now` is a parameter (instead of reading the clock inside) so the
# function can be TESTED with any time, as in the example above.
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
# f"{hour:%Y-%m-%d}" formats the datetime with a date pattern:
#   %Y year (2026), %m month (10), %d day (20)  ->  "2026-10-20"
# hour.hour is just the hour as a number (5), so there's no leading zero
# — exactly how GH Archive names its files: 2026-10-20-5.json.gz.
# ---------------------------------------------------------------------
def hour_file_name(hour: datetime) -> str:
    # Same naming as GH Archive: UTC hour without a leading zero, e.g. 2026-10-20-5.json.gz
    return f"{hour:%Y-%m-%d}-{hour.hour}.json.gz"


# ---------------------------------------------------------------------
# def acquire_lock() -> bool:
#
# A LOCK FILE prevents two runs from working at the same time. If one run
# took longer than an hour, the scheduler would start the next one while
# the first is still loading — and both would empty and fill the same
# databases at once.
#
#   - No lock file?                -> create it and go ahead (True).
#   - Lock file younger than 3 h?  -> another run is in progress: don't
#                                     start (False).
#   - Lock file older than 3 h?    -> a previous run crashed without
#                                     removing it ("stale"): delete it,
#                                     log a warning, and go ahead.
#
# LOCK_FILE.stat().st_mtime is when the file was last written (in seconds
# since 1970); time.time() is now, in the same unit, so the difference
# divided by 3600 is its age in hours. The file's content (the process id
# and start time) is only there for whoever looks at it by hand.
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
# Makes data/live/raw/ contain EXACTLY the window's hour files:
#
#   1. wanted = the set of file names that should be there.
#   2. Any file in the folder that isn't wanted (an hour that has left the
#      window, or a leftover ".part" from an interrupted download) is
#      deleted. RAW_DIR.iterdir() lists the folder's contents.
#   3. missing = the window's hours whose file isn't there yet, and only
#      those are downloaded, with download_gharchive.fetch_gz().
#
# So the first run downloads all 24 hours, and every later run downloads
# just the one new hour and deletes the one that left — this is what
# makes running every hour cheap.
#
# log.info("%d of %d ...", a, b, c) — logging fills in the %d
# placeholders with the extra arguments, in order (%d = whole number).
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
# Makes sure the target database exists on BOTH sides, creating it only
# if it doesn't. That's IDEMPOTENCE: running it once or ten times leaves
# the same result, so the very first run sets itself up, and a database
# deleted by mistake is simply recreated by the next run.
#
# PostgreSQL:
#   - Connects to the always-present "postgres" database (you can't
#     create a database while connected to it).
#   - autocommit=True: CREATE DATABASE can't run inside a transaction.
#   - pg_database is PostgreSQL's catalogue of databases: the SELECT
#     asks "is there one with this name?". %s is a PARAMETER: psycopg
#     inserts the value safely.
#   - A database NAME can't be passed as a parameter, so it's built with
#     sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)),
#     which quotes the name correctly instead of pasting raw text into
#     the SQL.
#
# Neo4j:
#   CREATE DATABASE `gharchive24h` IF NOT EXISTS WAIT
#     IF NOT EXISTS  does nothing if it already exists
#     WAIT           doesn't return until the new database is online
#   It's sent to the "system" database, where Neo4j manages databases
#   and users. (Creating extra databases needs Neo4j's Enterprise
#   Edition — the one Neo4j Desktop includes.)
#
# It's also a PRE-FLIGHT CHECK: it's called before any load, so if either
# server is down, the run fails here, before anything has been emptied.
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
# One complete run, step by step, each one timed and logged:
#   1. compute the window from the current UTC time;
#   2. (dry run: only list the files and stop — nothing changes);
#   3. sync the hour files (download what's missing);
#   4. extract the CSVs, reusing extract_csv's functions;
#   5. ensure both databases exist (and that both servers answer);
#   6. load PostgreSQL, then Neo4j, reusing the loaders, with the
#      database name passed in;
#   7. if both loads match their CSVs, record the window in
#      current_window.txt.
# Returns True only if both loads' checks came out OK.
#
# The ORDER is deliberate: everything that can fail without harm
# (downloading, extracting, connecting) happens BEFORE any database is
# emptied. If an hour is missing or a server is down, the databases keep
# the previous window.
#
# hours[-1] + timedelta(hours=1) is the window's END: the last hour's
# start plus one hour.
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
# parse_args(): the pipeline's options. All have defaults, so the
# scheduler can run it with no options at all.
#   --window-hours   size of the window (e.g. 6 for a quick test)
#   --lag-hours      how far back it ends
#   --database       which database to rebuild on both sides
#   --dry-run        show the plan only (a FLAG, like --exclude-bots was)
# formatter_class=RawDescriptionHelpFormatter keeps the docstring's line
# breaks when --help prints it.
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
# 1. SAFETY GUARD: refuse to touch "gharchive", the frozen benchmark
#    database — even if someone types --database gharchive by mistake.
# 2. LOCK: if another run is in progress, skip this one. sys.exit(0)
#    (success) on purpose: skipping is normal, not an error.
# 3. try / except / finally:
#      try      run the whole pipeline;
#      except   if ANYTHING raises an exception, log it with its full
#               traceback (log.exception) and mark the run as failed,
#               instead of crashing without leaving a trace in the log;
#      finally  runs in EVERY case, success or failure: remove the lock
#               file, so the next run isn't blocked.
# 4. EXIT CODE: sys.exit(0) on success, sys.exit(1) on failure. A
#    scheduler like Windows Task Scheduler shows this code as the task's
#    "last run result", so a failed run can be spotted without opening
#    the log.
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


# See download_gharchive.py's annotated copy for the __name__ guard —
# here it matters twice: it's also what lets OTHER scripts import a
# script's functions without running its main().
if __name__ == "__main__":
    main()
