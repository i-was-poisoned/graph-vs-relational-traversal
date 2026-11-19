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
#   - the three scripts under test: docs_english/choose_starts.py,
#     docs_english/traversal.py and docs_english/measure.py
#
# What's NEW here: pytest.raises (checking that a function REFUSES bad
# input), testing that a result does NOT depend on the order of the
# input, and two pytest FIXTURES, tmp_path and monkeypatch (in the last
# test). The tests also double as a precise, runnable description of the
# research's rules: which actors are chosen, what the Cypher texts look
# like, in which order the sides run, how a side's figures are
# summarised, who counts as faster, and the shape and naming of the
# results CSV files.
#
# Its job in the project: check the research scripts' own logic — the
# parts that need no database — so a mistake in a rule is caught in a
# second, not after hours of measuring.
#
# How to run the real tests:   python -m pytest
########################################################################

"""Unit tests for the research scripts' own logic (no network, no databases).

choose_starts.py (which actors), traversal.py (the query texts) and
measure.py (the order of the sides, the data window, the comparison).

Run with:  python -m pytest
"""

# pytest itself is imported this time (the earlier test files didn't
# need to): only for pytest.raises, in the traversal tests below.
import pytest

# ---------------------------------------------------------------------
# The functions under test. `from measure import ...` works because
# pytest.ini adds scripts/ to Python's search path (pythonpath = scripts).
# All of these are PURE functions — plain data in, plain data out — so
# they can be tested without PostgreSQL or Neo4j running. Outcome (the
# result of one run, docs_english/traversal.py) is imported to build
# fake runs.
# ---------------------------------------------------------------------
from choose_starts import choose, pick_median, pick_top
from measure import compare, data_window, run_order, side_summary, sides
from traversal import Outcome, cypher_hops, cypher_reach, sql_joins


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
# choose() puts the two groups together, as a list of rows.
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


# ---------- traversal: the query texts ----------

# cypher_reach(3, "paths") must contain the variable-length pattern {1,3}
# ("from 1 to 3 hops") and the $start parameter. `"..." in text` is True
# if the piece appears anywhere in the text.
def test_cypher_paths_writes_the_depth_into_the_pattern():
    assert "{1,3}" in cypher_reach(3, "paths")
    assert "$start" in cypher_reach(3, "paths")


# ---------------------------------------------------------------------
# The "levels" version glues one STEP per hop (see
# docs_english/traversal.py). text.count("piece") says how many times
# the piece appears: depth 4 -> exactly 4 CALL subqueries. The second
# assert checks that the step really drops the actors already seen, and
# that the start is still a parameter.
# ---------------------------------------------------------------------
def test_cypher_levels_has_one_step_per_hop():
    query = cypher_reach(4, "levels")
    assert query.count("CALL (seen, frontier)") == 4
    assert "NOT b IN seen" in query and "$start" in query


# ---------------------------------------------------------------------
# pytest.raises — TESTING THAT SOMETHING FAILS
#
# Sometimes the correct behaviour IS an error: a depth of 0 makes no
# sense, and cypher_reach must refuse it with a ValueError rather than
# build a broken query. The same for a version name it doesn't know.
#     with pytest.raises(ValueError):
#         <code>
# means "the code inside must raise a ValueError". If it does, pytest
# catches it and the test PASSES. If it raises nothing (or a different
# kind of error), the test FAILS. Each `with` block checks ONE call: the
# first error ends its block.
# ---------------------------------------------------------------------
def test_cypher_refuses_depth_zero_and_unknown_versions():
    with pytest.raises(ValueError):
        cypher_reach(0)
    with pytest.raises(ValueError):
        cypher_reach(2, "shortcut")


# One hop = 2 joins in SQL, 2 relationships in Cypher: depth 3 -> 6 each
# (the joins_or_hops columns of the results CSV).
def test_joins_and_hops_are_two_per_depth():
    assert sql_joins(3) == 6 and cypher_hops(3) == 6


# ---------- measure ----------

# --cypher both -> PostgreSQL and the two Cypher versions; --cypher levels
# -> PostgreSQL and that version only. PostgreSQL always comes first.
def test_sides_are_postgresql_then_the_cypher_versions():
    assert sides("both") == ["postgresql", "neo4j-paths", "neo4j-levels"]
    assert sides("levels") == ["postgresql", "neo4j-levels"]


# ---------------------------------------------------------------------
# The fairness rule of measure.py (see docs_english/measure.py,
# run_order): the sides are ROTATED, so each repetition starts with a
# different side. With three sides, repetition 4 is back to the start
# (the rotation goes round); with two sides, it simply alternates.
# ---------------------------------------------------------------------
def test_run_order_changes_which_side_goes_first():
    three = ["postgresql", "neo4j-paths", "neo4j-levels"]
    assert run_order(three, 1) == three
    assert run_order(three, 2) == ["neo4j-paths", "neo4j-levels", "postgresql"]
    assert run_order(three, 4) == three
    assert run_order(["postgresql", "neo4j-paths"], 2) == ["neo4j-paths", "postgresql"]


