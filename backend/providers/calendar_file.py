"""
File-backed economic calendar provider.

Loads upcoming events from a JSON file on disk. This is the honest middle
ground between pure simulation and a paid calendar feed (ForexFactory,
TradingEconomics, Finnhub): the operator drops a curated JSON into
`data/calendar.json` (or wherever CALENDAR_FILE points) and the provider
reads it on each call.

File format: a list of event dicts, each with at minimum:
  {
    "name": "US CPI",
    "impact": "high",                          # high | medium | low
    "datetime_utc": "2026-04-17T12:30:00Z",    # ISO-8601 UTC
    "currency": "USD"                          # optional
  }

Extra keys are preserved verbatim so operators can annotate freely.

Configuration:
  CALENDAR_PROVIDER=file         activates this provider
  CALENDAR_FILE=<path>           default: data/calendar.json
  CALENDAR_BLACKOUT_HOURS=2      minutes-before-event window considered
                                 "within blackout" (default 2h)

Honesty notes:
  - This is real data *if the operator curates it honestly*. It is not a
    live feed, so stale files degrade gracefully:
      - Events with datetime_utc in the past are filtered out of `upcoming`.
      - If the file is empty, missing, or malformed, we raise a clear
        CalendarConfigError -- we do NOT silently return an empty list.
  - Callers can compare get_status()["last_loaded"] to now() to detect
    stale curations.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.time_utils import now_utc, utc_timestamp, to_utc
from backend.providers.calendar_data import CalendarProvider


class CalendarConfigError(RuntimeError):
    """Raised when the calendar file is missing or malformed."""


class FileCalendarProvider(CalendarProvider):
    """Calendar backed by a JSON file on disk."""

    def __init__(self, path: Optional[str] = None, blackout_hours: float = 2.0):
        self.path = Path(path or os.environ.get("CALENDAR_FILE", "data/calendar.json"))
        self.blackout_hours = float(
            os.environ.get("CALENDAR_BLACKOUT_HOURS", blackout_hours)
        )
        self._events: List[Dict[str, Any]] = []
        self._last_loaded: Optional[str] = None
        self._load_error: Optional[str] = None
        self._try_load()

    # ── Status ───────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": "file",
            "kind": "real" if self._load_error is None else "unavailable",
            "is_real": self._load_error is None,
            "ready": self._load_error is None,
            "reason": self._load_error,
            "path": str(self.path),
            "event_count": len(self._events),
            "last_loaded": self._last_loaded,
        }

    def is_ready(self) -> bool:
        return self._load_error is None

    # ── Loading ──────────────────────────────────────────────────────────────

    def _try_load(self) -> None:
        try:
            if not self.path.exists():
                raise CalendarConfigError(f"Calendar file not found: {self.path}")
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, list):
                raise CalendarConfigError(
                    f"Calendar file must be a JSON list; got {type(data).__name__}"
                )
            cleaned: List[Dict[str, Any]] = []
            for i, evt in enumerate(data):
                if not isinstance(evt, dict):
                    raise CalendarConfigError(f"Event #{i} is not an object")
                for req in ("name", "impact", "datetime_utc"):
                    if req not in evt:
                        raise CalendarConfigError(
                            f"Event #{i} missing required field {req!r}"
                        )
                # Validate datetime parses.
                try:
                    _parse_iso(evt["datetime_utc"])
                except Exception as e:
                    raise CalendarConfigError(
                        f"Event #{i} has invalid datetime_utc: {e}"
                    )
                cleaned.append(evt)
            self._events = cleaned
            self._last_loaded = utc_timestamp()
            self._load_error = None
        except (OSError, ValueError, CalendarConfigError) as e:
            self._events = []
            self._load_error = str(e)

    def reload(self) -> None:
        """Re-read the file -- used after operator edits."""
        self._try_load()

    # ── CalendarProvider contract ────────────────────────────────────────────

    def get_upcoming_events(self, hours_ahead: int = 48) -> dict:
        if self._load_error:
            raise CalendarConfigError(self._load_error)

        now = now_utc()
        horizon = now + datetime.timedelta(hours=hours_ahead)

        enriched: List[Dict[str, Any]] = []
        for evt in self._events:
            ts = _parse_iso(evt["datetime_utc"])
            hours_until = (ts - now).total_seconds() / 3600
            if ts > horizon:
                continue
            # Keep past events within the last blackout window so the UI can
            # show "just happened" state, but drop older history.
            if hours_until < -self.blackout_hours:
                continue
            enriched.append({
                **evt,
                "datetime_utc": ts.isoformat(),
                "hours_until": round(hours_until, 2),
                "within_blackout": abs(hours_until) <= self.blackout_hours,
            })

        enriched.sort(key=lambda e: abs(e["hours_until"]))
        high_impact_soon = any(
            e["within_blackout"] and e["impact"] == "high" for e in enriched
        )
        nearest_high = next(
            (e for e in enriched if e["impact"] == "high" and e["hours_until"] >= 0),
            None,
        )

        return {
            "timestamp": utc_timestamp(),
            "events": enriched[:10],
            "high_impact_within_2h": high_impact_soon,
            "nearest_high_impact": nearest_high,
            "source": "file",
            "path": str(self.path),
        }

    def is_news_blackout(self, dt: datetime.datetime = None) -> bool:
        if self._load_error:
            # Fail-safe: if we can't read the calendar, treat as blackout.
            # This is the conservative choice for risk checks.
            return True
        now = to_utc(dt) if dt else now_utc()
        for evt in self._events:
            ts = _parse_iso(evt["datetime_utc"])
            if evt.get("impact") != "high":
                continue
            delta_h = abs((ts - now).total_seconds()) / 3600
            if delta_h <= self.blackout_hours:
                return True
        return False


def _parse_iso(s: str) -> datetime.datetime:
    # Accept trailing 'Z'.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


# ─── Factory helper ───────────────────────────────────────────────────────────


def get_calendar_provider():
    """Return file-backed or simulated calendar provider based on env.

    CALENDAR_PROVIDER=file       -> FileCalendarProvider (requires CALENDAR_FILE)
    CALENDAR_PROVIDER=simulated (default) -> SimulatedCalendarProvider
    """
    choice = (os.environ.get("CALENDAR_PROVIDER") or "simulated").lower()
    if choice == "file":
        return FileCalendarProvider()
    from backend.providers.calendar_data import SimulatedCalendarProvider
    return SimulatedCalendarProvider()
