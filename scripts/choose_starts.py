"""Choose the starting actors for the measurements, the same on both sides.

For every actor it counts, in PostgreSQL and in Neo4j:
    reached = distinct other actors that share at least one repo with it (one hop)
    repos   = distinct repos it touched
and then picks two groups of 10:

    top     the 10 that reach the most actors in one hop
    median  the 10 whose "reached" is closest to the median, among the actors
            that reach at least one other actor (those that reach nobody are
            only a single JOIN, and tell nothing about traversals)

Ties are broken by more repos, then by the smaller id, so the choice never
changes. Both databases must give exactly the same 20 actors (with the same
numbers); otherwise nothing is saved.

The list is saved to results/<database>/starts.csv. If that file already
exists it's kept, so a measurement repeated another day uses the same actors;
--force chooses them again.

Usage:
    ./run.sh scripts/choose_starts.py --database gharchive-2026-08-27-12-6h
    ./run.sh scripts/choose_starts.py --list-databases
"""

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

import drop_databases
import traversal

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
GROUP_SIZE = 10
FIELDS = ["group", "rank", "actor_id", "login", "reached", "repos"]


def ranking_key(actor: dict) -> tuple:
    # Most reached first; ties: more repos first; then the smaller id.
    return (-actor["reached"], -actor["repos"], actor["actor_id"])


def pick_top(actors: list[dict], size: int = GROUP_SIZE) -> list[dict]:
    return sorted(actors, key=ranking_key)[:size]


def pick_median(actors: list[dict], exclude: set[int], size: int = GROUP_SIZE) -> list[dict]:
    # Only actors that reach someone; the median of their "reached"; then the closest ones,
    # with the same tie-break. Actors already in the top group are left out.
    reaching = [a for a in actors if a["reached"] >= 1]
    if not reaching:
        return []
    median = statistics.median(a["reached"] for a in reaching)
    candidates = [a for a in reaching if a["actor_id"] not in exclude]
    return sorted(candidates, key=lambda a: (abs(a["reached"] - median),) + ranking_key(a))[:size]


def choose(actors: list[dict]) -> list[dict]:
    top = pick_top(actors)
    median = pick_median(actors, exclude={a["actor_id"] for a in top})
    rows = []
    for group, members in (("top", top), ("median", median)):
        for rank, actor in enumerate(members, start=1):
            rows.append({"group": group, "rank": rank, **{k: actor[k] for k in ("actor_id", "login", "reached", "repos")}})
    return rows


def postgres_actors(database: str) -> list[dict]:
    with traversal.connect_postgres(database) as conn:
        rows = conn.execute(traversal.SQL_ONE_HOP).fetchall()
    return [{"actor_id": r[0], "login": r[1], "reached": r[2], "repos": r[3]} for r in rows]


def neo4j_actors(database: str) -> list[dict]:
    with traversal.connect_neo4j() as driver:
        records = driver.execute_query(traversal.CYPHER_ONE_HOP, database_=database).records
    return [dict(r) for r in records]


def existing_databases() -> list[str]:
    # Project databases that exist on BOTH servers (the only ones that can be measured).
    with traversal.connect_neo4j() as driver:
        in_neo4j = set(drop_databases.neo4j_databases(driver))
    return [name for name in drop_databases.postgres_databases() if name in in_neo4j]


def save(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", help="The database to choose the actors in (same name on both sides)")
    parser.add_argument("--force", action="store_true", help="Choose again even if starts.csv already exists")
    parser.add_argument("--list-databases", action="store_true",
                        help="Only print the project databases that exist on both servers, one per line")
    args = parser.parse_args()

    if args.list_databases:
        print("\n".join(existing_databases()))
        return
    if not args.database:
        parser.error("--database is required")

    path = RESULTS_DIR / args.database / "starts.csv"
    if path.exists() and not args.force:
        print(f"The starting actors for \"{args.database}\" were already chosen: {path}")
        print("They're kept, so this measurement uses the same actors (use --force to choose again).")
        return

    print(f'Counting, for every actor of "{args.database}", how many actors it reaches in one hop ...')
    begin = time.perf_counter()
    in_postgres = choose(postgres_actors(args.database))
    print(f"PostgreSQL done in {time.perf_counter() - begin:.1f} s.")
    begin = time.perf_counter()
    in_neo4j = choose(neo4j_actors(args.database))
    print(f"Neo4j done in {time.perf_counter() - begin:.1f} s.")

    if in_postgres != in_neo4j:
        print("\nThe two databases DON'T choose the same actors; nothing was saved.")
        for p, n in zip(in_postgres, in_neo4j):
            if p != n:
                print(f"  PostgreSQL {p}\n  Neo4j      {n}")
        sys.exit(1)

    print(f"\nBoth databases choose the same {len(in_postgres)} actors:")
    print(f"  {'group':<7} {'rank':>4} {'actor_id':>12} {'reached':>8} {'repos':>6}  login")
    for row in in_postgres:
        print(f"  {row['group']:<7} {row['rank']:>4} {row['actor_id']:>12} {row['reached']:>8} {row['repos']:>6}  {row['login']}")
    save(in_postgres, path)
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
