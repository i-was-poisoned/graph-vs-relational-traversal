########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of tests/test_integration.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute (pytest only looks for tests in tests/, as
# pytest.ini says). The real, "clean" file (with none of this commentary)
# is tests/test_integration.py.
#
# Read docs_english/test_extract_csv.py first: the pytest basics (test_
# names, assert, fixtures, tmp_path) are explained there and not repeated.
#
# UNIT TESTS vs INTEGRATION TESTS
#   - A UNIT test checks ONE piece on its own, with nothing external:
#     no internet, no database. It runs in milliseconds, anywhere.
#   - An INTEGRATION test checks that SEVERAL pieces work TOGETHER, with
#     the real things they talk to. Here: made-up events -> extract_csv.py
#     -> CSV files -> load_postgres.py and load_neo4j.py -> a REAL
#     PostgreSQL and a REAL Neo4j. Then it asks both databases what they
#     hold and compares the answers.
#   Both kinds are written with pytest: same test_ functions, same assert.
#   The difference is what happens inside the test.
#
# Its job in the project: prove that both databases end up holding
# EXACTLY the same data, and that the same question (a 2-hop traversal)
# gets the same answer in SQL and in Cypher — the benchmark's starting
# point.
########################################################################

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

# json: to write the made-up events as JSON Lines, like GH Archive.
import json

# os: to read environment variables (os.environ), like the database names
# and NEO4J_PASSWORD.
import os

# time: for the "wait until Neo4j is ready" loop (time.monotonic, time.sleep).
import time
from pathlib import Path

# psycopg: the PostgreSQL connector — the tests talk to the database
# directly, to check what the loader left there.
import psycopg

# pytest: needed here (the unit tests didn't import it) for the marker
# and the @pytest.fixture decorator.
import pytest
from neo4j import GraphDatabase

# psycopg's `sql` module builds SQL statements SAFELY when a NAME (not a
# value) has to go into them — here, the name of the database to create.
from psycopg import sql

# The three scripts being tested together. pytest.ini's
# `pythonpath = scripts` lets these imports find them.
import extract_csv
import load_neo4j
import load_postgres

# ---------------------------------------------------------------------
# pytestmark: a special name pytest looks for. Whatever marker is
# assigned to it is put on EVERY test in this file at once.
# Here, the marker "integration" (registered in pytest.ini). Because
# pytest.ini has `addopts = -m "not integration"`, a plain
# `python -m pytest` skips all of these ("6 deselected"); they only run
# with `python -m pytest -m integration`.
# ---------------------------------------------------------------------
pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------
# Which databases to use. os.environ.get("NAME", default) reads an
# environment variable and, if it doesn't exist, returns the default.
# (Compare os.environ["NAME"], used for NEO4J_PASSWORD below: that one
# FAILS if the variable is missing — right for a password, which has no
# sensible default.)
# On your computer nothing is set, so both are "gharchivetest". In CI,
# ci.yml sets TEST_NEO4J_DATABASE=neo4j, because Neo4j Community (the
# free edition used there) only allows the one user database "neo4j".
# ---------------------------------------------------------------------
POSTGRES_DATABASE = os.environ.get("TEST_POSTGRES_DATABASE", "gharchivetest")
NEO4J_DATABASE = os.environ.get("TEST_NEO4J_DATABASE", "gharchivetest")

# The project's real databases. Each load EMPTIES the database first, so
# a test pointed at one of these would wipe the benchmark or the
# pipeline's data. The csv_dir fixture below refuses to use them.
PROTECTED_DATABASES = {"gharchive", "gharchive24h"}

