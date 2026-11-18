########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of tests/test_build_hours.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute (pytest only looks for tests in tests/, as
# pytest.ini says). The real, "clean" file (with none of this commentary)
# is tests/test_build_hours.py.
#
# Read these first; what they explain is NOT repeated here:
#   docs_english/test_extract_csv.py   pytest basics (test_ names, assert,
#                                      fixtures like tmp_path and caplog)
#   docs_english/test_pipeline.py      the utc() helper, comparing
#                                      datetimes, `assert not`
#   docs_english/build_hours.py        the functions tested here
#
# What's NEW here:
#   - pytest.raises: checking that a function RAISES an error (and with
#     which message);
#   - the capsys fixture: capturing what a function PRINTS;
#   - FAKING THE KEYBOARD: a function that returns ready-made answers
#     (with iter(), next() and a lambda), passed to ask_hours() instead
#     of input();
#   - *replies: a function that accepts any number of arguments.
#
# Its job in the project: build_hours.py asks questions and DELETES
# databases, so its rules must hold: invalid answers are refused, the
# date and hour are never chosen for you, unpublished hours are refused,
# names never clash with the other databases, and the safety check
# refuses to empty anything not named "gharchive-...". All of it is
# tested WITHOUT network, databases or anybody typing.
#
# How to run the real tests (from the project folder):
#     python -m pytest
########################################################################

"""Unit tests for the pure functions of scripts/build_hours.py (no network, no databases).

Run with:  python -m pytest
"""

from datetime import date, datetime, timezone

# pytest itself is imported this time, for pytest.raises (see below).
# (Plain tests with assert don't need the import; fixtures don't either.)
import pytest

# A long import, split over two lines: inside ( ) Python lets a line
# continue on the next one. These are the functions under test.
from build_hours import (ask_hours, chosen_hours, database_name, hours_are_published, may_be_emptied, parse_count,
                         parse_date, parse_hour, recreate_databases)

# ---------------------------------------------------------------------
# NOW — a FIXED "current time" for every test: 2026-11-12 15:20 UTC.
# build_hours.py takes `now` as a parameter precisely so tests can do
# this. With the real clock, a test about "recent hours" would pass
# today and fail tomorrow. Written in CAPITALS: a constant.
# With NOW, the current hour is 15:00, so the latest hour range accepted
# must END by 14:00 (see hours_are_published() in build_hours.py).
# ---------------------------------------------------------------------
NOW = datetime(2026, 11, 12, 15, 20, tzinfo=timezone.utc)


