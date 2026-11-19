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
#                             try/except and raising errors
#   - extract_csv.py          the csv module, open(..., newline=""),
#                             mkdir(parents=True, exist_ok=True), sorted(...), sets
#   - load_neo4j.py           csv.DictReader, driver.execute_query(..., database_=...)
#   - check_connections.py    psycopg / neo4j connections, `with`, sys.exit
#   - pipeline.py             RawDescriptionHelpFormatter
#   - build_hours.py          datetime, timedelta, strptime, and how the
#                             databases are NAMED (gharchive-<date>-<hour>[-<n>h])
#   - summarize_data.py       dict comprehensions, f-string column widths
#   - test_build_hours.py     lambda, iter() and next()
#   - traversal.py            the traversal queries (SQL, Cypher "paths" and
#                             "levels"), the Outcome object (status / seconds /
#                             count / error), the timeouts, and the WORK
#                             figures (data processed, memory) from EXPLAIN
#                             (ANALYZE, BUFFERS) and PROFILE
#   - choose_starts.py        how the 20 starting actors are chosen
#                             (choose_in_both), statistics.median
#
# What's NEW here — this is the script that actually produces the research's
# numbers, so most of the explanations are about MEASURING FAIRLY and about
# the results file:
#   - ONE CSV file per measurement, results/<database>_<date>_<time>.csv.
#     One line = one question answered by both databases (csv.DictWriter);
#   - its three-part layout: the test's columns, then a PostgreSQL block
#     and a Neo4j block with IDENTICAL columns, then the comparison;
#   - the four things compared: data processed, time, space (memory and
#     disk), and computing power (CPU seconds of the database SERVER
#     processes, measured with psutil);
#   - the `re` module: reading the data's time window from the database name;
#   - the "first run": not a result, but used to check that ALL sides give
#     the SAME count;
#   - timed repetitions that ROTATE which side goes first;
#   - the median, "reliable", and who was "faster" (and how many times);
#   - stopping deeper depths for a side once it runs out of time;
#   - reusing the starting actors of the latest CSV of the same database
#     (--new-starts to choose again).
#
# How it's meant to be run — normally through research.sh, which checks
# the connections, asks which database, then runs this script:
#     ./research.sh --database gharchive-2026-10-08-9-24h
# or alone, through run.sh (which loads .venv and the passwords):
#     ./run.sh scripts/measure.py --database gharchive-2026-10-08-9-24h
########################################################################

"""Measure the traversal in PostgreSQL and Neo4j, and write the results to ONE CSV file.

Every measurement (every analysis) writes its own file,
results/<database>_<date>_<time>.csv. One line of it = one question answered
by both databases: "from this starting actor, at this depth, in this volume of
data, how many actors are reached?". First the test, then PostgreSQL's figures
and Neo4j's figures side by side, with the same columns. Every column is
explained in the README ("What is measured, and why").

For the database given, it:

    1. chooses the 20 starting actors (choose_starts.py), or reuses the ones
       in the latest CSV of that database, so a repeated measurement
       starts from the same actors;
    2. for every actor and every depth from 1 to --max-depth:
       a. runs the traversal once on each side ("first run": it includes
          preparing the query) and checks that ALL sides give the same count;
       b. runs it --repeats more times, changing which side goes first each
          time, recording the time and the CPU used by each database server;
       c. runs it once more with EXPLAIN (ANALYZE, BUFFERS) / PROFILE, for the
          data read and the memory used inside each database;
    3. writes one line per actor, depth and Cypher version, and prints a summary.

If a side runs out of time at some depth, the deeper depths are skipped for that
side and actor (they can only be slower); their lines say so.

Usage:
    ./run.sh scripts/measure.py --database gharchive-2026-10-08-9-24h
    ./run.sh scripts/measure.py --database ... --max-depth 4 --repeats 5 --timeout 60 --cypher both
"""

# ---------------------------------------------------------------------
# Standard-library imports. Already met: argparse, csv, statistics, sys,
# datetime, timedelta, Path.
# New one:
#   re  — REGULAR EXPRESSIONS: patterns that describe the shape of a text
#         (see NAME and data_window() below).
# ---------------------------------------------------------------------
import argparse
import csv
import re
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------
# import psutil
#
# An EXTERNAL package (installed from requirements.txt, like psycopg and
# neo4j): "process and system utilities". It can list the programs
# (PROCESSES) running on the computer, say how much processor time each
# one has used, and how busy the whole computer is.
#
# Why does a benchmark need that? Two reasons:
#   - COMPUTING POWER: how much CPU each database SERVER spent on a query
#     (see server_processes() and cpu_seconds() below);
#   - FAIRNESS: the laptop is also being used for other things while the
#     measurement runs (a browser, an antivirus scan, Windows updates...).
#     If a run was slow because the computer was busy, we want to SEE
#     that, instead of blaming the database.
# ---------------------------------------------------------------------
import psutil

# ---------------------------------------------------------------------
# import choose_starts / import traversal
#
# The project's OWN scripts, imported like packages (this works because
# they're all in the same scripts/ folder). This script reuses:
#   choose_starts.choose_in_both                       the starting actors
#   traversal.connect_postgres / connect_neo4j
#   traversal.run_postgres_reach / run_neo4j_reach     one timed traversal
#   traversal.postgres_work / neo4j_work               the work figures
#   traversal.sql_joins / cypher_hops / CYPHER_VERSIONS
# All of them are explained in docs_english/traversal.py and
# docs_english/choose_starts.py.
# ---------------------------------------------------------------------
import choose_starts
import traversal

