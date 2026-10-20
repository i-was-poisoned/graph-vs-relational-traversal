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

if [ $# -eq 0 ]; then
    echo "Usage: ./run.sh <script.py> [arguments...]" >&2
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