# ---------------------------------------------------------------------
# data_window reads the data's time window from the database NAME:
#   ...-2026-10-08-9-24h   from 09:00, 24 hours -> ends the next day 09:00
#   ...-2026-10-08-23      no "-<n>h" part: ONE hour, 23:00 -> 00:00 the
#                          next day (the date changes too)
#   gharchive24h           not a name build_hours.py makes: empty values,
#                          not a crash
# ---------------------------------------------------------------------
def test_data_window_is_read_from_the_database_name():
    assert data_window("gharchive-2026-10-08-9-24h") == ("2026-10-08 09:00", "2026-10-09 09:00", 24)
    assert data_window("gharchive-2026-10-08-23") == ("2026-10-08 23:00", "2026-10-09 00:00", 1)
    assert data_window("gharchive24h") == ("", "", None)


# A helper: the two keys compare() reads from a side that finished.
def finished(time_s):
    return {"status": "finished", "time_s": time_s}


# PostgreSQL 0.4 s, Neo4j 0.1 s -> Neo4j, 0.4 / 0.1 = 4 times faster.
# And the other way round: 0.5 / 0.1 = 5 times, PostgreSQL faster.
def test_compare_says_who_was_faster_and_how_many_times():
    assert compare(finished(0.4), finished(0.1), 60) == ("neo4j", 4.0)
    assert compare(finished(0.1), finished(0.5), 60) == ("postgresql", 5.0)


# ---------------------------------------------------------------------
# When one side didn't finish, its time is unknown — but it's at least
# the time limit. So times_faster = limit / the other side's time is a
# MINIMUM ("at least 30 times"). When neither finished: "neither", and
# no number at all (None).
# ---------------------------------------------------------------------
def test_compare_with_a_timeout_gives_a_minimum():
    # Neo4j didn't finish in 60 s: PostgreSQL was at least 60 / 2 = 30 times faster.
    assert compare(finished(2.0), {"status": "timeout"}, 60) == ("postgresql", 30.0)
    assert compare({"status": "timeout"}, {"status": "skipped (timed out at a smaller depth)"}, 60) == ("neither", None)


# ---------------------------------------------------------------------
# A helper that builds one timed run the way timed_run() in measure.py
# returns it: the Outcome (docs_english/traversal.py), the CPU seconds
# the database server used, and how busy the whole computer was. The
# defaults describe an ordinary run: 0.1 s of CPU, computer at 10 %.
# ---------------------------------------------------------------------
def run(seconds, cpu_s=0.1, machine_cpu=10.0):
    return {"outcome": Outcome("ok", seconds, 7), "cpu_s": cpu_s, "machine_cpu": machine_cpu}


# ---------------------------------------------------------------------
# The first run took 9 s (the plan being prepared). It's reported as
# first_run_s, but NOT used for the time: the timed runs are 0.2, 0.4,
# 0.3 s -> median 0.3. Their CPU seconds are 0.1, 0.4, 0.3 -> median
# 0.3, and cores_used = 0.3 / 0.3 = 1.0 (one core busy for the whole
# run). The work figures ({"memory_mb": 1.5}) are copied in as is.
# ---------------------------------------------------------------------
def test_side_summary_uses_the_median_and_ignores_the_first_run():
    summary = side_summary(Outcome("ok", 9.0, 7), [run(0.2), run(0.4, 0.4), run(0.3, 0.3)], {"memory_mb": 1.5}, "finished")
    assert summary["time_s"] == 0.3 and summary["first_run_s"] == 9.0
    assert summary["cpu_s"] == 0.3 and summary["cores_used"] == 1.0
    assert summary["memory_mb"] == 1.5


# ---------------------------------------------------------------------
# The two "not reliable" rules (see side_summary in
# docs_english/measure.py), plus a case that must be neither:
#   0.1 s and 0.5 s           5x spread, above 3x        -> noisy
#   0.1 s twice, CPU 95 %     computer busy, above 80 %  -> busy
#   0.1 s and 0.12 s          1.2x, CPU 10 %             -> calm
# `assert not x` — passes when x is False.
# ---------------------------------------------------------------------
def test_side_summary_flags_noisy_or_busy_runs():
    assert side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.5)], {}, "finished")["noisy"]          # 5x spread
    assert side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.1, machine_cpu=95)], {}, "finished")["busy"]
    calm = side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.12)], {}, "finished")
    assert not calm["noisy"] and not calm["busy"]


