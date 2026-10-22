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

import argparse
import csv
import os
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "data" / "csv"
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"
DEFAULT_DATABASE = "gharchive"
BATCH_SIZE = 5000

CONSTRAINTS = [
    "CREATE CONSTRAINT actor_id_unique IF NOT EXISTS FOR (a:Actor) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT repo_id_unique IF NOT EXISTS FOR (r:Repo) REQUIRE r.id IS UNIQUE",
]

CREATE_ACTORS = "UNWIND $rows AS row CREATE (:Actor {id: row.id, login: row.login})"
CREATE_REPOS = "UNWIND $rows AS row CREATE (:Repo {id: row.id, name: row.name})"
CREATE_EDGES = """
UNWIND $rows AS row
MATCH (a:Actor {id: row.actor_id})
MATCH (r:Repo {id: row.repo_id})
CREATE (a)-[:INTERACTED_WITH]->(r)
"""

COUNTS = [
    ("Actor nodes", "MATCH (a:Actor) RETURN count(a) AS n", "actors.csv"),
    ("Repo nodes", "MATCH (r:Repo) RETURN count(r) AS n", "repos.csv"),
    ("INTERACTED_WITH edges", "MATCH ()-[e:INTERACTED_WITH]->() RETURN count(e) AS n", "actor_repo.csv"),
]


def read_csv(path: Path, int_columns: tuple[str, ...]) -> list[dict]:
    # csv.DictReader gives each row as a dict keyed by the header's column names.
    # Ids are converted to int, so they're stored as numbers, as in PostgreSQL.
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for column in int_columns:
            row[column] = int(row[column])
    return rows


def run_in_batches(driver, query: str, rows: list[dict], database: str) -> None:
    # Send the rows a few thousand at a time rather than all in one huge request.
    for start in range(0, len(rows), BATCH_SIZE):
        driver.execute_query(query, rows=rows[start:start + BATCH_SIZE], database_=database)


def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:6.2f} s"


def load(csv_dir: Path, database: str = DEFAULT_DATABASE) -> bool:
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

        step = time.perf_counter()
        driver.execute_query("MATCH (n) DETACH DELETE n", database_=database)
        for constraint in CONSTRAINTS:
            driver.execute_query(constraint, database_=database)
        print(f"Database emptied; unique constraints in place   {seconds_since(step)}")

        # Nodes first: the edges step looks each actor and repo up by id.
        for label, query, rows in (("Actor nodes", CREATE_ACTORS, actors),
                                   ("Repo nodes", CREATE_REPOS, repos),
                                   ("INTERACTED_WITH edges", CREATE_EDGES, edges)):
            step = time.perf_counter()
            run_in_batches(driver, query, rows, database)
            print(f"Created {label:<22}                  {seconds_since(step)}")

        print(f"Total load time                                 {seconds_since(load_start)}")

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


if __name__ == "__main__":
    main()
