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
#     N hops?", written as a SQL RECURSIVE CTE (WITH RECURSIVE) and in
#     TWO Cypher versions: "paths" (a QUANTIFIED PATH PATTERN ( ... ){1,N})
#     and "levels" (level by level like the SQL, with CALL { ... },
#     UNWIND, collect() and lists);
#   - sql_joins() / cypher_hops(): how many joins / relationships one
#     depth means on each side;
#   - a TIME LIMIT on each query (statement_timeout / Query(timeout=));
#   - a @dataclass (Outcome) to return a result in one tidy object;
#   - asking each database HOW MUCH WORK it did: EXPLAIN (ANALYZE, BUFFERS)
#     in PostgreSQL and PROFILE in Neo4j, turned into figures that can be
#     compared: MB of 8 KB pages processed, and MB of memory used.
#
# The research question: at what traversal DEPTH, and with how much DATA,
# does Neo4j (a graph database) start beating PostgreSQL (a relational
# one)? This file holds the one question asked to both, written once, so
# both scripts that use it ask exactly the same thing.
#
# How the real file is used (never directly: measure.py imports it, and
# so does choose_starts.py, which measure.py calls):
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
# that's why it runs only when the starting actors are CHOSEN. The chosen
# actors are written into every line of the measurement's CSV file in
# results/, and later measurements of the same database reuse them from
# the latest one (see previous_starts in docs_english/measure.py).
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
# TWO CYPHER VERSIONS OF THE SAME QUESTION — WHY?
#
# The first measurements used only the "paths" version below, and on 24
# hours of data it EXPLODED at depth 5-6 (it ran out of time) while the
# SQL didn't. Was that because of the DATABASE, or because of HOW the
# Cypher query was WRITTEN? To tell the two apart, the same question is
# also asked a second way, "levels", that follows the SQL's strategy:
#   paths    Neo4j's natural way: describe the walk as a pattern.
#   levels   the SQL's level-by-level strategy, written in Cypher.
# If "levels" stays fast where "paths" explodes, the problem was the way
# the query was written, not Neo4j itself. measure.py measures both (or
# one, with --cypher) and writes one results CSV line per version; both
# must give exactly the SQL's count.
#
# CYPHER_VERSIONS = ("paths", "levels"): the two names, in one tuple, used
# by measure.py (the choices of --cypher) and checked by cypher_reach().
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# CYPHER_REACH_PATHS — "paths": a QUANTIFIED PATH PATTERN (Neo4j 5.9 and later)
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
# repeats at EVERY level. Both give the same set of actors, but here the
# work grows with the number of PATHS, and that number multiplies at
# every hop (every popular repo opens dozens of new paths): that's what
# exploded at depth 5-6 on 24 hours of data.
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
CYPHER_REACH_PATHS = """
MATCH (a:Actor {{id: $start}})
      ((:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(:Actor)){{1,{depth}}}
      (b:Actor)
WHERE b <> a
RETURN count(DISTINCT b)
"""

# ---------------------------------------------------------------------
# "levels": THREE PIECES, GLUED TOGETHER BY cypher_reach()
#
# The idea is the SQL's: keep two LISTS of actors and go one level at a
# time.
#   seen       every actor found so far (the start included)
#   frontier   the actors found at the LAST level only: the next hop
#              starts from them, not from everyone again
# For depth 3 the query is START + STEP + STEP + STEP + END.
#
# CYPHER_LEVELS_START
#   MATCH (start:Actor {id: $start})     find the starting actor.
#   WITH [start] AS seen, [start] AS frontier
#       [x] is a Cypher LIST with one element. WITH passes the two lists
#       on to the rest of the query (WITH: see CYPHER_ONE_HOP above).
#   There's no .format() on this piece, so the braces stay single.
# ---------------------------------------------------------------------
CYPHER_LEVELS_START = """
MATCH (start:Actor {id: $start})
WITH [start] AS seen, [start] AS frontier
"""

# ---------------------------------------------------------------------
# CYPHER_LEVELS_STEP — ONE hop, repeated once per level
#
# CALL (seen, frontier) { ... }
#   A SUBQUERY: a small query run inside the big one. The brackets after
#   CALL say which variables it may use from outside (here the two
#   lists). Its RETURN gives its result back to the outer query. (This
#   is a different use of CALL from `CALL dbms.components()` in
#   check_connections.py, which calls a built-in procedure.)
#
# Inside:
#   UNWIND frontier AS a      one row per actor of the frontier (UNWIND:
#                             docs_english/load_neo4j.py).
#   MATCH (a)-...->(:Repo)<-...-(b:Actor)
#                             the one hop, from each of those actors.
#   WITH DISTINCT b           keep each actor found ONCE, however many
#                             paths led to it — like the SQL's UNION. This
#                             is THE difference with "paths": repeats are
#                             removed at every level, not only at the end.
#   WHERE NOT b IN seen       `x IN list` is True if x is in the list:
#                             drop the actors already found at an earlier
#                             level.
#   RETURN collect(b) AS next collect() is an aggregate (like count) that
#                             gathers all the rows' values into ONE list:
#                             the new actors of this level.
#
# After the subquery:
#   WITH seen + next AS seen, next AS frontier
#       `+` between two lists JOINS them: seen grows by the new actors,
#       and the new actors become the next frontier.
#
# Python then repeats this text `depth` times (see cypher_reach()). If a
# level finds nobody new, next is an empty list and the following steps
# simply add nothing.
# ---------------------------------------------------------------------
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

