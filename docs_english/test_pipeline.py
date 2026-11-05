########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of tests/test_pipeline.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute (pytest only looks for tests in tests/, as
# pytest.ini says). The real, "clean" file (with none of this commentary)
# is tests/test_pipeline.py.
#
# Read docs_english/test_extract_csv.py first: the basics of pytest (test_
# names, assert, how to run the tests) are explained there and NOT
# repeated here. This file focuses on what's NEW: building UTC dates with
# datetime, comparing them, timedelta, and zip() to walk through pairs of
# neighbours in a list.
#
# Its job in the project: check the two pure functions of pipeline.py —
# the ones that decide WHICH hours the live pipeline downloads and WHAT
# their files are called. If either were wrong, the pipeline would load
# the wrong window or ask GH Archive for files that don't exist.
########################################################################

"""Unit tests for the pure functions of scripts/pipeline.py (no network, no databases).

Run with:  python -m pytest
"""

# datetime: a date AND time in one object, e.g. 2026-10-22 11:15.
# timedelta: a DURATION, e.g. "1 hour". Subtracting two datetimes gives a
#   timedelta; adding a timedelta to a datetime gives another datetime.
# timezone: timezone.utc marks a datetime as UTC. GH Archive names its
#   files in UTC, so the pipeline (and these tests) always work in UTC.
from datetime import datetime, timedelta, timezone

# The two functions under test. "pure" means: same input -> same output,
# with no files, network or clock involved. That's what makes them so
# easy to test — we give them a fixed "now" instead of the real time.
from pipeline import compute_window, hour_file_name


# ---------------------------------------------------------------------
# A small helper (NOT a test: its name doesn't start with test_, so
# pytest doesn't run it on its own). It just saves typing: instead of
#     datetime(2026, 10, 22, 11, 15, tzinfo=timezone.utc)
# the tests write
#     utc(2026, 10, 22, 11, 15)
# `minute: int = 0` is a default value: if you leave it out, it's 0, so
# utc(2026, 10, 20, 11) means 11:00 sharp.
# ---------------------------------------------------------------------
def utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ---------- compute_window ----------

# The example used in the README and the project notes, turned into a
# test: if this ever fails, either the code or the documentation is
# wrong.
def test_compute_window_readme_example():
    # At 2026-10-22 11:15 UTC the window is 2026-10-20 11:00 -> 2026-10-21 11:00:
    # 24 hour files, the first starting at 11:00 and the last at 10:00 the next day.
    # `window_hours=24, lag_hours=24`: keyword arguments (name=value). They
    # make the call readable: you can see which 24 is which.
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    # Three checks: how many hours, the first one and the last one.
    # hours[-1]: a negative index counts from the end, so -1 is the last item.
    # Why does the last hour START at 10:00? Each item is the start of a
    # one-hour file: the file starting at 10:00 covers 10:00-11:00, so the
    # window ends at 11:00.
    assert len(hours) == 24
    assert hours[0] == utc(2026, 10, 20, 11)
    assert hours[-1] == utc(2026, 10, 21, 10)


def test_compute_window_hours_are_consecutive():
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    # zip(hours, hours[1:]) walks through NEIGHBOURS two by two:
    #   hours      = [h0, h1, h2, ..., h23]
    #   hours[1:]  = [h1, h2, h3, ..., h23]      (the same list, minus the first item)
    #   zip(...)   -> (h0, h1), (h1, h2), ..., (h22, h23)
    # zip stops when the shorter list runs out, so there are 23 pairs.
    # For each pair, the later hour must be exactly 1 hour after the
    # earlier one: no gaps, no repeats, nothing out of order.
    for earlier, later in zip(hours, hours[1:]):
        assert later - earlier == timedelta(hours=1)


def test_compute_window_exactly_on_the_hour():
    # 12:00:00 sharp, 6-hour window, 2-hour lag -> ends at 10:00, so hours 04:00 ... 09:00.
    # Different numbers from the default 24/24 on purpose: the function
    # must work for any window and lag, not only the ones we usually use.
    hours = compute_window(utc(2026, 10, 22, 12), window_hours=6, lag_hours=2)
    # The expected list is built with a list comprehension:
    # range(4, 10) gives 4, 5, 6, 7, 8, 9 (10 is NOT included), so this is
    # [utc(..., 4), utc(..., 5), ..., utc(..., 9)]. Comparing the whole
    # list with == checks every item AND the order in one go.
    assert hours == [utc(2026, 10, 22, h) for h in range(4, 10)]


# ---------- hour_file_name ----------

def test_hour_file_name_has_no_leading_zero():
    # GH Archive writes "-5", not "-05": a wrong name would mean a 404 on every early hour.
    # (The project notes show what pytest prints when this check fails.)
    assert hour_file_name(utc(2026, 10, 20, 5)) == "2026-10-20-5.json.gz"


# Two more edge cases for the same rule: a two-digit hour (must stay
# "23") and midnight (must be "0", not "00" and not an empty string).
def test_hour_file_name_two_digit_hour():
    assert hour_file_name(utc(2026, 10, 20, 23)) == "2026-10-20-23.json.gz"


def test_hour_file_name_midnight():
    assert hour_file_name(utc(2026, 10, 21, 0)) == "2026-10-21-0.json.gz"
