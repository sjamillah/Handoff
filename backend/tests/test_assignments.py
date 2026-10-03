"""Assignment rules and the delivered rule."""

import threading

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Assignment, Episode
from tests.conftest import assign_directly, login, set_status, status_of


@pytest.fixture
def started(make_request, db):
    """Return a factory for requests already in in_progress."""

    def create(episodes_requested: int = 1) -> int:
        request_id = make_request(episodes_requested=episodes_requested)
        set_status(db, request_id, "in_progress")
        return request_id

    return create


def assign(client, request_id, episode_ids):
    return client.post(f"/requests/{request_id}/assignments", json={"episode_ids": episode_ids})


def assignment_count(db):
    return db.scalar(select(func.count(Assignment.id)))


def test_bad_quality_episode_is_refused(operator, started, make_episodes, db):
    request_id = started()
    response = assign(operator, request_id, make_episodes(quality="bad"))
    assert response.status_code == 409
    assert assignment_count(db) == 0


def test_episode_cannot_go_to_two_requests(operator, started, make_episodes):
    first, second = started(), started()
    episode_ids = make_episodes()
    assert assign(operator, first, episode_ids).status_code == 201
    assert assign(operator, second, episode_ids).status_code == 409


def test_database_refuses_a_second_assignment_of_one_episode(started, make_episodes, db):
    first, second = started(), started()
    episode_ids = make_episodes()
    assign_directly(db, first, episode_ids)
    with pytest.raises(IntegrityError):
        assign_directly(db, second, episode_ids)


def test_concurrent_assignments_of_one_episode_leave_one_winner(started, make_episodes, db):
    requests = [started(), started()]
    operators = [login("ops1@example.com"), login("ops2@example.com")]
    for episode_id in make_episodes(count=5):
        barrier = threading.Barrier(2)
        codes = []

        def attempt(index, episode_id=episode_id, barrier=barrier, codes=codes):
            barrier.wait()
            codes.append(assign(operators[index], requests[index], [episode_id]).status_code)

        threads = [threading.Thread(target=attempt, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(codes) == [201, 409]
    db.expire_all()
    per_episode = db.execute(
        select(Episode.episode_id, func.count(Assignment.id))
        .join(Assignment, Assignment.episode_id == Episode.id)
        .group_by(Episode.episode_id)
    ).all()
    assert len(per_episode) == 5
    assert all(count == 1 for _, count in per_episode)


@pytest.mark.parametrize("status", ["submitted", "delivered"])
def test_episodes_can_only_be_assigned_while_in_progress(
    operator, make_request, make_episodes, db, status
):
    request_id = make_request()
    set_status(db, request_id, status)
    response = assign(operator, request_id, make_episodes())
    assert response.status_code == 409
    assert assignment_count(db) == 0


def test_episodes_cannot_be_unassigned_after_delivery(operator, started, make_episodes, db):
    request_id = started()
    (episode_id,) = make_episodes()
    assign_directly(db, request_id, [episode_id])
    set_status(db, request_id, "delivered")
    response = operator.delete(f"/requests/{request_id}/assignments/{episode_id}")
    assert response.status_code == 409
    assert assignment_count(db) == 1


def test_delivery_is_refused_when_fewer_episodes_assigned_than_requested(
    operator, started, make_episodes, db
):
    request_id = started(episodes_requested=2)
    assign_directly(db, request_id, make_episodes(count=1))
    response = operator.post(f"/requests/{request_id}/transitions", json={"to_status": "delivered"})
    assert response.status_code == 409
    assert status_of(db, request_id) == "in_progress"


def test_delivery_is_allowed_when_assigned_equals_requested(operator, started, make_episodes, db):
    request_id = started(episodes_requested=2)
    assign_directly(db, request_id, make_episodes(count=2))
    response = operator.post(f"/requests/{request_id}/transitions", json={"to_status": "delivered"})
    assert response.status_code == 200
    assert status_of(db, request_id) == "delivered"
