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
# whole file instead of a handful of lines, counting/aggregating with
# collections.Counter, tracking DISTINCT partners with sets and
# collections.defaultdict, skipping bot events with `continue`, and
# measuring how connected actors and repos are to each other.
########################################################################

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

# argparse, Path, json: already explained in docs_english/download_gharchive.py
# and docs_english/peek_data.py.
import argparse
import json

# ---------------------------------------------------------------------
# from collections import Counter, defaultdict
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
#
# `defaultdict` is the same idea, generalized: a dict where a missing key
# is automatically created with a starting value of your choice. Here we
# use defaultdict(set), so a missing key starts as an EMPTY SET (see
# actor_repos / repo_actors below for why we need sets).
# ---------------------------------------------------------------------
from collections import Counter, defaultdict
from pathlib import Path

# Same Path-building technique as DEFAULT_FILE in peek_data.py — see that
# file's annotated copy for the full explanation.
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# How many top actors/repos to show if --top isn't specified. 5 is enough
# to spot patterns (e.g. "the busiest accounts are all bots") without
# flooding the terminal.
DEFAULT_TOP = 5

# ---------------------------------------------------------------------
# BOT_SUFFIX = "[bot]"
#
# On GitHub, automated accounts created as "GitHub Apps" always have a
# login ending in "[bot]" (github-actions[bot], dependabot[bot], ...).
# That suffix is the simplest reliable way to recognise them. It is NOT
# a perfect filter: some automated accounts don't use it (e.g. the login
# "Copilot"), so --exclude-bots removes the official bots, not every
# automated account.
# ---------------------------------------------------------------------
BOT_SUFFIX = "[bot]"


# ---------------------------------------------------------------------
# def is_bot(login: str) -> bool:
#
# A tiny helper that answers one yes/no question. `-> bool` means it
# returns True or False. str.endswith() checks whether the text finishes
# with the given suffix: "dependabot[bot]".endswith("[bot]") is True,
# "octocat".endswith("[bot]") is False. Putting this in its own function
# gives the rule a name, so if the definition of "bot" ever changes, it
# only changes here.
# ---------------------------------------------------------------------
def is_bot(login: str) -> bool:
    return login.endswith(BOT_SUFFIX)


