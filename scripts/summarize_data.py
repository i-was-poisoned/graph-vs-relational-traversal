"""Summarize a downloaded GH Archive JSON Lines file.

Reads the full file once and reports, in three sections: general totals
(split into bot and non-bot), then the same analysis twice — with bots and
without bots — covering the event type breakdown, the most active actors and
repos, and how connected actors and repos are to each other. A first read on
data volume and connectivity before modeling the data relationally or as a
graph.

Usage:
    python scripts/summarize_data.py
    python scripts/summarize_data.py --file data/2026-08-27-15.json --top 10
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


class Stats:
    """All the counts for one group of events (e.g. all events, or non-bot events only)."""

    def __init__(self) -> None:
        self.total_events = 0
        self.event_type_counts: Counter[str] = Counter()
        self.actor_event_counts: Counter[str] = Counter()
        self.repo_event_counts: Counter[str] = Counter()
        self.actor_repos: defaultdict[str, set[str]] = defaultdict(set)
        self.repo_actors: defaultdict[str, set[str]] = defaultdict(set)

    def add(self, event_type: str, actor: str, repo: str) -> None:
        self.total_events += 1
        self.event_type_counts[event_type] += 1
        self.actor_event_counts[actor] += 1
        self.repo_event_counts[repo] += 1
        self.actor_repos[actor].add(repo)
        self.repo_actors[repo].add(actor)


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:5.1f}%"


def print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_general(all_events: Stats, non_bot: Stats) -> None:
    total = all_events.total_events
    bot_events = total - non_bot.total_events
    num_actors = len(all_events.actor_event_counts)
    non_bot_actors = len(non_bot.actor_event_counts)
    num_repos = len(all_events.repo_event_counts)
    non_bot_repos = len(non_bot.repo_event_counts)

    print_header("GENERAL")
    print(f"Total events:     {total:>7}")
    print(f"  Bot events:     {bot_events:>7} ({pct(bot_events, total)})")
    print(f"  Non-bot events: {non_bot.total_events:>7} ({pct(non_bot.total_events, total)})")
    print(f"Unique actors:    {num_actors:>7}")
    print(f"  Bot actors:     {num_actors - non_bot_actors:>7} "
          f"({pct(num_actors - non_bot_actors, num_actors)})")
    print(f"  Non-bot actors: {non_bot_actors:>7} ({pct(non_bot_actors, num_actors)})")
    print(f"Unique repos:     {num_repos:>7}")
    print(f"  Only bots made events in it:     {num_repos - non_bot_repos:>7} "
          f"({pct(num_repos - non_bot_repos, num_repos)})")
    print(f"  At least 1 non-bot made events:  {non_bot_repos:>7} "
          f"({pct(non_bot_repos, num_repos)})")


def print_analysis(title: str, stats: Stats, top_n: int) -> None:
    print_header(title)

    print("Event types:")
    type_width = max(len(event_type) for event_type in stats.event_type_counts)
    for event_type, count in stats.event_type_counts.most_common():
        print(f"  {event_type:<{type_width}} {count:>7} ({pct(count, stats.total_events)})")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in stats.actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in stats.repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")

    shared_repos = [repo for repo, actors in stats.repo_actors.items() if len(actors) >= 2]
    multi_repo_actors = [actor for actor, repos in stats.actor_repos.items() if len(repos) >= 2]
    connected_actors = {actor for repo in shared_repos for actor in stats.repo_actors[repo]}
    num_actors = len(stats.actor_repos)
    num_repos = len(stats.repo_actors)

    print("\nConnectivity:")
    print(f"  Repos with 2+ different actors:           {len(shared_repos):>6} "
          f"({pct(len(shared_repos), num_repos)} of repos)")
    print(f"  Actors who made events in 2+ repos:       {len(multi_repo_actors):>6} "
          f"({pct(len(multi_repo_actors), num_actors)} of actors)")
    print(f"  Actors sharing a repo with another actor: {len(connected_actors):>6} "
          f"({pct(len(connected_actors), num_actors)} of actors)")

    repos_per_actor = Counter({actor: len(repos) for actor, repos in stats.actor_repos.items()})
    print(f"\nTop {top_n} actors by number of different repos they made events in:")
    for actor, count in repos_per_actor.most_common(top_n):
        print(f"  {actor:<30} {count:>5} different repos")

    actors_per_repo = Counter({repo: len(actors) for repo, actors in stats.repo_actors.items()})
    print(f"\nTop {top_n} repos by number of different actors who made events in them:")
    for repo, count in actors_per_repo.most_common(top_n):
        print(f"  {repo:<40} {count:>5} different actors")


def summarize(file_path: Path, top_n: int) -> None:
    all_events = Stats()
    non_bot = Stats()

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            event_type = event["type"]
            actor = event["actor"]["login"]
            repo = event["repo"]["name"]
            all_events.add(event_type, actor, repo)
            if not is_bot(actor):
                non_bot.add(event_type, actor, repo)

    print_general(all_events, non_bot)
    print_analysis("ANALYSIS WITH BOTS (all events)", all_events, top_n)
    print_analysis(f"ANALYSIS WITHOUT BOTS (logins ending in '{BOT_SUFFIX}' removed)",
                   non_bot, top_n)


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
