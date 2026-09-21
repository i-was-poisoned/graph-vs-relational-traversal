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
