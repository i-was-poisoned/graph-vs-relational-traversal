"""Integration tests: load the same tiny data set into real PostgreSQL and Neo4j databases.

These tests need both servers running, so they're kept apart from the unit tests
(marker "integration") and don't run with a plain "python -m pytest".

Run with:
    ./run.sh -m pytest -m integration      # locally (passwords from secrets.sh)

The databases used are a separate test database on each side, never the
benchmark's "gharchive" or the pipeline's "gharchive24h":
    TEST_POSTGRES_DATABASE   default "gharchivetest" (created if missing)
    TEST_NEO4J_DATABASE      default "gharchivetest" (created if missing; in CI
                             "neo4j", the only database Neo4j Community allows)
"""

import json
import os
import time
from pathlib import Path

import psycopg
import pytest
from neo4j import GraphDatabase
from psycopg import sql

import extract_csv
import load_neo4j
import load_postgres

pytestmark = pytest.mark.integration

POSTGRES_DATABASE = os.environ.get("TEST_POSTGRES_DATABASE", "gharchivetest")
NEO4J_DATABASE = os.environ.get("TEST_NEO4J_DATABASE", "gharchivetest")
PROTECTED_DATABASES = {"gharchive", "gharchive24h"}

# Ana (1) and Bea (2) both work on repo 10; Bea also on 20; Carl (3) only on 30.
# Plus the known hard cases: a bot, an empty repo, a repeated pair and a renamed login.
EVENTS = [
    {"actor": {"id": 1, "login": "ana"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:00:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:01:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 20, "name": "bea/tool"}, "created_at": "2026-08-27T15:02:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 20, "name": "bea/tool"}, "created_at": "2026-08-27T15:03:00Z"},
    {"actor": {"id": 3, "login": "carl"}, "repo": {"id": 30, "name": "carl/notes"}, "created_at": "2026-08-27T15:04:00Z"},
    {"actor": {"id": 3, "login": "carl-dev"}, "repo": {"id": 30, "name": "carl/notes"}, "created_at": "2026-08-27T15:05:00Z"},
    {"actor": {"id": 9, "login": "dependabot[bot]"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:06:00Z"},
    {"actor": {"id": 4, "login": "dan"}, "repo": {}, "created_at": "2026-08-27T15:07:00Z"},
]
EXPECTED_ACTORS = {(1, "ana"), (2, "bea"), (3, "carl-dev")}
EXPECTED_REPOS = {(10, "ana/project"), (20, "bea/tool"), (30, "carl/notes")}
EXPECTED_PAIRS = {(1, 10), (2, 10), (2, 20), (3, 30)}


def neo4j_driver():
    return GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=(load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"]))


def wait_for_neo4j(timeout_seconds: int = 90) -> None:
    # In CI the Neo4j container takes a few seconds to start accepting connections.
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with neo4j_driver() as driver:
                driver.verify_connectivity()
            return
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(2)


def ensure_test_databases() -> None:
    with psycopg.connect(**load_postgres.POSTGRES_SETTINGS, dbname="postgres", autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (POSTGRES_DATABASE,)).fetchone() is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(POSTGRES_DATABASE)))
    # "neo4j" always exists; any other name needs CREATE DATABASE (Enterprise Edition only).
    if NEO4J_DATABASE != "neo4j":
        with neo4j_driver() as driver:
            driver.execute_query(f"CREATE DATABASE `{NEO4J_DATABASE}` IF NOT EXISTS WAIT", database_="system")


def load_both(csv_dir: Path) -> tuple[bool, bool]:
    return load_postgres.load(csv_dir, POSTGRES_DATABASE), load_neo4j.load(csv_dir, NEO4J_DATABASE)


def postgres_rows(query: str) -> set[tuple]:
    with psycopg.connect(**load_postgres.POSTGRES_SETTINGS, dbname=POSTGRES_DATABASE) as conn:
        return set(conn.execute(query).fetchall())


def neo4j_rows(query: str, **params) -> set[tuple]:
    with neo4j_driver() as driver:
        records, _, _ = driver.execute_query(query, params, database_=NEO4J_DATABASE)
    return {tuple(record.values()) for record in records}


@pytest.fixture(scope="module")
def csv_dir(tmp_path_factory) -> Path:
    # Safety guard: these tests empty the databases they load into.
    assert POSTGRES_DATABASE not in PROTECTED_DATABASES, f"refusing to use {POSTGRES_DATABASE!r}"
    assert NEO4J_DATABASE not in PROTECTED_DATABASES, f"refusing to use {NEO4J_DATABASE!r}"

    folder = tmp_path_factory.mktemp("integration")
    events_file = folder / "events.json"
    events_file.write_text("".join(json.dumps(event) + "\n" for event in EVENTS), encoding="utf-8")
    actors, repos, pairs, _ = extract_csv.extract([events_file])
    extract_csv.write_all(folder, actors, repos, pairs)

    wait_for_neo4j()
    ensure_test_databases()
    return folder


@pytest.fixture(scope="module")
def loaded(csv_dir) -> tuple[bool, bool]:
    # Loaded once and shared by the tests below, which only read.
    return load_both(csv_dir)


def test_both_loads_match_their_csv_files(loaded):
    postgres_ok, neo4j_ok = loaded
    assert postgres_ok
    assert neo4j_ok


def test_both_databases_hold_the_same_actors(loaded):
    assert postgres_rows("SELECT id, login FROM actor") == EXPECTED_ACTORS
    assert neo4j_rows("MATCH (a:Actor) RETURN a.id, a.login") == EXPECTED_ACTORS


def test_both_databases_hold_the_same_repos(loaded):
    assert postgres_rows("SELECT id, name FROM repo") == EXPECTED_REPOS
    assert neo4j_rows("MATCH (r:Repo) RETURN r.id, r.name") == EXPECTED_REPOS


def test_both_databases_hold_the_same_connections(loaded):
    assert postgres_rows("SELECT actor_id, repo_id FROM actor_repo") == EXPECTED_PAIRS
    assert neo4j_rows("MATCH (a:Actor)-[:INTERACTED_WITH]->(r:Repo) RETURN a.id, r.id") == EXPECTED_PAIRS


def test_same_traversal_answer_on_both_sides(loaded):
    # Who worked on a repo that Ana (1) also worked on? Two hops: actor -> repo -> actor.
    postgres_answer = postgres_rows("""
        SELECT DISTINCT other.actor_id
        FROM actor_repo AS mine
        JOIN actor_repo AS other ON other.repo_id = mine.repo_id
        WHERE mine.actor_id = 1 AND other.actor_id <> 1
    """)
    neo4j_answer = neo4j_rows("""
        MATCH (:Actor {id: $id})-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(other:Actor)
        WHERE other.id <> $id
        RETURN DISTINCT other.id
    """, id=1)
    assert postgres_answer == neo4j_answer == {(2,)}


def test_loading_twice_gives_the_same_result(loaded, csv_dir):
    # Each load starts from empty tables/graph, so a second run must not duplicate anything.
    assert load_both(csv_dir) == (True, True)
    assert postgres_rows("SELECT count(*) FROM actor_repo") == {(len(EXPECTED_PAIRS),)}
    assert neo4j_rows("MATCH ()-[e:INTERACTED_WITH]->() RETURN count(e)") == {(len(EXPECTED_PAIRS),)}
