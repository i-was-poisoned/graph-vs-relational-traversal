# graph-vs-relational-traversal

At what traversal depth, and at what data volume, does a property graph model outperform an equivalent normalized relational model for the same query?

## Dataset

Data source: [GH Archive](https://www.gharchive.org/), which publishes hourly
dumps of every public GitHub event. See
[docs_english/gh-archive-guide.md](docs_english/gh-archive-guide.md) for a full explanation of
what GH Archive is and how it works.

This project uses a single, fixed hour for reproducibility:

- **Date/hour:** 2026-08-27, 15:00 UTC
- **URL:** https://data.gharchive.org/2026-08-27-15.json.gz
- **Why this hour:** a weekday (Thursday), within the ~13:00-19:00 UTC window
  where US and European activity overlap, giving high event volume for
  building a meaningfully connected graph. It is also comfortably in the past,
  so the file is guaranteed to be published and available.

Download it with:

```bash
python scripts/download_gharchive.py
```

## Schema

The schema is designed **query-first**: it contains only what the
benchmarked traversal (`actor → repo → actor → repo`, at increasing depths)
needs, and it is the same logical model on both sides, so the comparison
stays like-for-like.

Why the walk goes through repos: in this dataset almost every event is a
`PushEvent` (95.3%), which names no second person, and only 0.26% of events
name a genuinely different user. People are therefore connected through the
repos they share, not directly. See
[docs_english/project-notes.md](docs_english/project-notes.md) (Schema Design
Stage) for the full analysis.

| Concept | Relational (PostgreSQL) | Graph (Neo4j) |
|---|---|---|
| Actor | table `actor` (`id`, `login`) | node `:Actor` (`id`, `login`) |
| Repo | table `repo` (`id`, `name`) | node `:Repo` (`id`, `name`) |
| Connection | table `actor_repo` (`actor_id`, `repo_id`) | edge `(:Actor)-[:INTERACTED_WITH]->(:Repo)` |
| Unique keys / indexes | primary keys on `actor.id`, `repo.id`, `(actor_id, repo_id)`, plus an index on `actor_repo.repo_id` | uniqueness constraints on `Actor.id`, `Repo.id` |

- Both sides use a database called `gharchive`.
- Keys use GitHub's numeric ids (`event["actor"]["id"]`, `event["repo"]["id"]`),
  not names: a user can change their login, but their id never changes.
- **One connection per actor–repo pair**, never repeated: ten pushes by the
  same actor to the same repo are a single connection.
- Bot accounts (logins ending in `[bot]`) are excluded, since they act as
  artificial hubs between unrelated repos.
- Both databases are loaded from the same extracted CSV files, and their
  counts are checked to match:

| | Actors | Repos | Connections |
|---|---|---|---|
| PostgreSQL and Neo4j (2026-08-27, 15:00 UTC, no bots) | 14,515 | 14,995 | 15,053 |

The pipeline that builds them:

```bash
./run.sh scripts/extract_csv.py      # JSON -> data/csv/{actors,repos,actor_repo}.csv
./run.sh scripts/load_postgres.py    # CSVs -> PostgreSQL (tables, keys, index, ANALYZE)
./run.sh scripts/load_neo4j.py       # same CSVs -> Neo4j (nodes, edges, constraints)
```

## Tools and versions

Everything runs locally on the same machine, so neither database gains an
advantage from network or hardware differences.

| Tool | Version | Role |
|---|---|---|
| Python | 3.14.0 | Scripts for downloading, profiling, loading and timing |
| PostgreSQL | 18.6 | Relational database (managed with pgAdmin 4 or `psql`) |
| Neo4j | 2026.10.0 (Enterprise Edition bundled with Neo4j Desktop, free for local development) | Graph database (managed with Neo4j Desktop and Neo4j Browser) |
| psycopg | 3.3.6 | Python connector for PostgreSQL |
| neo4j (Python driver) | 6.4.1 | Python connector for Neo4j |

Versions are pinned on purpose: this project compares two tools, so every
condition (database versions, connectors, Python) must stay the same across
all measurements. If any of them is upgraded, the change is recorded here and
every measurement is repeated.

## Setup

The Python connectors are installed in a project-only **virtual environment**
(`.venv`, not committed), from the pinned [requirements.txt](requirements.txt):

```bash
python -m venv .venv
source .venv/Scripts/activate        # Git Bash on Windows
python -m pip install -r requirements.txt
```

Database passwords are never stored in the repository. They live in a local,
git-ignored `secrets.sh` (created from the [secrets.example.sh](secrets.example.sh)
template) as environment variables: `PGPASSWORD` (read automatically by
PostgreSQL/psycopg) and `NEO4J_PASSWORD` (read by the project's scripts).

```bash
cp secrets.example.sh secrets.sh     # then fill in your passwords
```

Scripts that need the databases are run through [run.sh](run.sh), which
activates `.venv`, loads `secrets.sh` and runs Python (which inherits the
passwords only for that run). `run.sh` is a generic launcher: always give it
the script to run, followed by that script's own options, if any. For
example, to check that both databases are reachable:

```bash
./run.sh scripts/check_connections.py
# or, equivalently (e.g. if ./run.sh says "Permission denied"):
bash run.sh scripts/check_connections.py
```

Any other script works the same way, e.g.
`./run.sh scripts/summarize_data.py --top 10`.

Step-by-step installation of PostgreSQL, Neo4j and the virtual environment
(with checks and troubleshooting) is in
[docs_english/project-notes.md](docs_english/project-notes.md), section
"Installing the software".
