########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/build_hours.py.
# It is NOT meant to be run as part of the project pipeline — it lives in
# docs_english/ because its purpose is to teach, not to execute. The real, "clean"
# script (with none of this commentary) is scripts/build_hours.py.
#
# Read these annotated copies first; what they explain is NOT repeated:
#   download_gharchive.py   fetch_gz(), try/except, `raise ... from`
#   extract_csv.py          extract(), write_all()
#   load_postgres.py,
#   load_neo4j.py           load(), and the count checks (OK / MISMATCH)
#   check_connections.py    connecting to both servers, the passwords
#   pipeline.py             importing our own scripts as modules,
#                           hour_file_name(), sql.Identifier, CREATE
#                           DATABASE ... WAIT, servers_not_ready()
#   test_integration.py     `while True:`, Neo4j records
#
# WHAT IT IS — the MANUAL PROCESS. The research asks at what traversal
# depth and data volume Neo4j starts beating PostgreSQL, so it needs the
# SAME fixed data in both databases, at several sizes (1 hour, 3 hours,
# 24 hours...). This script builds one of those data sets on request:
# YOU choose the hours, it puts them in a database of their own, on both
# sides. (The automatic 24-hour pipeline, pipeline.py, is postponed for
# now: the research phase uses data built with this script.)
#
# What's NEW here:
#   - asking questions on the keyboard with input(), and VALIDATING the
#     answers (asking again until they're valid);
#   - raising our own errors (raise ValueError) with readable messages;
#   - reading a date from text (datetime.strptime);
#   - passing a FUNCTION as a parameter so tests can replace the keyboard;
#   - deleting and recreating a whole database (DROP DATABASE ... WITH
#     (FORCE), CREATE OR REPLACE DATABASE), behind a SAFETY CHECK on the
#     name, then PROVING it's empty before loading;
#   - EOFError / KeyboardInterrupt (no keyboard, or Ctrl+C).
# Its messages are deliberately VERBOSE: every step says what it's about
# to do and what it did, so you can follow it without opening any code.
#
# How the real script is run (it asks the rest):
#     ./run.sh scripts/build_hours.py
# run.sh activates .venv and loads the passwords from secrets.sh; this
# script never contains or asks for a password.
########################################################################

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

# ---------------------------------------------------------------------
# Imports: all already seen. `date` (a day without a time) is explained
# in pipeline.py's annotated copy, like datetime/timedelta/timezone.
# Note: no argparse here — this script ASKS instead of taking options.
# ---------------------------------------------------------------------
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg
from neo4j import GraphDatabase
from psycopg import sql

# ---------------------------------------------------------------------
# Our own scripts, imported as MODULES (see pipeline.py's annotated
# copy). It reuses the downloader, the extractor and both loaders — the
# very same code as the benchmark and the pipeline, so every data set is
# built the same way — and two functions of pipeline.py itself:
# hour_file_name() and servers_not_ready().
# ---------------------------------------------------------------------
import download_gharchive
import extract_csv
import load_neo4j
import load_postgres
import pipeline

# ---------------------------------------------------------------------
# Constants:
#   HOURS_DIR   data/hours/ — where this script's downloads and CSVs go
#               (git-ignored like the rest of data/). Separate from the
#               benchmark's files and from data/live/ (the pipeline's).
#   FIRST_DATE  the earliest date it accepts. date(2015, 1, 1) is a
#               `date` object: year, month, day.
#   MAX_HOURS   the most hours it accepts at once: 168 = 7 x 24, a week.
# ---------------------------------------------------------------------
HOURS_DIR = Path(__file__).resolve().parent.parent / "data" / "hours"
# GH Archive's events have had today's format since 2015; older files use another one.
FIRST_DATE = date(2015, 1, 1)
# A week. More would take very long to load and need a lot of memory in Neo4j.
MAX_HOURS = 168


