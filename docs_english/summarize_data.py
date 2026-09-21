########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/summarize_data.py.
# It is NOT meant to be run as part of the project pipeline — it lives in
# docs_english/ because its purpose is to teach, not to execute. The real, "clean"
# script (with none of this commentary) is scripts/summarize_data.py.
#
# This file assumes you've already read docs_english/download_gharchive.py and
# docs_english/peek_data.py — argparse, Path, f-strings, dict/nested-dict
# lookups, main(), and the __name__ guard are NOT re-explained from scratch
# here. This file focuses on what's NEW in summarize_data.py: reading a
# whole file instead of a handful of lines, and counting/aggregating with
# collections.Counter.
########################################################################

"""Summarize a downloaded GH Archive JSON Lines file.

Reads the full file once and reports total event count, the event type
breakdown, and unique actor/repo counts — a first read on data volume and
connectivity before modeling the data relationally or as a graph.

Usage:
    python scripts/summarize_data.py
    python scripts/summarize_data.py --file data/2026-08-27-15.json --top 10
"""

# argparse, Path, json: already explained in docs_english/download_gharchive.py
# and docs_english/peek_data.py.
import argparse
import json

# ---------------------------------------------------------------------
# from collections import Counter
#
# `collections` is a standard-library module of specialized container
# types that build on the built-in dict/list/tuple. `Counter` is a dict
# subclass purpose-built for counting things: every key defaults to 0
# the first time you touch it, so `counter[key] += 1` works even on a
# key you've never seen before — no need to write
#     if key not in counter:
#         counter[key] = 0
#     counter[key] += 1
# every time, the way you would with a plain dict.
#
# We need this three times in this script: counting how many events
# there are of each `type`, how many events each actor produced, and how
# many events each repo received.
# ---------------------------------------------------------------------
from collections import Counter
from pathlib import Path

# Same Path-building technique as DEFAULT_FILE in peek_data.py — see that
# file's annotated copy for the full explanation.
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# How many top actors/repos to show if --top isn't specified. 5 is enough
# to spot patterns (e.g. "the busiest accounts are all bots") without
# flooding the terminal.
DEFAULT_TOP = 5


# ---------------------------------------------------------------------
# def summarize(file_path: Path, top_n: int) -> None:
# Same two-required-parameters shape as peek()'s (file_path, num_lines).
# ---------------------------------------------------------------------
def summarize(file_path: Path, top_n: int) -> None:
    # A plain int, incremented once per line. Simpler than len()-ing a
    # list of every event, and doesn't require holding all 69k+ events in
    # memory at once just to count them.
    total_events = 0

    # ---------------------------------------------------------------
    # Counter[str]: the type hint reads as "a Counter whose keys are
    # strings" (the values are always the counts, i.e. ints — Counter
    # doesn't need you to spell that out separately).
    #
    # Three separate counters, one per thing being tallied:
    #   event_type_counts   key = event["type"], e.g. "PushEvent"
    #   actor_event_counts  key = event["actor"]["login"], e.g. "octocat"
    #   repo_event_counts   key = event["repo"]["name"], e.g. "octocat/Hello-World"
    # ---------------------------------------------------------------
    event_type_counts: Counter[str] = Counter()
    actor_event_counts: Counter[str] = Counter()
    repo_event_counts: Counter[str] = Counter()

    # ---------------------------------------------------------------
    # Same `with open(..., "r", encoding="utf-8") as f:` pattern as
    # peek() — see peek_data.py's annotated copy for why text mode and
    # explicit UTF-8 are the right choices here.
    #
    # The key difference from peek(): there is NO `if i >= num_lines:
    # break` here. peek() deliberately stops early because it only wants
    # a handful of sample events; summarize() deliberately reads every
    # single line, because a count or percentage computed from only the
    # first few hundred events wouldn't represent the whole file.
    # ---------------------------------------------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        # No enumerate() needed here — unlike peek(), summarize() never
        # prints a per-line index, so there's no use for the loop
        # position, only the parsed event itself.
        for line in f:
            event = json.loads(line)
            total_events += 1

            # ---------------------------------------------------------
            # counter[key] += 1
            #
            # This is the payoff of using Counter instead of a plain
            # dict: the first time a given event type / actor / repo is
            # seen, Counter silently treats the missing key as 0, so
            # `+= 1` takes it to 1. Every later occurrence just adds 1
            # to whatever it already was. By the time the loop finishes,
            # each Counter holds the full tally for every distinct key
            # it ever saw.
            # ---------------------------------------------------------
            event_type_counts[event["type"]] += 1
            actor_event_counts[event["actor"]["login"]] += 1
            repo_event_counts[event["repo"]["name"]] += 1

    print(f"Total events: {total_events}")

    # ---------------------------------------------------------------
    # len(actor_event_counts)
    #
    # Because Counter is a dict subclass, len() on it returns the number
    # of DISTINCT keys, not the sum of the counts. So this is exactly
    # "how many unique actors/repos appeared in the file" — the sum of
    # all values would instead just equal total_events again, which
    # isn't what we want here.
    # ---------------------------------------------------------------
    print(f"Unique actors: {len(actor_event_counts)}")
    print(f"Unique repos: {len(repo_event_counts)}")

    print("\nEvent types:")
    # ---------------------------------------------------------------
    # .most_common()
    #
    # A method only Counter has (plain dicts don't have it). Called with
    # no argument, it returns EVERY (key, count) pair as a list of
    # tuples, sorted from most frequent to least frequent — exactly the
    # order you want when eyeballing "what dominates this dataset."
    # Called as .most_common(n) (used below for actors/repos), it
    # returns only the top n pairs, which is more efficient than sorting
    # everything and slicing when you only need a handful of results.
    # ---------------------------------------------------------------
    for event_type, count in event_type_counts.most_common():
        pct = 100 * count / total_events

        # ---------------------------------------------------------------
        # f"{event_type:<25} {count:>7} ({pct:5.1f}%)"
        #
        # The part after the colon inside {} is a FORMAT SPEC — it
        # controls how the value is padded/aligned when converted to
        # text, not just what the value is.
        #   <25   left-align, pad with spaces to at least 25 characters
        #         wide. Used for event_type so the numbers that follow
        #         it line up in a column regardless of how long the
        #         event type name is.
        #   >7    right-align, pad to at least 7 characters wide. Used
        #         for count so the digits line up on their right edge,
        #         the way numbers are conventionally aligned in a table.
        #   5.1f  a FIXED-POINT float, at least 5 characters wide total,
        #         with exactly 1 digit after the decimal point (e.g.
        #         " 95.3" or "  0.1"). Used for the percentage so every
        #         row shows the same number of decimal places.
        # None of this changes the underlying value — only how it's
        # rendered as text.
        # ---------------------------------------------------------------
        print(f"  {event_type:<25} {count:>7} ({pct:5.1f}%)")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")


# ---------------------------------------------------------------------
# parse_args(): same overall pattern as peek_data.py's version. The one
# thing worth calling out is that --top plays the same role --lines
# played there (a plain positive integer, no `choices=` restriction) —
# just applied to "how many top actors/repos to show" instead of "how
# many sample events to print".
# ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                         help=f"How many top actors/repos to show (default: {DEFAULT_TOP})")
    return parser.parse_args()


# main() and the `if __name__ == "__main__":` guard: identical purpose and
# mechanics to the other two scripts — see download_gharchive.py's
# annotated copy for the full explanation.
def main() -> None:
    args = parse_args()
    summarize(args.file, args.top)


if __name__ == "__main__":
    main()
