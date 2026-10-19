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
# collections.defaultdict, grouping all those counts in a CLASS so the
# same analysis can be run twice (with and without bots), and measuring
# how connected actors and repos are to each other.
#
# The output has three sections:
#   1. GENERAL                 totals, split into bots and non-bots
#   2. ANALYSIS WITH BOTS      every event
#   3. ANALYSIS WITHOUT BOTS   the same analysis, bot events removed
# Sections 2 and 3 print exactly the same things, so they can be
# compared side by side.
########################################################################

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
# We need this three times in each analysis: counting how many events
# there are of each `type`, how many events each actor produced, and how
# many events each repo received.
#
# `defaultdict` is the same idea, generalized: a dict where a missing key
# is automatically created with a starting value of your choice. Here we
# use defaultdict(set), so a missing key starts as an EMPTY SET (see
# actor_repos / repo_actors in the Stats class for why we need sets).
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
# "Copilot"), so the "without bots" analysis removes the official bots,
# not every automated account.
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
# class Stats:
#
# We want to run the SAME analysis twice: once on every event, once on
# non-bot events only. That needs two complete, separate sets of
# counters. Instead of creating six counters with "_all" names and six
# more with "_non_bot" names, we define a CLASS: a template that says
# "a Stats object holds these six counters, and knows how to add an
# event to them". Then we create two objects from the same template:
#
#     all_events = Stats()     # one complete set of counters
#     non_bot = Stats()        # another, completely separate set
#
# Think of the class as a blank form, and each object as one filled-in
# copy of that form.
#
# The """...""" line under `class Stats:` is a DOCSTRING — the same kind
# of description as the one at the top of this file, but for the class.
# ---------------------------------------------------------------------
class Stats:
    """All the counts for one group of events (e.g. all events, or non-bot events only)."""

    # -----------------------------------------------------------------
    # def __init__(self) -> None:
    #
    # __init__ is a special method Python runs automatically every time
    # a new object is created with Stats(). Its job is to set up the
    # object's starting values.
    #
    # `self` is the object being set up. `self.total_events = 0` means
    # "this object has its own total_events, starting at 0". Because
    # each object has its own `self`, all_events.total_events and
    # non_bot.total_events are two different numbers.
    # -----------------------------------------------------------------
    def __init__(self) -> None:
        # A plain int, incremented once per event. Simpler than len()-ing
        # a list of every event, and doesn't require holding all 69k+
        # events in memory at once just to count them.
        self.total_events = 0

        # -------------------------------------------------------------
        # Counter[str]: the type hint reads as "a Counter whose keys are
        # strings" (the values are always the counts, i.e. ints —
        # Counter doesn't need you to spell that out separately).
        #
        # Three separate counters, one per thing being tallied:
        #   event_type_counts   key = event["type"], e.g. "PushEvent"
        #   actor_event_counts  key = event["actor"]["login"], e.g. "octocat"
        #   repo_event_counts   key = event["repo"]["name"], e.g. "octocat/Hello-World"
        # -------------------------------------------------------------
        self.event_type_counts: Counter[str] = Counter()
        self.actor_event_counts: Counter[str] = Counter()
        self.repo_event_counts: Counter[str] = Counter()

        # -------------------------------------------------------------
        # actor_repos / repo_actors: defaultdict(set)
        #
        # The Counters above count EVENTS. But for a graph, the question
        # is different: "how many DIFFERENT repos did this actor make
        # events in?" and "how many DIFFERENT actors made events in this
        # repo?". If ana pushes 10 times to the same repo, that's 10
        # events but still only 1 repo.
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
        # These two dicts ARE the actor <-> repo graph, seen from each
        # side. defaultdict(set) means the first time an actor/repo
        # appears, its empty set is created automatically (same
        # convenience as Counter starting at 0).
        # -------------------------------------------------------------
        self.actor_repos: defaultdict[str, set[str]] = defaultdict(set)
        self.repo_actors: defaultdict[str, set[str]] = defaultdict(set)

    # -----------------------------------------------------------------
    # def add(self, event_type, actor, repo) -> None:
    #
    # A METHOD: a function that belongs to the class and works on one
    # object's own counters (through `self`). Calling
    # all_events.add("PushEvent", "ana", "ana/app") updates only
    # all_events' counters; non_bot's are untouched.
    # -----------------------------------------------------------------
    def add(self, event_type: str, actor: str, repo: str) -> None:
        self.total_events += 1

        # -------------------------------------------------------------
        # counter[key] += 1
        #
        # This is the payoff of using Counter instead of a plain dict:
        # the first time a given event type / actor / repo is seen,
        # Counter silently treats the missing key as 0, so `+= 1` takes
        # it to 1. Every later occurrence just adds 1 to whatever it
        # already was. By the time the loop finishes, each Counter holds
        # the full tally for every distinct key it ever saw.
        # -------------------------------------------------------------
        self.event_type_counts[event_type] += 1
        self.actor_event_counts[actor] += 1
        self.repo_event_counts[repo] += 1

        # Record the connection in both directions. Because these are
        # sets, repeated events between the same actor and repo don't
        # add duplicates — only NEW partners grow the set.
        self.actor_repos[actor].add(repo)
        self.repo_actors[repo].add(actor)