# ---------------------------------------------------------------------
# def parse_date(text) -> date:
#
# The first of three small VALIDATING functions: each turns what you
# typed (a str) into a proper value, or RAISES a ValueError with a
# message a person can understand.
#
# raise ValueError("...")
#   NEW: raising our OWN error. Until now we only caught errors raised
#   by others. ValueError is Python's usual type for "right type, wrong
#   value". The text becomes the error's message, and ask_hours() simply
#   prints it (see below). One function, two jobs: say whether the
#   answer is valid AND why not.
#
# text.strip() removes spaces and the line end around the text, so an
# answer of "   " counts as empty. `not ""` is True (an empty string is
# "falsy"), so `if not text.strip():` means "if nothing was typed".
#
# datetime.strptime(text, "%Y-%m-%d")
#   "STRing Parse TIME": the opposite of the f"{day:%Y-%m-%d}" formatting
#   seen in pipeline.py — it READS a date written in that pattern. If the
#   text doesn't fit (wrong order, month 13...), it raises ValueError.
#   It returns a datetime (at midnight); .date() keeps only the day.
#
# except ValueError: raise ValueError(...) from None
#   strptime's own message ("time data '27/08/2026' does not match
#   format '%Y-%m-%d'") is correct but cryptic, so we catch it and raise
#   a clearer one. `from None` hides the original error: unlike `from
#   error` (see download_gharchive.py), there's nothing useful in it to
#   keep, and the user should only see our message.
#
# day < FIRST_DATE — dates can be compared like numbers: earlier < later.
# ---------------------------------------------------------------------
def parse_date(text: str) -> date:
    # "2026-08-27" -> date(2026, 8, 27); anything else raises ValueError with a readable message.
    if not text.strip():
        raise ValueError("Please type a date, like 2026-08-27 (year-month-day)")
    try:
        day = datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"'{text}' isn't a date like 2026-08-27 (year-month-day)") from None
    if day < FIRST_DATE:
        raise ValueError(f"Dates before {FIRST_DATE} use an older GH Archive format; choose a later one")
    return day


# ---------------------------------------------------------------------
# def parse_hour(text) -> int:
#
# text.strip().isdigit()
#   True only if the text is made of digits 0-9 and nothing else. "15"
#   passes; "-1", "3pm" and "1.5" don't. It's checked BEFORE int(text),
#   so int() never gets text it can't convert.
#
# 0 <= int(text) <= 23
#   A CHAINED comparison: Python reads it as
#   "0 <= int(text) and int(text) <= 23" — the usual maths notation.
#
# `A or B` in the condition: if the text isn't digits, `or` already
# knows the answer is True and doesn't even evaluate the second part.
#
# The hours are UTC because GH Archive names its files in UTC (see
# pipeline.py's annotated copy, compute_window()).
# ---------------------------------------------------------------------
def parse_hour(text: str) -> int:
    # "15" -> 15. GH Archive hours are UTC, 0 to 23.
    if not text.strip():
        raise ValueError("Please type an hour from 0 to 23 (UTC)")
    if not text.strip().isdigit() or not 0 <= int(text) <= 23:
        raise ValueError(f"'{text}' isn't an hour from 0 to 23 (UTC)")
    return int(text)


# Same idea for the number of hours: 1 to MAX_HOURS. There's no "empty"
# check here, because an empty answer never reaches this function: it's
# replaced by "1" in ask_hours() (the only question with a default).
def parse_count(text: str) -> int:
    # "3" -> 3 consecutive hours, from 1 to MAX_HOURS.
    if not text.strip().isdigit() or not 1 <= int(text) <= MAX_HOURS:
        raise ValueError(f"'{text}' isn't a number of hours from 1 to {MAX_HOURS}")
    return int(text)


