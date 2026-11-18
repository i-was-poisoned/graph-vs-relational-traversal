########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/traversal.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute. The real, "clean" file (with none of this
# commentary) is scripts/traversal.py. (The real file isn't run on its own
# either: it's a MODULE of shared queries, imported by choose_starts.py
# and measure.py.)
#
# This file assumes you've already read the earlier annotated scripts:
#   check_connections.py   psycopg, the Neo4j driver, os.environ, try/except
#   load_postgres.py       the tables actor, repo, actor_repo, their
#                          indexes, time.perf_counter()
#   load_neo4j.py          Cypher basics (MATCH, patterns, $parameters),
#                          database_=
#   test_integration.py    the 2-hop traversal written as a SQL
#                          SELF-JOIN and as a Cypher pattern
#   pipeline.py            sql.SQL / sql.Identifier, autocommit=True
#   profile_schema.py      RECURSION (a function that calls itself)
#   drop_databases.py      the most recent copy, same style
#
# What's NEW here — this is the HEART of the research:
#   - the "one hop" counts for every actor (used to choose who to start
#     from), in SQL (a self-join + GROUP BY) and in Cypher;
#   - the MEASURED traversal: "how many actors can be reached in at most
#     N hops?", written as a SQL RECURSIVE CTE (WITH RECURSIVE) and as a
#     Cypher QUANTIFIED PATH PATTERN ( ... ){1,N};
#   - a TIME LIMIT on each query (statement_timeout / Query(timeout=));
#   - a @dataclass (Outcome) to return a result in one tidy object;
#   - asking each database HOW MUCH WORK it did: EXPLAIN (ANALYZE, BUFFERS)
#     in PostgreSQL and PROFILE in Neo4j;
#   - the difference between the time the SERVER reports and the time
#     Python measures.
#
# The research question: at what traversal DEPTH, and with how much DATA,
# does Neo4j (a graph database) start beating PostgreSQL (a relational
# one)? This file holds the one question asked to both, written once, so
# both scripts that use it ask exactly the same thing.
#
# How the real file is used (never directly):
#     ./run.sh scripts/choose_starts.py --database <name>
#     ./run.sh scripts/measure.py --database <name> ...
########################################################################

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

# ---------------------------------------------------------------------
# os, time, psycopg, GraphDatabase, sql, load_neo4j: all seen before.
#
# NEW:
#   from dataclasses import dataclass
#       a DECORATOR that writes the boring parts of a small class for
#       you (see Outcome below).
#   from neo4j import ... Query
#       a wrapper around a Cypher string that can carry OPTIONS with it;
#       here the option is a time limit (see run_neo4j_reach()).
# ---------------------------------------------------------------------
import os
import time
from dataclasses import dataclass

import psycopg
from neo4j import GraphDatabase, Query
from psycopg import sql

import load_neo4j

# ---------- ONE_HOP: used to choose the starting actors ----------

