#!/usr/bin/env bash
########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of research.sh (in the
# project folder). It is NOT meant to be run — it lives in docs_english/
# because its purpose is to teach, not to execute. (It wouldn't even
# work from here: it looks for run.sh and scripts/ next to itself.) The
# real, "clean" file (with none of this commentary) is research.sh.
#
# The line above this box is the original's first line, kept first on
# purpose (see "the shebang" just below). Apart from these
# added comment lines, every line is identical to the original.
#
# What to read first: research.sh calls run.sh, which has no annotated
# copy but is short and commented — read run.sh itself. It's useful to
# compare the two (see "research.sh vs run.sh" below). For what the
# Python steps do, see docs_english/check_connections.py,
# docs_english/measure.py (the measurement itself) and
# docs_english/choose_starts.py (the list of databases, and how the
# starting actors are chosen).
#
# What's NEW here: this is the project's first BASH script explained line
# by line. It's the single entry point of the research: one command
# checks the servers, asks which database to measure, and runs
# measure.py on it, stopping at the first step that fails. Every
# measurement writes ONE CSV file of its own in results/, named after the
# database and the moment it started. Bash concepts covered: the
# shebang, set -eo pipefail, cd "$(dirname "$0")", a loop over the
# arguments with case / shift,
# arrays, mapfile with process substitution, tr -d '\r', read -p, and a
# regular-expression check with [[ =~ ]].
#
# The whole research, as three commands:
#     ./run.sh scripts/drop_databases.py   (optional: start from a clean slate)
#     ./run.sh scripts/build_hours.py      (one database per data volume)
#     ./research.sh                        (this file: measure one of them)
#
# How to run the real file (from Git Bash, in the project folder, with
# PostgreSQL running and Neo4j Desktop open):
#     ./research.sh
#     ./research.sh --database gharchive-2026-10-08-9-24h
#     ./research.sh --new-starts
########################################################################

# ---------------------------------------------------------------------
# The shebang: #!/usr/bin/env bash  (the very first line of the file)
#
# "#!" at the very start of a file tells the system WHICH PROGRAM should
# read the rest when you run the file directly as ./research.sh.
# /usr/bin/env bash means "find bash wherever it's installed and use it".
# For bash itself it's just a comment (it starts with #).
#
# research.sh vs run.sh
#   run.sh       a generic LAUNCHER: prepares the environment (.venv,
#                passwords from secrets.sh), then becomes `python <script>`.
#                It runs ONE Python script.
#   research.sh  an ORCHESTRATOR: it never touches .venv or the passwords
#                itself. It calls ./run.sh once per step (and once for
#                the list of databases); each call gets its own environment, which
#                disappears when that step ends.
# Both start with the same three lines: shebang, set -eo pipefail, cd.
# ---------------------------------------------------------------------
# Run the research for one database:
#     0. check that both servers answer
#     1. ask which database to measure (unless --database is given)
#     2. measure.py: choose (or reuse) the starting actors, measure the traversal in
#        PostgreSQL and Neo4j, and write the results to one CSV file in results/
#
# Usage (from Git Bash, with PostgreSQL running and Neo4j Desktop open):
#     ./research.sh                                     # asks which database to measure
#     ./research.sh --database gharchive-2026-10-08-9-24h
#     ./research.sh --database ... --max-depth 4 --repeats 5 --timeout 60 --cypher both
#     ./research.sh --new-starts                        # choose the starting actors again
#
# The work is done by the Python scripts; this file only runs them in order,
# asks the one question, and stops at the first step that fails.

# ---------------------------------------------------------------------
# set -eo pipefail — STOP AT THE FIRST FAILURE
#
# By default, bash carries on with the next line even when a command
# fails. That would be bad here: if the servers weren't answering, the
# script would still go on and ask a question, then try to measure.
#   -e         exit as soon as a command fails (ends with a non-zero exit
#              code — e.g. a Python script calling sys.exit(1), see
#              docs_english/check_connections.py).
#   -o pipefail
#              in a PIPE `a | b`, the pipe counts as failed if ANY part
#              fails. Without it, only the last command's result counts,
#              so `failing_command | tr ...` would look like a success.
#
# cd "$(dirname "$0")" — WORK FROM THE PROJECT FOLDER
#   $0             the path this script was started with, e.g.
#                  ./research.sh or /c/dev/Research/research.sh
#   dirname ...    keeps only its folder part: . or /c/dev/Research
#   $( ... )       COMMAND SUBSTITUTION: runs the command inside and puts
#                  its output in its place.
#   the quotes     keep a folder name with spaces in one piece.
# So whatever folder you're in when you start it, the script moves to its
# own folder, and paths like ./run.sh and scripts/... work.
# ---------------------------------------------------------------------
set -eo pipefail
cd "$(dirname "$0")"

