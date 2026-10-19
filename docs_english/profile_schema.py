########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/profile_schema.py.
# It is NOT meant to be run as part of the project pipeline — it lives in
# docs_english/ because its purpose is to teach, not to execute. The real, "clean"
# script (with none of this commentary) is scripts/profile_schema.py.
#
# This file assumes you've already read docs_english/download_gharchive.py,
# docs_english/peek_data.py, and docs_english/summarize_data.py — argparse,
# Path, f-strings, dict/nested-dict lookups, Counter, .most_common(), main(),
# and the __name__ guard are NOT re-explained from scratch here. This file
# focuses on what's NEW in profile_schema.py: RECURSION — a function that
# calls itself to search an arbitrarily-nested structure of unknown shape.
########################################################################

"""Profile the payload shape of a downloaded GH Archive JSON Lines file.

Reads the full file once and reports, per event type, which `payload`
fields appear, how often, and what Python type they hold, plus any nested
"actor-like" references (dicts with a 'login' key, e.g. a PR's author or
reviewer, distinct from the event's top-level actor) found anywhere inside
the payload. This is ground truth for hand-designing the relational/graph
schema later, since payload shape varies a lot between event types (e.g.
PushEvent vs. PullRequestEvent), and multi-actor connectivity (needed for
an actor-repo-actor traversal) mostly lives in these nested references.

Usage:
    python scripts/profile_schema.py
    python scripts/profile_schema.py --file data/2026-08-27-15.json
    python scripts/profile_schema.py --type PushEvent
"""

# argparse, json, Counter, Path: already explained in the previous three
# annotated scripts.
import argparse
import json
from collections import Counter
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# ---------------------------------------------------------------------
# WHY a depth limit exists at all
#
# find_actor_refs() (below) is RECURSIVE: it calls itself on whatever it
# finds nested inside a dict or list, and JSON data can nest arbitrarily
# deep (a dict inside a list inside a dict inside a list...). Without some
# limit, a sufficiently deep or unexpectedly self-referential structure
# could make the function recurse effectively forever, eventually
# crashing with a RecursionError. In practice GH Archive payloads are
# only ever a few levels deep, but MAX_SEARCH_DEPTH is a cheap safety net
# regardless, and it also caps how much work is wasted searching where an
# actor reference realistically wouldn't be found anyway.
# ---------------------------------------------------------------------
MAX_SEARCH_DEPTH = 3


