"""
Timezone-aware UTC time utilities for the Gold Trading Platform.
All timestamps in the system must be timezone-aware UTC.
"""

import datetime


UTC = datetime.timezone.utc


def now_utc() -> datetime.datetime:
    """Return the current time as timezone-aware UTC."""
    return datetime.datetime.now(UTC)


def utc_timestamp() -> str:
    """Return an ISO 8601 timestamp string with timezone info."""
    return now_utc().isoformat()


def parse_utc(iso_str: str) -> datetime.datetime:
    """Parse an ISO 8601 string into a timezone-aware UTC datetime.
    Handles both 'Z' suffix and '+00:00' offset formats.
    Naive datetimes (no tz info) are assumed UTC."""
    if iso_str.endswith("Z"):
        iso_str = iso_str[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def to_utc(dt: datetime.datetime) -> datetime.datetime:
    """Ensure a datetime is timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def epoch_ms() -> int:
    """Return current time as milliseconds since Unix epoch."""
    return int(now_utc().timestamp() * 1000)


def get_session(dt: datetime.datetime = None) -> str:
    """Determine the trading session for a given UTC datetime.
    Sessions:
        asia:     00:00 - 08:00 UTC
        london:   08:00 - 13:00 UTC
        overlap:  13:00 - 17:00 UTC  (London + New York)
        new_york: 17:00 - 21:00 UTC
        off_hours: 21:00 - 00:00 UTC
    """
    if dt is None:
        dt = now_utc()
    dt = to_utc(dt)
    hour = dt.hour
    if 0 <= hour < 8:
        return "asia"
    elif 8 <= hour < 13:
        return "london"
    elif 13 <= hour < 17:
        return "overlap"
    elif 17 <= hour < 21:
        return "new_york"
    else:
        return "off_hours"


def is_weekend(dt: datetime.datetime = None) -> bool:
    """Check if the given datetime is Saturday or Sunday."""
    if dt is None:
        dt = now_utc()
    return dt.weekday() in (5, 6)


def is_friday_late(dt: datetime.datetime = None, cutoff_hour: int = 18) -> bool:
    """Check if it's Friday after the cutoff hour (default 18:00 UTC)."""
    if dt is None:
        dt = now_utc()
    dt = to_utc(dt)
    return dt.weekday() == 4 and dt.hour >= cutoff_hour


def day_of_week_name(dt: datetime.datetime = None) -> str:
    """Return the day-of-week name."""
    if dt is None:
        dt = now_utc()
    return dt.strftime("%A")
