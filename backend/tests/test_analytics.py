"""Analytics figures: Kigali day buckets, the median to first delivery, and top tasks.

Every test works in March 2020, where no other test data falls, and sets the
timestamps itself so the expected figures are exact.
"""

from datetime import datetime

from sqlalchemy import insert

from app.models import Episode, StatusHistory
from tests.conftest import user_id


def add_episode(db, episode_id, recorded_at, task_name="pick cup", quality="good"):
    db.execute(
        insert(Episode).values(
            episode_id=episode_id,
            robot_id="arm-01",
            task_name=task_name,
            recorded_at=datetime.fromisoformat(recorded_at),
            duration_seconds=30,
            operator_name="Tester",
            quality=quality,
        )
    )
    db.commit()


def add_history(db, request_id, changes):
    operator_id = user_id(db, "ops1@example.com")
    db.execute(
        insert(StatusHistory),
        [
            {
                "request_id": request_id,
                "from_status": None,
                "to_status": to_status,
                "changed_by_id": operator_id,
                "changed_by_role": "operator",
                "changed_at": datetime.fromisoformat(at),
            }
            for to_status, at in changes
        ],
    )
    db.commit()


def analytics(client, day_from, day_to):
    response = client.get("/analytics", params={"from": day_from, "to": day_to})
    assert response.status_code == 200, response.text
    return response.json()


def test_episodes_are_counted_on_their_day_in_kigali(operator, db):
    add_episode(db, "EP-A0001", "2020-03-01T23:30:00+00:00")

    assert analytics(operator, "2020-03-01", "2020-03-01")["episodes_per_day"] == []
    assert analytics(operator, "2020-03-02", "2020-03-02")["episodes_per_day"] == [
        {"day": "2020-03-02", "robot_id": "arm-01", "episodes": 1}
    ]


def test_median_runs_from_submission_to_the_first_delivery(operator, make_request, db):
    reworked, direct = make_request(), make_request()
    add_history(
        db,
        reworked,
        [
            ("submitted", "2020-03-10T08:00:00+00:00"),
            ("delivered", "2020-03-10T09:00:00+00:00"),
            ("rejected", "2020-03-10T10:00:00+00:00"),
            ("delivered", "2020-03-10T20:00:00+00:00"),
        ],
    )
    add_history(
        db,
        direct,
        [
            ("submitted", "2020-03-10T08:00:00+00:00"),
            ("delivered", "2020-03-10T11:00:00+00:00"),
        ],
    )

    figures = analytics(operator, "2020-03-10", "2020-03-10")
    assert figures["delivered_requests_measured"] == 2
    assert figures["median_seconds_submitted_to_delivered"] == 2 * 60 * 60


def test_top_tasks_count_only_good_episodes(operator, db):
    for number, (task_name, quality) in enumerate(
        [
            ("pick cup", "good"),
            ("pick cup", "good"),
            ("pour water", "good"),
            ("fold towel", "bad"),
            ("fold towel", "bad"),
            ("fold towel", "usable"),
        ]
    ):
        add_episode(db, f"EP-B{number:04d}", "2020-03-20T10:00:00+00:00", task_name, quality)

    assert analytics(operator, "2020-03-20", "2020-03-20")["top_tasks_by_good_episodes"] == [
        {"task_name": "pick cup", "good_episodes": 2},
        {"task_name": "pour water", "good_episodes": 1},
    ]
