########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/peek_data.py.
# It is NOT meant to be run as part of the project pipeline — it lives in
# docs_english/ because its purpose is to teach, not to execute. The real, "clean"
# script (with none of this commentary) is scripts/peek_data.py.
#
# This file assumes you've already read docs_english/download_gharchive.py — the
# fundamentals explained there (docstrings, imports, Path, type hints,
# f-strings, argparse, main(), the __name__ guard) are NOT re-explained
# from scratch here. This file focuses on what's NEW in peek_data.py.
########################################################################

"""Peek at the first few events in a downloaded GH Archive JSON Lines file.

Usage:
    python scripts/peek_data.py
    python scripts/peek_data.py --file data/2026-08-27-15.json --lines 10
"""

# argparse, Path: already explained in docs_english/download_gharchive.py.
import argparse

# json: the standard library module for converting between JSON text and
# Python objects. `json.loads(text)` ("load string") parses a JSON-formatted
# string into Python values — a JSON object like {"a": 1} becomes a Python
# dict, a JSON array becomes a Python list, and so on. This is exactly what
# we need here: each line of the data file is one JSON object as text, and
# we want it as a Python dict we can pull fields out of.
#
# (Compare `json.loads` with `json.load` — no "s" — which reads directly
# from an already-open file instead of from a string. We use `loads` here
# because we're handling one already-read line of text at a time, not an
# entire file object.)
import json

from pathlib import Path

# ---------------------------------------------------------------------
# DEFAULT_FILE: same Path-building technique as DATA_DIR in
# download_gharchive.py — computed from this script's own location
# (__file__), walking up to the project root (.parent.parent), then down
# into data/2026-08-27-15.json. This hardcodes the specific dataset file
# this project uses as the default target to peek at, while still letting
# --file override it for a different downloaded hour.
# ---------------------------------------------------------------------
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# How many events to print if --lines isn't specified. Kept small (5) since
# this function is for a quick sanity check, not for reading the whole file.
DEFAULT_LINES = 5


# ---------------------------------------------------------------------
# def peek(file_path: Path, num_lines: int) -> None:
# Two parameters, both required (no default values here, unlike
# download()'s data_dir) — this function always needs to be told
# explicitly which file to read and how many lines to show.
# ---------------------------------------------------------------------
def peek(file_path: Path, num_lines: int) -> None:
    # ---------------------------------------------------------------
    # open(file_path, "r", encoding="utf-8"):
    #   "r"                "read" mode, and — unlike download_gharchive.py's
    #                      "rb"/"wb" (binary modes) — plain "r" here means
    #                      TEXT mode: Python automatically decodes the raw
    #                      bytes on disk into a Python str as you read,
    #                      using the given encoding. Binary mode was right
    #                      for download_gharchive.py because we were just
    #                      relaying bytes through unchanged; here we
    #                      actually want to interpret the content as text
    #                      (specifically, as JSON), so text mode is correct.
    #   encoding="utf-8"    JSON Lines files (and JSON in general) are
    #                      near-universally UTF-8 encoded. Being explicit
    #                      about the encoding, rather than relying on
    #                      whatever the operating system's default happens
    #                      to be, avoids subtle bugs where the same file
    #                      might be read differently on different machines
    #                      (e.g. Windows sometimes defaults to a different
    #                      encoding than macOS/Linux).
    #
    # Just like download_gharchive.py, this uses a `with` block so the
    # file is automatically and reliably closed once we're done with it.
    # ---------------------------------------------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        # ---------------------------------------------------------------
        # for i, line in enumerate(f):
        #
        # A plain `for line in f:` would already loop over the file one
        # line at a time (this is one of the most useful properties of an
        # open file object in Python — it's directly iterable line by
        # line, so you never need to manually call something like
        # f.readline() in a loop). But we also want to know WHICH line
        # number we're on, to print something like "[0]", "[1]", "[2]"
        # and to know when to stop.
        #
        # enumerate(f) wraps that same line-by-line iteration, but instead
        # of just handing back each `line`, it hands back a pair:
        # (index, line) — starting the index at 0 by default. Writing
        # `for i, line in enumerate(f):` unpacks that pair directly into
        # two separate variables, `i` (the position, 0, 1, 2, ...) and
        # `line` (the actual text of that line).
        # ---------------------------------------------------------------
        for i, line in enumerate(f):
            # Stop once we've printed the requested number of lines.
            # Without this, the loop would keep going through the ENTIRE
            # file (which could be tens of thousands of lines) even
            # though we only wanted to peek at a handful.
            if i >= num_lines:
                break

            # Parse this one line of text (a single JSON object, e.g.
            # {"type": "PushEvent", "actor": {...}, ...}) into a Python
            # dict, so we can access its fields with square-bracket
            # lookups below.
            event = json.loads(line)

            # ---------------------------------------------------------------
            # Printing the fields we care about.
            #
            # event['type']              a dict lookup: 'type' is a key in
            #                            the top-level JSON object, e.g.
            #                            "PushEvent".
            # event['actor']['login']     a NESTED lookup: 'actor' is itself
            #                            a dict (an object inside the
            #                            object), and 'login' is a key
            #                            inside THAT nested dict — this
            #                            mirrors the nested JSON structure
            #                            shown in gh-archive-guide.md
            #                            (the "actor": {"login": ...} shape).
            # event['repo']['name']       same nested-lookup idea, reaching
            #                            into the 'repo' sub-object.
            # event['created_at']         a plain top-level lookup again.
            #
            # The `!r` inside each f-string placeholder (e.g. {event['type']!r})
            # requests the "repr" (representation) of the value instead of
            # its plain string form. For strings, this wraps the value in
            # quotes in the output (e.g. 'PushEvent' instead of PushEvent),
            # which makes it visually unambiguous where one field's value
            # ends and the next field's label begins when scanning the
            # printed output.
            #
            # This one print() call is split across four lines in the
            # source code using implicit string concatenation — Python
            # automatically joins adjacent string literals that appear
            # next to each other with nothing but whitespace/newlines
            # between them, so this is really just one long f-string
            # written across multiple lines for readability.
            # ---------------------------------------------------------------
            print(f"[{i}] type={event['type']!r} "
                  f"actor={event['actor']['login']!r} "
                  f"repo={event['repo']['name']!r} "
                  f"created_at={event['created_at']!r}")


