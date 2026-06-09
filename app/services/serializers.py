from datetime import date, datetime
from typing import Any


def serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize_value(v) for v in value]
    return value


def model_to_dict(obj: Any, fields: list[str]) -> dict[str, Any]:
    data = {}
    for field in fields:
        data[field] = serialize_value(getattr(obj, field))
    return data
