"""Build a database from GH Archive hours that you choose, on both sides.

The benchmark's fixed hour lives in the "gharchive" databases and never
changes. This script lets you load other data to compare with it: it asks
which date, starting hour and number of consecutive hours you want, then

    1. downloads those hours to data/hours/ (hours already there are reused);
    2. extracts the CSV files from them (extract_csv.py), into
       data/hours/csv/<database name>/;
    3. empties the database named after the hours, in PostgreSQL and in Neo4j:
       it deletes it (if it exists) and creates it again, then checks that both
       sides really are empty, and stops if they aren't;
           1 hour  from 2026-08-27 15:00 UTC -> "gharchive-2026-08-27-15"
           3 hours from 2026-08-27 15:00 UTC -> "gharchive-2026-08-27-15-3h"
    4. loads the CSVs into both (load_postgres.py, load_neo4j.py).

Each choice gets its own database, so "gharchive" and "gharchive24h" are never
touched. Loading the same choice again empties and rebuilds only its own databases.

Usage (it asks the rest; press Enter to keep the value in brackets):
    ./run.sh scripts/build_hours.py
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg
from neo4j import GraphDatabase
from psycopg import sql

import download_gharchive
import extract_csv
import load_neo4j
import load_postgres
import pipeline

HOURS_DIR = Path(__file__).resolve().parent.parent / "data" / "hours"
# GH Archive's events have had today's format since 2015; older files use another one.
FIRST_DATE = date(2015, 1, 1)
# A week. More would take very long to load and need a lot of memory in Neo4j.
MAX_HOURS = 168


def parse_date(text: str) -> date:
    # "2026-08-27" -> date(2026, 8, 27); anything else raises ValueError with a readable message.
    try:
        day = datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"'{text}' isn't a date like 2026-08-27 (year-month-day)") from None
    if day < FIRST_DATE:
        raise ValueError(f"Dates before {FIRST_DATE} use an older GH Archive format; choose a later one")
    return day


def parse_hour(text: str) -> int:
    # "15" -> 15. GH Archive hours are UTC, 0 to 23.
    if not text.strip().isdigit() or not 0 <= int(text) <= 23:
        raise ValueError(f"'{text}' isn't an hour from 0 to 23 (UTC)")
    return int(text)


def parse_count(text: str) -> int:
    # "3" -> 3 consecutive hours, from 1 to MAX_HOURS.
    if not text.strip().isdigit() or not 1 <= int(text) <= MAX_HOURS:
        raise ValueError(f"'{text}' isn't a number of hours from 1 to {MAX_HOURS}")
    return int(text)


def chosen_hours(day: date, hour: int, count: int) -> list[datetime]:
    # Example: 2026-08-27, 23, 2 -> 2026-08-27 23:00 and 2026-08-28 00:00 (crossing midnight is fine).
    first = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
    return [first + timedelta(hours=i) for i in range(count)]


def hours_are_published(hours: list[datetime], now: datetime) -> bool:
    # GH Archive publishes each hour's file a little after the hour ends. Accept the hours only
    # if the last one ended at least one full hour before the current hour began.
    last_end = hours[-1] + timedelta(hours=1)
    return last_end <= now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)


def database_name(hours: list[datetime]) -> str:
    # Neo4j allows letters, digits, dots and dashes in database names (not "_"), so dashes it is.
    # The hour has no leading zero, like GH Archive's file names.
    name = f"gharchive-{hours[0]:%Y-%m-%d}-{hours[0].hour}"
    return name if len(hours) == 1 else f"{name}-{len(hours)}h"


def describe(hours: list[datetime]) -> str:
    # e.g. "2026-08-27 15:00 -> 2026-08-27 18:00 UTC (3 hours)"
    end = hours[-1] + timedelta(hours=1)
    return f"{hours[0]:%Y-%m-%d %H:00} -> {end:%Y-%m-%d %H:00} UTC ({len(hours)} hour{'s' * (len(hours) > 1)})"


def ask_hours(now: datetime, ask=input) -> list[datetime] | None:
    # Asks for the date, the first hour and how many hours until all are valid, then asks for
    # confirmation. Returns None if the answer to the confirmation is "n".
    # "ask" is input() unless a test replaces it.
    default_date, default_hour = download_gharchive.DEFAULT_DATE, download_gharchive.DEFAULT_HOUR
    while True:
        try:
            day = parse_date(ask(f"Date (UTC) [{default_date}]: ") or default_date)
            hour = parse_hour(ask(f"First hour (UTC, 0-23) [{default_hour}]: ") or str(default_hour))
            count = parse_count(ask("How many consecutive hours [1]: ") or "1")
        except ValueError as error:
            print(error)
            continue
        hours = chosen_hours(day, hour, count)
        if not hours_are_published(hours, now):
            print("GH Archive hasn't published all those hours yet: "
                  "the last one must end at least an hour before the current hour.")
            continue

        answer = ask(f'Load {describe(hours)} into "{database_name(hours)}"? '
                     "(if that database already exists, it's emptied first) [Y/n]: ")
        return hours if answer.strip().lower() in ("", "y", "yes", "s", "si", "sí") else None


def may_be_emptied(name: str) -> bool:
    # Only databases made by this script may be deleted: never "gharchive" (the frozen
    # benchmark), "gharchive24h" (the pipeline's) or anything else on the servers.
    return name.startswith("gharchive-")


def recreate_databases(name: str) -> None:
    # Deleting the whole database and creating it again is the surest way to empty it:
    # nothing from before survives (tables, rows, nodes, relationships, constraints).
    if not may_be_emptied(name):
        raise ValueError(f'Refusing to empty "{name}": build_hours.py only empties databases named gharchive-...')

    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        # WITH (FORCE) first closes other connections to it (e.g. pgAdmin), which would block the DROP.
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    print(f'PostgreSQL: "{name}" deleted (if it existed) and created again')

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        # CREATE OR REPLACE = delete it if it exists, then create it (Enterprise Edition only).
        # WAIT: don't return until the new database is online.
        driver.execute_query(f"CREATE OR REPLACE DATABASE `{name}` WAIT", database_="system")
    print(f'Neo4j:      "{name}" deleted (if it existed) and created again')


def databases_are_empty(name: str) -> bool:
    # Checks both sides and prints what it finds; True only if everything is 0.
    with psycopg.connect(host="localhost", user="postgres", dbname=name) as conn:
        tables = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'").fetchone()[0]

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        def count(query: str) -> int:
            return driver.execute_query(query, database_=name).records[0][0]
        nodes = count("MATCH (n) RETURN count(n)")
        relationships = count("MATCH ()-[r]->() RETURN count(r)")
        constraints = count("SHOW CONSTRAINTS YIELD name RETURN count(name)")

    found = {"PostgreSQL tables": tables, "Neo4j nodes": nodes,
             "Neo4j relationships": relationships, "Neo4j constraints": constraints}
    for what, how_many in found.items():
        print(f"  {what:<20} {how_many:>3}   {'empty' if how_many == 0 else 'NOT EMPTY'}")
    return all(how_many == 0 for how_many in found.values())


def build(hours: list[datetime]) -> bool:
    name = database_name(hours)
    csv_dir = HOURS_DIR / "csv" / name

    print(f"\n== 1. Download {len(hours)} hour file(s) to {HOURS_DIR}")
    files = []
    for hour in hours:
        path = HOURS_DIR / pipeline.hour_file_name(hour)
        if path.exists():
            print(f"Already downloaded: {path.name}")
        else:
            download_gharchive.fetch_gz(f"{hour:%Y-%m-%d}", hour.hour, HOURS_DIR)
        files.append(path)

    print(f"\n== 2. Extract the CSV files to {csv_dir}")
    actors, repos, pairs, skipped_bot_events = extract_csv.extract(files)
    extract_csv.write_all(csv_dir, actors, repos, pairs)
    print(f"{len(actors)} actors, {len(repos)} repos, {len(pairs)} connections "
          f"({skipped_bot_events} bot events skipped)")

    print(f'\n== 3. Empty "{name}" on both sides, and check that it is empty')
    recreate_databases(name)
    if not databases_are_empty(name):
        print("The database isn't empty after being recreated; nothing was loaded.")
        return False

    print("\n== 4. Load PostgreSQL")
    postgres_ok = load_postgres.load(csv_dir, name)

    print("\n== 5. Load Neo4j")
    neo4j_ok = load_neo4j.load(csv_dir, name)

    return postgres_ok and neo4j_ok


def main() -> None:
    try:
        hours = ask_hours(datetime.now(timezone.utc))
    except (EOFError, KeyboardInterrupt):
        # EOFError: there's no keyboard to answer (this script is meant to be run by hand).
        print("\nNo hours chosen; nothing done.")
        sys.exit(1)
    if hours is None:
        print("Nothing done.")
        sys.exit(0)

    ok = build(hours)
    name = database_name(hours)
    print(f'\n{"Done" if ok else "Finished with MISMATCHES (see above)"}: database "{name}" on both sides.')
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