# ---------------------------------------------------------------------
# def pct(part: int, whole: int) -> str:
#
# Turns "part out of whole" into a percentage, already formatted as text
# (e.g. pct(1970, 69429) -> "  2.8%"). The script prints percentages in
# many places; writing the formula once here means every percentage is
# calculated and formatted the same way. `5.1f` is explained below, in
# the event-types loop.
# ---------------------------------------------------------------------
def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:5.1f}%"


# ---------------------------------------------------------------------
# def print_header(title: str) -> None:
#
# Prints a section title between two lines of "=" signs, so the three
# sections are easy to tell apart in the terminal. "=" * 70 repeats the
# "=" character 70 times; "\n" is a line break, which leaves an empty
# line before each section.
# ---------------------------------------------------------------------
def print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------
# def print_general(all_events: Stats, non_bot: Stats) -> None:
#
# SECTION 1: the overall picture. It doesn't need a separate count of
# bots — it gets them by SUBTRACTION: everything minus non-bots = bots.
#   bot events = all events  - non-bot events
#   bot actors = all actors  - non-bot actors
#   bot-only repos = all repos - repos where at least 1 non-bot made
#                    an event (repos that ONLY bots touched)
#
# `:>7` right-aligns each number in a 7-character column so the numbers
# line up (same format spec idea as in the event-types loop below).
# ---------------------------------------------------------------------
def print_general(all_events: Stats, non_bot: Stats) -> None:
    total = all_events.total_events
    bot_events = total - non_bot.total_events

    # -----------------------------------------------------------------
    # len(all_events.actor_event_counts)
    #
    # Because Counter is a dict subclass, len() on it returns the number
    # of DISTINCT keys, not the sum of the counts. So this is exactly
    # "how many unique actors/repos appeared in the file" — the sum of
    # all values would instead just equal total_events again, which
    # isn't what we want here.
    #
    # Worked example: if the file only had 6 events, made by the actors
    # ana, luis, ana, marta, ana, luis (in that order), the loop would
    # leave
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
    # -----------------------------------------------------------------
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


