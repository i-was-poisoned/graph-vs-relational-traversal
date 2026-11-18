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
# NEW IN THIS VERSION — the --scheduled mode ("once a day, on its own"):
# already_ran_today(), servers_not_ready(), skip_scheduled_run(), and two
# small STATUS FILES (last_success_date.txt, scheduled_status.txt). Also
# new: `date` (a day without a time), local date vs UTC date, CONNECTION
# TIMEOUTS, and type hints like `str | None` ("a str, or None").
#
# WHY IT EXISTS — the project has TWO kinds of data:
#   1. FIXED data for the research: the frozen benchmark hour in the
#      "gharchive" databases, plus the hours YOU choose, loaded by hand
#      with build_hours.py into their own "gharchive-..." databases (see
#      docs_english/build_hours.py). Never changed automatically, so
#      measurements can always be repeated on the same data;
#   2. this LIVE PIPELINE: a rolling 24-hour window in SEPARATE databases
#      called "gharchive24h", rebuilt once a day.
#
# HOW IT GETS STARTED — Windows Task Scheduler runs
#     ./run.sh scripts/pipeline.py --scheduled
# when you log on and then every 15 minutes, HIDDEN (no window) through
# `conhost.exe --headless`. Most of those starts find nothing to do
# (today's run already succeeded, or Neo4j Desktop isn't open yet) and
# stop in a fraction of a second — see skip_scheduled_run(). For now the
# automatic pipeline is POSTPONED: the research phase uses the fixed data
# of point 1. The code stays ready for when it's switched on.
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
# Standard-library imports
#   logging   NEW: writing timestamped messages to a file and the screen
#             (see setup_logging()).
#   datetime, timedelta, timezone   NEW: dates/times and arithmetic on
#             them (see compute_window()).
#   date      NEW: a calendar DAY with no time (e.g. 2026-11-12).
#             date.today() is today's date on YOUR computer's clock (local
#             time, not UTC) — used by the --scheduled mode to decide
#             "has today's run already happened?" (see already_ran_today()).
#   os        for os.getpid() and os.environ (as in check_connections.py).
#   argparse, sys, time, Path: already explained in earlier scripts.
# ---------------------------------------------------------------------
import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
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
# The benchmark's files (data/2026-08-27-15.json, data/csv/) and
# build_hours.py's files (data/hours/) are separate and never touched.
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
LIVE_DIR = PROJECT_DIR / "data" / "live"
RAW_DIR = LIVE_DIR / "raw"
CSV_DIR = LIVE_DIR / "csv"
LOCK_FILE = LIVE_DIR / "pipeline.lock"
WINDOW_FILE = LIVE_DIR / "current_window.txt"
LOG_FILE = PROJECT_DIR / "logs" / "pipeline.log"
# ---------------------------------------------------------------------
# Two STATUS FILES, used only by the --scheduled mode. Each holds a
# single line and is OVERWRITTEN every time (it's not a history — the
# log is the history):
#   last_success_date.txt   the date of the last successful run, e.g.
#                           "2026-11-12". This is the pipeline's MEMORY
#                           between starts: each start is a brand-new
#                           Python process that remembers nothing, so
#                           "did I already run today?" has to be written
#                           down in a file.
#   scheduled_status.txt    what the LAST start found, e.g.
#                           "2026-11-12 10:15 (your time): Neo4j isn't
#                           answering (...); will try again at the next
#                           check" or "... run SUCCEEDED". Since the task
#                           runs hidden, this is the quickest way to see
#                           what it's doing.
# ---------------------------------------------------------------------
# --scheduled only: the local date of the last successful run, and what the last attempt found.
LAST_SUCCESS_FILE = LIVE_DIR / "last_success_date.txt"
SCHEDULED_STATUS_FILE = LIVE_DIR / "scheduled_status.txt"

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
# A LOCK FILE prevents two runs from working at the same time. Task
# Scheduler starts the pipeline every 15 minutes; if a run took longer
# than that (a slow download, a big window), the next start could begin
# while the first is still loading — and both would empty and fill the
# same databases at once. (Someone running it by hand during a scheduled
# run would cause the same problem.)
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
#      current_window.txt — and, for the real "gharchive24h" database,
#      today's date in last_success_date.txt (see below).
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
        # -------------------------------------------------------------
        # Remember "today's run succeeded" — but only when the REAL
        # database was rebuilt. A test run like --database gharchivetest
        # must not make the scheduled task think the day's work is done.
        #
        # date.today() is the LOCAL date (your computer's calendar), on
        # purpose, even though everything else here is in UTC: "once a
        # day" is meant from your point of view. Near midnight the two
        # can differ — at 00:30 in Madrid in winter it's still yesterday
        # in UTC — and a UTC date would make the daily run "change day"
        # at an odd local hour.
        #
        # f"{date.today():%Y-%m-%d}" formats it as "2026-11-12" (the same
        # date pattern as in hour_file_name()); "\n" ends the line.
        # -------------------------------------------------------------
        if database == DEFAULT_DATABASE:
            # Your computer's date, not UTC: "once a day" means once per day of yours.
            LAST_SUCCESS_FILE.write_text(f"{date.today():%Y-%m-%d}\n")
    log.info("Run finished in %.1f s", time.perf_counter() - run_start)
    return postgres_ok and neo4j_ok


