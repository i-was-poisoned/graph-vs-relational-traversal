########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/load_postgres.py.
# It is NOT meant to be run as part of the project pipeline — it lives in
# docs_english/ because its purpose is to teach, not to execute. The real, "clean"
# script (with none of this commentary) is scripts/load_postgres.py.
#
# This file assumes you've already read the earlier annotated scripts,
# especially check_connections.py (psycopg, connecting, `with`, PGPASSWORD)
# and extract_csv.py (the CSV files this script loads). This file focuses
# on what's NEW: SQL to create tables (CREATE TABLE, PRIMARY KEY,
# REFERENCES, CREATE INDEX), loading CSV files with COPY, TRANSACTIONS and
# COMMIT, ANALYZE, and measuring time with time.perf_counter().
#
# Run it through run.sh (it needs PGPASSWORD):
#     ./run.sh scripts/load_postgres.py
########################################################################

"""Load the extracted CSV files into the PostgreSQL "gharchive" database.

Creates (or re-creates) the three benchmark tables and fills them from the CSV
files written by extract_csv.py:

    actor        (id PRIMARY KEY, login)
    repo         (id PRIMARY KEY, name)
    actor_repo   (actor_id -> actor.id, repo_id -> repo.id,
                  PRIMARY KEY (actor_id, repo_id)), plus an index on repo_id

Every run starts from empty tables, so running it twice gives the same result.
At the end it checks that each table has exactly as many rows as its CSV file.

Usage:
    ./run.sh scripts/load_postgres.py
    ./run.sh scripts/load_postgres.py --csv-dir data/csv
"""

# ---------------------------------------------------------------------
# import time — NEW: the standard-library module for clocks. We only use
# time.perf_counter() (see seconds_since() below).
# argparse, sys, Path, psycopg: already explained in earlier scripts.
# ---------------------------------------------------------------------
import argparse
import sys
import time
from pathlib import Path

import psycopg

# Same constants as extract_csv.py (where the CSVs are) and
# check_connections.py (how to reach PostgreSQL).
PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "data" / "csv"
POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}

# ---------------------------------------------------------------------
# SCHEMA — the SQL that builds the three tables
#
# A Python string written with triple quotes ("""...""") can span many
# lines. This one holds SQL, PostgreSQL's language, which is sent to the
# server as-is.
#
# DROP TABLE IF EXISTS ...
#   Deletes the table if it's already there (from a previous run), and
#   does nothing if it isn't. That's what makes the script REPEATABLE:
#   every run starts from scratch. The ORDER matters: actor_repo points
#   at actor and repo, so it's deleted FIRST (you can't delete a table
#   another one still depends on).
#
# CREATE TABLE actor ( id BIGINT PRIMARY KEY, login TEXT NOT NULL );
#   BIGINT       a whole number big enough for GitHub's ids (an ordinary
#                INTEGER stops at about 2,100 million; some ids already
#                go beyond that, and BIGINT is the safe choice).
#   TEXT         text of any length.
#   NOT NULL     the value can never be missing.
#   PRIMARY KEY  the column that identifies each row: it must be unique,
#                can't be missing, and PostgreSQL automatically builds an
#                INDEX on it, so finding a row by id is instant.
#   (login is NOT unique: remember the two "Copilot" accounts.)
#
# CREATE TABLE actor_repo (... REFERENCES actor (id) ...)
#   REFERENCES makes a FOREIGN KEY: every actor_id must exist in
#   actor.id, and every repo_id in repo.id. The database itself refuses
#   a connection pointing at an actor or repo that doesn't exist.
#
#   PRIMARY KEY (actor_id, repo_id) — a primary key made of TWO columns:
#   the PAIR must be unique. This is the database enforcing "one
#   connection per actor-repo pair, no repeats", the same rule
#   extract_csv.py applied with its set.
#
# CREATE INDEX actor_repo_repo_id_idx ON actor_repo (repo_id);
#   An INDEX is like the index at the back of a book: instead of reading
#   every page to find a word, you look it up and jump straight to it.
#   The two-column primary key is ordered by actor_id first, so it's
#   great for "an actor's repos" but not for "a repo's actors". This
#   extra index covers that other direction. The benchmark walk
#   (actor -> repo -> actor -> repo) needs BOTH, at every hop.
#
# Lines starting with -- inside the SQL are SQL comments (like # in
# Python); PostgreSQL ignores them.
# ---------------------------------------------------------------------
# Dropped child-first (actor_repo points at actor and repo), created parent-first.
SCHEMA = """
DROP TABLE IF EXISTS actor_repo;
DROP TABLE IF EXISTS repo;
DROP TABLE IF EXISTS actor;

CREATE TABLE actor (
    id    BIGINT PRIMARY KEY,
    login TEXT   NOT NULL
);

CREATE TABLE repo (
    id   BIGINT PRIMARY KEY,
    name TEXT   NOT NULL
);

CREATE TABLE actor_repo (
    actor_id BIGINT NOT NULL REFERENCES actor (id),
    repo_id  BIGINT NOT NULL REFERENCES repo (id),
    PRIMARY KEY (actor_id, repo_id)
);

-- The primary key already finds an actor's repos quickly (actor_id comes first).
-- This index does the same in the other direction: a repo's actors.
CREATE INDEX actor_repo_repo_id_idx ON actor_repo (repo_id);
"""

