"""Extract the benchmark's actor/repo graph from a GH Archive file into CSV files.

Reads the JSON Lines file once, skips bot accounts (logins ending in "[bot]"),
and writes three CSV files that both databases are loaded from, so they always
hold exactly the same data:

    actors.csv       id, login             one row per actor (most recent login)
    repos.csv        id, name              one row per repo (most recent name)
    actor_repo.csv   actor_id, repo_id     one row per actor-repo pair, no repeats

Usage:
    python scripts/extract_csv.py
    python scripts/extract_csv.py --file data/2026-08-27-15.json --out-dir data/csv
"""

import argparse
import csv
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FILE = PROJECT_DIR / "data" / "2026-08-27-15.json"
DEFAULT_OUT_DIR = PROJECT_DIR / "data" / "csv"
BOT_SUFFIX = "[bot]"


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


def extract(file_path: Path) -> tuple[dict[int, tuple[str, str]], dict[int, tuple[str, str]], set[tuple[int, int]], int]:
    actors: dict[int, tuple[str, str]] = {}
    repos: dict[int, tuple[str, str]] = {}
    pairs: set[tuple[int, int]] = set()
    skipped_bot_events = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            actor = event["actor"]
            repo = event["repo"]
            if is_bot(actor["login"]):
                skipped_bot_events += 1
                continue
            remember_latest(actors, actor["id"], event["created_at"], actor["login"])
            remember_latest(repos, repo["id"], event["created_at"], repo["name"])
            pairs.add((actor["id"], repo["id"]))

    return actors, repos, pairs, skipped_bot_events


def write_csv(path: Path, header: list[str], rows: list[tuple]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {path.name:<16} {len(rows):>7} rows")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"Folder to write the CSV files to (default: {DEFAULT_OUT_DIR})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    actors, repos, pairs, skipped_bot_events = extract(args.file)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Skipped {skipped_bot_events} bot events. Writing to {args.out_dir}:")
    # Sorted by id so the same input always produces byte-for-byte the same files.
    write_csv(args.out_dir / "actors.csv", ["id", "login"],
              [(actor_id, login) for actor_id, (_, login) in sorted(actors.items())])
    write_csv(args.out_dir / "repos.csv", ["id", "name"],
              [(repo_id, name) for repo_id, (_, name) in sorted(repos.items())])
    write_csv(args.out_dir / "actor_repo.csv", ["actor_id", "repo_id"], sorted(pairs))


if __name__ == "__main__":
    main()