# CYPHER_LEVELS_END — size(list) is its number of elements. `seen` holds
# every actor reached, PLUS the start itself, hence - 1: the same number
# as the SQL's count (which leaves the start out with <> %(start)s).
CYPHER_LEVELS_END = """
RETURN size(seen) - 1
"""


# ---------------------------------------------------------------------
# def cypher_reach(depth, version="paths") -> str:
#
# Builds the Cypher text for one depth and one version.
#   version: str = "paths"   a DEFAULT value: cypher_reach(3) still means
#                            the "paths" version.
#
# Because the depth goes into the query TEXT (not a safe parameter), it's
# checked first: {1,0} would be meaningless, so a depth below 1 raises a
# ValueError instead of sending a broken query.
#
#   "paths"    fills the template with str.format() (see above).
#   "levels"   glues the pieces: START, then STEP `depth` times, then END.
#              `text * 3` REPEATS a string: "ab" * 3 == "ababab".
#   anything else: a ValueError. {version!r} in an f-string shows the
#              value with repr(), i.e. WITH its quotes ('shortcut'), so
#              the message makes clear what was received.
# tests/test_research.py checks all three cases.
# ---------------------------------------------------------------------
def cypher_reach(depth: int, version: str = "paths") -> str:
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if version == "paths":
        return CYPHER_REACH_PATHS.format(depth=depth)
    if version == "levels":
        return CYPHER_LEVELS_START + CYPHER_LEVELS_STEP * depth + CYPHER_LEVELS_END
    raise ValueError(f"unknown Cypher version {version!r}: use one of {CYPHER_VERSIONS}")


# ---------------------------------------------------------------------
# sql_joins(depth) / cypher_hops(depth) — "HOW MUCH WALKING" ONE DEPTH IS
#
# Two small numbers written on every line of the results CSV, so a reader
# can see what a depth means on each side:
#   sql_joins     one hop = actor_repo joined twice (actor -> its repos,
#                 repo -> its actors); the recursive part runs once per
#                 hop. Depth 3 -> 6 joins.
#   cypher_hops   one hop = two INTERACTED_WITH relationships followed
#                 (actor -> repo, repo <- actor). Depth 3 -> 6.
# Both are 2 x depth: the same walk, counted in each database's own
# units. (Tested in tests/test_research.py.)
# ---------------------------------------------------------------------
def sql_joins(depth: int) -> int:
    # Each hop of the recursive part joins actor_repo twice (actor -> repo, repo -> actor),
    # and the recursive part runs once per hop.
    return 2 * depth


def cypher_hops(depth: int) -> int:
    # Each hop follows two relationships: (actor)-[:INTERACTED_WITH]->(repo)<-[:INTERACTED_WITH]-(actor).
    return 2 * depth


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
# the query, the server's work, and the answer coming back — the time a
# USER of the database would wait. measure.py takes the MEDIAN of several
# such times (the time_s columns of the results CSV).
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
# def run_neo4j_reach(driver, database, start, depth, timeout_s, version="paths") -> Outcome:
#
# The same job on the Neo4j side. `version` says which Cypher version to
# run ("paths" or "levels", see cypher_reach()); measure.py passes it.
#
# driver.session(database=database)
#   Until now we used driver.execute_query(), a one-call shortcut. A
#   SESSION is the longer form: a "conversation" with one database, opened
#   with `with` (so it's closed afterwards), in which session.run() sends
#   a query. We need it because of the next point.
#
# Query(cypher_reach(depth, version), timeout=timeout_s)
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

# ---------------------------------------------------------------------
# PAGE_MB — ONE PAGE, IN MEGABYTES
#
# Both databases store their data in fixed-size PAGES of 8 KB (8192
# bytes) and keep recently used pages in memory: PostgreSQL calls them
# "blocks" in its "shared buffers", Neo4j "pages" in its "page cache".
# Because the page size is the SAME, the number of pages each side
# touched can be compared directly — and turned into megabytes, which
# are easier to picture: pages x 8192 / 1024**2 (1 MB = 1024 x 1024
# bytes; `**` is "to the power of"). 8192 / 1048576 = 0.0078125 MB.
# ---------------------------------------------------------------------
PAGE_MB = 8192 / 1024 ** 2   # both databases read and cache data in pages of 8 KB


