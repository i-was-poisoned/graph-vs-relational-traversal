########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/measure.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute. The real, "clean" script (with none of this
# commentary) is scripts/measure.py.
#
# Read these annotated copies first; what they explain is NOT repeated here:
#   - download_gharchive.py   argparse, Path, main() and the __name__ guard,
#                             try/except and raising FileNotFoundError
#   - extract_csv.py          csv.writer, open(..., newline=""), mkdir(parents=True),
#                             sorted(...), sets
#   - load_neo4j.py           csv.DictReader, driver.execute_query(..., database_=...)
#   - check_connections.py    psycopg / neo4j connections, `with`, sys.exit
#   - pipeline.py             RawDescriptionHelpFormatter
#   - traversal.py            the two traversal queries, the Outcome object
#                             (status / seconds / count / error), the timeouts,
#                             EXPLAIN (ANALYZE, BUFFERS) and PROFILE
#   - choose_starts.py        how the 20 starting actors are chosen, RESULTS_DIR
#                             and results/<database>/starts.csv
#
# What's NEW here — this is the script that actually produces the research's
# numbers, so most of the explanations are about MEASURING FAIRLY:
#   - run 0, the "first run": not a result (it includes the query plan being
#     prepared), but used to check that both sides give the SAME count;
#   - timed repetitions that ALTERNATE which side goes first;
#   - recording how busy the computer was (psutil) next to every run;
#   - stopping deeper depths for a side once it runs out of time;
#   - conditions.json: versions, memory settings and sizes, saved so the
#     results can be read in context later;
#   - flush(), one output folder per date and time (csv.DictWriter is
#     explained in docs_english/choose_starts.py; a reminder is below).
#
# How it's meant to be run — normally through research.sh, which runs
# choose_starts.py, then this script, then analyze.py:
#     ./research.sh --database gharchive-2026-08-27-12-6h
# or alone, through run.sh (which loads .venv and the passwords):
#     ./run.sh scripts/measure.py --database gharchive-2026-08-27-12-6h
########################################################################

"""Measure the traversal in PostgreSQL and Neo4j, from the chosen starting actors.

For every starting actor (results/<database>/starts.csv, from choose_starts.py)
and every depth from 1 to --max-depth, it:

    1. runs the traversal once on each side, not timed as a result ("first run":
       it includes preparing the query plan), and checks that BOTH SIDES GIVE
       THE SAME COUNT;
    2. runs it --repeats more times, alternating which side goes first, so that
       anything else happening on the computer affects both sides alike; each
       run records its time, its answer, whether it finished, failed or ran out
       of time (--timeout), and how busy the computer was (CPU and memory);
    3. runs it once more with EXPLAIN (ANALYZE, BUFFERS) / PROFILE, to record
       the work done inside each database.

If a side runs out of time at some depth, the deeper depths are skipped for that
side and actor (they can only be slower). The conditions (versions, memory
settings, data size) are saved too, so every result can be read later in context.

Everything goes to results/<database>/<date-time>/:
    conditions.json   versions, settings, sizes, options used
    runs.csv          one line per timed run
    work.csv          one line per actor, depth and side: the database's own figures

Usage:
    ./run.sh scripts/measure.py --database gharchive-2026-08-27-12-6h
    ./run.sh scripts/measure.py --database ... --max-depth 4 --repeats 5 --timeout 60
"""

# ---------------------------------------------------------------------
# Standard-library imports. Already met: argparse, csv, json, sys, Path.
# New ones:
#   platform  — describes the computer and Python itself: processor name,
#               operating system, Python version. Used in conditions().
#   datetime  — the current date and time: datetime.now(). Used to name
#               the output folder and to stamp conditions.json.
# ---------------------------------------------------------------------
import argparse
import csv
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------
# import psutil
#
# An EXTERNAL package (installed from requirements.txt, like psycopg and
# neo4j): "process and system utilities". It reads how busy the computer
# is — CPU use, memory in use, number of processors, total memory.
#
# Why does a benchmark need that? The laptop is also being used for other
# things while the measurement runs (a browser, an antivirus scan, Windows
# updates...). If a run was slow because the computer was busy, we want
# to SEE that next to the time, instead of blaming the database.
# ---------------------------------------------------------------------
import psutil

