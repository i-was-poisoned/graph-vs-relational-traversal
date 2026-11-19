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

import argparse
import csv
import re
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

import psutil

import choose_starts
import traversal

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

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

BUSY_CPU = 80.0       # computer CPU above this (percent) during a run: not reliable
NOISY_SPREAD = 3.0    # slowest run more than 3 times the fastest: not reliable
NAME = re.compile(r"^gharchive-(\d{4}-\d{2}-\d{2})-(\d{1,2})(?:-(\d+)h)?$")


# ---------- which data ----------

def data_window(database: str) -> tuple[str, str, int | None]:
    # build_hours.py names each database after its data: gharchive-<date>-<hour>[-<n>h].
    match = NAME.match(database)
    if not match:
        return "", "", None
    date, hour, hours = match.group(1), int(match.group(2)), int(match.group(3) or 1)
    begin = datetime.strptime(date, "%Y-%m-%d") + timedelta(hours=hour)
    end = begin + timedelta(hours=hours)
    return begin.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M"), hours


def folder_size_mb(path: Path) -> float | None:
    if not path.is_dir():
        return None
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024 ** 2


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

def sides(cypher: str) -> list[str]:
    # The "sides" measured: PostgreSQL and one or two Cypher versions.
    versions = traversal.CYPHER_VERSIONS if cypher == "both" else (cypher,)
    return ["postgresql"] + [f"neo4j-{v}" for v in versions]


def run_order(all_sides: list[str], repeat: int) -> list[str]:
    # Repetition 1 starts with the first side, repetition 2 with the second, and so on, so
    # anything else happening on the computer affects every side alike.
    shift = (repeat - 1) % len(all_sides)
    return all_sides[shift:] + all_sides[:shift]


def run_once(side: str, conn, driver, database: str, start: int, depth: int, timeout: int):
    if side == "postgresql":
        return traversal.run_postgres_reach(conn, start, depth, timeout)
    return traversal.run_neo4j_reach(driver, database, start, depth, timeout, side.split("-", 1)[1])


def timed_run(side, processes, conn, driver, database, start, depth, timeout) -> dict:
    machine_cpu = psutil.cpu_percent(interval=0.2)
    procs = processes["postgresql" if side == "postgresql" else "neo4j"]
    before = cpu_seconds(procs)
    outcome = run_once(side, conn, driver, database, start, depth, timeout)
    after = cpu_seconds(procs)
    used = sum(after[pid] - before[pid] for pid in after if pid in before) if procs else None
    return {"outcome": outcome, "cpu_s": used, "machine_cpu": machine_cpu}


def work_figures(side, conn, driver, database, start, depth, timeout) -> dict:
    try:
        if side == "postgresql":
            return traversal.postgres_work(conn, start, depth, timeout)
        return traversal.neo4j_work(driver, database, start, depth, timeout, side.split("-", 1)[1])
    except Exception as error:
        print(f"(no work figures for {side}: {str(error)[:80]})", end=" ")
        return {}


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


def measure_actor(actor: dict, context: dict, args, writer: csv.DictWriter) -> None:
    conn, driver, database = context["conn"], context["driver"], args.database
    all_sides = sides(args.cypher)
    stopped = {}   # side -> the status it gets at deeper depths
    for depth in range(1, args.max_depth + 1):
        active = [s for s in all_sides if s not in stopped]
        print(f"  depth {depth}:", end=" ", flush=True)

        # a. First run (not a result) and the count check.
        first = {s: run_once(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in active}
        counts = {o.count for o in first.values() if o.status == "ok"}
        for side, outcome in first.items():
            if outcome.status != "ok":
                stopped[side] = "skipped (timed out at a smaller depth)" if outcome.status == "timeout" \
                    else "skipped (failed at a smaller depth)"
        finished = [s for s in active if s not in stopped]

        # b. Timed repetitions, changing which side goes first.
        runs = {s: [] for s in finished}
        for repeat in range(1, args.repeats + 1):
            for side in run_order(finished, repeat):
                runs[side].append(timed_run(side, context["processes"], conn, driver, database,
                                            actor["actor_id"], depth, args.timeout))

        # c. The work done inside each database.
        work = {s: work_figures(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in finished}

        summaries = {}
        for side in all_sides:
            if side in finished:
                summaries[side] = side_summary(first[side], runs[side], work[side], "finished")
            elif side in first:
                summaries[side] = side_summary(first[side], [], {}, first[side].status)
            else:
                summaries[side] = side_summary(None, [], {}, stopped[side])

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

        if len(counts) > 1:
            print(f"ANSWERS DIFFER {sorted(counts)}; stopping this actor")
            return
        shown = next(iter(counts)) if counts else "?"
        notes = ", ".join(f"{s} {first[s].status}" for s in active if first[s].status != "ok")
        print(f"{shown} actors reached" + (f" ({notes})" if notes else ""))
        if all(s in stopped for s in all_sides):
            break


# ---------- starting actors, and the summary ----------

def results_file(database: str, measured_at: datetime) -> Path:
    # One file per measurement, named after the database and the moment it started.
    return RESULTS_DIR / f"{database}_{measured_at.strftime('%Y-%m-%d_%H-%M-%S')}.csv"


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

    starts = [] if args.new_starts else previous_starts(args.database)
    if starts:
        print(f"Reusing the {len(starts)} starting actors already measured for \"{args.database}\" (from their latest measurement).")
    else:
        starts = choose_starts.choose_in_both(args.database)
        print(f"Both databases choose the same {len(starts)} actors.")

    data_from, data_to, hours = data_window(args.database)
    started = datetime.now()
    measured_at = started.strftime("%Y-%m-%d %H:%M:%S")
    path = results_file(args.database, started)
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

    print_summary(args.database, path)
    print(f"\nDone. The results of this measurement are in {path}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError) as error:
        print(error)
        sys.exit(1)
