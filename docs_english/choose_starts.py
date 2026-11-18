########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/choose_starts.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute. The real, "clean" script (with none of this
# commentary) is scripts/choose_starts.py.
#
# Read these annotated copies first; what they explain is NOT repeated here:
#   - download_gharchive.py   argparse, Path, main() and the __name__ guard
#   - extract_csv.py          the csv module, open(..., newline=""),
#                             mkdir(parents=True, exist_ok=True), sorted(...)
#   - load_neo4j.py           csv.DictReader, database_=
#   - summarize_data.py       dict comprehensions, f-string column widths
#   - pipeline.py             RawDescriptionHelpFormatter
#   - drop_databases.py       neo4j_databases() / postgres_databases()
#   - traversal.py            SQL_ONE_HOP / CYPHER_ONE_HOP (what "reached"
#                             and "repos" mean), connect_postgres/neo4j
#
# What's NEW here:
#   - WHY the starting actors are CHOSEN BY A RULE, and what the rule is;
#   - sorting with a KEY function that returns a TUPLE, and negative
#     numbers to sort some parts from biggest to smallest;
#   - statistics.median() and "closest to the median";
#   - lambda (a one-line function without a name);
#   - comparing the choice made by the two databases, and saving it ONCE
#     (results/<database>/starts.csv) so it never changes afterwards;
#   - action="store_true" flags and parser.error().
#
# WHY CHOOSE THE STARTING ACTORS AT ALL? The measured traversal (REACH in
# traversal.py) starts from ONE actor. Who that actor is changes
# everything: from a very connected actor, depth 2 can already reach a
# big part of the graph; from a quiet one, almost nothing. If we picked
# actors by hand ("this one looks interesting"), the results could be
# bent — even without meaning to. So the choice is made by a fixed RULE,
# written down here, that gives the same answer every time:
#   - 10 "top" actors: the most connected (the hardest case);
#   - 10 "median" actors: typical ones (the usual case).
#
# How it's meant to be run — normally through research.sh, or alone:
#     ./run.sh scripts/choose_starts.py --database gharchive-2026-08-27-12-6h
#     ./run.sh scripts/choose_starts.py --list-databases
########################################################################

"""Choose the starting actors for the measurements, the same on both sides.

For every actor it counts, in PostgreSQL and in Neo4j:
    reached = distinct other actors that share at least one repo with it (one hop)
    repos   = distinct repos it touched
and then picks two groups of 10:

    top     the 10 that reach the most actors in one hop
    median  the 10 whose "reached" is closest to the median, among the actors
            that reach at least one other actor (those that reach nobody are
            only a single JOIN, and tell nothing about traversals)

Ties are broken by more repos, then by the smaller id, so the choice never
changes. Both databases must give exactly the same 20 actors (with the same
numbers); otherwise nothing is saved.

The list is saved to results/<database>/starts.csv. If that file already
exists it's kept, so a measurement repeated another day uses the same actors;
--force chooses them again.

Usage:
    ./run.sh scripts/choose_starts.py --database gharchive-2026-08-27-12-6h
    ./run.sh scripts/choose_starts.py --list-databases
"""

# ---------------------------------------------------------------------
# NEW: `import statistics` — a standard-library module with the usual
# summary numbers (mean, median, ...). Only statistics.median() is used.
#
# `import drop_databases` / `import traversal`: our own scripts, used as
# modules. drop_databases gives the functions that list the project's
# databases; traversal gives the queries and the connections.
# ---------------------------------------------------------------------
import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

import drop_databases
import traversal

# ---------------------------------------------------------------------
# RESULTS_DIR: <project>/results (same Path recipe as PROJECT_DIR in
# load_postgres.py). Each database gets its own sub-folder:
#     results/gharchive-2026-08-27-12-6h/starts.csv
# because each data VOLUME is its own database, with its own actors.
#
# GROUP_SIZE = 10: the size of each group (top, median).
# FIELDS: the columns of starts.csv, in order.
#   group, rank   which group, and the position inside it (1 to 10)
#   actor_id, login, reached, repos   the actor and its two counts
# ---------------------------------------------------------------------
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
GROUP_SIZE = 10
FIELDS = ["group", "rank", "actor_id", "login", "reached", "repos"]