# ---------------------------------------------------------------------
# WHAT IS RECURSION? (a function that calls itself)
#
# find_actor_refs() below calls find_actor_refs() inside its own body.
# That's called RECURSION, and a function that does it is RECURSIVE.
# (It's not "nesting" a function — nesting means DEFINING one function
# inside another. Here there's only one function; it just CALLS itself.)
#
# Why it's allowed: every time a function is called, Python creates a
# fresh, separate copy of its parameters and variables for that call.
# So when find_actor_refs() calls find_actor_refs() again, the new call
# has its own `value`, `path` and `depth`, and doesn't overwrite the
# first call's. The first call simply waits, paused, until the inner
# call returns its answer, and then carries on where it left off.
#
# An analogy: Russian nesting dolls. To find a note hidden somewhere
# inside a set of dolls, the instructions are the same at every level:
#   "Open the doll. If the note is here, take it. Otherwise, for each
#    doll you find inside, apply THESE SAME INSTRUCTIONS to it."
# The instructions refer to themselves — that's recursion.
#
# Why we need it HERE: a payload is a dict that can contain dicts, that
# can contain lists of dicts, and so on — and we don't know in advance
# how deep it goes. A plain `for` loop only looks at ONE level. To look
# at every level, without knowing how many there are, the function
# handles one level and then asks itself to handle the next one.
#
# The two rules every recursive function needs:
#   1. A BASE CASE: a situation where it answers WITHOUT calling itself
#      (here: found a user, reached a plain value like a string, or ran
#      out of depth). Without it, it would call itself forever.
#   2. Each self-call must move CLOSER to a base case (here: each call
#      goes one level deeper into the data, with depth - 1).
#
# Step by step, with a small payload:
#
#     payload = {"action": "created",
#                "issue": {"user": {"login": "luis"}}}
#
#   call 1: find_actor_refs(payload, "payload", 3)
#           a dict without "login" -> look at each of its values:
#     call 2: find_actor_refs("created", "payload.action", 2)
#             a string -> nothing inside -> returns []
#     call 3: find_actor_refs({"user": {...}}, "payload.issue", 2)
#             a dict without "login" -> look at each of its values:
#       call 4: find_actor_refs({"login": "luis"}, "payload.issue.user", 1)
#               a dict WITH "login" -> returns ["payload.issue.user"]
#             call 3 collects that and returns ["payload.issue.user"]
#   call 1 collects [] + ["payload.issue.user"] and returns
#   ["payload.issue.user"]
#
# Each call only deals with ONE level; the answers travel back up, one
# call at a time, until the first call has the complete list.
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# def find_actor_refs(value: object, path: str, depth: int) -> list[str]:
#
# `value: object` — the parameter's declared type is `object`, the most
# general type in Python (everything is an `object`). This is deliberate:
# this function is handed pieces of already-parsed JSON, which could be a
# dict, a list, a str, an int, a bool, or None depending on where in the
# structure it's currently looking — there's no single more specific type
# that covers all of those, so `object` is the honest type hint here.
#
# `path: str` — a human-readable breadcrumb trail of how we got here,
# e.g. "payload.pull_request.user". Built up one `.attribute` at a time
# as the function recurses deeper, purely for the final printed report —
# it plays no role in the actual searching logic.
#
# `depth: int` — how many more levels this call is allowed to recurse
# before giving up. Each recursive call passes `depth - 1`, counting down
# toward the depth limit explained above.
#
# `-> list[str]` — this function always returns a list of path strings
# (possibly empty), regardless of which branch below actually runs.
# ---------------------------------------------------------------------
def find_actor_refs(value: object, path: str, depth: int) -> list[str]:
    # ---------------------------------------------------------------
    # THE BASE CASE
    #
    # Every recursive function needs at least one condition that stops
    # the recursion outright, without making any further recursive
    # calls — otherwise it truly would recurse forever. Here, once we've
    # gone deeper than MAX_SEARCH_DEPTH allows, we immediately return an
    # empty list (found nothing) rather than looking any further.
    # ---------------------------------------------------------------
    if depth < 0:
        return []

    # ---------------------------------------------------------------
    # isinstance(value, dict)
    #
    # Checks whether `value` is (an instance of) the dict type. This is
    # how the function tells the three cases it cares about apart, since
    # `value`'s actual type varies call to call (see the `object` note
    # above): is this a dict I should look inside, a list I should look
    # inside, or something else (a str/int/bool/None) with nothing
    # further to search?
    # ---------------------------------------------------------------
    if isinstance(value, dict):
        # ---------------------------------------------------------------
        # value.get("login")
        #
        # `.get(key)` is a dict lookup that returns None instead of
        # raising an error when the key is missing — unlike
        # value["login"], which would crash with a KeyError on any dict
        # that doesn't happen to have a "login" key (most of them,
        # here). This is the right tool whenever a key's absence is a
        # normal, expected possibility rather than a bug.
        #
        # isinstance(..., str) on the result then checks the login value
        # is actually a string (a real username) and not, say, None from
        # a missing key, or some other type we wouldn't recognize as a
        # username.
        #
        # gh-archive-guide.md documents that every GitHub user reference
        # (the event's own top-level `actor`, but also PR authors,
        # reviewers, comment authors, etc.) is shaped like
        # {"id": ..., "login": "some-user"}. So: "does this dict have a
        # string 'login' field?" is a reasonable, general test for "is
        # this dict a reference to a GitHub user?" — without needing to
        # hardcode every possible field name (user/author/assignee/
        # reviewer/owner/...) a user-reference might be stored under.
        # ---------------------------------------------------------------
        if isinstance(value.get("login"), str):
            # Found one. Return immediately — a dict that looks like a
            # user reference is a "leaf" for our purposes; there's no
            # reason to keep recursing INTO a user object looking for
            # yet more nested users.
            return [path]

        # ---------------------------------------------------------------
        # This dict itself wasn't a user reference, so search each of
        # its values instead, in case ONE OF THEM is (or contains) one.
        #
        # `refs = []` then `refs.extend(...)` in a loop, rather than
        # `return find_actor_refs(...)` directly inside the loop: a dict
        # can have many keys, and an actor reference might be hiding
        # under more than one of them (e.g. both "assignee" and
        # "assignees" in the same payload) — so every key needs to be
        # checked and all of their results combined, not just the first
        # match returned immediately.
        #
        # `f"{path}.{key}"` extends the breadcrumb trail with this key's
        # name before recursing into its value — so if a match is found
        # three levels down, the returned path records the whole route
        # there, not just the last step.
        #
        # `depth - 1` — one level deeper, one less allowance remaining.
        # ---------------------------------------------------------------
        refs = []
        for key, sub_value in value.items():
            refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
        return refs

    # ---------------------------------------------------------------
    # isinstance(value, list)
    #
    # Lists show up here for fields like "assignees" (a list of user
    # dicts) or "requested_reviewers". Note the path is NOT extended
    # with an index (no ".0", ".1", ...) when recursing into list items
    # — every item in, say, "assignees" is conceptually the same kind of
    # thing (an assignee), so they're reported under one shared path
    # rather than as separate numbered paths.
    # ---------------------------------------------------------------
    if isinstance(value, list):
        refs = []
        for item in value:
            refs.extend(find_actor_refs(item, path, depth - 1))
        return refs

    # ---------------------------------------------------------------
    # Anything else (str, int, float, bool, None, ...) has nothing
    # inside it to search - this is the other base case, reached once
    # the recursion has drilled down to a plain value rather than a
    # container.
    # ---------------------------------------------------------------
    return []


