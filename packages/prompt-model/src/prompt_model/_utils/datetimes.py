from __future__ import annotations

from datetime import datetime, timedelta

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def duration_from_perfcounters(start: float, end: float) -> str:
    delta: float = end - start
    return f"{delta:.4f}"


def duration_from_datetimes(start: datetime, end: datetime) -> str:
    delta: timedelta = end - start
    return f"{delta.total_seconds():.4f}"


def datetime_format(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.strftime(DATETIME_FORMAT)


def parse_datetime(value: str) -> datetime:
    return datetime.strptime(value, DATETIME_FORMAT)
