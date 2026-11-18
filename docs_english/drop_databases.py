########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/drop_databases.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute. The real, "clean" script (with none of this
# commentary) is scripts/drop_databases.py.
#
# This file assumes you've already read the earlier annotated scripts,
# especially check_connections.py (psycopg, the Neo4j driver,
# execute_query, os.environ, sys.exit, try/except) and pipeline.py
# (autocommit=True, the pg_database catalogue, sql.SQL + sql.Identifier,
# the "system" database where Neo4j manages databases, CREATE DATABASE
# ... WAIT). Those are NOT re-explained from scratch here.
#
# What's NEW in this file:
#   - the DANGEROUS operation, DROP DATABASE, on both sides, and the
#     SAFETY RULES around it: an explicit allow-list ("gharchive*") and a
#     deny-list (the servers' own databases), checked INSIDE the drop
#     functions themselves, before anything connects;
#   - asking the user to CONFIRM by typing a word, with input();
#   - DROP DATABASE ... WITH (FORCE) (PostgreSQL) and
#     DROP DATABASE `x` IF EXISTS DESTROY DATA WAIT (Neo4j);
#   - VERIFYING afterwards that nothing is left, instead of trusting
#     that the deletes worked.
#
# WHY IT EXISTS: every data volume of the research (1 hour, 6 hours,
# 12 hours, 1 day, ...) is its own pair of databases, called
# "gharchive-<date>-<hour>-<n>h", built by build_hours.py. They pile up.
# This script removes them all in one go, to start the measurements again
# from a clean state. The downloaded files in data/ are kept, so rebuilding
# a database never needs a new download.
#
# Run it through run.sh (it needs PGPASSWORD and NEO4J_PASSWORD):
#     ./run.sh scripts/drop_databases.py
########################################################################

"""Delete every database this project created, in PostgreSQL and in Neo4j.

A project database is one called "gharchive" or whose name starts with
"gharchive": gharchive, gharchive24h, gharchive-<date>-<hour>..., gharchivetest.
The databases that come with the servers ("postgres" in PostgreSQL, "neo4j"
and "system" in Neo4j) are never touched, and neither are the downloaded
files in data/ (so nothing has to be downloaded again to rebuild a database).

It shows what it found and asks you to type "delete" before deleting
anything. Afterwards it checks that no project database is left on either side.
This can't be undone.

Usage:
    ./run.sh scripts/drop_databases.py
"""

# ---------------------------------------------------------------------
# os, sys, psycopg, GraphDatabase: explained in check_connections.py.
# `from psycopg import sql`: the tools to build SQL text safely (sql.SQL,
# sql.Identifier), explained in pipeline.py (ensure_databases).
#
# `import load_neo4j` / `import pipeline`: our OWN scripts imported as
# modules (explained in pipeline.py). From load_neo4j we only reuse the
# constants NEO4J_URI and NEO4J_USER (so the address is written in ONE
# place), and from pipeline the helper servers_not_ready() (see main()).
# ---------------------------------------------------------------------
import os
import sys

import psycopg
from neo4j import GraphDatabase
from psycopg import sql

import load_neo4j
import pipeline

# ---------------------------------------------------------------------
# SERVER_DATABASES — a DENY-LIST, written as a SET ({...}).
#
# These are the databases that come with the servers themselves:
#   PostgreSQL  postgres (the default one you connect to), template0 and
#               template1 (the "moulds" every new database is copied
#               from). Deleting a template breaks CREATE DATABASE.
#   Neo4j       neo4j (the default database) and system (where Neo4j
#               keeps its users and the list of databases — deleting it
#               would break the whole server).
#
# None of them starts with "gharchive", so the name test below would
# already skip them. The deny-list is a SECOND, independent safety net:
# "defence in depth". With a destructive operation, you want two locks,
# so that one mistake in one rule isn't enough to cause a disaster.
#
# A set is used because the only question asked is "is this name IN
# it?", which a set answers instantly.
# ---------------------------------------------------------------------
# Names that may never be deleted, whatever they look like.
SERVER_DATABASES = {"postgres", "template0", "template1", "neo4j", "system"}