# ---------------------------------------------------------------------
# import choose_starts / import traversal
#
# The project's OWN scripts, imported like packages (this works because
# they're all in the same scripts/ folder). This script reuses:
#   choose_starts.RESULTS_DIR            the results/ folder
#   traversal.connect_postgres / connect_neo4j
#   traversal.run_postgres_reach / run_neo4j_reach     one timed traversal
#   traversal.postgres_work / neo4j_work               the work figures
# All of them are explained in docs_english/traversal.py and
# docs_english/choose_starts.py.
# ---------------------------------------------------------------------
import choose_starts
import traversal

# ---------------------------------------------------------------------
# The column names of the two CSV files this script writes.
#
# RUN_FIELDS — runs.csv, ONE LINE PER RUN:
#   actor_id, group    which starting actor ("top" or "median" group)
#   depth              how many hops
#   system             "postgresql" or "neo4j"
#   run                0 for the first run (not a result), then 1, 2, ...
#   status             "ok", "timeout" or "error"
#   seconds            how long it took, measured from Python
#   count              the answer: how many actors were reached
#   machine_cpu_percent, machine_memory_percent
#                      how busy the whole computer was just before the run
#   error              the error message, if any
#
# WORK_FIELDS — work.csv, the figures each DATABASE gives about its own
# work (from EXPLAIN / PROFILE, see docs_english/traversal.py):
#   server_ms                         time measured inside the server
#   blocks_from_memory / from_disk    PostgreSQL: data pages found in its
#                                     memory vs. read from disk
#   temp_blocks_written               PostgreSQL: spilled to temporary files
#                                     because work_mem was too small
#   db_hits                           Neo4j: its unit of "work done"
#   page_cache_hits / misses          Neo4j: same idea as PostgreSQL's blocks
#   memory_bytes                      Neo4j: memory the query used
#
# Keeping the column lists as constants means the header and the rows
# can never disagree (see csv.DictWriter in main()).
#
# SYSTEMS — the two sides, as a tuple, always in this order.
# ---------------------------------------------------------------------
RUN_FIELDS = ["actor_id", "group", "depth", "system", "run", "status", "seconds", "count",
              "machine_cpu_percent", "machine_memory_percent", "error"]
WORK_FIELDS = ["actor_id", "group", "depth", "system", "server_ms", "blocks_from_memory", "blocks_from_disk",
               "temp_blocks_written", "db_hits", "page_cache_hits", "page_cache_misses", "memory_bytes"]
SYSTEMS = ("postgresql", "neo4j")


# ---------------------------------------------------------------------
# def run_order(repeat) — WHICH SIDE GOES FIRST
#
# Why alternate? Anything that changes during the measurement affects
# whoever happens to run at that moment: you open a browser tab, the
# antivirus wakes up, the laptop heats up and slows down, Windows writes
# to disk... If PostgreSQL ALWAYS ran first, every such disturbance would
# land on the same side, in the same position. Alternating spreads it out
# so it hits both sides alike, and neither gets a systematic advantage
# (for example, "the second one to run always finds the data already in
# the operating system's memory").
#
# repeat % 2 — `%` is the REMAINDER of a division: 1 % 2 is 1, 2 % 2 is 0,
# 3 % 2 is 1... so `repeat % 2 == 1` means "repeat is odd".
#
# SYSTEMS[::-1] — slicing with a step of -1 gives the tuple REVERSED:
# ("neo4j", "postgresql").
#
# `A if condition else B` — a one-line if/else that gives a VALUE: A when
# the condition is True, B otherwise.
#
# -> tuple[str, str]: the function returns a tuple of two strings.
# tests/test_research.py checks this function (docs_english/test_research.py).
# ---------------------------------------------------------------------
def run_order(repeat: int) -> tuple[str, str]:
    # Repetition 1: PostgreSQL first; repetition 2: Neo4j first; and so on.
    return SYSTEMS if repeat % 2 == 1 else SYSTEMS[::-1]