# ---------------------------------------------------------------------
# RESULTS_DIR — the folder of the results files: <project>/results
#
# (Same Path recipe as PROJECT_DIR in load_postgres.py.) Each measurement
# writes ONE CSV file there, named after the database and the moment it
# started (see results_file()), e.g.
#     results/gharchive-2026-10-08-9-24h_2026-11-19_14-05-31.csv
# One file holds everything about one measurement, and a new measurement
# never touches an earlier one. (Earlier versions wrote several files per
# measurement — runs, work, per-actor, summary — which turned out too
# hard to read.)
# ---------------------------------------------------------------------
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# ---------------------------------------------------------------------
# THE COLUMNS OF A RESULTS CSV — THREE PARTS
#
# The user asked for this layout: the TEST's information first, then a
# PostgreSQL table and a Neo4j table side by side with the SAME columns,
# so each database can be read on its own AND compared column by column
# (pg_time_s next to... the same place in the Neo4j block: neo4j_time_s).
#
# 1. TEST_COLUMNS — which data, when, and which question:
#   measured_at          when the measurement started (the same for all
#                        its lines, so files can be combined later)
#   database             the database measured
#   data_from_utc, data_to_utc, volume_hours
#                        the data's time window, read from the database
#                        name (see data_window())
#   graph_actors, graph_repos, graph_connections
#                        the size of the graph (identical on both sides:
#                        checked in graph_facts())
#   start_group, start_rank, start_actor_id, start_login, start_reach_1_hop
#                        the starting actor (from choose_starts.py)
#   depth                how many hops
#   cypher_version       which Cypher version this line compares with the
#                        SQL: "paths" or "levels" (docs_english/traversal.py)
#   actors_reached       the answer, if all sides agree
#   answers_match        yes / no / unknown (nobody finished)
#   runs, timeout_s      how many timed runs, and the time limit
#
# 2. SIDE_COLUMNS — the same list, used TWICE: once with the prefix
#    "pg_", once with "neo4j_". The four things compared are here:
#   joins_or_hops        how much walking one depth is: JOINs in SQL,
#                        relationships followed in Cypher (2 per depth,
#                        see traversal.sql_joins / cypher_hops)
#   status               finished / timeout / error / skipped (...)
#   time_s               TIME: the MEDIAN of the timed runs, in seconds
#   first_run_s          the first run (with the query being prepared)
#   data_processed_mb    DATA PROCESSED: MB of 8 KB pages touched (a page
#                        used twice counts twice)
#   data_from_disk_mb    the part read from disk
#   memory_mb            SPACE: the memory the query used
#   temp_disk_mb         SPACE: temporary disk files (PostgreSQL only; it
#                        stays EMPTY for Neo4j, which has no equivalent)
#   database_mb          SPACE: the size of the whole database on disk
#   cpu_s                COMPUTING POWER: CPU seconds the database server
#                        used (median of the timed runs)
#   cores_used           cpu_s / time_s: how many processor cores were
#                        busy on average (2.0 = two cores the whole time)
#   reliable             yes / no, for THIS side (see side_summary())
#
# 3. COMPARISON_COLUMNS — at the end:
#   faster, times_faster who was faster, and how many times (compare())
#
# COLUMNS — the full list, in order, glued with `+` (list + list = one
# longer list). [f"pg_{c}" for c in SIDE_COLUMNS] is a list comprehension
# that puts the prefix in front of every name: "pg_status", "pg_time_s"...
# The brackets ( ... ) around the expression let it continue on the next
# line.
#
# Keeping the columns as constants means the header and the rows can
# never disagree (see csv.DictWriter in main()), every file has the same
# columns, and
# tests/test_research.py checks the three-part shape.
# ---------------------------------------------------------------------
# The columns of every results CSV, in order: first the test (which data, when, which question),
# then two blocks with THE SAME columns, one for PostgreSQL ("pg_...") and one for Neo4j
# ("neo4j_..."), and at the end the comparison. Their meaning is explained in the README.
TEST_COLUMNS = [
    "measured_at", "database", "data_from_utc", "data_to_utc", "volume_hours",
    "graph_actors", "graph_repos", "graph_connections",
    "start_group", "start_rank", "start_actor_id", "start_login", "start_reach_1_hop",
    "depth", "cypher_version", "actors_reached", "answers_match", "runs", "timeout_s",
]
SIDE_COLUMNS = [
    "joins_or_hops", "status", "time_s", "first_run_s", "data_processed_mb", "data_from_disk_mb",
    "memory_mb", "temp_disk_mb", "database_mb", "cpu_s", "cores_used", "reliable",
]
COMPARISON_COLUMNS = ["faster", "times_faster"]
COLUMNS = (TEST_COLUMNS + [f"pg_{c}" for c in SIDE_COLUMNS] + [f"neo4j_{c}" for c in SIDE_COLUMNS]
           + COMPARISON_COLUMNS)

# ---------------------------------------------------------------------
# The two "not reliable" thresholds (used in side_summary()):
#   BUSY_CPU      the whole computer above 80 % CPU during a run: the
#                 database had to share the processor.
#   NOISY_SPREAD  the slowest timed run more than 3 times the fastest:
#                 something disturbed the runs.
#
# NAME — a REGULAR EXPRESSION (the `re` module)
#
# A regular expression is a small pattern language that describes the
# SHAPE of a text. re.compile(...) prepares the pattern once, so it can be
# used many times. r"..." is a RAW string: the backslashes stay as typed
# (otherwise Python would try to read \d itself).
#
#   ^ ... $                 the start and the end of the text: the WHOLE
#                           name must match, not just a piece of it
#   gharchive-              these exact characters
#   (\d{4}-\d{2}-\d{2})     \d = one digit; {4} = exactly 4 of them. So
#                           "2026-10-08". The round brackets make a GROUP:
#                           the part matched is kept, as group 1.
#   -(\d{1,2})              a dash, then 1 or 2 digits: the hour (group 2)
#   (?:-(\d+)h)?            (?: ... ) is a group that is NOT kept, only
#                           used to bundle "-<n>h" together; the ? after it
#                           makes the whole bundle OPTIONAL. Inside, \d+ =
#                           one digit or more, kept as group 3.
# So both "gharchive-2026-10-08-9-24h" and "gharchive-2026-10-08-23"
# match (the second without group 3). The names are those made by
# build_hours.py (database_name(), see docs_english/build_hours.py).
# (The same idea as bash's [[ =~ ]] in docs_english/research.sh.)
# ---------------------------------------------------------------------
BUSY_CPU = 80.0       # computer CPU above this (percent) during a run: not reliable
NOISY_SPREAD = 3.0    # slowest run more than 3 times the fastest: not reliable
NAME = re.compile(r"^gharchive-(\d{4}-\d{2}-\d{2})-(\d{1,2})(?:-(\d+)h)?$")


# ---------- which data ----------