# ---------------------------------------------------------------------
# TABLES — a list of (table, columns, CSV file) tuples, one per table.
# Keeping this in one list lets the same loop load and check all three.
# The ORDER is the load order: actor and repo before actor_repo, because
# of the foreign keys (a connection can only be loaded once its actor and
# its repo exist).
# ---------------------------------------------------------------------
# (table, columns, CSV file) in load order: parents before actor_repo.
TABLES = [
    ("actor", "id, login", "actors.csv"),
    ("repo", "id, name", "repos.csv"),
    ("actor_repo", "actor_id, repo_id", "actor_repo.csv"),
]


# ---------------------------------------------------------------------
# def count_csv_rows(path) -> int:
#
# Counts a CSV file's data rows, to compare with the table afterwards.
# sum(1 for _ in f) adds 1 for every line of the file (a compact way of
# counting lines); - 1 removes the header line (id,login), which isn't
# data.
# ---------------------------------------------------------------------
def count_csv_rows(path: Path) -> int:
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # minus the header line


# ---------------------------------------------------------------------
# def copy_csv(cur, table, columns, path) -> None:
#
# COPY is PostgreSQL's BULK LOADING command: much faster than one INSERT
# per row, because the data goes in as one continuous stream.
#
#   COPY actor (id, login) FROM STDIN WITH (FORMAT csv, HEADER true)
#     FROM STDIN    the data arrives through the connection ("standard
#                   input"), sent by Python, instead of being read from a
#                   file on the server. The server never needs access to
#                   your files.
#     FORMAT csv    the data is CSV.
#     HEADER true   skip the first line (the column names).
#
# cur.copy(...) opens that stream; copy.write(chunk) sends data into it.
#
# `with A as f, B as copy:` — two `with`s on one line; the backslash \ at
# the end of the line just means "the statement continues on the next
# line".
#
# while chunk := f.read(1024 * 1024):
#   f.read(1024 * 1024) reads up to 1 MB of the file at a time, so even a
#   huge file never has to fit in memory all at once.
#   `:=` (the "walrus operator") assigns AND checks in one go: "read a
#   chunk, store it in `chunk`, and keep looping while it isn't empty".
#   At the end of the file, f.read() returns "" (empty), and the loop
#   stops.
# ---------------------------------------------------------------------
def copy_csv(cur: psycopg.Cursor, table: str, columns: str, path: Path) -> None:
    # COPY ... FROM STDIN: Python sends the file's contents over the connection,
    # so the PostgreSQL server never needs access to the file itself.
    with open(path, "r", encoding="utf-8") as f, \
         cur.copy(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
        while chunk := f.read(1024 * 1024):
            copy.write(chunk)


# ---------------------------------------------------------------------
# def seconds_since(start) -> str:
#
# time.perf_counter() returns a number of seconds from an arbitrary
# starting point. On its own it means nothing, but the DIFFERENCE between
# two calls is exactly how much time passed in between. It's the clock
# made for measuring durations: the most precise one, and unaffected if
# the computer's time of day changes.
#
#     start = time.perf_counter()
#     ...something...
#     seconds_since(start)   # e.g. "  0.12 s"
#
# :6.2f — a number 6 characters wide with 2 decimals, so the times line
# up in a column.
# ---------------------------------------------------------------------
def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:6.2f} s"