# ---------------------------------------------------------------------
# SQL_ONE_HOP — for EVERY actor: how many others it reaches in one hop
# ("reached"), and how many repos it touched ("repos").
#
# WHAT IS ONE HOP? actor -> repo -> another actor. Two actors are one hop
# apart if they share at least one repo. (In test_integration.py the
# same walk was called "2 hops" because it counted each arrow; in the
# research, ONE HOP = one actor-to-actor step = two arrows.)
#
# WITH name AS (...)  — a CTE ("Common Table Expression"): a named,
# temporary result you can then use like a table in the rest of the
# query. Here there are two, separated by a comma: reach and degree.
# It's just a way of writing a big query in readable pieces.
#
# reach — the SELF-JOIN (explained in test_integration.py):
#   actor_repo appears twice, as a1 ("the actor we count for") and a2
#   ("the others"). `a2.repo_id = a1.repo_id` pairs each of a1's rows with
#   every row of the same repo; `a2.actor_id <> a1.actor_id` (<> means
#   "not equal") removes the actor itself.
#   GROUP BY a1.actor_id makes ONE output row per actor; the count is
#   computed inside each group.
#   count(DISTINCT a2.actor_id): someone who shares THREE repos with a1
#   appears in three joined rows, but must be counted once.
#
#   Small example. actor_repo holds (1,R), (2,R), (2,S), (3,S):
#     actor 1: shares R with 2                      -> reached 1
#     actor 2: shares R with 1, S with 3            -> reached 2
#     actor 3: shares S with 2                      -> reached 1
#
# degree — the actor's number of repos ("degree" is the graph word for
#   "how many edges touch this node"). count(*) per actor is enough: the
#   primary key (actor_id, repo_id) guarantees each pair appears once.
#
# The final SELECT puts the pieces side by side:
#   JOIN degree d USING (actor_id)   USING (col) = "join ON the column
#                                    with this name in both tables".
#   JOIN actor a ON a.id = ...       to fetch the login, for display.
#
# Note: an actor that shares no repo with anyone has no row in `reach`
# (the self-join finds nothing for it), so it simply doesn't appear in
# the answer. The Cypher version behaves the same way.
#
# This query runs on the WHOLE table, so it's heavy on big databases —
# that's why choose_starts.py runs it once and saves the result.
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# CYPHER_ONE_HOP — the same question in Cypher.
#
# MATCH (a:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
#   The one-hop walk DRAWN as a pattern (seen in test_integration.py):
#   a points at a repo, and b points at the same repo. Without a fixed
#   start, Neo4j finds this pattern for EVERY actor a.
# WHERE a <> b       same as the SQL's "not the actor itself".
#
# WITH a, count(DISTINCT b) AS reached
#   In Cypher, WITH is a "pipe" between two parts of a query: only what's
#   listed continues. Putting an aggregate (count) next to `a` GROUPS by a
#   — Cypher has no GROUP BY keyword: everything that isn't an aggregate
#   is the grouping key. So: one row per actor, with its count.
#
# MATCH (a)-[:INTERACTED_WITH]->(r:Repo)
#   Second step, starting again from each a: its repos.
# RETURN a.id AS actor_id, a.login AS login, reached, count(r) AS repos
#   Again an aggregate (count(r)) groups by everything else in the RETURN.
#   count(r) counts edges; the loader created one edge per actor-repo
#   pair, so it's the number of repos. The AS names are the SAME as the
#   SQL's column names, so choose_starts.py can compare the two answers
#   key by key.
# ---------------------------------------------------------------------
CYPHER_ONE_HOP = """
MATCH (a:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
WHERE a <> b
WITH a, count(DISTINCT b) AS reached
MATCH (a)-[:INTERACTED_WITH]->(r:Repo)
RETURN a.id AS actor_id, a.login AS login, reached, count(r) AS repos
"""

# ---------- REACH: the measured traversal ----------