# ---------------------------------------------------------------------
# parse_args(): the pipeline's options. All have defaults, so the
# scheduler can run it with no options at all.
#   --window-hours   size of the window (e.g. 6 for a quick test)
#   --lag-hours      how far back it ends
#   --database       which database to rebuild on both sides
#   --dry-run        show the plan only (a FLAG, like --exclude-bots was)
#   --scheduled      NEW: another flag, the one Task Scheduler passes.
#                    It adds the "is there anything to do?" checks of
#                    skip_scheduled_run() before the run (see main()).
#                    Run by hand without it, the pipeline always runs.
# formatter_class=RawDescriptionHelpFormatter keeps the docstring's line
# breaks when --help prints it.
#
# Note the help= text of --scheduled: two string literals side by side
# ("... run " "already ...") are JOINED into one by Python. It's a way to
# split a long text over two lines without a + sign.
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
# Answers "did today's run already succeed?", given:
#   last_success   the TEXT of last_success_date.txt, e.g. "2026-11-12\n",
#                  or None if the file doesn't exist yet (never ran);
#   today          today's date.
#
# `str | None` is a type hint meaning "a str OR None". The `|` reads as
# "or". It's only a note for the reader (Python doesn't enforce it), but
# it warns that the function must handle None.
#
# How it decides, left to right:
#   last_success is not None   — if it IS None, `and` stops right here
#                                and the answer is False. (That also
#                                avoids calling .strip() on None, which
#                                would be an error.)
#   last_success.strip()       — removes the "\n" (and any spaces) at the
#                                ends, so "2026-11-12\n" becomes
#                                "2026-11-12";
#   == f"{today:%Y-%m-%d}"     — compares it with today written the same
#                                way.
#
# Why is it so small and separate? It's a PURE function: it gets the
# file's text and the date as PARAMETERS, instead of reading the file and
# the clock itself. So it can be TESTED with any date, without files —
# the same reason compute_window() takes `now` as a parameter (see
# docs_english/test_pipeline.py).
# ---------------------------------------------------------------------
def already_ran_today(last_success: str | None, today: date) -> bool:
    # last_success is the text of LAST_SUCCESS_FILE (None if it doesn't exist yet).
    return last_success is not None and last_success.strip() == f"{today:%Y-%m-%d}"


