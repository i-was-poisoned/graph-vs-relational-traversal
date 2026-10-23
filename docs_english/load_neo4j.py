########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/load_neo4j.py.
# It is NOT meant to be run as part of the project pipeline — it lives in
# docs_english/ because its purpose is to teach, not to execute. The real, "clean"
# script (with none of this commentary) is scripts/load_neo4j.py.
#
# This file assumes you've already read the earlier annotated scripts,
# especially check_connections.py (the Neo4j driver, execute_query,
# NEO4J_PASSWORD) and load_postgres.py (the PostgreSQL side of the same
# job, and time.perf_counter()). This file focuses on what's NEW: Cypher
# to create nodes and edges (CREATE, MATCH, UNWIND, parameters),
# uniqueness CONSTRAINTS, reading a CSV into dicts with csv.DictReader,
# and sending data in BATCHES.
#
# WHAT'S NEW in this version: as in load_postgres.py, you can choose
# WHICH database to load into (--database, or the `database` parameter
# of load()). The default is still "gharchive", the benchmark's frozen
# database; the live 24-hour pipeline (pipeline.py) loads into
# "gharchive24h" instead, so it never touches the benchmark data.
#
# Run it through run.sh (it needs NEO4J_PASSWORD):
#     ./run.sh scripts/load_neo4j.py
########################################################################

"""Load the extracted CSV files into the Neo4j "gharchive" database.

Creates (or re-creates) the benchmark graph from the CSV files written by
extract_csv.py, the same files PostgreSQL is loaded from:

    (:Actor {id, login})   one node per row of actors.csv      id is unique
    (:Repo  {id, name})    one node per row of repos.csv       id is unique
    (:Actor)-[:INTERACTED_WITH]->(:Repo)   one edge per row of actor_repo.csv

Every run starts from an empty database, so running it twice gives the same
result. At the end it checks that the node and edge counts match the CSV files.

Usage:
    ./run.sh scripts/load_neo4j.py
    ./run.sh scripts/load_neo4j.py --csv-dir data/csv
    ./run.sh scripts/load_neo4j.py --csv-dir data/live/csv --database gharchive24h
"""

# All already explained in earlier scripts (csv in extract_csv.py, time in
# load_postgres.py, GraphDatabase and os in check_connections.py).
import argparse
import csv
import os
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

# ---------------------------------------------------------------------
# Constants
#
# DEFAULT_DATABASE = "gharchive" — the project's decision: the benchmark
# always works in the database called gharchive, on both sides.
# check_connections.py didn't name a database, so it used the instance's
# default ("neo4j"). Here every query passes database_=... explicitly.
#
# NEW: this constant used to be called NEO4J_DATABASE and was used
# directly by every query. It's now DEFAULT_DATABASE (the same name as
# in load_postgres.py) because it's only the DEFAULT: load() takes a
# `database` parameter, and the live pipeline passes "gharchive24h".
#
# Why "gharchive24h" and not "gharchive_24h"? Neo4j database names may
# only contain letters, digits, dots (.) and dashes (-) — NO underscores
# — so "gharchive_24h" would be rejected. The same name is used on the
# PostgreSQL side too, to keep the two matching.
#
# BATCH_SIZE = 5000 — how many rows go in each request (see
# run_in_batches()).
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "data" / "csv"
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"
DEFAULT_DATABASE = "gharchive"
BATCH_SIZE = 5000

# ---------------------------------------------------------------------
# CONSTRAINTS — Neo4j's equivalent of PostgreSQL's PRIMARY KEY
#
# CREATE CONSTRAINT actor_id_unique IF NOT EXISTS
#     FOR (a:Actor) REQUIRE a.id IS UNIQUE
#
#   "For every node with the label Actor, the id property must be
#   unique." Like a primary key, it also builds an INDEX on that
#   property, so finding an actor by id is instant — which the edges step
#   below relies on.
#   IF NOT EXISTS: on a second run the constraint is already there, and
#   this simply does nothing (instead of failing).
#
# Notice there's NO index for the edges: in a graph, every node already
# stores direct links to its own edges ("index-free adjacency"). That's
# exactly the advantage the benchmark wants to measure against
# PostgreSQL's actor_repo indexes.
# ---------------------------------------------------------------------
CONSTRAINTS = [
    "CREATE CONSTRAINT actor_id_unique IF NOT EXISTS FOR (a:Actor) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT repo_id_unique IF NOT EXISTS FOR (r:Repo) REQUIRE r.id IS UNIQUE",
]

