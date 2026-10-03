"""Export jobs: claiming, retries, lease expiry, completion, job creation and delivery."""

import pytest
from sqlalchemy import func, select, text

from app import config
from app.db import SessionLocal
from app.models import DatasetRequest, ExportJob
from app.services.exports import CLAIM, claim_next_job, finish_job, run_export
from tests.conftest import set_status, status_of


@pytest.fixture(autouse=True)
def fast_exports(monkeypatch):
    """No sleeping and no backoff, so every outcome is decided by the test."""
    monkeypatch.setattr(config, "EXPORT_MIN_SECONDS", 0)
    monkeypatch.setattr(config, "EXPORT_MAX_SECONDS", 0)
    monkeypatch.setattr(config, "EXPORT_BACKOFF_SECONDS", 0)


@pytest.fixture
def queue_jobs(operator, make_request, make_episodes, db):
    """Assign episodes through the API, which creates one pending job each."""

    def create(count: int = 1) -> list[int]:
        request_id = make_request(episodes_requested=count)
        set_status(db, request_id, "in_progress")
        response = operator.post(
            f"/requests/{request_id}/assignments", json={"episode_ids": make_episodes(count=count)}
        )
        assert response.status_code == 201, response.text
        return list(db.scalars(select(ExportJob.id).order_by(ExportJob.id)))

    return create


def job(db, job_id):
    db.expire_all()
    return db.get(ExportJob, job_id)


def claim():
    with SessionLocal() as session:
        return claim_next_job(session)


def finish(claimed, error=None):
    with SessionLocal() as session:
        return finish_job(session, claimed, error)


def test_two_workers_claiming_at_once_never_get_the_same_job(queue_jobs):
    queue_jobs(count=3)
    with SessionLocal() as worker_a:
        held = worker_a.execute(CLAIM).one()
        with SessionLocal() as worker_b:
            worker_b.execute(text("SET lock_timeout = '2s'"))
            claimed_by_b = claim_next_job(worker_b)
        worker_a.rollback()
    assert claimed_by_b is not None
    assert claimed_by_b.id != held.id


def test_a_job_that_keeps_failing_ends_failed_after_max_attempts(queue_jobs, monkeypatch, db):
    monkeypatch.setattr(config, "EXPORT_FAILURE_RATE", 1)
    (job_id,) = queue_jobs()
    max_attempts = job(db, job_id).max_attempts
    for attempt in range(1, max_attempts + 1):
        claimed = claim()
        assert claimed.attempt == attempt
        with pytest.raises(Exception) as failure:
            run_export(claimed)
        outcome = finish(claimed, str(failure.value))
        expected = "failed" if attempt == max_attempts else "retrying"
        assert outcome == expected
        assert job(db, job_id).status == ("failed" if expected == "failed" else "pending")
    assert job(db, job_id).attempts == max_attempts
    assert claim() is None


def test_a_job_stuck_in_running_with_an_expired_lease_is_reclaimed(queue_jobs, db):
    (job_id,) = queue_jobs()
    first = claim()
    assert claim() is None
    db.execute(text("UPDATE export_jobs SET locked_until = now() - interval '1 second'"))
    db.commit()
    second = claim()
    assert (second.id, second.attempt) == (job_id, 2)
    assert finish(first) == "ignored"
    assert finish(second) == "succeeded"


def test_completing_a_succeeded_job_again_changes_nothing(queue_jobs, db):
    (job_id,) = queue_jobs()
    claimed = claim()
    assert finish(claimed) == "succeeded"
    before = job(db, job_id)
    snapshot = (before.status, before.attempts, before.finished_at, before.updated_at)
    assert finish(claimed) == "ignored"
    after = job(db, job_id)
    assert (after.status, after.attempts, after.finished_at, after.updated_at) == snapshot


def test_assigning_creates_one_job_and_a_refused_duplicate_creates_none(
    operator, make_request, make_episodes, db
):
    first, second = make_request(), make_request()
    for request_id in (first, second):
        set_status(db, request_id, "in_progress")
    episode_ids = make_episodes()
    assert (
        operator.post(
            f"/requests/{first}/assignments", json={"episode_ids": episode_ids}
        ).status_code
        == 201
    )
    assert db.scalar(select(func.count(ExportJob.id))) == 1
    assert (
        operator.post(
            f"/requests/{second}/assignments", json={"episode_ids": episode_ids}
        ).status_code
        == 409
    )
    assert db.scalar(select(func.count(ExportJob.id))) == 1


def test_delivery_waits_until_every_export_has_succeeded(operator, queue_jobs, db):
    queue_jobs()
    request_id = db.scalar(select(DatasetRequest.id))

    def deliver():
        return operator.post(f"/requests/{request_id}/transitions", json={"to_status": "delivered"})

    response = deliver()
    assert response.status_code == 409
    assert response.json()["detail"] == "Cannot deliver: 1 episode export has not succeeded yet"
    assert status_of(db, request_id) == "in_progress"

    assert finish(claim()) == "succeeded"
    assert deliver().status_code == 200
    assert status_of(db, request_id) == "delivered"