# ---------------------------------------------------------------------
# def chosen_hours(day, hour, count) -> list[datetime]:
#
# Turns the three answers into the list of hours, the same shape as
# compute_window() in pipeline.py: one UTC datetime per hourly file.
# It builds the first one from the day's year/month/day plus the hour,
# then adds 0, 1, 2... hours with timedelta. Because it's datetime
# arithmetic, going past 23:00 moves to the next day (and month, and
# year) by itself.
# ---------------------------------------------------------------------
def chosen_hours(day: date, hour: int, count: int) -> list[datetime]:
    # Example: 2026-08-27, 23, 2 -> 2026-08-27 23:00 and 2026-08-28 00:00 (crossing midnight is fine).
    first = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
    return [first + timedelta(hours=i) for i in range(count)]


# ---------------------------------------------------------------------
# def hours_are_published(hours, now) -> bool:
#
# Refuses hours GH Archive can't have yet (recent hours, or the future),
# BEFORE trying to download them. With now = 15:20 UTC:
#   current hour starts        15:00
#   minus one full hour     -> 14:00   the latest allowed END
#   12:00 + 2 hours ends at    14:00   -> accepted
#   13:00 + 2 hours ends at    15:00   -> refused (too recent)
# last_end = the last hour's start + 1 hour (as in pipeline.py's run()).
# `now` is a parameter, so tests can use a fixed time (see
# docs_english/test_build_hours.py).
# ---------------------------------------------------------------------
def hours_are_published(hours: list[datetime], now: datetime) -> bool:
    # GH Archive publishes each hour's file a little after the hour ends. Accept the hours only
    # if the last one ended at least one full hour before the current hour began.
    last_end = hours[-1] + timedelta(hours=1)
    return last_end <= now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)


# ---------------------------------------------------------------------
# def database_name(hours) -> str:
#
# Each choice of hours gets its OWN database, named after the hours, so
# data sets never mix and you can tell from the name what's inside:
#   1 hour   -> "gharchive-2026-08-27-15"
#   3 hours  -> "gharchive-2026-08-27-15-3h"
# Always starting with "gharchive-" (with a dash): that prefix is what
# may_be_emptied() checks, and it can never equal "gharchive" or
# "gharchive24h". Dashes, not underscores: Neo4j forbids "_" in database
# names (see DEFAULT_DATABASE in pipeline.py).
#
# `X if condition else Y` (seen before): the plain name for 1 hour, the
# name plus "-<count>h" otherwise.
# ---------------------------------------------------------------------
def database_name(hours: list[datetime]) -> str:
    # Neo4j allows letters, digits, dots and dashes in database names (not "_"), so dashes it is.
    # The hour has no leading zero, like GH Archive's file names.
    name = f"gharchive-{hours[0]:%Y-%m-%d}-{hours[0].hour}"
    return name if len(hours) == 1 else f"{name}-{len(hours)}h"


# ---------------------------------------------------------------------
# def describe(hours) -> str:
#
# A human-readable summary for the messages. The small trick at the end:
#   's' * (len(hours) > 1)
# A comparison gives True or False, and in arithmetic True counts as 1
# and False as 0. A string times 1 is itself, times 0 is "". So it adds
# the plural "s" only when there's more than one hour: "1 hour",
# "3 hours".
# ---------------------------------------------------------------------
def describe(hours: list[datetime]) -> str:
    # e.g. "2026-08-27 15:00 -> 2026-08-27 18:00 UTC (3 hours)"
    end = hours[-1] + timedelta(hours=1)
    return f"{hours[0]:%Y-%m-%d %H:00} -> {end:%Y-%m-%d %H:00} UTC ({len(hours)} hour{'s' * (len(hours) > 1)})"