# ---------------------------------------------------------------------
# The Cypher queries that create the data
#
# Cypher is Neo4j's query language. It "draws" the graph with symbols:
#   (a:Actor {id: 19})        a NODE: round brackets, a label (:Actor)
#                             and properties in curly braces
#   -[:INTERACTED_WITH]->     an EDGE: square brackets, a type, and an
#                             arrow showing its direction
#
# $rows: a PARAMETER, i.e. a "placeholder" that Python fills in
#
#   The query is FIXED TEXT with a gap, $rows, like a form. Python sends
#   Neo4j TWO things separately: the query (the text with the gap) and the
#   gap's value (the data). It happens in run_in_batches():
#
#       driver.execute_query(query, rows=rows[start:start + BATCH_SIZE], ...)
#       #                    └ the query    └ the value of $rows
#
#   It's like calling a function: $rows is the parameter, and what Python
#   sends is the argument. For example, $rows could be this list of 3
#   dicts (in reality each batch has 5,000):
#
#       [{"id": 19,        "login": "brynary"},
#        {"id": 452,       "login": "yrashk"},
#        {"id": 321725054, "login": "peitongshi"}]
#
#   Why not paste the data straight into the query text?
#     - It's SAFER. If a login contained a quote (') or a malicious piece
#       of text, pasting it into the query could break it or change what
#       it does (an attack known as "injection"). As a parameter, Neo4j
#       always treats it as DATA, never as part of the command.
#     - It's FASTER. Before running a query, Neo4j analyses it and decides
#       how to do it (its "plan"). If the text is always the same and only
#       the data changes, it prepares the plan ONCE and reuses it for
#       every batch. If the data were pasted in, every batch would be
#       different text, and the plan would have to be prepared each time.
#
# UNWIND $rows AS row: turns the LIST into one row per element
#
#   Neo4j receives ONE thing: the whole list. But CREATE has to run ONCE
#   PER ACTOR. UNWIND "unrolls" the list into one row per element, and
#   calls each one "row" (AS row):
#
#     $rows (1 list with 3 elements)
#        │  UNWIND $rows AS row
#        ▼
#     row 1: row = {id: 19, login: "brynary"}           -> CREATE (:Actor ...)
#     row 2: row = {id: 452, login: "yrashk"}           -> CREATE (:Actor ...)
#     row 3: row = {id: 321725054, login: "peitongshi"} -> CREATE (:Actor ...)
#
#   row.id and row.login read each dict's keys, like row["id"] in Python.
#   So the query is the same as this loop, but run INSIDE Neo4j, in a
#   single request:
#
#       for row in rows:
#           create_actor_node(id=row["id"], login=row["login"])
#
#   Why not run that loop in Python, with one query per actor? Because
#   that would be 14,515 requests, each one a round trip between Python
#   and Neo4j. It's like sending 14,515 letters, each with one actor,
#   instead of a few boxes with 5,000 actors each and the instruction
#   "for every actor in this list, create a node". With UNWIND and the
#   batches, the actors arrive in 3 boxes (14,515 / 5,000).
#
# CREATE (:Actor {id: row.id, login: row.login})
#   Creates one node per row. row.id reads the "id" key of the dict.
#
# CREATE_EDGES does more work per row:
#   MATCH (a:Actor {id: row.actor_id})   FIND the actor with that id
#   MATCH (r:Repo {id: row.repo_id})     FIND the repo with that id
#   CREATE (a)-[:INTERACTED_WITH]->(r)   create the edge between them
# The two MATCHes are instant thanks to the constraints' indexes.
#
# Why the name INTERACTED_WITH? The connections come from every kind of
# event (pushes, comments, stars...), and starring or commenting isn't
# "contributing", so a neutral name is more accurate.
# ---------------------------------------------------------------------
CREATE_ACTORS = "UNWIND $rows AS row CREATE (:Actor {id: row.id, login: row.login})"
CREATE_REPOS = "UNWIND $rows AS row CREATE (:Repo {id: row.id, name: row.name})"
CREATE_EDGES = """
UNWIND $rows AS row
MATCH (a:Actor {id: row.actor_id})
MATCH (r:Repo {id: row.repo_id})
CREATE (a)-[:INTERACTED_WITH]->(r)
"""

