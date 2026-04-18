"""
HTTP request/response validation utilities.
"""

import json


def parse_json_body(raw_body: bytes) -> tuple:
    """Parse JSON body. Returns (data, error_string)."""
    if not raw_body:
        return {}, None
    try:
        data = json.loads(raw_body)
        if not isinstance(data, dict):
            return None, "Request body must be a JSON object"
        return data, None
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"Invalid JSON: {str(e)}"


def require_fields(data: dict, fields: list) -> str:
    """Check that all required fields are present. Returns error string or None."""
    missing = [f for f in fields if f not in data]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None


def validate_positive_number(value, name: str) -> str:
    """Validate a positive number. Returns error or None."""
    if not isinstance(value, (int, float)):
        return f"'{name}' must be a number"
    if value <= 0:
        return f"'{name}' must be positive"
    return None


def validate_trade_id(raw_id: str) -> tuple:
    """Parse and validate a trade ID from URL path. Returns (int_id, error_string)."""
    try:
        tid = int(raw_id)
        if tid <= 0:
            return None, "Trade ID must be positive"
        return tid, None
    except (ValueError, TypeError):
        return None, f"Invalid trade ID: {raw_id}"