# ---------------------------------------------------------------------
# def machine_load() — HOW BUSY IS THE COMPUTER RIGHT NOW
#
# psutil.cpu_percent(interval=0.2)
#   Watches the processor for 0.2 seconds and returns how much of it was
#   in use, in percent (0-100), counting ALL programs, not just ours.
#   The interval is needed: "CPU use" only means something over a period
#   of time. 0.2 s is short enough not to slow the measurement much.
#
# psutil.virtual_memory().percent
#   How much of the computer's memory (RAM) is in use, in percent.
#
# It's called just BEFORE each timed run (see measure_actor()), so each
# line of runs.csv says how busy the computer was at that moment.
# analyze.py then flags runs where the CPU was above 80 % as "noisy".
# ---------------------------------------------------------------------
def machine_load() -> tuple[float, float]:
    # CPU use of the whole computer over a short moment, and memory in use (percent).
    return psutil.cpu_percent(interval=0.2), psutil.virtual_memory().percent


# ---------------------------------------------------------------------
# def read_starts(database) — read the starting actors
#
# starts.csv was written by choose_starts.py (see
# docs_english/choose_starts.py). If it isn't there, measuring makes no
# sense, so the function raises FileNotFoundError with a message saying
# what to run first. The error is caught at the very bottom of the file
# (in the __name__ guard) and printed nicely, without a long traceback.
#
# {**row, "actor_id": int(row["actor_id"])}
#   csv.DictReader gives every value as TEXT. `**row` copies all the
#   key/value pairs of row into a NEW dict, then "actor_id": ... comes
#   after it and REPLACES that one key with a real integer. Same idea as
#   `**` unpacking a dict into keyword arguments in check_connections.py,
#   but used inside a { } dict. Everything else (group, rank, login,
#   reached) stays text — it's only printed.
# ---------------------------------------------------------------------
def read_starts(database: str) -> list[dict]:
    path = choose_starts.RESULTS_DIR / database / "starts.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} doesn't exist: run choose_starts.py --database {database} first")
    with open(path, encoding="utf-8") as f:
        return [{**row, "actor_id": int(row["actor_id"])} for row in csv.DictReader(f)]


