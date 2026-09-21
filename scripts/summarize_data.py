"""Summarize a downloaded GH Archive JSON Lines file.

Reads the full file once and reports total event count, the event type
breakdown, and unique actor/repo counts — a first read on data volume and
connectivity before modeling the data relationally or as a graph.

Usage:
    python scripts/summarize_data.py
    python scripts/summarize_data.py --file data/2026-08-27-15.json --top 10
"""

import argparse
import json
from collections import Counter
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"
DEFAULT_TOP = 5


def summarize(file_path: Path, top_n: int) -> None:
    total_events = 0
    event_type_counts: Counter[str] = Counter()
    actor_event_counts: Counter[str] = Counter()
    repo_event_counts: Counter[str] = Counter()

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            total_events += 1
            event_type_counts[event["type"]] += 1
            actor_event_counts[event["actor"]["login"]] += 1
            repo_event_counts[event["repo"]["name"]] += 1

    print(f"Total events: {total_events}")
    print(f"Unique actors: {len(actor_event_counts)}")
    print(f"Unique repos: {len(repo_event_counts)}")

    print("\nEvent types:")
    for event_type, count in event_type_counts.most_common():
        pct = 100 * count / total_events
        print(f"  {event_type:<25} {count:>7} ({pct:5.1f}%)")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                         help=f"How many top actors/repos to show (default: {DEFAULT_TOP})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summarize(args.file, args.top)


if __name__ == "__main__":
    main()
