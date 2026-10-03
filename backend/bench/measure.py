"""Measure the CSV import and the analytics queries at volume.

Run with ``docker compose run --rm --build bench``. Everything happens in a
separate database, ``handoff_bench``, which is dropped and recreated first.

Steps:
    1. Import a generated CSV of ``--import-rows`` episodes (the brief's
       generator) and time it, then import the same file again.
    2. Add synthetic requests and status history, so the request queries have
       something to measure.
    3. For each episode count in ``--sizes``, top the table up with rows
       generated in SQL (same distribution as the generator) and run every
       analytics query with EXPLAIN (ANALYZE, BUFFERS), with the current
       indexes and with each index removed inside a rolled-back transaction.

Every printed number is measured on the machine that runs this script.
"""

import argparse
import os
import resource
import statistics
import subprocess
import sys
import time
from datetime import date

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url

from app.db import SessionLocal, engine
from app.seed import seed
from app.services import analytics
from app.services.episode_import import import_episodes

RANGES = {
    "1 month": (date(2026, 3, 1), date(2026, 3, 31)),
    "3 months": (date(2026, 1, 1), date(2026, 3, 31)),
    "12 months": (date(2025, 9, 1), date(2026, 8, 31)),
}
INDEX_VARIANTS = {
    "current indexes": [],
    "without (recorded_at, robot_id)": ["ix_episodes_recorded_at_robot_id"],
    "without partial good index": ["ix_episodes_good_recorded_at_task_name"],
    "without (task_name, quality)": ["ix_episodes_task_name_quality"],
    "no recorded_at index at all": [
        "ix_episodes_recorded_at_robot_id",
        "ix_episodes_good_recorded_at_task_name",
    ],
}
SYNTHETIC_EPISODES = """
INSERT INTO episodes (episode_id, robot_id, task_name, recorded_at, duration_seconds,
                      operator_name, quality)
SELECT 'EP-S' || lpad(g::text, 9, '0'),
       (ARRAY['arm-01','arm-02','arm-03','mobile-01','humanoid-01'])[1 + floor(random() * 5)::int],
       (ARRAY['pick cup','place cup on shelf','open drawer','fold towel','pour water',
              'stack blocks','wipe table'])[1 + floor(random() * 7)::int],
       timestamptz '2025-09-01 08:00+00' + random() * interval '365 days',
       8 + floor(random() * 113)::int,
       (ARRAY['Aline','Eric','Diane','Patrick','Jeanne','Kevin'])[1 + floor(random() * 6)::int],
       (ARRAY['good','good','good','good','good','good','usable','usable','usable','bad'])
           [1 + floor(random() * 10)::int]
FROM generate_series(CAST(:first AS integer), CAST(:last AS integer)) AS g
"""
SYNTHETIC_REQUESTS = """
INSERT INTO requests (client_id, task_name, episodes_requested, deadline, status, created_at)
SELECT (SELECT id FROM users WHERE email = 'client-a@example.com'), 'pick cup', 10,
       date '2027-01-01',
       (ARRAY['submitted','in_progress','delivered','accepted','rejected'])
           [1 + floor(random() * 5)::int],
       timestamptz '2025-09-01 08:00+00' + random() * interval '365 days'
FROM generate_series(1, CAST(:count AS integer));
INSERT INTO status_history (request_id, from_status, to_status, changed_by_id, changed_by_role,
                            changed_at)
SELECT id, NULL, 'submitted', client_id, 'client', created_at FROM requests;
INSERT INTO status_history (request_id, from_status, to_status, changed_by_id, changed_by_role,
                            changed_at)
SELECT id, 'in_progress', 'delivered',
       (SELECT id FROM users WHERE email = 'ops1@example.com'), 'operator',
       created_at + random() * interval '30 days'
FROM requests WHERE status IN ('delivered', 'accepted', 'rejected');
"""


def peak_memory_mb() -> float:
    """Peak resident memory of this process so far, in megabytes (Linux reports kilobytes)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def recreate_database() -> None:
    """Drop and recreate the database named in DATABASE_URL, which must end in _bench."""
    url = make_url(os.environ["DATABASE_URL"])
    if not url.database.endswith("_bench"):
        raise SystemExit(f"Refusing to use {url.database!r}: the name must end in _bench")
    server = url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(server.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{url.database}"')
    command.upgrade(Config("alembic.ini"), "head")
    with SessionLocal() as session:
        seed(session)


def episode_count() -> int:
    """Number of episodes stored."""
    with engine.connect() as connection:
        return connection.scalar(text("SELECT count(*) FROM episodes"))


def measure_import(rows: int) -> None:
    """Generate a CSV with the brief's generator, import it twice and print timings."""
    path = f"/tmp/episodes_{rows}.csv"
    with open(path, "w") as out:
        subprocess.run(
            [sys.executable, "bench/generate_episodes.py", str(rows)], stdout=out, check=True
        )
    print(f"\n## Import of {rows:,} generated rows\n")
    print("| Run | Imported | Duplicates | Seconds | Rows/s | Peak memory MB | Episodes after |")
    print("|---|---|---|---|---|---|---|")
    for run in ("first", "second"):
        started = time.perf_counter()
        with open(path, encoding="utf-8", newline="") as csv_file, SessionLocal() as db:
            report = import_episodes(db, csv_file)
        seconds = time.perf_counter() - started
        print(
            f"| {run} | {report.imported:,} | {report.duplicates:,} | {seconds:.1f} | "
            f"{rows / seconds:,.0f} | {peak_memory_mb():.0f} | {episode_count():,} |"
        )


