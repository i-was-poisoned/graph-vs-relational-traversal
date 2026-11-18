########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of tests/test_research.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute (pytest only looks for tests in tests/, as
# pytest.ini says). The real, "clean" file (with none of this commentary)
# is tests/test_research.py.
#
# Read these first; what they explain is NOT repeated here:
#   - docs_english/test_extract_csv.py   the basics of pytest (test_ names,
#                                        assert, how to run the tests)
#   - docs_english/test_pipeline.py      small helper functions in a test
#                                        file, keyword arguments
#   - the four scripts under test: docs_english/choose_starts.py,
#     docs_english/measure.py, docs_english/traversal.py and
#     docs_english/analyze.py
#
# What's NEW here: pytest.raises (checking that a function REFUSES bad
# input), and testing that a result does NOT depend on the order of the
# input. The tests also double as a precise, runnable description of the
# research's rules: which actors are chosen, in which order the sides
# run, and how the times are summarised.
#
# Its job in the project: check the research scripts' own logic — the
# parts that need no database — so a mistake in a rule is caught in a
# second, not after hours of measuring.
#
# How to run the real tests:   python -m pytest
########################################################################

"""Unit tests for the research scripts' own logic (no network, no databases).

choose_starts.py (which actors), measure.py (the alternating order),
traversal.py (the Cypher text) and analyze.py (the summaries).

Run with:  python -m pytest
"""

# pytest itself is imported this time (the earlier test files didn't
# need to): only for pytest.raises, in the traversal tests below.
import pytest

# ---------------------------------------------------------------------
# The functions under test. `from analyze import ...` works because
# pytest.ini adds scripts/ to Python's search path (pythonpath = scripts).
# All of these are PURE functions — plain data in, plain data out — so
# they can be tested without PostgreSQL or Neo4j running.
# ---------------------------------------------------------------------
from analyze import summarise_actor, summary
from choose_starts import choose, pick_median, pick_top
from measure import run_order
from traversal import cypher_reach


# ---------------------------------------------------------------------
# A helper (not a test: no test_ prefix) that builds one fake actor as a
# dict, with the same keys the real ones have (see choose_starts.py):
#   reached   how many other actors it reaches in one hop
#   repos     how many repos it interacted with
# `login=None` + `login or f"user{actor_id}"`: if no login is given,
# invent one ("user7"). `or` gives the right side when the left is None.
# ---------------------------------------------------------------------
def actor(actor_id, reached, repos, login=None):
    return {"actor_id": actor_id, "login": login or f"user{actor_id}", "reached": reached, "repos": repos}


# ---------- choose_starts: the top group ----------

# The top group is "the actors that reach the most others", most first.
def test_top_is_ordered_by_actors_reached():
    actors = [actor(1, 2, 1), actor(2, 9, 1), actor(3, 5, 1)]
    # The list comprehension keeps only the ids, to compare the ORDER:
    # 9 reached (id 2), then 5 (id 3), then 2 (id 1).
    assert [a["actor_id"] for a in pick_top(actors, size=3)] == [2, 3, 1]


# Ties must be broken by a fixed rule, otherwise the choice could change
# from one run to the next (or between PostgreSQL and Neo4j).
def test_top_tie_is_broken_by_more_repos_then_smaller_id():
    actors = [actor(30, 5, 1), actor(20, 5, 4), actor(10, 5, 1)]
    # same "reached": 20 has more repos; then 10 before 30 (smaller id)
    assert [a["actor_id"] for a in pick_top(actors, size=3)] == [20, 10, 30]


# Without size=..., the default group size (10) applies.
def test_top_keeps_only_ten():
    actors = [actor(i, i, 1) for i in range(1, 30)]
    assert len(pick_top(actors)) == 10


# ---------- choose_starts: the median group ----------

# The "median" group is the TYPICAL actors: those whose "reached" is
# closest to the median. Actors that reach nobody (reached = 0) are left
# out first: starting a traversal from them would measure nothing.
def test_median_leaves_out_actors_that_reach_nobody():
    actors = [actor(1, 0, 1), actor(2, 0, 1), actor(3, 2, 1), actor(4, 2, 1), actor(5, 2, 1)]
    chosen = pick_median(actors, exclude=set(), size=3)
    # A SET comprehension { } — the order doesn't matter here, only which
    # ids were chosen. Comparing two sets ignores order.
    assert {a["actor_id"] for a in chosen} == {3, 4, 5}


def test_median_takes_the_closest_to_the_median():
    # reached 1..9 -> median 5; closest: 5, then 4 and 6 (tie: more repos first, then id)
    actors = [actor(i, i, 1) for i in range(1, 10)]
    # Position 5 of the list (counting from 0) is the actor with id 6.
    # It's replaced by the same actor with 3 repos, so it wins the tie
    # against id 4 (both are 1 away from the median).
    actors[5] = actor(6, 6, 3)
    chosen = pick_median(actors, exclude=set(), size=3)
    assert [a["actor_id"] for a in chosen] == [5, 6, 4]


# exclude= the ids already in the top group: an actor is never in both.
def test_median_never_repeats_a_top_actor():
    actors = [actor(i, 3, 1) for i in range(1, 6)]
    chosen = pick_median(actors, exclude={1, 2}, size=5)
    assert {a["actor_id"] for a in chosen} == {3, 4, 5}


# ---------------------------------------------------------------------
# choose() puts the two groups together, as the rows of starts.csv.
# ["top"] * 10 + ["median"] * 10 — `*` repeats a list, `+` joins two:
# ten "top" followed by ten "median". The ranks restart at 1 in each
# group: rows[0] is the first top actor, rows[10] the first median one.
# With reached = 1..30, the actor reaching the most is id 30.
# ---------------------------------------------------------------------
def test_choose_gives_groups_and_ranks():
    rows = choose([actor(i, i, 1) for i in range(1, 31)])
    assert [r["group"] for r in rows] == ["top"] * 10 + ["median"] * 10
    assert rows[0]["rank"] == 1 and rows[0]["actor_id"] == 30
    assert rows[10]["rank"] == 1


