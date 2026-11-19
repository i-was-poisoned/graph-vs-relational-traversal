"""The research queries, the same question asked to PostgreSQL (SQL) and to Neo4j (Cypher).

Used by choose_starts.py and measure.py; it isn't run by itself.

Two questions:

* ONE_HOP: for every actor, how many distinct OTHER actors share at least one
  repo with it ("reached in one hop"), and how many distinct repos it touched.
  This chooses the starting actors.

* REACH: from one starting actor, how many distinct other actors can be
  reached in at most N hops, one hop being actor -> repo -> actor. This is the
  traversal that is measured.

Both databases must give exactly the same numbers; measure.py checks it every time.
"""

import os
import time
from dataclasses import dataclass

import psycopg
from neo4j import GraphDatabase, Query
from psycopg import sql

import load_neo4j

# ---------- ONE_HOP: used to choose the starting actors ----------

SQL_ONE_HOP = """
WITH reach AS (
    SELECT a1.actor_id, count(DISTINCT a2.actor_id) AS reached
    FROM actor_repo a1
    JOIN actor_repo a2 ON a2.repo_id = a1.repo_id AND a2.actor_id <> a1.actor_id
    GROUP BY a1.actor_id
), degree AS (
    SELECT actor_id, count(*) AS repos FROM actor_repo GROUP BY actor_id
)
SELECT r.actor_id, a.login, r.reached, d.repos
FROM reach r
JOIN degree d USING (actor_id)
JOIN actor a ON a.id = r.actor_id
"""

CYPHER_ONE_HOP = """
MATCH (a:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
WHERE a <> b
WITH a, count(DISTINCT b) AS reached
MATCH (a)-[:INTERACTED_WITH]->(r:Repo)
RETURN a.id AS actor_id, a.login AS login, reached, count(r) AS repos
"""

# ---------- REACH: the measured traversal ----------

# Level by level: each row is (actor, depth). UNION drops a row already found at that
# depth, so every level holds at most one row per actor, never one row per path.
SQL_REACH = """
WITH RECURSIVE reach(actor_id, depth) AS (
    SELECT %(start)s::bigint, 0
    UNION
    SELECT ar2.actor_id, r.depth + 1
    FROM reach r
    JOIN actor_repo ar1 ON ar1.actor_id = r.actor_id
    JOIN actor_repo ar2 ON ar2.repo_id  = ar1.repo_id
    WHERE r.depth < %(depth)s
)
SELECT count(DISTINCT actor_id) FROM reach WHERE actor_id <> %(start)s
"""

# Two ways of asking the same question in Cypher (both must give the SQL's count):
#
# "paths"   A quantified path pattern: the group in brackets (one hop, actor -> repo ->
#           actor) is repeated from 1 to N times. Neo4j follows every PATH and removes
#           repeated actors only at the end, so the work grows with the number of paths.
# "levels"  Level by level, like the SQL: each step starts from the actors found in the
#           step before (the "frontier") and keeps only actors never seen before.
#
# N can't be a query parameter, so it's written into the text.
CYPHER_VERSIONS = ("paths", "levels")

CYPHER_REACH_PATHS = """
MATCH (a:Actor {{id: $start}})
      ((:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(:Actor)){{1,{depth}}}
      (b:Actor)
WHERE b <> a
RETURN count(DISTINCT b)
"""

CYPHER_LEVELS_START = """
MATCH (start:Actor {id: $start})
WITH [start] AS seen, [start] AS frontier
"""

CYPHER_LEVELS_STEP = """
CALL (seen, frontier) {
    UNWIND frontier AS a
    MATCH (a)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
    WITH DISTINCT b
    WHERE NOT b IN seen
    RETURN collect(b) AS next
}
WITH seen + next AS seen, next AS frontier
"""

CYPHER_LEVELS_END = """
RETURN size(seen) - 1
"""


def cypher_reach(depth: int, version: str = "paths") -> str:
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if version == "paths":
        return CYPHER_REACH_PATHS.format(depth=depth)
    if version == "levels":
        return CYPHER_LEVELS_START + CYPHER_LEVELS_STEP * depth + CYPHER_LEVELS_END
    raise ValueError(f"unknown Cypher version {version!r}: use one of {CYPHER_VERSIONS}")


def sql_joins(depth: int) -> int:
    # Each hop of the recursive part joins actor_repo twice (actor -> repo, repo -> actor),
    # and the recursive part runs once per hop.
    return 2 * depth


def cypher_hops(depth: int) -> int:
    # Each hop follows two relationships: (actor)-[:INTERACTED_WITH]->(repo)<-[:INTERACTED_WITH]-(actor).
    return 2 * depth


# ---------- running a query, with a time limit, on either side ----------

