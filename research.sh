#!/usr/bin/env bash
# Run the research for one database:
#     0. check that both servers answer
#     1. ask which database to measure (unless --database is given)
#     2. measure.py: choose (or reuse) the starting actors, measure the traversal in
#        PostgreSQL and Neo4j, and write the results to one Excel file in results/
#
# Usage (from Git Bash, with PostgreSQL running and Neo4j Desktop open):
#     ./research.sh                                     # asks which database to measure
#     ./research.sh --database gharchive-2026-10-08-9-24h
#     ./research.sh --database ... --max-depth 4 --repeats 5 --timeout 60 --cypher both
#     ./research.sh --new-starts                        # choose the starting actors again
#
# The work is done by the Python scripts; this file only runs them in order,
# asks the one question, and stops at the first step that fails.

set -eo pipefail
cd "$(dirname "$0")"

DATABASE=""
MEASURE_OPTIONS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --database) DATABASE="$2"; shift 2 ;;
        --max-depth|--repeats|--timeout|--cypher) MEASURE_OPTIONS+=("$1" "$2"); shift 2 ;;
        --new-starts) MEASURE_OPTIONS+=("$1"); shift ;;
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
echo "== 1. Measure \"$DATABASE\""
./run.sh scripts/measure.py --database "$DATABASE" "${MEASURE_OPTIONS[@]}"

echo "Done. The results are in results/ (one Excel file per measurement; its columns are explained in the README)."