# ---------------------------------------------------------------------
# def is_project_database(name) -> bool:
#
# THE rule of the whole script, in one line: a name is a project database
# if it STARTS WITH "gharchive" (an ALLOW-LIST by prefix) AND isn't in the
# deny-list. str.startswith() returns True or False.
#
# Why a prefix and not a fixed list of names? Because the per-volume
# databases have names that change with the date and size, e.g.
# "gharchive-2026-08-27-15-6h"; a prefix catches them all, and nothing
# else. Note it's "starts with", not "contains": "mygharchive" would NOT
# match, so a database that merely mentions the word is safe.
#
# It's a PURE function (no server involved), so it can be unit-tested
# without any database: that's what tests/test_drop_databases.py does.
# ---------------------------------------------------------------------
def is_project_database(name: str) -> bool:
    # gharchive, gharchive24h, gharchive-..., gharchivetest; nothing else.
    return name.startswith("gharchive") and name not in SERVER_DATABASES


# ---------------------------------------------------------------------
# def project_databases(names) -> list[str]:
#
# Filters a list of names down to the project's ones and sorts them.
# `name for name in names if ...` is a GENERATOR EXPRESSION: a list
# comprehension without the square brackets, fed straight into sorted(),
# which returns a new sorted LIST. Sorting makes the printed list easy to
# read and identical from one run to the next.
#
# Also pure: both postgres_databases() and neo4j_databases() pass their
# raw answer through it, so the SAME rule decides on both sides.
# ---------------------------------------------------------------------
def project_databases(names: list[str]) -> list[str]:
    # The project's databases among all the names a server reports, sorted.
    return sorted(name for name in names if is_project_database(name))


# ---------------------------------------------------------------------
# def postgres_databases() -> list[str]:
#
# Asks PostgreSQL for every database it has. It connects to "postgres"
# (always present) and reads pg_database, PostgreSQL's catalogue of
# databases (seen in pipeline.py); the column datname is the name.
# fetchall() returns a list of one-column tuples, e.g.
# [("postgres",), ("gharchive",), ...]; row[0] takes the name out of each.
#
# Note the `return` is OUTSIDE the `with`: the connection is already
# closed when the filtering happens. Nothing needs it any more.
# ---------------------------------------------------------------------
def postgres_databases() -> list[str]:
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres") as conn:
        rows = conn.execute("SELECT datname FROM pg_database").fetchall()
    return project_databases([row[0] for row in rows])


# ---------------------------------------------------------------------
# def neo4j_databases(driver) -> list[str]:
#
# The same question for Neo4j, asked to the "system" database (database_=
# explained in load_neo4j.py):
#   SHOW DATABASES          Neo4j's command that lists its databases.
#   YIELD name              keeps only the "name" column of that listing
#                           (it has many: status, address, role...).
#   RETURN DISTINCT name    one row per name. In a cluster the same
#                           database can appear once per server; DISTINCT
#                           keeps one copy.
# .records is the list of answer rows; record["name"] reads a column by
# its name, like a dict.
#
# Unlike postgres_databases(), it takes the driver as a PARAMETER instead
# of creating its own: main() opens ONE driver and reuses it for every
# Neo4j step (a driver is heavier to create than a psycopg connection).
# ---------------------------------------------------------------------
def neo4j_databases(driver) -> list[str]:
    records = driver.execute_query("SHOW DATABASES YIELD name RETURN DISTINCT name", database_="system").records
    return project_databases([record["name"] for record in records])