# ---------------------------------------------------------------------
# def conditions(...) — THE CONDITIONS OF THE MEASUREMENT
#
# A time like "0.8 s" means little on its own. It depends on the software
# versions, on how much memory each database was ALLOWED to use, on how
# big the data was, on the computer. This function collects all of that
# into one dict, which main() saves as conditions.json next to the
# results. Months later, the numbers can still be read in context ("this
# was measured with PostgreSQL's default 128 MB of shared_buffers").
#
# Note: the settings are RECORDED, not changed. Both databases run with
# their installation defaults; the point is to know what they were.
# ---------------------------------------------------------------------
def conditions(conn, driver, database: str, args: argparse.Namespace) -> dict:
    # -----------------------------------------------------------------
    # PostgreSQL settings, read with the SQL command `SHOW <name>`:
    #   shared_buffers        PostgreSQL's own memory for data pages
    #                         (default 128MB — small; the operating
    #                         system's file cache helps on top of it)
    #   work_mem              memory per sort / hash step before spilling
    #                         to temporary files on disk (default 4MB)
    #   effective_cache_size  what the planner ASSUMES is cached in total
    #                         (default 4GB); it only influences plan choices
    #   max_parallel_workers_per_gather
    #                         how many extra processes one query may use
    #                         (default 2)
    #   jit                   compiling parts of big queries to machine
    #                         code (default on)
    #
    # f"SHOW {name}" builds the SQL text with an f-string. That's safe
    # HERE only because the names come from our own fixed tuple above,
    # never from a user (see docs_english/traversal.py on sql.Literal).
    #
    # {name: ... for name in settings} is a DICT COMPREHENSION: like a list
    # comprehension, but it builds a dict, one key: value per item.
    # -----------------------------------------------------------------
    settings = ("shared_buffers", "work_mem", "effective_cache_size", "max_parallel_workers_per_gather", "jit")
    postgres = {name: conn.execute(f"SHOW {name}").fetchone()[0] for name in settings}
    # The server version, the size of the whole database on disk in bytes
    # (pg_database_size of the database we're connected to), and how many
    # rows each of the three tables has.
    postgres["version"] = conn.execute("SHOW server_version").fetchone()[0]
    postgres["database_size_bytes"] = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    postgres["rows"] = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("actor", "repo", "actor_repo")}

    # -----------------------------------------------------------------
    # Neo4j memory settings, read with the Cypher command SHOW SETTINGS:
    #   server.memory.heap.initial_size / max_size
    #                         the Java "heap": memory for running queries
    #   server.memory.pagecache.size
    #                         Neo4j's memory for data pages (the equivalent
    #                         of PostgreSQL's shared_buffers)
    #   dbms.memory.transaction.total.max
    #                         the cap on memory used by all queries at once
    # Server settings live in the special "system" database, hence
    # database_="system". `.records` is the list of result rows (the first
    # of the three things execute_query returns, see check_connections.py).
    #
    # The query text is split over several "..." pieces: Python glues
    # strings that are written next to each other into one.
    # -----------------------------------------------------------------
    records = driver.execute_query(
        "SHOW SETTINGS YIELD name, value WHERE name IN ['server.memory.heap.initial_size', "
        "'server.memory.heap.max_size', 'server.memory.pagecache.size', 'dbms.memory.transaction.total.max'] "
        "RETURN name, value", database_="system").records
    neo4j = {r["name"]: r["value"] for r in records}
    # The version, as in check_connections.py; `AS v` names the column.
    # .records[0] is the first (only) row.
    version = driver.execute_query("CALL dbms.components() YIELD versions, edition RETURN versions[0] AS v, edition",
                                   database_="system").records[0]
    neo4j["version"] = f"{version['v']} {version['edition']}"
    # -----------------------------------------------------------------
    # count = lambda q: ...
    #
    # A LAMBDA is a tiny function without a name, written in one line:
    #     lambda q: <expression>
    # is the same as
    #     def count(q):
    #         return <expression>
    # Here it saves repeating the long execute_query(...) call three times.
    # records[0][0] is the first column of the first row: the number.
    #
    # The three counts are the graph's equivalent of the three tables, so
    # conditions.json can show that both sides hold the same data.
    # -----------------------------------------------------------------
    count = lambda q: driver.execute_query(q, database_=database).records[0][0]
    neo4j["rows"] = {"actors": count("MATCH (a:Actor) RETURN count(a)"),
                     "repos": count("MATCH (r:Repo) RETURN count(r)"),
                     "connections": count("MATCH ()-[c:INTERACTED_WITH]->() RETURN count(c)")}

    # -----------------------------------------------------------------
    # The whole picture, as one nested dict (dicts inside a dict), which
    # json.dumps() can turn into a file as is.
    #   started      datetime.now().isoformat(timespec="seconds") gives the
    #                date and time as text, e.g. "2026-11-18T14:05:31"
    #   options      what the measurement was asked to do
    #   machine      processor name, number of LOGICAL processors (cores,
    #                counting hyper-threads), total memory in GB
    #                (bytes / 1024**3, `**` being "to the power of"; rounded
    #                to one decimal), operating system and Python version
    # -----------------------------------------------------------------
    return {
        "database": database,
        "started": datetime.now().isoformat(timespec="seconds"),
        "options": {"max_depth": args.max_depth, "repeats": args.repeats, "timeout_s": args.timeout},
        "machine": {"cpu": platform.processor(), "logical_cpus": psutil.cpu_count(),
                    "memory_gb": round(psutil.virtual_memory().total / 1024 ** 3, 1),
                    "os": platform.platform(), "python": platform.python_version()},
        "postgresql": postgres,
        "neo4j": neo4j,
    }


