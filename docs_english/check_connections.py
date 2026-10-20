########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/check_connections.py.
# It is NOT meant to be run as part of the project pipeline — it lives in
# docs_english/ because its purpose is to teach, not to execute. The real, "clean"
# script (with none of this commentary) is scripts/check_connections.py.
#
# This file assumes you've already read the earlier annotated scripts —
# imports, functions, f-strings, `with`, main() and the __name__ guard are
# NOT re-explained from scratch here. This file focuses on what's NEW in
# check_connections.py: the project's first EXTERNAL packages (psycopg and
# neo4j), reading passwords from ENVIRONMENT VARIABLES, connecting to a
# database server, and handling errors with try/except so one failure
# doesn't hide the other check.
#
# How it's meant to be run — always through run.sh:
#     ./run.sh scripts/check_connections.py
# run.sh activates .venv (so `import psycopg` / `import neo4j` work) and
# loads secrets.sh (so PGPASSWORD / NEO4J_PASSWORD exist). This script
# inherits both. See project-notes.md, step 4.
########################################################################

"""Check that Python can reach both of the project's databases.

Connects to PostgreSQL and to Neo4j with the passwords taken from the
environment (PGPASSWORD and NEO4J_PASSWORD, loaded from secrets.sh by run.sh)
and prints each server's version. Exits with an error if either one fails.

Usage:
    ./run.sh scripts/check_connections.py
"""

# ---------------------------------------------------------------------
# import os, import sys
#
# Both are standard-library modules (they come with Python).
#   os   — "operating system". Here we only use os.environ: a dict-like
#          object holding the ENVIRONMENT VARIABLES this process inherited
#          from the terminal (or from run.sh). That's how the passwords
#          reach Python without ever being written in the code.
#   sys  — "system". Here we only use sys.exit(), which stops the program
#          and tells whoever ran it whether it succeeded (see main()).
# ---------------------------------------------------------------------
import os
import sys

# ---------------------------------------------------------------------
# import psycopg / from neo4j import GraphDatabase
#
# These are the project's first EXTERNAL packages: they don't come with
# Python, they were installed into .venv with `pip install -r
# requirements.txt`. If .venv isn't active, these two lines fail with
# "ModuleNotFoundError" — one of the reasons to always go through run.sh.
#
# The blank line between the two groups of imports is a convention:
# standard-library imports first, then external packages.
#
#   psycopg         — the PostgreSQL connector.
#   GraphDatabase   — the entry point of the Neo4j connector; we only need
#                     this one name from the `neo4j` package, hence
#                     `from neo4j import ...` instead of `import neo4j`.
# ---------------------------------------------------------------------
import psycopg
from neo4j import GraphDatabase

# ---------------------------------------------------------------------
# Connection settings, as constants at the top (same idea as DEFAULT_FILE
# in the earlier scripts): one place to look if anything ever changes.
#
# POSTGRES_SETTINGS is a dict whose keys are exactly the names psycopg's
# connect() expects:
#   host="localhost"     the database runs on this same computer
#   dbname="gharchive"   the database created in step 1
#   user="postgres"      the superuser created by the installer
# There's deliberately NO password here: see check_postgres().
#
# NEO4J_URI = "neo4j://localhost:7687"
#   The address of the Neo4j server: protocol neo4j://, this computer,
#   port 7687 (the "Bolt" port for programs; 7474 is for the browser).
# NEO4J_USER = "neo4j" — the default Neo4j user.
# ---------------------------------------------------------------------
POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"


# ---------------------------------------------------------------------
# def check_postgres() -> None:
#
# psycopg.connect(**POSTGRES_SETTINGS)
#   `**` UNPACKS a dict into keyword arguments, so this is exactly the
#   same as writing:
#       psycopg.connect(host="localhost", dbname="gharchive", user="postgres")
#
# Where's the password? PGPASSWORD is a standard environment variable
# name that the PostgreSQL client library (which psycopg uses underneath)
# looks for on its own. Because run.sh loaded it from secrets.sh, it's
# already in this process's environment — the code never touches it.
#
# `with ... as conn:` — same pattern as `with open(...) as f:` in the
# earlier scripts: the connection is closed automatically when the block
# ends, even if something goes wrong inside it.
#
# conn.execute("SELECT version();") sends a SQL query to the server.
# .fetchone() gets the first (here, the only) row of the answer, as a
# tuple; [0] takes its first (only) column — the version text.
# ---------------------------------------------------------------------
def check_postgres() -> None:
    # psycopg reads the password from PGPASSWORD by itself.
    with psycopg.connect(**POSTGRES_SETTINGS) as conn:
        version = conn.execute("SELECT version();").fetchone()[0]
    print(f"PostgreSQL OK: {version}")