# Same helper as in test_pipeline.py, without minutes (not needed here).
def utc(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


# ---------------------------------------------------------------------
# def answers(*replies): — the FAKE KEYBOARD.
#
# *replies — the star collects ANY NUMBER of arguments into one tuple:
#   answers("2026-08-27", "15", "", "y")  ->  replies = ("2026-08-27", "15", "", "y")
#
# iter(replies) — turns the tuple into an ITERATOR: an object that hands
#   out the items ONE AT A TIME and remembers where it is.
# next(remaining) — gives the next item; the first call gives
#   "2026-08-27", the second "15", and so on. (If the answers run out,
#   next() raises StopIteration and the test fails — a sign the function
#   asked more questions than expected.)
#
# lambda prompt: next(remaining) — a LAMBDA is a tiny function without a
#   name, written in one expression. It's the same as:
#       def fake_input(prompt):
#           return next(remaining)
#   It takes `prompt` (the question text), like input() does, ignores it,
#   and returns the next ready-made answer.
#
# answers(...) RETURNS that function; the tests pass it as ask=... to
# ask_hours(), which then calls it instead of input(). The lambda keeps
# using `remaining` after answers() has finished: a function remembers
# the variables of the place where it was created.
# ---------------------------------------------------------------------
def answers(*replies):
    # Stands in for the keyboard: each call returns the next ready-made answer.
    remaining = iter(replies)
    return lambda prompt: next(remaining)


# ---------- parse_date ----------

def test_parse_date_valid():
    assert parse_date("2026-08-27") == date(2026, 8, 27)


# ---------------------------------------------------------------------
# with pytest.raises(ValueError):
#     parse_date(bad)
#
# NEW: a test that EXPECTS an error. Normally an error inside a test
# makes it fail. Inside `with pytest.raises(ValueError):` it's the
# opposite: the test passes only if the code in the block raises a
# ValueError, and FAILS if it runs without raising one.
#
# The three bad dates: the wrong order (day/month/year), a month that
# doesn't exist (13), and a word. The loop checks each one; each gets
# its own `with`, because the block stops at the first error.
# ---------------------------------------------------------------------
def test_parse_date_rejects_other_formats():
    for bad in ("27/08/2026", "2026-13-01", "yesterday"):
        with pytest.raises(ValueError):
            parse_date(bad)


# match="older GH Archive format" — the error must ALSO contain this text
# in its message. So the test checks it's the RIGHT error (the "before
# 2015" one), not some other ValueError. (match= is really a regular
# expression, a search pattern, but plain words like these simply mean
# "contains this text".)
def test_parse_date_rejects_dates_before_2015():
    with pytest.raises(ValueError, match="older GH Archive format"):
        parse_date("2014-12-31")


# ---------- parse_hour and parse_count ----------

# EDGE CASES: the two limits, 0 and 23, must be accepted; just outside
# them (24, -1), and things that aren't numbers ("3pm", empty), refused.
# Limits are where off-by-one mistakes (< instead of <=) show up.
def test_parse_hour_valid_limits():
    assert parse_hour("0") == 0
    assert parse_hour("23") == 23


def test_parse_hour_rejects_out_of_range():
    for bad in ("24", "-1", "3pm", ""):
        with pytest.raises(ValueError):
            parse_hour(bad)


# The same for the count: 1 and 168 (a week, MAX_HOURS) accepted; 0, 169
# and a word refused.
def test_parse_count_limits():
    assert parse_count("1") == 1
    assert parse_count("168") == 168
    for bad in ("0", "169", "two"):
        with pytest.raises(ValueError):
            parse_count(bad)


# ---------- chosen_hours ----------

def test_chosen_hours_one_hour():
    assert chosen_hours(date(2026, 8, 27), 15, 1) == [utc(2026, 8, 27, 15)]


# 23:00 plus one hour must be 00:00 of the NEXT day, not an hour 24.
def test_chosen_hours_cross_midnight():
    assert chosen_hours(date(2026, 8, 27), 23, 2) == [utc(2026, 8, 27, 23), utc(2026, 8, 28, 0)]


# ---------- hours_are_published ----------

# Three cases around the rule, with NOW = 15:20 (latest allowed end
# 14:00): old hours (August) are fine; hours ending exactly at 14:00 are
# fine (the limit itself); ending at 15:00, or tomorrow, are refused.
# The comments at the end of some lines are the original's own notes.
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


# The names must never be one of the two other databases, and never
# contain "_" (Neo4j would refuse it). `not in (...)`: not equal to any
# item of the tuple. `"_" not in name`: on strings, `in` looks for text.
def test_database_name_never_clashes_with_the_other_databases():
    for count in (1, 24):
        name = database_name(chosen_hours(date(2026, 8, 27), 15, count))
        assert name not in ("gharchive", "gharchive24h")
        assert "_" not in name   # Neo4j doesn't allow "_" in database names


# ---------- ask_hours ----------

# ---------------------------------------------------------------------
# capsys — NEW fixture ("capture system output"). Like caplog (see
# test_extract_csv.py) but for print(): everything printed during the
# test is captured instead of shown. capsys.readouterr().out returns it
# as one string, so the test can check the messages really appeared.
#
# This test proves the rule "the date and the hour have NO default": the
# fake keyboard presses Enter ("") at the date, then at the hour, and
# ask_hours() must ask again each time (printing "Please type ...")
# instead of picking a value. Each line of answers() is one round of
# questions; the comments say what each answer means. Only on the third
# round does it get everything, with Enter at the count (= 1 hour) and
# Enter at the confirmation (= yes).
# ---------------------------------------------------------------------
def test_ask_hours_has_no_default_date_or_hour(capsys):
    # Pressing Enter at the date or the hour doesn't pick one: it asks again.
    reply = answers("",                      # no date
                    "2026-08-27", "",        # no hour
                    "2026-08-27", "15", "", "")   # Enter at the count = 1 hour; Enter to confirm
    assert ask_hours(NOW, ask=reply) == [utc(2026, 8, 27, 15)]
    printed = capsys.readouterr().out
    assert "Please type a date" in printed and "Please type an hour" in printed


# The normal case: date, hour 9, 3 hours, "y" -> three consecutive hours.
def test_ask_hours_chosen_date_hour_and_count():
    hours = ask_hours(NOW, ask=answers("2026-11-10", "9", "3", "y"))
    assert hours == [utc(2026, 11, 10, 9), utc(2026, 11, 10, 10), utc(2026, 11, 10, 11)]


# Every way of answering wrong, one round each, and finally a good round.
# The last check loops over the four expected messages: each must appear
# in what was printed, proving each mistake was caught and explained.
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


# Answering "n" to the confirmation returns None: nothing will be done.
# `is None` (not == None) is the usual way to check for None.
def test_ask_hours_no_means_nothing_is_done():
    assert ask_hours(NOW, ask=answers("2026-08-27", "15", "", "n")) is None


# ---------- may_be_emptied / recreate_databases (the safety check before deleting) ----------

# The names this script makes are allowed...
def test_databases_made_by_this_script_may_be_emptied():
    assert may_be_emptied(database_name(chosen_hours(date(2026, 8, 27), 15, 1)))
    assert may_be_emptied(database_name(chosen_hours(date(2026, 8, 27), 15, 3)))


# ...and every other database on the two servers is refused: the frozen
# benchmark, the live pipeline's, the integration tests', and the
# servers' own built-in ones.
def test_the_other_databases_may_never_be_emptied():
    for name in ("gharchive", "gharchive24h", "gharchivetest", "neo4j", "postgres", "system"):
        assert not may_be_emptied(name)


# ---------------------------------------------------------------------
# The most important test of the file: recreate_databases("gharchive")
# must raise "Refusing to empty" BEFORE it connects to anything. This
# test can run with no database server and no password: if the
# check came after the connection, the test would fail with a connection
# error instead — so passing proves the order is right, and that the
# frozen benchmark can't be deleted by this script.
# ---------------------------------------------------------------------
def test_recreate_refuses_before_connecting_to_anything():
    # The check comes first, so this fails safely even with no server running and no password.
    with pytest.raises(ValueError, match="Refusing to empty"):
        recreate_databases("gharchive")