# ---------------------------------------------------------------------
# def data_window(database) -> tuple[str, str, int | None]:
#
# Turns a database name into its data's time window, e.g.
#   "gharchive-2026-10-08-9-24h" -> ("2026-10-08 09:00", "2026-10-09 09:00", 24)
#
# NAME.match(database) tries the pattern on the text: it gives a MATCH
# object if the text has that shape, or None if not. A name that doesn't
# match (made by hand, say) isn't an error: the three columns stay empty
# ("", "", None).
#
# match.group(1), (2), (3) — the text each kept group matched. An
# OPTIONAL group that matched nothing gives None, so
#   int(match.group(3) or 1)    no "-<n>h" part -> 1 hour.
# The values are TEXT: int(...) turns them into numbers.
#
# datetime.strptime(date, "%Y-%m-%d") reads the date (build_hours.py), at
# midnight; + timedelta(hours=hour) moves it to the starting hour; adding
# `hours` more gives the end. strftime("%Y-%m-%d %H:%M") writes them back
# as text. GH Archive's hours are in UTC, hence the _utc column names.
# ---------------------------------------------------------------------
def data_window(database: str) -> tuple[str, str, int | None]:
    # build_hours.py names each database after its data: gharchive-<date>-<hour>[-<n>h].
    match = NAME.match(database)
    if not match:
        return "", "", None
    date, hour, hours = match.group(1), int(match.group(2)), int(match.group(3) or 1)
    begin = datetime.strptime(date, "%Y-%m-%d") + timedelta(hours=hour)
    end = begin + timedelta(hours=hours)
    return begin.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M"), hours


# ---------------------------------------------------------------------
# def folder_size_mb(path) -> float | None:  — the size of a folder on disk
#
#   path.is_dir()          is there such a folder? If not: None (unknown).
#   path.rglob("*")        every file and folder INSIDE it, at any depth
#                          (the "r" is for recursive).
#   f.is_file()            keep the files (folders have no size of their own).
#   f.stat().st_size       a file's size, in bytes.
#   sum(...) / 1024 ** 2   all added up, in MB.
# Used for Neo4j's database size (graph_facts()).
# ---------------------------------------------------------------------
def folder_size_mb(path: Path) -> float | None:
    if not path.is_dir():
        return None
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024 ** 2


# ---------------------------------------------------------------------
# def graph_facts(conn, driver, database) -> dict:  — THE DATA, AND A CHECK
#
# Collects the figures that are the same for every line of this
# measurement: the size of the graph, and of each database on disk.
#
# count = lambda q: ... — a one-line function (lambda: test_build_hours.py)
# that runs a Cypher count and returns the number (records[0][0]: the
# first column of the first row).
#
# The PostgreSQL side: the three tables counted, and
# pg_database_size(current_database()) — the size in bytes of the whole
# database on disk (tables AND indexes), / 1024 ** 2 -> MB.
#
# THE SAME DATA ON BOTH SIDES: the Neo4j counts (actors, repos,
# connections) are put in a tuple and compared with PostgreSQL's. If they
# differ, the two databases don't hold the same graph, and comparing their
# speed would be meaningless: raise RuntimeError, caught at the bottom of
# the file (nothing is measured).
#
# NEO4J'S SIZE ON DISK: Neo4j has no pg_database_size. Its databases are
# folders under the server's data directory, so the script asks the
# server where that is (SHOW SETTINGS ... 'server.directories.data', in
# the special "system" database) and measures the folder
# <data>/databases/<database> with folder_size_mb(). `if records else
# None`: if the setting can't be read, the size stays unknown. (This
# works because Neo4j Desktop runs on the same computer.)
#
# The keys "pg_database_mb" and "neo4j_database_mb" are exactly the
# column names of the two blocks, so they go straight into every line.
# ---------------------------------------------------------------------
def graph_facts(conn, driver, database: str) -> dict:
    count = lambda q: driver.execute_query(q, database_=database).records[0][0]
    facts = {
        "graph_actors": conn.execute("SELECT count(*) FROM actor").fetchone()[0],
        "graph_repos": conn.execute("SELECT count(*) FROM repo").fetchone()[0],
        "graph_connections": conn.execute("SELECT count(*) FROM actor_repo").fetchone()[0],
        "pg_database_mb": conn.execute("SELECT pg_database_size(current_database())").fetchone()[0] / 1024 ** 2,
    }
    neo4j = (count("MATCH (a:Actor) RETURN count(a)"), count("MATCH (r:Repo) RETURN count(r)"),
             count("MATCH ()-[c:INTERACTED_WITH]->() RETURN count(c)"))
    if neo4j != (facts["graph_actors"], facts["graph_repos"], facts["graph_connections"]):
        raise RuntimeError(f"The two databases don't hold the same data: PostgreSQL "
                           f"{facts['graph_actors']}/{facts['graph_repos']}/{facts['graph_connections']}, "
                           f"Neo4j {neo4j[0]}/{neo4j[1]}/{neo4j[2]} (actors/repos/connections)")
    # Neo4j's size on disk: the database's folder under the server's data directory.
    records = driver.execute_query("SHOW SETTINGS YIELD name, value WHERE name = 'server.directories.data' "
                                   "RETURN value", database_="system").records
    facts["neo4j_database_mb"] = folder_size_mb(Path(records[0]["value"]) / "databases" / database) if records else None
    return facts


# ---------- the CPU used by each database server ----------

# ---------------------------------------------------------------------
# def server_processes(system) -> list[psutil.Process]:  — FIND THE SERVERS
#
# COMPUTING POWER is measured on the database SERVER, not on Python: the
# servers are separate programs (PROCESSES) running on the same computer.
#   PostgreSQL   runs as SEVERAL processes called postgres (one main one,
#                one per connection, and helpers). All of them count.
#   Neo4j        runs as ONE Java program (java.exe). But other Java
#                programs may be running too, so the process is kept only
#                if its COMMAND LINE (the program and its arguments,
#                process.cmdline()) mentions neo4j.
#
# psutil.process_iter(["name"]) goes through every process on the
# computer, with its name already read (process.info["name"]).
# `(... or "").lower()`: a missing name becomes "", and lower() makes the
# comparison ignore capitals. name.startswith("postgres") is True for
# "postgres" and "postgres.exe".
#
# try / except (psutil.Error, OSError): pass — some processes belong to
# Windows or to another user, and asking about them is REFUSED; others
# end while we look. Those are simply skipped (`pass` = do nothing). A
# tuple of error classes catches any of them.
# ---------------------------------------------------------------------
def server_processes(system: str) -> list[psutil.Process]:
    # PostgreSQL runs as several postgres processes; Neo4j as one Java process.
    found = []
    for process in psutil.process_iter(["name"]):
        name = (process.info["name"] or "").lower()
        try:
            if system == "postgresql" and name.startswith("postgres"):
                found.append(process)
            elif system == "neo4j" and name.startswith("java") and "neo4j" in " ".join(process.cmdline()).lower():
                found.append(process)
        except (psutil.Error, OSError):
            pass
    return found


