########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of tests/test_loaders.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute (pytest only looks for tests in tests/, as
# pytest.ini says). The real, "clean" file (with none of this commentary)
# is tests/test_loaders.py.
#
# Read docs_english/test_extract_csv.py first: the basics of pytest (test_
# names, assert, the tmp_path fixture, how to run the tests) are explained
# there and NOT repeated here.
#
# Its job in the project: check the small file-reading helpers of the two
# loaders. The loaders themselves (load_postgres.load, load_neo4j.load)
# need real databases, so they belong to the integration test (step 3 of
# the plan), not here.
########################################################################

"""Unit tests for the CSV-reading helpers of the two loaders.

Only the parts that work on files are tested here; loading into a real
PostgreSQL or Neo4j database belongs to the integration test.

Run with:  python -m pytest
"""

from pathlib import Path

# One function from each loader. Importing load_neo4j also imports the
# neo4j package (and load_postgres imports psycopg), so the packages must
# be installed — but no database is contacted: importing a module only
# defines its functions, it doesn't run main().
from load_neo4j import read_csv
from load_postgres import count_csv_rows


# ---------------------------------------------------------------------
# Helper (not a test): write some text to a file and give back its path,
# so each test can create its CSV file in one line.
# Path.write_text() opens the file, writes the text and closes it.
# "\n" in the strings below is a line break: "id,login\n1,ana\n" is the
# two-line file
#     id,login
#     1,ana
# ---------------------------------------------------------------------
def write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ---------- load_neo4j.read_csv ----------

# tmp_path: pytest's fixture that gives each test its own empty temporary
# folder (explained in test_extract_csv.py).
def test_read_csv_converts_id_columns_to_int(tmp_path):
    file = write_text(tmp_path / "actors.csv", "id,login\n1,ana\n2,bea\n")
    # ("id",) is a tuple with ONE item: the comma is what makes it a tuple.
    # Without it, ("id") would just be the string "id" in brackets.
    rows = read_csv(file, ("id",))
    # Numbers, not text: in Neo4j, 1 and "1" are different values and would never match.
    # Note 1 (a number) vs "ana" (text) in the expected result: the test
    # checks the TYPES as well as the values, because 1 == "1" is False in
    # Python.
    assert rows == [{"id": 1, "login": "ana"}, {"id": 2, "login": "bea"}]


def test_read_csv_leaves_other_columns_as_text(tmp_path):
    # A login made of digits must stay text: only the columns we name are converted.
    file = write_text(tmp_path / "actors.csv", "id,login\n3,12345\n")
    rows = read_csv(file, ("id",))
    # "12345" in quotes (text), while 3 has none (number).
    assert rows == [{"id": 3, "login": "12345"}]


# The connections file has TWO id columns, and both must be converted,
# or the MATCH in load_neo4j.py (which looks actors and repos up by
# numeric id) would find nothing.
def test_read_csv_converts_both_columns_of_connections(tmp_path):
    file = write_text(tmp_path / "actor_repo.csv", "actor_id,repo_id\n1,10\n")
    rows = read_csv(file, ("actor_id", "repo_id"))
    assert rows == [{"actor_id": 1, "repo_id": 10}]


# ---------- load_postgres.count_csv_rows ----------

# count_csv_rows is what load_postgres.py compares the table counts with
# at the end. If it counted the header too, every check would be off by
# one and report a mismatch that doesn't exist.
def test_count_csv_rows_excludes_header(tmp_path):
    file = write_text(tmp_path / "repos.csv", "id,name\n10,ana/project\n20,bea/tool\n")
    assert count_csv_rows(file) == 2


# Edge case: a file with only the header (e.g. an hour with no usable
# events) must give 0, not -1 or an error.
def test_count_csv_rows_header_only_is_zero(tmp_path):
    file = write_text(tmp_path / "repos.csv", "id,name\n")
    assert count_csv_rows(file) == 0
