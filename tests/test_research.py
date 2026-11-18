"""Unit tests for the research scripts' own logic (no network, no databases).

choose_starts.py (which actors), measure.py (the alternating order),
traversal.py (the Cypher text) and analyze.py (the summaries).

Run with:  python -m pytest
"""

import pytest

from analyze import summarise_actor, summary
from choose_starts import choose, pick_median, pick_top
from measure import run_order
from traversal import cypher_reach


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


# ---------- measure: alternating order ----------

def test_run_order_alternates_which_side_goes_first():
    assert run_order(1) == ("postgresql", "neo4j")
    assert run_order(2) == ("neo4j", "postgresql")
    assert run_order(3) == ("postgresql", "neo4j")


# ---------- traversal: the Cypher text ----------

def test_cypher_reach_writes_the_depth_into_the_pattern():
    assert "{1,3}" in cypher_reach(3)
    assert "$start" in cypher_reach(3)


def test_cypher_reach_refuses_depth_zero():
    with pytest.raises(ValueError):
        cypher_reach(0)


# ---------- analyze ----------

def run(run_number, seconds, status="ok", count="7", cpu="10"):
    return {"run": str(run_number), "seconds": str(seconds), "status": status, "count": count,
            "machine_cpu_percent": cpu}


def test_summary_of_an_actor_ignores_the_first_run():
    result = summarise_actor([run(0, 9.0), run(1, 0.2), run(2, 0.4), run(3, 0.3)])
    assert result["median_s"] == 0.3 and result["min_s"] == 0.2 and result["max_s"] == 0.4
    assert result["finished"] == 3 and result["count"] == 7


def test_summary_of_an_actor_counts_timeouts():
    result = summarise_actor([run(0, 60, "timeout", "")])
    assert result["timeouts"] == 1 and result["median_s"] is None


def test_noisy_when_spread_is_large_or_computer_busy():
    assert summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.5)])["noisy"]          # 5x spread
    assert summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.1, cpu="95")])["noisy"]  # busy
    assert not summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.12)])["noisy"]


def test_group_summary_gives_postgresql_vs_neo4j():
    rows = [
        {"group": "top", "actor_id": 1, "depth": 2, "system": "postgresql", "median_s": 0.4, "timeouts": 0,
         "errors": 0, "noisy": False},
        {"group": "top", "actor_id": 1, "depth": 2, "system": "neo4j", "median_s": 0.1, "timeouts": 0,
         "errors": 0, "noisy": False},
    ]
    by_system = {r["system"]: r for r in summary(rows)}
    assert by_system["postgresql"]["postgresql_vs_neo4j"] == 4.0
