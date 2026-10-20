"""Check that Python can reach both of the project's databases.

Connects to PostgreSQL and to Neo4j with the passwords taken from the
environment (PGPASSWORD and NEO4J_PASSWORD, loaded from secrets.sh by run.sh)
and prints each server's version. Exits with an error if either one fails.

Usage:
    ./run.sh scripts/check_connections.py
"""

import os
import sys

import psycopg
from neo4j import GraphDatabase

POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"


def check_postgres() -> None:
    # psycopg reads the password from PGPASSWORD by itself.
    with psycopg.connect(**POSTGRES_SETTINGS) as conn:
        version = conn.execute("SELECT version();").fetchone()[0]
    print(f"PostgreSQL OK: {version}")


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


def main() -> None:
    missing = [name for name in ("PGPASSWORD", "NEO4J_PASSWORD") if not os.environ.get(name)]
    if missing:
        sys.exit(f"Missing environment variable(s): {', '.join(missing)}. "
                 "Run this script through run.sh, which loads them from secrets.sh.")

    failed = False
    for name, check in (("PostgreSQL", check_postgres), ("Neo4j", check_neo4j)):
        try:
            check()
        except Exception as error:
            print(f"{name} FAILED: {error}")
            failed = True

    if failed:
        sys.exit(1)
    print("Both databases are reachable.")


if __name__ == "__main__":
    main()