# ---------------------------------------------------------------------
# FULL EXAMPLE: a complete walk through find_actor_refs()
#
# This example goes through EVERY branch of the function: a dict
# without "login", a dict with "login", a list, plain values, and the
# depth limit. It's a payload similar to an IssuesEvent's:
#
#     payload = {
#         "action": "opened",
#         "issue": {
#             "number": 7,
#             "user": {"login": "luis", "id": 1},
#             "assignees": [{"login": "ana"}, {"login": "marta"}],
#             "milestone": {"creator": {"login": "pedro"}}
#         }
#     }
#
# profile() calls it like this:  find_actor_refs(payload, "payload", 3)
#
# Each indentation level is a call made INSIDE the previous one. The
# outer call waits, paused, until the inner one finishes.
#
# CALL 1: find_actor_refs(payload, "payload", 3)
#   - depth < 0? 3 isn't -> carry on.
#   - Is it a dict? YES. Does it have "login"? No (its keys are action
#     and issue).
#   - Sets up refs = [] and goes through its keys one by one:
#
#   WHERE THE NEXT CALLS' ARGUMENTS COME FROM
#
#   Every new call is born from the LOOP of the previous call. In the
#   dict branch, the loop is:
#
#       for key, sub_value in value.items():
#           refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
#
#   In call 1: value = payload, path = "payload", depth = 3.
#   value.items() gives one (key, sub_value) pair on each pass:
#
#       1st pass: key = "action", sub_value = "opened"
#       2nd pass: key = "issue",  sub_value = {...issue...}
#
#   Substituting on the 1st pass:
#
#       sub_value          -> "opened"
#       f"{path}.{key}"    -> "payload" + "." + "action" = "payload.action"
#       depth - 1          -> 3 - 1 = 2
#
#   and out comes exactly CALL 2. The 2nd pass gives CALL 3.
#
#   General rule:
#     - the pair's VALUE becomes the new `value` (what gets examined);
#     - the KEY is added to `path` (the trail of where we are);
#     - `depth` drops by 1, because we've gone down one level.
#   In the LIST loop there's no key: each item becomes the new `value`,
#   `path` stays the SAME, and `depth` drops by 1.
#
#   Under each call, "Comes from" says which pass of which loop it was
#   born from.
#
#   CALL 2: find_actor_refs("opened", "payload.action", 2)
#     Comes from: 1st pass of call 1's loop (key = "action").
#     - It's text: neither dict nor list -> reaches the final
#       `return []`.
#     - Returns [].  Call 1 does refs.extend([]) -> refs = [].
#
#   CALL 3: find_actor_refs({...issue...}, "payload.issue", 2)
#     Comes from: 2nd pass of call 1's loop (key = "issue";
#     path "payload" + ".issue"; depth 3 - 1 = 2).
#     - Is it a dict? YES. Does it have "login"? No.
#     - Sets up its OWN refs = [] (separate from call 1's) and goes
#       through its keys:
#
#     CALL 4: find_actor_refs(7, "payload.issue.number", 1)
#       Comes from: 1st pass of call 3's loop (key = "number";
#       path "payload.issue" + ".number"; depth 2 - 1 = 1).
#       - It's a number: neither dict nor list -> returns [].
#
#     CALL 5: find_actor_refs({"login": "luis", "id": 1},
#                             "payload.issue.user", 1)
#       Comes from: 2nd pass of call 3's loop (key = "user").
#       - A dict with a text "login" ("luis") -> FOUND!
#       - Returns ["payload.issue.user"] and doesn't look further in.
#       Call 3 now has refs = ["payload.issue.user"].
#
#     CALL 6: find_actor_refs([{ana}, {marta}],
#                             "payload.issue.assignees", 1)
#       Comes from: 3rd pass of call 3's loop (key = "assignees").
#       - Is it a dict? No. Is it a list? YES.
#       - Goes through each item. The path does NOT change (no .0, .1).
#
#       CALL 7: find_actor_refs({"login": "ana"},
#                               "payload.issue.assignees", 0)
#         Comes from: 1st pass of call 6's LIST loop
#         (item {"login": "ana"}; no key, so the path doesn't change;
#         depth 1 - 1 = 0).
#         - depth = 0: zero isn't less than zero -> carry on.
#         - A dict with "login" -> returns ["payload.issue.assignees"].
#
#       CALL 8: find_actor_refs({"login": "marta"},
#                               "payload.issue.assignees", 0)
#         Comes from: 2nd pass of call 6's LIST loop
#         (item {"login": "marta"}).
#         - Same -> returns ["payload.issue.assignees"].
#
#       - Call 6 returns
#         ["payload.issue.assignees", "payload.issue.assignees"].
#
#     CALL 9: find_actor_refs({"creator": {...}},
#                             "payload.issue.milestone", 1)
#       Comes from: 4th pass of call 3's loop (key = "milestone").
#       - A dict without "login" -> goes through its only key:
#
#       CALL 10: find_actor_refs({"login": "pedro"},
#                                "payload.issue.milestone.creator", 0)
#         Comes from: the only pass of call 9's loop
#         (key = "creator"; depth 1 - 1 = 0).
#         - depth = 0 -> carry on. A dict with "login" ->
#           returns ["payload.issue.milestone.creator"].
#
#       - Call 9 returns ["payload.issue.milestone.creator"].
#
#     - Call 3 finishes its loop and returns its 4 paths.
#
#   - Call 1 does refs.extend(...) with those 4 paths and returns:
#
#     ['payload.issue.user',
#      'payload.issue.assignees',
#      'payload.issue.assignees',
#      'payload.issue.milestone.creator']
#
# WHICH BRANCH SHOWS UP IN WHICH CALL
#   dict without "login" -> look inside ......... calls 1, 3 and 9
#   dict WITH "login" -> return [path] .......... calls 5, 7, 8 and 10
#   list -> look at each item, same path ........ call 6
#   plain value -> return [] .................... calls 2 and 4
#   depth drops by 1 at each level: 3 -> 2 -> 1 -> 0, all the way down
#
# That's 10 calls to the SAME function. Each one has its own value,
# path, depth and refs, and none of them overwrites another's
# variables. The answers travel back UP: calls 7 and 8 answer call 6,
# call 6 answers call 3, and call 3 answers call 1.
#
# TWO MORE DETAILS
#
# 1. The depth limit in action. If the user were one level deeper:
#
#        deep = {"a": {"b": {"c": {"d": {"login": "x"}}}}}
#        find_actor_refs(deep, "payload", 3)   # -> []
#
#    by the time it reached {"login": "x"}, depth would be -1, and the
#    first check (`if depth < 0: return []`) would stop there: it does
#    NOT find it. That's the price of the safety net; since GH Archive
#    payloads are shallow, nothing is lost in practice.
#
# 2. Why profile() uses set(...) afterwards. The list contains
#    "payload.issue.assignees" TWICE (once for ana, once for marta).
#    profile() calls set(...), which keeps each path only once:
#
#        {'payload.issue.user', 'payload.issue.assignees',
#         'payload.issue.milestone.creator'}
#
#    So this event counts as ONE event that has assignees, not two:
#    what's being counted is IN HOW MANY EVENTS each path appears, not
#    how many users there are.
# ---------------------------------------------------------------------


