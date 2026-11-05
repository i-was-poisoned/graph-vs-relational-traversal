########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of tests/test_extract_csv.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute (pytest only looks for tests in tests/, as
# pytest.ini says). The real, "clean" file (with none of this commentary)
# is tests/test_extract_csv.py.
#
# This is the first test file to read: it explains the basics of pytest,
# which test_pipeline.py and test_loaders.py then reuse.
#
# HOW PYTEST WORKS, IN SHORT
#   - You run `python -m pytest` from the project folder.
#   - pytest reads pytest.ini, goes into tests/, and opens every file whose
#     name starts with "test_".
#   - In each file, it runs every function whose name starts with "test_".
#     Nobody has to call them or list them anywhere: the name is enough.
#   - Inside a test, `assert <something>` means "I claim this is true".
#     If it's true, nothing happens. If it's false, the test FAILS and
#     pytest shows both values, so you can see what went wrong.
#   - At the end it prints a summary, e.g. "24 passed in 1.70s".
#
# Its job in the project: check extract_csv.py, the heart of the
# pipeline, against the tricky cases we've already met in the real data:
# bots, an empty repo ({}), renamed users, repeated actor-repo pairs,
# events out of order, and compressed files.
########################################################################

"""Unit tests for scripts/extract_csv.py.

Each test builds a tiny GH Archive-like file (two or three made-up events) in a
temporary folder, so the tests run in milliseconds and need no downloaded data.

Run with:  python -m pytest
"""

# csv: to READ back the CSV files that write_all() writes (last test).
import csv

# gzip: to WRITE a compressed .json.gz test file, like the ones GH Archive
# publishes, so we can check that extract() reads those too.
import gzip

# json: json.dumps() turns a Python dict into one line of JSON text — the
# opposite of json.loads(), which extract_csv.py uses to read it back.
import json

from pathlib import Path

# The functions under test. This works only because pytest.ini says
# `pythonpath = scripts`: the scripts folder is added to the places Python
# searches, so `extract_csv` is found even though this file is in tests/.
from extract_csv import extract, is_bot, remember_latest, write_all


# ---------------------------------------------------------------------
# HELPERS (not tests: their names don't start with test_, so pytest
# doesn't run them on their own; the tests call them).
#
# make_event: builds one fake GH Archive event as a dict.
# Real events have dozens of fields (type, payload, org, ...), but
# extract_csv.py only reads these four: actor id and login, repo id and
# name, and created_at. A test only needs what the code under test reads.
# `created_at: str = "..."` is a default value: most tests don't care
# about the time, so they leave it out; the renaming test passes its own.
# ---------------------------------------------------------------------
def make_event(actor_id: int, login: str, repo_id: int, repo_name: str,
               created_at: str = "2026-08-27T15:00:00Z") -> dict:
    # Only the fields extract_csv.py reads; real events have many more.
    return {
        "actor": {"id": actor_id, "login": login},
        "repo": {"id": repo_id, "name": repo_name},
        "created_at": created_at,
    }


# ---------------------------------------------------------------------
# write_events: writes a list of events to a file, one JSON object per
# line, and gives back the file's path.
# ---------------------------------------------------------------------
def write_events(path: Path, events: list[dict]) -> Path:
    # One JSON object per line (JSON Lines), like GH Archive; compressed if the name ends in .gz.
    # "".join(...) glues the pieces together with nothing in between;
    # each piece is one event as JSON text plus a line break ("\n").
    text = "".join(json.dumps(event) + "\n" for event in events)
    if path.suffix == ".gz":
        # gzip.open(..., "wt"): "w" = write, "t" = text. We hand it plain
        # text and gzip compresses it on the way to the disk — the mirror
        # image of the "rt" that extract_csv.open_text() uses to read.
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


# ---------- is_bot ----------

# The simplest kind of test: call the function, assert the answer.
# Each test checks ONE thing, and its name says which, so when one fails
# the name alone tells you what broke.
def test_is_bot_true_for_bot_suffix():
    assert is_bot("dependabot[bot]")


# `assert not ...`: claim that the result is False.
def test_is_bot_false_for_normal_login():
    assert not is_bot("pedro")


def test_is_bot_false_when_bot_is_not_the_suffix():
    # Only the "[bot]" ending counts, not the word "bot" somewhere in the login.
    # A test may contain several asserts; it fails at the first one that
    # doesn't hold.
    assert not is_bot("robot")
    assert not is_bot("bot-builder")


# ---------- remember_latest ----------

# These three tests follow the example written above remember_latest()
# in extract_csv.py: first time, newer name, older name.
def test_remember_latest_stores_new_key():
    names = {}
    remember_latest(names, 7, "2026-08-27T15:10:00Z", "ana")
    # remember_latest returns nothing: it CHANGES the dict it's given.
    # So the test checks the dict afterwards.
    assert names == {7: ("2026-08-27T15:10:00Z", "ana")}


def test_remember_latest_newer_name_replaces_older():
    # The dict starts with a value already in it (the "before" state)...
    names = {7: ("2026-08-27T15:10:00Z", "ana")}
    remember_latest(names, 7, "2026-08-27T15:30:00Z", "ana-dev")
    # ...and we check the "after" state.
    assert names[7] == ("2026-08-27T15:30:00Z", "ana-dev")