# ---------------------------------------------------------------------
# def drop_postgres(name) -> None:
#
# 1. THE GUARD comes first, before any connection:
#      if not is_project_database(name): raise ValueError(...)
#    `raise` stops the function with an error (raise was explained in
#    download_gharchive.py). ValueError is Python's standard error for
#    "the type is fine but the VALUE isn't acceptable". Because the check
#    sits inside the drop function itself, no caller — today's main() or
#    some future script — can ever delete "postgres" through it, even by
#    mistake. The test file checks exactly this.
#    In the message, \' is an ESCAPED quote: the string is written with
#    single quotes '...', so the apostrophe of "isn't" needs a backslash.
#
# 2. The connection uses autocommit=True because DROP DATABASE, like
#    CREATE DATABASE, can't run inside a transaction (see pipeline.py).
#    It connects to "postgres": you can't delete the database you're
#    connected to.
#
# 3. The SQL:  DROP DATABASE IF EXISTS "name" WITH (FORCE)
#      DROP DATABASE   deletes the database and all its files.
#      IF EXISTS       no error if it's already gone (just a notice).
#      WITH (FORCE)    (PostgreSQL 13+) first closes every other
#                      connection to it. Without it, an open pgAdmin tab
#                      on that database makes the DROP fail with
#                      "database is being accessed by other users".
#    sql.Identifier(name) puts the name between double quotes: needed
#    here because names like "gharchive-2026-08-27-15" contain hyphens,
#    which SQL would otherwise read as minus signs.
# ---------------------------------------------------------------------
def drop_postgres(name: str) -> None:
    if not is_project_database(name):
        raise ValueError(f'Refusing to delete "{name}": it isn\'t a project database')
    print(f'Deleting the PostgreSQL database "{name}" ...')
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        # WITH (FORCE) first closes other connections to it (e.g. pgAdmin), which would block the DROP.
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
    print(f'The PostgreSQL database "{name}" has been deleted.')


# ---------------------------------------------------------------------
# def drop_neo4j(driver, name) -> None:
#
# Same guard first, then Cypher's administration command, sent to the
# "system" database:
#   DROP DATABASE `name`   the BACKTICKS `...` quote a name in Cypher (the
#                          same job as double quotes in SQL); needed for
#                          the hyphens in the names.
#   IF EXISTS              no error if it's already gone.
#   DESTROY DATA           delete its data files as well. (The other
#                          option, DUMP DATA, would first save a copy —
#                          not wanted: the data can always be rebuilt
#                          from data/.)
#   WAIT                   don't return until the deletion is finished, so
#                          the check in step 3 of main() sees the final
#                          state (the same WAIT as in CREATE DATABASE).
#
# Here the name is pasted into the text with an f-string, because Cypher
# doesn't accept a database name as a $parameter either. That's only
# acceptable because the guard above has just checked the name.
# ---------------------------------------------------------------------
def drop_neo4j(driver, name: str) -> None:
    if not is_project_database(name):
        raise ValueError(f'Refusing to delete "{name}": it isn\'t a project database')
    print(f'Deleting the Neo4j database "{name}" ...')
    # DESTROY DATA: delete its files too. WAIT: don't return until it's gone.
    driver.execute_query(f"DROP DATABASE `{name}` IF EXISTS DESTROY DATA WAIT", database_="system")
    print(f'The Neo4j database "{name}" has been deleted.')