# ---------------------------------------------------------------------
# def print_analysis(title: str, stats: Stats, top_n: int) -> None:
#
# SECTIONS 2 and 3. This one function prints the whole analysis for
# whichever Stats object it is given. summarize() calls it twice: once
# with all_events, once with non_bot. Because it's the same code both
# times, the two sections are guaranteed to show exactly the same
# things in the same order — which is what makes them comparable.
# ---------------------------------------------------------------------
def print_analysis(title: str, stats: Stats, top_n: int) -> None:
    print_header(title)

    print("Event types:")
    # -----------------------------------------------------------------
    # type_width = max(len(event_type) for event_type in stats.event_type_counts)
    #
    # The width of the event-type column, computed from the data instead
    # of being fixed. An earlier version used a fixed width of 25, and
    # "PullRequestReviewCommentEvent" (29 characters) didn't fit, which
    # pushed its numbers out of line. Here we measure the length of
    # every event type name and take the longest one (max), so the
    # column is always exactly wide enough.
    # -----------------------------------------------------------------
    type_width = max(len(event_type) for event_type in stats.event_type_counts)

    # -----------------------------------------------------------------
    # .most_common()
    #
    # A method only Counter has (plain dicts don't have it). Called with
    # no argument, it returns EVERY (key, count) pair as a list of
    # tuples, sorted from most frequent to least frequent — exactly the
    # order you want when eyeballing "what dominates this dataset."
    # Called as .most_common(n) (used below for actors/repos), it
    # returns only the top n pairs, which is more efficient than sorting
    # everything and slicing when you only need a handful of results.
    # -----------------------------------------------------------------
    for event_type, count in stats.event_type_counts.most_common():
        # -------------------------------------------------------------
        # f"{event_type:<{type_width}} {count:>7} ({pct(...)})"
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
        #   5.1f  (inside pct()) a FIXED-POINT float, at least 5
        #         characters wide total, with exactly 1 digit after the
        #         decimal point (e.g. " 95.3" or "  0.1"). Used for the
        #         percentage so every row shows the same number of
        #         decimal places.
        # None of this changes the underlying value — only how it's
        # rendered as text.
        # -------------------------------------------------------------
        print(f"  {event_type:<{type_width}} {count:>7} ({pct(count, stats.total_events)})")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in stats.actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in stats.repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")

    # -----------------------------------------------------------------
    # Connectivity: can you actually WALK through this graph?
    #
    # The benchmark walks actor -> repo -> actor -> repo. Each step from
    # a repo to "another actor" only works if that repo had events from
    # at least 2 different actors; otherwise the walk is stuck. These
    # three numbers measure how often that's possible:
    #
    #   shared_repos       repos with 2+ different actors — the only
    #                      "bridges" from one actor to another.
    #   multi_repo_actors  actors who made events in 2+ repos — the
    #                      only actors from which a walk can branch out
    #                      to a different repo.
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
    # -----------------------------------------------------------------
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

    # -----------------------------------------------------------------
    # repos_per_actor = Counter({actor: len(repos) for ...})
    #
    # {k: v for ...} is a DICT COMPREHENSION: a one-line loop that builds
    # a dict. Here it turns "actor -> set of repos" into "actor -> HOW
    # MANY different repos". Wrapping it in Counter(...) is just so we
    # can reuse .most_common(top_n) to get the top ones, sorted.
    #
    # This ranking matters more than "most events": an account that
    # makes events in hundreds of DIFFERENT repos acts as a hub that
    # links otherwise unrelated parts of the graph — which is exactly
    # what bots like github-actions[bot] turn out to do.
    # -----------------------------------------------------------------
    repos_per_actor = Counter({actor: len(repos) for actor, repos in stats.actor_repos.items()})
    print(f"\nTop {top_n} actors by number of different repos they made events in:")
    for actor, count in repos_per_actor.most_common(top_n):
        print(f"  {actor:<30} {count:>5} different repos")

    # Same idea from the repo side: the repos with the most different
    # actors are the busiest "meeting points" in the graph.
    actors_per_repo = Counter({repo: len(actors) for repo, actors in stats.repo_actors.items()})
    print(f"\nTop {top_n} repos by number of different actors who made events in them:")
    for repo, count in actors_per_repo.most_common(top_n):
        print(f"  {repo:<40} {count:>5} different actors")


# ---------------------------------------------------------------------
# def summarize(file_path: Path, top_n: int) -> None:
# Same two-required-parameters shape as peek()'s (file_path, num_lines).
# It reads the file ONCE, fills two Stats objects at the same time, and
# then prints the three sections.
# ---------------------------------------------------------------------
def summarize(file_path: Path, top_n: int) -> None:
    all_events = Stats()
    non_bot = Stats()

    # -----------------------------------------------------------------
    # Same `with open(..., "r", encoding="utf-8") as f:` pattern as
    # peek() — see peek_data.py's annotated copy for why text mode and
    # explicit UTF-8 are the right choices here.
    #
    # The key difference from peek(): there is NO `if i >= num_lines:
    # break` here. peek() deliberately stops early because it only wants
    # a handful of sample events; summarize() deliberately reads every
    # single line, because a count or percentage computed from only the
    # first few hundred events wouldn't represent the whole file.
    # -----------------------------------------------------------------
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
        # line after it (the print_...() calls below).
        #
        # No enumerate() needed here — unlike peek(), summarize() never
        # prints a per-line index, so there's no use for the loop
        # position, only the parsed event itself.
        for line in f:
            event = json.loads(line)

            # Pull the three values out once and give them short
            # variable names, since each is used twice below.
            event_type = event["type"]
            actor = event["actor"]["login"]
            repo = event["repo"]["name"]

            # ---------------------------------------------------------
            # Every event goes into all_events. Only non-bot events ALSO
            # go into non_bot. So after the loop:
            #   all_events  = the counts WITH bots
            #   non_bot     = the counts WITHOUT bots
            # Both come from a single pass over the file — no need to
            # read the 69k lines twice.
            # ---------------------------------------------------------
            all_events.add(event_type, actor, repo)
            if not is_bot(actor):
                non_bot.add(event_type, actor, repo)

    print_general(all_events, non_bot)
    print_analysis("ANALYSIS WITH BOTS (all events)", all_events, top_n)
    print_analysis(f"ANALYSIS WITHOUT BOTS (logins ending in '{BOT_SUFFIX}' removed)",
                   non_bot, top_n)


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