# ---------------------------------------------------------------------
# def check_neo4j() -> None:
#
# os.environ["NEO4J_PASSWORD"]
#   Unlike PostgreSQL, the Neo4j connector doesn't look for a password on
#   its own, so we read it ourselves from the environment and pass it in.
#   os.environ works like a dict: ["NAME"] gives the variable's value.
#
# GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password))
#   Creates a DRIVER: the object that manages connections to the Neo4j
#   server. auth= takes a (user, password) tuple. `with ... as driver:`
#   closes it automatically at the end.
#
# driver.verify_connectivity()
#   Creating a driver doesn't actually connect yet. This line forces a
#   real connection and login, so a wrong password or a stopped database
#   is reported right here, with a clear error.
#
# driver.execute_query("CALL dbms.components() ...")
#   Sends a Cypher query (Neo4j's query language) — the same one used in
#   Neo4j Browser in the notes to see the version. It returns three
#   things; `records, _, _ = ...` keeps the first (the result rows) and
#   throws the other two away. `_` is the conventional name for "a value
#   I don't need".
#
# Each record behaves like a dict: record['name'], record['versions'],
# record['edition']. 'versions' is a list, so [0] takes its first entry.
# ---------------------------------------------------------------------
def check_neo4j() -> None:
    password = os.environ["NEO4J_PASSWORD"]
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password)) as driver:
        driver.verify_connectivity()
        records, _, _ = driver.execute_query(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name, versions, edition"
        )
    for record in records:
        print(f"Neo4j OK: {record['name']} {record['versions'][0]} ({record['edition']} edition)")


# ---------------------------------------------------------------------
# def main() -> None:
# ---------------------------------------------------------------------
def main() -> None:
    # -----------------------------------------------------------------
    # First, check the passwords are actually there.
    #
    # os.environ.get(name) returns None (instead of an error) when the
    # variable doesn't exist — same idea as dict.get() in
    # profile_schema.py. `not ...` is True when it's missing OR empty.
    # The list comprehension collects the names of the missing ones.
    #
    # sys.exit("some text") stops the program, prints the text, and
    # reports FAILURE to whoever ran it. Checking this up front gives a
    # clear message ("run it through run.sh") instead of a confusing
    # authentication error later.
    # -----------------------------------------------------------------
    missing = [name for name in ("PGPASSWORD", "NEO4J_PASSWORD") if not os.environ.get(name)]
    if missing:
        sys.exit(f"Missing environment variable(s): {', '.join(missing)}. "
                 "Run this script through run.sh, which loads them from secrets.sh.")

    # -----------------------------------------------------------------
    # try / except — handling errors without stopping everything
    #
    # Normally, an error (an EXCEPTION) stops the program on the spot. If
    # PostgreSQL failed, we'd never find out whether Neo4j works. So each
    # check runs inside `try:`; if it raises an exception, Python jumps to
    # `except Exception as error:` instead of stopping, prints which one
    # failed and why, remembers that something failed, and the loop goes
    # on to the next check.
    #
    # The loop goes through (name, function) pairs. `check` is the
    # function itself (no parentheses), and `check()` calls it — functions
    # can be stored in variables and tuples like any other value.
    # -----------------------------------------------------------------
    failed = False
    for name, check in (("PostgreSQL", check_postgres), ("Neo4j", check_neo4j)):
        try:
            check()
        except Exception as error:
            print(f"{name} FAILED: {error}")
            failed = True

    # -----------------------------------------------------------------
    # sys.exit(1) — the EXIT CODE
    #
    # Every program ends with a number that tells whoever ran it how it
    # went: 0 means success, anything else means failure. Reaching the
    # end of the script normally gives 0; sys.exit(1) gives 1. Other
    # scripts (or run.sh) can use this to tell whether the check passed.
    # -----------------------------------------------------------------
    if failed:
        sys.exit(1)
    print("Both databases are reachable.")


# main() and the `if __name__ == "__main__":` guard: identical purpose and
# mechanics to the other scripts — see download_gharchive.py's annotated
# copy for the full explanation.
if __name__ == "__main__":
    main()