# ---------------------------------------------------------------------
# EVENTS: the test data — 8 made-up events with only the fields
# extract_csv.py reads. They're written straight into the list (no
# make_event helper like in test_extract_csv.py) so all 8 can be read at
# a glance, like a small table.
# ---------------------------------------------------------------------
# Ana (1) and Bea (2) both work on repo 10; Bea also on 20; Carl (3) only on 30.
# Plus the known hard cases: a bot, an empty repo, a repeated pair and a renamed login.
EVENTS = [
    {"actor": {"id": 1, "login": "ana"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:00:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:01:00Z"},
    # The same pair (Bea, repo 20) twice: must become ONE connection.
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 20, "name": "bea/tool"}, "created_at": "2026-08-27T15:02:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 20, "name": "bea/tool"}, "created_at": "2026-08-27T15:03:00Z"},
    # Carl renames himself: the later login, "carl-dev", must be kept.
    {"actor": {"id": 3, "login": "carl"}, "repo": {"id": 30, "name": "carl/notes"}, "created_at": "2026-08-27T15:04:00Z"},
    {"actor": {"id": 3, "login": "carl-dev"}, "repo": {"id": 30, "name": "carl/notes"}, "created_at": "2026-08-27T15:05:00Z"},
    # A bot: must not be loaded.
    {"actor": {"id": 9, "login": "dependabot[bot]"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:06:00Z"},
    # An empty repo ({}), like the 2 real ForkEvents of 2026-10-22: skipped.
    {"actor": {"id": 4, "login": "dan"}, "repo": {}, "created_at": "2026-08-27T15:07:00Z"},
]

# ---------------------------------------------------------------------
# What BOTH databases must hold afterwards, written by hand. They're SETS
# of TUPLES: each tuple is one row, e.g. (1, "ana") = id 1, login "ana".
# A set has no order and no repeats, so comparing two sets with ==
# asks exactly "same rows, ignoring order?" — databases don't promise
# any particular order unless you ask for one (ORDER BY).
# No dependabot (9) and no dan (4); carl appears as "carl-dev"; and
# (2, 20) appears once even though the event was there twice.
# ---------------------------------------------------------------------
EXPECTED_ACTORS = {(1, "ana"), (2, "bea"), (3, "carl-dev")}
EXPECTED_REPOS = {(10, "ana/project"), (20, "bea/tool"), (30, "carl/notes")}
EXPECTED_PAIRS = {(1, 10), (2, 10), (2, 20), (3, 30)}


# A small helper so every Neo4j connection is opened the same way, with
# the same address and user as load_neo4j.py (reused from that module,
# not copied, so they can never drift apart).
def neo4j_driver():
    return GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=(load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"]))


# ---------------------------------------------------------------------
# wait_for_neo4j: in CI, the Neo4j container starts at the same time as
# the job, but takes some seconds before it accepts connections. Without
# waiting, the first test would fail just because it came too early.
#
# The pattern is a RETRY LOOP with a DEADLINE:
#   - time.monotonic() is a clock that only ever moves forward (unlike
#     the wall clock, which can jump if the computer adjusts its time) —
#     the right clock for measuring "how long has passed".
#   - deadline = now + 90 seconds.
#   - `while True:` repeats forever, until a `return` or an error ends it.
#   - try: connect. If it works, `return` — Neo4j is ready.
#   - except Exception: it failed. If the deadline has passed, `raise`
#     with nothing after it RE-RAISES the same error, so the test fails
#     with Neo4j's real message. Otherwise wait 2 s and try again.
# On your computer, with Neo4j already running, it succeeds at once.
# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# ensure_test_databases: create the test databases if they don't exist
# yet (the same idea as ensure_databases() in pipeline.py).
# ---------------------------------------------------------------------
def ensure_test_databases() -> None:
    # PostgreSQL: connect to the always-present "postgres" database (you
    # can't connect to a database that doesn't exist yet), and look it up
    # in the catalogue table pg_database.
    # autocommit=True: CREATE DATABASE is not allowed inside a transaction,
    # and psycopg opens one by default; autocommit runs each statement
    # on its own, immediately.
    # %s with (POSTGRES_DATABASE,) passes the name as a VALUE, safely.
    with psycopg.connect(**load_postgres.POSTGRES_SETTINGS, dbname="postgres", autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (POSTGRES_DATABASE,)).fetchone() is None:
            # A database NAME can't be passed with %s (that's only for
            # values). sql.SQL(...).format(sql.Identifier(name)) inserts
            # it as an identifier, correctly quoted — safe even for odd
            # names, unlike pasting it in with an f-string.
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(POSTGRES_DATABASE)))
    # "neo4j" always exists; any other name needs CREATE DATABASE (Enterprise Edition only).
    # Locally (Enterprise, via Neo4j Desktop) "gharchivetest" is created in
    # the "system" database, where such commands go. IF NOT EXISTS makes it
    # harmless when it already exists; WAIT returns only once it's ready.
    # In CI the name is "neo4j", so this block is skipped — Community
    # Edition would reject CREATE DATABASE.
    if NEO4J_DATABASE != "neo4j":
        with neo4j_driver() as driver:
            driver.execute_query(f"CREATE DATABASE `{NEO4J_DATABASE}` IF NOT EXISTS WAIT", database_="system")


# Run both real loaders on the same CSV folder. Each returns True when its
# counts match the CSV files, so the result is a pair like (True, True).
def load_both(csv_dir: Path) -> tuple[bool, bool]:
    return load_postgres.load(csv_dir, POSTGRES_DATABASE), load_neo4j.load(csv_dir, NEO4J_DATABASE)


# Ask PostgreSQL a question and get the answer as a set of tuples.
# fetchall() already gives a list of tuples, one per row; set(...) drops
# the order so it can be compared with ==.
def postgres_rows(query: str) -> set[tuple]:
    with psycopg.connect(**load_postgres.POSTGRES_SETTINGS, dbname=POSTGRES_DATABASE) as conn:
        return set(conn.execute(query).fetchall())


# The same for Neo4j. **params collects any keyword arguments (e.g.
# id=1) into a dict, which is passed to the query as its $parameters.
# Each record is one result row; record.values() gives its values in the
# order of RETURN, and tuple(...) makes it the same shape as PostgreSQL's
# rows — so both answers can be compared directly.
def neo4j_rows(query: str, **params) -> set[tuple]:
    with neo4j_driver() as driver:
        records, _, _ = driver.execute_query(query, params, database_=NEO4J_DATABASE)
    return {tuple(record.values()) for record in records}


# ---------------------------------------------------------------------
# FIXTURES WITH scope="module"
# By default a fixture is prepared again for EACH test (that's how
# tmp_path gives every unit test its own empty folder). Here that would
# mean loading both databases six times. scope="module" means: prepare
# it ONCE for the whole file (a "module" = one .py file), and give every
# test the same result.
#
# tmp_path_factory: tmp_path is per-test, so a module-wide fixture can't
# use it. tmp_path_factory is its module-friendly sibling:
# .mktemp("integration") creates a new temporary folder on request.
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def csv_dir(tmp_path_factory) -> Path:
    # Safety guard: these tests empty the databases they load into.
    # `assert condition, message`: if the condition is false, stop with
    # that message. {...!r} shows the value with its quotes, e.g.
    # 'gharchive'. This runs before ANY database is touched.
    assert POSTGRES_DATABASE not in PROTECTED_DATABASES, f"refusing to use {POSTGRES_DATABASE!r}"
    assert NEO4J_DATABASE not in PROTECTED_DATABASES, f"refusing to use {NEO4J_DATABASE!r}"

    # Write the 8 events as JSON Lines and run the REAL extract step on
    # them, exactly as the pipeline does — no shortcut.
    folder = tmp_path_factory.mktemp("integration")
    events_file = folder / "events.json"
    events_file.write_text("".join(json.dumps(event) + "\n" for event in EVENTS), encoding="utf-8")
    actors, repos, pairs, _ = extract_csv.extract([events_file])
    extract_csv.write_all(folder, actors, repos, pairs)

    # Make sure both servers are ready to be loaded into.
    wait_for_neo4j()
    ensure_test_databases()
    return folder


# A fixture can ask for another fixture, just like a test does: `loaded`
# receives csv_dir's folder. pytest works out the order by itself
# (csv_dir first, then loaded).
@pytest.fixture(scope="module")
def loaded(csv_dir) -> tuple[bool, bool]:
    # Loaded once and shared by the tests below, which only read.
    return load_both(csv_dir)


# Test 1. Both loaders say their counts match their CSV files.
# `postgres_ok, neo4j_ok = loaded` unpacks the pair into two names.
def test_both_loads_match_their_csv_files(loaded):
    postgres_ok, neo4j_ok = loaded
    assert postgres_ok
    assert neo4j_ok


# Tests 2-4. The heart of it: each database is asked what it holds, and
# BOTH must equal the same hand-written expectation — so they also equal
# each other. Asking for `loaded` (even without using its value) makes
# sure the data was loaded before the test runs.
def test_both_databases_hold_the_same_actors(loaded):
    assert postgres_rows("SELECT id, login FROM actor") == EXPECTED_ACTORS
    assert neo4j_rows("MATCH (a:Actor) RETURN a.id, a.login") == EXPECTED_ACTORS


def test_both_databases_hold_the_same_repos(loaded):
    assert postgres_rows("SELECT id, name FROM repo") == EXPECTED_REPOS
    assert neo4j_rows("MATCH (r:Repo) RETURN r.id, r.name") == EXPECTED_REPOS


def test_both_databases_hold_the_same_connections(loaded):
    assert postgres_rows("SELECT actor_id, repo_id FROM actor_repo") == EXPECTED_PAIRS
    assert neo4j_rows("MATCH (a:Actor)-[:INTERACTED_WITH]->(r:Repo) RETURN a.id, r.id") == EXPECTED_PAIRS


# ---------------------------------------------------------------------
# Test 5. The same TRAVERSAL in both models: a preview of the benchmark.
# Question: who worked on a repo that Ana (id 1) also worked on?
# Path: Ana -> a repo -> another actor = 2 hops.
#
# SQL: a SELF-JOIN — the table actor_repo is used TWICE, under two
# nicknames (aliases): `mine` = Ana's rows, `other` = everyone's rows.
# Joining them ON the same repo_id pairs each of Ana's repos with every
# actor of that repo. `other.actor_id <> 1` removes Ana herself;
# DISTINCT removes repeats (someone sharing two repos with Ana).
# Each extra hop in SQL means one more JOIN.
#
# Cypher: the same path, DRAWN as a pattern:
#   (Ana)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(other)
# The second arrow points LEFT: the other actor also points AT the repo.
# $id is a query parameter, filled from id=1.
#
# Chained comparison: `a == b == c` means `a == b and b == c`. So one
# line checks that both answers agree AND that they're right: {(2,)} —
# Bea. (2,) is a tuple with one element; the comma makes it a tuple.
# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# Test 6. IDEMPOTENCY: doing the same operation twice gives the same
# result as doing it once. Both loaders start by emptying (DROP TABLE /
# DETACH DELETE), so a second load must NOT double the connections.
# This matters for the pipeline, which reloads every hour.
# It needs csv_dir too, to load the same files again.
# {(len(EXPECTED_PAIRS),)} = {(4,)}: count(*) returns one row with one
# value, so the answer is a set holding the tuple (4,).
# ---------------------------------------------------------------------
def test_loading_twice_gives_the_same_result(loaded, csv_dir):
    # Each load starts from empty tables/graph, so a second run must not duplicate anything.
    assert load_both(csv_dir) == (True, True)
    assert postgres_rows("SELECT count(*) FROM actor_repo") == {(len(EXPECTED_PAIRS),)}
    assert neo4j_rows("MATCH ()-[e:INTERACTED_WITH]->() RETURN count(e)") == {(len(EXPECTED_PAIRS),)}