# ---------------------------------------------------------------------
# def summarize(file_path: Path, top_n: int, exclude_bots: bool) -> None:
# Same shape as peek()'s (file_path, num_lines), plus a third parameter:
# exclude_bots, a True/False switch that comes from the --exclude-bots
# command-line flag (see parse_args() below).
# ---------------------------------------------------------------------
def summarize(file_path: Path, top_n: int, exclude_bots: bool) -> None:
    # A plain int, incremented once per line. Simpler than len()-ing a
    # list of every event, and doesn't require holding all 69k+ events in
    # memory at once just to count them.
    total_events = 0

    # How many events were skipped because their actor is a bot. Only
    # printed when --exclude-bots is used, so you can see how much data
    # the filter removed.
    skipped_bot_events = 0

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
    # actor_repos / repo_actors: defaultdict(set)
    #
    # The Counters above count EVENTS. But for a graph, the question is
    # different: "how many DIFFERENT repos did this actor touch?" and
    # "how many DIFFERENT actors touched this repo?". If ana pushes 10
    # times to the same repo, that's 10 events but still only 1 repo.
    #
    # A SET is a collection that keeps each item only once: adding
    # something that's already there does nothing. So:
    #
    #     s = set()
    #     s.add("ana/app"); s.add("ana/app"); s.add("luis/web")
    #     s        # {"ana/app", "luis/web"}  -> len(s) == 2
    #
    #   actor_repos  key = actor login, value = set of repo names
    #   repo_actors  key = repo name,   value = set of actor logins
    #
    # These two dicts ARE the actor <-> repo graph, seen from each side.
    # defaultdict(set) means the first time an actor/repo appears, its
    # empty set is created automatically (same convenience as Counter
    # starting at 0).
    # ---------------------------------------------------------------
    actor_repos: defaultdict[str, set[str]] = defaultdict(set)
    repo_actors: defaultdict[str, set[str]] = defaultdict(set)

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
        # for line in f:
        #
        # This is a LOOP: a block of code that REPEATS. Read it as "for
        # each line in the file f, do the indented lines below". Those
        # indented lines are written once but run once PER LINE of the
        # file — 69,429 times for this project's hour, one per event.
        # Think of counting votes from a ballot box: take one ballot, add
        # a tally mark next to its name, go back and take the next one,
        # until the box is empty. When the file runs out of lines, the
        # loop ends and Python carries on with the first non-indented
        # line after it (the print() calls below).
        #
        # No enumerate() needed here — unlike peek(), summarize() never
        # prints a per-line index, so there's no use for the loop
        # position, only the parsed event itself.
        for line in f:
            event = json.loads(line)

            # Pull the two names out once and give them short variable
            # names, since each is used several times below.
            actor = event["actor"]["login"]
            repo = event["repo"]["name"]

            # ---------------------------------------------------------
            # if exclude_bots and is_bot(actor): ... continue
            #
            # `continue` means "skip the rest of the loop body for THIS
            # line and jump straight to the next one". Compare with
            # peek_data.py's `break`, which leaves the loop entirely:
            #   break     -> stop reading the file altogether
            #   continue  -> ignore this one event, keep reading
            # So a bot event is counted in skipped_bot_events and then
            # never reaches the counters below. Without --exclude-bots,
            # exclude_bots is False, the whole condition is False, and
            # every event goes through as before.
            # ---------------------------------------------------------
            if exclude_bots and is_bot(actor):
                skipped_bot_events += 1
                continue
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
            actor_event_counts[actor] += 1
            repo_event_counts[repo] += 1

            # Record the connection in both directions. Because these
            # are sets, repeated events between the same actor and repo
            # don't add duplicates — only NEW partners grow the set.
            actor_repos[actor].add(repo)
            repo_actors[repo].add(actor)

    if exclude_bots:
        print(f"Bot events excluded: {skipped_bot_events}")
    print(f"Total events: {total_events}")

    # ---------------------------------------------------------------
    # len(actor_event_counts)
    #
    # Because Counter is a dict subclass, len() on it returns the number
    # of DISTINCT keys, not the sum of the counts. So this is exactly
    # "how many unique actors/repos appeared in the file" — the sum of
    # all values would instead just equal total_events again, which
    # isn't what we want here.
    #
    # Worked example: if the file only had 6 events, made by the actors
    # ana, luis, ana, marta, ana, luis (in that order), the loop above
    # would leave
    #
    #     actor_event_counts == Counter({"ana": 3, "luis": 2, "marta": 1})
    #
    # Each entry has a KEY (the name) and a VALUE (how many times that
    # name appeared). Then:
    #
    #     len(actor_event_counts)            # 3 -> ana, luis, marta
    #     sum(actor_event_counts.values())   # 6 -> 3 + 2 + 1
    #
    # len() answers "how many DIFFERENT actors?" (ana counts once, even
    # with 3 events). The sum answers "how many events?" — and since
    # every event has exactly one actor, that always equals total_events,
    # so it would tell us nothing new.
    #
    # "Subclass of dict" just means Counter IS a dictionary with extra
    # features added (.most_common(), missing keys starting at 0). So
    # anything that works on a plain dict — like len() counting its
    # keys — works on a Counter exactly the same way.
    # ---------------------------------------------------------------
    print(f"Unique actors: {len(actor_event_counts)}")
    print(f"Unique repos: {len(repo_event_counts)}")

    print("\nEvent types:")
    # ---------------------------------------------------------------
    # type_width = max(len(event_type) for event_type in event_type_counts)
    #
    # The width of the event-type column, computed from the data instead
    # of being fixed. An earlier version used a fixed width of 25, and
    # "PullRequestReviewCommentEvent" (29 characters) didn't fit, which
    # pushed its numbers out of line. Here we measure the length of every
    # event type name and take the longest one (max), so the column is
    # always exactly wide enough.
    # ---------------------------------------------------------------
    type_width = max(len(event_type) for event_type in event_type_counts)

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
        # f"{event_type:<{type_width}} {count:>7} ({pct:5.1f}%)"
        #
        # The part after the colon inside {} is a FORMAT SPEC — it
        # controls how the value is padded/aligned when converted to
        # text, not just what the value is.
        #   <{type_width}  left-align, pad with spaces to type_width
        #         characters. The inner {type_width} is replaced by its
        #         value first (e.g. 29), so this becomes <29. Used for
        #         event_type so the numbers that follow it line up in a
        #         column regardless of how long the event type name is.
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
        print(f"  {event_type:<{type_width}} {count:>7} ({pct:5.1f}%)")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")

    # ---------------------------------------------------------------
    # Connectivity: can you actually WALK through this graph?
    #
    # The benchmark walks actor -> repo -> actor -> repo. Each step from
    # a repo to "another actor" only works if that repo was touched by
    # at least 2 different actors; otherwise the walk is stuck. These
    # three numbers measure how often that's possible:
    #
    #   shared_repos       repos with 2+ distinct actors — the only
    #                      "bridges" from one actor to another.
    #   multi_repo_actors  actors who touched 2+ repos — the only
    #                      actors from which a walk can branch out to a
    #                      different repo.
    #   connected_actors   every actor who appears in at least one
    #                      shared repo, i.e. who has at least one
    #                      neighbour actor. Everyone else is an island.
    #
    # Syntax used:
    #   [x for x, y in d.items() if cond]   a LIST COMPREHENSION: a
    #       one-line loop that builds a list, keeping only the items for
    #       which cond is True. .items() gives (key, value) pairs.
    #   {a for r in shared_repos for a in repo_actors[r]}   a SET
    #       COMPREHENSION with two loops: for every shared repo, take
    #       every actor in it. Being a set, an actor who is in several
    #       shared repos is only counted once.
    # ---------------------------------------------------------------
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

    # ---------------------------------------------------------------
    # repos_per_actor = Counter({actor: len(repos) for ...})
    #
    # {k: v for ...} is a DICT COMPREHENSION: a one-line loop that builds
    # a dict. Here it turns "actor -> set of repos" into "actor -> HOW
    # MANY repos". Wrapping it in Counter(...) is just so we can reuse
    # .most_common(top_n) to get the top ones, sorted.
    #
    # This ranking matters more than "most events": an account that
    # touches hundreds of DIFFERENT repos acts as a hub that links
    # otherwise unrelated parts of the graph — which is exactly what
    # bots like github-actions[bot] turn out to do.
    # ---------------------------------------------------------------
    repos_per_actor = Counter({actor: len(repos) for actor, repos in actor_repos.items()})
    print(f"\nTop {top_n} actors by distinct repos touched:")
    for actor, count in repos_per_actor.most_common(top_n):
        print(f"  {actor:<30} {count:>5} repos")

    # Same idea from the repo side: the repos with the most distinct
    # actors are the busiest "meeting points" in the graph.
    actors_per_repo = Counter({repo: len(actors) for repo, actors in repo_actors.items()})
    print(f"\nTop {top_n} repos by distinct actors:")
    for repo, count in actors_per_repo.most_common(top_n):
        print(f"  {repo:<40} {count:>5} actors")


# ---------------------------------------------------------------------
# parse_args(): same overall pattern as peek_data.py's version. Two
# things worth calling out:
#
#   --top plays the same role --lines played there (a plain positive
#   integer, no `choices=` restriction) — just applied to "how many top
#   actors/repos to show" instead of "how many sample events to print".
#
#   action="store_true" (for --exclude-bots)
#     A FLAG: an option that takes no value. If you write --exclude-bots
#     on the command line, args.exclude_bots is True; if you leave it
#     out, it's False. argparse also turns the dash into an underscore
#     (--exclude-bots -> args.exclude_bots), because a dash isn't
#     allowed in a Python variable name.
# ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                         help=f"How many top actors/repos to show (default: {DEFAULT_TOP})")
    parser.add_argument("--exclude-bots", action="store_true",
                         help=f"Skip events whose actor login ends with '{BOT_SUFFIX}'")
    return parser.parse_args()


# main() and the `if __name__ == "__main__":` guard: identical purpose and
# mechanics to the other two scripts — see download_gharchive.py's
# annotated copy for the full explanation.
def main() -> None:
    args = parse_args()
    summarize(args.file, args.top, args.exclude_bots)


if __name__ == "__main__":
    main()
