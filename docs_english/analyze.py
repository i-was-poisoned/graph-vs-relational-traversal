########################################################################
# ANNOTATED COPY — for learning purposes only.
#
# This is a line-by-line explained duplicate of scripts/analyze.py.
# It is NOT meant to be run — it lives in docs_english/ because its purpose
# is to teach, not to execute. The real, "clean" script (with none of this
# commentary) is scripts/analyze.py.
#
# Read these annotated copies first; what they explain is NOT repeated here:
#   - download_gharchive.py   argparse, Path, main() and the __name__ guard
#   - extract_csv.py          open(..., newline=""), sorted(...), sets
#   - load_neo4j.py           csv.DictReader
#   - summarize_data.py       collections.defaultdict (the basic idea)
#   - pipeline.py             RawDescriptionHelpFormatter
#   - measure.py              what runs.csv contains (run 0, the timed runs,
#                             status, machine load), csv.DictWriter, lambda,
#                             dict comprehensions, `**` inside a dict, the
#                             one-folder-per-date-time layout of results/
#
# What's NEW here — turning a pile of timed runs into a few numbers you
# can trust:
#   - the MEDIAN (and why not the mean), the minimum and the maximum;
#   - ignoring run 0;
#   - flagging NOISY runs (spread above 3x, or the computer above 80 % CPU);
#   - grouping lines by a tuple key with defaultdict(list);
#   - the PostgreSQL / Neo4j RATIO (above 1: Neo4j faster);
#   - results/all_databases.csv, to compare data VOLUMES side by side.
#
# How it's meant to be run — normally as the last step of research.sh:
#     ./research.sh --database gharchive-2026-08-27-12-6h
# or alone, through run.sh:
#     ./run.sh scripts/analyze.py --database gharchive-2026-08-27-12-6h
#     ./run.sh scripts/analyze.py --all
# (It needs no database connection: it only reads CSV files.)
########################################################################

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

# ---------------------------------------------------------------------
# statistics — a standard-library module with the usual summary numbers
# (mean, median, standard deviation...). Only statistics.median() is
# used here.
#
# defaultdict — see docs_english/summarize_data.py. Here it's used as
# defaultdict(list): a dict where a missing key starts as an EMPTY LIST,
# so `grouped[key].append(x)` works even the first time a key is seen.
#
# No psycopg, no neo4j: this script only reads the CSV files that
# measure.py wrote.
# ---------------------------------------------------------------------
import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import choose_starts

# ---------------------------------------------------------------------
# The two thresholds for calling a measurement "noisy" (untrustworthy):
#
#   NOISY_SPREAD = 3.0   the slowest timed run took more than 3 times the
#                        fastest. The same query on the same data should
#                        take roughly the same time every run; a 3x gap
#                        means something else interfered.
#   BUSY_CPU = 80.0      the computer's CPU was above 80 % just before a
#                        run (machine_cpu_percent, from measure.py): other
#                        programs were competing for the processor.
#
# A noisy line is still kept and summarised — it's only FLAGGED, so you
# know which numbers to treat with care (or to measure again).
# ---------------------------------------------------------------------
NOISY_SPREAD = 3.0
BUSY_CPU = 80.0
SYSTEMS = ("postgresql", "neo4j")


# ---------------------------------------------------------------------
# def latest_measurement(database) — the newest results folder
#
# folder.glob("*") lists everything inside results/<database>/. Only the
# folders that contain a runs.csv are measurements (starts.csv also lives
# there, and is not one).
#
# sorted(...) — the folder names are dates like 2026-11-18_14-05-31, so
# alphabetical order IS time order; measurements[-1] is the newest.
#
# `... if folder.exists() else []` — if the database was never measured,
# the folder may not exist at all: use an empty list instead of failing.
# Either way, an empty list gives a clear FileNotFoundError message.
# \" inside a "..." string is a literal double-quote character.
# ---------------------------------------------------------------------
def latest_measurement(database: str) -> Path:
    folder = choose_starts.RESULTS_DIR / database
    measurements = sorted(p for p in folder.glob("*") if (p / "runs.csv").exists()) if folder.exists() else []
    if not measurements:
        raise FileNotFoundError(f"No measurement of \"{database}\" yet: run measure.py --database {database}")
    return measurements[-1]