# ---------------------------------------------------------------------
# Variables and an ARRAY
#
# DATABASE=""          a variable, empty for now. In bash there must be
#                      NO spaces around = (DATABASE = "" would fail).
# MEASURE_OPTIONS=()   an ARRAY: a list of separate strings, empty for
#                      now. It will collect the options meant for
#                      measure.py, e.g. (--max-depth 4 --timeout 60).
# Why an array and not one string? Each item stays a separate argument
# when passed on, even if it contained spaces.
# ---------------------------------------------------------------------
DATABASE=""
MEASURE_OPTIONS=()
# ---------------------------------------------------------------------
# THE ARGUMENT LOOP: while / case / shift
#
# $#  the number of arguments still left; $1, $2 the first and second.
#   ./research.sh --database X --repeats 5
#     -> $# = 4, $1 = --database, $2 = X
#
# while [ $# -gt 0 ]; do ... done
#   repeat while there are arguments left (-gt: "greater than"; [ ] is a
#   test, and needs the spaces inside the brackets).
#
# case "$1" in ... esac — compare $1 with several patterns, like a chain
# of if/elif. Each branch is `pattern) commands ;;`
#   --database)        keep the next argument as the database name.
#   --max-depth|--repeats|--timeout|--cypher)
#                      `|` means OR. These four aren't used by
#                      research.sh itself: they're added to the array, as
#                      the option AND its value, to be handed to
#                      measure.py later. += ( ... ) appends to an array.
#                      (--cypher chooses which Cypher version(s) to
#                      measure: paths, levels or both; see
#                      docs_english/traversal.py.)
#   --new-starts)      a SWITCH: an option with NO value. Only the option
#                      itself goes into the array, and `shift` (= shift 1)
#                      drops just that one argument. It tells measure.py
#                      to choose the starting actors again instead of
#                      reusing the ones of the latest measurement of
#                      that database
#                      (see docs_english/measure.py, previous_starts).
#   *)                 `*` matches anything else: an unknown option. The
#                      message goes to the ERROR output (>&2: "send this
#                      to stream 2", stderr) and exit 1 stops with failure.
#
# shift 2 — throw away the first two arguments ($1 and $2): what was $3
# becomes $1, and $# goes down by 2. That's how the loop moves forward,
# two by two (an option and its value) — or one by one for a switch.
# ---------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --database) DATABASE="$2"; shift 2 ;;
        --max-depth|--repeats|--timeout|--cypher) MEASURE_OPTIONS+=("$1" "$2"); shift 2 ;;
        --new-starts) MEASURE_OPTIONS+=("$1"); shift ;;
        *) echo "Unknown option: $1 (see the top of research.sh)" >&2; exit 1 ;;
    esac
done

# Step 0: check_connections.py (docs_english/check_connections.py). If a
# server isn't running, it exits with 1 and, thanks to set -e, the
# research stops here — before asking anything or measuring anything.
echo "== 0. Check that both servers are answering"
./run.sh scripts/check_connections.py

