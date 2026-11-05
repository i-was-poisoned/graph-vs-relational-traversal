"""Unit tests for scripts/extract_csv.py.

Each test builds a tiny GH Archive-like file (two or three made-up events) in a
temporary folder, so the tests run in milliseconds and need no downloaded data.

Run with:  python -m pytest
"""

import csv
import gzip
import json
from pathlib import Path

from extract_csv import extract, is_bot, remember_latest, write_all


def make_event(actor_id: int, login: str, repo_id: int, repo_name: str,
               created_at: str = "2026-08-27T15:00:00Z") -> dict:
    # Only the fields extract_csv.py reads; real events have many more.
    return {
        "actor": {"id": actor_id, "login": login},
        "repo": {"id": repo_id, "name": repo_name},
        "created_at": created_at,
    }


def write_events(path: Path, events: list[dict]) -> Path:
    # One JSON object per line (JSON Lines), like GH Archive; compressed if the name ends in .gz.
    text = "".join(json.dumps(event) + "\n" for event in events)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


# ---------- is_bot ----------

def test_is_bot_true_for_bot_suffix():
    assert is_bot("dependabot[bot]")


def test_is_bot_false_for_normal_login():
    assert not is_bot("pedro")


def test_is_bot_false_when_bot_is_not_the_suffix():
    # Only the "[bot]" ending counts, not the word "bot" somewhere in the login.
    assert not is_bot("robot")
    assert not is_bot("bot-builder")


# ---------- remember_latest ----------

def test_remember_latest_stores_new_key():
    names = {}
    remember_latest(names, 7, "2026-08-27T15:10:00Z", "ana")
    assert names == {7: ("2026-08-27T15:10:00Z", "ana")}


def test_remember_latest_newer_name_replaces_older():
    names = {7: ("2026-08-27T15:10:00Z", "ana")}
    remember_latest(names, 7, "2026-08-27T15:30:00Z", "ana-dev")
    assert names[7] == ("2026-08-27T15:30:00Z", "ana-dev")


def test_remember_latest_older_name_is_ignored():
    # Events can arrive out of order: an older event must not undo a newer name.
    names = {7: ("2026-08-27T15:30:00Z", "ana-dev")}
    remember_latest(names, 7, "2026-08-27T15:20:00Z", "ana")
    assert names[7] == ("2026-08-27T15:30:00Z", "ana-dev")


# ---------- extract ----------

def test_extract_normal_event(tmp_path):
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project")])
    actors, repos, pairs, skipped_bots = extract([file])
    assert actors == {1: ("2026-08-27T15:00:00Z", "ana")}
    assert repos == {10: ("2026-08-27T15:00:00Z", "ana/project")}
    assert pairs == {(1, 10)}
    assert skipped_bots == 0


def test_extract_skips_bots(tmp_path):
    file = write_events(tmp_path / "hour.json", [
        make_event(1, "ana", 10, "ana/project"),
        make_event(2, "dependabot[bot]", 10, "ana/project"),
    ])
    actors, repos, pairs, skipped_bots = extract([file])
    assert set(actors) == {1}
    assert pairs == {(1, 10)}
    assert skipped_bots == 1


def test_extract_skips_event_with_empty_repo(tmp_path, caplog):
    # The real case found on 2026-10-22: a ForkEvent whose repo was {} (no id, no name).
    empty_repo = {"actor": {"id": 2, "login": "bea"}, "repo": {}, "created_at": "2026-08-27T15:05:00Z"}
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project"), empty_repo])
    actors, repos, pairs, _ = extract([file])
    assert set(actors) == {1}
    assert pairs == {(1, 10)}
    assert "Skipped 1 event(s) without an actor or repo id" in caplog.text


def test_extract_repeated_pair_counted_once(tmp_path):
    # Three events by the same actor on the same repo -> one connection.
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project")] * 3)
    _, _, pairs, _ = extract([file])
    assert pairs == {(1, 10)}


def test_extract_keeps_latest_login(tmp_path):
    file = write_events(tmp_path / "hour.json", [
        make_event(1, "ana-dev", 10, "ana/project", "2026-08-27T15:30:00Z"),
        make_event(1, "ana", 10, "ana/project", "2026-08-27T15:10:00Z"),
    ])
    actors, _, _, _ = extract([file])
    assert actors[1][1] == "ana-dev"


def test_extract_reads_several_files_plain_and_gz(tmp_path):
    plain = write_events(tmp_path / "2026-10-20-5.json", [make_event(1, "ana", 10, "ana/project")])
    compressed = write_events(tmp_path / "2026-10-20-6.json.gz", [make_event(2, "bea", 20, "bea/tool")])
    actors, repos, pairs, _ = extract([plain, compressed])
    assert set(actors) == {1, 2}
    assert set(repos) == {10, 20}
    assert pairs == {(1, 10), (2, 20)}


# ---------- write_all / write_csv ----------

def test_write_all_writes_headers_and_sorted_rows(tmp_path):
    actors = {2: ("t", "bea"), 1: ("t", "ana")}
    repos = {10: ("t", "ana/project")}
    pairs = {(2, 10), (1, 10)}
    write_all(tmp_path, actors, repos, pairs)

    def read(name: str) -> list[list[str]]:
        with open(tmp_path / name, encoding="utf-8", newline="") as f:
            return list(csv.reader(f))

    assert read("actors.csv") == [["id", "login"], ["1", "ana"], ["2", "bea"]]
    assert read("repos.csv") == [["id", "name"], ["10", "ana/project"]]
    assert read("actor_repo.csv") == [["actor_id", "repo_id"], ["1", "10"], ["2", "10"]]
