"""
Historical OHLC import for non-simulated backtesting.

Supports CSV and JSON files. Validates shape, normalizes timestamps to UTC
ISO-8601, rejects malformed rows cleanly. Does NOT touch the network.

CSV format (header required, case-insensitive):
    timestamp,open,high,low,close,volume
    2024-01-15T10:00:00Z,2050.10,2052.50,2048.30,2051.40,1234

Accepted timestamp formats:
    - ISO-8601 with timezone (preferred)
    - ISO-8601 without timezone (assumed UTC)
    - Unix epoch seconds (numeric)
    - Unix epoch milliseconds (numeric, > 1e12)

JSON format: a list of objects with the same fields as CSV.

Files are expected under DATA_DIR/historical/ but any path works.
"""

import csv
import json
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterable
from backend.core.time_utils import UTC


REQUIRED_FIELDS = ("timestamp", "open", "high", "low", "close")
SUPPORTED_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")


class HistoricalImportError(ValueError):
    """Raised when a historical file is malformed or fails validation."""


def _parse_timestamp(raw: Any) -> str:
    """Parse a timestamp into a UTC ISO-8601 string. Raises on garbage."""
    if raw is None or raw == "":
        raise HistoricalImportError("empty timestamp")

    # Numeric epoch
    if isinstance(raw, (int, float)) or (isinstance(raw, str) and raw.replace(".", "", 1).isdigit()):
        n = float(raw)
        if n > 1e12:  # milliseconds
            n = n / 1000.0
        try:
            dt = datetime.datetime.fromtimestamp(n, tz=UTC)
        except (OverflowError, OSError, ValueError) as e:
            raise HistoricalImportError(f"invalid epoch timestamp {raw!r}: {e}")
        return dt.isoformat()

    # ISO-8601 string
    s = str(raw).strip()
    # Accept trailing Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(s)
    except ValueError as e:
        raise HistoricalImportError(f"invalid timestamp {raw!r}: {e}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat()


def _coerce_float(name: str, raw: Any) -> float:
    if raw is None or raw == "":
        raise HistoricalImportError(f"{name} is empty")
    try:
        return float(raw)
    except (TypeError, ValueError) as e:
        raise HistoricalImportError(f"{name}={raw!r} is not numeric: {e}")


def _coerce_int(name: str, raw: Any, default: int = 0) -> int:
    if raw is None or raw == "":
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError) as e:
        raise HistoricalImportError(f"{name}={raw!r} is not numeric: {e}")


def _validate_candle(row_index: int, raw: Dict[str, Any], timeframe: str) -> Dict[str, Any]:
    # Lowercase keys so callers can be sloppy.
    lc = { (k or "").strip().lower(): v for k, v in raw.items() }
    missing = [f for f in REQUIRED_FIELDS if f not in lc]
    if missing:
        raise HistoricalImportError(
            f"row {row_index}: missing required fields {missing} (have {sorted(lc.keys())})"
        )

    ts = _parse_timestamp(lc["timestamp"])
    o = _coerce_float("open", lc["open"])
    h = _coerce_float("high", lc["high"])
    l = _coerce_float("low", lc["low"])
    c = _coerce_float("close", lc["close"])
    v = _coerce_int("volume", lc.get("volume", 0))

    if h < l:
        raise HistoricalImportError(f"row {row_index}: high {h} < low {l}")
    if not (l <= o <= h) or not (l <= c <= h):
        raise HistoricalImportError(
            f"row {row_index}: open/close ({o},{c}) outside [low,high] ({l},{h})"
        )
    if o <= 0 or c <= 0:
        raise HistoricalImportError(f"row {row_index}: non-positive price")

    return {
        "timestamp": ts,
        "open": round(o, 4),
        "high": round(h, 4),
        "low": round(l, 4),
        "close": round(c, 4),
        "volume": v,
        "timeframe": timeframe,
    }


def load_candles_csv(path: Path, timeframe: str = "1h") -> List[Dict[str, Any]]:
    """Load and validate a CSV file. Returns a sorted, normalized candle list."""
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise HistoricalImportError(
            f"timeframe {timeframe!r} not in {SUPPORTED_TIMEFRAMES}"
        )
    p = Path(path)
    if not p.exists():
        raise HistoricalImportError(f"file not found: {p}")

    with p.open("r", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise HistoricalImportError(f"{p}: empty or missing header")
        rows = list(reader)

    if not rows:
        raise HistoricalImportError(f"{p}: no data rows")

    return _validate_and_sort(rows, timeframe)


def load_candles_json(path: Path, timeframe: str = "1h") -> List[Dict[str, Any]]:
    """Load and validate a JSON file (list of objects). Returns normalized list."""
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise HistoricalImportError(
            f"timeframe {timeframe!r} not in {SUPPORTED_TIMEFRAMES}"
        )
    p = Path(path)
    if not p.exists():
        raise HistoricalImportError(f"file not found: {p}")

    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise HistoricalImportError(f"{p}: invalid JSON: {e}")

    if not isinstance(data, list):
        raise HistoricalImportError(f"{p}: top-level must be a list of candle objects")
    if not data:
        raise HistoricalImportError(f"{p}: empty list")

    return _validate_and_sort(data, timeframe)


def load_candles(path: Path, timeframe: str = "1h") -> List[Dict[str, Any]]:
    """Auto-dispatch on extension. Useful entry point for HTTP handlers."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".csv":
        return load_candles_csv(p, timeframe)
    if suffix == ".json":
        return load_candles_json(p, timeframe)
    raise HistoricalImportError(
        f"unsupported extension {suffix!r} (use .csv or .json)"
    )


def _validate_and_sort(rows: Iterable[Dict[str, Any]], timeframe: str) -> List[Dict[str, Any]]:
    candles: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        candles.append(_validate_candle(i, row, timeframe))

    # Sort by timestamp ascending (deterministic replay, no lookahead).
    candles.sort(key=lambda c: c["timestamp"])

    # Reject duplicate timestamps; that signals a corrupt source.
    seen = set()
    for c in candles:
        if c["timestamp"] in seen:
            raise HistoricalImportError(
                f"duplicate timestamp {c['timestamp']} -- refusing to replay corrupted history"
            )
        seen.add(c["timestamp"])

    return candles


def list_available(historical_dir: Path) -> List[Dict[str, Any]]:
    """Inventory CSV/JSON files in the historical dir for HTTP listing."""
    p = Path(historical_dir)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in (".csv", ".json"):
            try:
                stat = f.stat()
                out.append({
                    "filename": f.name,
                    "size_bytes": stat.st_size,
                    "extension": f.suffix.lower(),
                })
            except OSError:
                continue
    return out
