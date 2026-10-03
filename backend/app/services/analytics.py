"""Analytics computed in the database.

Every figure is one aggregate query; no episode or request rows are loaded into
Python. Dates are calendar days in the business time zone (``APP_TIMEZONE``):
the range ``date_from`` to ``date_to`` covers both days in full, from local
midnight at the start to local midnight after the end.

Range filters:
    episodes per day and top tasks: the episode's ``recorded_at``;
    request counts by status: the request's submission time;
    median submitted to delivered: the time of the request's first delivery.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app import config
from app.models import DatasetRequest, Episode, StatusHistory
from app.models.constants import REQUEST_STATUSES
from app.schemas import AnalyticsOut, DailyRobotCount, StatusCount, TaskCount
from app.services.errors import RuleError

TOP_TASKS = 5


def get_analytics(db: Session, date_from: date, date_to: date) -> AnalyticsOut:
    """Return every analytics figure for the given range of days.

    Raises:
        RuleError: ``date_from`` is after ``date_to``.
    """
    if date_from > date_to:
        raise RuleError("from must be on or before to")
    start, end = day_bounds(date_from, date_to)
    per_day = db.execute(episodes_per_day_query(start, end)).all()
    counts = dict(db.execute(requests_by_status_query(start, end)).tuples().all())
    median_seconds, measured = db.execute(median_delivery_query(start, end)).one()
    top = db.execute(top_tasks_query(start, end)).all()
    return AnalyticsOut(
        date_from=date_from,
        date_to=date_to,
        timezone=str(config.APP_TIMEZONE),
        episodes_per_day=[
            DailyRobotCount(day=row.day, robot_id=row.robot_id, episodes=row.episodes)
            for row in per_day
        ],
        requests_by_status=[
            StatusCount(status=status, requests=counts.get(status, 0))
            for status in REQUEST_STATUSES
        ],
        median_seconds_submitted_to_delivered=median_seconds,
        delivered_requests_measured=measured,
        top_tasks_by_good_episodes=[
            TaskCount(task_name=row.task_name, good_episodes=row.good_episodes) for row in top
        ],
    )


def day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """Return the start and the exclusive end of a range of local days, as aware datetimes."""
    tz = config.APP_TIMEZONE
    start = datetime.combine(date_from, time.min, tz)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tz)
    return start, end


def local_day(column: object) -> object:
    """SQL expression for the calendar day of a timestamp in the business time zone."""
    return func.date(func.timezone(str(config.APP_TIMEZONE), column))


def episodes_per_day_query(start: datetime, end: datetime) -> Select:
    """Episodes recorded per local day and robot, in day then robot order.

    SQL::

        SELECT date(timezone(:tz, recorded_at)) AS day, robot_id, count(*) AS episodes
        FROM episodes
        WHERE recorded_at >= :start AND recorded_at < :end
        GROUP BY day, robot_id ORDER BY day, robot_id
    """
    day = local_day(Episode.recorded_at).label("day")
    return (
        select(day, Episode.robot_id, func.count().label("episodes"))
        .where(Episode.recorded_at >= start, Episode.recorded_at < end)
        .group_by(day, Episode.robot_id)
        .order_by(day, Episode.robot_id)
    )


def requests_by_status_query(start: datetime, end: datetime) -> Select:
    """Current status of the requests submitted in the range, counted per status.

    SQL::

        SELECT status, count(*) FROM requests
        WHERE created_at >= :start AND created_at < :end
        GROUP BY status
    """
    return (
        select(DatasetRequest.status, func.count())
        .where(DatasetRequest.created_at >= start, DatasetRequest.created_at < end)
        .group_by(DatasetRequest.status)
    )


def median_delivery_query(start: datetime, end: datetime) -> Select:
    """Median seconds from submission to first delivery, for first deliveries in the range.

    Uses the history row into ``submitted`` and the earliest history row into
    ``delivered``, so rework after a rejection does not stretch the figure.

    SQL::

        WITH submitted AS (SELECT request_id, min(changed_at) AS at FROM status_history
                           WHERE to_status = 'submitted' GROUP BY request_id),
             delivered AS (SELECT request_id, min(changed_at) AS at FROM status_history
                           WHERE to_status = 'delivered' GROUP BY request_id)
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM d.at - s.at)),
               count(*)
        FROM submitted s JOIN delivered d USING (request_id)
        WHERE d.at >= :start AND d.at < :end

    Returns one row: the median (NULL when nothing was delivered) and the count.
    """
    submitted = first_entry_into("submitted")
    delivered = first_entry_into("delivered")
    seconds = func.extract("epoch", delivered.c.at - submitted.c.at)
    return (
        select(func.percentile_cont(0.5).within_group(seconds), func.count())
        .select_from(submitted)
        .join(delivered, delivered.c.request_id == submitted.c.request_id)
        .where(delivered.c.at >= start, delivered.c.at < end)
    )


def first_entry_into(status: str) -> object:
    """Subquery of each request's first move into ``status``: request_id and at."""
    return (
        select(StatusHistory.request_id, func.min(StatusHistory.changed_at).label("at"))
        .where(StatusHistory.to_status == status)
        .group_by(StatusHistory.request_id)
        .subquery(f"{status}_at")
    )


def top_tasks_query(start: datetime, end: datetime) -> Select:
    """The five task names with the most good episodes recorded in the range.

    Ties are broken by task name, so the result is stable.

    SQL::

        SELECT task_name, count(*) AS good_episodes FROM episodes
        WHERE quality = 'good' AND recorded_at >= :start AND recorded_at < :end
        GROUP BY task_name ORDER BY good_episodes DESC, task_name LIMIT 5
    """
    good = func.count().label("good_episodes")
    return (
        select(Episode.task_name, good)
        .where(
            Episode.quality == "good",
            Episode.recorded_at >= start,
            Episode.recorded_at < end,
        )
        .group_by(Episode.task_name)
        .order_by(good.desc(), Episode.task_name)
        .limit(TOP_TASKS)
    )