# ---------------------------------------------------------------------
# SQL_REACH — a RECURSIVE CTE
#
# The question: starting from ONE actor, how many distinct other actors
# can be reached in AT MOST N hops? With plain JOINs you'd need one more
# pair of JOINs per hop, so a different query for each depth. A
# RECURSIVE CTE writes "one more hop" ONCE and lets PostgreSQL repeat it.
#
# WITH RECURSIVE reach(actor_id, depth) AS ( <anchor> UNION <recursive part> )
#   reach is a table PostgreSQL builds step by step; each row is
#   (an actor found, at which depth).
#
#   1. THE ANCHOR (the part before UNION) runs ONCE and gives the
#      starting row:
#          SELECT %(start)s::bigint, 0      -> (start actor, depth 0)
#      %(start)s is a NAMED PARAMETER: psycopg fills it from the dict
#      {"start": ..., "depth": ...} passed with the query, safely (no
#      text pasting). ::bigint is a CAST ("treat this as a BIGINT"), so
#      the anchor's column has the same type as actor_repo.actor_id.
#
#   2. THE RECURSIVE PART (after UNION) refers to reach ITSELF. It runs
#      on the rows produced by the PREVIOUS step only, and its new rows
#      become the input of the next step:
#          FROM reach r                                     the actors found last step
#          JOIN actor_repo ar1 ON ar1.actor_id = r.actor_id their repos
#          JOIN actor_repo ar2 ON ar2.repo_id = ar1.repo_id everyone on those repos
#          SELECT ar2.actor_id, r.depth + 1                 = found one hop further
#      (These two joins are exactly the one-hop self-join above; the two
#      indexes built by load_postgres.py — actor_id first, and repo_id —
#      serve the two directions.)
#
#   3. It STOPS when a step produces no new rows.
#
#   Example, start = 1, with (1,R), (2,R), (2,S), (3,S) and N = 2:
#     anchor  -> (1, 0)
#     step 1  -> (1, 1), (2, 1)              1's repo R has actors 1 and 2
#     step 2  -> (1, 2), (2, 2), (3, 2)      from 1 and 2: repos R, S
#     stop (depth 2 = N)
#   Final count: distinct actors except 1 -> {2, 3} -> 2.
#
# WHY UNION AND NOT UNION ALL? UNION throws away any row that's an exact
# DUPLICATE of a row already found. Since a row is (actor, depth), an
# actor reached by 50 different paths at depth 2 is kept ONCE at depth 2.
# Each level therefore holds at most one row per actor — never one row
# per PATH. That matters: the number of paths explodes with depth (every
# popular repo multiplies them), the number of actors can't.
# (It does NOT remove an actor found at depth 1 from depth 2, because
# (2, 1) and (2, 2) are different rows. That's why the final SELECT uses
# DISTINCT.)
#
# WHY THE DEPTH LIMIT (WHERE r.depth < %(depth)s)? Two reasons:
#   - it's the N of the question ("in at most N hops");
#   - without it the query would NEVER END: each step adds depth + 1, so
#     every row is new (a different depth), and the graph has cycles
#     (A -> repo -> B -> repo -> A...). The limit is what stops it.
#
# The final line: count(DISTINCT actor_id) over all the levels, without
# the start actor itself (<> %(start)s).
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# CYPHER_REACH — a QUANTIFIED PATH PATTERN (Neo4j 5.9 and later)
#
# Once the Python formatting below has been applied, the query reads (for N = 3):
#
#   MATCH (a:Actor {id: $start})
#         ((:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(:Actor)){1,3}
#         (b:Actor)
#   WHERE b <> a
#   RETURN count(DISTINCT b)
#
#   (a:Actor {id: $start})   the start: the Actor node whose id property
#                            equals the parameter $start.
#   ( ...one hop... ){1,3}   the part in brackets is ONE hop
#                            (actor -> repo <- actor), and {1,3} is a
#                            QUANTIFIER: "repeat this 1 to 3 times", like
#                            {1,3} in a regular expression. The last
#                            actor of one repetition is the first of the
#                            next, and the first one is `a` itself.
#   (b:Actor)                the actor where the path ends.
#   count(DISTINCT b)        how many different end actors.
#
# Compare with SQL: the hop is drawn once and repeated, just like the
# recursive part of the CTE — but the thinking is different. Cypher's
# MATCH looks for PATHS (in one path, the same edge can't be used twice)
# and DISTINCT removes repeated end actors only at the END; the SQL removes
# repeats at EVERY level. Both give the same set of actors; how much work
# each needs to get there is exactly what the research measures.
#
# WHY THE DEPTH IS WRITTEN INTO THE TEXT: Cypher only accepts a literal
# number inside {1,N}, not a $parameter. So the query is a TEMPLATE, and
# Python's str.format() writes the number in (see cypher_reach()). In a
# format template, {depth} is a gap to fill, and a DOUBLED brace {{ or }}
# means "a real brace, not a gap". So:
#   {{id: $start}}      becomes   {id: $start}
#   {{1,{depth}}}       becomes   {1,3}       (with depth=3)
# $start stays a normal parameter, filled by the driver.
# ---------------------------------------------------------------------
# A quantified path pattern: the group in brackets (one hop, actor -> repo -> actor) is
# repeated from 1 to N times. N can't be a query parameter, so it's written into the text.
CYPHER_REACH = """
MATCH (a:Actor {{id: $start}})
      ((:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(:Actor)){{1,{depth}}}
      (b:Actor)
WHERE b <> a
RETURN count(DISTINCT b)
"""


# ---------------------------------------------------------------------
# def cypher_reach(depth) -> str:
#
# Fills the template. Because the depth goes into the query TEXT (not a
# safe parameter), it's checked first: {1,0} would be meaningless, so a
# depth below 1 raises a ValueError instead of sending a broken query.
# ---------------------------------------------------------------------
def cypher_reach(depth: int) -> str:
    if depth < 1:
        raise ValueError("depth must be at least 1")
    return CYPHER_REACH.format(depth=depth)


