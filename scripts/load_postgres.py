"""Load the extracted CSV files into the PostgreSQL "gharchive" database.

Creates (or re-creates) the three benchmark tables and fills them from the CSV
files written by extract_csv.py:

    actor        (id PRIMARY KEY, login)
    repo         (id PRIMARY KEY, name)
    actor_repo   (actor_id -> actor.id, repo_id -> repo.id,
                  PRIMARY KEY (actor_id, repo_id)), plus an index on repo_id

Every run starts from empty tables, so running it twice gives the same result.
At the end it checks that each table has exactly as many rows as its CSV file.

Usage:
    ./run.sh scripts/load_postgres.py
    ./run.sh scripts/load_postgres.py --csv-dir data/csv
"""

import argparse
import sys
import time
from pathlib import Path

import psycopg

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "data" / "csv"
POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}

# Dropped child-first (actor_repo points at actor and repo), created parent-first.
SCHEMA = """
DROP TABLE IF EXISTS actor_repo;
DROP TABLE IF EXISTS repo;
DROP TABLE IF EXISTS actor;

CREATE TABLE actor (
    id    BIGINT PRIMARY KEY,
    login TEXT   NOT NULL
);

CREATE TABLE repo (
    id   BIGINT PRIMARY KEY,
    name TEXT   NOT NULL
);

CREATE TABLE actor_repo (
    actor_id BIGINT NOT NULL REFERENCES actor (id),
    repo_id  BIGINT NOT NULL REFERENCES repo (id),
    PRIMARY KEY (actor_id, repo_id)
);

-- The primary key already finds an actor's repos quickly (actor_id comes first).
-- This index does the same in the other direction: a repo's actors.
CREATE INDEX actor_repo_repo_id_idx ON actor_repo (repo_id);
"""

# (table, columns, CSV file) in load order: parents before actor_repo.
TABLES = [
    ("actor", "id, login", "actors.csv"),
    ("repo", "id, name", "repos.csv"),
    ("actor_repo", "actor_id, repo_id", "actor_repo.csv"),
]


def count_csv_rows(path: Path) -> int:
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # minus the header line


def copy_csv(cur: psycopg.Cursor, table: str, columns: str, path: Path) -> None:
    # COPY ... FROM STDIN: Python sends the file's contents over the connection,
    # so the PostgreSQL server never needs access to the file itself.
    with open(path, "r", encoding="utf-8") as f, \
         cur.copy(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
        while chunk := f.read(1024 * 1024):
            copy.write(chunk)


def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:6.2f} s"


def load(csv_dir: Path) -> bool:
    all_match = True
    with psycopg.connect(**POSTGRES_SETTINGS) as conn:
        with conn.cursor() as cur:
            load_start = time.perf_counter()

            step = time.perf_counter()
            cur.execute(SCHEMA)
            print(f"Tables created: actor, repo, actor_repo        {seconds_since(step)}")

            for table, columns, csv_name in TABLES:
                step = time.perf_counter()
                copy_csv(cur, table, columns, csv_dir / csv_name)
                print(f"Loaded {table:<12} from {csv_name:<16}  {seconds_since(step)}")

            # Refresh the planner's statistics so queries are planned on the real data.
            step = time.perf_counter()
            cur.execute("ANALYZE actor; ANALYZE repo; ANALYZE actor_repo;")
            print(f"Statistics refreshed (ANALYZE)                 {seconds_since(step)}")

            # Commit here, so the total covers saving the data but not the checks below.
            conn.commit()
            print(f"Total load time                                {seconds_since(load_start)}")

            print("\nRows loaded (database vs. CSV file):")
            for table, _, csv_name in TABLES:
                in_db = cur.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                in_csv = count_csv_rows(csv_dir / csv_name)
                status = "OK" if in_db == in_csv else "MISMATCH"
                all_match = all_match and in_db == in_csv
                print(f"  {table:<12} {in_db:>7}   {csv_name:<16} {in_csv:>7}   {status}")
    return all_match


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR,
                         help=f"Folder with the CSV files from extract_csv.py (default: {DEFAULT_CSV_DIR})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not load(args.csv_dir):
        sys.exit("Some row counts don't match their CSV file.")
    print("\nPostgreSQL load complete.")


if __name__ == "__main__":
    main()