def grow_episodes(target: int) -> None:
    """Add synthetic episodes in SQL until the table holds ``target`` rows, then vacuum."""
    current = episode_count()
    if target > current:
        with engine.begin() as connection:
            connection.execute(text(SYNTHETIC_EPISODES), {"first": current + 1, "last": target})
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("VACUUM ANALYZE episodes"))


def add_requests(count: int) -> None:
    """Add synthetic requests with their history, then analyze."""
    with engine.begin() as connection:
        for statement in SYNTHETIC_REQUESTS.split(";"):
            if statement.strip():
                connection.execute(text(statement), {"count": count})
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("VACUUM ANALYZE requests, status_history"))


def explain(query: object, drop: list[str], repeats: int = 3) -> dict:
    """Run EXPLAIN (ANALYZE, BUFFERS) a few times with some indexes dropped, then roll back.

    Returns the median execution time, the scan used on the main table, the
    planner's row estimate against the actual rows, and buffers hit and read.
    """
    sql = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    times, plan = [], None
    with engine.connect() as connection:
        transaction = connection.begin()
        for index in drop:
            connection.execute(text(f"DROP INDEX {index}"))
        for _ in range(repeats):
            result = connection.execute(text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"))
            plan = result.scalar()[0]
            times.append(plan["Execution Time"])
        transaction.rollback()
    scan = deepest_scan(plan["Plan"])
    return {
        "ms": statistics.median(times),
        "scan": f"{scan['Node Type']}"
        + (f" ({scan['Index Name']})" if "Index Name" in scan else ""),
        "estimated": scan["Plan Rows"],
        "actual": scan["Actual Rows"] * scan.get("Actual Loops", 1),
        "hit": plan["Plan"].get("Shared Hit Blocks", 0),
        "read": plan["Plan"].get("Shared Read Blocks", 0),
    }


def deepest_scan(node: dict) -> dict:
    """Return the first scan node under ``node``: the step that reads the table or index."""
    if "Scan" in node["Node Type"]:
        return node
    for child in node.get("Plans", []):
        found = deepest_scan(child)
        if found:
            return found
    return {}


def print_query_table(size: int) -> None:
    """Print one row per query, range and index variant at the current table size."""
    print(f"\n## Analytics at {size:,} episodes\n")
    print("| Query | Range | Indexes | Scan | Est. rows | Actual rows | Median ms | Hit/read |")
    print("|---|---|---|---|---|---|---|---|")
    queries = {
        "per day per robot": (analytics.episodes_per_day_query, INDEX_VARIANTS),
        "top 5 tasks": (analytics.top_tasks_query, INDEX_VARIANTS),
        "requests by status": (analytics.requests_by_status_query, {"current indexes": []}),
        "median to delivery": (analytics.median_delivery_query, {"current indexes": []}),
    }
    for name, (build, variants) in queries.items():
        for label, (first, last) in RANGES.items():
            start, end = analytics.day_bounds(first, last)
            for variant, drop in variants.items():
                r = explain(build(start, end), drop)
                print(
                    f"| {name} | {label} | {variant} | {r['scan']} | {r['estimated']:,} | "
                    f"{r['actual']:,} | {r['ms']:.1f} | {r['hit']:,}/{r['read']:,} |"
                )


def main() -> None:
    """Parse the arguments and run every measurement."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--import-rows", type=int, default=200_000)
    parser.add_argument("--requests", type=int, default=20_000)
    parser.add_argument("--sizes", type=int, nargs="+", default=[200_000, 1_000_000, 5_000_000])
    args = parser.parse_args()
    recreate_database()
    measure_import(args.import_rows)
    add_requests(args.requests)
    print(f"\nAdded {args.requests:,} synthetic requests with their status history.")
    for size in args.sizes:
        started = time.perf_counter()
        grow_episodes(size)
        print(f"\n(grew to {episode_count():,} episodes in {time.perf_counter() - started:.0f} s)")
        print_query_table(size)


if __name__ == "__main__":
    main()