# ---------------------------------------------------------------------
# NO --database GIVEN: ASK WHICH ONE
#
# [ -z "$DATABASE" ] — true if the variable is empty (-z: "zero length").
# ---------------------------------------------------------------------
if [ -z "$DATABASE" ]; then
    # -----------------------------------------------------------------
    # mapfile -t DATABASES < <( ... )
    #
    # choose_starts.py --list-databases prints the databases that exist
    # on BOTH sides, one per line (see docs_english/choose_starts.py).
    # This line puts those lines into an array:
    #   mapfile -t NAME    reads lines from its input into the array NAME,
    #                      one item per line; -t removes the newline at
    #                      the end of each.
    #   < <( command )     PROCESS SUBSTITUTION: <( command ) runs the
    #                      command and makes its output look like a file;
    #                      the first < feeds that "file" to mapfile.
    #                      (Why not `command | mapfile`? Each side of a
    #                      pipe runs in a separate copy of the shell, so
    #                      the array would vanish when the pipe ended.)
    #
    # | tr -d '\r' — WINDOWS LINE ENDINGS
    #   On Windows, Python ends printed lines with "\r\n" (carriage return
    #   + newline), while bash expects just "\n". mapfile -t removes the
    #   \n, but the invisible \r would stay glued to every name, and
    #   "gharchive-...-6h\r" is not a database that exists. tr -d '\r'
    #   ("translate: delete") removes every \r character.
    # -----------------------------------------------------------------
    mapfile -t DATABASES < <(./run.sh scripts/choose_starts.py --list-databases | tr -d '\r')
    # ${#DATABASES[@]} — the number of items in the array. -eq: "equals".
    # None: there's nothing to measure; say what to run first.
    if [ ${#DATABASES[@]} -eq 0 ]; then
        echo "There's no database to measure yet. Load one first: ./run.sh scripts/build_hours.py" >&2
        exit 1
    fi
    echo ""
    echo "Databases you can measure:"
    # -----------------------------------------------------------------
    # A numbered menu.
    #   "${!DATABASES[@]}"   the INDEXES of the array: 0 1 2 ... (the !
    #                        asks for the positions, not the values)
    #   ${DATABASES[$i]}     the item at position i
    #   $((i + 1))           ARITHMETIC: bash computes i + 1, so the menu
    #                        starts at 1 rather than 0, as people count.
    # -----------------------------------------------------------------
    for i in "${!DATABASES[@]}"; do
        echo "  $((i + 1))) ${DATABASES[$i]}"
    done
    # -----------------------------------------------------------------
    # read -r -p "question " CHOICE
    #   Shows the question (-p: "prompt") and waits for you to type
    #   something and press Enter; what you typed goes into CHOICE.
    #   -r keeps backslashes as typed (always a good habit with read).
    # -----------------------------------------------------------------
    read -r -p "Which one? (number) " CHOICE
    # -----------------------------------------------------------------
    # CHECK THE ANSWER before using it.
    #
    # [[ "$CHOICE" =~ ^[0-9]+$ ]] — a REGULAR EXPRESSION test (bash's
    # [[ ]] form; =~ means "matches the pattern"):
    #   ^       the start of the text
    #   [0-9]+  one or more digits
    #   $       the end of the text
    # i.e. "only digits, nothing else". `!` in front reverses it: "is NOT
    # a number". This check comes first because -lt / -gt below would
    # give an error if CHOICE were, say, "abc".
    #
    # || means OR, between three tests: not a number, OR below 1 (-lt:
    # "less than"), OR above the number of databases. Any of them: refuse,
    # without doing anything.
    # -----------------------------------------------------------------
    if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt ${#DATABASES[@]} ]; then
        echo "Not a number from the list; nothing done." >&2
        exit 1
    fi
    # The menu showed 1, 2, 3..., the array counts 0, 1, 2...: hence - 1.
    DATABASE="${DATABASES[$((CHOICE - 1))]}"
fi

# ---------------------------------------------------------------------
# THE MEASUREMENT, through run.sh.
#
# measure.py does everything else: it chooses (or reuses) the starting
# actors, measures the traversal on both sides and writes ONE CSV file
# for this measurement, results/<database>_<date>_<time>.csv (one line =
# one question answered by both databases; the columns are explained in
# the README and in docs_english/measure.py). One analysis = one file,
# easy to open and understand on its own.
#
# "$DATABASE" is always in double quotes: the value is passed as ONE
# argument, exactly as is. \" inside "..." prints a literal " character.
#
# "${MEASURE_OPTIONS[@]}" — expands to every item of the array, EACH as
# a separate argument: --max-depth 4 --timeout 60. If the array is empty
# it expands to nothing at all, and measure.py uses its own defaults.
#
# Thanks to set -e, if measure.py fails, the "Done" line is never shown.
# ---------------------------------------------------------------------
echo ""
echo "== 1. Measure \"$DATABASE\""
./run.sh scripts/measure.py --database "$DATABASE" "${MEASURE_OPTIONS[@]}"

echo "Done. The results are in results/ (one CSV per measurement; its columns are explained in the README)."
