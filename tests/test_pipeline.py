"""Unit tests for the pure functions of scripts/pipeline.py (no network, no databases).

Run with:  python -m pytest
"""

from datetime import date, datetime, timedelta, timezone

from pipeline import already_ran_today, compute_window, hour_file_name


def utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ---------- compute_window ----------

def test_compute_window_readme_example():
    # At 2026-10-22 11:15 UTC the window is 2026-10-20 11:00 -> 2026-10-21 11:00:
    # 24 hour files, the first starting at 11:00 and the last at 10:00 the next day.
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    assert len(hours) == 24
    assert hours[0] == utc(2026, 10, 20, 11)
    assert hours[-1] == utc(2026, 10, 21, 10)


def test_compute_window_hours_are_consecutive():
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    for earlier, later in zip(hours, hours[1:]):
        assert later - earlier == timedelta(hours=1)


def test_compute_window_exactly_on_the_hour():
    # 12:00:00 sharp, 6-hour window, 2-hour lag -> ends at 10:00, so hours 04:00 ... 09:00.
    hours = compute_window(utc(2026, 10, 22, 12), window_hours=6, lag_hours=2)
    assert hours == [utc(2026, 10, 22, h) for h in range(4, 10)]


# ---------- hour_file_name ----------

def test_hour_file_name_has_no_leading_zero():
    # GH Archive writes "-5", not "-05": a wrong name would mean a 404 on every early hour.
    assert hour_file_name(utc(2026, 10, 20, 5)) == "2026-10-20-5.json.gz"


def test_hour_file_name_two_digit_hour():
    assert hour_file_name(utc(2026, 10, 20, 23)) == "2026-10-20-23.json.gz"


def test_hour_file_name_midnight():
    assert hour_file_name(utc(2026, 10, 21, 0)) == "2026-10-21-0.json.gz"


# ---------- already_ran_today (--scheduled: once a day) ----------

def test_never_ran_before():
    assert not already_ran_today(None, date(2026, 11, 12))


def test_already_ran_today():
    assert already_ran_today("2026-11-12\n", date(2026, 11, 12))


def test_ran_yesterday_so_runs_again_today():
    assert not already_ran_today("2026-11-11\n", date(2026, 11, 12))