# ---------- running a query, with a time limit, on either side ----------

# ---------------------------------------------------------------------
# @dataclass  class Outcome — the result of ONE timed run.
#
# A class (explained in summarize_data.py) normally needs an __init__
# method that copies every argument into self. @dataclass is a DECORATOR
# (the @ line just above a class or function, which adds behaviour to
# it): from the list of annotated fields below, it WRITES that __init__
# for you, plus a readable print-out (__repr__) and an == comparison.
# So Outcome("ok", 0.42, 1234) creates an object with .status = "ok",
# .seconds = 0.42, .count = 1234 and .error = "".
#
# The fields:
#   status   "ok", "timeout" or "error" — one word, easy to count later.
#   seconds  the time measured from Python (see run_postgres_reach()).
#   count    the answer; `int | None` = an int, or None when the query
#            didn't finish (so no answer exists — None, not 0, because 0
#            would be a real, wrong answer).
#   error    = "" is a DEFAULT value: it can be left out, as on success.
#            Fields with defaults must come after those without.
#
# Why a dataclass and not a tuple? outcome.status reads better than
# outcome[0], and a mistake in a field name is an error, not a silent
# wrong position.
# ---------------------------------------------------------------------
@dataclass
class Outcome:
    status: str            # "ok", "timeout" or "error"
    seconds: float         # wall-clock time seen from Python
    count: int | None      # the answer (None if it didn't finish)
    error: str = ""        # the error message, if any


# ---------------------------------------------------------------------
# Two connection helpers, so the connection details live in one place.
#
# connect_postgres: autocommit=True (seen in pipeline.py) here for a new
# reason: each query is its own transaction. If one is cancelled by the
# time limit, a normal transaction would stay "aborted" and refuse every
# later command on that connection; with autocommit the next measurement
# can simply carry on. The `-> psycopg.Connection` hint names the type
# returned.
#
# connect_neo4j: the same driver as in check_connections.py, with the
# address and user reused from load_neo4j.py.
# ---------------------------------------------------------------------
def connect_postgres(database: str) -> psycopg.Connection:
    return psycopg.connect(host="localhost", user="postgres", dbname=database, autocommit=True)


