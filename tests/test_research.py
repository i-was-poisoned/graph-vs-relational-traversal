"""Unit tests for the research scripts' own logic (no network, no databases).

choose_starts.py (which actors), traversal.py (the query texts) and
measure.py (the order of the sides, the data window, the comparison).

Run with:  python -m pytest
"""

import pytest

from choose_starts import choose, pick_median, pick_top
from measure import compare, data_window, run_order, side_summary, sides
from traversal import Outcome, cypher_hops, cypher_reach, sql_joins


def actor(actor_id, reached, repos, login=None):
    return {"actor_id": actor_id, "login": login or f"user{actor_id}", "reached": reached, "repos": repos}


# ---------- choose_starts: the top group ----------

def test_top_is_ordered_by_actors_reached():
    actors = [actor(1, 2, 1), actor(2, 9, 1), actor(3, 5, 1)]
    assert [a["actor_id"] for a in pick_top(actors, size=3)] == [2, 3, 1]


def test_top_tie_is_broken_by_more_repos_then_smaller_id():
    actors = [actor(30, 5, 1), actor(20, 5, 4), actor(10, 5, 1)]
    # same "reached": 20 has more repos; then 10 before 30 (smaller id)
    assert [a["actor_id"] for a in pick_top(actors, size=3)] == [20, 10, 30]


def test_top_keeps_only_ten():
    actors = [actor(i, i, 1) for i in range(1, 30)]
    assert len(pick_top(actors)) == 10


# ---------- choose_starts: the median group ----------

def test_median_leaves_out_actors_that_reach_nobody():
    actors = [actor(1, 0, 1), actor(2, 0, 1), actor(3, 2, 1), actor(4, 2, 1), actor(5, 2, 1)]
    chosen = pick_median(actors, exclude=set(), size=3)
    assert {a["actor_id"] for a in chosen} == {3, 4, 5}


def test_median_takes_the_closest_to_the_median():
    # reached 1..9 -> median 5; closest: 5, then 4 and 6 (tie: more repos first, then id)
    actors = [actor(i, i, 1) for i in range(1, 10)]
    actors[5] = actor(6, 6, 3)
    chosen = pick_median(actors, exclude=set(), size=3)
    assert [a["actor_id"] for a in chosen] == [5, 6, 4]


def test_median_never_repeats_a_top_actor():
    actors = [actor(i, 3, 1) for i in range(1, 6)]
    chosen = pick_median(actors, exclude={1, 2}, size=5)
    assert {a["actor_id"] for a in chosen} == {3, 4, 5}


def test_choose_gives_groups_and_ranks():
    rows = choose([actor(i, i, 1) for i in range(1, 31)])
    assert [r["group"] for r in rows] == ["top"] * 10 + ["median"] * 10
    assert rows[0]["rank"] == 1 and rows[0]["actor_id"] == 30
    assert rows[10]["rank"] == 1


def test_choose_is_the_same_whatever_the_input_order():
    # PostgreSQL and Neo4j return rows in different orders; the choice must not depend on it.
    actors = [actor(i, i % 7, i % 3) for i in range(1, 50)]
    assert choose(actors) == choose(list(reversed(actors)))


# ---------- traversal: the query texts ----------

def test_cypher_paths_writes_the_depth_into_the_pattern():
    assert "{1,3}" in cypher_reach(3, "paths")
    assert "$start" in cypher_reach(3, "paths")


def test_cypher_levels_has_one_step_per_hop():
    query = cypher_reach(4, "levels")
    assert query.count("CALL (seen, frontier)") == 4
    assert "NOT b IN seen" in query and "$start" in query


def test_cypher_refuses_depth_zero_and_unknown_versions():
    with pytest.raises(ValueError):
        cypher_reach(0)
    with pytest.raises(ValueError):
        cypher_reach(2, "shortcut")


def test_joins_and_hops_are_two_per_depth():
    assert sql_joins(3) == 6 and cypher_hops(3) == 6


# ---------- measure ----------

def test_sides_are_postgresql_then_the_cypher_versions():
    assert sides("both") == ["postgresql", "neo4j-paths", "neo4j-levels"]
    assert sides("levels") == ["postgresql", "neo4j-levels"]


def test_run_order_changes_which_side_goes_first():
    three = ["postgresql", "neo4j-paths", "neo4j-levels"]
    assert run_order(three, 1) == three
    assert run_order(three, 2) == ["neo4j-paths", "neo4j-levels", "postgresql"]
    assert run_order(three, 4) == three
    assert run_order(["postgresql", "neo4j-paths"], 2) == ["neo4j-paths", "postgresql"]


def test_data_window_is_read_from_the_database_name():
    assert data_window("gharchive-2026-10-08-9-24h") == ("2026-10-08 09:00", "2026-10-09 09:00", 24)
    assert data_window("gharchive-2026-10-08-23") == ("2026-10-08 23:00", "2026-10-09 00:00", 1)
    assert data_window("gharchive24h") == ("", "", None)


def finished(time_s):
    return {"status": "finished", "time_s": time_s}


def test_compare_says_who_was_faster_and_how_many_times():
    assert compare(finished(0.4), finished(0.1), 60) == ("neo4j", 4.0)
    assert compare(finished(0.1), finished(0.5), 60) == ("postgresql", 5.0)


def test_compare_with_a_timeout_gives_a_minimum():
    # Neo4j didn't finish in 60 s: PostgreSQL was at least 60 / 2 = 30 times faster.
    assert compare(finished(2.0), {"status": "timeout"}, 60) == ("postgresql", 30.0)
    assert compare({"status": "timeout"}, {"status": "skipped (timed out at a smaller depth)"}, 60) == ("neither", None)


