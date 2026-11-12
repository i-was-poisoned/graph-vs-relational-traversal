"""Unit tests for the pure functions of scripts/build_hours.py (no network, no databases).

Run with:  python -m pytest
"""

from datetime import date, datetime, timezone

import pytest

from build_hours import (ask_hours, chosen_hours, database_name, hours_are_published, may_be_emptied, parse_count,
                         parse_date, parse_hour, recreate_databases)

NOW = datetime(2026, 11, 12, 15, 20, tzinfo=timezone.utc)


def utc(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def answers(*replies):
    # Stands in for the keyboard: each call returns the next ready-made answer.
    remaining = iter(replies)
    return lambda prompt: next(remaining)


# ---------- parse_date ----------

def test_parse_date_valid():
    assert parse_date("2026-08-27") == date(2026, 8, 27)


def test_parse_date_rejects_other_formats():
    for bad in ("27/08/2026", "2026-13-01", "yesterday"):
        with pytest.raises(ValueError):
            parse_date(bad)


def test_parse_date_rejects_dates_before_2015():
    with pytest.raises(ValueError, match="older GH Archive format"):
        parse_date("2014-12-31")


# ---------- parse_hour and parse_count ----------

def test_parse_hour_valid_limits():
    assert parse_hour("0") == 0
    assert parse_hour("23") == 23


def test_parse_hour_rejects_out_of_range():
    for bad in ("24", "-1", "3pm", ""):
        with pytest.raises(ValueError):
            parse_hour(bad)


def test_parse_count_limits():
    assert parse_count("1") == 1
    assert parse_count("168") == 168
    for bad in ("0", "169", "two"):
        with pytest.raises(ValueError):
            parse_count(bad)


# ---------- chosen_hours ----------

def test_chosen_hours_one_hour():
    assert chosen_hours(date(2026, 8, 27), 15, 1) == [utc(2026, 8, 27, 15)]


def test_chosen_hours_cross_midnight():
    assert chosen_hours(date(2026, 8, 27), 23, 2) == [utc(2026, 8, 27, 23), utc(2026, 8, 28, 0)]


# ---------- hours_are_published ----------

def test_old_hours_are_published():
    assert hours_are_published(chosen_hours(date(2026, 8, 27), 15, 3), NOW)


def test_hours_ending_one_hour_before_the_current_hour_are_published():
    # now 15:20 -> current hour 15:00; 12:00-14:00 is accepted
    assert hours_are_published(chosen_hours(date(2026, 11, 12), 12, 2), NOW)


def test_recent_or_future_hours_are_not_published():
    assert not hours_are_published(chosen_hours(date(2026, 11, 12), 13, 2), NOW)   # ends 15:00, too recent
    assert not hours_are_published(chosen_hours(date(2026, 11, 13), 0, 1), NOW)    # tomorrow


# ---------- database_name ----------

def test_database_name_one_hour_has_no_leading_zero_like_gh_archive():
    assert database_name(chosen_hours(date(2026, 8, 27), 5, 1)) == "gharchive-2026-08-27-5"


def test_database_name_several_hours_says_how_many():
    assert database_name(chosen_hours(date(2026, 8, 27), 15, 3)) == "gharchive-2026-08-27-15-3h"


def test_database_name_never_clashes_with_the_other_databases():
    for count in (1, 24):
        name = database_name(chosen_hours(date(2026, 8, 27), 15, count))
        assert name not in ("gharchive", "gharchive24h")
        assert "_" not in name   # Neo4j doesn't allow "_" in database names


# ---------- ask_hours ----------

def test_ask_hours_enter_keeps_the_benchmark_hour():
    assert ask_hours(NOW, ask=answers("", "", "", "")) == [utc(2026, 8, 27, 15)]


def test_ask_hours_chosen_date_hour_and_count():
    hours = ask_hours(NOW, ask=answers("2026-11-10", "9", "3", "y"))
    assert hours == [utc(2026, 11, 10, 9), utc(2026, 11, 10, 10), utc(2026, 11, 10, 11)]


def test_ask_hours_asks_again_after_bad_answers(capsys):
    # a wrong date; a wrong hour; a wrong count; hours not published yet; then a good answer
    reply = answers("10/11/2026",
                    "2026-11-10", "25",
                    "2026-11-10", "9", "0",
                    "2026-11-12", "13", "2",
                    "2026-11-10", "9", "", "")
    assert ask_hours(NOW, ask=reply) == [utc(2026, 11, 10, 9)]
    printed = capsys.readouterr().out
    for message in ("isn't a date", "isn't an hour", "isn't a number of hours", "hasn't published"):
        assert message in printed


def test_ask_hours_no_means_nothing_is_done():
    assert ask_hours(NOW, ask=answers("", "", "", "n")) is None


# ---------- may_be_emptied / recreate_databases (the safety check before deleting) ----------

def test_databases_made_by_this_script_may_be_emptied():
    assert may_be_emptied(database_name(chosen_hours(date(2026, 8, 27), 15, 1)))
    assert may_be_emptied(database_name(chosen_hours(date(2026, 8, 27), 15, 3)))


def test_the_other_databases_may_never_be_emptied():
    for name in ("gharchive", "gharchive24h", "gharchivetest", "neo4j", "postgres", "system"):
        assert not may_be_emptied(name)


def test_recreate_refuses_before_connecting_to_anything():
    # The check comes first, so this fails safely even with no server running and no password.
    with pytest.raises(ValueError, match="Refusing to empty"):
        recreate_databases("gharchive")
