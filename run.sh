#!/usr/bin/env bash
# Run one of the project's Python scripts with everything it needs loaded:
# the .venv virtual environment and the database passwords from secrets.sh.
#
# Usage (from Git Bash, in the project folder):
#     ./run.sh scripts/check_connections.py
#     ./run.sh scripts/some_script.py --some-option value
#
# The passwords only exist while this script runs: Python inherits them from
# this shell, and they disappear as soon as it finishes. Your own terminal
# never has them set.

set -eo pipefail

# Work from the project folder, wherever run.sh was called from.
cd "$(dirname "$0")"

# run.sh is a generic launcher: it prepares the environment, then runs the
# Python script named right after it. $# is the number of arguments given to
# run.sh; if it's 0, there's no script to run, so explain and stop.
if [ $# -eq 0 ]; then
    echo "run.sh needs the Python script to run, written right after it." >&2
    echo "" >&2
    echo "Usage:" >&2
    echo "    ./run.sh <script.py> [script options...]" >&2
    echo "    bash run.sh <script.py> [script options...]   (same thing)" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "    ./run.sh scripts/check_connections.py" >&2
    echo "    ./run.sh scripts/summarize_data.py --top 10" >&2
    exit 1
fi

if [ ! -f .venv/Scripts/activate ]; then
    echo "Missing virtual environment (.venv)." >&2
    echo "Create it with: python -m venv .venv  (see project notes, step 3)" >&2
    exit 1
fi

if [ ! -f secrets.sh ]; then
    echo "Missing secrets.sh." >&2
    echo "Create it with: cp secrets.example.sh secrets.sh  and fill in your passwords" >&2
    echo "(see project notes, step 4)" >&2
    exit 1
fi

source .venv/Scripts/activate
source secrets.sh

if [ "$PGPASSWORD" = "your-postgres-password" ] || [ "$NEO4J_PASSWORD" = "your-neo4j-password" ]; then
    echo "secrets.sh still has the template's placeholder passwords." >&2
    echo "Open it and replace them with your real ones." >&2
    exit 1
fi

# Replace this shell with Python, passing the script and any arguments through.
exec python "$@"