# ---------------------------------------------------------------------
# COUNTS — the queries for the final check: (label, query, CSV file).
#   MATCH (a:Actor) RETURN count(a) AS n           how many Actor nodes
#   MATCH ()-[e:INTERACTED_WITH]->() RETURN ...    how many edges; ()
#                                                  is "any node"
# `AS n` names the result column, so Python can read it as record["n"].
# ---------------------------------------------------------------------
COUNTS = [
    ("Actor nodes", "MATCH (a:Actor) RETURN count(a) AS n", "actors.csv"),
    ("Repo nodes", "MATCH (r:Repo) RETURN count(r) AS n", "repos.csv"),
    ("INTERACTED_WITH edges", "MATCH ()-[e:INTERACTED_WITH]->() RETURN count(e) AS n", "actor_repo.csv"),
]


# ---------------------------------------------------------------------
# def read_csv(path, int_columns) -> list[dict]:
#
# csv.DictReader reads a CSV file and gives each row as a DICT whose keys
# are the header's column names:
#
#     id,login            ->   {"id": "19", "login": "brynary"}
#     19,brynary
#
# A CSV is just text, so every value comes out as a STRING ("19"). The
# loop then turns the id columns into numbers with int(), so Neo4j
# stores them as integers, exactly like PostgreSQL's BIGINT. If one side
# stored ids as text and the other as numbers, the data wouldn't be
# truly identical.
#
# int_columns: tuple[str, ...] — a tuple of column names of any length;
# the `...` means "any number of str". ("id",) with a trailing comma is a
# tuple with ONE element (without the comma, ("id") would just be the
# string "id").
# ---------------------------------------------------------------------
def read_csv(path: Path, int_columns: tuple[str, ...]) -> list[dict]:
    # csv.DictReader gives each row as a dict keyed by the header's column names.
    # Ids are converted to int, so they're stored as numbers, as in PostgreSQL.
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for column in int_columns:
            row[column] = int(row[column])
    return rows


# ---------------------------------------------------------------------
# def run_in_batches(driver, query, rows, database) -> None:
#
# Instead of sending 15,053 rows in one huge request, it sends them in
# BATCHES of BATCH_SIZE (5,000): smaller requests use less memory on both
# sides and don't risk hitting a size limit.
#
# range(0, len(rows), BATCH_SIZE) counts in steps of 5,000:
#     0, 5000, 10000, 15000
# rows[start:start + BATCH_SIZE] is a SLICE of 5,000 rows (the last one
# can be shorter): rows[0:5000], rows[5000:10000], ...
#
# rows=... is sent as the $rows parameter of the query.
# database_= has a trailing underscore so it can't be confused with a
# query parameter that happened to be called "database".
#
# NEW: `database` is now a parameter (passed in by load()) instead of the
# fixed constant, so the batches go to whichever database load() was
# asked to fill. Note the two different names on that line:
#   database_=database   the driver's option (with _) = our variable.
#
# PostgreSQL's COPY sends everything as one continuous stream; Neo4j gets
# it in batches. Both are the usual way of bulk-loading each database.
# ---------------------------------------------------------------------
def run_in_batches(driver, query: str, rows: list[dict], database: str) -> None:
    # Send the rows a few thousand at a time rather than all in one huge request.
    for start in range(0, len(rows), BATCH_SIZE):
        driver.execute_query(query, rows=rows[start:start + BATCH_SIZE], database_=database)


# Same timer helper as load_postgres.py — see its annotated copy.
def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:6.2f} s"


