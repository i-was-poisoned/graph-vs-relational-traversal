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

import os
import sys

import psycopg
from neo4j import GraphDatabase
from psycopg import sql

import load_neo4j
import pipeline

# Names that may never be deleted, whatever they look like.
SERVER_DATABASES = {"postgres", "template0", "template1", "neo4j", "system"}


def is_project_database(name: str) -> bool:
    # gharchive, gharchive24h, gharchive-..., gharchivetest; nothing else.
    return name.startswith("gharchive") and name not in SERVER_DATABASES


def project_databases(names: list[str]) -> list[str]:
    # The project's databases among all the names a server reports, sorted.
    return sorted(name for name in names if is_project_database(name))


def postgres_databases() -> list[str]:
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres") as conn:
        rows = conn.execute("SELECT datname FROM pg_database").fetchall()
    return project_databases([row[0] for row in rows])


def neo4j_databases(driver) -> list[str]:
    records = driver.execute_query("SHOW DATABASES YIELD name RETURN DISTINCT name", database_="system").records
    return project_databases([record["name"] for record in records])


def drop_postgres(name: str) -> None:
    if not is_project_database(name):
        raise ValueError(f'Refusing to delete "{name}": it isn\'t a project database')
    print(f'Deleting the PostgreSQL database "{name}" ...')
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        # WITH (FORCE) first closes other connections to it (e.g. pgAdmin), which would block the DROP.
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
    print(f'The PostgreSQL database "{name}" has been deleted.')


def drop_neo4j(driver, name: str) -> None:
    if not is_project_database(name):
        raise ValueError(f'Refusing to delete "{name}": it isn\'t a project database')
    print(f'Deleting the Neo4j database "{name}" ...')
    # DESTROY DATA: delete its files too. WAIT: don't return until it's gone.
    driver.execute_query(f"DROP DATABASE `{name}` IF EXISTS DESTROY DATA WAIT", database_="system")
    print(f'The Neo4j database "{name}" has been deleted.')


def main() -> None:
    print("== 0. Check that both servers are answering")
    problem = pipeline.servers_not_ready()
    if problem is not None:
        print(f"{problem}. Nothing was deleted.")
        sys.exit(1)
    print("Both servers are answering.")

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        print("\n== 1. Find the project's databases")
        in_postgres, in_neo4j = postgres_databases(), neo4j_databases(driver)
        print(f"PostgreSQL ({len(in_postgres)}): {', '.join(in_postgres) or 'none'}")
        print(f"Neo4j      ({len(in_neo4j)}): {', '.join(in_neo4j) or 'none'}")
        if not in_postgres and not in_neo4j:
            print("\nThere's nothing to delete: both servers are already clean.")
            return

        print("\nThese databases and ALL their data will be deleted. This can't be undone.")
        print("(The server databases postgres, neo4j and system, and the files in data/, are kept.)")
        try:
            answer = input('Type "delete" to delete them, or anything else to stop: ')
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() != "delete":
            print("\nNothing was deleted.")
            return

        print("\n== 2. Delete them")
        for name in in_postgres:
            drop_postgres(name)
        for name in in_neo4j:
            drop_neo4j(driver, name)

        print("\n== 3. Check that none is left")
        left_postgres, left_neo4j = postgres_databases(), neo4j_databases(driver)
        print(f"PostgreSQL: {', '.join(left_postgres) or 'no project database left'}")
        print(f"Neo4j:      {', '.join(left_neo4j) or 'no project database left'}")
        if left_postgres or left_neo4j:
            print("\nSome databases are still there (see above).")
            sys.exit(1)
        print("\nDone: both servers are clean.")


if __name__ == "__main__":
    main()
