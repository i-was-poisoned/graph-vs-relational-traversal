# graph-vs-relational-traversal

[![CI](https://github.com/i-was-poisoned/graph-vs-relational-traversal/actions/workflows/ci.yml/badge.svg)](https://github.com/i-was-poisoned/graph-vs-relational-traversal/actions/workflows/ci.yml)

At what traversal depth, and at what data volume, does a property graph model outperform an equivalent normalized relational model for the same query?

Everything needed to answer it is in this repository: anyone can load the
same GitHub data into PostgreSQL and Neo4j, run the same measurements and
see the results with their own eyes. This README explains how, in the order
it's done.

## Two processes

The project runs two separate processes. Each one loads its data into a
database **with the same name on both servers** (PostgreSQL and Neo4j), so
the two models always hold exactly the same data.

| | 1. The research (you choose the hours, then measure) | 2. The automatic 24-hour pipeline |
|---|---|---|
| **Data** | One hour, or several consecutive hours, chosen by you | The 24 complete hours that ended 24 hours ago |
| **Database** (PostgreSQL and Neo4j) | `gharchive-<date>-<hour>`, e.g. `gharchive-2026-08-27-12` (1 hour) or `gharchive-2026-08-27-12-6h` (6 hours) | `gharchive24h` |
| **Started by** | You, in this order: `drop_databases.py` (delete the databases of earlier research), `build_hours.py` (load the hours you choose), `research.sh` (measure) | Nobody: Windows Task Scheduler's trigger starts `pipeline.py` on its own, once a day, without asking anything |
| **Changes?** | **Never by itself**, so every measurement can be repeated on the same data. It only changes if you delete it, or load the same choice again (which empties it first) | Rebuilt once a day |
| **Purpose** | Measuring and comparing the same query in both databases, under repeatable conditions, at growing data volumes | Fresh data through a repeatable, automatic data-engineering process. **The research doesn't use it for now**, which is why it's explained last |

```
PostgreSQL (port 5432)                       Neo4j (instance "gharchive", port 7687)
├── gharchive-2026-08-27-12-6h  <- process 1 ├── gharchive-2026-08-27-12-6h  <- process 1 (example: 6 hours)
├── gharchive-2026-08-27-12-12h <- process 1 ├── gharchive-2026-08-27-12-12h <- process 1 (example: 12 hours)
└── gharchive24h                <- process 2 └── gharchive24h                <- process 2
```

Each script only touches its own databases: `build_hours.py` only writes to
names that start with `gharchive-`, and `pipeline.py` only to
`gharchive24h`. The one exception is `drop_databases.py`, whose job is to
delete **every** project database (every name starting with `gharchive`)
before a new research starts. (Names use dashes, never underscores, because
Neo4j doesn't allow `_` in database names. Several databases on one Neo4j
server need the Enterprise Edition, which Neo4j Desktop includes for free.)

## The order, in short

Everything happens in this order. Steps 1-5 are the setup, done **once**.
Steps 6-11 are the research.

| # | What | How often | Where it's explained |
|---|---|---|---|
| 1 | Install **PostgreSQL** and **Neo4j Desktop** (the database servers) | Once | [project-notes.md](docs_english/project-notes.md), "Installing the software" |
| 2 | Create the **environment** (`python -m venv .venv`) | Once | [Setup A](#a-the-virtual-environment-venv-create-it-only-once) |
| 3 | Install the **requirements** (`pip install -r requirements.txt`) inside it | Once | [Setup A](#a-the-virtual-environment-venv-create-it-only-once) |
| 4 | Write your passwords in **`secrets.sh`** | Once | [Setup B](#b-the-passwords-secretssh-once) |
| 5 | Check that Python reaches both servers (`check_connections.py`) | Once (then only if something seems wrong) | [Setup C](#c-check-that-everything-works) |
| 6 | Make sure the servers are **running**: PostgreSQL (starts with Windows) and Neo4j Desktop (open it, start the instance) | **Every time** | [Step 0](#step-0-what-must-be-running) |
| 7 | Run **`drop_databases.py`**: it deletes the databases left by earlier research, so you start from empty servers | **At the start of every new research**, before loading anything | [Step 1](#step-1-delete-the-databases-of-earlier-research) |
| 8 | Run **`build_hours.py`**: it asks which hours you want and puts them in both databases | Once **per volume** (6 hours, 12 hours, ...) | [Step 2](#step-2-load-the-hours-you-choose) |
| 9 | Run **`research.sh`**: it measures one database and writes the results to **one CSV file** in `results/` | Once **per volume** | [Step 4](#step-4-measure-researchsh) |
| 10 | Read the results (every column is explained) | After each measurement | [Step 5](#step-5-read-the-results) |
| 11 | **Save the iteration**: commit the new CSV in `results/` to Git | After each volume, **before** loading the next one | [Step 6](#step-6-save-the-iteration) |

So, once the setup is done, a research is just:

```bash
cd /c/dev/Research
./run.sh scripts/drop_databases.py   # step 1: delete the databases of earlier research (type "delete")
./run.sh scripts/build_hours.py      # step 2: load the hours you choose, e.g. 6 hours
./research.sh                        # step 4: measure that database and summarise the results
git add results/ && git commit -m "Results: 6 hours (gharchive-2026-08-27-12-6h)" && git push   # step 6: save the iteration
```

and then `build_hours.py` + `research.sh` + the commit again for every bigger volume
(12 hours, 1 day, ...). `drop_databases.py` is **not** run between volumes
of the same research: only once, at the very start.

There's no need to type `source .venv/Scripts/activate` first: `run.sh`
turns on the project's `.venv` and loads `secrets.sh` by itself. (Careful
with a `.venv` outside the project, e.g. `/c/dev/.venv`: it isn't this
project's, and `pip` run from `/c/dev` can't find `requirements.txt`.)

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

## 1. The research, step by step

First do the [Setup](#setup-once-before-anything-else), once. All commands
are typed in **Git Bash**, in the project folder. Times in GH Archive and in
the scripts are always **UTC**.

The research always follows the same steps, in this order:

```
Step 0  servers running
Step 1  delete the databases of earlier research   ./run.sh scripts/drop_databases.py   (once, at the start)
Step 2  load a volume                              ./run.sh scripts/build_hours.py      (once per volume)
Step 3    (what build_hours.py does, stage by stage)
Step 4  measure it                                 ./research.sh                        (once per volume)
Step 5  read the results                           results/
Step 6  save the iteration                         git add results/ ; git commit ; git push   (once per volume)
Step 7  next volume: back to step 2
```

The plan is to measure several volumes, each one loaded **from the same
day** so that only the size changes: first **6 hours**, then 12 hours, 1
day, 3 days and up to a week. (One single hour is too fragmented: its actors
run out of neighbours after one or two hops, so there is no deep traversal
to measure.)

The question each measurement answers: **from one actor, how many distinct
actors can be reached in 1, 2, ... 6 hops actor → repo → actor, and how long
does each database take to answer?**

### Step 0. What must be running

| Needed for | What | How to check |
|---|---|---|
| Everything that uses the databases | The **PostgreSQL** service (it starts by itself with Windows) | Windows *Services* app: `postgresql-x64-18` is *Running* |
| Everything that uses the databases | **Neo4j Desktop** open, with the instance `gharchive` **started** | Neo4j Desktop shows the instance as *Running* |
| Downloads | An internet connection | `https://data.gharchive.org` opens in a browser |

### Step 1. Delete the databases of earlier research

**Before putting any data in the databases, delete the ones left from
earlier research or tests.** That way every research starts from empty
servers, each volume is built the same way (by `build_hours.py`), and
there's never a doubt about what a database holds or where it came from.

```bash
./run.sh scripts/drop_databases.py
```

What it does, in order:

| Stage | What happens |
|---|---|
| **0. Check the servers** | Both PostgreSQL and Neo4j must answer; if one doesn't, it stops with "Nothing was deleted" (so one side is never cleaned while the other isn't) |
| **1. Find the project's databases** | Lists, on each server, every database whose name starts with `gharchive`: `gharchive-...` (earlier volumes), `gharchive24h` (the automatic pipeline), and `gharchive` (the fixed benchmark hour of the building phase, if it's still there). If there are none, it says so and stops |
| **2. Ask** | Shows the list and asks you to **type `delete`**. Anything else (Enter, `y`, `yes`, `Ctrl+C`) deletes nothing |
| **3. Delete them** | PostgreSQL: `DROP DATABASE ... WITH (FORCE)` (it also closes open connections, e.g. from pgAdmin). Neo4j: `DROP DATABASE ... IF EXISTS DESTROY DATA WAIT` |
| **4. Check that none is left** | Asks both servers again; it only says `Done: both servers are clean.` if no project database is left |

For example:

```
== 0. Check that both servers are answering
Both servers are answering.

== 1. Find the project's databases
PostgreSQL (2): gharchive, gharchive-2026-11-09-9-5h
Neo4j      (2): gharchive, gharchive-2026-11-09-9-5h

These databases and ALL their data will be deleted. This can't be undone.
(The server databases postgres, neo4j and system, and the files in data/, are kept.)
Type "delete" to delete them, or anything else to stop: delete

== 2. Delete them
Deleting the PostgreSQL database "gharchive" ...
The PostgreSQL database "gharchive" has been deleted.
Deleting the PostgreSQL database "gharchive-2026-11-09-9-5h" ...
The PostgreSQL database "gharchive-2026-11-09-9-5h" has been deleted.
Deleting the Neo4j database "gharchive" ...
The Neo4j database "gharchive" has been deleted.
Deleting the Neo4j database "gharchive-2026-11-09-9-5h" ...
The Neo4j database "gharchive-2026-11-09-9-5h" has been deleted.

== 3. Check that none is left
PostgreSQL: no project database left
Neo4j:      no project database left

Done: both servers are clean.
```

What it **never** deletes:

- the servers' own databases (`postgres`, `template0`, `template1`, `neo4j`,
  `system`), not even by mistake: they're excluded by name;
- the downloaded hours in `data/` (they're reused by `build_hours.py`, so a
  volume loaded again doesn't need to be downloaded again);
- the measurements in `results/` (they're files, not databases).

If the automatic pipeline is set up, `gharchive24h` is deleted too; the
pipeline creates it again on its next day's run.

**Deleting only one database, by hand.** If you only want to remove one
database, delete it **on both sides** (this can't be undone):

```sql
-- PostgreSQL (pgAdmin, or psql -U postgres); the double quotes are needed because of the dashes
DROP DATABASE "gharchive-2026-11-10-9-3h";
```

```cypher
// Neo4j Browser; the backticks are needed because of the dashes
DROP DATABASE `gharchive-2026-11-10-9-3h`;
```

### Step 2. Load the hours you choose

```bash
./run.sh scripts/build_hours.py
```

It asks three questions. The date and the hour have **no default**: you
always type them, so nothing is ever loaded for a date you didn't choose.
Only the number of hours has one (press Enter for 1):

| Question | If you press Enter | Accepted answers |
|---|---|---|
| `Date (UTC)` | Asked again | A date written `YYYY-MM-DD`, from 2015-01-01 (older files use another format) |
| `First hour (UTC, 0-23)` | Asked again | An hour from 0 to 23, in UTC |
| `How many consecutive hours` | `1` hour | From 1 to 168 (a week); the hours may cross midnight |

A wrong answer, or hours GH Archive hasn't published yet, are explained and
asked again. A last question confirms the choice (`n`, or `Ctrl+C`, = do
nothing):

```
Date (UTC, e.g. 2026-08-27): 2026-11-10
First hour (UTC, 0-23): 9
How many consecutive hours [1]: 3
Load 2026-11-10 09:00 -> 2026-11-10 12:00 UTC (3 hours) into "gharchive-2026-11-10-9-3h"? (if that database already exists, it's emptied first) [Y/n]: y
```

The database name records exactly what's inside:
`gharchive-2026-11-10-9` = 1 hour from 2026-11-10 09:00 UTC;
`gharchive-2026-11-10-9-3h` = 3 hours from 2026-11-10 09:00 UTC.

For the research, start with **6 hours of a weekday**, for example
`2026-08-27`, `12` and `6`, which creates `gharchive-2026-08-27-12-6h`. To
compare your results with ours, choose the same hours.

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

### Step 4. Measure (`research.sh`)

```bash
./research.sh
```

It checks that both servers answer, shows the databases that exist on both
sides, asks which one to measure (type its number), and runs
[measure.py](scripts/measure.py):

```
Databases you can measure:
  1) gharchive-2026-10-08-9-24h
Which one? (number) 1
```

What `measure.py` does, in order:

1. **Checks the data.** Both databases must hold the same number of actors,
   repos and connections; otherwise it stops before measuring anything.
2. **Chooses the 20 starting actors**, by fixed rules, never by hand
   ([choose_starts.py](scripts/choose_starts.py)): the **10 that reach the
   most actors in one hop** (ties: more repos, then the smaller id) and the
   **10 closest to the median** (leaving out actors that reach nobody). Both
   databases must choose exactly the same 20. If this database was
   already measured, it **reuses** the actors of its latest CSV instead, so
   a repeated measurement starts from the same place (`--new-starts`
   chooses again).
3. **For every actor and every depth from 1 to 6:**
   - a **first run** on each side, which doesn't count as a result (it
     includes preparing the query). Here **all sides must give the same
     answer**;
   - **5 timed runs**, changing which side goes first each time;
   - **one more run** with `EXPLAIN (ANALYZE, BUFFERS)` (PostgreSQL) and
     `PROFILE` (Neo4j), which report the data processed and the memory used
     inside each database.
4. **Writes the lines to its CSV file** after each actor, and prints a
   summary at the end.

Each run has a **time limit** (60 seconds). A side that runs out of time at a
depth isn't tried at the deeper depths for that actor (it could only be
slower); its lines say so.

**Two versions of the Cypher query are measured** (both give exactly the SQL's
answer):

| Version | How it walks the graph |
|---|---|
| `paths` | One pattern repeated 1 to N times. Neo4j follows **every path** and removes repeated actors only at the end, so the work grows with the number of paths: two actors who share 27 repos are connected by 27 paths, then 27 × 27, ... |
| `levels` | Level by level, **like the SQL**: each step starts from the actors found in the step before and keeps only actors never seen before |

`paths` is the obvious way to write it in Cypher; `levels` follows the same
method as the SQL. Measuring both shows how much of the difference comes from
the **database** and how much from **how the query is written**.

Options, all optional:

```bash
./research.sh --database gharchive-2026-10-08-9-24h   # don't ask, measure this one
./research.sh --max-depth 3 --repeats 2                # a quick first try
./research.sh --timeout 120                            # seconds per run (default 60)
./research.sh --cypher levels                          # only one Cypher version (default: both)
./research.sh --new-starts                             # choose the starting actors again
```

### Step 5. Read the results

**Every measurement (every analysis) writes one CSV file**, and only one, in
`results/`. Its name says which database was measured and when:

```
results/
├── gharchive-2026-10-08-9-6h_2026-11-19_10-30-00.csv    <- 6 hours, measured on 2026-11-19 at 10:30
└── gharchive-2026-10-08-9-24h_2026-11-19_14-05-12.csv   <- 24 hours, measured on 2026-11-19 at 14:05
```

The file opens in Excel. All the files have the same columns, so they can
be put together later to compare the volumes (6 hours, 24 hours, 3 days,
...).

**One line = one question answered by both databases**: "from this starting
actor, at this depth, with this volume of data, how many actors are
reached?", with PostgreSQL's and Neo4j's figures side by side. With 20
actors, 6 depths and 2 Cypher versions, each file has 240 lines.

At the end, `measure.py` also prints a short summary (the median over the
actors of each group). For example (the numbers are only an illustration):

```
  group   depth  cypher   PostgreSQL       Neo4j  faster (count of actors)
  top         3  levels      248.0 ms     30.0 ms  PG 0, Neo4j 10
  top         6  paths       904.8 ms  21,729.5 ms +8t/o  PG 10, Neo4j 0
```

(`+8t/o` = 8 actors didn't finish in time.)

#### What is measured, and why

The research question has two axes, **depth** and **data volume**, and four
things are compared for each point: **data processed, time, space and
computing power**.

Each line of a results CSV has three parts, from left to right:

```
| the test (19 columns)                | PostgreSQL (pg_..., 12 columns)  | Neo4j (neo4j_..., 12 columns)    | comparison |
| data, date, hours, sizes, question  | joins_or_hops, status, time_s ...| joins_or_hops, status, time_s ...| faster ... |
```

The **PostgreSQL and Neo4j blocks have exactly the same columns, in the same
order**: each database can be read on its own, or compared with the other one
column by column (`pg_time_s` with `neo4j_time_s`, `pg_cpu_s` with
`neo4j_cpu_s`, ...).

**1. The test (the first columns)**

| Column | What it is | Why it's there |
|---|---|---|
| `measured_at` | Date and time of the measurement (your computer's clock) | Tells measurements apart; a volume can be measured more than once |
| `database` | The database measured, e.g. `gharchive-2026-10-08-9-24h` | Its name says which hours it holds |
| `data_from_utc`, `data_to_utc` | The first and last moment of the GitHub data loaded (UTC) | Anyone can load exactly the same data and repeat the measurement |
| `volume_hours` | How many hours of GitHub activity were loaded (6, 24, 72, ...) | The **data volume** axis of the research question |
| `graph_actors`, `graph_repos`, `graph_connections` | How many actors, repos and actor–repo connections the database holds: the nodes and relationships in Neo4j, the rows of the tables `actor`, `repo` and `actor_repo` in PostgreSQL (the same in both; checked before measuring) | The real size of the data: hours alone don't say how big the graph is |
| `start_group` | `top` (one of the 10 best-connected actors) or `median` (one of 10 typical actors) | The hardest case and the usual case behave very differently |
| `start_rank` | The actor's position in its group (1 to 10) | To keep the order of the groups |
| `start_actor_id`, `start_login` | The starting actor | Anyone can repeat the traversal from the same actor |
| `start_reach_1_hop` | How many actors it reaches in one hop | How "connected" the start is; it's why the actor was chosen |
| `depth` | Hops actor → repo → actor | The **depth** axis of the research question |
| `cypher_version` | `paths` or `levels` (see [Step 4](#step-4-measure-researchsh)) | Separates the effect of the database from the effect of how the query is written |
| `actors_reached` | The answer: distinct actors reached (the starting actor not counted) | The size of the work done; it grows with depth until the connected group runs out |
| `answers_match` | `yes` if PostgreSQL and both Cypher versions gave the same answer | **A time comparison only means something if both answered the same question correctly** |
| `runs` | How many timed runs each database made (5) | The time is the median of these runs |
| `timeout_s` | The time limit of one run, in seconds (60) | Above it, a run is stopped and counted as `timeout` |

**2. PostgreSQL (`pg_...`) and 3. Neo4j (`neo4j_...`): the same columns for each**

| Column | What it is | Why it's there |
|---|---|---|
| `..._joins_or_hops` | PostgreSQL: how many `JOIN`s the SQL query makes to reach that depth. Neo4j: how many relationships the Cypher query follows. Both are 2 per hop (actor → repo, repo → actor) | The cost of a deep traversal in each model: every hop is two more `JOIN`s in SQL, two more relationships followed in Cypher |
| `..._status` | `finished`, `timeout` (didn't finish within the time limit), or `skipped (...)` (not tried, because it ran out of time at a smaller depth) | A timeout is a result, not a missing value |
| `..._time_s` | **Time**, in seconds: the **median** of the 5 timed runs, measured from Python | The main result. The median isn't moved by one slow run (an antivirus scan, an email arriving), the average is |
| `..._first_run_s` | Time of the first run, which includes preparing the query (in Neo4j, up to several seconds) | It's what someone running the query only once would wait |
| `..._data_processed_mb` | **Data processed**: MB of data pages the database went through to answer (both use pages of 8 KB; a page used twice counts twice) | Shows **how much work** each model needs for the same answer, independently of how fast the computer is |
| `..._data_from_disk_mb` | The part of the above that had to be read from disk, not from memory | Disk is much slower than memory: explains slow runs |
| `..._memory_mb` | **Space in memory**: what the query kept in memory while it ran (PostgreSQL: its hash tables, sorts and intermediate results; Neo4j: the memory of the whole query) | A database can be fast by using a lot of memory |
| `..._temp_disk_mb` | Data the query had to write to disk because it didn't fit in memory. **Only PostgreSQL** reports it (its `work_mem`); for Neo4j it's always empty | A sign that the database is short of memory |
| `..._database_mb` | **Space on disk**: the size of the whole database, in MB | What it costs to store the same data in each model |
| `..._cpu_s` | **Computing power**: CPU seconds used by the database **server** during the query (median of the 5 runs) | Measures the processor's work, not the waiting |
| `..._cores_used` | CPU seconds ÷ time: how many processor cores it used at once, on average | A database can be faster by using several cores in parallel; this makes it visible |
| `..._reliable` | `no` if the computer was busy (CPU above 80 %) or that database's runs were very uneven (slowest more than 3 × the fastest) | Results measured on a laptop in use must be read with care |

**4. The comparison (the last columns)**

| Column | What it is | Why it's there |
|---|---|---|
| `faster` | `postgresql`, `neo4j` or `neither` (neither finished) | The direct answer for that line |
| `times_faster` | How many times faster (slower time ÷ faster time). If the slower side didn't finish, it's computed with the time limit, so it's a **minimum** | How big the difference is |

The computer's characteristics (31.6 GB of RAM, Intel i7-1260P with 16
threads, Windows 11) and the databases' memory settings (both run with their
defaults: PostgreSQL `shared_buffers` 128 MB, `work_mem` 4 MB; Neo4j page
cache 512 MB, heap up to 1 GB) are the same for every line, so they're written
here instead of being repeated in the file. Results measured on another
computer will have other times, but the comparison between the two databases
should keep its shape.

**A note on Excel:** the file uses commas between columns and a point for
decimals. If Excel shows each line in a single column (it happens when
Windows is set up for a language that writes decimals with a comma), open it
with *Data → From Text/CSV* and choose *comma* as the delimiter.

### Step 6. Save the iteration

Before moving to the next volume, **save this one in Git**. `results/` only
exists on your computer until it's committed; once pushed, every iteration
is kept in the repository's history with its date, and anyone can compare
their own results with it.

```bash
git status                     # check: only the new CSV in results/ should be new
git add results/
git commit -m "Results: 24 hours (gharchive-2026-10-08-9-24h)"
git push
```

Change the message for each iteration, e.g. `"Results: 6 hours
(gharchive-2026-10-08-9-6h)"`, `"Results: 3 days (gharchive-2026-10-08-9-72h)"`.

Why nothing is lost between iterations:

- **Every measurement writes a new file**; nothing is overwritten.
  Measuring the same volume again creates another file, with another date
  and time in its name.
- **Deleting databases doesn't touch `results/`**: `drop_databases.py` only
  deletes databases, never files.

Besides the numbers, each iteration also gets its **text**: a chapter in the
report (tables, what we see, screenshots) and a section at the end of the
project notes, in the three languages.

### Step 7. The next volume

Go back to [Step 2](#step-2-load-the-hours-you-choose) with more hours from
the same day (e.g. `2026-10-08`, `9`, `72` for 3 days), measure it with
`./research.sh` (Step 4) and save it (Step 6). **Don't run
`drop_databases.py` between volumes**: it's only for the start of a new
research.

### Measuring on a computer that is in use

The scripts are designed for an ordinary laptop: the order of the sides
changes on every run, the computer's CPU load is recorded before every run,
the median is used instead of the average, and doubtful results get
`pg_reliable` or `neo4j_reliable` = `no`. Even so, close heavy programs while measuring, and run large
volumes when the computer is quiet (at lunch or at night).

### When something goes wrong

| Message | Cause | What to do |
|---|---|---|
| `Missing virtual environment (.venv)` / `Missing secrets.sh` | Setup not done | Do the [Setup](#setup-once-before-anything-else) |
| `source : The term 'source' is not recognized` | You're in PowerShell | Open **Git Bash** instead |
| `Unable to copy ... venvlauncher.exe` | `.venv` already exists | Nothing to fix: skip `python -m venv .venv` |
| `PostgreSQL isn't answering` / `connection to server at "localhost" ... failed` | The PostgreSQL service isn't running | Start it in the *Services* app |
| `Neo4j isn't answering` / a Neo4j error mentioning `localhost:7687` | Neo4j Desktop is closed, or the instance is stopped | Open Neo4j Desktop and start the instance |
| `Some databases are still there` | A deletion didn't complete | Run `drop_databases.py` again |
| `... does not exist (not published yet?)` | That hour isn't on GH Archive (yet) | Choose an older hour |
| `MISMATCH` / `DON'T match` | A database doesn't hold what the CSVs say | Run the same choice again (it starts from empty) |
| `There's no database to measure yet` | Nothing loaded | Load one first ([Step 2](#step-2-load-the-hours-you-choose)) |
| `The two databases DON'T choose the same actors` / `don't hold the same data` / `ANSWERS DIFFER` | The two sides don't hold the same data | Load the same hours again with `build_hours.py`; if it happens again, open an issue with the output |
| Many `timeout` / `skipped` statuses | Normal for deep traversals from the top actors | Raise `--timeout` if you want them to finish |
| `Permission denied` for `./run.sh` or `./research.sh` | The file lost its "executable" flag | Use `bash run.sh ...` / `bash research.sh` instead |

<details>
<summary><b>The scripts inside <code>build_hours.py</code>, one by one (not needed)</b></summary>

At the start of the project, the fixed benchmark hour `gharchive`
(2026-08-27, 15:00 UTC) was built step by step, one script per stage.
**You don't need to run these yourself:** `build_hours.py` runs the same
four scripts for you, in the same order. They're kept because
`build_hours.py` and `pipeline.py` use them inside (they share one copy of
the download, extract and load code, so every database is loaded in exactly
the same way), and because each one can still be run alone:

```bash
./run.sh scripts/download_gharchive.py    # data/2026-08-27-15.json.gz and .json
./run.sh scripts/extract_csv.py           # data/2026-08-27-15.json -> data/csv/*.csv
./run.sh scripts/load_postgres.py         # data/csv -> PostgreSQL database "gharchive"
./run.sh scripts/load_neo4j.py            # data/csv -> Neo4j database "gharchive"
```

Each loader ends with a table comparing the database with the CSV files;
every line must say `OK` (14,515 actors, 14,995 repos, 15,053 connections).
The database `gharchive` must exist before the first load: `CREATE DATABASE
gharchive;` in pgAdmin or `psql -U postgres`, and in Neo4j Desktop or Neo4j
Browser. The research doesn't use it (`drop_databases.py` deletes it):
choosing 2026-08-27, 15:00, 1 hour in `build_hours.py` gives the same data,
in `gharchive-2026-08-27-15`.

</details>

The method and every decision behind it are explained in
[docs_english/project-notes.md](docs_english/project-notes.md), section "The
research scripts", and the findings are recorded in the report:
[report/report.pdf](report/report.pdf).

## 2. The automatic 24-hour pipeline

This process is **independent of the research**: nothing in steps 0 to 7
above needs it, and the research doesn't use its data for now. It's kept
because it shows, end to end, how an automatic data pipeline is built.

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

How it was downloaded and loaded is in "The scripts inside `build_hours.py`"
(at the end of [section 1](#1-the-research-step-by-step)). The research
itself measures bigger volumes from the same day (6 hours, 12 hours, ...),
each loaded with `build_hours.py`.

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
`build_hours.py`'s questions, database names and safety check, and the
research scripts' rules: which actors are chosen, the order of the sides, the two Cypher
versions, the data window and the comparison) live in
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