# ---------------------------------------------------------------------
# def load(csv_dir, database=DEFAULT_DATABASE) -> bool:
#
# NEW: the `database` parameter, same idea as in load_postgres.py. It
# defaults to DEFAULT_DATABASE ("gharchive"), so load(csv_dir) behaves
# exactly as before. Every query below now uses database_=database, and
# run_in_batches() is handed the same name, so ALL the work (emptying,
# constraints, loading, counting) happens in the chosen database.
#
# One difference from PostgreSQL: here the driver connects to the Neo4j
# SERVER (NEO4J_URI) and the database is picked per query, with
# database_=...; in psycopg the database is picked once, when connecting.
# ---------------------------------------------------------------------
def load(csv_dir: Path, database: str = DEFAULT_DATABASE) -> bool:
    # Reading the CSVs into Python is timed on its own and left OUT of the
    # total: it's preparation, not loading into the database.
    step = time.perf_counter()
    actors = read_csv(csv_dir / "actors.csv", ("id",))
    repos = read_csv(csv_dir / "repos.csv", ("id",))
    edges = read_csv(csv_dir / "actor_repo.csv", ("actor_id", "repo_id"))
    print(f"CSV files read into Python                      {seconds_since(step)}")

    password = os.environ["NEO4J_PASSWORD"]
    all_match = True
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password)) as driver:
        driver.verify_connectivity()
        load_start = time.perf_counter()

        # -------------------------------------------------------------
        # MATCH (n) DETACH DELETE n
        #   MATCH (n)   every node in the database
        #   DETACH      first remove each node's edges...
        #   DELETE n    ...then the node itself (Neo4j won't delete a
        #               node that still has edges).
        # The Neo4j equivalent of PostgreSQL's DROP TABLE: every run
        # starts from an empty database.
        # -------------------------------------------------------------
        step = time.perf_counter()
        driver.execute_query("MATCH (n) DETACH DELETE n", database_=database)
        for constraint in CONSTRAINTS:
            driver.execute_query(constraint, database_=database)
        print(f"Database emptied; unique constraints in place   {seconds_since(step)}")

        # -------------------------------------------------------------
        # The three loads, in a loop over (label, query, rows) tuples.
        # ORDER matters, as in PostgreSQL: nodes first, because each
        # edge needs to FIND its actor and its repo (the MATCHes in
        # CREATE_EDGES). Each step is timed on its own.
        # -------------------------------------------------------------
        # Nodes first: the edges step looks each actor and repo up by id.
        for label, query, rows in (("Actor nodes", CREATE_ACTORS, actors),
                                   ("Repo nodes", CREATE_REPOS, repos),
                                   ("INTERACTED_WITH edges", CREATE_EDGES, edges)):
            step = time.perf_counter()
            run_in_batches(driver, query, rows, database)
            print(f"Created {label:<22}                  {seconds_since(step)}")

        # No explicit commit here: execute_query() commits each request
        # on its own, so the data is already saved.
        print(f"Total load time                                 {seconds_since(load_start)}")

        # -------------------------------------------------------------
        # The check, same idea as load_postgres.py: count in the
        # database, compare with the CSV. records[0]["n"] reads column
        # "n" of the first (only) result row.
        # -------------------------------------------------------------
        print("\nLoaded (database vs. CSV file):")
        csv_counts = {"actors.csv": len(actors), "repos.csv": len(repos), "actor_repo.csv": len(edges)}
        for label, query, csv_name in COUNTS:
            records, _, _ = driver.execute_query(query, database_=database)
            in_db = records[0]["n"]
            in_csv = csv_counts[csv_name]
            status = "OK" if in_db == in_csv else "MISMATCH"
            all_match = all_match and in_db == in_csv
            print(f"  {label:<22} {in_db:>7}   {csv_name:<16} {in_csv:>7}   {status}")
    return all_match


# parse_args() and main(): same as load_postgres.py, including the NEW
# --database option (e.g. --database gharchive24h).
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR,
                         help=f"Folder with the CSV files from extract_csv.py (default: {DEFAULT_CSV_DIR})")
    parser.add_argument("--database", default=DEFAULT_DATABASE,
                         help=f"Neo4j database to load into (default: {DEFAULT_DATABASE})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not load(args.csv_dir, args.database):
        sys.exit("Some counts don't match their CSV file.")
    print("\nNeo4j load complete.")


# See download_gharchive.py's annotated copy for the __name__ guard.
if __name__ == "__main__":
    main()
