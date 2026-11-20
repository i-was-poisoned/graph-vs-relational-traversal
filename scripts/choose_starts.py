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
numbers); otherwise the measurement doesn't start.

measure.py uses choose_in_both(). The chosen actors are saved in the
"Starting actors" sheet of the measurement's Excel file in results/, so a
measurement repeated another day reuses them.

Usage (only to list the databases that can be measured; research.sh uses it):
    ./run.sh scripts/choose_starts.py --list-databases
"""

import argparse
import statistics
import time

import drop_databases
import traversal

GROUP_SIZE = 10


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


def choose_in_both(database: str) -> list[dict]:
    # The same choice made in each database; they must agree, or nothing is measured.
    print(f'Choosing the starting actors: counting, for every actor of "{database}", '
          "how many actors it reaches in one hop ...")
    begin = time.perf_counter()
    in_postgres = choose(postgres_actors(database))
    print(f"  PostgreSQL done in {time.perf_counter() - begin:.1f} s.")
    begin = time.perf_counter()
    in_neo4j = choose(neo4j_actors(database))
    print(f"  Neo4j done in {time.perf_counter() - begin:.1f} s.")
    if in_postgres != in_neo4j:
        differences = [f"  PostgreSQL {p}\n  Neo4j      {n}" for p, n in zip(in_postgres, in_neo4j) if p != n]
        raise RuntimeError("The two databases DON'T choose the same actors; nothing was measured.\n"
                           + "\n".join(differences))
    return in_postgres


def existing_databases() -> list[str]:
    # Project databases that exist on BOTH servers (the only ones that can be measured).
    with traversal.connect_neo4j() as driver:
        in_neo4j = set(drop_databases.neo4j_databases(driver))
    return [name for name in drop_databases.postgres_databases() if name in in_neo4j]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list-databases", action="store_true",
                        help="Print the project databases that exist on both servers, one per line")
    args = parser.parse_args()
    if not args.list_databases:
        parser.error("the only option is --list-databases (measure.py chooses the actors)")
    print("\n".join(existing_databases()))


if __name__ == "__main__":
    main()
