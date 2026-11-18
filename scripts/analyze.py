"""Summarise the measurements made by measure.py.

For one database, it reads its latest measurement (results/<database>/<date-time>/)
and writes, in that same folder:

    per_actor.csv   for every actor, depth and side: median, minimum and maximum
                    time of the timed runs, how many finished, timed out or
                    failed, the answer, and a warning if the runs were noisy
    summary.csv     the same per group (top / median) and depth: the median over
                    the actors, and how many times slower PostgreSQL was than
                    Neo4j (above 1: Neo4j faster; below 1: PostgreSQL faster)

It also rebuilds results/all_databases.csv: one line per database, group, depth
and side, from the latest measurement of every database, to compare volumes.

A run is "noisy" if its slowest timed run took more than NOISY_SPREAD times its
fastest, or if the computer was very busy (CPU above BUSY_CPU %) during it.

Usage:
    ./run.sh scripts/analyze.py --database gharchive-2026-08-27-12-6h
    ./run.sh scripts/analyze.py --all
"""

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import choose_starts

NOISY_SPREAD = 3.0
BUSY_CPU = 80.0
SYSTEMS = ("postgresql", "neo4j")


def latest_measurement(database: str) -> Path:
    folder = choose_starts.RESULTS_DIR / database
    measurements = sorted(p for p in folder.glob("*") if (p / "runs.csv").exists()) if folder.exists() else []
    if not measurements:
        raise FileNotFoundError(f"No measurement of \"{database}\" yet: run measure.py --database {database}")
    return measurements[-1]


def read_runs(folder: Path) -> list[dict]:
    with open(folder / "runs.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarise_actor(runs: list[dict]) -> dict:
    # runs: the lines of ONE actor, depth and side. Run 0 is the first run: not a result.
    timed = [r for r in runs if int(r["run"]) >= 1]
    ok = [float(r["seconds"]) for r in timed if r["status"] == "ok"]
    statuses = [r["status"] for r in timed] or [r["status"] for r in runs]
    counts = {int(r["count"]) for r in runs if r["status"] == "ok" and r["count"] != ""}
    busy = any(r["machine_cpu_percent"] and float(r["machine_cpu_percent"]) > BUSY_CPU for r in timed)
    spread = (max(ok) / min(ok)) if len(ok) >= 2 and min(ok) > 0 else None
    return {
        "median_s": statistics.median(ok) if ok else None,
        "min_s": min(ok) if ok else None,
        "max_s": max(ok) if ok else None,
        "finished": statuses.count("ok"),
        "timeouts": statuses.count("timeout"),
        "errors": statuses.count("error"),
        "count": next(iter(counts)) if len(counts) == 1 else None,
        "noisy": bool(busy or (spread is not None and spread > NOISY_SPREAD)),
    }


def per_actor(runs: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in runs:
        grouped[(r["group"], int(r["actor_id"]), int(r["depth"]), r["system"])].append(r)
    rows = []
    for (group, actor_id, depth, system), lines in sorted(grouped.items()):
        rows.append({"group": group, "actor_id": actor_id, "depth": depth, "system": system, **summarise_actor(lines)})
    return rows


def summary(actor_rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in actor_rows:
        grouped[(r["group"], r["depth"], r["system"])].append(r)
    medians = {}
    rows = []
    for (group, depth, system), lines in sorted(grouped.items(), key=lambda kv: (kv[0][0] != "top",) + kv[0][1:]):
        times = [r["median_s"] for r in lines if r["median_s"] is not None]
        medians[(group, depth, system)] = statistics.median(times) if times else None
        rows.append({"group": group, "depth": depth, "system": system, "actors": len(lines),
                     "actors_finished": len(times), "median_s": medians[(group, depth, system)],
                     "timeouts": sum(r["timeouts"] for r in lines), "errors": sum(r["errors"] for r in lines),
                     "noisy_actors": sum(r["noisy"] for r in lines)})
    for row in rows:
        pg, neo = medians.get((row["group"], row["depth"], "postgresql")), medians.get((row["group"], row["depth"], "neo4j"))
        row["postgresql_vs_neo4j"] = round(pg / neo, 3) if pg and neo else None
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt(seconds) -> str:
    return "-" if seconds is None else f"{seconds * 1000:,.1f} ms" if seconds < 1 else f"{seconds:,.2f} s"


def analyse(database: str) -> list[dict]:
    folder = latest_measurement(database)
    actor_rows = per_actor(read_runs(folder))
    summary_rows = summary(actor_rows)
    write_csv(actor_rows, folder / "per_actor.csv")
    write_csv(summary_rows, folder / "summary.csv")

    print(f'"{database}" (measurement {folder.name})')
    print(f"  {'group':<7} {'depth':>5}  {'PostgreSQL':>12}  {'Neo4j':>12}  {'PG / Neo4j':>10}  notes")
    by_key = {(r["group"], r["depth"], r["system"]): r for r in summary_rows}
    for group, depth in sorted({(r["group"], r["depth"]) for r in summary_rows}, key=lambda k: (k[0] != "top", k[1])):
        pg, neo = by_key.get((group, depth, "postgresql"), {}), by_key.get((group, depth, "neo4j"), {})
        notes = [f"{s}: {r['timeouts']} timeouts" for s, r in (("PG", pg), ("Neo4j", neo)) if r.get("timeouts")]
        notes += [f"{s}: {r['noisy_actors']} noisy" for s, r in (("PG", pg), ("Neo4j", neo)) if r.get("noisy_actors")]
        ratio = pg.get("postgresql_vs_neo4j")
        print(f"  {group:<7} {depth:>5}  {fmt(pg.get('median_s')):>12}  {fmt(neo.get('median_s')):>12}  "
              f"{'-' if ratio is None else f'{ratio:,.2f}x':>10}  {'; '.join(notes)}")
    mismatches = sum(1 for r in actor_rows if r["count"] is None and r["finished"])
    if mismatches:
        print(f"  WARNING: {mismatches} actor/depth lines didn't give one single answer")
    print(f"  Written: {folder / 'per_actor.csv'} and {folder / 'summary.csv'}\n")
    return [{"database": database, "measurement": folder.name, **r} for r in summary_rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", help="Summarise the latest measurement of this database")
    parser.add_argument("--all", action="store_true", help="Summarise every measured database")
    args = parser.parse_args()

    root = choose_starts.RESULTS_DIR
    measured = sorted(p.name for p in root.glob("*") if p.is_dir() and any(p.glob("*/runs.csv"))) if root.exists() else []
    if args.database:
        analyse(args.database)
    elif not args.all:
        parser.error("give --database NAME or --all")

    # Always refresh the comparison of all volumes measured so far.
    all_rows = []
    for database in measured:
        all_rows += analyse(database) if args.all else \
            [{"database": database, "measurement": latest_measurement(database).name, **r}
             for r in summary(per_actor(read_runs(latest_measurement(database))))]
    write_csv(all_rows, root / "all_databases.csv")
    if all_rows:
        print(f"Comparison of all {len(measured)} measured database(s): {root / 'all_databases.csv'}")


if __name__ == "__main__":
    main()
