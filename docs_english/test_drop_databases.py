########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of tests/test_drop_databases.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute (pytest only looks for tests in tests/, as
# pytest.ini says). The real, "clean" file (with none of this commentary)
# is tests/test_drop_databases.py.
#
# Read docs_english/test_extract_csv.py first (the basics of pytest:
# test_ names, assert, how to run the tests) and docs_english/drop_databases.py
# (the script under test). They're NOT repeated here. This file focuses on
# what's NEW: checking that a function RAISES an error, with
# pytest.raises(), and testing SAFETY RULES — what must NEVER happen —
# rather than what should happen.
#
# Its job in the project: drop_databases.py deletes databases for good.
# These tests prove, without any server running, that its name rule
# accepts every kind of project database, rejects the servers' own
# databases (and look-alikes), and that the drop functions refuse a
# server database BEFORE they even try to connect.
#
# Run the real tests with:
#     python -m pytest
########################################################################

"""Unit tests for the safety rules of scripts/drop_databases.py (no network, no databases).

Run with:  python -m pytest
"""

# `import pytest`: needed here (unlike in some earlier test files) because
# we use one of its tools directly: pytest.raises (see the last test).
import pytest

# The four functions under test. is_project_database and project_databases
# are pure. drop_postgres and drop_neo4j would normally touch a server —
# but only AFTER their guard, and the guard is what's tested here.
from drop_databases import drop_neo4j, drop_postgres, is_project_database, project_databases


# ---------------------------------------------------------------------
# One test per SIDE of the rule: what must be accepted, and what must be
# refused. A loop over a tuple of names checks several cases in one test.
# (The tuple is split over two lines; inside brackets Python lets a line
# continue freely.)
# The names cover every shape the project uses: the benchmark database,
# the live 24-hour one, a per-hour one, a per-volume one ("-6h") and the
# integration test's one.
# ---------------------------------------------------------------------
def test_project_databases_are_recognised():
    for name in ("gharchive", "gharchive24h", "gharchive-2026-08-27-15", "gharchive-2026-08-27-15-6h",
                 "gharchivetest"):
        assert is_project_database(name)


# The servers' own databases, plus two LOOK-ALIKES: "myothers" (an
# unrelated name) and "archive" (contains part of the word but doesn't
# start with "gharchive"). `assert not ...` claims the result is False.
def test_server_databases_are_never_project_databases():
    for name in ("postgres", "template0", "template1", "neo4j", "system", "myothers", "archive"):
        assert not is_project_database(name)


# A mixed list, as a server would report it, in no particular order.
# Comparing with == against the expected LIST checks the filtering AND
# the order at once. Note the order is ALPHABETICAL, character by
# character: "-" comes before "2" in the character table, so
# "gharchive-2026..." sorts before "gharchive24h".
def test_project_databases_picks_only_the_project_ones_sorted():
    names = ["postgres", "gharchive24h", "template1", "gharchive", "neo4j", "gharchive-2026-11-09-9-5h"]
    assert project_databases(names) == ["gharchive", "gharchive-2026-11-09-9-5h", "gharchive24h"]


# ---------------------------------------------------------------------
# NEW: pytest.raises — testing that something FAILS
#
#     with pytest.raises(ValueError, match="Refusing to delete"):
#         drop_postgres("postgres")
#
# reads: "the code inside this `with` block MUST raise a ValueError whose
# message contains 'Refusing to delete'".
#   - If it does, the error is caught and the test carries on (passes).
#   - If NO error is raised, the test FAILS ("DID NOT RAISE").
#   - If a DIFFERENT error is raised, or the message doesn't match, the
#     test fails too.
# match= is a regular expression searched in the message; plain words
# like these simply mean "contains this text".
#
# Why this proves the guard comes FIRST: no server is running during unit
# tests. If drop_postgres tried to connect before checking the name, it
# would raise a psycopg connection error instead — a different error, so
# the test would fail. And drop_neo4j is given None instead of a driver:
# if it ever reached driver.execute_query(...), it would crash with an
# AttributeError. Getting exactly ValueError shows that nothing past the
# guard ran.
# ---------------------------------------------------------------------
def test_drop_refuses_server_databases_before_connecting_to_anything():
    # The check comes first, so this fails safely even with no server running.
    with pytest.raises(ValueError, match="Refusing to delete"):
        drop_postgres("postgres")
    with pytest.raises(ValueError, match="Refusing to delete"):
        drop_neo4j(None, "neo4j")
