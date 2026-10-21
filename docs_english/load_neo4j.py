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
# NEO4J_DATABASE = "gharchive" — the project's decision: always work in
# the database called gharchive, on both sides. check_connections.py
# didn't name a database, so it used the instance's default ("neo4j").
# Here every query passes database_=NEO4J_DATABASE explicitly.
#
# BATCH_SIZE = 5000 — how many rows go in each request (see
# run_in_batches()).
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "data" / "csv"
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_DATABASE = "gharchive"
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
# $rows is a PARAMETER: a placeholder whose value Python sends separately
# (here, a list of dicts). Sending data as parameters, instead of pasting
# it into the query text, is safer and lets Neo4j reuse the same query
# plan for every batch.
#
# UNWIND $rows AS row
#   Takes the LIST and turns it into one row per element, so the rest of
#   the query runs once per element — like a `for row in rows:` loop, but
#   inside the database, in a single request.
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
# def run_in_batches(driver, query, rows) -> None:
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
# PostgreSQL's COPY sends everything as one continuous stream; Neo4j gets
# it in batches. Both are the usual way of bulk-loading each database.
# ---------------------------------------------------------------------
def run_in_batches(driver, query: str, rows: list[dict]) -> None:
    # Send the rows a few thousand at a time rather than all in one huge request.
    for start in range(0, len(rows), BATCH_SIZE):
        driver.execute_query(query, rows=rows[start:start + BATCH_SIZE], database_=NEO4J_DATABASE)


# Same timer helper as load_postgres.py — see its annotated copy.
def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:6.2f} s"


def load(csv_dir: Path) -> bool:
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
        driver.execute_query("MATCH (n) DETACH DELETE n", database_=NEO4J_DATABASE)
        for constraint in CONSTRAINTS:
            driver.execute_query(constraint, database_=NEO4J_DATABASE)
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
            run_in_batches(driver, query, rows)
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
            records, _, _ = driver.execute_query(query, database_=NEO4J_DATABASE)
            in_db = records[0]["n"]
            in_csv = csv_counts[csv_name]
            status = "OK" if in_db == in_csv else "MISMATCH"
            all_match = all_match and in_db == in_csv
            print(f"  {label:<22} {in_db:>7}   {csv_name:<16} {in_csv:>7}   {status}")
    return all_match


# parse_args() and main(): same as load_postgres.py.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR,
                         help=f"Folder with the CSV files from extract_csv.py (default: {DEFAULT_CSV_DIR})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not load(args.csv_dir):
        sys.exit("Some counts don't match their CSV file.")
    print("\nNeo4j load complete.")


# See download_gharchive.py's annotated copy for the __name__ guard.
if __name__ == "__main__":
    main()