# ---------------------------------------------------------------------
# def ranking_key(actor) -> tuple:  — HOW TO SORT, AND WHY A TUPLE
#
# Each actor is a dict like
#     {"actor_id": 19, "login": "brynary", "reached": 340, "repos": 12}
# sorted(..., key=ranking_key) calls ranking_key on every actor and sorts
# the actors by what it returns.
#
# Python compares TUPLES element by element, left to right, like words in
# a dictionary: the first elements decide; only if they're EQUAL do the
# second elements decide; and so on. So one tuple encodes "sort by this,
# then by that, then by that".
#
# sorted() always sorts from SMALL to BIG. To get "the MOST reached
# first", the trick is a MINUS sign: -340 is smaller than -12, so the
# actor reaching 340 comes before the one reaching 12. Same for repos.
# The id is NOT negated: the SMALLER id wins.
#
# Example, three actors:
#     A: reached 50, repos 3, id 7   -> key (-50, -3, 7)
#     B: reached 50, repos 5, id 9   -> key (-50, -5, 9)
#     C: reached 80, repos 1, id 4   -> key (-80, -1, 4)
#   sorted order: C (-80 is the smallest), then B (tie on -50, and -5 < -3),
#   then A.
#
# WHY THESE TIE-BREAKS? Many actors have the same "reached" count. Without
# a tie-break, which of them lands in the top 10 could depend on the
# order the database happened to return the rows — and PostgreSQL and
# Neo4j return them in different orders. With the tie-break, the order
# is TOTAL: two different actors can never have the same key (ids are
# unique), so the result is always the same. "More repos" comes first
# because it's a meaningful number (more starting points for the walk);
# the id is the final, arbitrary-but-fixed rule. (A natural tie-break
# would be "more events", but event counts aren't stored in the
# databases — only the actor-repo pairs are.)
# ---------------------------------------------------------------------
def ranking_key(actor: dict) -> tuple:
    # Most reached first; ties: more repos first; then the smaller id.
    return (-actor["reached"], -actor["repos"], actor["actor_id"])


# The top group: sort everything by the key and keep the first `size`.
# [:size] is a slice: items 0 to size-1. `size: int = GROUP_SIZE` is a
# default value, so tests can ask for a smaller group.
def pick_top(actors: list[dict], size: int = GROUP_SIZE) -> list[dict]:
    return sorted(actors, key=ranking_key)[:size]


# ---------------------------------------------------------------------
# def pick_median(actors, exclude, size) -> list[dict]:  — THE TYPICAL ACTORS
#
# 1. reaching = only the actors with reached >= 1. An actor that reaches
#    nobody gives a traversal that stops immediately (a single lookup):
#    it would measure nothing interesting. (In practice the ONE_HOP
#    queries already leave those actors out; this line makes the rule
#    explicit and safe whatever the input.)
#    If nobody is left (an empty database), there's no median: return [].
#
# 2. statistics.median(...): sort the numbers and take the MIDDLE one
#    (with an even count, the average of the two middle ones, so it can
#    be e.g. 3.5). Why the median and not the average (mean)? The data is
#    very SKEWED: most actors reach a handful of others, a few bots and
#    popular projects reach thousands. Those few pull the average way up,
#    so "average" would describe nobody; the median is the actor in the
#    middle of the line — a truly typical one.
#
# 3. candidates = everyone in `reaching` EXCEPT the actors in `exclude`
#    (the top group). On a small database the two groups could overlap;
#    an actor measured twice under two labels would distort both groups.
#    `exclude` is a set, so `not in exclude` is instant.
#
# 4. The sort key, with a LAMBDA:
#        lambda a: (abs(a["reached"] - median),) + ranking_key(a)
#    `lambda a: <expression>` is a tiny function with no name: it takes
#    a and returns the expression. Handy when the function is used once,
#    right here. What it returns:
#      abs(...)            the DISTANCE from the median (abs = absolute
#                          value: 3 above and 3 below both count as 3).
#      (x,)                a tuple with ONE element (the comma makes it a
#                          tuple).
#      + ranking_key(a)    `+` between tuples GLUES them:
#                          (2,) + (-5, -3, 7) -> (2, -5, -3, 7).
#    So: closest to the median first; on equal distance, the same
#    tie-breaks as the top group (more reached, more repos, smaller id).
#    Then [:size] keeps the 10 closest.
# ---------------------------------------------------------------------
def pick_median(actors: list[dict], exclude: set[int], size: int = GROUP_SIZE) -> list[dict]:
    # Only actors that reach someone; the median of their "reached"; then the closest ones,
    # with the same tie-break. Actors already in the top group are left out.
    reaching = [a for a in actors if a["reached"] >= 1]
    if not reaching:
        return []
    median = statistics.median(a["reached"] for a in reaching)
    candidates = [a for a in reaching if a["actor_id"] not in exclude]
    return sorted(candidates, key=lambda a: (abs(a["reached"] - median),) + ranking_key(a))[:size]


