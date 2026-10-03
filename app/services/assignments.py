"""Assigning episodes to requests and removing them again.

Assignments change only while a request is ``in_progress``. Every change locks
the request row first, the same lock a status change takes, so the delivered
check always counts a stable set of assignments.

A bulk assignment is all or nothing: if any episode fails a rule, none are
assigned and the error lists every failing episode.
"""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Assignment, Episode, User
from app.schemas import AssignmentOut
from app.services.episodes import ASSIGNABLE_QUALITIES
from app.services.errors import ConflictError, NotFoundError, violated_constraint
from app.services.requests import get_request

ASSIGNABLE_STATUSES = ("in_progress",)
EPISODE_UNIQUE_CONSTRAINT = "uq_assignments_episode_id"


def assign_episodes(
    db: Session, user: User, request_id: int, episode_ids: list[str]
) -> AssignmentOut:
    """Assign episodes to a request in one transaction.

    Rules are checked in this order: the request exists, every episode exists,
    every episode is good or usable, no episode is already assigned, and the
    request is in a status that accepts assignments. The UNIQUE constraint on
    ``assignments.episode_id`` is the final guard against a concurrent
    assignment of the same episode.

    Args:
        db: Database session.
        user: Operator or admin making the assignment.
        request_id: Id of the request.
        episode_ids: CSV episode ids, already normalised and without repeats.

    Returns:
        The episodes assigned and the request's new assigned count.

    Raises:
        NotFoundError: The request or one of the episodes does not exist.
        ConflictError: An episode has bad quality or is already assigned, or the
            request does not accept assignments in its current status.
    """
    request = get_request(db, user, request_id, lock=True)
    episodes = load_episodes(db, episode_ids)
    missing = [episode_id for episode_id in episode_ids if episode_id not in episodes]
    if missing:
        raise NotFoundError(f"Episodes not found: {', '.join(missing)}")
    bad = [e.episode_id for e in episodes.values() if e.quality not in ASSIGNABLE_QUALITIES]
    if bad:
        raise ConflictError(f"Only good or usable episodes can be assigned: {', '.join(bad)}")
    taken = assigned_elsewhere(db, [episode.id for episode in episodes.values()])
    if taken:
        raise ConflictError(already_assigned_message(taken))
    if request.status not in ASSIGNABLE_STATUSES:
        raise ConflictError(
            f"Episodes can only be assigned while a request is in_progress, not {request.status}"
        )
    rows = [
        {"episode_id": episode.id, "request_id": request.id, "assigned_by_id": user.id}
        for episode in episodes.values()
    ]
    try:
        db.execute(insert(Assignment).values(rows))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if violated_constraint(exc) != EPISODE_UNIQUE_CONSTRAINT:
            raise
        taken = assigned_elsewhere(db, [episode.id for episode in episodes.values()])
        raise ConflictError(already_assigned_message(taken)) from exc
    db.refresh(request)
    return AssignmentOut(
        request_id=request.id,
        assigned=list(episodes),
        assigned_count=request.assigned_count,
        episodes_requested=request.episodes_requested,
    )


def unassign_episode(db: Session, user: User, request_id: int, episode_id: str) -> None:
    """Remove one episode from a request while the request is in_progress.

    Raises:
        NotFoundError: The request does not exist, or the episode is not
            assigned to it.
        ConflictError: The request is not in_progress.
    """
    request = get_request(db, user, request_id, lock=True)
    episode = db.scalar(select(Episode).where(Episode.episode_id == episode_id.strip().upper()))
    assignment = None
    if episode:
        assignment = db.scalar(
            select(Assignment).where(
                Assignment.episode_id == episode.id, Assignment.request_id == request.id
            )
        )
    if assignment is None:
        raise NotFoundError(f"Episode {episode_id} is not assigned to request {request.id}")
    if request.status not in ASSIGNABLE_STATUSES:
        raise ConflictError(
            f"Episodes can only be unassigned while a request is in_progress, not {request.status}"
        )
    db.execute(delete(Assignment).where(Assignment.id == assignment.id))
    db.commit()


def load_episodes(db: Session, episode_ids: list[str]) -> dict[str, Episode]:
    """Return the episodes with these CSV ids, keyed by id, in the order given."""
    found = {
        e.episode_id: e
        for e in db.scalars(select(Episode).where(Episode.episode_id.in_(episode_ids)))
    }
    return {episode_id: found[episode_id] for episode_id in episode_ids if episode_id in found}


def assigned_elsewhere(db: Session, episode_pks: list[int]) -> dict[str, int]:
    """Return the episodes among these that are already assigned, mapped to their request id."""
    rows = db.execute(
        select(Episode.episode_id, Assignment.request_id)
        .join(Assignment, Assignment.episode_id == Episode.id)
        .where(Episode.id.in_(episode_pks))
    )
    return dict(rows.tuples().all())


def already_assigned_message(taken: dict[str, int]) -> str:
    """Describe episodes that are already assigned, for example ``EP-00001 (request 3)``."""
    listed = ", ".join(
        f"{episode_id} (request {request_id})" for episode_id, request_id in taken.items()
    )
    return f"Episodes already assigned to a request: {listed}"
