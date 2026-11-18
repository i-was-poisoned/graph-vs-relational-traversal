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

import argparse
import csv
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

import psutil

import choose_starts
import traversal

RUN_FIELDS = ["actor_id", "group", "depth", "system", "run", "status", "seconds", "count",
              "machine_cpu_percent", "machine_memory_percent", "error"]
WORK_FIELDS = ["actor_id", "group", "depth", "system", "server_ms", "blocks_from_memory", "blocks_from_disk",
               "temp_blocks_written", "db_hits", "page_cache_hits", "page_cache_misses", "memory_bytes"]
SYSTEMS = ("postgresql", "neo4j")


def run_order(repeat: int) -> tuple[str, str]:
    # Repetition 1: PostgreSQL first; repetition 2: Neo4j first; and so on.
    return SYSTEMS if repeat % 2 == 1 else SYSTEMS[::-1]


def machine_load() -> tuple[float, float]:
    # CPU use of the whole computer over a short moment, and memory in use (percent).
    return psutil.cpu_percent(interval=0.2), psutil.virtual_memory().percent


def read_starts(database: str) -> list[dict]:
    path = choose_starts.RESULTS_DIR / database / "starts.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} doesn't exist: run choose_starts.py --database {database} first")
    with open(path, encoding="utf-8") as f:
        return [{**row, "actor_id": int(row["actor_id"])} for row in csv.DictReader(f)]


def conditions(conn, driver, database: str, args: argparse.Namespace) -> dict:
    settings = ("shared_buffers", "work_mem", "effective_cache_size", "max_parallel_workers_per_gather", "jit")
    postgres = {name: conn.execute(f"SHOW {name}").fetchone()[0] for name in settings}
    postgres["version"] = conn.execute("SHOW server_version").fetchone()[0]
    postgres["database_size_bytes"] = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    postgres["rows"] = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("actor", "repo", "actor_repo")}

    records = driver.execute_query(
        "SHOW SETTINGS YIELD name, value WHERE name IN ['server.memory.heap.initial_size', "
        "'server.memory.heap.max_size', 'server.memory.pagecache.size', 'dbms.memory.transaction.total.max'] "
        "RETURN name, value", database_="system").records
    neo4j = {r["name"]: r["value"] for r in records}
    version = driver.execute_query("CALL dbms.components() YIELD versions, edition RETURN versions[0] AS v, edition",
                                   database_="system").records[0]
    neo4j["version"] = f"{version['v']} {version['edition']}"
    count = lambda q: driver.execute_query(q, database_=database).records[0][0]
    neo4j["rows"] = {"actors": count("MATCH (a:Actor) RETURN count(a)"),
                     "repos": count("MATCH (r:Repo) RETURN count(r)"),
                     "connections": count("MATCH ()-[c:INTERACTED_WITH]->() RETURN count(c)")}

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


def run_once(system: str, conn, driver, database: str, start: int, depth: int, timeout: int):
    if system == "postgresql":
        return traversal.run_postgres_reach(conn, start, depth, timeout)
    return traversal.run_neo4j_reach(driver, database, start, depth, timeout)


def measure_actor(actor: dict, conn, driver, database: str, args, runs: csv.DictWriter, work: csv.DictWriter) -> None:
    stopped = set()   # sides that ran out of time at a smaller depth
    for depth in range(1, args.max_depth + 1):
        active = [s for s in SYSTEMS if s not in stopped]
        if not active:
            break
        print(f"  depth {depth}:", end=" ", flush=True)

        # 1. First run (not a result) and the count check.
        first = {s: run_once(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in active}
        for system, outcome in first.items():
            runs.writerow(row(actor, depth, system, 0, outcome, (None, None)))
        counts = {s: o.count for s, o in first.items() if o.status == "ok"}
        if len(counts) == 2 and counts["postgresql"] != counts["neo4j"]:
            print(f"COUNTS DIFFER (PostgreSQL {counts['postgresql']}, Neo4j {counts['neo4j']}); stopping this actor")
            return
        for system, outcome in first.items():
            if outcome.status != "ok":
                stopped.add(system)
        timed = [s for s in active if s not in stopped]

        # 2. Timed repetitions, alternating which side goes first.
        for repeat in range(1, args.repeats + 1):
            for system in run_order(repeat):
                if system in timed:
                    load = machine_load()
                    outcome = run_once(system, conn, driver, database, actor["actor_id"], depth, args.timeout)
                    runs.writerow(row(actor, depth, system, repeat, outcome, load))

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

        shown = counts.get("postgresql", counts.get("neo4j"))
        status = ", ".join(f"{s} {first[s].status}" for s in active if first[s].status != "ok")
        print(f"{shown} actors reached" + (f" ({status})" if status else ""))


def row(actor: dict, depth: int, system: str, run: int, outcome, load) -> dict:
    return {"actor_id": actor["actor_id"], "group": actor["group"], "depth": depth, "system": system, "run": run,
            "status": outcome.status, "seconds": round(outcome.seconds, 6), "count": outcome.count,
            "machine_cpu_percent": load[0], "machine_memory_percent": load[1], "error": outcome.error}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", required=True, help="The database to measure (same name on both sides)")
    parser.add_argument("--max-depth", type=int, default=6, help="Deepest traversal, in hops (default: 6)")
    parser.add_argument("--repeats", type=int, default=5, help="Timed runs per depth and side (default: 5)")
    parser.add_argument("--timeout", type=int, default=60, help="Seconds before a run is stopped (default: 60)")
    args = parser.parse_args()
    if args.max_depth < 1 or args.repeats < 1 or args.timeout < 1:
        parser.error("--max-depth, --repeats and --timeout must be at least 1")

    starts = read_starts(args.database)
    out_dir = choose_starts.RESULTS_DIR / args.database / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir.mkdir(parents=True)

    with traversal.connect_postgres(args.database) as conn, traversal.connect_neo4j() as driver:
        info = conditions(conn, driver, args.database, args)
        (out_dir / "conditions.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        print(f'Measuring "{args.database}": {len(starts)} starting actors, depths 1-{args.max_depth}, '
              f"{args.repeats} timed runs each, time limit {args.timeout} s")
        print(f"Results: {out_dir}\n")

        with open(out_dir / "runs.csv", "w", newline="", encoding="utf-8") as runs_file, \
             open(out_dir / "work.csv", "w", newline="", encoding="utf-8") as work_file:
            runs = csv.DictWriter(runs_file, fieldnames=RUN_FIELDS)
            work = csv.DictWriter(work_file, fieldnames=WORK_FIELDS)
            runs.writeheader()
            work.writeheader()
            for number, actor in enumerate(starts, start=1):
                print(f"[{number}/{len(starts)}] {actor['group']} #{actor['rank']}: {actor['login']} "
                      f"(reaches {actor['reached']} in one hop)")
                measure_actor(actor, conn, driver, args.database, args, runs, work)
                runs_file.flush()
                work_file.flush()

    print(f"\nDone. Results in {out_dir}")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(error)
        sys.exit(1)