# ---------------------------------------------------------------------
# def choose(actors) -> list[dict]:  — the two groups, as rows for starts.csv
#
# exclude={a["actor_id"] for a in top}: a SET COMPREHENSION (curly
# brackets, no key: value) — the set of the top group's ids.
#
# The double loop builds one row per chosen actor:
#   for group, members in (("top", top), ("median", median)):
#       loops over two (name, list) pairs, so the same code handles both.
#   for rank, actor in enumerate(members, start=1):
#       enumerate (peek_data.py) with start=1: ranks 1..10, not 0..9.
#
# The row itself:
#   {"group": group, "rank": rank, **{k: actor[k] for k in (...)}}
#   {k: actor[k] for k in (...)} is a dict comprehension (summarize_data.py)
#   that copies those four keys from the actor. `**` INSIDE a dict literal
#   unpacks that dict's keys and values into the new one (the same `**`
#   as for keyword arguments in check_connections.py). Result, e.g.:
#   {"group": "top", "rank": 1, "actor_id": 19, "login": "...",
#    "reached": 340, "repos": 12} — exactly the FIELDS of the CSV.
# ---------------------------------------------------------------------
def choose(actors: list[dict]) -> list[dict]:
    top = pick_top(actors)
    median = pick_median(actors, exclude={a["actor_id"] for a in top})
    rows = []
    for group, members in (("top", top), ("median", median)):
        for rank, actor in enumerate(members, start=1):
            rows.append({"group": group, "rank": rank, **{k: actor[k] for k in ("actor_id", "login", "reached", "repos")}})
    return rows


# ---------------------------------------------------------------------
# Getting the counts from each database, in the SAME shape: a list of
# dicts with the keys actor_id, login, reached, repos.
#
# postgres_actors: fetchall() gives tuples in the SELECT's column order
# (actor_id, login, reached, repos), turned into dicts by position.
#
# neo4j_actors: a Neo4j record already knows its column names (the AS
# names of CYPHER_ONE_HOP, chosen identical to the SQL ones), so
# dict(r) gives the same dict directly.
#
# The rows come back in NO particular order on either side — which is
# fine, because choose() sorts them with a total order (see ranking_key).
# ---------------------------------------------------------------------
def postgres_actors(database: str) -> list[dict]:
    with traversal.connect_postgres(database) as conn:
        rows = conn.execute(traversal.SQL_ONE_HOP).fetchall()
    return [{"actor_id": r[0], "login": r[1], "reached": r[2], "repos": r[3]} for r in rows]


def neo4j_actors(database: str) -> list[dict]:
    with traversal.connect_neo4j() as driver:
        records = driver.execute_query(traversal.CYPHER_ONE_HOP, database_=database).records
    return [dict(r) for r in records]


# ---------------------------------------------------------------------
# def existing_databases() -> list[str]:
#
# A database can only be measured if it exists on BOTH servers (a build
# could have failed half-way). This keeps the PostgreSQL names (already
# filtered and sorted by drop_databases) that are ALSO in the Neo4j set:
# an INTERSECTION, written as a list comprehension so the sorted order is
# kept. Used by --list-databases (research.sh reads that list).
# ---------------------------------------------------------------------
def existing_databases() -> list[str]:
    # Project databases that exist on BOTH servers (the only ones that can be measured).
    with traversal.connect_neo4j() as driver:
        in_neo4j = set(drop_databases.neo4j_databases(driver))
    return [name for name in drop_databases.postgres_databases() if name in in_neo4j]


