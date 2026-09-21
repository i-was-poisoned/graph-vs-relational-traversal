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

import argparse
import json
from collections import Counter
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# How deep into a nested payload structure to search for actor-like
# references before giving up. Kept shallow since GH Archive payloads are
# only a few levels deep in practice; this just guards against ever
# looping forever on unexpectedly deep/self-referential data.
MAX_SEARCH_DEPTH = 3


def find_actor_refs(value: object, path: str, depth: int) -> list[str]:
    if depth < 0:
        return []

    if isinstance(value, dict):
        if isinstance(value.get("login"), str):
            # This dict itself looks like a GitHub user reference (it has
            # the same 'login' field the top-level actor has) - record
            # where we found it and stop; no need to look inside a user
            # object for further nested users.
            return [path]
        refs = []
        for key, sub_value in value.items():
            refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
        return refs

    if isinstance(value, list):
        refs = []
        for item in value:
            refs.extend(find_actor_refs(item, path, depth - 1))
        return refs

    return []


def profile(file_path: Path, type_filter: str | None) -> None:
    event_type_totals: Counter[str] = Counter()
    # For each event type, for each payload field name, a Counter of how
    # many times each Python type (dict/list/str/int/bool/NoneType) was
    # seen in that field.
    payload_field_types: dict[str, dict[str, Counter[str]]] = {}
    # For each event type, a Counter of how many events contained an
    # actor-like reference at each nested path (e.g.
    # "payload.pull_request.user").
    actor_ref_counts: dict[str, Counter[str]] = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            event_type = event["type"]

            if type_filter is not None and event_type != type_filter:
                continue

            event_type_totals[event_type] += 1
            fields = payload_field_types.setdefault(event_type, {})
            payload = event.get("payload", {})

            for key, value in payload.items():
                type_counts = fields.setdefault(key, Counter())
                type_counts[type(value).__name__] += 1

            # set(...) so an event with, say, three requested reviewers
            # (three separate 'login' dicts under the same path) counts
            # as ONE event with that reference, not three - this counter
            # tracks event presence, matching how the field-type counters
            # above work.
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--type", type=str, default=None,
                         help="Only profile this event type (default: all types)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile(args.file, args.type)


if __name__ == "__main__":
    main()
