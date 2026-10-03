"""Reading export status for a request, and sending a failed export back to the queue."""

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Assignment, Episode, ExportJob, User
from app.normalise import normalise_episode_id
from app.schemas import ExportJobOut, ExportListOut
from app.services.errors import ConflictError, NotFoundError
from app.services.requests import get_request

FINISHED = ("succeeded", "failed")
RETRY = text("""
    UPDATE export_jobs
    SET status = 'pending', attempts = 0, next_run_at = now(), last_error = NULL,
        finished_at = NULL, updated_at = now()
    WHERE id = :id AND status = 'failed'
""")


def list_exports(db: Session, user: User, request_id: int) -> ExportListOut:
    """Return the export status of every episode assigned to a request, by episode id.

    ``finished`` is decided here, so a client polling this endpoint stops when
    the server says there is nothing left to wait for.

    Raises:
        NotFoundError: The request does not exist or is not visible to the user.
    """
    get_request(db, user, request_id)
    rows = db.execute(
        select(Episode.episode_id, ExportJob)
        .join(Assignment, Assignment.episode_id == Episode.id)
        .join(ExportJob, ExportJob.assignment_id == Assignment.id)
        .where(Assignment.request_id == request_id)
        .order_by(Episode.episode_id)
    ).all()
    jobs = [
        ExportJobOut(
            episode_id=episode_id,
            status=job.status,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            last_error=job.last_error,
        )
        for episode_id, job in rows
    ]
    return ExportListOut(jobs=jobs, finished=all(job.status in FINISHED for job in jobs))


def retry_export(db: Session, user: User, request_id: int, episode_id: str) -> None:
    """Send a failed export back to the queue with a fresh set of attempts.

    The update only applies to a job that is still failed, so two operators
    pressing retry at once queue it once.

    Raises:
        NotFoundError: The episode is not assigned to this request.
        ConflictError: The export has not failed.
    """
    get_request(db, user, request_id)
    job_id = db.scalar(
        select(ExportJob.id)
        .join(Assignment, Assignment.id == ExportJob.assignment_id)
        .join(Episode, Episode.id == Assignment.episode_id)
        .where(
            Assignment.request_id == request_id,
            Episode.episode_id == normalise_episode_id(episode_id),
        )
    )
    if job_id is None:
        raise NotFoundError(f"Episode {episode_id} is not assigned to request {request_id}")
    if not db.execute(RETRY, {"id": job_id}).rowcount:
        db.rollback()
        raise ConflictError("Only failed exports can be retried")
    db.commit()
