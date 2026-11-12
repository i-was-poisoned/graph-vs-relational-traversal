# graph-vs-relational-traversal

[![CI](https://github.com/i-was-poisoned/graph-vs-relational-traversal/actions/workflows/ci.yml/badge.svg)](https://github.com/i-was-poisoned/graph-vs-relational-traversal/actions/workflows/ci.yml)

At what traversal depth, and at what data volume, does a property graph model outperform an equivalent normalized relational model for the same query?

## Two processes

The project runs two separate processes. Each one loads its data into a
database **with the same name on both servers** (PostgreSQL and Neo4j), so
the two models always hold exactly the same data.

| | 1. Benchmark data (hours you choose) | 2. Daily 24-hour pipeline |
|---|---|---|
| **Data** | One hour, or several consecutive hours, chosen by you | The 24 complete hours that ended 24 hours ago |
| **Database** (PostgreSQL and Neo4j) | `gharchive` for the fixed benchmark hour (2026-08-27, 15:00 UTC); `gharchive-<date>-<hour>` for every other choice, e.g. `gharchive-2026-11-10-9` (1 hour) or `gharchive-2026-11-10-9-3h` (3 hours) | `gharchive24h` |
| **Built by** | You, by hand: `build_hours.py` asks for the date, the first hour and how many hours (the fixed hour was built step by step with `extract_csv.py`, `load_postgres.py`, `load_neo4j.py`) | `pipeline.py`, started **once a day** by Windows Task Scheduler, without asking anything |
| **Changes?** | **Never by itself.** `gharchive` is frozen, so every measurement can be repeated on the same data; the other databases only change if you load the same choice again, which empties them first | Rebuilt on every run |
| **Purpose** | Measuring and comparing queries under repeatable conditions, at different data volumes | Fresh, larger data through a repeatable, automatic data-engineering process |

```
PostgreSQL (port 5432)                      Neo4j (instance "gharchive", port 7687)
├── gharchive                 <- process 1  ├── gharchive                 <- process 1 (fixed hour)
├── gharchive-2026-11-10-9    <- process 1  ├── gharchive-2026-11-10-9    <- process 1 (example)
├── gharchive-2026-11-10-9-3h <- process 1  ├── gharchive-2026-11-10-9-3h <- process 1 (example)
└── gharchive24h              <- process 2  └── gharchive24h              <- process 2
```

Neither process ever touches the other's databases: `pipeline.py` refuses
to rebuild `gharchive`, and `build_hours.py` only writes to names that start
with `gharchive-`. (Names use dashes, never underscores, because Neo4j
doesn't allow `_` in database names. Several databases on one Neo4j server
need the Enterprise Edition, which Neo4j Desktop includes for free.)

**How to run all of this, step by step, is in
[Running everything, step by step](#running-everything-step-by-step).**

## Dataset

Data source: [GH Archive](https://www.gharchive.org/), which publishes hourly
dumps of every public GitHub event. See
[docs_english/gh-archive-guide.md](docs_english/gh-archive-guide.md) for a full explanation of
what GH Archive is and how it works.

The **benchmark** uses a single, fixed hour for reproducibility:

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

- The benchmark uses a database called `gharchive` on both sides (the
  24-hour pipeline uses the same schema in `gharchive24h`).
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

How the benchmark databases are built:

```bash
./run.sh scripts/extract_csv.py      # JSON -> data/csv/{actors,repos,actor_repo}.csv
./run.sh scripts/load_postgres.py    # CSVs -> PostgreSQL (tables, keys, index, ANALYZE)
./run.sh scripts/load_neo4j.py       # same CSVs -> Neo4j (nodes, edges, constraints)
```

## Loading other hours (`build_hours.py`)

[scripts/build_hours.py](scripts/build_hours.py) builds a database from GH
Archive hours you choose. It asks three questions (press Enter to keep the
value in brackets):

| Question | Default (Enter) | Accepted answers |
|---|---|---|
| `Date (UTC)` | `2026-08-27` | A date written `YYYY-MM-DD`, from 2015-01-01 (older files use another format) |
| `First hour (UTC, 0-23)` | `15` | An hour from 0 to 23, in UTC |
| `How many consecutive hours` | `1` | From 1 to 168 (a week); the hours may cross midnight |

A wrong answer, or hours GH Archive hasn't published yet, are explained and
asked again. A last question confirms the choice (`n` = do nothing). Then it:

1. downloads the hours to `data/hours/` (hours already there are reused, even
   by another choice);
2. extracts the CSVs with `extract_csv.py` into `data/hours/csv/<database name>/`;
3. **empties the database on both servers**: deletes it if it exists
   (`DROP DATABASE ... WITH (FORCE)` in PostgreSQL, `CREATE OR REPLACE DATABASE`
   in Neo4j) and creates it again, so nothing from an earlier load survives,
   not even tables or constraints;
4. **checks that it really is empty** (PostgreSQL tables, Neo4j nodes,
   relationships and constraints must all be 0) and stops without loading
   anything if it isn't;
5. loads it with the same loaders as the benchmark and checks the counts.

Only databases whose name starts with `gharchive-` can be emptied this way;
the script refuses to empty `gharchive`, `gharchive24h` or any other
database, even by mistake.

The database name records exactly what's inside:
`gharchive-2026-11-10-9` = 1 hour from 2026-11-10 09:00 UTC;
`gharchive-2026-11-10-9-3h` = 3 hours from 2026-11-10 09:00 UTC.

## The 24-hour pipeline

[scripts/pipeline.py](scripts/pipeline.py) rebuilds the `gharchive24h`
databases (PostgreSQL and Neo4j) from the last 24 complete UTC hours, ending
24 hours ago so every hour is surely published. It asks nothing, so it can
run on its own, once a day. For example, at
2026-10-22 11:15 UTC it loads 2026-10-20 11:00 → 2026-10-21 11:00. Each run:

1. computes the window (in UTC, like GH Archive's file names);
2. downloads only the missing hours to `data/live/raw/` and deletes those that
   left the window (with retries; a missing hour stops the run);
3. extracts the CSVs with the same code as the benchmark (`extract_csv.py`);
4. checks both servers and creates `gharchive24h` if it doesn't exist —
   before emptying anything;
5. rebuilds both databases with the same loaders as the benchmark and checks
   the counts;
6. logs everything to `logs/pipeline.log` (UTC times) and records the loaded
   window in `data/live/current_window.txt`.

A lock file stops two runs from overlapping, and the exit code (0/1) tells
the scheduler whether the run succeeded.

```bash
./run.sh scripts/pipeline.py --dry-run   # show the window and planned downloads only
./run.sh scripts/pipeline.py             # real run
./run.sh scripts/pipeline.py --window-hours 6 --lag-hours 2   # other window
./run.sh scripts/pipeline.py --scheduled # what Task Scheduler runs: only if not done today and both servers answer
```

First full run (window 2026-10-20 12:00 → 2026-10-21 12:00 UTC): 160 s in
total, all counts matching.

| | Benchmark hour | 24-hour window |
|---|---|---|
| Events | 69,429 | 1,250,059 |
| Bot events skipped | 1,970 (2.8%) | 297,733 (23.8%) |
| Events without an id skipped | 0 | 2 |
| Actors / repos / connections | 14,515 / 14,995 / 15,053 | 362,730 / 406,603 / 424,098 |

The pipeline runs **on its own, once a day**: Task Scheduler checks every 15
minutes, and the pipeline does the day's work as soon as the computer is on and
both servers answer (PostgreSQL starts with Windows; Neo4j Desktop must be
opened). You never need to start it by hand. How to set it up is in [step 6](#6-process-2-let-the-pipeline-run-on-its-own-once-a-day) below. The
full design, decisions and results are in
[docs_english/project-notes.md](docs_english/project-notes.md), section "The
24-hour pipeline".

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
| pytest | 9.2.0 | Unit and integration tests (development only, `requirements-dev.txt`) |
| Docker Desktop | Engine 28.3.3 | Runs the CI's temporary PostgreSQL and Neo4j containers locally (`simulate_ci.sh`) |

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

## Running everything, step by step

All commands are typed in **Git Bash**, in the project folder
(`cd /c/dev/Research`, or wherever you cloned it). Times in GH Archive and
in the scripts are always **UTC**; Task Scheduler uses your computer's local
time.

### 0. What must be running

| Needed for | What | How to check |
|---|---|---|
| Everything that uses the databases | The **PostgreSQL** service | Windows *Services* app: `postgresql-x64-18` is *Running* |
| Everything that uses the databases | **Neo4j Desktop** open, with the instance `gharchive` **started** | Neo4j Desktop shows the instance as *Running* |
| Downloads (`download_gharchive.py`, `build_hours.py`, `pipeline.py`) | An internet connection | `https://data.gharchive.org` opens in a browser |
| Only `./simulate_ci.sh` | **Docker Desktop** open | It shows *Engine running* |

### 1. Once: set up the project

Follow [Setup](#setup): create `.venv`, install `requirements.txt` (and
`requirements-dev.txt` for the tests), and create `secrets.sh` with your
passwords. Then check that both servers answer:

```bash
./run.sh scripts/check_connections.py     # expected: "Both databases are reachable."
```

### 2. Once: build the fixed benchmark (`gharchive`)

```bash
./run.sh scripts/download_gharchive.py    # data/2026-08-27-15.json.gz and .json
./run.sh scripts/extract_csv.py           # data/2026-08-27-15.json -> data/csv/*.csv
./run.sh scripts/load_postgres.py         # data/csv -> PostgreSQL database "gharchive"
./run.sh scripts/load_neo4j.py            # data/csv -> Neo4j database "gharchive"
```

Each loader ends with a table comparing the database with the CSV files;
every line must say `OK` (14,515 actors, 14,995 repos, 15,053 connections).
This is done once: `gharchive` is frozen and nothing rebuilds it
automatically. (The PostgreSQL database `gharchive` must exist before the
first load: `CREATE DATABASE gharchive;` in pgAdmin or `psql -U postgres`.
In Neo4j, create the database `gharchive` in Neo4j Desktop or with
`CREATE DATABASE gharchive;` in Neo4j Browser.)

### 3. Process 1: load other hours, whenever you want

```bash
./run.sh scripts/build_hours.py
```

An example session (here: 3 hours from 2026-11-10 09:00 UTC):

```
Date (UTC) [2026-08-27]: 2026-11-10
First hour (UTC, 0-23) [15]: 9
How many consecutive hours [1]: 3
Load 2026-11-10 09:00 -> 2026-11-10 12:00 UTC (3 hours) into "gharchive-2026-11-10-9-3h"? (if that database already exists, it's emptied first) [Y/n]: y
```

Step 3 of its output shows the emptying and the check:

```
== 3. Empty "gharchive-2026-11-10-9-3h" on both sides, and check that it is empty
PostgreSQL: "gharchive-2026-11-10-9-3h" deleted (if it existed) and created again
Neo4j:      "gharchive-2026-11-10-9-3h" deleted (if it existed) and created again
  PostgreSQL tables      0   empty
  Neo4j nodes            0   empty
  Neo4j relationships    0   empty
  Neo4j constraints      0   empty
```

It then prints its five steps (download, extract, empty and check, load PostgreSQL,
load Neo4j), each loader's `OK` table, and finally
`Done: database "gharchive-2026-11-10-9-3h" on both sides.` As a rough guide,
one hour takes well under a minute and 24 hours about three (the first
pipeline run, 24 hours, took 160 s); downloads depend on your connection. To stop at a question, press
`Ctrl+C`: nothing is changed until you confirm.

To delete a database you no longer need, delete it **on both sides** (this
can't be undone; never do it to `gharchive`):

```sql
-- PostgreSQL (pgAdmin, or psql -U postgres); the double quotes are needed because of the dashes
DROP DATABASE "gharchive-2026-11-10-9-3h";
```

```cypher
// Neo4j Browser; the backticks are needed because of the dashes
DROP DATABASE `gharchive-2026-11-10-9-3h`;
```

The downloaded hours stay in `data/hours/` (each about 10-15 MB) and can be
deleted at any time; they're downloaded again if needed.

### 4. Process 2: run the pipeline by hand (first time, or whenever you want)

```bash
./run.sh scripts/pipeline.py --dry-run    # shows the window and what it would download; changes nothing
./run.sh scripts/pipeline.py              # real run: about 3 minutes
```

The real run ends with `Status: SUCCESS`. It downloads only the hours it
doesn't have yet, so a run one day after the previous one downloads about 24
new files and deletes the 24 that left the window.

### 5. Process 2: check what the pipeline did

| Where | What you see |
|---|---|
| `logs/pipeline.log` | Every run: the window, downloads, counts, load times and `Status: SUCCESS` or `FAILURE`. See the end with `tail -20 logs/pipeline.log` |
| `data/live/current_window.txt` | The window currently loaded in `gharchive24h`, and its counts |
| `data/live/scheduled_status.txt` (once scheduled) | What the last automatic check found: nothing to do, a server not answering yet, or whether the run succeeded |
| `data/live/last_success_date.txt` | The date (yours, not UTC) of the last successful run |

If a run fails (for example, Neo4j Desktop was closed), `gharchive24h` keeps
the previous window, unless a load had already started, and the log says why.

### 6. Process 2: let the pipeline run on its own, once a day

The pipeline is meant to be **left alone**. Task Scheduler starts it when you
log on to Windows and then **every 15 minutes**, with `--scheduled`. Each
time, the pipeline first checks two things and, if either is true, ends in a
few seconds without changing anything:

| Check | If true |
|---|---|
| Today's run (your computer's date) already succeeded | Nothing to do until tomorrow |
| PostgreSQL or Neo4j doesn't answer (e.g. Neo4j Desktop isn't open yet) | Try again 15 minutes later |

So, in practice: **turn on the computer and open Neo4j Desktop** (PostgreSQL
starts by itself with Windows), and within 15 minutes the day's pipeline runs,
once. If a run fails (e.g. GH Archive is unreachable), the next check simply
tries again. These quick checks don't write to `logs/pipeline.log`; the last
one is described in `data/live/scheduled_status.txt`, e.g.
`2026-11-12 10:15 (your time): Neo4j isn't answering (...); will try again at the next check`.

It runs **hidden** (no window), through `conhost.exe --headless`. Because of
that, Task Scheduler's *Last Run Result* is always `0x0`, even when the
pipeline failed: check `logs/pipeline.log` and
`data/live/scheduled_status.txt` instead (step 5).

**Create the task with the Task Scheduler window** (Start menu → *Task
Scheduler*):

1. *Action* → **Create Task...** (not "Create Basic Task", which hides
   the settings needed below).
2. **General** tab:
   - *Name:* `graph-vs-relational pipeline`
   - Keep **Run only when user is logged on** (Windows doesn't need to store
     your password, and Neo4j Desktop only runs while you're logged on
     anyway).
3. **Triggers** tab → *New...*:
   - *Begin the task:* **At log on**, *Specific user:* you.
   - *Advanced settings:* tick **Repeat task every:** `15 minutes`, *for a
     duration of:* **Indefinitely**.
   - *Enabled* ticked → OK.
4. **Actions** tab → *New...*:
   - *Action:* Start a program.
   - *Program/script:* `conhost.exe`
   - *Add arguments:*
     `--headless "C:\Program Files\Git\bin\bash.exe" -lc "/c/dev/Research/run.sh scripts/pipeline.py --scheduled"`
     (change `/c/dev/Research` if the project is somewhere else)
   - OK.
5. **Conditions** tab: untick **Start the task only if the computer is on AC
   power**, so it also runs on battery.
6. **Settings** tab:
   - Tick **Stop the task if it runs longer than:** 1 hour.
   - *If the task is already running:* **Do not start a new instance**.
   - OK.
7. Test it now: select the task → **Run**. Nothing appears on screen; after
   about 3 minutes, check the end of `logs/pipeline.log` (`Status: SUCCESS`)
   and `data/live/scheduled_status.txt` (`run SUCCEEDED`). Press **Run** again:
   this time it ends at once, with "today's run already succeeded".

**Or in one go, in PowerShell** (the same task and settings):

```powershell
$action   = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument '--headless "C:\Program Files\Git\bin\bash.exe" -lc "/c/dev/Research/run.sh scripts/pipeline.py --scheduled"'
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)).Repetition
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName 'graph-vs-relational pipeline' -Action $action -Trigger $trigger -Settings $settings
```

**Which data a day's run loads:** the 24 complete UTC hours ending 24 hours
before it starts. Started at 10:15 UTC on 2026-11-12, it loads
2026-11-10 10:00 → 2026-11-11 10:00 UTC. (10:00 UTC is 10:00 in Lisbon in
winter and 11:00 in Madrid; in summer, one hour more.) So the window depends
on when you open the servers that day.

**To pause or remove it:** right-click the task → *Disable* (or *Delete*).
Nothing else depends on it. Running the pipeline by hand (step 4) also counts
as the day's run.

### 7. Run the tests

```bash
source .venv/Scripts/activate && python -m pytest   # unit tests: no internet, no databases
./run.sh -m pytest -m integration                   # integration tests on your servers (database "gharchivetest")
./simulate_ci.sh                                     # integration tests in Docker, exactly as in CI
```

Details in [Tests](#tests).

### 8. When something goes wrong

| Message | Cause | What to do |
|---|---|---|
| `Missing virtual environment (.venv)` / `Missing secrets.sh` | Step 1 not done | Do [Setup](#setup) |
| `connection to server at "localhost" ... failed` | The PostgreSQL service isn't running | Start it in the *Services* app |
| A Neo4j connection error mentioning `localhost:7687` | Neo4j Desktop is closed, or the instance is stopped | Open Neo4j Desktop and start the instance |
| `... does not exist (not published yet?)` | That hour isn't on GH Archive yet (or never was) | Choose an older hour; the pipeline retries on its next run |
| `Another pipeline run is still in progress; skipping this one` | A previous run is still going | Wait; a lock older than 3 hours is removed automatically |
| `MISMATCH` in a loader's table | A database doesn't hold what the CSVs say | Run the same command again; if it repeats, check the log |
| The day's data never arrives | Neo4j Desktop wasn't opened, or every run failed | Read `data/live/scheduled_status.txt` and the end of `logs/pipeline.log` |
| `Permission denied` for `./run.sh` | The file lost its "executable" flag | Use `bash run.sh ...` instead |

## Tests

Unit tests for the parts of the pipeline with their own logic (bot filtering,
empty-repo events, latest names, unique connections, the rolling window, GH
Archive file names, CSV reading, and `build_hours.py`'s questions and
database names) live in [tests/](tests/). They use tiny
made-up events in a temporary folder, so they need neither the internet nor
the databases (and no passwords):

```bash
source .venv/Scripts/activate
python -m pip install -r requirements-dev.txt   # pytest, pinned; once
python -m pytest
```

**Integration tests** ([tests/test_integration.py](tests/test_integration.py))
load the same tiny data set into real PostgreSQL and Neo4j databases and check
that both hold exactly the same actors, repos and connections, and that a
two-hop traversal gives the same answer in SQL and Cypher. They are marked
`integration`, so the plain command above skips them. They never use the
`gharchive` or `gharchive24h` databases, only a separate test database:

```bash
./run.sh -m pytest -m integration    # against your local servers (database "gharchivetest")
./simulate_ci.sh                     # in Docker containers, exactly as in CI
```

GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs both
on every push and pull request: the unit tests, and the integration tests
against temporary PostgreSQL 18.6 and Neo4j 2026.10.0 Community containers.
The badge at the top shows the latest result.

Which functions are tested, which aren't and why is explained in
[docs_english/project-notes.md](docs_english/project-notes.md), section
"Unit tests with pytest".