# ---------------------------------------------------------------------
# def cpu_seconds(processes) -> dict[int, float]:
#
# For each process, the CPU time it has used SINCE IT STARTED:
#   cpu.user     seconds the processor spent running its own code
#   cpu.system   seconds spent by Windows working for it (reading files...)
# The sum is stored under the process's id (pid: "process id", a number
# that identifies a running program).
#
# One reading means nothing by itself; timed_run() reads it BEFORE and
# AFTER a query, and the difference is what the query cost. A process
# that has ended (or refuses) is skipped.
# ---------------------------------------------------------------------
def cpu_seconds(processes: list[psutil.Process]) -> dict[int, float]:
    times = {}
    for process in processes:
        try:
            cpu = process.cpu_times()
            times[process.pid] = cpu.user + cpu.system
        except (psutil.Error, OSError):
            pass
    return times


# ---------- running ----------

# ---------------------------------------------------------------------
# def sides(cypher) -> list[str]:  — WHAT IS MEASURED
#
# A "side" is one way of answering the question:
#   "postgresql"     the SQL
#   "neo4j-paths"    Cypher, "paths" version
#   "neo4j-levels"   Cypher, "levels" version
# --cypher both gives all three; --cypher levels gives PostgreSQL and
# that version only. (cypher,) is a tuple with one element (the comma
# makes it a tuple), so both branches give something to loop over.
# ---------------------------------------------------------------------
def sides(cypher: str) -> list[str]:
    # The "sides" measured: PostgreSQL and one or two Cypher versions.
    versions = traversal.CYPHER_VERSIONS if cypher == "both" else (cypher,)
    return ["postgresql"] + [f"neo4j-{v}" for v in versions]


# ---------------------------------------------------------------------
# def run_order(all_sides, repeat) -> list[str]:  — WHICH SIDE GOES FIRST
#
# Why change the order? Anything that changes during the measurement
# affects whoever happens to run at that moment: you open a browser tab,
# the antivirus wakes up, the laptop heats up and slows down, Windows
# writes to disk... If PostgreSQL ALWAYS ran first, every such
# disturbance would land on the same side, in the same position. Rotating
# spreads it out so it hits every side alike, and none gets a systematic
# advantage (for example, "the one that runs second always finds the
# data already in the operating system's memory").
#
# THE ROTATION, with three sides [A, B, C]:
#   repeat 1 -> shift 0 -> [A, B, C]
#   repeat 2 -> shift 1 -> [B, C, A]
#   repeat 3 -> shift 2 -> [C, A, B]
#   repeat 4 -> shift 0 -> [A, B, C] again
# `%` is the REMAINDER of a division: (repeat - 1) % 3 goes 0, 1, 2, 0...
# all_sides[shift:] + all_sides[:shift] — two SLICES glued: from position
# `shift` to the end, then the beginning up to `shift`.
# tests/test_research.py checks this function (docs_english/test_research.py).
# ---------------------------------------------------------------------
def run_order(all_sides: list[str], repeat: int) -> list[str]:
    # Repetition 1 starts with the first side, repetition 2 with the second, and so on, so
    # anything else happening on the computer affects every side alike.
    shift = (repeat - 1) % len(all_sides)
    return all_sides[shift:] + all_sides[:shift]


# ---------------------------------------------------------------------
# def run_once(side, ...) — one traversal on ONE side
#
# A small switch so the rest of the code can just say "run it on this
# side" without caring which side it is. Both functions return an
# Outcome (status, seconds, count, error): see docs_english/traversal.py.
#
# side.split("-", 1)[1] — split the text at the FIRST "-" only (the 1),
# and take the second piece: "neo4j-levels" -> ["neo4j", "levels"] ->
# "levels", the Cypher version.
# ---------------------------------------------------------------------
def run_once(side: str, conn, driver, database: str, start: int, depth: int, timeout: int):
    if side == "postgresql":
        return traversal.run_postgres_reach(conn, start, depth, timeout)
    return traversal.run_neo4j_reach(driver, database, start, depth, timeout, side.split("-", 1)[1])


# ---------------------------------------------------------------------
# def timed_run(...) -> dict:  — ONE TIMED RUN, WITH ITS CPU
#
# 1. psutil.cpu_percent(interval=0.2) — watches the processor for 0.2 s
#    and returns how much of it was in use, in percent, counting ALL
#    programs. Taken just BEFORE the run (it can't be during: it waits
#    its 0.2 s before returning). It says how busy the computer was.
#
# 2. procs = the server processes of this side ("neo4j-paths" and
#    "neo4j-levels" both use the Neo4j server). `A if condition else B`:
#    a one-line if/else that gives a value.
#
# 3. CPU seconds BEFORE, the run, CPU seconds AFTER. The run's own time
#    is measured inside run_once() (the Outcome), so the CPU readings
#    don't add to it.
#
# 4. used = the CPU the server spent on this run: for every process, after
#    minus before, added up. `if pid in before`: a process that appeared
#    in between has no "before" and is left out. `if procs else None`: if
#    no server process was found, the CPU is UNKNOWN (None — not 0, which
#    would be a real, wrong value).
#
# Note: this counts EVERYTHING the server did during the run, so the
# research assumes nothing else is using the databases at the time.
# ---------------------------------------------------------------------
def timed_run(side, processes, conn, driver, database, start, depth, timeout) -> dict:
    machine_cpu = psutil.cpu_percent(interval=0.2)
    procs = processes["postgresql" if side == "postgresql" else "neo4j"]
    before = cpu_seconds(procs)
    outcome = run_once(side, conn, driver, database, start, depth, timeout)
    after = cpu_seconds(procs)
    used = sum(after[pid] - before[pid] for pid in after if pid in before) if procs else None
    return {"outcome": outcome, "cpu_s": used, "machine_cpu": machine_cpu}


# ---------------------------------------------------------------------
# def work_figures(...) -> dict:  — THE WORK FIGURES OF ONE SIDE
#
# One extra run, this time asking the database to report what it did:
# EXPLAIN (ANALYZE, BUFFERS) in PostgreSQL, PROFILE in Neo4j (explained
# in docs_english/traversal.py). It returns a dict like
#   {"data_processed_mb": ..., "data_from_disk_mb": ..., "memory_mb": ...}
# (plus "temp_disk_mb" for PostgreSQL). It's separate from the timed runs
# because collecting those figures itself costs time.
#
# try / except: if collecting the figures fails, it's not worth losing
# the whole measurement: an empty dict leaves those columns empty, and a
# short note is printed. str(error)[:80] — the first 80 characters of the
# message (a SLICE of the text). end=" " keeps the screen line going.
# ---------------------------------------------------------------------
def work_figures(side, conn, driver, database, start, depth, timeout) -> dict:
    try:
        if side == "postgresql":
            return traversal.postgres_work(conn, start, depth, timeout)
        return traversal.neo4j_work(driver, database, start, depth, timeout, side.split("-", 1)[1])
    except Exception as error:
        print(f"(no work figures for {side}: {str(error)[:80]})", end=" ")
        return {}


