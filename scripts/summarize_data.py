"""Summarize a downloaded GH Archive JSON Lines file.

Reads the full file once and reports total event count, the event type
breakdown, unique actor/repo counts, and how connected actors and repos are
to each other — a first read on data volume and connectivity before modeling
the data relationally or as a graph.

Usage:
    python scripts/summarize_data.py
    python scripts/summarize_data.py --file data/2026-08-27-15.json --top 10
    python scripts/summarize_data.py --exclude-bots
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"
DEFAULT_TOP = 5
BOT_SUFFIX = "[bot]"


def is_bot(login: str) -> bool:
    return login.endswith(BOT_SUFFIX)


def summarize(file_path: Path, top_n: int, exclude_bots: bool) -> None:
    total_events = 0
    skipped_bot_events = 0
    event_type_counts: Counter[str] = Counter()
    actor_event_counts: Counter[str] = Counter()
    repo_event_counts: Counter[str] = Counter()
    actor_repos: defaultdict[str, set[str]] = defaultdict(set)
    repo_actors: defaultdict[str, set[str]] = defaultdict(set)

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            actor = event["actor"]["login"]
            repo = event["repo"]["name"]
            if exclude_bots and is_bot(actor):
                skipped_bot_events += 1
                continue
            total_events += 1
            event_type_counts[event["type"]] += 1
            actor_event_counts[actor] += 1
            repo_event_counts[repo] += 1
            actor_repos[actor].add(repo)
            repo_actors[repo].add(actor)

    if exclude_bots:
        print(f"Bot events excluded: {skipped_bot_events}")
    print(f"Total events: {total_events}")
    print(f"Unique actors: {len(actor_event_counts)}")
    print(f"Unique repos: {len(repo_event_counts)}")

    print("\nEvent types:")
    type_width = max(len(event_type) for event_type in event_type_counts)
    for event_type, count in event_type_counts.most_common():
        pct = 100 * count / total_events
        print(f"  {event_type:<{type_width}} {count:>7} ({pct:5.1f}%)")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")

    shared_repos = [repo for repo, actors in repo_actors.items() if len(actors) >= 2]
    multi_repo_actors = [actor for actor, repos in actor_repos.items() if len(repos) >= 2]
    connected_actors = {actor for repo in shared_repos for actor in repo_actors[repo]}
    num_actors = len(actor_repos)
    num_repos = len(repo_actors)

    print("\nConnectivity:")
    print(f"  Repos with 2+ distinct actors:         {len(shared_repos):>6} "
          f"({100 * len(shared_repos) / num_repos:5.1f}% of repos)")
    print(f"  Actors who touched 2+ repos:           {len(multi_repo_actors):>6} "
          f"({100 * len(multi_repo_actors) / num_actors:5.1f}% of actors)")
    print(f"  Actors sharing a repo with another one: {len(connected_actors):>5} "
          f"({100 * len(connected_actors) / num_actors:5.1f}% of actors)")

    repos_per_actor = Counter({actor: len(repos) for actor, repos in actor_repos.items()})
    print(f"\nTop {top_n} actors by distinct repos touched:")
    for actor, count in repos_per_actor.most_common(top_n):
        print(f"  {actor:<30} {count:>5} repos")

    actors_per_repo = Counter({repo: len(actors) for repo, actors in repo_actors.items()})
    print(f"\nTop {top_n} repos by distinct actors:")
    for repo, count in actors_per_repo.most_common(top_n):
        print(f"  {repo:<40} {count:>5} actors")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                         help=f"How many top actors/repos to show (default: {DEFAULT_TOP})")
    parser.add_argument("--exclude-bots", action="store_true",
                         help=f"Skip events whose actor login ends with '{BOT_SUFFIX}'")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summarize(args.file, args.top, args.exclude_bots)


if __name__ == "__main__":
    main()
