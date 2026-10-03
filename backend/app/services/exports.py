"""Export jobs: claiming, running and finishing the simulated export of assigned episodes.

A worker never holds a transaction or a row lock while it works:

1. ``claim_next_job`` runs one short transaction. ``FOR UPDATE SKIP LOCKED``
   lets concurrent workers each take a different job without waiting. The job
   is marked running with a lease and the transaction commits at once.
2. ``run_export`` does the slow part with no transaction open.
3. ``finish_job`` runs a second short transaction to record the outcome.

The attempt number returned by the claim is a fencing token. Finishing only
updates the job if it is still running under that same attempt, so finishing
twice, or finishing after the lease expired and another worker took the job
over, changes nothing.

All times come from the database clock, so workers on different machines
always agree on whether a lease has expired.
"""

import random
import time
from typing import NamedTuple

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import config
from app.models import Assignment, DatasetRequest, ExportJob
from app.services.errors import ConflictError

CLAIM = text("""
    SELECT id, attempts, max_attempts, status FROM export_jobs
    WHERE (status = 'pending' AND next_run_at <= now())
       OR (status = 'running' AND locked_until <= now())
    ORDER BY next_run_at, id
    LIMIT 1
    FOR UPDATE SKIP LOCKED
""")
START = text("""
    UPDATE export_jobs
    SET status = 'running', attempts = attempts + 1,
        locked_until = now() + make_interval(secs => :lease), updated_at = now()
    WHERE id = :id
""")
GIVE_UP = text("""
    UPDATE export_jobs
    SET status = 'failed', locked_until = NULL, finished_at = now(), updated_at = now(),
        last_error = 'The worker stopped during the final attempt and its lease expired'
    WHERE id = :id
""")
SUCCEED = text("""
    UPDATE export_jobs
    SET status = 'succeeded', locked_until = NULL, last_error = NULL,
        finished_at = now(), updated_at = now()
    WHERE id = :id AND status = 'running' AND attempts = :attempt
""")
RETRY_LATER = text("""
    UPDATE export_jobs
    SET status = 'pending', locked_until = NULL, last_error = :error, updated_at = now(),
        next_run_at = now() + make_interval(secs => LEAST(:base * power(2, attempts - 1), :cap))
    WHERE id = :id AND status = 'running' AND attempts = :attempt AND attempts < max_attempts
""")
FAIL = text("""
    UPDATE export_jobs
    SET status = 'failed', locked_until = NULL, last_error = :error,
        finished_at = now(), updated_at = now()
    WHERE id = :id AND status = 'running' AND attempts = :attempt AND attempts >= max_attempts
""")


class ClaimedJob(NamedTuple):
    """A job this worker now holds, and the attempt number that proves it."""

    id: int
    attempt: int


class ExportFailedError(Exception):
    """The simulated export failed. The message is stored as the job's last error."""


def claim_next_job(db: Session) -> ClaimedJob | None:
    """Claim the next due job in one short transaction, or return None when none is due.

    A running job whose lease expired on its last allowed attempt is marked
    failed instead of being run again; the search then continues.
    """
    while True:
        row = db.execute(CLAIM).one_or_none()
        if row is None:
            db.commit()
            return None
        if row.status == "running" and row.attempts >= row.max_attempts:
            db.execute(GIVE_UP, {"id": row.id})
            db.commit()
            continue
        db.execute(START, {"id": row.id, "lease": config.EXPORT_LEASE_SECONDS})
        db.commit()
        return ClaimedJob(row.id, row.attempts + 1)


def run_export(job: ClaimedJob) -> None:
    """Simulate the export: wait a few seconds, then fail at the configured rate.

    Raises:
        ExportFailedError: The simulated export failed.
    """
    time.sleep(random.uniform(config.EXPORT_MIN_SECONDS, config.EXPORT_MAX_SECONDS))
    if random.random() < config.EXPORT_FAILURE_RATE:
        raise ExportFailedError(f"Simulated export failure on attempt {job.attempt}")


def finish_job(db: Session, job: ClaimedJob, error: str | None) -> str:
    """Record the outcome of an attempt in one short transaction.

    On success the job is succeeded. On failure it goes back to pending with a
    doubling delay, or becomes failed once it has used every attempt. Nothing
    happens if the job is no longer running under this attempt.

    Returns:
        "succeeded", "retrying", "failed" or "ignored".
    """
    params = {"id": job.id, "attempt": job.attempt}
    if error is None:
        outcome = "succeeded" if db.execute(SUCCEED, params).rowcount else "ignored"
    elif db.execute(
        RETRY_LATER,
        {**params, "error": error, "base": config.EXPORT_BACKOFF_SECONDS, "cap": 300},
    ).rowcount:
        outcome = "retrying"
    else:
        outcome = "failed" if db.execute(FAIL, {**params, "error": error}).rowcount else "ignored"
    db.commit()
    return outcome


def ensure_exports_succeeded(db: Session, request: DatasetRequest) -> None:
    """Entry check for ``delivered``: every assigned episode must have exported.

    Runs under the request row lock in the status change transaction. An
    assignment without a job counts as not exported.

    Raises:
        ConflictError: Some exports have not succeeded yet.
    """
    waiting = db.scalar(
        select(func.count(Assignment.id))
        .outerjoin(ExportJob, ExportJob.assignment_id == Assignment.id)
        .where(Assignment.request_id == request.id)
        .where((ExportJob.status.is_(None)) | (ExportJob.status != "succeeded"))
    )
    if waiting:
        noun = "export has" if waiting == 1 else "exports have"
        raise ConflictError(f"Cannot deliver: {waiting} episode {noun} not succeeded yet")
