"""
Economic calendar provider interface and simulated implementation.
"""

import abc
import datetime
from backend.core.time_utils import now_utc, utc_timestamp


class CalendarProvider(abc.ABC):
    """Abstract interface for economic calendar data."""

    @abc.abstractmethod
    def get_upcoming_events(self, hours_ahead: int = 48) -> dict:
        """Get upcoming economic events.
        Returns: {timestamp, events: [...], high_impact_within_2h, nearest_high_impact}
        """

    @abc.abstractmethod
    def is_news_blackout(self, dt: datetime.datetime = None) -> bool:
        """Check if we are within a news blackout window (high-impact within 2h)."""


class SimulatedCalendarProvider(CalendarProvider):
    """Simulated economic calendar with recurring weekly events."""

    BASE_EVENTS = [
        {"name": "FOMC Minutes", "impact": "high", "typical_day": 2, "hour": 18},
        {"name": "US CPI", "impact": "high", "typical_day": 1, "hour": 12},
        {"name": "US NFP", "impact": "high", "typical_day": 4, "hour": 12},
        {"name": "US PPI", "impact": "medium", "typical_day": 3, "hour": 12},
        {"name": "US Retail Sales", "impact": "medium", "typical_day": 0, "hour": 12},
        {"name": "ECB Rate Decision", "impact": "high", "typical_day": 3, "hour": 11},
        {"name": "US Jobless Claims", "impact": "medium", "typical_day": 3, "hour": 12},
    ]

    def get_upcoming_events(self, hours_ahead: int = 48) -> dict:
        now = now_utc()
        day = now.weekday()

        events = []
        for evt in self.BASE_EVENTS:
            days_until = (evt["typical_day"] - day) % 7
            event_time = now.replace(
                hour=evt["hour"], minute=30, second=0, microsecond=0
            ) + datetime.timedelta(days=days_until)
            hours_until = (event_time - now).total_seconds() / 3600

            events.append({
                "name": evt["name"],
                "impact": evt["impact"],
                "datetime_utc": event_time.isoformat(),
                "hours_until": round(hours_until, 1),
                "within_2h": abs(hours_until) <= 2,
            })

        events.sort(key=lambda e: abs(e["hours_until"]))
        high_impact_soon = any(
            e["within_2h"] and e["impact"] == "high" for e in events
        )

        return {
            "timestamp": utc_timestamp(),
            "events": events[:5],
            "high_impact_within_2h": high_impact_soon,
            "nearest_high_impact": next(
                (e for e in events if e["impact"] == "high"), None
            ),
            "source": "simulated",
        }

    def is_news_blackout(self, dt: datetime.datetime = None) -> bool:
        result = self.get_upcoming_events()
        return result["high_impact_within_2h"]