# ---------------------------------------------------------------------
# def servers_not_ready() -> str | None:
#
# Asks both servers "are you there?", the cheapest possible way, and
# answers with:
#   None                 both answered — ready to work;
#   a short text         the REASON one didn't (e.g. "Neo4j isn't
#                        answering (...)").
# Returning "the problem, or None if there's none" is a common pattern:
# the caller checks `if reason is not None:` and has the message ready
# to show.
#
# It's the same kind of connection as in check_connections.py, with two
# differences:
#   - TIMEOUTS: connect_timeout=5 (psycopg) and connection_timeout=5
#     (Neo4j) give up after 5 seconds. When a server isn't running, the
#     check should fail QUICKLY, not hang — it's repeated every 15
#     minutes in the background.
#   - The exceptions are CAUGHT and turned into a message instead of
#     stopping the program: here, a server that isn't answering is a
#     normal situation (e.g. you haven't opened Neo4j Desktop yet), not
#     an error.
#
# "SELECT 1" is the smallest possible SQL query: it just proves the
# connection works. verify_connectivity() does the same for Neo4j (see
# check_connections.py).
#
# The password: PostgreSQL's comes from PGPASSWORD by itself, Neo4j's is
# read from os.environ — exactly as in check_connections.py. Both come
# from secrets.sh via run.sh; neither is ever written in the code.
#
# build_hours.py reuses this function as its "step 0" (see
# docs_english/build_hours.py).
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
# The --scheduled mode's GATE. Returns True if this start should do
# nothing, False if the real run should go ahead. Two reasons to skip,
# checked in this order:
#   1. today's run already succeeded  -> nothing to do until tomorrow;
#   2. a server isn't answering       -> try again in 15 minutes.
# The cheap check (reading a one-line file) comes first, so on most
# starts the servers aren't even contacted.
#
# Line by line:
#   X if condition else Y   (seen before) — read the file's text if it
#       exists, otherwise None, which already_ran_today() understands.
#   reason += "; will try ..."   `+=` adds text to the END of a string
#       ("a" += "b" gives "ab"). Only done if reason isn't None — adding
#       to None would be an error.
#   if reason is None: return False   nothing stops the run.
#   Otherwise: write ONE line to scheduled_status.txt (write_text
#       replaces the whole file, so it always shows the LAST check),
#       print it too, and return True.
#
# datetime.now() WITHOUT timezone.utc gives your computer's LOCAL time —
# hence "(your time)" in the text. That file is meant to be read by you,
# so local time is clearer; the log keeps using UTC.
#
# WHY IT RUNS BEFORE setup_logging(): it can be called up to 96 times a day (every
# 15 minutes) and almost always finds nothing to do. If each of those
# checks wrote to logs/pipeline.log, the real runs would be buried in
# thousands of "nothing to do" lines. So the checks only overwrite their
# one-line status file, and the log only gets the real runs.
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
# 0. NEW — SCHEDULED GATE: with --scheduled (and not --dry-run), ask
#    skip_scheduled_run() first; if there's nothing to do, stop at once
#    with sys.exit(0) — success, because "nothing to do" is normal. This
#    happens BEFORE setup_logging(), so these quick exits never touch the
#    log (see skip_scheduled_run()).
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
# 4. NEW — with --scheduled, write the run's OUTCOME to
#    scheduled_status.txt, so the file always tells what the last start
#    did, whether it skipped, succeeded or failed.
# 5. EXIT CODE: sys.exit(0) on success, sys.exit(1) on failure. Useful
#    when you run it by hand or from another script. BUT: Task
#    Scheduler's "Last Run Result" always shows 0x0 here, even after a
#    failure, because the hidden launcher (conhost.exe --headless)
#    doesn't pass the exit code on. That's why the status file of step 4
#    exists: it's where a scheduled failure can be seen.
# ---------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    # Step 0. `and` evaluates left to right and stops at the first False,
    # so skip_scheduled_run() (which may contact the servers) is only
    # called when --scheduled was given and it's not a dry run.
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
    # Step 4: the outcome, in your local time, for whoever opens
    # data/live/scheduled_status.txt. On failure it points to the log,
    # where log.exception() wrote the full details.
    if args.scheduled and not args.dry_run:
        outcome = "run SUCCEEDED" if ok else "run FAILED (see logs/pipeline.log); will try again at the next check"
        SCHEDULED_STATUS_FILE.write_text(f"{datetime.now():%Y-%m-%d %H:%M} (your time): {outcome}\n")
    sys.exit(0 if ok else 1)


# See download_gharchive.py's annotated copy for the __name__ guard —
# here it matters twice: it's also what lets OTHER scripts import a
# script's functions without running its main().
if __name__ == "__main__":
    main()
