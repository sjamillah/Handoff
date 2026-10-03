"""The request status workflow: allowed moves, who may make them, and the history."""

from datetime import UTC, datetime, timedelta
from itertools import product

import pytest
from sqlalchemy import select

from app.models import StatusHistory
from app.models.constants import REQUEST_STATUSES
from app.services.requests import TRANSITION_TABLE, TRANSITIONS
from tests.conftest import assign_directly, set_status, status_of, user_id

INVALID_MOVES = [
    pair for pair in product(REQUEST_STATUSES, repeat=2) if pair not in TRANSITION_TABLE
]


@pytest.mark.parametrize(("from_status", "to_status"), INVALID_MOVES)
def test_invalid_transition_is_rejected(
    from_status, to_status, client_a, operator, make_request, db
):
    request_id = make_request()
    set_status(db, request_id, from_status)
    for user in (operator, client_a):
        response = user.post(f"/requests/{request_id}/transitions", json={"to_status": to_status})
        assert response.status_code == 409
    assert status_of(db, request_id) == from_status


@pytest.mark.parametrize("transition", TRANSITIONS, ids=lambda t: f"{t.from_status}-{t.to_status}")
def test_only_the_owning_role_can_make_each_move(
    transition, client_a, operator, admin, make_request, make_episodes, db
):
    request_id = make_request(episodes_requested=1)
    assign_directly(db, request_id, make_episodes())
    set_status(db, request_id, transition.from_status)
    users = {"client": [client_a], "staff": [operator, admin]}
    allowed, refused = ("client", "staff") if "client" in transition.roles else ("staff", "client")
    body = {"to_status": transition.to_status}

    for user in users[refused]:
        response = user.post(f"/requests/{request_id}/transitions", json=body)
        assert response.status_code == 403
    response = users[allowed][0].post(f"/requests/{request_id}/transitions", json=body)
    assert response.status_code == 200
    assert status_of(db, request_id) == transition.to_status


def test_each_change_writes_a_history_row_with_user_and_time(operator, make_request, db):
    request_id = make_request()
    before = datetime.now(UTC)
    response = operator.post(
        f"/requests/{request_id}/transitions", json={"to_status": "in_progress"}
    )
    assert response.status_code == 200

    rows = db.scalars(
        select(StatusHistory)
        .where(StatusHistory.request_id == request_id)
        .order_by(StatusHistory.id)
    ).all()
    assert [(r.from_status, r.to_status) for r in rows] == [
        (None, "submitted"),
        ("submitted", "in_progress"),
    ]
    assert rows[0].changed_by_id == user_id(db, "client-a@example.com")
    assert rows[1].changed_by_id == user_id(db, "ops1@example.com")
    assert rows[1].changed_by_role == "operator"
    assert before - timedelta(seconds=5) <= rows[1].changed_at <= datetime.now(UTC)


def test_clients_see_staff_changes_by_role_only(client_a, operator, make_request):
    request_id = make_request()
    operator.post(f"/requests/{request_id}/transitions", json={"to_status": "in_progress"})

    seen_by_client = client_a.get(f"/requests/{request_id}").json()["history"]
    assert [entry["changed_by_role"] for entry in seen_by_client] == ["client", "operator"]
    assert seen_by_client[0]["changed_by_name"] is not None
    assert seen_by_client[1]["changed_by_name"] is None

    seen_by_staff = operator.get(f"/requests/{request_id}").json()["history"]
    assert seen_by_staff[1]["changed_by_name"] is not None


class HalfPastMidnightInKigali(datetime):
    """``datetime`` whose ``now`` is 00:30 on 5 October in Kigali, still 4 October in UTC."""

    @classmethod
    def now(cls, tz=None):
        """Return the fixed instant, in ``tz``."""
        return datetime(2026, 10, 4, 22, 30, tzinfo=UTC).astimezone(tz)


def test_deadlines_are_judged_by_the_date_in_kigali(client_a, monkeypatch):
    monkeypatch.setattr("app.schemas.requests.datetime", HalfPastMidnightInKigali)

    def create(deadline):
        return client_a.post(
            "/requests",
            json={"task_name": "pick cup", "episodes_requested": 1, "deadline": deadline},
        )

    assert create("2026-10-04").status_code == 422
    assert create("2026-10-05").status_code == 201
