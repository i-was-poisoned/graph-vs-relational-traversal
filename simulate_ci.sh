#!/usr/bin/env bash
# Run the CI's integration tests locally, in the same Docker containers GitHub
# Actions uses (.github/workflows/ci.yml, job "integration-tests"):
#     PostgreSQL 18.6, Neo4j 2026.10.0 Community, Python 3.14.0
#
# Usage (from Git Bash, with Docker Desktop running):
#     ./simulate_ci.sh
#
# Your own PostgreSQL and Neo4j are never touched: the three containers share
# one private network (that of the Neo4j container) and publish no port, so
# they don't clash with the servers already using ports 5432 and 7687.
# The database containers (and their data) are removed at the end; the downloaded images stay,
# so the next run starts in seconds.

set -u
# Stop Git Bash from rewriting paths like /src inside the docker commands.
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")"
PROJECT_DIR="$(cygpath -w "$PWD" 2>/dev/null || pwd)"

if ! docker info >/dev/null 2>&1; then
    echo "Docker isn't running. Open Docker Desktop, wait for \"Engine running\", and try again." >&2
    exit 1
fi

# -v also deletes the containers' anonymous volumes: the postgres and neo4j images keep
# their data in volumes, which "docker rm" alone would leave behind on every run.
cleanup() { docker rm -f -v gvr-ci-postgres gvr-ci-neo4j >/dev/null 2>&1; }
cleanup
trap cleanup EXIT

echo "== Starting Neo4j 2026.10.0 Community (authentication off)"
docker run -d --name gvr-ci-neo4j -e NEO4J_AUTH=none neo4j:2026.10.0-community >/dev/null || exit 1

echo "== Starting PostgreSQL 18.6 (no password) in the same private network"
docker run -d --name gvr-ci-postgres --network container:gvr-ci-neo4j \
    -e POSTGRES_HOST_AUTH_METHOD=trust postgres:18.6 >/dev/null || exit 1

echo "== Waiting for PostgreSQL"
for _ in $(seq 1 30); do
    docker exec gvr-ci-postgres pg_isready -U postgres -h localhost >/dev/null 2>&1 && break
    sleep 2
done

echo "== Running the integration tests in Python 3.14.0"
# The project is mounted read-only; only what the tests need is copied inside.
docker run --rm --network container:gvr-ci-neo4j \
    -v "${PROJECT_DIR}:/src:ro" \
    -e NEO4J_PASSWORD=unused-authentication-is-off \
    -e TEST_NEO4J_DATABASE=neo4j \
    python:3.14.0-slim bash -c '
        mkdir /work &&
        cp -r /src/scripts /src/tests /src/pytest.ini /src/requirements.txt /src/requirements-dev.txt /work/ &&
        cd /work &&
        python -m pip install -q --root-user-action=ignore --disable-pip-version-check -r requirements-dev.txt &&
        python -m pytest -v -m integration -p no:cacheprovider
    '