# ---------------------------------------------------------------------
# def side_summary(first, runs, work, status) -> dict:  — ONE SIDE'S FIGURES
#
# Turns the runs of one side, for one actor and depth, into the values of
# its block of columns (time_s, cpu_s, ...).
#
# A side that did NOT finish (timeout, error, or skipped) has no times:
# only its status, and the first run's time if there was one (`if first
# else None`: a skipped side never ran).
#
# A side that finished:
#   time_s       statistics.median of the timed runs. Why the MEDIAN and
#                not the average? One disturbed run (the antivirus...) can
#                be 10 times slower; it would pull the average up, but
#                barely moves the median (the middle value).
#   first_run_s  the first run, kept apart: it includes preparing the
#                query plan, so it's NOT part of time_s.
#   cpu_s        the median of the CPU seconds (the runs where it's known).
#   cores_used   cpu_s / time_s. Example: 0.6 CPU seconds in a 0.3-second
#                run = 2.0 — on average two processor cores were busy
#                (a database can work on several cores at once). Not
#                computed if the CPU is unknown or the time is 0 (a
#                division by zero would crash).
#   **{k: round(v, 3) for k, v in work.items() if v is not None}
#                the work figures, rounded to 3 decimals; `**` copies them
#                into this dict (the same `**` as in choose_starts.py).
#                A None (e.g. Neo4j didn't report its memory) is left
#                out, so its column stays empty.
#   noisy        the slowest run more than NOISY_SPREAD (3) times the
#                fastest. (`if min(times) > 0`: avoids dividing by 0.)
#   busy         any(...) is True if at least ONE run had the computer
#                above BUSY_CPU (80 %).
#   reliable     "no" if noisy or busy, else "yes" — the column of THIS
#                side's block. A "no" doesn't mean the figure is wrong;
#                it means: be careful, measure again if it matters.
# round(..., 4): 4 decimals of a second = a tenth of a millisecond.
# tests/test_research.py checks this function.
# ---------------------------------------------------------------------
def side_summary(first, runs: list[dict], work: dict, status: str) -> dict:
    # The figures of one side, for one actor and depth.
    if status != "finished":
        return {"status": status, "first_run_s": round(first.seconds, 4) if first else None}
    times = [r["outcome"].seconds for r in runs]
    cpus = [r["cpu_s"] for r in runs if r["cpu_s"] is not None]
    time_s = statistics.median(times)
    cpu_s = statistics.median(cpus) if cpus else None
    noisy = max(times) / min(times) > NOISY_SPREAD if min(times) > 0 else False
    busy = any(r["machine_cpu"] > BUSY_CPU for r in runs)
    return {
        "status": "finished",
        "time_s": round(time_s, 4),
        "first_run_s": round(first.seconds, 4),
        "cpu_s": round(cpu_s, 4) if cpu_s is not None else None,
        "cores_used": round(cpu_s / time_s, 2) if cpu_s is not None and time_s > 0 else None,
        **{k: round(v, 3) for k, v in work.items() if v is not None},
        "noisy": noisy,
        "busy": busy,
        "reliable": "no" if noisy or busy else "yes",
    }


# ---------------------------------------------------------------------
# def compare(pg, neo, timeout) -> tuple[str, float | None]:  — WHO WAS FASTER
#
# Gives the two comparison columns, faster and times_faster:
#   both finished       the smaller time wins; times_faster = the slower
#                       time / the faster one (0.4 s vs 0.1 s -> 4.0).
#                       A tie goes to PostgreSQL (<=).
#   only one finished   the other one took AT LEAST the time limit (it was
#                       stopped), so timeout / the winner's time is a
#                       MINIMUM: "at least 30 times faster".
#   neither finished    "neither", and no number.
# Each `... if pg["time_s"] else None` avoids dividing by a time of 0.
# ---------------------------------------------------------------------
def compare(pg: dict, neo: dict, timeout: int) -> tuple[str, float | None]:
    # Who was faster, and how many times. If only one side finished, the other took at
    # least the time limit, so "times_faster" is a minimum.
    if pg["status"] == "finished" and neo["status"] == "finished":
        if pg["time_s"] <= neo["time_s"]:
            return "postgresql", round(neo["time_s"] / pg["time_s"], 2) if pg["time_s"] else None
        return "neo4j", round(pg["time_s"] / neo["time_s"], 2) if neo["time_s"] else None
    if pg["status"] == "finished":
        return "postgresql", round(timeout / pg["time_s"], 2) if pg["time_s"] else None
    if neo["status"] == "finished":
        return "neo4j", round(timeout / neo["time_s"], 2) if neo["time_s"] else None
    return "neither", None


