#!/usr/bin/env bash
# Run the whole research for one database, in order:
#     1. choose_starts.py  - the 10 top and 10 median starting actors (same on both sides)
#     2. measure.py        - the traversal in PostgreSQL and Neo4j, timed and checked
#     3. analyze.py        - the summary tables, and the comparison of every volume measured
#
# Usage (from Git Bash, with PostgreSQL running and Neo4j Desktop open):
#     ./research.sh                                     # asks which database to measure
#     ./research.sh --database gharchive-2026-08-27-12-6h
#     ./research.sh --database ... --max-depth 4 --repeats 5 --timeout 60
#
# The work is done by the Python scripts; this file only runs them in order,
# asks the one question, and stops at the first step that fails. Each script
# can also be run alone with ./run.sh (see README).

set -eo pipefail
cd "$(dirname "$0")"

DATABASE=""
MEASURE_OPTIONS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --database) DATABASE="$2"; shift 2 ;;
        --max-depth|--repeats|--timeout) MEASURE_OPTIONS+=("$1" "$2"); shift 2 ;;
        *) echo "Unknown option: $1 (see the top of research.sh)" >&2; exit 1 ;;
    esac
done

echo "== 0. Check that both servers are answering"
./run.sh scripts/check_connections.py

if [ -z "$DATABASE" ]; then
    mapfile -t DATABASES < <(./run.sh scripts/choose_starts.py --list-databases | tr -d '\r')
    if [ ${#DATABASES[@]} -eq 0 ]; then
        echo "There's no database to measure yet. Load one first: ./run.sh scripts/build_hours.py" >&2
        exit 1
    fi
    echo ""
    echo "Databases you can measure:"
    for i in "${!DATABASES[@]}"; do
        echo "  $((i + 1))) ${DATABASES[$i]}"
    done
    read -r -p "Which one? (number) " CHOICE
    if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt ${#DATABASES[@]} ]; then
        echo "Not a number from the list; nothing done." >&2
        exit 1
    fi
    DATABASE="${DATABASES[$((CHOICE - 1))]}"
fi

echo ""
echo "== 1. Choose the starting actors in \"$DATABASE\""
./run.sh scripts/choose_starts.py --database "$DATABASE"

echo ""
echo "== 2. Measure the traversal in \"$DATABASE\""
./run.sh scripts/measure.py --database "$DATABASE" "${MEASURE_OPTIONS[@]}"

echo ""
echo "== 3. Analyse"
./run.sh scripts/analyze.py --database "$DATABASE"

echo "Done. Everything is in results/$DATABASE/"