# ---------------------------------------------------------------------
# THE SHAPE OF A RESULTS CSV
#
# The user asked for this layout: the test's information first, then a
# PostgreSQL block and a Neo4j block with the SAME columns, side by side,
# then the comparison. This test makes sure the layout can't drift:
#
# 1. from measure import ... INSIDE the function: an import can be
#    written anywhere; here it keeps these three names next to the only
#    test that needs them.
#
# 2. COLUMNS[:len(TEST_COLUMNS)] == TEST_COLUMNS
#    The first columns are exactly the test's columns, in order.
#
# 3. pg = [c[len("pg_"):] for c in COLUMNS if c.startswith("pg_")]
#    Every column that starts with "pg_", with that prefix cut off
#    (c[3:] = the text from position 3 on: "pg_time_s" -> "time_s").
#    The same for "neo4j_". `pg == neo4j == SIDE_COLUMNS` is a CHAINED
#    comparison: both must be equal to SIDE_COLUMNS, so the two blocks
#    hold the same columns IN THE SAME ORDER.
#
# 4. The last assert checks that the blocks are side by side: the first
#    Neo4j column comes RIGHT AFTER the last PostgreSQL one (its
#    position, .index(), is one more), so no other column sits between
#    them.
# ---------------------------------------------------------------------
def test_results_columns_are_the_test_then_two_identical_blocks():
    from measure import COLUMNS, SIDE_COLUMNS, TEST_COLUMNS
    assert COLUMNS[:len(TEST_COLUMNS)] == TEST_COLUMNS
    pg = [c[len("pg_"):] for c in COLUMNS if c.startswith("pg_")]
    neo4j = [c[len("neo4j_"):] for c in COLUMNS if c.startswith("neo4j_")]
    assert pg == neo4j == SIDE_COLUMNS
    assert COLUMNS.index("neo4j_" + SIDE_COLUMNS[0]) == COLUMNS.index("pg_" + SIDE_COLUMNS[-1]) + 1


# ---------------------------------------------------------------------
# ONE FILE PER MEASUREMENT, AND REUSING THE LATEST ACTORS
#
# The user wanted each analysis to leave exactly ONE CSV, easy to open
# and understand. This test checks the two rules that come with that:
# the file's NAME, and that the starting actors are taken from the
# LATEST file of the database.
#
# FIXTURES — tmp_path and monkeypatch in the brackets
#   When a test function has parameters with these special names, pytest
#   PREPARES them and passes them in (a "fixture"):
#   tmp_path     a new, EMPTY temporary folder (a Path), different for
#                every test and cleaned up by pytest. The test can write
#                files there without touching the real results/.
#   monkeypatch  a helper to change something TEMPORARILY:
#                monkeypatch.setattr(measure, "RESULTS_DIR", tmp_path)
#                replaces measure.RESULTS_DIR by the temporary folder for
#                the length of this test only; pytest puts the real value
#                back afterwards. So results_file() and previous_starts()
#                look in the temporary folder.
#
# The imports are written inside the test: `import measure` (the whole
# module, so its RESULTS_DIR can be replaced), csv and datetime.
#
# 1. results_file(...) with 2026-11-19 10:30:00 must give the name
#    "<database>_2026-11-19_10-30-00.csv" (.name: the file name alone,
#    without the folder).
# 2. In the still-empty folder, previous_starts() finds no file: [].
# 3. Two fake measurement files are written with csv.DictWriter (see
#    docs_english/measure.py), one from 18 November with actor 1, one from
#    19 November with actor 2. Each holds the header and ONE line; the
#    columns not given stay empty.
# 4. previous_starts() must return the actor of the LATEST file only:
#    [2]. (The file names sort in time order, see results_file().)
# ---------------------------------------------------------------------
def test_each_measurement_gets_its_own_file_and_reuses_the_latest_actors(tmp_path, monkeypatch):
    import csv
    from datetime import datetime

    import measure
    monkeypatch.setattr(measure, "RESULTS_DIR", tmp_path)
    path = measure.results_file("gharchive-2026-10-08-9-24h", datetime(2026, 11, 19, 10, 30, 0))
    assert path.name == "gharchive-2026-10-08-9-24h_2026-11-19_10-30-00.csv"
    assert measure.previous_starts("gharchive-2026-10-08-9-24h") == []

    for name, actor_id in (("2026-11-18_09-00-00", 1), ("2026-11-19_10-30-00", 2)):
        with open(tmp_path / f"gharchive-2026-10-08-9-24h_{name}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=measure.COLUMNS)
            writer.writeheader()
            writer.writerow({"database": "gharchive-2026-10-08-9-24h", "start_group": "top", "start_rank": 1,
                             "start_actor_id": actor_id, "start_login": "x", "start_reach_1_hop": 3})
    # The latest measurement wins.
    assert [a["actor_id"] for a in measure.previous_starts("gharchive-2026-10-08-9-24h")] == [2]