# ---------------------------------------------------------------------
# def measure_actor(actor, context, args, writer) — EVERYTHING FOR ONE STARTING ACTOR
#
# For depth 1, 2, 3 ... up to --max-depth: steps a, b, c (the same as in
# the docstring at the top), then d, writing the lines. `context` is a
# dict built in main() (the connections, the server processes, the
# facts), so the function doesn't need a long list of arguments.
# `writer` is the csv.DictWriter of this measurement's CSV file.
#
# stopped — SKIPPING DEEPER DEPTHS
#   A dict {side: the status it gets at deeper depths}. Going one hop
#   deeper can only reach MORE actors, so it can only take longer: if
#   depth 4 didn't finish in 60 s, depth 5 won't either. Skipping it
#   saves 60 s x (1 + repeats) of pointless waiting per depth. The OTHER
#   sides carry on, as long as they keep finishing; the skipped side's
#   lines still get written, with status "skipped (...)".
# ---------------------------------------------------------------------
def measure_actor(actor: dict, context: dict, args, writer: csv.DictWriter) -> None:
    conn, driver, database = context["conn"], context["driver"], args.database
    all_sides = sides(args.cypher)
    stopped = {}   # side -> the status it gets at deeper depths
    # range(1, args.max_depth + 1): 1, 2, ..., max_depth (the end of a
    # range is NOT included, hence + 1).
    for depth in range(1, args.max_depth + 1):
        # The sides still being measured at this depth.
        active = [s for s in all_sides if s not in stopped]
        # end=" " — print without going to a new line, so the rest of this
        # depth's report appears on the same line later.
        # flush=True — show it NOW. Python normally holds printed text in a
        # buffer for a while; without flush, you'd stare at an empty line
        # during a long run without knowing which depth is being measured.
        print(f"  depth {depth}:", end=" ", flush=True)

        # -------------------------------------------------------------
        # STEP a — THE "FIRST RUN": NOT A RESULT
        #
        # The very first time a database sees a query of a new shape, it
        # does extra one-off work before running it: it parses the text and
        # prepares (compiles) a query PLAN. Neo4j in particular can take a
        # few seconds to plan a new query; afterwards the plan is kept in
        # its cache and reused. The first run also pulls the data into
        # memory. Counting that time would measure "the first time" rather
        # than the traversal itself, so it's reported apart (first_run_s).
        #
        # It IS used for something important: the COUNT CHECK. Every side
        # answers "how many actors are reachable"; if the numbers differ,
        # one of the queries (or the loaded data) is wrong, and comparing
        # their speed would be meaningless.
        #
        # first = {s: run_once(...) for s in active} — a dict
        # comprehension: {"postgresql": Outcome, "neo4j-paths": Outcome...}.
        # counts = {o.count for ...} — a SET of the answers of the sides
        # that finished: a set keeps each value once, so if they all
        # agree it holds ONE number; two or more numbers = they disagree.
        #
        # A side whose first run didn't finish goes into `stopped`, with
        # the status its DEEPER depths will get. (The `\` at the end of the
        # line continues the statement on the next line.)
        # -------------------------------------------------------------
        # a. First run (not a result) and the count check.
        first = {s: run_once(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in active}
        counts = {o.count for o in first.values() if o.status == "ok"}
        for side, outcome in first.items():
            if outcome.status != "ok":
                stopped[side] = "skipped (timed out at a smaller depth)" if outcome.status == "timeout" \
                    else "skipped (failed at a smaller depth)"
        finished = [s for s in active if s not in stopped]

        # -------------------------------------------------------------
        # STEP b — THE TIMED REPETITIONS
        #
        # Why repeat at all? One single time is not reliable: the same
        # query can take 0.30 s, then 0.45 s, then 0.31 s, depending on
        # what else the computer is doing. With several runs, the MEDIAN
        # can be taken, and the spread seen (side_summary()).
        #
        # runs = {s: [] for s in finished} — an empty list per side; each
        # timed run is appended to its side's list. run_order() rotates
        # which side goes first in each repetition.
        # -------------------------------------------------------------
        # b. Timed repetitions, changing which side goes first.
        runs = {s: [] for s in finished}
        for repeat in range(1, args.repeats + 1):
            for side in run_order(finished, repeat):
                runs[side].append(timed_run(side, context["processes"], conn, driver, database,
                                            actor["actor_id"], depth, args.timeout))

        # STEP c — the work figures, one extra run per side that finished
        # (see work_figures()).
        # c. The work done inside each database.
        work = {s: work_figures(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in finished}

        # -------------------------------------------------------------
        # One summary per side, in three cases:
        #   finished                  all its figures (side_summary())
        #   in `first` but not ok     it ran now and failed: its status
        #                             ("timeout" or "error") and first time
        #   not in `first`            skipped: it had stopped at a smaller
        #                             depth; the status saved in `stopped`
        # -------------------------------------------------------------
        summaries = {}
        for side in all_sides:
            if side in finished:
                summaries[side] = side_summary(first[side], runs[side], work[side], "finished")
            elif side in first:
                summaries[side] = side_summary(first[side], [], {}, first[side].status)
            else:
                summaries[side] = side_summary(None, [], {}, stopped[side])

        # -------------------------------------------------------------
        # STEP d — WRITING THE LINES
        #
        # One line per CYPHER VERSION: each line compares PostgreSQL with
        # one Cypher version, so PostgreSQL's figures appear on both lines
        # (the same figures, measured once).
        #
        # pg / neo — the summary, plus joins_or_hops: {**dict, "key": v}
        # copies the dict and adds one key. The SQL counts joins, Cypher
        # relationships followed (traversal.sql_joins / cypher_hops).
        #
        # all_sides[1:] — every side except the first (PostgreSQL).
        #
        # line = { ... } — the TEST columns:
        #   **context["facts"]   when, which data, the graph size, and the
        #                        two database sizes (see main())
        #   start_...            the starting actor
        #   actors_reached       next(iter(counts)): the one number in the
        #                        set (iter + next take its first element:
        #                        test_build_hours.py), or "" if they
        #                        disagree or nobody finished
        #   answers_match        "yes" (one answer), "no" (several),
        #                        "unknown" (none: the set is empty)
        #   faster, times_faster from compare()
        #
        # Then the two BLOCKS, with the same loop for both sides: for each
        # name in SIDE_COLUMNS, the column "pg_<name>" (or "neo4j_<name>")
        # gets that side's value. figures.get(key, "") — an empty cell if
        # the side has no such value (temp_disk_mb for Neo4j, everything
        # but the status for a side that didn't finish). database_mb is
        # skipped here because it already came with the facts.
        #
        # writer.writerow(line) — one line of the CSV. DictWriter puts
        # each value in the column of the same name, whatever the order of
        # the dict (see main()).
        # -------------------------------------------------------------
        # d. One line per Cypher version: the test, then PostgreSQL's block, then Neo4j's.
        pg = {**summaries["postgresql"], "joins_or_hops": traversal.sql_joins(depth)}
        for side in all_sides[1:]:
            neo = {**summaries[side], "joins_or_hops": traversal.cypher_hops(depth)}
            faster, times = compare(pg, neo, args.timeout)
            line = {
                **context["facts"],
                "start_group": actor["group"], "start_rank": actor["rank"], "start_actor_id": actor["actor_id"],
                "start_login": actor["login"], "start_reach_1_hop": actor["reached"],
                "depth": depth, "cypher_version": side.split("-", 1)[1],
                "actors_reached": next(iter(counts)) if len(counts) == 1 else "",
                "answers_match": "yes" if len(counts) == 1 else ("no" if counts else "unknown"),
                "runs": args.repeats, "timeout_s": args.timeout,
                "faster": faster, "times_faster": times,
            }
            for prefix, figures in (("pg", pg), ("neo4j", neo)):
                for key in SIDE_COLUMNS:
                    if key != "database_mb":   # the database sizes are already in the facts
                        line[f"{prefix}_{key}"] = figures.get(key, "")
            writer.writerow(line)

        # -------------------------------------------------------------
        # Finish this depth's line on screen.
        #
        # If the answers differ, the lines were written (with
        # answers_match = "no", so the problem is visible in the file),
        # and `return` stops measuring this actor altogether; main() goes
        # on with the next one. sorted(counts) shows the set in order.
        #
        # notes: the sides whose first run was NOT "ok", e.g.
        # "neo4j-paths timeout". ", ".join(...) joins the pieces with
        # commas; the pieces come from a GENERATOR EXPRESSION
        # (drop_databases.py). (f"..." if notes else "") adds the part in
        # brackets only when there is something to say.
        #
        # all(...) — True if EVERY side has stopped: nothing is left to
        # measure for this actor, and `break` leaves the depth loop.
        # -------------------------------------------------------------
        if len(counts) > 1:
            print(f"ANSWERS DIFFER {sorted(counts)}; stopping this actor")
            return
        shown = next(iter(counts)) if counts else "?"
        notes = ", ".join(f"{s} {first[s].status}" for s in active if first[s].status != "ok")
        print(f"{shown} actors reached" + (f" ({notes})" if notes else ""))
        if all(s in stopped for s in all_sides):
            break


# ---------- starting actors, and the summary ----------

# ---------------------------------------------------------------------
# def results_file(database, measured_at) -> Path:  — THIS MEASUREMENT'S FILE
#
# The name is the database, "_", then the moment the measurement started.
# Inside the f-string, strftime('%Y-%m-%d_%H-%M-%S') uses SINGLE quotes
# because the f-string itself is in double quotes. No ":" in the time:
# Windows doesn't allow it in file names. Because the name starts with
# the year, sorting the names alphabetically also sorts them by TIME —
# previous_starts() relies on that.
# ---------------------------------------------------------------------
def results_file(database: str, measured_at: datetime) -> Path:
    # One file per measurement, named after the database and the moment it started.
    return RESULTS_DIR / f"{database}_{measured_at.strftime('%Y-%m-%d_%H-%M-%S')}.csv"


# ---------------------------------------------------------------------
# def previous_starts(database) -> list[dict]:  — REUSE THE SAME ACTORS
#
# The research compares measurements: the same database measured again
# another day must use the SAME 20 actors, or the two would not be
# comparable. The actors are not saved in a file of their own: every
# line of a results CSV already says which actor it started from (the
# start_... columns). So this function READS the LATEST CSV of this
# database back and collects its actors.
#
# RESULTS_DIR.glob(f"{database}_*.csv") — every file whose name matches
# the pattern: `*` stands for "any characters" (here the date-time).
# sorted(...) puts them in time order (see results_file()), so
# earlier[-1] — the LAST item of the list — is the latest. No file yet:
# an empty list (main() then chooses the actors).
#
# csv.DictReader (load_neo4j.py) gives each line as a dict, values as
# TEXT. row.get("database") (rather than row["database"]) gives None
# instead of crashing if a file has no such column. The same actor
# appears on many lines (one per depth and version), so `seen` (a set of
# ids) keeps each actor once. int(...) turns the numbers back into
# numbers.
#
# The sort key, a lambda returning a tuple (choose_starts.py):
#   a["group"] != "top"   False for "top", True for "median"; False sorts
#                         before True, so the top group comes first;
#   a["rank"]             then by rank, 1 to 10.
# ---------------------------------------------------------------------
def previous_starts(database: str) -> list[dict]:
    # The actors used in the latest measurement of this database, in their order.
    # (The date-time in the file names sorts in time order.)
    earlier = sorted(RESULTS_DIR.glob(f"{database}_*.csv"))
    if not earlier:
        return []
    seen, actors = set(), []
    with open(earlier[-1], encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("database") == database and row["start_actor_id"] not in seen:
                seen.add(row["start_actor_id"])
                actors.append({"group": row["start_group"], "rank": int(row["start_rank"]),
                               "actor_id": int(row["start_actor_id"]), "login": row["start_login"],
                               "reached": int(row["start_reach_1_hop"])})
    return sorted(actors, key=lambda a: (a["group"] != "top", a["rank"]))


# ---------------------------------------------------------------------
# def print_summary(database, path) -> None:  — A TABLE ON SCREEN
#
# After the measurement, a short table of what was just measured. It
# reads this measurement's CSV file back (`path`); every line of it
# belongs to this measurement, so list(...) keeps them all.
#
# keys — the different (group, depth, version) combinations: a SET
# comprehension (each combination once), then sorted: top before median
# (same trick as previous_starts), then by depth, then version.
#
# For each combination:
#   lines    its lines (one per actor).
#   cells    one cell per side: the median time of the actors that
#            FINISHED, in milliseconds (* 1000); `:,.1f` = a thousands
#            separator and one decimal. "+3t/o" says 3 actors didn't
#            finish (timed out or skipped). "-" if nobody finished.
#   wins     how many actors each side was faster for. sum(True, False,
#            True...) counts the True values (True counts as 1).
# Column widths (:<7, :>11): summarize_data.py.
# ---------------------------------------------------------------------
def print_summary(database: str, path: Path) -> None:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f'\nSummary of "{database}" (median over the actors that finished; t/o = timed out or skipped):')
    print(f"  {'group':<7} {'depth':>5}  {'cypher':<7} {'PostgreSQL':>11} {'Neo4j':>11}  faster (count of actors)")
    keys = sorted({(r["start_group"], int(r["depth"]), r["cypher_version"]) for r in rows},
                  key=lambda k: (k[0] != "top", k[1], k[2]))
    for group, depth, version in keys:
        lines = [r for r in rows if (r["start_group"], int(r["depth"]), r["cypher_version"]) == (group, depth, version)]
        cells = []
        for prefix in ("pg", "neo4j"):
            times = [float(r[f"{prefix}_time_s"]) for r in lines if r[f"{prefix}_status"] == "finished"]
            missing = len(lines) - len(times)
            cell = f"{statistics.median(times) * 1000:,.1f} ms" if times else "-"
            cells.append(cell + (f" +{missing}t/o" if missing else ""))
        wins = {name: sum(r["faster"] == name for r in lines) for name in ("postgresql", "neo4j")}
        print(f"  {group:<7} {depth:>5}  {version:<7} {cells[0]:>11} {cells[1]:>11}  "
              f"PG {wins['postgresql']}, Neo4j {wins['neo4j']}")


def main() -> None:
    # -----------------------------------------------------------------
    # The options. argparse turns "--max-depth" into args.max_depth (the
    # dash becomes an underscore). required=True: the script refuses to
    # run without --database. type=int converts the text to a number.
    #   --cypher       choices=... : argparse refuses any other value.
    #                  ("both",) + traversal.CYPHER_VERSIONS glues two
    #                  tuples: ("both", "paths", "levels").
    #   --new-starts   action="store_true": an ON/OFF switch with no value
    #                  (choose_starts.py).
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
    parser.add_argument("--cypher", choices=("both",) + traversal.CYPHER_VERSIONS, default="both",
                        help="Which Cypher version(s) to measure (default: both)")
    parser.add_argument("--new-starts", action="store_true",
                        help="Choose the starting actors again instead of reusing the ones of the latest measurement")
    args = parser.parse_args()
    if args.max_depth < 1 or args.repeats < 1 or args.timeout < 1:
        parser.error("--max-depth, --repeats and --timeout must be at least 1")

    # -----------------------------------------------------------------
    # THE STARTING ACTORS: reused, or chosen.
    #
    # `[] if args.new_starts else previous_starts(...)`: with --new-starts,
    # pretend there are none. An empty list counts as False, so if nothing
    # was found, choose_starts.choose_in_both() chooses them (in BOTH
    # databases, which must agree — or it raises RuntimeError).
    # \" inside the f-string is an escaped double quote.
    # -----------------------------------------------------------------
    starts = [] if args.new_starts else previous_starts(args.database)
    if starts:
        print(f"Reusing the {len(starts)} starting actors already measured for \"{args.database}\" (from their latest measurement).")
    else:
        starts = choose_starts.choose_in_both(args.database)
        print(f"Both databases choose the same {len(starts)} actors.")

    # The data window (data_window()), and the moment this measurement
    # started (datetime.now()), used twice:
    #   measured_at   as text, "%H:%M:%S" = hours, minutes, seconds; it
    #                 goes on every line of the file;
    #   path          the name of this measurement's file (results_file()).
    data_from, data_to, hours = data_window(args.database)
    started = datetime.now()
    measured_at = started.strftime("%Y-%m-%d %H:%M:%S")
    path = results_file(args.database, started)
    # -----------------------------------------------------------------
    # Two connections in ONE `with` statement, separated by a comma: both
    # are closed at the end, whatever happens. One PostgreSQL connection
    # and one Neo4j driver are reused for every run — opening a new
    # connection per run would add its own cost to every time measured.
    #
    # processes: the server processes of each database, found ONCE. If
    # none is found (e.g. the server runs on another computer, or under a
    # name not recognised), the measurement still runs: only the CPU
    # columns stay empty, and a note says so.
    #
    # context: everything measure_actor() needs, in one dict.
    #   "facts"   the TEST columns that are the same for every line:
    #             measured_at, database, the data window, plus graph_facts()
    #             (graph size and the two database_mb). The dict
    #             comprehension rounds the decimal numbers (floats: the
    #             sizes in MB) to one decimal; isinstance(v, float) checks
    #             the type (profile_schema.py); counts stay as they are.
    #
    # The print: `:,` adds thousands separators (1,234,567). Three
    # f-strings side by side are glued into one.
    # -----------------------------------------------------------------
    with traversal.connect_postgres(args.database) as conn, traversal.connect_neo4j() as driver:
        facts = graph_facts(conn, driver, args.database)
        processes = {"postgresql": server_processes("postgresql"), "neo4j": server_processes("neo4j")}
        for system, found in processes.items():
            if not found:
                print(f"Note: no {system} server process found on this computer; its CPU columns stay empty.")
        context = {"conn": conn, "driver": driver, "processes": processes,
                   "facts": {"measured_at": measured_at, "database": args.database, "data_from_utc": data_from,
                             "data_to_utc": data_to, "volume_hours": hours,
                             **{k: round(v, 1) if isinstance(v, float) else v for k, v in facts.items()}}}
        print(f'\nMeasuring "{args.database}" ({facts["graph_actors"]:,} actors, {facts["graph_repos"]:,} repos, '
              f'{facts["graph_connections"]:,} connections): {len(starts)} starting actors, depths 1-{args.max_depth}, '
              f"{args.repeats} timed runs each, time limit {args.timeout} s, Cypher: {args.cypher}")

        # -------------------------------------------------------------
        # WRITING THIS MEASUREMENT'S CSV FILE
        #
        # The file's name is printed first, so you know where to look
        # while it runs. mkdir(parents=True, exist_ok=True): creates
        # results/ if needed (extract_csv.py).
        #
        # open(path, "w", ...) — "w" opens a NEW file for writing (an
        # existing file of the same name would be emptied; the date-time
        # in the name makes that practically impossible).
        #
        # csv.DictWriter — writing rows that are DICTS
        #   csv.writer (docs_english/extract_csv.py) writes lists, where
        #   the order of the values must match the header by hand.
        #   DictWriter takes fieldnames= (the column names, here COLUMNS)
        #   and then rows as dicts: each value goes to the column with the
        #   SAME NAME, whatever order the dict is in, and a missing key
        #   gives an empty cell. It's the writing twin of csv.DictReader
        #   (load_neo4j.py).
        #     writeheader()    writes the header line (the fieldnames)
        #     writerow(dict)   writes one line (in measure_actor())
        #
        # enumerate(starts, start=1) numbers the actors from 1 (not 0) for
        # the "[3/20]" progress display.
        #
        # f.flush() after each actor — a whole measurement can take HOURS.
        # Python keeps written lines in memory for a while before they
        # really reach the file. flush() pushes them to the file now, so
        # if something goes wrong at actor 15 (a crash, Ctrl+C, the laptop
        # going to sleep), the lines of actors 1-14 are safely on disk.
        # -------------------------------------------------------------
        print(f"Results: {path}")
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            for number, actor in enumerate(starts, start=1):
                print(f"[{number}/{len(starts)}] {actor['group']} #{actor['rank']}: {actor['login']} "
                      f"(reaches {actor['reached']} in one hop)")
                measure_actor(actor, context, args, writer)
                f.flush()

    # After the `with` blocks (file closed, connections closed): the
    # table on screen, and where the lines are.
    print_summary(args.database, path)
    print(f"\nDone. The results of this measurement are in {path}")


# ---------------------------------------------------------------------
# The __name__ guard (see docs_english/download_gharchive.py), with one
# addition: main() runs inside try / except, and catches TWO kinds of
# error, written as a tuple (FileNotFoundError, RuntimeError):
#   RuntimeError        the two databases don't hold the same data
#                       (graph_facts()) or don't choose the same actors
#                       (choose_starts.choose_in_both());
#   FileNotFoundError   a missing file.
# Their messages already say what's wrong, so they're printed alone,
# without Python's long traceback, and sys.exit(1) reports the failure —
# which makes research.sh stop there (set -e, see docs_english/research.sh).
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError) as error:
        print(error)
        sys.exit(1)