# ---------------------------------------------------------------------
# def _postgres_memory_kb(node) -> float:  — THE QUERY'S MEMORY, PostgreSQL side
#
# A PostgreSQL plan is a TREE of steps; each node may report how much
# memory its step kept for itself (PostgreSQL 18 reports these in kB):
#   "Maximum Storage"     the recursive UNION and the CTE scan (the rows of
#                         `reach` kept while it's being built);
#   "Sort Space Used"     a sort;
#   "Peak Memory Usage"   a hash table (used for joins and DISTINCT).
# A step that ran out of its allowed memory (work_mem) continues on DISK
# instead: then "Storage" / "Sort Space Type" says "Disk", and that
# amount is NOT memory — it's counted separately, as temp_disk_mb (see
# postgres_work()). `node.get("Storage", "Memory") == "Memory"`: if the
# key is missing, assume memory.
#
# `node.get(...) or 0` turns a missing value (None) into 0, and the
# function walks the tree RECURSIVELY like _sum_profile() below:
# this node's memory + the sum over its "Plans" (PostgreSQL's word for
# the children). The result is the total memory the steps used, in kB.
# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# def postgres_work(conn, start, depth, timeout_s) -> dict:
#
# TIME isn't the only thing worth measuring: it depends on the computer
# and on what else is running. HOW MUCH WORK the database did (how much
# data it went through, how much memory it needed) explains WHY one side
# is faster. measure.py calls this once per depth, as an extra run AFTER
# the timed ones, because measuring the work slows a query down a little
# and mustn't spoil the timings.
#
# EXPLAIN shows the PLAN PostgreSQL chose for a query (which index, which
# join method...). The options in brackets:
#   ANALYZE      actually RUN the query, and report real numbers instead
#                of estimates. (Not the same as the ANALYZE command of
#                load_postgres.py, which refreshes statistics.)
#   BUFFERS      also report the BLOCKS (8 KB pages) used.
#   FORMAT JSON  give the report as JSON, so Python can read figures by
#                name instead of parsing text.
#
# .fetchone()[0][0]: the report is one row with one column holding a JSON
# LIST (psycopg turns it into a Python list); [0] is its only element, a
# dict. plan["Plan"] is the TOP node of the plan tree, i.e. the last step,
# whose BUFFER numbers already include all the steps below it (no need to
# add them up — unlike Neo4j below, and unlike the memory, which each
# step reports for itself).
#
# from_memory, from_disk = A, B — two variables assigned in one line.
#   "Shared Hit Blocks"    blocks already in memory.
#   "Shared Read Blocks"   blocks PostgreSQL had to read from a file (from
#                          disk — or from Windows' own file cache, which
#                          PostgreSQL can't tell apart).
#
# The figures returned, all in MB (they become the pg_... columns of
# results CSV, see docs_english/measure.py):
#   data_processed_mb   (hits + reads) x PAGE_MB: all the data the query
#                       went through. A page used twice counts twice: it's
#                       a measure of WORK, not of how big the data is.
#   data_from_disk_mb   the part that had to be read from a file.
#   memory_mb           _postgres_memory_kb(top) / 1024 (kB -> MB).
#   temp_disk_mb        "Temp Written Blocks": blocks written to TEMPORARY
#                       files because the work didn't fit in the memory
#                       allowed for one step (the work_mem setting) — e.g.
#                       a huge intermediate result of the recursive CTE.
#                       A sign the query is outgrowing memory. (Neo4j has
#                       no such figure, so the results CSV has no
#                       neo4j_temp_disk_mb column.)
# The same time limit is set first, as this is a full run of the query.
# ---------------------------------------------------------------------
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
# def neo4j_work(driver, database, start, depth, timeout_s, version="paths") -> dict:
#
# PROFILE in front of a Cypher query = Neo4j's EXPLAIN ANALYZE: it RUNS
# the query and records, for every step of its plan, what it did.
# `version` picks the Cypher version profiled (see cypher_reach()).
#
# result.consume() reads the result to the end and returns its SUMMARY
# (the metadata, not the rows). summary.profile is the plan tree as a
# dict (or None if there's none, hence `or {}`).
#
#   hits, misses       Neo4j's PAGE CACHE is its equivalent of
#                      PostgreSQL's shared buffers, with the same 8 KB
#                      pages: a hit = the page was in memory, a miss = it
#                      had to be read from disk. Summed over the tree.
#   memory             "GlobalMemory": the memory the WHOLE query used, in
#                      BYTES, found in the top step's arguments. The key
#                      holding the arguments is "args" in some driver
#                      versions and "arguments" in others, so both are
#                      tried (`A or B or {}` = the first one that isn't
#                      empty).
#
# The figures returned — the SAME names as postgres_work()'s, so
# measure.py can treat both sides alike (the neo4j_... columns):
#   data_processed_mb   (hits + misses) x PAGE_MB — directly comparable
#                       with PostgreSQL's, since the pages are the same
#                       size. A page used twice counts twice.
#   data_from_disk_mb   misses x PAGE_MB.
#   memory_mb           bytes / 1024**2 -> MB; None if Neo4j didn't
#                       report it (`X if condition else None`, a
#                       conditional expression).
# ---------------------------------------------------------------------
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