@dataclass
class Outcome:
    status: str            # "ok", "timeout" or "error"
    seconds: float         # wall-clock time seen from Python
    count: int | None      # the answer (None if it didn't finish)
    error: str = ""        # the error message, if any


def connect_postgres(database: str) -> psycopg.Connection:
    return psycopg.connect(host="localhost", user="postgres", dbname=database, autocommit=True)


def connect_neo4j():
    return GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=(load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"]))


def run_postgres_reach(conn: psycopg.Connection, start: int, depth: int, timeout_s: int) -> Outcome:
    conn.execute(sql.SQL("SET statement_timeout = {}").format(sql.Literal(f"{timeout_s}s")))
    begin = time.perf_counter()
    try:
        count = conn.execute(SQL_REACH, {"start": start, "depth": depth}).fetchone()[0]
        return Outcome("ok", time.perf_counter() - begin, count)
    except psycopg.errors.QueryCanceled as error:
        return Outcome("timeout", time.perf_counter() - begin, None, str(error).strip())
    except psycopg.Error as error:
        return Outcome("error", time.perf_counter() - begin, None, str(error).strip())


def run_neo4j_reach(driver, database: str, start: int, depth: int, timeout_s: int, version: str = "paths") -> Outcome:
    begin = time.perf_counter()
    try:
        with driver.session(database=database) as session:
            count = session.run(Query(cypher_reach(depth, version), timeout=timeout_s), start=start).single()[0]
        return Outcome("ok", time.perf_counter() - begin, count)
    except Exception as error:   # the driver raises different classes for a timeout
        status = "timeout" if "timeout" in str(error).lower() or "timed out" in str(error).lower() else "error"
        return Outcome(status, time.perf_counter() - begin, None, str(error).strip()[:300])


# ---------- the work done inside each database ----------

PAGE_MB = 8192 / 1024 ** 2   # both databases read and cache data in pages of 8 KB


def _postgres_memory_kb(node: dict) -> float:
    # The memory each step of the plan kept for itself (PostgreSQL 18 reports it in kB):
    # "Maximum Storage" (recursive union, CTE scan), "Sort Space Used", "Peak Memory Usage"
    # (hash tables). Only what stayed in memory; what went to disk is counted as temp.
    own = 0.0
    if node.get("Storage", "Memory") == "Memory":
        own += node.get("Maximum Storage") or 0
    if node.get("Sort Space Type", "Memory") == "Memory":
        own += node.get("Sort Space Used") or 0
    own += node.get("Peak Memory Usage") or 0
    return own + sum(_postgres_memory_kb(child) for child in node.get("Plans", []))


def postgres_work(conn: psycopg.Connection, start: int, depth: int, timeout_s: int) -> dict:
    # EXPLAIN (ANALYZE, BUFFERS) runs the query and reports what it did. The top node's
    # buffer numbers include everything below it.
    conn.execute(sql.SQL("SET statement_timeout = {}").format(sql.Literal(f"{timeout_s}s")))
    query = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + SQL_REACH
    plan = conn.execute(query, {"start": start, "depth": depth}).fetchone()[0][0]
    top = plan["Plan"]
    from_memory, from_disk = top.get("Shared Hit Blocks") or 0, top.get("Shared Read Blocks") or 0
    return {
        "data_processed_mb": (from_memory + from_disk) * PAGE_MB,
        "data_from_disk_mb": from_disk * PAGE_MB,
        "memory_mb": _postgres_memory_kb(top) / 1024,
        "temp_disk_mb": (top.get("Temp Written Blocks") or 0) * PAGE_MB,
    }


def _sum_profile(node: dict, key: str) -> int:
    return (node.get(key) or 0) + sum(_sum_profile(child, key) for child in node.get("children", []))


def neo4j_work(driver, database: str, start: int, depth: int, timeout_s: int, version: str = "paths") -> dict:
    # PROFILE runs the query and reports, for every step of its plan, the page cache
    # hits/misses; they're added up over the whole plan. GlobalMemory is the memory the
    # whole query used.
    with driver.session(database=database) as session:
        result = session.run(Query("PROFILE " + cypher_reach(depth, version), timeout=timeout_s), start=start)
        summary = result.consume()
    profile = summary.profile or {}
    arguments = profile.get("args") or profile.get("arguments") or {}
    hits, misses = _sum_profile(profile, "pageCacheHits"), _sum_profile(profile, "pageCacheMisses")
    memory = arguments.get("GlobalMemory")
    return {
        "data_processed_mb": (hits + misses) * PAGE_MB,
        "data_from_disk_mb": misses * PAGE_MB,
        "memory_mb": memory / 1024 ** 2 if memory is not None else None,
    }