# ---------------------------------------------------------------------
# def load(csv_dir) -> bool:
#
# Does the whole job and returns True if every table ended up with
# exactly as many rows as its CSV file.
#
# conn.cursor() — a CURSOR is the object used to send SQL through the
# connection and read the answers (check_connections.py used the
# shortcut conn.execute(), which creates one behind the scenes).
#
# TRANSACTIONS: with psycopg, everything sent through a connection is
# part of one TRANSACTION, a group of changes that either ALL happen or
# NONE do. Until conn.commit() is called, nothing is permanently saved:
# if the script crashed halfway, PostgreSQL would undo everything and
# the tables would be as before. That's why a half-finished load can
# never be left behind.
# ---------------------------------------------------------------------
def load(csv_dir: Path) -> bool:
    all_match = True
    with psycopg.connect(**POSTGRES_SETTINGS) as conn:
        with conn.cursor() as cur:
            # The total starts here, once connected: connecting isn't part
            # of loading.
            load_start = time.perf_counter()

            # Each step is timed on its own: take the time, do the step,
            # print how long it took.
            step = time.perf_counter()
            cur.execute(SCHEMA)
            print(f"Tables created: actor, repo, actor_repo        {seconds_since(step)}")

            for table, columns, csv_name in TABLES:
                step = time.perf_counter()
                copy_csv(cur, table, columns, csv_dir / csv_name)
                print(f"Loaded {table:<12} from {csv_name:<16}  {seconds_since(step)}")

            # ---------------------------------------------------------
            # ANALYZE
            #
            # Before running a query, PostgreSQL's PLANNER decides HOW to
            # run it (use an index or read the whole table? which table
            # first?). To decide well, it relies on STATISTICS about the
            # data: how many rows, how values are spread. Right after a
            # bulk load those statistics are out of date, so ANALYZE
            # refreshes them. For the benchmark, this means the
            # relational side is measured on well-planned queries —
            # part of giving each side its normal aids.
            # ---------------------------------------------------------
            # Refresh the planner's statistics so queries are planned on the real data.
            step = time.perf_counter()
            cur.execute("ANALYZE actor; ANALYZE repo; ANALYZE actor_repo;")
            print(f"Statistics refreshed (ANALYZE)                 {seconds_since(step)}")

            # COMMIT saves the transaction permanently. It's done here,
            # before stopping the clock, so the total includes saving the
            # data, but not the checks that follow.
            # Commit here, so the total covers saving the data but not the checks below.
            conn.commit()
            print(f"Total load time                                {seconds_since(load_start)}")

            # ---------------------------------------------------------
            # The check: count the rows in each table and compare them
            # with the CSV. SELECT count(*) FROM actor counts the rows;
            # .fetchone()[0] takes the single number from the answer.
            #
            # all_match = all_match and in_db == in_csv
            #   all_match starts True and becomes False as soon as one
            #   table doesn't match (and stays False: False and anything
            #   is False).
            # ---------------------------------------------------------
            print("\nRows loaded (database vs. CSV file):")
            for table, _, csv_name in TABLES:
                in_db = cur.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                in_csv = count_csv_rows(csv_dir / csv_name)
                status = "OK" if in_db == in_csv else "MISMATCH"
                all_match = all_match and in_db == in_csv
                print(f"  {table:<12} {in_db:>7}   {csv_name:<16} {in_csv:>7}   {status}")
    return all_match


# parse_args(): same pattern as extract_csv.py; --csv-dir lets you load
# from another folder.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR,
                         help=f"Folder with the CSV files from extract_csv.py (default: {DEFAULT_CSV_DIR})")
    return parser.parse_args()


# main(): if the counts don't match, sys.exit("...") prints the message
# and ends with a failure exit code (see check_connections.py).
def main() -> None:
    args = parse_args()
    if not load(args.csv_dir):
        sys.exit("Some row counts don't match their CSV file.")
    print("\nPostgreSQL load complete.")


# main() and the `if __name__ == "__main__":` guard: see
# download_gharchive.py's annotated copy.
if __name__ == "__main__":
    main()
