"""Unit tests for the CSV-reading helpers of the two loaders.

Only the parts that work on files are tested here; loading into a real
PostgreSQL or Neo4j database belongs to the integration test.

Run with:  python -m pytest
"""

from pathlib import Path

from load_neo4j import read_csv
from load_postgres import count_csv_rows


def write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ---------- load_neo4j.read_csv ----------

def test_read_csv_converts_id_columns_to_int(tmp_path):
    file = write_text(tmp_path / "actors.csv", "id,login\n1,ana\n2,bea\n")
    rows = read_csv(file, ("id",))
    # Numbers, not text: in Neo4j, 1 and "1" are different values and would never match.
    assert rows == [{"id": 1, "login": "ana"}, {"id": 2, "login": "bea"}]


def test_read_csv_leaves_other_columns_as_text(tmp_path):
    # A login made of digits must stay text: only the columns we name are converted.
    file = write_text(tmp_path / "actors.csv", "id,login\n3,12345\n")
    rows = read_csv(file, ("id",))
    assert rows == [{"id": 3, "login": "12345"}]


def test_read_csv_converts_both_columns_of_connections(tmp_path):
    file = write_text(tmp_path / "actor_repo.csv", "actor_id,repo_id\n1,10\n")
    rows = read_csv(file, ("actor_id", "repo_id"))
    assert rows == [{"actor_id": 1, "repo_id": 10}]


# ---------- load_postgres.count_csv_rows ----------

def test_count_csv_rows_excludes_header(tmp_path):
    file = write_text(tmp_path / "repos.csv", "id,name\n10,ana/project\n20,bea/tool\n")
    assert count_csv_rows(file) == 2


def test_count_csv_rows_header_only_is_zero(tmp_path):
    file = write_text(tmp_path / "repos.csv", "id,name\n")
    assert count_csv_rows(file) == 0