# ---------------------------------------------------------------------
# def ask_hours(now, ask=input) -> list[datetime] | None:
#
# input("question") — NEW: shows the question, waits until you type
# something and press Enter, and returns what you typed as a str
# (without the Enter). Pressing Enter alone returns "".
#
# ask=input — a FUNCTION as a default parameter value. Functions are
# values like any other (see the (name, check) loop in
# check_connections.py), so the function is called through the name
# `ask`. Normally ask IS input (the keyboard). A test passes its own
# function instead, which returns ready-made answers — so ask_hours() can
# be tested without anybody typing (see docs_english/test_build_hours.py).
# Note: `input`, not `input()` — we pass the function itself, not call it.
#
# The questions loop (`while True:` is explained in test_integration.py):
#   - each answer goes straight through its parse_... function; the
#     first one that raises ValueError jumps to `except`;
#   - `except ValueError as error: print(error)` shows the readable
#     message we wrote in the parse_ function;
#   - `continue` — jump back to the TOP of the loop: all three questions
#     are asked again;
#   - the same happens if the hours aren't published yet.
#
# ask("How many consecutive hours [1]: ") or "1"
#   THE ONLY DEFAULT. `A or B` gives A if A is "truthy", otherwise B. An
#   empty answer "" is falsy, so pressing Enter gives "1". The "[1]" in
#   the question is the usual way of showing the default.
#
# The DATE and the HOUR deliberately have NO default: Enter alone just
# asks again ("Please type a date..."). A default date would make it
# possible to load, by pressing Enter, data that nobody actually chose —
# and then measure the wrong thing without noticing.
#
# The CONFIRMATION: it shows exactly what will be loaded and into which
# database, and warns that an existing database with that name is
# emptied first. The answer is cleaned with .strip().lower() (no spaces,
# lowercase, so " Y " is "y") and checked with `in` against a TUPLE of
# accepted answers: Enter alone (""), y/yes, and s/si/sí for whoever
# answers in Portuguese or Spanish. Anything else (e.g. "n") returns
# None, which tells main() "nothing to do".
#
# The return type `list[datetime] | None`: a list of hours, OR None
# (the `|` hint is explained in pipeline.py's annotated copy).
# ---------------------------------------------------------------------
def ask_hours(now: datetime, ask=input) -> list[datetime] | None:
    # Asks for the date, the first hour and how many hours until all are valid, then asks for
    # confirmation. Returns None if the answer to the confirmation is "n".
    # "ask" is input() unless a test replaces it.
    # The date and the hour have no default: they must always be typed, so data is never
    # loaded for a date nobody chose. Only the number of hours has one (Enter = 1).
    while True:
        try:
            day = parse_date(ask("Date (UTC, e.g. 2026-08-27): "))
            hour = parse_hour(ask("First hour (UTC, 0-23): "))
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


# ---------------------------------------------------------------------
# def may_be_emptied(name) -> bool:
#
# The SAFETY CHECK before deleting anything. This script deletes whole
# databases, so it must be impossible for it to delete the wrong one.
# The rule is one line: only names starting with "gharchive-".
# str.startswith(prefix) is True if the text begins with that prefix.
#   "gharchive"             -> False (no dash)     the frozen benchmark
#   "gharchive24h"          -> False               the live pipeline's
#   "gharchivetest"         -> False               the integration tests'
#   "neo4j", "postgres", "system" -> False         the servers' own
#   "gharchive-2026-08-27-15" -> True              made by this script
# Kept as a separate, tiny function so it can be tested on its own.
# ---------------------------------------------------------------------
def may_be_emptied(name: str) -> bool:
    # Only databases made by this script may be deleted: never "gharchive" (the frozen
    # benchmark), "gharchive24h" (the pipeline's) or anything else on the servers.
    return name.startswith("gharchive-")


