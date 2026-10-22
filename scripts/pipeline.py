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

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from neo4j import GraphDatabase
from psycopg import sql

import download_gharchive
import extract_csv
import load_neo4j
import load_postgres

PROJECT_DIR = Path(__file__).resolve().parent.parent
LIVE_DIR = PROJECT_DIR / "data" / "live"
RAW_DIR = LIVE_DIR / "raw"
CSV_DIR = LIVE_DIR / "csv"
LOCK_FILE = LIVE_DIR / "pipeline.lock"
WINDOW_FILE = LIVE_DIR / "current_window.txt"
LOG_FILE = PROJECT_DIR / "logs" / "pipeline.log"

DEFAULT_DATABASE = "gharchive24h"  # Neo4j doesn't allow "_" in database names
DEFAULT_WINDOW_HOURS = 24
DEFAULT_LAG_HOURS = 24
STALE_LOCK_HOURS = 3

log = logging.getLogger("pipeline")


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


def compute_window(now: datetime, window_hours: int, lag_hours: int) -> list[datetime]:
    # Example (24 h, lag 24 h): now 2026-10-22 11:15 UTC -> hours 2026-10-20 11:00 ... 2026-10-21 10:00,
    # i.e. the window 2026-10-20 11:00 -> 2026-10-21 11:00.
    end = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=lag_hours)
    start = end - timedelta(hours=window_hours)
    return [start + timedelta(hours=i) for i in range(window_hours)]


def hour_file_name(hour: datetime) -> str:
    # Same naming as GH Archive: UTC hour without a leading zero, e.g. 2026-10-20-5.json.gz
    return f"{hour:%Y-%m-%d}-{hour.hour}.json.gz"


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


if __name__ == "__main__":
    main()