# ---------------------------------------------------------------------
# TESTING THAT THE ORDER OF THE INPUT DOESN'T MATTER
#
# The actors come from a database query, and databases don't promise any
# particular row order. If the choice depended on it, the same database
# could give different starting actors from one day to the next. So the
# test gives choose() the same actors in two opposite orders and requires
# exactly the same result. `i % 7` and `i % 3` (remainders) create many
# ties on purpose, to exercise the tie-break rule.
# ---------------------------------------------------------------------
def test_choose_is_the_same_whatever_the_input_order():
    # PostgreSQL and Neo4j return rows in different orders; the choice must not depend on it.
    actors = [actor(i, i % 7, i % 3) for i in range(1, 50)]
    assert choose(actors) == choose(list(reversed(actors)))


# ---------- measure: alternating order ----------

# The fairness rule of measure.py (see docs_english/measure.py, run_order):
# odd repetitions PostgreSQL first, even ones Neo4j first.
def test_run_order_alternates_which_side_goes_first():
    assert run_order(1) == ("postgresql", "neo4j")
    assert run_order(2) == ("neo4j", "postgresql")
    assert run_order(3) == ("postgresql", "neo4j")


# ---------- traversal: the Cypher text ----------

# cypher_reach(3) must contain the variable-length pattern {1,3} ("from 1
# to 3 hops") and the $start parameter. `"..." in text` is True if the
# piece appears anywhere in the text.
def test_cypher_reach_writes_the_depth_into_the_pattern():
    assert "{1,3}" in cypher_reach(3)
    assert "$start" in cypher_reach(3)


# ---------------------------------------------------------------------
# pytest.raises — TESTING THAT SOMETHING FAILS
#
# Sometimes the correct behaviour IS an error: a depth of 0 makes no
# sense, and cypher_reach must refuse it with a ValueError rather than
# build a broken query.
#     with pytest.raises(ValueError):
#         <code>
# means "the code inside must raise a ValueError". If it does, pytest
# catches it and the test PASSES. If it raises nothing (or a different
# kind of error), the test FAILS.
# ---------------------------------------------------------------------
def test_cypher_reach_refuses_depth_zero():
    with pytest.raises(ValueError):
        cypher_reach(0)


# ---------- analyze ----------

# ---------------------------------------------------------------------
# A helper that builds one line of runs.csv as csv.DictReader would give
# it: every value is TEXT (str(...)), just like the real file. The
# defaults describe an ordinary finished run: status "ok", answer "7",
# CPU at 10 %.
# ---------------------------------------------------------------------
def run(run_number, seconds, status="ok", count="7", cpu="10"):
    return {"run": str(run_number), "seconds": str(seconds), "status": status, "count": count,
            "machine_cpu_percent": cpu}


# ---------------------------------------------------------------------
# Run 0 took 9 s (the first run, with the plan being prepared). If it were
# counted, the max would be 9.0 and the median 0.35. Ignoring it: the
# timed runs are 0.2, 0.4, 0.3 -> median 0.3, min 0.2, max 0.4, three
# finished, and the answer 7 (now a number, not text).
# ---------------------------------------------------------------------
def test_summary_of_an_actor_ignores_the_first_run():
    result = summarise_actor([run(0, 9.0), run(1, 0.2), run(2, 0.4), run(3, 0.3)])
    assert result["median_s"] == 0.3 and result["min_s"] == 0.2 and result["max_s"] == 0.4
    assert result["finished"] == 3 and result["count"] == 7


# Only run 0, and it timed out (so measure.py skipped the repetitions):
# the timeout must still be counted, and there's no time at all.
def test_summary_of_an_actor_counts_timeouts():
    result = summarise_actor([run(0, 60, "timeout", "")])
    assert result["timeouts"] == 1 and result["median_s"] is None


# ---------------------------------------------------------------------
# The two "noisy" rules (see docs_english/analyze.py), plus a case that
# must NOT be noisy:
#   0.1 s and 0.5 s           5x spread, above 3x        -> noisy
#   0.1 s twice, CPU 95 %     computer busy, above 80 %  -> noisy
#   0.1 s and 0.12 s          1.2x, CPU 10 %             -> not noisy
# `assert not x` — passes when x is False.
# ---------------------------------------------------------------------
def test_noisy_when_spread_is_large_or_computer_busy():
    assert summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.5)])["noisy"]          # 5x spread
    assert summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.1, cpu="95")])["noisy"]  # busy
    assert not summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.12)])["noisy"]


# ---------------------------------------------------------------------
# The headline ratio: PostgreSQL's median 0.4 s, Neo4j's 0.1 s, same group
# and depth -> 0.4 / 0.1 = 4.0, "PostgreSQL 4 times slower" (Neo4j
# faster). The rows imitate per_actor()'s output. by_system: the summary
# lines in a dict keyed by side, to pick the PostgreSQL one.
# ---------------------------------------------------------------------
def test_group_summary_gives_postgresql_vs_neo4j():
    rows = [
        {"group": "top", "actor_id": 1, "depth": 2, "system": "postgresql", "median_s": 0.4, "timeouts": 0,
         "errors": 0, "noisy": False},
        {"group": "top", "actor_id": 1, "depth": 2, "system": "neo4j", "median_s": 0.1, "timeouts": 0,
         "errors": 0, "noisy": False},
    ]
    by_system = {r["system"]: r for r in summary(rows)}
    assert by_system["postgresql"]["postgresql_vs_neo4j"] == 4.0