# ---------------------------------------------------------------------
# def run_once(system, ...) — one traversal on ONE side
#
# A small switch so the rest of the code can just say "run it on this
# side" without caring which side it is. Both functions return an
# Outcome (status, seconds, count, error): see docs_english/traversal.py.
# ---------------------------------------------------------------------
def run_once(system: str, conn, driver, database: str, start: int, depth: int, timeout: int):
    if system == "postgresql":
        return traversal.run_postgres_reach(conn, start, depth, timeout)
    return traversal.run_neo4j_reach(driver, database, start, depth, timeout)


# ---------------------------------------------------------------------
# def measure_actor(...) — EVERYTHING FOR ONE STARTING ACTOR
#
# For depth 1, 2, 3 ... up to --max-depth, three steps (the same three as
# in the docstring at the top). `runs` and `work` are the two CSV writers
# created in main(): this function writes its lines into them.
# ---------------------------------------------------------------------
def measure_actor(actor: dict, conn, driver, database: str, args, runs: csv.DictWriter, work: csv.DictWriter) -> None:
    # -----------------------------------------------------------------
    # stopped — SKIPPING DEEPER DEPTHS
    #
    # A set of the sides that already ran out of time (--timeout) for this
    # actor. Going one hop deeper can only reach MORE actors, so it can
    # only take longer: if depth 4 didn't finish in 60 s, depth 5 won't
    # either. Skipping it saves 60 s x (1 + repeats) of pointless waiting
    # per depth. The OTHER side carries on, as long as it keeps finishing.
    # -----------------------------------------------------------------
    stopped = set()   # sides that ran out of time at a smaller depth
    # range(1, args.max_depth + 1): 1, 2, ..., max_depth (the end of a
    # range is NOT included, hence + 1).
    for depth in range(1, args.max_depth + 1):
        # The sides still being measured. If both have stopped, there's
        # nothing left to do for this actor: `break` leaves the loop.
        active = [s for s in SYSTEMS if s not in stopped]
        if not active:
            break
        # end=" " — print without going to a new line, so the rest of this
        # depth's report appears on the same line later.
        # flush=True — show it NOW. Python normally holds printed text in a
        # buffer for a while; without flush, you'd stare at an empty line
        # during a long run without knowing which depth is being measured.
        print(f"  depth {depth}:", end=" ", flush=True)

        # -------------------------------------------------------------
        # STEP 1 — RUN 0, THE "FIRST RUN": NOT A RESULT
        #
        # The very first time a database sees a query of a new shape, it
        # does extra one-off work before running it: it parses the text and
        # prepares (compiles) a query PLAN. Neo4j in particular takes a few
        # seconds (about 5 s) to plan the first variable-length query of a
        # new depth; afterwards the plan is kept in its cache and reused.
        # The first run also pulls the data into memory. Counting that time
        # would measure "the first time" rather than the traversal itself.
        #
        # So run 0 is written to runs.csv (with run = 0, and no machine
        # load: (None, None)) for the record, but analyze.py ignores it
        # when computing times.
        #
        # It IS used for something important: the COUNT CHECK. Both sides
        # answer "how many actors are reachable"; if the two numbers
        # differ, one of the two queries (or the loaded data) is wrong, and
        # comparing their speed would be meaningless.
        #
        # first = {s: run_once(...) for s in active}
        #   A dict comprehension: {"postgresql": Outcome, "neo4j": Outcome}.
        # -------------------------------------------------------------
        # 1. First run (not a result) and the count check.
        first = {s: run_once(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in active}
        for system, outcome in first.items():
            runs.writerow(row(actor, depth, system, 0, outcome, (None, None)))
        # The counts of the sides that finished ("ok"). Only when BOTH
        # finished (len(counts) == 2) can they be compared. If they differ,
        # print a loud message and `return`: stop measuring this actor
        # altogether (main() goes on with the next actor).
        counts = {s: o.count for s, o in first.items() if o.status == "ok"}
        if len(counts) == 2 and counts["postgresql"] != counts["neo4j"]:
            print(f"COUNTS DIFFER (PostgreSQL {counts['postgresql']}, Neo4j {counts['neo4j']}); stopping this actor")
            return
        # A side whose first run didn't finish (timeout or error) is added
        # to `stopped`: no timed runs at this depth, and no deeper depths.
        for system, outcome in first.items():
            if outcome.status != "ok":
                stopped.add(system)
        timed = [s for s in active if s not in stopped]

        # -------------------------------------------------------------
        # STEP 2 — THE TIMED REPETITIONS
        #
        # Why repeat at all? One single time is not reliable: the same
        # query can take 0.30 s, then 0.45 s, then 0.31 s, depending on
        # what else the computer is doing. With several runs, analyze.py
        # can take the MEDIAN and see how much they spread.
        #
        # Repetition 1: PostgreSQL then Neo4j; repetition 2: Neo4j then
        # PostgreSQL; ... (run_order above). `if system in timed` skips a
        # side that stopped at step 1.
        #
        # machine_load() is measured just BEFORE the run (it can't be
        # during it: cpu_percent() waits its 0.2 s before returning), and
        # written on the same line of runs.csv. The 0.2 s is not part of
        # the run's time: the clock starts inside run_once().
        # -------------------------------------------------------------
        # 2. Timed repetitions, alternating which side goes first.
        for repeat in range(1, args.repeats + 1):
            for system in run_order(repeat):
                if system in timed:
                    load = machine_load()
                    outcome = run_once(system, conn, driver, database, actor["actor_id"], depth, args.timeout)
                    runs.writerow(row(actor, depth, system, repeat, outcome, load))

        # -------------------------------------------------------------
        # STEP 3 — THE WORK FIGURES
        #
        # One extra run per side, this time asking the database to report
        # what it did: EXPLAIN (ANALYZE, BUFFERS) in PostgreSQL, PROFILE in
        # Neo4j (explained in docs_english/traversal.py). It's separate from
        # the timed runs because collecting those figures itself costs time.
        #
        # These figures explain the times: e.g. "Neo4j did 2 million
        # db_hits" or "PostgreSQL read 9,000 blocks from disk".
        #
        # try / except: if collecting the figures fails, it's not worth
        # losing the whole measurement. figures = {} writes a line with
        # the columns left empty, and a short note is printed.
        # str(error)[:80] — the first 80 characters of the message (a
        # SLICE of the text), so the screen doesn't fill with it.
        #
        # {"actor_id": ..., **figures} — `**` copies the figures' keys into
        # the row (same idea as in read_starts()). DictWriter leaves empty
        # any column of WORK_FIELDS the dict doesn't have: PostgreSQL has
        # no db_hits, Neo4j has no blocks_from_disk.
        # -------------------------------------------------------------
        # 3. The work done inside each database (one extra run each).
        for system in timed:
            try:
                if system == "postgresql":
                    figures = traversal.postgres_work(conn, actor["actor_id"], depth, args.timeout)
                else:
                    figures = traversal.neo4j_work(driver, database, actor["actor_id"], depth, args.timeout)
            except Exception as error:
                figures = {}
                print(f"(no work figures for {system}: {str(error)[:80]})", end=" ")
            work.writerow({"actor_id": actor["actor_id"], "group": actor["group"], "depth": depth,
                           "system": system, **figures})

        # -------------------------------------------------------------
        # Finish this depth's line on screen.
        #
        # counts.get("postgresql", counts.get("neo4j"))
        #   dict.get(key, default): PostgreSQL's count if it finished,
        #   otherwise Neo4j's (or None if neither finished).
        #
        # status: the sides whose first run was NOT "ok", e.g.
        # "neo4j timeout". ", ".join(...) joins the pieces with commas.
        # The pieces are produced by a GENERATOR EXPRESSION — a list
        # comprehension without the [ ], fed straight into join().
        #
        # (f"..." if status else "") adds the part in brackets only when
        # there is something to say.
        # -------------------------------------------------------------
        shown = counts.get("postgresql", counts.get("neo4j"))
        status = ", ".join(f"{s} {first[s].status}" for s in active if first[s].status != "ok")
        print(f"{shown} actors reached" + (f" ({status})" if status else ""))


# ---------------------------------------------------------------------
# def row(...) — one line of runs.csv, as a dict
#
# The keys are exactly RUN_FIELDS. round(outcome.seconds, 6) keeps
# microseconds (6 decimals): more digits than that are just noise.
# load is the (cpu, memory) tuple from machine_load(), or (None, None)
# for run 0; load[0] and load[1] pick its two values. None is written
# as an empty cell in the CSV.
# ---------------------------------------------------------------------
def row(actor: dict, depth: int, system: str, run: int, outcome, load) -> dict:
    return {"actor_id": actor["actor_id"], "group": actor["group"], "depth": depth, "system": system, "run": run,
            "status": outcome.status, "seconds": round(outcome.seconds, 6), "count": outcome.count,
            "machine_cpu_percent": load[0], "machine_memory_percent": load[1], "error": outcome.error}


def main() -> None:
    # -----------------------------------------------------------------
    # The options. argparse turns "--max-depth" into args.max_depth (the
    # dash becomes an underscore). required=True: the script refuses to
    # run without --database. type=int converts the text to a number.
    #
    # The defaults (depth 6, 5 repeats, 60 s) are a compromise: 5 timed
    # runs are enough for a meaningful median; 60 s stops hopeless deep
    # runs without cutting off ones that are merely slow.
    #
    # parser.error("...") prints the usage and the message, and stops the
    # script with an error — the standard way for argparse to reject a
    # value it can't check on its own (here: numbers below 1).
    # -----------------------------------------------------------------
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", required=True, help="The database to measure (same name on both sides)")
    parser.add_argument("--max-depth", type=int, default=6, help="Deepest traversal, in hops (default: 6)")
    parser.add_argument("--repeats", type=int, default=5, help="Timed runs per depth and side (default: 5)")
    parser.add_argument("--timeout", type=int, default=60, help="Seconds before a run is stopped (default: 60)")
    args = parser.parse_args()
    if args.max_depth < 1 or args.repeats < 1 or args.timeout < 1:
        parser.error("--max-depth, --repeats and --timeout must be at least 1")

    # -----------------------------------------------------------------
    # ONE OUTPUT FOLDER PER DATE AND TIME
    #
    # datetime.now().strftime("%Y-%m-%d_%H-%M-%S") formats the current
    # time as text: "%Y" year, "%m" month, "%d" day, "%H" hour, "%M"
    # minute, "%S" second -> e.g. "2026-11-18_14-05-31". (No ":" because
    # Windows doesn't allow it in file names.)
    #
    # Every measurement gets its own folder, so measuring the same
    # database again never overwrites an earlier result. Because the name
    # starts with the year, sorting the folder names alphabetically also
    # sorts them by time — analyze.py relies on that to find the latest.
    #
    # mkdir(parents=True) WITHOUT exist_ok=True: if the folder somehow
    # already existed, it's an error — on purpose, never mix two runs.
    # -----------------------------------------------------------------
    starts = read_starts(args.database)
    out_dir = choose_starts.RESULTS_DIR / args.database / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir.mkdir(parents=True)

    # -----------------------------------------------------------------
    # Two connections in ONE `with` statement, separated by a comma: both
    # are closed at the end, whatever happens. One PostgreSQL connection
    # and one Neo4j driver are reused for every run — opening a new
    # connection per run would add its own cost to every time measured.
    #
    # json.dumps(info, indent=2) turns the dict into JSON text, indented
    # with 2 spaces so it's easy to read; Path.write_text() writes that
    # text to the file in one go (open + write + close).
    # -----------------------------------------------------------------
    with traversal.connect_postgres(args.database) as conn, traversal.connect_neo4j() as driver:
        info = conditions(conn, driver, args.database, args)
        (out_dir / "conditions.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        # f'...' with SINGLE quotes, so the text can contain "double"
        # quotes around the database name. Two f-strings next to each
        # other are glued into one (see conditions()). "\n" is a new line.
        print(f'Measuring "{args.database}": {len(starts)} starting actors, depths 1-{args.max_depth}, '
              f"{args.repeats} timed runs each, time limit {args.timeout} s")
        print(f"Results: {out_dir}\n")

        # -------------------------------------------------------------
        # csv.DictWriter — writing rows that are DICTS (a reminder; first seen
        # in docs_english/choose_starts.py)
        #
        # csv.writer (docs_english/extract_csv.py) writes lists, where the
        # order of the values must match the header by hand. DictWriter
        # takes fieldnames= (the header) and then rows as dicts: each value
        # goes to the column with the SAME NAME, whatever order the dict is
        # in, and a missing key gives an empty cell. It's the writing twin
        # of csv.DictReader.
        #   writeheader()   writes the header line (the fieldnames)
        #   writerow(dict)  writes one line
        #
        # The `with open(...) as a, \` line ends with a backslash: it
        # CONTINUES the statement on the next line (the line would be too
        # long otherwise). Both files are closed at the end of the block.
        # -------------------------------------------------------------
        with open(out_dir / "runs.csv", "w", newline="", encoding="utf-8") as runs_file, \
             open(out_dir / "work.csv", "w", newline="", encoding="utf-8") as work_file:
            runs = csv.DictWriter(runs_file, fieldnames=RUN_FIELDS)
            work = csv.DictWriter(work_file, fieldnames=WORK_FIELDS)
            runs.writeheader()
            work.writeheader()
            # ---------------------------------------------------------
            # enumerate(starts, start=1) numbers the actors from 1 (not 0)
            # for the "[3/20]" progress display.
            #
            # flush() after each actor — a whole measurement can take
            # HOURS. Python keeps written lines in memory for a while
            # before they really reach the file. flush() pushes them to the
            # file now, so if something goes wrong at actor 15 (a crash,
            # Ctrl+C, the laptop going to sleep), the results of actors
            # 1-14 are safely on disk and can be analysed.
            # ---------------------------------------------------------
            for number, actor in enumerate(starts, start=1):
                print(f"[{number}/{len(starts)}] {actor['group']} #{actor['rank']}: {actor['login']} "
                      f"(reaches {actor['reached']} in one hop)")
                measure_actor(actor, conn, driver, args.database, args, runs, work)
                runs_file.flush()
                work_file.flush()

    print(f"\nDone. Results in {out_dir}")


# ---------------------------------------------------------------------
# The __name__ guard (see docs_english/download_gharchive.py), with one
# addition: main() runs inside try / except FileNotFoundError. The only
# expected "file not found" is a missing starts.csv (read_starts()); its
# message already says what to do, so it's printed alone, without
# Python's long traceback, and sys.exit(1) reports the failure — which
# makes research.sh stop there (set -e, see docs_english/research.sh).
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(error)
        sys.exit(1)
