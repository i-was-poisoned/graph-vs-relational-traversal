# graph-vs-relational-traversal

[![CI](https://github.com/i-was-poisoned/graph-vs-relational-traversal/actions/workflows/ci.yml/badge.svg)](https://github.com/i-was-poisoned/graph-vs-relational-traversal/actions/workflows/ci.yml)

At what traversal depth, and at what data volume, does a property graph model outperform an equivalent normalized relational model for the same query?

## Two processes

The project runs two separate processes. Each one loads its data into a
database **with the same name on both servers** (PostgreSQL and Neo4j), so
the two models always hold exactly the same data.

| | 1. Manual pipeline (hours you choose) | 2. Automatic 24-hour pipeline |
|---|---|---|
| **Data** | One hour, or several consecutive hours, chosen by you | The 24 complete hours that ended 24 hours ago |
| **Database** (PostgreSQL and Neo4j) | `gharchive-<date>-<hour>`, e.g. `gharchive-2026-11-10-9` (1 hour) or `gharchive-2026-11-10-9-3h` (3 hours); plus `gharchive`, the fixed benchmark hour (2026-08-27, 15:00 UTC) | `gharchive24h` |
| **Started by** | You: `./run.sh scripts/build_hours.py` asks for the date, the first hour and how many hours | Nobody: Windows Task Scheduler's trigger starts `pipeline.py` on its own, once a day, without asking anything |
| **Changes?** | **Never by itself.** `gharchive` is frozen, so every measurement can be repeated on the same data; the other databases only change if you load the same choice again, which empties them first | Rebuilt once a day |
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

## Setup (once, before anything else)

**Use Git Bash, not PowerShell.** Every command in this README is written for
**Git Bash** (installed with Git for Windows: Start menu → *Git Bash*).
PowerShell and the Command Prompt don't understand `source` or `./run.sh`.
You know you're in Git Bash when the prompt ends with `$` and shows paths like
`/c/dev/Research`; PowerShell shows `PS C:\dev\Research>`.

Go to the project folder:

```bash
cd /c/dev/Research
```

### A. The virtual environment (`.venv`): create it only once

The Python connectors are installed in a project-only **virtual environment**
(`.venv`, not committed), from the pinned [requirements.txt](requirements.txt).
**If the folder `.venv` already exists, skip this step**: it's already done.

```bash
python -m venv .venv                              # creates the .venv folder (only once)
source .venv/Scripts/activate                     # turns it on in this terminal; the prompt shows (.venv)
python -m pip install -r requirements.txt         # the database connectors
python -m pip install -r requirements-dev.txt     # pytest, for the tests
```

(`python -m venv .venv` fails with `Unable to copy ... venvlauncher.exe` if
`.venv` already exists and is turned on: it's trying to overwrite the Python
that's running. Nothing is broken; just don't create it again.)

### B. The passwords (`secrets.sh`): once

Database passwords are never stored in the repository. They live in a local,
git-ignored `secrets.sh` (created from the [secrets.example.sh](secrets.example.sh)
template) as environment variables: `PGPASSWORD` (read automatically by
PostgreSQL/psycopg) and `NEO4J_PASSWORD` (read by the project's scripts).

```bash
cp secrets.example.sh secrets.sh     # then open it and fill in your passwords
```

### C. Check that everything works

Scripts that need the databases are run through [run.sh](run.sh), which
activates `.venv` and loads `secrets.sh` by itself (so you don't need
`source` for them), then runs Python, which inherits the passwords only for
that run. `run.sh` is a generic launcher: always give it the script to run,
followed by that script's own options, if any. With PostgreSQL running and
Neo4j Desktop open:

```bash
./run.sh scripts/check_connections.py     # expected: "Both databases are reachable."
# or, equivalently (e.g. if ./run.sh says "Permission denied"):
bash run.sh scripts/check_connections.py
```

Step-by-step installation of PostgreSQL, Neo4j and the virtual environment
(with checks and troubleshooting) is in
[docs_english/project-notes.md](docs_english/project-notes.md), section
"Installing the software".

## 1. The manual pipeline, step by step

First do the [Setup](#setup-once-before-anything-else), once. All commands
are typed in **Git Bash**, in the project folder. Times in GH Archive and in
the scripts are always **UTC**.

### Step 0. What must be running

| Needed for | What | How to check |
|---|---|---|
| Everything that uses the databases | The **PostgreSQL** service (it starts by itself with Windows) | Windows *Services* app: `postgresql-x64-18` is *Running* |
| Everything that uses the databases | **Neo4j Desktop** open, with the instance `gharchive` **started** | Neo4j Desktop shows the instance as *Running* |
| Downloads | An internet connection | `https://data.gharchive.org` opens in a browser |

### Step 1. Once: build the fixed benchmark (`gharchive`)

The benchmark's reference hour was built step by step, one script per stage:

```bash
./run.sh scripts/download_gharchive.py    # data/2026-08-27-15.json.gz and .json
./run.sh scripts/extract_csv.py           # data/2026-08-27-15.json -> data/csv/*.csv
./run.sh scripts/load_postgres.py         # data/csv -> PostgreSQL database "gharchive"
./run.sh scripts/load_neo4j.py            # data/csv -> Neo4j database "gharchive"
```

Each loader ends with a table comparing the database with the CSV files;
every line must say `OK` (14,515 actors, 14,995 repos, 15,053 connections).
This is done once: `gharchive` is frozen and nothing rebuilds it. (The
database `gharchive` must exist before the first load: `CREATE DATABASE
gharchive;` in pgAdmin or `psql -U postgres`, and in Neo4j Desktop or Neo4j
Browser.)

### Step 2. Load the hours you choose

```bash
./run.sh scripts/build_hours.py
```

It asks three questions (press Enter to keep the value in brackets):

| Question | Default (Enter) | Accepted answers |
|---|---|---|
| `Date (UTC)` | `2026-08-27` | A date written `YYYY-MM-DD`, from 2015-01-01 (older files use another format) |
| `First hour (UTC, 0-23)` | `15` | An hour from 0 to 23, in UTC |
| `How many consecutive hours` | `1` | From 1 to 168 (a week); the hours may cross midnight |

A wrong answer, or hours GH Archive hasn't published yet, are explained and
asked again. A last question confirms the choice (`n`, or `Ctrl+C`, = do
nothing):

```
Date (UTC) [2026-08-27]: 2026-11-10
First hour (UTC, 0-23) [15]: 9
How many consecutive hours [1]: 3
Load 2026-11-10 09:00 -> 2026-11-10 12:00 UTC (3 hours) into "gharchive-2026-11-10-9-3h"? (if that database already exists, it's emptied first) [Y/n]: y
```

The database name records exactly what's inside:
`gharchive-2026-11-10-9` = 1 hour from 2026-11-10 09:00 UTC;
`gharchive-2026-11-10-9-3h` = 3 hours from 2026-11-10 09:00 UTC.

### Step 3. What it does after you confirm

Every stage announces what it's about to do and then confirms it, always
naming the database:

| Stage | What happens |
|---|---|
| **0. Check the servers** | Both PostgreSQL and Neo4j must answer; if one doesn't, it stops with "Nothing was changed" (so one side is never emptied while the other can't be) |
| **1. Download** | The hours go to `data/hours/` (each about 10-15 MB); hours already there are reused, even by another choice |
| **2. Extract** | `extract_csv.py` turns the events into `actors.csv`, `repos.csv` and `actor_repo.csv` in `data/hours/csv/<database name>/` (bots left out) |
| **3. Empty and check** | Deletes the database on both servers if it exists (`DROP DATABASE ... WITH (FORCE)` in PostgreSQL, `CREATE OR REPLACE DATABASE` in Neo4j) and creates it again, then **checks that it's really empty** (PostgreSQL tables, Neo4j nodes, relationships and constraints all 0); if not, it stops without loading anything |
| **4. Load PostgreSQL** | `load_postgres.py` creates the tables and loads them; every count must match its CSV file |
| **5. Load Neo4j** | `load_neo4j.py` creates the constraints, nodes and relationships; every count must match its CSV file |

Stage 3, for example, when loading the same choice a second time:

```
== 3. Empty the database "gharchive-2026-11-10-9-3h" on both sides, and check that it is empty
Deleting the PostgreSQL database "gharchive-2026-11-10-9-3h" and all its data ...
The PostgreSQL database "gharchive-2026-11-10-9-3h" has been deleted.
Creating the PostgreSQL database "gharchive-2026-11-10-9-3h" (empty) ...
The PostgreSQL database "gharchive-2026-11-10-9-3h" has been created.
Deleting the Neo4j database "gharchive-2026-11-10-9-3h" and all its data, then creating it again (empty) ...
The Neo4j database "gharchive-2026-11-10-9-3h" has been deleted and created again.
Checking that the database "gharchive-2026-11-10-9-3h" is empty on both sides ...
  PostgreSQL tables      0   empty
  Neo4j nodes            0   empty
  Neo4j relationships    0   empty
  Neo4j constraints      0   empty
The database "gharchive-2026-11-10-9-3h" is empty in PostgreSQL and in Neo4j: ready to load.
```

(The first time, it says instead that the database "doesn't exist yet:
nothing to delete".) The run ends with a one-line summary and
`Done: database "gharchive-2026-11-10-9-3h".` As a rough guide, one hour
takes well under a minute and 24 hours about three; downloads depend on your
connection.

Only databases whose name starts with `gharchive-` can be emptied this way:
the script refuses to empty `gharchive`, `gharchive24h` or any other
database, even by mistake.

### Step 4. Delete a database you no longer need

Delete it **on both sides** (this can't be undone; never do it to
`gharchive`):

```sql
-- PostgreSQL (pgAdmin, or psql -U postgres); the double quotes are needed because of the dashes
DROP DATABASE "gharchive-2026-11-10-9-3h";
```

```cypher
// Neo4j Browser; the backticks are needed because of the dashes
DROP DATABASE `gharchive-2026-11-10-9-3h`;
```

The downloaded hours in `data/hours/` can be deleted at any time; they're
downloaded again if needed.

### When something goes wrong

| Message | Cause | What to do |
|---|---|---|
| `Missing virtual environment (.venv)` / `Missing secrets.sh` | Setup not done | Do the [Setup](#setup-once-before-anything-else) |
| `source : The term 'source' is not recognized` | You're in PowerShell | Open **Git Bash** instead |
| `Unable to copy ... venvlauncher.exe` | `.venv` already exists | Nothing to fix: skip `python -m venv .venv` |
| `PostgreSQL isn't answering` / `connection to server at "localhost" ... failed` | The PostgreSQL service isn't running | Start it in the *Services* app |
| `Neo4j isn't answering` / a Neo4j error mentioning `localhost:7687` | Neo4j Desktop is closed, or the instance is stopped | Open Neo4j Desktop and start the instance |
| `... does not exist (not published yet?)` | That hour isn't on GH Archive (yet) | Choose an older hour |
| `MISMATCH` / `DON'T match` | A database doesn't hold what the CSVs say | Run the same choice again (it starts from empty) |
| `Permission denied` for `./run.sh` | The file lost its "executable" flag | Use `bash run.sh ...` instead |

## 2. The automatic 24-hour pipeline

[scripts/pipeline.py](scripts/pipeline.py) keeps the `gharchive24h`
databases (PostgreSQL and Neo4j) filled with the last 24 complete UTC hours,
ending 24 hours ago so every hour is surely published. **There are no steps
to follow: it runs on its own whenever its trigger fires.**

**When it runs.** Windows Task Scheduler's trigger fires when you log on and
then every 15 minutes. Each time, the pipeline first checks:

| Check | If true |
|---|---|
| Today's run (your computer's date) already succeeded | Nothing to do until tomorrow |
| PostgreSQL or Neo4j doesn't answer (e.g. Neo4j Desktop isn't open yet) | Try again 15 minutes later |

So, in practice: **turn on the computer and open Neo4j Desktop**, and within
15 minutes the day's pipeline runs, once, hidden (no window). If a run fails
(e.g. no internet), the next check simply tries again.

**What a run does:**

1. works out the window: started at 10:15 UTC on 2026-11-12, it loads
   2026-11-10 10:00 → 2026-11-11 10:00 UTC (10:00 UTC is 10:00 in Lisbon in
   winter and 11:00 in Madrid; in summer, one hour more);
2. downloads only the missing hours to `data/live/raw/` and deletes those that
   left the window (with retries; a missing hour stops the run);
3. extracts the CSVs with the same code as process 1 (`extract_csv.py`);
4. checks both servers and creates `gharchive24h` if it doesn't exist, before
   emptying anything;
5. rebuilds both databases with the same loaders as process 1 and checks the
   counts.

A lock file stops two runs from overlapping. If a run fails, `gharchive24h`
keeps the previous window, unless a load had already started.

**Where to see what happened:**

| Where | What you see |
|---|---|
| `logs/pipeline.log` | Every real run: the window, downloads, counts, load times and `Status: SUCCESS` or `FAILURE` (`tail -20 logs/pipeline.log`) |
| `data/live/scheduled_status.txt` | What the last check found, e.g. `2026-11-12 10:15 (your time): Neo4j isn't answering (...); will try again at the next check` or `run SUCCEEDED` |
| `data/live/last_success_date.txt` | The date (yours, not UTC) of the last successful run |
| `data/live/current_window.txt` | The window currently loaded in `gharchive24h`, and its counts |

Task Scheduler's *Last Run Result* always shows `0x0`, even when a run failed
(the hidden launcher, `conhost.exe --headless`, doesn't pass the result on),
so use the files above.

First full run (window 2026-10-20 12:00 → 2026-10-21 12:00 UTC): 160 s in
total, all counts matching.

| | Benchmark hour | 24-hour window |
|---|---|---|
| Events | 69,429 | 1,250,059 |
| Bot events skipped | 1,970 (2.8%) | 297,733 (23.8%) |
| Events without an id skipped | 0 | 2 |
| Actors / repos / connections | 14,515 / 14,995 / 15,053 | 362,730 / 406,603 / 424,098 |

<details>
<summary><b>One-time setup: create the trigger in Task Scheduler</b></summary>

With the Task Scheduler window (Start menu → *Task Scheduler*):

1. *Action* → **Create Task...** (not "Create Basic Task", which hides
   the settings needed below).
2. **General** tab: *Name:* `graph-vs-relational pipeline`; keep **Run only
   when user is logged on** (Windows doesn't need to store your password, and
   Neo4j Desktop only runs while you're logged on anyway).
3. **Triggers** tab → *New...*: *Begin the task:* **At log on**, *Specific
   user:* you; *Advanced settings:* tick **Repeat task every:** `15 minutes`,
   *for a duration of:* **Indefinitely**; *Enabled* ticked → OK.
4. **Actions** tab → *New...*: *Action:* Start a program;
   *Program/script:* `conhost.exe`; *Add arguments:*
   `--headless "C:\Program Files\Git\bin\bash.exe" -lc "/c/dev/Research/run.sh scripts/pipeline.py --scheduled"`
   (change `/c/dev/Research` if the project is somewhere else) → OK.
5. **Conditions** tab: untick **Start the task only if the computer is on AC
   power**, so it also runs on battery.
6. **Settings** tab: tick **Stop the task if it runs longer than:** 1 hour;
   *If the task is already running:* **Do not start a new instance** → OK.
7. Test it: select the task → **Run**. Nothing appears on screen; after about
   3 minutes, `logs/pipeline.log` ends with `Status: SUCCESS` and
   `data/live/scheduled_status.txt` says `run SUCCEEDED`. Press **Run** again:
   this time it ends at once ("today's run already succeeded").

Or the same task in one go, in PowerShell:

```powershell
$action   = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument '--headless "C:\Program Files\Git\bin\bash.exe" -lc "/c/dev/Research/run.sh scripts/pipeline.py --scheduled"'
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)).Repetition
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName 'graph-vs-relational pipeline' -Action $action -Trigger $trigger -Settings $settings
```

To pause or remove it: right-click the task → *Disable* (or *Delete*).

</details>

<details>
<summary><b>Optional: run it by hand</b></summary>

Never needed, but useful to try something. A successful run by hand also
counts as the day's run.

```bash
./run.sh scripts/pipeline.py --dry-run   # show the window and planned downloads only; changes nothing
./run.sh scripts/pipeline.py             # real run (about 3 minutes)
./run.sh scripts/pipeline.py --window-hours 6 --lag-hours 2   # another window
./run.sh scripts/pipeline.py --scheduled # exactly what the trigger runs
```

</details>

The full design, decisions and results are in
[docs_english/project-notes.md](docs_english/project-notes.md), section "The
24-hour pipeline".

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

It's also the default answer of `build_hours.py`. How it was downloaded and
loaded is in [step 1](#step-1-once-build-the-fixed-benchmark-gharchive).

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

- Every database of both processes (`gharchive`, `gharchive-...`,
  `gharchive24h`) uses this same schema.
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

## Tests

Unit tests for the parts of the pipelines with their own logic (bot
filtering, empty-repo events, latest names, unique connections, the rolling
window, "already ran today", GH Archive file names, CSV reading, and
`build_hours.py`'s questions, database names and safety check) live in
[tests/](tests/). They use tiny made-up events in a temporary folder, so they
need neither the internet nor the databases (and no passwords):

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
`gharchive`, `gharchive-...` or `gharchive24h` databases, only a separate
test database:

```bash
./run.sh -m pytest -m integration    # against your local servers (database "gharchivetest")
./simulate_ci.sh                     # in Docker containers, exactly as in CI (needs Docker Desktop open)
```

GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs both
on every push and pull request: the unit tests, and the integration tests
against temporary PostgreSQL 18.6 and Neo4j 2026.10.0 Community containers.
The badge at the top shows the latest result.

Which functions are tested, which aren't and why is explained in
[docs_english/project-notes.md](docs_english/project-notes.md), section
"Unit tests with pytest".
