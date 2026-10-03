"""How a request is shown to each viewer.

The workflow lives in ``requests``. This module only decides what a given user
sees: which actions are offered, and whose names appear in the history.
"""

from app.models import DatasetRequest, User
from app.models.constants import ASSIGNABLE_REQUEST_STATUSES
from app.schemas import RequestDetail, RequestOut, StatusChangeOut
from app.services.requests import available_transitions


def request_detail(request: DatasetRequest, viewer: User) -> RequestDetail:
    """Build the detail view of a request for this viewer.

    Staff see the name of everyone in the history. Clients see names only for
    their own changes, and the role alone for changes made by staff.
    """
    history = [
        StatusChangeOut(
            from_status=change.from_status,
            to_status=change.to_status,
            changed_by_role=change.changed_by_role,
            changed_by_name=change.changed_by.name
            if viewer.role != "client" or change.changed_by_id == viewer.id
            else None,
            changed_at=change.changed_at,
        )
        for change in request.history
    ]
    return RequestDetail(**request_summary(request, viewer).model_dump(), history=history)


def request_summary(request: DatasetRequest, viewer: User) -> RequestOut:
    """Build the list view of a request, with the actions this viewer may take on it now.

    ``available_transitions`` and ``can_assign`` come from the same table and
    statuses the service enforces, so a UI can show exactly the allowed actions
    without repeating any rule. The server still checks every action.
    """
    return RequestOut(
        id=request.id,
        client_id=request.client_id,
        client_name=request.client.name,
        task_name=request.task_name,
        episodes_requested=request.episodes_requested,
        deadline=request.deadline,
        notes=request.notes,
        status=request.status,
        assigned_count=request.assigned_count,
        available_transitions=available_transitions(request.status, viewer.role),
        can_assign=viewer.role != "client" and request.status in ASSIGNABLE_REQUEST_STATUSES,
        created_at=request.created_at,
    )