def test_remember_latest_older_name_is_ignored():
    # Events can arrive out of order: an older event must not undo a newer name.
    names = {7: ("2026-08-27T15:30:00Z", "ana-dev")}
    remember_latest(names, 7, "2026-08-27T15:20:00Z", "ana")
    assert names[7] == ("2026-08-27T15:30:00Z", "ana-dev")


# ---------- extract ----------

# FIXTURES: `tmp_path` in the brackets is not a value we pass ourselves.
# When pytest sees a parameter with that exact name, it creates a new,
# empty temporary folder and passes its Path in. Each test gets its own
# folder, so tests can't disturb each other, and nobody has to clean up.
# `tmp_path / "hour.json"` is a file path inside that folder.
def test_extract_normal_event(tmp_path):
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project")])
    # extract() returns FOUR things (a tuple); this line unpacks them into
    # four names at once.
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
    # set(actors): the dict's KEYS as a set — here, which actor ids were
    # kept. Only ana (1); the bot (2) must not be there.
    assert set(actors) == {1}
    assert pairs == {(1, 10)}
    assert skipped_bots == 1


# Two fixtures this time. `caplog` ("capture log") collects everything
# written with the logging module during the test; caplog.text is all of
# it as one string, so we can check that the warning really appears.
def test_extract_skips_event_with_empty_repo(tmp_path, caplog):
    # The real case found on 2026-10-22: a ForkEvent whose repo was {} (no id, no name).
    # Written by hand instead of with make_event(), because make_event()
    # always fills in the repo.
    empty_repo = {"actor": {"id": 2, "login": "bea"}, "repo": {}, "created_at": "2026-08-27T15:05:00Z"}
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project"), empty_repo])
    # `_` is the usual name for "a value I don't need" (here, the bot count).
    actors, repos, pairs, _ = extract([file])
    assert set(actors) == {1}
    assert pairs == {(1, 10)}
    # `in` on strings: is this text somewhere inside the log?
    assert "Skipped 1 event(s) without an actor or repo id" in caplog.text


def test_extract_repeated_pair_counted_once(tmp_path):
    # Three events by the same actor on the same repo -> one connection.
    # `[x] * 3` repeats a list: [x, x, x]. A quick way to write the same
    # event three times.
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project")] * 3)
    _, _, pairs, _ = extract([file])
    assert pairs == {(1, 10)}


def test_extract_keeps_latest_login(tmp_path):
    # The newer event (15:30) comes FIRST in the file, the older one (15:10)
    # second — so this also checks that the order in the file doesn't
    # matter, only the created_at time.
    file = write_events(tmp_path / "hour.json", [
        make_event(1, "ana-dev", 10, "ana/project", "2026-08-27T15:30:00Z"),
        make_event(1, "ana", 10, "ana/project", "2026-08-27T15:10:00Z"),
    ])
    actors, _, _, _ = extract([file])
    # actors[1] is the tuple (created_at, login); [1] picks the login.
    assert actors[1][1] == "ana-dev"


def test_extract_reads_several_files_plain_and_gz(tmp_path):
    # Two files, like two hours of the live pipeline's window: one plain
    # .json and one compressed .json.gz (write_events compresses it because
    # of the name). extract() must read both and combine them.
    plain = write_events(tmp_path / "2026-10-20-5.json", [make_event(1, "ana", 10, "ana/project")])
    compressed = write_events(tmp_path / "2026-10-20-6.json.gz", [make_event(2, "bea", 20, "bea/tool")])
    actors, repos, pairs, _ = extract([plain, compressed])
    assert set(actors) == {1, 2}
    assert set(repos) == {10, 20}
    assert pairs == {(1, 10), (2, 20)}


# ---------- write_all / write_csv ----------

def test_write_all_writes_headers_and_sorted_rows(tmp_path):
    # Input in the "wrong" order on purpose (2 before 1), to check that
    # write_all sorts by id. The times are just "t": write_all doesn't
    # write them, so their value doesn't matter here.
    actors = {2: ("t", "bea"), 1: ("t", "ana")}
    repos = {10: ("t", "ana/project")}
    pairs = {(2, 10), (1, 10)}
    write_all(tmp_path, actors, repos, pairs)

    # A NESTED function: defined inside the test, used only by it. It
    # reads one of the three CSV files back as a list of rows, each row a
    # list of strings — csv.reader gives everything as text, which is why
    # the expected values below are "1" and "10" in quotes.
    # It can use tmp_path because a nested function sees the variables of
    # the function around it.
    def read(name: str) -> list[list[str]]:
        with open(tmp_path / name, encoding="utf-8", newline="") as f:
            return list(csv.reader(f))

    # Header first, then the rows sorted by id.
    assert read("actors.csv") == [["id", "login"], ["1", "ana"], ["2", "bea"]]
    assert read("repos.csv") == [["id", "name"], ["10", "ana/project"]]
    assert read("actor_repo.csv") == [["actor_id", "repo_id"], ["1", "10"], ["2", "10"]]