# ---------------------------------------------------------------------
# def recreate_databases(name) -> None:
#
# Empties the database on both sides by DELETING it and CREATING it
# again. The loaders already empty their own tables and nodes (see
# load_postgres.py and load_neo4j.py), but recreating the whole database
# is surer: nothing from before survives, not even something the loaders
# don't know about.
#
# FIRST LINE: the safety check, BEFORE connecting to anything. If the
# name isn't allowed, it raises ValueError and nothing at all happens.
#
# PostgreSQL (connection to the "postgres" database with autocommit=True,
# the pg_database lookup and sql.Identifier: all as in ensure_databases()
# in pipeline.py's annotated copy):
#   - `exists` is True or False: `... is not None` turns "a row, or None"
#     into a yes/no.
#   - DROP DATABASE "name" WITH (FORCE) — NEW: deletes the database and
#     ALL its data. PostgreSQL refuses to drop a database somebody is
#     connected to (pgAdmin, for instance); WITH (FORCE) closes those
#     connections first.
#   - CREATE DATABASE "name" — a new, empty database.
#   - The messages are written f'...' (single quotes) so they can contain
#     "double quotes" around the name. To put an apostrophe in them, as
#     in doesn\'t, it's written \' — an ESCAPED quote: part of the text,
#     not the end of the string.
#
# Neo4j (in the "system" database, where databases are managed):
#   - SHOW DATABASES YIELD name WHERE name = $name RETURN name
#     lists the databases with that name: one row if it exists, none if
#     not. $name is a query PARAMETER (see load_neo4j.py), filled in by
#     name=name. Its value is a VALUE, so a parameter works here.
#   - .records — the result has the rows in its .records attribute; it's
#     the same list that `records, _, _ = ...` unpacks elsewhere. An
#     empty list is falsy, so `if records:` means "it exists".
#   - CREATE OR REPLACE DATABASE `name` WAIT — NEW: one command that
#     deletes the database if it exists and creates it again (Enterprise
#     Edition, the one Neo4j Desktop includes). WAIT returns only when
#     it's online. Here the name can't be a parameter (it's a NAME, not
#     a value), so it's put in the text between backticks — which is
#     only acceptable because may_be_emptied() already checked it.
# The `if records:` before and after only choose the right messages.
# ---------------------------------------------------------------------
def recreate_databases(name: str) -> None:
    # Deleting the whole database and creating it again is the surest way to empty it:
    # nothing from before survives (tables, rows, nodes, relationships, constraints).
    if not may_be_emptied(name):
        raise ValueError(f'Refusing to empty "{name}": build_hours.py only empties databases named gharchive-...')

    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone() is not None
        if exists:
            print(f'Deleting the PostgreSQL database "{name}" and all its data ...')
            # WITH (FORCE) first closes other connections to it (e.g. pgAdmin), which would block the DROP.
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            print(f'The PostgreSQL database "{name}" has been deleted.')
        else:
            print(f'The PostgreSQL database "{name}" doesn\'t exist yet: nothing to delete.')
        print(f'Creating the PostgreSQL database "{name}" (empty) ...')
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        print(f'The PostgreSQL database "{name}" has been created.')

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        records = driver.execute_query("SHOW DATABASES YIELD name WHERE name = $name RETURN name",
                                       name=name, database_="system").records
        if records:
            print(f'Deleting the Neo4j database "{name}" and all its data, then creating it again (empty) ...')
        else:
            print(f'The Neo4j database "{name}" doesn\'t exist yet: nothing to delete. Creating it (empty) ...')
        # CREATE OR REPLACE = delete it if it exists, then create it (Enterprise Edition only).
        # WAIT: don't return until the new database is online.
        driver.execute_query(f"CREATE OR REPLACE DATABASE `{name}` WAIT", database_="system")
        if records:
            print(f'The Neo4j database "{name}" has been deleted and created again.')
        else:
            print(f'The Neo4j database "{name}" has been created.')


