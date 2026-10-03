"""Export worker: ``python -m app.worker``.

Runs as its own docker compose service from the same image as the API. It
loops: claim a due job, run the simulated export outside any transaction,
record the outcome, and wait ``EXPORT_POLL_SECONDS`` when nothing is due.
Several workers can run at once (``docker compose up --scale worker=3``);
``SKIP LOCKED`` keeps them on different jobs.

On SIGTERM, as sent by ``docker compose stop``, it finishes the job it holds
and then exits, so a normal shutdown never leaves a job waiting for its lease.
"""

import logging
import signal
import sys
import threading

from app import config
from app.db import SessionLocal
from app.request_logging import JsonFormatter
from app.services.exports import ExportFailedError, claim_next_job, finish_job, run_export

logger = logging.getLogger("handoff.worker")
stopping = threading.Event()


def configure_logging() -> None:
    """Log one JSON line per event to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log(event: str, **fields: object) -> None:
    """Write one structured log line."""
    logger.info(event, extra={"fields": {"event": event, **fields}})


def work_once() -> bool:
    """Claim and process one job. Returns False when no job was due."""
    with SessionLocal() as db:
        job = claim_next_job(db)
    if job is None:
        return False
    log("export_started", job_id=job.id, attempt=job.attempt)
    try:
        run_export(job)
        error = None
    except ExportFailedError as exc:
        error = str(exc)
    with SessionLocal() as db:
        outcome = finish_job(db, job, error)
    log("export_finished", job_id=job.id, attempt=job.attempt, outcome=outcome, error=error)
    return True


def main() -> None:
    """Process jobs until asked to stop."""
    configure_logging()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    log("worker_started", lease_seconds=config.EXPORT_LEASE_SECONDS)
    while not stopping.is_set():
        try:
            if not work_once():
                stopping.wait(config.EXPORT_POLL_SECONDS)
        except Exception:
            logger.exception("worker_error")
            stopping.wait(config.EXPORT_POLL_SECONDS)
    log("worker_stopped")


if __name__ == "__main__":
    main()
