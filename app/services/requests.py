"""Dataset requests and their status workflow.

Every allowed status change is listed once in ``TRANSITIONS``. A change is
applied only if it appears there and the user's role is allowed for it. The
status update and its history row are written in the same transaction, with
the request row locked so that two changes cannot run at the same time.
"""

from collections.abc import Callable
from typing import NamedTuple

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import DatasetRequest, StatusHistory, User
from app.schemas import RequestCreate
from app.services.errors import ConflictError, NotFoundError, PermissionDeniedError

STAFF = frozenset({"operator", "admin"})
CLIENT = frozenset({"client"})


class Transition(NamedTuple):
    """One allowed status change and the roles that may make it."""

    from_status: str
    to_status: str
    roles: frozenset[str]


TRANSITIONS = (
    Transition("submitted", "in_progress", STAFF),
    Transition("in_progress", "delivered", STAFF),
    Transition("delivered", "accepted", CLIENT),
    Transition("delivered", "rejected", CLIENT),
    Transition("rejected", "in_progress", STAFF),
)
TRANSITION_TABLE = {(t.from_status, t.to_status): t for t in TRANSITIONS}


def create_request(db: Session, client: User, data: RequestCreate) -> DatasetRequest:
    """Create a request in ``submitted`` status, together with its first history row.

    Args:
        db: Database session.
        client: Client who owns the request.
        data: Validated request fields.

    Returns:
        The new request.
    """
    request = DatasetRequest(
        client_id=client.id,
        task_name=data.task_name,
        episodes_requested=data.episodes_requested,
        deadline=data.deadline,
        notes=data.notes,
        status="submitted",
    )
    db.add(request)
    db.flush()
    db.add(record_change(request, None, "submitted", client))
    db.commit()
    db.refresh(request)
    return request


def visible_requests(user: User) -> Select[tuple[DatasetRequest]]:
    """Return a query for the requests this user may see.

    Clients see only their own requests. Operators and admins see all of them.
    Every read goes through this query, so a client can never load another
    client's request by guessing its id.
    """
    query = select(DatasetRequest)
    if user.role == "client":
        query = query.where(DatasetRequest.client_id == user.id)
    return query


def list_requests(db: Session, user: User, status: str | None = None) -> list[DatasetRequest]:
    """Return the visible requests, newest first, optionally filtered by status."""
    query = visible_requests(user)
    if status:
        query = query.where(DatasetRequest.status == status)
    query = query.order_by(DatasetRequest.created_at.desc(), DatasetRequest.id.desc())
    return list(db.scalars(query))


def get_request(db: Session, user: User, request_id: int, lock: bool = False) -> DatasetRequest:
    """Return one visible request.

    Args:
        db: Database session.
        user: User asking for the request.
        request_id: Id of the request.
        lock: Lock the row with ``SELECT ... FOR UPDATE`` until the transaction ends.

    Raises:
        NotFoundError: The request does not exist or belongs to another client.
    """
    query = visible_requests(user).where(DatasetRequest.id == request_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    request = db.scalar(query)
    if request is None:
        raise NotFoundError("Request not found")
    return request


def change_status(db: Session, user: User, request_id: int, to_status: str) -> DatasetRequest:
    """Move a request to a new status and record who did it.

    The request row is locked first, so a second change to the same request
    waits for this one to commit and is then checked against the new status.

    Args:
        db: Database session.
        user: User making the change.
        request_id: Id of the request.
        to_status: Status to move to.

    Returns:
        The updated request.

    Raises:
        NotFoundError: The request does not exist or belongs to another client.
        ConflictError: The change is not allowed from the current status, or an
            entry check for the new status failed.
        PermissionDeniedError: The user's role may not make this change.
    """
    request = get_request(db, user, request_id, lock=True)
    from_status = request.status
    transition = TRANSITION_TABLE.get((from_status, to_status))
    if transition is None:
        raise ConflictError(not_allowed_message(from_status, to_status))
    if user.role not in transition.roles:
        roles = " or ".join(sorted(transition.roles))
        raise PermissionDeniedError(
            f"Only {roles} users can move a request from {from_status} to {to_status}"
        )
    entry_check = ENTRY_CHECKS.get(to_status)
    if entry_check:
        entry_check(db, request)
    request.status = to_status
    db.add(record_change(request, from_status, to_status, user))
    db.commit()
    db.refresh(request)
    return request


def record_change(
    request: DatasetRequest, from_status: str | None, to_status: str, user: User
) -> StatusHistory:
    """Build the history row for a status change. The caller adds and commits it."""
    return StatusHistory(
        request_id=request.id,
        from_status=from_status,
        to_status=to_status,
        changed_by_id=user.id,
    )


def not_allowed_message(from_status: str, to_status: str) -> str:
    """Explain a refused change and list the statuses reachable from the current one."""
    allowed = [t.to_status for t in TRANSITIONS if t.from_status == from_status]
    if not allowed:
        return f"Cannot move a request from {from_status} to {to_status}: {from_status} is final"
    return (
        f"Cannot move a request from {from_status} to {to_status}. "
        f"Allowed from {from_status}: {', '.join(allowed)}"
    )


def ensure_enough_episodes_assigned(db: Session, request: DatasetRequest) -> None:
    """Entry check for ``delivered``: the request needs enough assigned episodes.

    Not enforced yet. Assignments do not exist, so this check always passes.
    Once they do, it must count the episodes assigned to the request and raise
    ConflictError when the count is below ``episodes_requested``.
    """


ENTRY_CHECKS: dict[str, Callable[[Session, DatasetRequest], None]] = {
    "delivered": ensure_enough_episodes_assigned,
}
