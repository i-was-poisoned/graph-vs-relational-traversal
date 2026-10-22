"""Extract the benchmark's actor/repo graph from GH Archive files into CSV files.

Reads one or more JSON Lines files (plain .json or compressed .json.gz) once,
skips bot accounts (logins ending in "[bot]"), and writes three CSV files that
both databases are loaded from, so they always hold exactly the same data:

    actors.csv       id, login             one row per actor (most recent login)
    repos.csv        id, name              one row per repo (most recent name)
    actor_repo.csv   actor_id, repo_id     one row per actor-repo pair, no repeats

Usage:
    python scripts/extract_csv.py
    python scripts/extract_csv.py --file data/2026-08-27-15.json --out-dir data/csv
    python scripts/extract_csv.py --file data/live/raw/*.json.gz --out-dir data/live/csv
"""

import argparse
import csv
import gzip
import json
import logging
from pathlib import Path
from typing import TextIO

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FILE = PROJECT_DIR / "data" / "2026-08-27-15.json"
DEFAULT_OUT_DIR = PROJECT_DIR / "data" / "csv"
BOT_SUFFIX = "[bot]"

log = logging.getLogger(__name__)


def is_bot(login: str) -> bool:
    return login.endswith(BOT_SUFFIX)


# Example: the same actor (id 7) renamed from "ana" to "ana-dev"; events arrive out of order.
#   names = {}
#   remember_latest(names, 7, "2026-08-27T15:10:00Z", "ana")      # first time  -> {7: ("...15:10...", "ana")}
#   remember_latest(names, 7, "2026-08-27T15:30:00Z", "ana-dev")  # newer       -> {7: ("...15:30...", "ana-dev")}
#   remember_latest(names, 7, "2026-08-27T15:20:00Z", "ana")      # older: kept -> {7: ("...15:30...", "ana-dev")}
def remember_latest(names: dict[int, tuple[str, str]], key: int, created_at: str, name: str) -> None:
    # Keep the name from the most recent event: logins and repo names can change.
    # created_at is ISO 8601 text, so comparing the strings compares the times.
    if key not in names or created_at >= names[key][0]:
        names[key] = (created_at, name)


def open_text(path: Path) -> TextIO:
    # .json.gz files are read compressed, without first unpacking them to disk.
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def extract(file_paths: list[Path]) -> tuple[dict[int, tuple[str, str]], dict[int, tuple[str, str]], set[tuple[int, int]], int]:
    actors: dict[int, tuple[str, str]] = {}
    repos: dict[int, tuple[str, str]] = {}
    pairs: set[tuple[int, int]] = set()
    skipped_bot_events = 0
    skipped_without_id = 0

    for file_path in file_paths:
        with open_text(file_path) as f:
            for line in f:
                event = json.loads(line)
                actor = event["actor"]
                repo = event["repo"]
                # A few events come with an empty repo ({}), e.g. forks of repos deleted
                # since: without ids there is no node or connection to create.
                if "id" not in actor or "id" not in repo:
                    skipped_without_id += 1
                    continue
                if is_bot(actor["login"]):
                    skipped_bot_events += 1
                    continue
                remember_latest(actors, actor["id"], event["created_at"], actor["login"])
                remember_latest(repos, repo["id"], event["created_at"], repo["name"])
                pairs.add((actor["id"], repo["id"]))

    if skipped_without_id:
        log.warning("Skipped %d event(s) without an actor or repo id", skipped_without_id)
    return actors, repos, pairs, skipped_bot_events


def write_csv(path: Path, header: list[str], rows: list[tuple]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {path.name:<16} {len(rows):>7} rows")


def write_all(out_dir: Path, actors: dict[int, tuple[str, str]], repos: dict[int, tuple[str, str]],
              pairs: set[tuple[int, int]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Sorted by id so the same input always produces byte-for-byte the same files.
    write_csv(out_dir / "actors.csv", ["id", "login"],
              [(actor_id, login) for actor_id, (_, login) in sorted(actors.items())])
    write_csv(out_dir / "repos.csv", ["id", "name"],
              [(repo_id, name) for repo_id, (_, name) in sorted(repos.items())])
    write_csv(out_dir / "actor_repo.csv", ["actor_id", "repo_id"], sorted(pairs))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, nargs="+", default=[DEFAULT_FILE],
                         help=f"One or more .json or .json.gz files (default: {DEFAULT_FILE})")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"Folder to write the CSV files to (default: {DEFAULT_OUT_DIR})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    actors, repos, pairs, skipped_bot_events = extract(args.file)
    print(f"Read {len(args.file)} file(s). Skipped {skipped_bot_events} bot events. Writing to {args.out_dir}:")
    write_all(args.out_dir, actors, repos, pairs)


if __name__ == "__main__":
    main()