# All the lines of runs.csv, as a list of dicts (values are TEXT).
def read_runs(folder: Path) -> list[dict]:
    with open(folder / "runs.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------
# def summarise_actor(runs) — ONE actor, ONE depth, ONE side -> one line
#
# `runs` holds the lines of runs.csv for that combination: run 0 plus the
# timed runs 1..5. Remember every value is text, hence int(...) and
# float(...).
# ---------------------------------------------------------------------
def summarise_actor(runs: list[dict]) -> dict:
    # -----------------------------------------------------------------
    # timed — only runs 1, 2, 3...: run 0 is IGNORED for the times. It
    # includes one-off work (preparing the query plan — about 5 s for
    # Neo4j's first query of a new shape — and pulling data into memory),
    # so it would describe "the first time", not the traversal. See
    # docs_english/measure.py, step 1.
    #
    # ok — the times (as numbers) of the timed runs that FINISHED. A run
    # that timed out has a "seconds" too (the time until it was stopped),
    # but that's not a real time and must not be mixed in.
    # -----------------------------------------------------------------
    # runs: the lines of ONE actor, depth and side. Run 0 is the first run: not a result.
    timed = [r for r in runs if int(r["run"]) >= 1]
    ok = [float(r["seconds"]) for r in timed if r["status"] == "ok"]
    # -----------------------------------------------------------------
    # statuses — "ok" / "timeout" / "error" of the timed runs, to count
    # them below. `A or B` gives A if A is not empty, otherwise B: when
    # there are NO timed runs (the side already ran out of time on run 0,
    # so measure.py skipped the repetitions), fall back to run 0's status,
    # so the timeout still shows up in the counts.
    #
    # counts — a SET of the answers given by the runs that finished. A set
    # keeps each value once: if every run said 1234, the set is {1234}.
    # More than one value would mean the same query gave different
    # answers — a bug. (r["count"] != "": an empty cell is skipped.)
    #
    # busy — any(...) is True if AT LEAST ONE item is True. For each timed
    # run: is there a CPU figure (`r[...] and`: an empty cell is falsy, so
    # float("") is never attempted) and is it above BUSY_CPU?
    #
    # spread — slowest / fastest. Only meaningful with at least 2 finished
    # runs, and not dividing by 0; otherwise None ("no spread to speak of").
    # -----------------------------------------------------------------
    statuses = [r["status"] for r in timed] or [r["status"] for r in runs]
    counts = {int(r["count"]) for r in runs if r["status"] == "ok" and r["count"] != ""}
    busy = any(r["machine_cpu_percent"] and float(r["machine_cpu_percent"]) > BUSY_CPU for r in timed)
    spread = (max(ok) / min(ok)) if len(ok) >= 2 and min(ok) > 0 else None
    # -----------------------------------------------------------------
    # The line for per_actor.csv.
    #
    # median_s — THE MEDIAN, NOT THE MEAN. Sort the times and take the
    # middle one (with an even number of values, the average of the two
    # middle ones). Why not the mean (the average)? Because a benchmark's
    # disturbances only ever make runs SLOWER, never faster: one run hit
    # by an antivirus scan, e.g. 0.30, 0.31, 0.29, 0.30, 3.00 s, pulls the
    # mean up to 0.84 s — a time that no run actually took — while the
    # median stays at 0.30 s. The median ignores a few outliers.
    #
    # min_s / max_s — the fastest and slowest finished runs: they show how
    # much the runs spread around the median.
    #
    # `... if ok else None` — with no finished run there's no time at all;
    # None becomes an empty cell in the CSV.
    #
    # statuses.count("ok") — list.count(x) counts how many items equal x.
    #
    # count — next(iter(counts)) takes the single value out of the set (a
    # set has no [0]: iter() walks through it, next() takes the first
    # item). Only when there's exactly ONE answer; otherwise None, which
    # analyse() reports as a warning.
    #
    # noisy — True if the computer was busy OR the spread was above 3x.
    # bool(...) makes sure the value is exactly True/False.
    # -----------------------------------------------------------------
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


# ---------------------------------------------------------------------
# def per_actor(runs) — GROUP the lines, then summarise each group
#
# grouped[(group, actor_id, depth, system)].append(r)
#   The key is a TUPLE of four values: a tuple can be a dict key, so all
#   the lines with the same actor, depth and side end up in the same
#   list. defaultdict(list) creates that list the first time a key
#   appears. actor_id and depth are converted to int so that sorting
#   puts depth 10 after 9 (as text, "10" < "9").
#
# for (group, actor_id, depth, system), lines in sorted(grouped.items()):
#   .items() gives (key, value) pairs; the key tuple is UNPACKED into four
#   names right in the for line. sorted() orders them by group, then
#   actor, then depth, then side.
#
# {..., **summarise_actor(lines)} — the four identifying columns, then
# all the summary columns added after them (`**` as in measure.py).
# ---------------------------------------------------------------------
def per_actor(runs: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in runs:
        grouped[(r["group"], int(r["actor_id"]), int(r["depth"]), r["system"])].append(r)
    rows = []
    for (group, actor_id, depth, system), lines in sorted(grouped.items()):
        rows.append({"group": group, "actor_id": actor_id, "depth": depth, "system": system, **summarise_actor(lines)})
    return rows


# ---------------------------------------------------------------------
# def summary(actor_rows) — FROM ACTORS TO GROUPS
#
# The 10 actors of a group (top or median) are combined into one line per
# group, depth and side. Same grouping technique as per_actor(), with a
# three-value key this time (no actor_id).
# ---------------------------------------------------------------------
def summary(actor_rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in actor_rows:
        grouped[(r["group"], r["depth"], r["system"])].append(r)
    # medians remembers each group's median, so the ratio can be computed
    # afterwards, once both sides are known.
    medians = {}
    rows = []
    # -----------------------------------------------------------------
    # The sort order: "top" before "median", then by depth, then by side.
    #
    # Plain alphabetical order would put "median" before "top". The key
    # function builds, for each (key, value) pair kv:
    #     (kv[0][0] != "top",) + kv[0][1:]
    #   kv[0] is the key tuple (group, depth, system); kv[0][0] the group.
    #   `kv[0][0] != "top"` is False for top, True for median, and False
    #   sorts before True. `(x,)` — with the comma — is a one-item tuple,
    #   and `+` glues it to (depth, system). So top comes first, and inside
    #   each group, depth 1, 2, 3...
    # -----------------------------------------------------------------
    for (group, depth, system), lines in sorted(grouped.items(), key=lambda kv: (kv[0][0] != "top",) + kv[0][1:]):
        # -------------------------------------------------------------
        # The group's time = the MEDIAN OF THE ACTORS' MEDIANS, for the
        # same reason as before: one unusual actor doesn't drag the whole
        # group. Actors with no finished run (median_s None) are left out
        # of the time, but still counted in "actors" — compare "actors"
        # with "actors_finished" to see how many timed out.
        #
        # sum(r["noisy"] for r in lines) — True counts as 1 and False as 0,
        # so summing True/False values counts the noisy actors.
        # -------------------------------------------------------------
        times = [r["median_s"] for r in lines if r["median_s"] is not None]
        medians[(group, depth, system)] = statistics.median(times) if times else None
        rows.append({"group": group, "depth": depth, "system": system, "actors": len(lines),
                     "actors_finished": len(times), "median_s": medians[(group, depth, system)],
                     "timeouts": sum(r["timeouts"] for r in lines), "errors": sum(r["errors"] for r in lines),
                     "noisy_actors": sum(r["noisy"] for r in lines)})
    # -----------------------------------------------------------------
    # THE RATIO — the research's headline number.
    #
    # postgresql_vs_neo4j = PostgreSQL's median time / Neo4j's median time,
    # for the same group and depth. It's "how many times slower PostgreSQL
    # was":
    #     4.0   PostgreSQL took 4 times as long -> Neo4j faster
    #     1.0   the same
    #     0.25  PostgreSQL took a quarter of the time -> PostgreSQL faster
    # Watching this number cross 1 as the depth (or the data volume) grows
    # answers the research question: WHERE does Neo4j start to win?
    #
    # The same value is written on both sides' lines (postgresql and
    # neo4j). medians.get(...) gives None if a side has no line; `if pg
    # and neo` — only when both have a time (None, or a 0 that would make
    # the division fail, give None). round(..., 3): three decimals.
    # -----------------------------------------------------------------
    for row in rows:
        pg, neo = medians.get((row["group"], row["depth"], "postgresql")), medians.get((row["group"], row["depth"], "neo4j"))
        row["postgresql_vs_neo4j"] = round(pg / neo, 3) if pg and neo else None
    return rows


# ---------------------------------------------------------------------
# def write_csv(rows, path) — a list of dicts to a CSV file
#
# csv.DictWriter (docs_english/measure.py) with fieldnames=list(rows[0]):
# list(a_dict) gives its KEYS, in the order they were added, so the
# header is taken from the first row itself. (Nothing to write -> return
# straight away, since there'd be no rows[0].)
# writer.writerows(rows) writes all the lines in one call.
# ---------------------------------------------------------------------
def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------
# def fmt(seconds) — a time, readable on screen
#
# Two one-line if/else chained:  A if cond1 else B if cond2 else C
#   None        -> "-"
#   below 1 s   -> in milliseconds: 0.0123 -> "12.3 ms"
#   otherwise   -> in seconds:      12.3456 -> "12.35 s"
# Format specs inside { }: `,` adds a thousands separator (1,234.5) and
# `.1f` / `.2f` mean "1 / 2 decimals".
# ---------------------------------------------------------------------
def fmt(seconds) -> str:
    return "-" if seconds is None else f"{seconds * 1000:,.1f} ms" if seconds < 1 else f"{seconds:,.2f} s"


# ---------------------------------------------------------------------
# def analyse(database) — the whole job for ONE database
#
# Find the latest measurement, summarise per actor, then per group,
# write both CSV files next to runs.csv, and print a table.
# ---------------------------------------------------------------------
def analyse(database: str) -> list[dict]:
    folder = latest_measurement(database)
    actor_rows = per_actor(read_runs(folder))
    summary_rows = summary(actor_rows)
    write_csv(actor_rows, folder / "per_actor.csv")
    write_csv(summary_rows, folder / "summary.csv")

    # -----------------------------------------------------------------
    # The table on screen: one line per group and depth, both sides side
    # by side. Column widths: `:<7` pads to 7 characters, aligned left;
    # `:>12` pads to 12, aligned right (numbers line up on the right).
    #
    # by_key — the summary rows in a dict keyed by (group, depth, system),
    # to pick the PostgreSQL and the Neo4j line of the same group and
    # depth. {(..., ...) for r in summary_rows} is a SET comprehension:
    # each (group, depth) once. Sorted with "top" first, as in summary().
    # .get(..., {}) gives an empty dict if a side is missing, so pg.get()
    # / neo.get() below still work (and give None).
    # -----------------------------------------------------------------
    print(f'"{database}" (measurement {folder.name})')
    print(f"  {'group':<7} {'depth':>5}  {'PostgreSQL':>12}  {'Neo4j':>12}  {'PG / Neo4j':>10}  notes")
    by_key = {(r["group"], r["depth"], r["system"]): r for r in summary_rows}
    for group, depth in sorted({(r["group"], r["depth"]) for r in summary_rows}, key=lambda k: (k[0] != "top", k[1])):
        pg, neo = by_key.get((group, depth, "postgresql"), {}), by_key.get((group, depth, "neo4j"), {})
        # The "notes" column: timeouts and noisy actors, per side, only
        # when there are any (0 is falsy, so `if r.get(...)` skips it).
        # `notes += [...]` adds the second list's items to the first.
        notes = [f"{s}: {r['timeouts']} timeouts" for s, r in (("PG", pg), ("Neo4j", neo)) if r.get("timeouts")]
        notes += [f"{s}: {r['noisy_actors']} noisy" for s, r in (("PG", pg), ("Neo4j", neo)) if r.get("noisy_actors")]
        ratio = pg.get("postgresql_vs_neo4j")
        # An f-string INSIDE an f-string: the ratio is formatted as e.g.
        # "4.00x" first, then that text is right-aligned to 10 characters.
        # '; '.join(notes) puts the notes on one line, separated by "; ".
        print(f"  {group:<7} {depth:>5}  {fmt(pg.get('median_s')):>12}  {fmt(neo.get('median_s')):>12}  "
              f"{'-' if ratio is None else f'{ratio:,.2f}x':>10}  {'; '.join(notes)}")
    # -----------------------------------------------------------------
    # A safety warning: lines where runs FINISHED but did not give one
    # single answer (count is None). measure.py already checks that both
    # sides agree on run 0; this catches a query giving different answers
    # from one run to the next. sum(1 for ...) counts matching lines.
    # -----------------------------------------------------------------
    mismatches = sum(1 for r in actor_rows if r["count"] is None and r["finished"])
    if mismatches:
        print(f"  WARNING: {mismatches} actor/depth lines didn't give one single answer")
    print(f"  Written: {folder / 'per_actor.csv'} and {folder / 'summary.csv'}\n")
    # The summary rows, each with the database name and measurement folder
    # added in front: the lines that go into all_databases.csv.
    return [{"database": database, "measurement": folder.name, **r} for r in summary_rows]


def main() -> None:
    # --database NAME: summarise one database. --all: every one measured
    # so far. action="store_true" makes --all an on/off switch (True when
    # given, False otherwise), with no value after it.
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", help="Summarise the latest measurement of this database")
    parser.add_argument("--all", action="store_true", help="Summarise every measured database")
    args = parser.parse_args()

    # -----------------------------------------------------------------
    # measured — the names of every database that has at least one
    # measurement: the folders of results/ (p.is_dir()) containing some
    # <date-time>/runs.csv. any(p.glob("*/runs.csv")) is True if the
    # pattern matches at least one file.
    #
    # With --database, analyse that one; with neither option, parser.error
    # stops with a message (see docs_english/measure.py).
    # -----------------------------------------------------------------
    root = choose_starts.RESULTS_DIR
    measured = sorted(p.name for p in root.glob("*") if p.is_dir() and any(p.glob("*/runs.csv"))) if root.exists() else []
    if args.database:
        analyse(args.database)
    elif not args.all:
        parser.error("give --database NAME or --all")

    # -----------------------------------------------------------------
    # results/all_databases.csv — COMPARING VOLUMES
    #
    # Each data volume (6 hours, 1 day, a week...) is its own database
    # (built by build_hours.py) and is measured separately. This file puts
    # the summary lines of ALL of them in one table, with a "database"
    # column, so you can follow e.g. "top group, depth 3" as the volume
    # grows and see where the ratio crosses 1.
    #
    # It's rebuilt every time, even after analysing one single database,
    # so it always reflects the latest measurement of each.
    #
    # The loop body is ONE statement split over three lines by the `\` at
    # the end of the first:
    #     all_rows += (analyse(database)) if args.all else (the same rows,
    #                                                       built silently)
    # With --all, analyse() prints each database's table and writes its
    # files. Otherwise the same summary rows are recomputed quietly (no
    # printing, no per-database files), only to fill all_databases.csv.
    # -----------------------------------------------------------------
    # Always refresh the comparison of all volumes measured so far.
    all_rows = []
    for database in measured:
        all_rows += analyse(database) if args.all else \
            [{"database": database, "measurement": latest_measurement(database).name, **r}
             for r in summary(per_actor(read_runs(latest_measurement(database))))]
    write_csv(all_rows, root / "all_databases.csv")
    if all_rows:
        print(f"Comparison of all {len(measured)} measured database(s): {root / 'all_databases.csv'}")


# The __name__ guard: see docs_english/download_gharchive.py.
if __name__ == "__main__":
    main()