# ---------------------------------------------------------------------
# def databases_are_empty(name) -> bool:
#
# Don't assume, CHECK: after recreating, count what's inside on both
# sides. Everything must be 0.
#
# PostgreSQL: information_schema.tables — NEW: a standard catalogue
#   (every SQL database has it) listing all tables. table_schema =
#   'public' keeps only OUR tables (PostgreSQL's own live elsewhere).
#   This time we connect to the new database itself (dbname=name).
#
# Neo4j: three counts, in the new database (database_=name):
#   MATCH (n) RETURN count(n)            all nodes
#   MATCH ()-[r]->() RETURN count(r)     all relationships
#   SHOW CONSTRAINTS ... count(name)     all constraints (load_neo4j.py
#                                        creates two; an empty database
#                                        has none)
#
# def count(query) inside the `with` block: a NESTED function (see
# test_extract_csv.py). It can use `driver` because it's defined where
# driver exists. It saves writing the same long line three times.
# .records[0][0]: the first row, its first column — the number.
#
# The report: a dict {what: how many}, walked with .items() (pairs of
# key and value). In the f-string, :<20 pads the text to 20 characters,
# left-aligned, and :>3 right-aligns the number in 3 (see
# summarize_data.py), so the lines form neat columns:
#   PostgreSQL tables      0   empty
#
# all(how_many == 0 for how_many in found.values())
#   all(...) is True only if EVERY item is True (here: every count is 0).
#   The part inside is a GENERATOR expression — like a list
#   comprehension, without the square brackets.
# ---------------------------------------------------------------------
def databases_are_empty(name: str) -> bool:
    # Checks both sides and prints what it finds; True only if everything is 0.
    print(f'Checking that the database "{name}" is empty on both sides ...')
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
    empty = all(how_many == 0 for how_many in found.values())
    if empty:
        print(f'The database "{name}" is empty in PostgreSQL and in Neo4j: ready to load.')
    return empty


# ---------------------------------------------------------------------
# def build(hours) -> bool:
#
# The whole job, in numbered steps that are printed as headings
# ("== 0. ...", "== 1. ..."); "\n" at the start of each prints an empty
# line first, to separate the steps on screen. Returns True only if both
# loads' counts match their CSVs.
#
# Step 0 — BOTH SERVERS FIRST. pipeline.servers_not_ready() (see
#   pipeline.py's annotated copy) gives None or the reason. Checked
#   before anything is downloaded or deleted: if Neo4j were down, step 3
#   would empty PostgreSQL and then fail on Neo4j, leaving the two sides
#   DIFFERENT — the one thing a comparison can't have.
#
# Step 1 — DOWNLOAD only what's missing: an hour file already in
#   data/hours/ is reused (data sets that share hours share files).
#   download_gharchive.fetch_gz() is the same downloader as always, with
#   its retries; it raises an error if GH Archive doesn't have an hour.
#   files.append(path) collects the paths for step 2.
#
# Step 2 — EXTRACT with extract_csv.extract() and write_all() (bots left
#   out), into data/hours/csv/<database name>/: each data set keeps its
#   own CSVs.
#
# Step 3 — EMPTY: recreate the database on both sides, then PROVE it's
#   empty. If it isn't, stop with False: nothing is loaded on top of old
#   data.
#
# Steps 4 and 5 — LOAD with the same loaders as the benchmark, passing
#   the database name. Each returns True if its counts match the CSVs
#   (OK) and False otherwise (MISMATCH; the loader has already printed
#   which count is wrong).
#
# The SUMMARY repeats the essentials on one line: which hours, how many
#   actors / repos / connections, and OK or MISMATCH on each side.
#   (Several f-strings side by side are joined into one, as seen in
#   pipeline.py's parse_args().)
# ---------------------------------------------------------------------
def build(hours: list[datetime]) -> bool:
    name = database_name(hours)
    csv_dir = HOURS_DIR / "csv" / name

    # Before changing anything: if one server isn't answering, stop now. Otherwise one side
    # could be emptied while the other can't be, leaving the two databases different.
    print("\n== 0. Check that both servers are answering")
    print("Connecting to PostgreSQL (localhost:5432) and Neo4j (localhost:7687) ...")
    problem = pipeline.servers_not_ready()
    if problem is not None:
        print(f"{problem}. Nothing was changed.")
        return False
    print("Both servers are answering.")

    print(f"\n== 1. Download {len(hours)} hour file(s) from GH Archive to {HOURS_DIR}")
    files = []
    for hour in hours:
        path = HOURS_DIR / pipeline.hour_file_name(hour)
        if path.exists():
            print(f"{path.name} is already on this computer: no need to download it again.")
        else:
            download_gharchive.fetch_gz(f"{hour:%Y-%m-%d}", hour.hour, HOURS_DIR)
        files.append(path)
    print(f"All {len(files)} hour file(s) are ready.")

    print("\n== 2. Extract actors, repos and connections into CSV files")
    print(f"Reading the events in {len(files)} file(s) (bots are left out) ...")
    actors, repos, pairs, skipped_bot_events = extract_csv.extract(files)
    print(f"Found {len(actors)} actors, {len(repos)} repos and {len(pairs)} connections "
          f"({skipped_bot_events} bot events skipped).")
    print(f"Writing actors.csv, repos.csv and actor_repo.csv to {csv_dir} ...")
    extract_csv.write_all(csv_dir, actors, repos, pairs)
    print("The CSV files have been written.")

    print(f'\n== 3. Empty the database "{name}" on both sides, and check that it is empty')
    recreate_databases(name)
    if not databases_are_empty(name):
        print(f'The database "{name}" isn\'t empty after being recreated; nothing was loaded.')
        return False

    print(f'\n== 4. Load the data into the PostgreSQL database "{name}"')
    print(f'The data is being loaded into the PostgreSQL database "{name}" ...')
    postgres_ok = load_postgres.load(csv_dir, name)
    if postgres_ok:
        print(f'The data has been loaded into the PostgreSQL database "{name}", and every count matches its CSV file.')
    else:
        print(f'The PostgreSQL database "{name}" was loaded, but some counts DON\'T match their CSV files (MISMATCH above).')

    print(f'\n== 5. Load the data into the Neo4j database "{name}"')
    print(f'The data is being loaded into the Neo4j database "{name}" ...')
    neo4j_ok = load_neo4j.load(csv_dir, name)
    if neo4j_ok:
        print(f'The data has been loaded into the Neo4j database "{name}", and every count matches its CSV file.')
    else:
        print(f'The Neo4j database "{name}" was loaded, but some counts DON\'T match their CSV files (MISMATCH above).')

    print(f'\nSummary: "{name}" holds {describe(hours)}: {len(actors)} actors, {len(repos)} repos '
          f"and {len(pairs)} connections, in PostgreSQL ({'OK' if postgres_ok else 'MISMATCH'}) "
          f"and in Neo4j ({'OK' if neo4j_ok else 'MISMATCH'}).")
    return postgres_ok and neo4j_ok