# ---------------------------------------------------------------------
# def main() -> None:
#
# Four numbered steps, each announced with "== n." so the output reads
# like a checklist:
#   0. both servers answer?        (otherwise stop, having changed nothing)
#   1. find the project databases  (and show them)
#      -> confirmation: the user must type "delete"
#   2. delete them
#   3. check that none is left     (exit code 1 if some are)
# ---------------------------------------------------------------------
def main() -> None:
    # -----------------------------------------------------------------
    # Step 0. pipeline.servers_not_ready() tries a quick connection to
    # each server (5-second timeout) and returns None if both answer, or
    # a short sentence saying which one doesn't. `str | None` in its
    # signature means "a string, or None".
    #
    # Checking BOTH before touching EITHER avoids a half-done job: e.g.
    # the PostgreSQL databases deleted, then a crash because Neo4j Desktop
    # isn't open, leaving the two sides out of step.
    # `is not None` is the correct way to test for None (not `!= None`).
    # -----------------------------------------------------------------
    print("== 0. Check that both servers are answering")
    problem = pipeline.servers_not_ready()
    if problem is not None:
        print(f"{problem}. Nothing was deleted.")
        sys.exit(1)
    print("Both servers are answering.")

    # One Neo4j driver for the whole run (see neo4j_databases()).
    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        # -------------------------------------------------------------
        # Step 1. `a, b = x(), y()` assigns two variables in one line
        # (tuple unpacking). The "\n" at the start of the string prints
        # an empty line first, to separate the steps.
        #
        # ', '.join(list) glues the names into one string with ", "
        # between them. If the list is empty, join gives "" — and
        # `"" or 'none'` gives 'none', because `or` returns its right-hand
        # side when the left one is "empty/false". A short way to print
        # "none" instead of nothing.
        #
        # `not in_postgres`: an empty list counts as False, so this means
        # "the list is empty". If both are empty there's nothing to do,
        # and `return` ends main() normally (exit code 0).
        # -------------------------------------------------------------
        print("\n== 1. Find the project's databases")
        in_postgres, in_neo4j = postgres_databases(), neo4j_databases(driver)
        print(f"PostgreSQL ({len(in_postgres)}): {', '.join(in_postgres) or 'none'}")
        print(f"Neo4j      ({len(in_neo4j)}): {', '.join(in_neo4j) or 'none'}")
        if not in_postgres and not in_neo4j:
            print("\nThere's nothing to delete: both servers are already clean.")
            return

        # -------------------------------------------------------------
        # THE CONFIRMATION
        #
        # input(prompt) prints the prompt and WAITS for the user to type
        # a line and press Enter; it returns what was typed (as a str).
        #
        # Two ways input() can fail instead of returning:
        #   EOFError           there's no keyboard at all — e.g. the
        #                      script was run by a scheduler, or with its
        #                      input redirected from an empty file.
        #   KeyboardInterrupt  the user pressed Ctrl+C.
        # Both are caught and treated as an empty answer, i.e. "no".
        # (`except (A, B):` catches either type, as in download_gharchive.py.)
        #
        # answer.strip().lower(): strip() removes spaces and the line end
        # around the text, lower() makes it lowercase, so " Delete " is
        # accepted too. ANYTHING else — "y", "yes", Enter alone — stops.
        #
        # Why a whole word and not "y/n"? Typing "delete" is a deliberate
        # act: you can't do it by reflex. Deleting is the safe default
        # NEVER being taken: only one exact answer goes ahead.
        # -------------------------------------------------------------
        print("\nThese databases and ALL their data will be deleted. This can't be undone.")
        print("(The server databases postgres, neo4j and system, and the files in data/, are kept.)")
        try:
            answer = input('Type "delete" to delete them, or anything else to stop: ')
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() != "delete":
            print("\nNothing was deleted.")
            return

        # Step 2. One database at a time; each drop function re-checks the
        # name (the guard), even though these lists are already filtered.
        print("\n== 2. Delete them")
        for name in in_postgres:
            drop_postgres(name)
        for name in in_neo4j:
            drop_neo4j(driver, name)

        # -------------------------------------------------------------
        # Step 3. TRUST, BUT VERIFY: ask both servers again, with the same
        # functions as step 1. A command that "returned without error" is
        # not proof that the result is what you wanted; asking the server
        # again is. If anything is left, exit code 1 tells whoever ran the
        # script that it didn't fully succeed (exit codes: check_connections.py).
        # -------------------------------------------------------------
        print("\n== 3. Check that none is left")
        left_postgres, left_neo4j = postgres_databases(), neo4j_databases(driver)
        print(f"PostgreSQL: {', '.join(left_postgres) or 'no project database left'}")
        print(f"Neo4j:      {', '.join(left_neo4j) or 'no project database left'}")
        if left_postgres or left_neo4j:
            print("\nSome databases are still there (see above).")
            sys.exit(1)
        print("\nDone: both servers are clean.")


# main() and the `if __name__ == "__main__":` guard: identical purpose and
# shape as in download_gharchive.py. Here the guard matters for real: the
# test file IMPORTS this module, and importing must never start deleting.
if __name__ == "__main__":
    main()