# ---------------------------------------------------------------------
# def save(rows, path) -> None:
#
# path.parent.mkdir(...): creates results/<database>/ if needed
# (extract_csv.py).
#
# csv.DictWriter is the writing twin of csv.DictReader (load_neo4j.py):
# it writes DICTS as CSV lines, putting each value in the column of the
# same name. fieldnames=FIELDS fixes the columns and their order.
#   writeheader()    the first line: group,rank,actor_id,login,reached,repos
#   writerows(rows)  one line per dict.
# ---------------------------------------------------------------------
def save(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    # -----------------------------------------------------------------
    # The command-line options.
    #   --database         which database to work on (the same name exists
    #                      on both servers).
    #   --force, --list-databases: action="store_true" makes an ON/OFF
    #                      SWITCH that takes no value: False if absent,
    #                      True if written. (argparse turns the hyphen into
    #                      an underscore: args.list_databases.)
    # The help text of --list-databases is split over two lines inside
    # the brackets, which Python allows.
    # -----------------------------------------------------------------
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", help="The database to choose the actors in (same name on both sides)")
    parser.add_argument("--force", action="store_true", help="Choose again even if starts.csv already exists")
    parser.add_argument("--list-databases", action="store_true",
                        help="Only print the project databases that exist on both servers, one per line")
    args = parser.parse_args()

    # --list-databases: print the names, one per line ("\n".join), and stop.
    # Otherwise --database is needed. It isn't declared required=True
    # because --list-databases works without it; so it's checked by hand.
    # parser.error("...") prints the usage line and the message, and stops
    # the program with exit code 2 — the same as argparse's own errors.
    if args.list_databases:
        print("\n".join(existing_databases()))
        return
    if not args.database:
        parser.error("--database is required")

    # -----------------------------------------------------------------
    # CHOSEN ONCE, THEN KEPT
    #
    # If starts.csv already exists, it is NOT recomputed (unless --force).
    # Why? The research compares measurements: the same database measured
    # again another day must use the SAME 20 actors, or the two runs
    # wouldn't be comparable. The rule is deterministic, so recomputing
    # would normally give the same list anyway — but keeping the file
    # makes it CERTAIN (e.g. even if the rule were improved later), and it
    # saves the cost of the heavy ONE_HOP queries.
    # \" inside the f-string is an escaped double quote.
    # -----------------------------------------------------------------
    path = RESULTS_DIR / args.database / "starts.csv"
    if path.exists() and not args.force:
        print(f"The starting actors for \"{args.database}\" were already chosen: {path}")
        print("They're kept, so this measurement uses the same actors (use --force to choose again).")
        return

    # -----------------------------------------------------------------
    # The choice is made TWICE, independently: once from PostgreSQL's
    # counts, once from Neo4j's. Each takes a while on a big database, so
    # the time is printed (perf_counter: load_postgres.py; :.1f = one
    # decimal place).
    # -----------------------------------------------------------------
    print(f'Counting, for every actor of "{args.database}", how many actors it reaches in one hop ...')
    begin = time.perf_counter()
    in_postgres = choose(postgres_actors(args.database))
    print(f"PostgreSQL done in {time.perf_counter() - begin:.1f} s.")
    begin = time.perf_counter()
    in_neo4j = choose(neo4j_actors(args.database))
    print(f"Neo4j done in {time.perf_counter() - begin:.1f} s.")

    # -----------------------------------------------------------------
    # BOTH DATABASES MUST AGREE
    #
    # in_postgres != in_neo4j compares the two LISTS of dicts item by
    # item: same length, same order, and every dict equal (same keys,
    # same values). Any difference — another actor, or the same actor
    # with another count — means the two databases don't hold the same
    # data, and comparing their speeds would be meaningless. So nothing
    # is saved, the differing rows are shown side by side (zip:
    # test_pipeline.py), and the exit code is 1.
    # -----------------------------------------------------------------
    if in_postgres != in_neo4j:
        print("\nThe two databases DON'T choose the same actors; nothing was saved.")
        for p, n in zip(in_postgres, in_neo4j):
            if p != n:
                print(f"  PostgreSQL {p}\n  Neo4j      {n}")
        sys.exit(1)

    # They agree: print the list as a table (column widths :<7, :>4 ...:
    # summarize_data.py), then save it.
    print(f"\nBoth databases choose the same {len(in_postgres)} actors:")
    print(f"  {'group':<7} {'rank':>4} {'actor_id':>12} {'reached':>8} {'repos':>6}  login")
    for row in in_postgres:
        print(f"  {row['group']:<7} {row['rank']:>4} {row['actor_id']:>12} {row['reached']:>8} {row['repos']:>6}  {row['login']}")
    save(in_postgres, path)
    print(f"\nSaved to {path}")


# The __name__ guard: download_gharchive.py.
if __name__ == "__main__":
    main()