def profile(file_path: Path, type_filter: str | None) -> None:
    event_type_totals: Counter[str] = Counter()
    # For each event type, for each payload field name, a Counter of how
    # many times each Python type (dict/list/str/int/bool/NoneType) was
    # seen in that field. Same nested-Counter idea as summarize_data.py,
    # just keyed one level deeper (event type -> field name -> type name).
    payload_field_types: dict[str, dict[str, Counter[str]]] = {}
    # For each event type, a Counter of how many events contained an
    # actor-like reference at each nested path (e.g.
    # "payload.pull_request.user").
    actor_ref_counts: dict[str, Counter[str]] = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            event_type = event["type"]

            # ---------------------------------------------------------
            # --type lets you focus the (potentially long) report on one
            # event type at a time. `continue` skips the rest of THIS
            # loop iteration and moves straight to the next line, without
            # touching any of the counters below - so filtered-out events
            # contribute nothing to the totals or reports.
            # ---------------------------------------------------------
            if type_filter is not None and event_type != type_filter:
                continue

            event_type_totals[event_type] += 1
            fields = payload_field_types.setdefault(event_type, {})
            payload = event.get("payload", {})

            for key, value in payload.items():
                type_counts = fields.setdefault(key, Counter())
                type_counts[type(value).__name__] += 1

            # ---------------------------------------------------------
            # set(find_actor_refs(...))
            #
            # find_actor_refs can return the SAME path more than once
            # for a single event - e.g. three requested reviewers under
            # "payload.requested_reviewers" would come back as that path
            # three times, once per reviewer. Wrapping the result in
            # set(...) collapses duplicates, so this matches how the
            # field-type counters above work: counting how many EVENTS
            # have a reference at that path, not how many references
            # exist in total.
            # ---------------------------------------------------------
            ref_paths = set(find_actor_refs(payload, "payload", MAX_SEARCH_DEPTH))
            ref_counts = actor_ref_counts.setdefault(event_type, Counter())
            for ref_path in ref_paths:
                ref_counts[ref_path] += 1

    # ---------------------------------------------------------------
    # How to read the output
    #
    # A real example from this project's fixed hour:
    #
    #   IssueCommentEvent (194 events)
    #     payload.action               present in 100.0% (194/194) - types: str x194
    #     payload.issue                present in 100.0% (194/194) - types: dict x194
    #     payload.comment              present in 100.0% (194/194) - types: dict x194
    #     actor references (nested 'login' fields):
    #       payload.issue.user                  present in 100.0% (194/194)
    #       payload.comment.user                present in 100.0% (194/194)
    #
    # - Line 1: the event type, and how many events of that type the
    #   file contains.
    # - Each payload line: the field name, then "present in X%" - in
    #   how many of THOSE events the field exists at all. 100% means
    #   always there (reliable); a low % means only sometimes, so it
    #   would become an optional/nullable column. "types" says what
    #   kind of value it held (str, int, dict, list, NoneType) and how
    #   often. NoneType means the field is sometimes empty - e.g.
    #   CreateEvent's description is None in 633 of 1290 events.
    # - "actor references": paths to nested user objects (anything
    #   with a "login"), and in what % of events each one appears.
    #
    # IMPORTANT: this only checks that a user object EXISTS at that
    # path, not WHO it is. payload.comment.user is the commenter -
    # i.e. the actor themself (100% of the time). payload.issue.user
    # is the issue's author, a different person in 66% of cases. See
    # project-notes.md (Schema Design Stage) for the check against
    # the event's actor.
    # ---------------------------------------------------------------
    for event_type, total in event_type_totals.most_common():
        print(f"{event_type} ({total} events)")
        fields = payload_field_types[event_type]
        if not fields:
            print("  (empty payload)")
        for field_name, type_counts in fields.items():
            presence = sum(type_counts.values())
            pct = 100 * presence / total
            types = ", ".join(f"{t} x{c}" for t, c in type_counts.most_common())
            print(f"  payload.{field_name:<20} present in {pct:5.1f}% ({presence}/{total}) - types: {types}")

        print("  actor references (nested 'login' fields):")
        refs = actor_ref_counts[event_type]
        if not refs:
            print("    (none found)")
        for ref_path, count in refs.most_common():
            pct = 100 * count / total
            print(f"    {ref_path:<35} present in {pct:5.1f}% ({count}/{total})")
        print()


# parse_args(): same overall pattern as the other three scripts - --file
# and --type follow the same style as --file/--lines in peek_data.py and
# --file/--top in summarize_data.py.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--type", type=str, default=None,
                         help="Only profile this event type (default: all types)")
    return parser.parse_args()


# main() and the `if __name__ == "__main__":` guard: identical purpose and
# mechanics to the other three scripts.
def main() -> None:
    args = parse_args()
    profile(args.file, args.type)


if __name__ == "__main__":
    main()