def run(seconds, cpu_s=0.1, machine_cpu=10.0):
    return {"outcome": Outcome("ok", seconds, 7), "cpu_s": cpu_s, "machine_cpu": machine_cpu}


def test_side_summary_uses_the_median_and_ignores_the_first_run():
    summary = side_summary(Outcome("ok", 9.0, 7), [run(0.2), run(0.4, 0.4), run(0.3, 0.3)], {"memory_mb": 1.5}, "finished")
    assert summary["time_s"] == 0.3 and summary["first_run_s"] == 9.0
    assert summary["cpu_s"] == 0.3 and summary["cores_used"] == 1.0
    assert summary["memory_mb"] == 1.5


def test_side_summary_flags_noisy_or_busy_runs():
    assert side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.5)], {}, "finished")["noisy"]          # 5x spread
    assert side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.1, machine_cpu=95)], {}, "finished")["busy"]
    calm = side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.12)], {}, "finished")
    assert not calm["noisy"] and not calm["busy"]


def line(group, depth, pg_time, neo_time, actor_id=1):
    def side(time_s):
        return {"status": "finished", "time_s": time_s} if time_s else {"status": "timeout"}
    return {"group": group, "rank": 1, "login": "x", "actor_id": actor_id, "depth": depth, "actors_reached": 5,
            "answers_match": True, "postgresql": {**side(pg_time), "joins_or_hops": 2 * depth},
            "neo4j": {**side(neo_time), "joins_or_hops": 2 * depth}}


def test_neo4j_faster_from_needs_to_stay_faster():
    from measure import neo4j_faster_from
    # Neo4j wins at depth 2, loses at 3, wins from 4 on: the answer is depth 4.
    lines = [line("top", 1, 0.1, 0.5), line("top", 2, 0.5, 0.1), line("top", 3, 0.1, 0.5),
             line("top", 4, 0.9, 0.1), line("top", 5, None, 0.2)]
    assert neo4j_faster_from(lines, "top", 60) == "depth 4"
    assert neo4j_faster_from([line("top", 1, 0.1, 0.5)], "top", 60) == "never (up to depth 1)"


def test_workbook_has_the_information_once_and_two_tables_side_by_side(tmp_path):
    from openpyxl import load_workbook

    import results_workbook as rw
    path = tmp_path / "x.xlsx"
    starts = [{"group": "top", "rank": 1, "actor_id": 7, "login": "ana", "reached": 3}]
    information = [("Database", "gharchive-test"), ("Hours of data", 6)]
    rw.write_workbook(path, {"levels": (information, [line("top", 1, 0.1, 0.2), line("top", 2, 0.3, 0.1)])}, starts)

    sheet = load_workbook(path)["levels"]
    where = rw.table_positions()
    assert sheet.cell(1, 1).value == "Analysis information" and sheet.cell(2, 2).value == "gharchive-test"
    assert sheet.cell(1, where["postgresql"]).value == "PostgreSQL" and sheet.cell(1, where["neo4j"]).value == "Neo4j"
    # One empty column between the two tables, and the same headers in both (JOINs / Hops apart).
    assert where["neo4j"] == where["postgresql"] + len(rw.TABLE_COLUMNS) + 1
    assert sheet.cell(2, where["neo4j"] - 1).value is None
    pg = [sheet.cell(2, where["postgresql"] + i).value for i in range(len(rw.TABLE_COLUMNS))]
    neo = [sheet.cell(2, where["neo4j"] + i).value for i in range(len(rw.TABLE_COLUMNS))]
    assert [h for h in pg if h != "JOINs"] == [h for h in neo if h != "Hops"]
    # Headers strong blue; lines in light blues.
    assert sheet.cell(2, where["postgresql"]).fill.fgColor.rgb.endswith(rw.STRONG_BLUE)
    assert sheet.cell(3, where["postgresql"]).fill.fgColor.rgb.endswith(rw.LIGHT_BLUES[0])
    # The same line of both tables is the same question; the figures are each database's own.
    time_col = [name for name, _ in rw.TABLE_COLUMNS].index("Time (s)")
    assert sheet.cell(4, where["postgresql"] + time_col).value == 0.3
    assert sheet.cell(4, where["neo4j"] + time_col).value == 0.1
    assert rw.read_starts(path) == starts


def test_each_measurement_gets_its_own_file_and_reuses_the_latest_actors(tmp_path, monkeypatch):
    from datetime import datetime

    import measure
    import results_workbook as rw
    monkeypatch.setattr(measure, "RESULTS_DIR", tmp_path)
    path = measure.results_file("gharchive-2026-10-08-9-24h", datetime(2026, 11, 19, 10, 30, 0))
    assert path.name == "gharchive-2026-10-08-9-24h_2026-11-19_10-30-00.xlsx"
    assert measure.previous_starts("gharchive-2026-10-08-9-24h") == []

    for name, actor_id in (("2026-11-18_09-00-00", 1), ("2026-11-19_10-30-00", 2)):
        starts = [{"group": "top", "rank": 1, "actor_id": actor_id, "login": "x", "reached": 3}]
        rw.write_workbook(tmp_path / f"gharchive-2026-10-08-9-24h_{name}.xlsx", {}, starts)
    # The latest measurement wins.
    assert [a["actor_id"] for a in measure.previous_starts("gharchive-2026-10-08-9-24h")] == [2]