def connect_neo4j():
    return GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=(load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"]))


# ---------------------------------------------------------------------
# def run_postgres_reach(conn, start, depth, timeout_s) -> Outcome:
#
# THE TIME LIMIT: SET statement_timeout = '60s'
#   A PostgreSQL setting for this connection: any statement still running
#   after that long is CANCELLED by the server itself. Deep traversals
#   can take hours; the research needs to say "didn't finish within the
#   limit" instead of waiting forever.
#   SET doesn't accept a %s parameter, so the value is built with
#   sql.Literal(...), which quotes it correctly as '60s' (the sql.SQL
#   family was explained in pipeline.py). f"{timeout_s}s" turns 60 into
#   the text "60s".
#
# THE TIMING: begin = time.perf_counter() just before the query; the
# difference afterwards is the WALL-CLOCK time seen from Python: sending
# the query, the server's work, and the answer coming back. (The time
# the SERVER says it spent is collected separately, in postgres_work().)
#
# THE QUERY: conn.execute(SQL_REACH, {"start": ..., "depth": ...}) fills
# the %(start)s and %(depth)s gaps from the dict. fetchone()[0]: the one
# row, its one column — the count.
#
# THREE ENDINGS, one Outcome each:
#   ok        the count, and the time.
#   timeout   psycopg.errors.QueryCanceled is the error PostgreSQL sends
#             when statement_timeout cancels the query.
#   error     any other database error (psycopg.Error is the parent of
#             all psycopg errors, QueryCanceled included).
#   The ORDER of the `except` lines matters: Python uses the first one
#   that matches, so the specific QueryCanceled must come before its
#   parent psycopg.Error, or a timeout would be labelled "error".
#   str(error).strip(): the message as text, without the trailing newline.
# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# def run_neo4j_reach(driver, database, start, depth, timeout_s) -> Outcome:
#
# The same job on the Neo4j side.
#
# driver.session(database=database)
#   Until now we used driver.execute_query(), a one-call shortcut. A
#   SESSION is the longer form: a "conversation" with one database, opened
#   with `with` (so it's closed afterwards), in which session.run() sends
#   a query. We need it because of the next point.
#
# Query(cypher_reach(depth), timeout=timeout_s)
#   Wraps the query text together with a TIME LIMIT in seconds. The Neo4j
#   SERVER stops the query's transaction once the limit is passed — the
#   equivalent of statement_timeout.
#   start=start is the value of $start.
#
# .single()[0]: the answer must be exactly ONE record (single() complains
# otherwise); [0] is its first column, the count.
#
# The `except` is broad (Exception) on purpose, as the comment says:
# depending on the moment and the driver version, a timeout arrives as
# different error classes. So the decision is made on the MESSAGE:
#   "timeout" in str(error).lower()   is the word in the message (lower()
#                                     so "Timeout" and "TIMEOUT" match too)?
#   X if condition else Y             a CONDITIONAL EXPRESSION: a one-line
#                                     if/else that gives a value.
# [:300] keeps only the first 300 characters of a possibly huge message.
# ---------------------------------------------------------------------
def run_neo4j_reach(driver, database: str, start: int, depth: int, timeout_s: int) -> Outcome:
    begin = time.perf_counter()
    try:
        with driver.session(database=database) as session:
            count = session.run(Query(cypher_reach(depth), timeout=timeout_s), start=start).single()[0]
        return Outcome("ok", time.perf_counter() - begin, count)
    except Exception as error:   # the driver raises different classes for a timeout
        status = "timeout" if "timeout" in str(error).lower() or "timed out" in str(error).lower() else "error"
        return Outcome(status, time.perf_counter() - begin, None, str(error).strip()[:300])


# ---------- the work done inside each database ----------

# ---------------------------------------------------------------------
# def postgres_work(conn, start, depth, timeout_s) -> dict:
#
# TIME isn't the only thing worth measuring: it depends on the computer
# and on what else is running. HOW MUCH WORK the database did (how many
# pieces of data it touched, from memory or from disk) explains WHY one
# side is faster. measure.py calls this once per depth, as an extra run
# AFTER the timed ones, because measuring the work slows a query down a
# little and mustn't spoil the timings.
#
# EXPLAIN shows the PLAN PostgreSQL chose for a query (which index, which
# join method...). The options in brackets:
#   ANALYZE      actually RUN the query, and report real numbers instead
#                of estimates. (Not the same as the ANALYZE command of
#                load_postgres.py, which refreshes statistics.)
#   BUFFERS      also report the BLOCKS used. PostgreSQL stores tables
#                and indexes in blocks of 8 kB, and keeps recently used
#                blocks in memory ("shared buffers").
#   FORMAT JSON  give the report as JSON, so Python can read figures by
#                name instead of parsing text.
#
# .fetchone()[0][0]: the report is one row with one column holding a JSON
# LIST (psycopg turns it into a Python list); [0] is its only element, a
# dict. plan["Plan"] is the TOP node of the plan tree, i.e. the last step,
# whose numbers already include all the steps below it (no need to add
# them up — unlike Neo4j below).
#
# The figures kept (dict.get() returns None if a key is missing):
#   server_ms            "Execution Time": milliseconds spent inside the
#                        server running the query (without planning, and
#                        without sending the answer to Python).
#   blocks_from_memory   "Shared Hit Blocks": blocks already in memory.
#   blocks_from_disk     "Shared Read Blocks": blocks PostgreSQL had to
#                        read from a file (from disk — or from Windows'
#                        own file cache, which PostgreSQL can't tell apart).
#   temp_blocks_written  "Temp Written Blocks": blocks written to TEMPORARY
#                        files because the work didn't fit in the memory
#                        allowed for one step (the work_mem setting) — e.g.
#                        a huge intermediate result of the recursive CTE.
#                        A sign the query is outgrowing memory.
# The same time limit is set first, as this is a full run of the query.
# ---------------------------------------------------------------------
def postgres_work(conn: psycopg.Connection, start: int, depth: int, timeout_s: int) -> dict:
    # EXPLAIN (ANALYZE, BUFFERS) runs the query and reports what it did. The top node's
    # buffer numbers include everything below it.
    conn.execute(sql.SQL("SET statement_timeout = {}").format(sql.Literal(f"{timeout_s}s")))
    query = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + SQL_REACH
    plan = conn.execute(query, {"start": start, "depth": depth}).fetchone()[0][0]
    top = plan["Plan"]
    return {
        "server_ms": plan.get("Execution Time"),
        "blocks_from_memory": top.get("Shared Hit Blocks"),
        "blocks_from_disk": top.get("Shared Read Blocks"),
        "temp_blocks_written": top.get("Temp Written Blocks"),
    }


# ---------------------------------------------------------------------
# def _sum_profile(node, key) -> int:
#
# A Neo4j plan is a TREE of steps ("operators"), each a dict with its own
# figures and a list of "children" (the steps feeding it). Unlike
# PostgreSQL's, each Neo4j step reports only ITS OWN work, so the total
# is the sum over the whole tree. This function walks it RECURSIVELY
# (recursion: profile_schema.py):
#   this node's value  +  the sum of _sum_profile(child) for each child
# A node with no children: node.get("children", []) gives an empty list,
# the sum of nothing is 0, and the recursion stops there.
# `node.get(key) or 0` turns a missing value (None) into 0.
# The leading underscore in the name is a convention: "internal helper,
# not meant to be used from other files".
# ---------------------------------------------------------------------
def _sum_profile(node: dict, key: str) -> int:
    return (node.get(key) or 0) + sum(_sum_profile(child, key) for child in node.get("children", []))


# ---------------------------------------------------------------------
# def neo4j_work(driver, database, start, depth, timeout_s) -> dict:
#
# PROFILE in front of a Cypher query = Neo4j's EXPLAIN ANALYZE: it RUNS
# the query and records, for every step of its plan, what it did.
#
# result.consume() reads the result to the end and returns its SUMMARY
# (the metadata, not the rows). summary.profile is the plan tree as a
# dict (or None if there's none, hence `or {}`).
#
# The figures kept:
#   server_ms          result_available_after (ms until the first record
#                      was ready) + result_consumed_after (ms to deliver
#                      the rest): the time spent inside the server.
#   db_hits            "database hits": Neo4j's unit of storage work —
#                      roughly one per node, relationship or property
#                      looked up. The closest thing to "rows touched".
#   page_cache_hits    Neo4j's PAGE CACHE is its equivalent of
#   page_cache_misses  PostgreSQL's shared buffers: a hit = the data page
#                      was in memory, a miss = it had to be read from disk.
#   memory_bytes       "GlobalMemory": the peak memory the query needed,
#                      found in the top step's arguments. The key holding
#                      the arguments is "args" in some driver versions and
#                      "arguments" in others, so both are tried
#                      (`A or B or {}` = the first one that isn't empty).
#
# SERVER TIME vs PYTHON TIME — both are recorded on purpose:
#   - the Outcome's `seconds` (measured in Python) is what a USER of the
#     database would wait: it includes the network, the driver, and
#     turning the answer into Python objects;
#   - server_ms is only the database's own work.
#   The gap between them is overhead that has nothing to do with the
#   data model; comparing the server times keeps that overhead out of the
#   PostgreSQL-vs-Neo4j comparison.
# ---------------------------------------------------------------------
def neo4j_work(driver, database: str, start: int, depth: int, timeout_s: int) -> dict:
    # PROFILE runs the query and reports, for every step of its plan, the database hits
    # and the page cache hits/misses; they're added up over the whole plan.
    with driver.session(database=database) as session:
        result = session.run(Query("PROFILE " + cypher_reach(depth), timeout=timeout_s), start=start)
        summary = result.consume()
    profile = summary.profile or {}
    arguments = profile.get("args") or profile.get("arguments") or {}
    return {
        "server_ms": summary.result_available_after + summary.result_consumed_after,
        "db_hits": _sum_profile(profile, "dbHits"),
        "page_cache_hits": _sum_profile(profile, "pageCacheHits"),
        "page_cache_misses": _sum_profile(profile, "pageCacheMisses"),
        "memory_bytes": arguments.get("GlobalMemory"),
    }