# ---------------------------------------------------------------------
# def main() -> None:
#
# 1. ASK. Two exceptions are caught at once (a tuple in `except`):
#      EOFError           input() found no keyboard to read from ("End
#                         Of File") — e.g. the script was started by a
#                         scheduler or with its input redirected. It's
#                         meant to be run by hand, so it stops.
#      KeyboardInterrupt  you pressed Ctrl+C during a question.
#    Either way: a short message and exit code 1, instead of a long
#    traceback.
#    If you answered "n" to the confirmation, ask_hours() returned None:
#    "Nothing done." with exit code 0 — you chose it, so it's not a
#    failure.
# 2. BUILD, inside try / except Exception: a missing hour on GH Archive,
#    no internet, a database error... are all reported in one readable
#    line ("Stopped by an error: ...") instead of a traceback.
# 3. A final line saying Done or NOT done, and the EXIT CODE (0 / 1, see
#    check_connections.py).
# ---------------------------------------------------------------------
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

    name = database_name(hours)
    try:
        ok = build(hours)
    except Exception as error:
        # e.g. an hour GH Archive doesn't have, no internet, a database error
        print(f"\nStopped by an error: {error}")
        ok = False
    print(f'\n{"Done" if ok else "NOT done (see the messages above)"}: database "{name}".')
    sys.exit(0 if ok else 1)


# The __name__ guard: see download_gharchive.py's annotated copy (and
# pipeline.py's, for why it also lets tests import this file's functions
# without running main()).
if __name__ == "__main__":
    main()