# ---------------------------------------------------------------------
# parse_args(): same overall pattern as download_gharchive.py's version,
# with two differences worth calling out:
#
#   type=Path (for --file)
#     Key idea: everything you type in the terminal reaches Python as
#     TEXT (a str). If you run
#
#         python scripts/peek_data.py --file data/2026-08-27-15.json --lines 10
#
#     Python receives "data/2026-08-27-15.json" and "10" — both as text,
#     even the 10. The `type=` parameter tells argparse what to convert
#     that text into before handing it to us. Behind the scenes it does
#     roughly:
#
#         args.file  = Path("data/2026-08-27-15.json")   # text -> Path
#         args.lines = int("10")                          # text -> number 10
#
#     That's what "argparse will call Path(...) for us" means: without
#     type=Path, args.file would be a plain string and we'd have to write
#     Path(args.file) ourselves later.
#
#     Why a Path instead of plain text? A Path is an object that "knows"
#     it's a file path, so it comes with useful tools that a string
#     doesn't have:
#
#         p = Path("data/2026-08-27-15.json")
#         p.exists()   # does the file exist? -> True / False
#         p.name       # "2026-08-27-15.json"
#         p.parent     # Path("data")
#
#     and it works the same on Windows and Linux (no worrying about /
#     vs \). It also keeps things consistent: DEFAULT_FILE is already a
#     Path, so with type=Path, args.file is ALWAYS a Path, whether or not
#     the user passed --file — peek() always receives the same type.
#
#     Why download_gharchive.py's --date stayed plain text: there, the
#     value is only used to build ANOTHER piece of text (the download
#     URL, https://data.gharchive.org/2026-08-27-15.json.gz), so there's
#     nothing to convert it into. Here, --file really is a path to a file
#     on disk, so it makes sense for it to be a Path.
#
#   No `choices=` restriction on --lines
#     download_gharchive.py restricted --hour to range(0, 24) because
#     only 24 values are ever valid. Here, --lines is just "however many
#     you want to see" — any positive integer is reasonable, so there's
#     no fixed set of valid choices to restrict it to.
# ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--lines", type=int, default=DEFAULT_LINES,
                         help=f"How many events to print (default: {DEFAULT_LINES})")
    return parser.parse_args()


# main() and the `if __name__ == "__main__":` guard: identical purpose and
# mechanics to download_gharchive.py — see that file's annotated copy for
# the full explanation. In short: main() ties argument parsing to the
# actual work (here, peek() instead of download()), and the guard ensures
# that work only runs when this file is executed directly, not when
# imported.
def main() -> None:
    args = parse_args()
    peek(args.file, args.lines)


if __name__ == "__main__":
    main()
