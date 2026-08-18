"""Byte-stable JSON emission with six-decimal floating-point formatting."""

from __future__ import annotations

import json
import math
from typing import Any, Iterable


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats are not valid activation JSON")
        return format(value, ".6f")
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            json.dumps(str(key), ensure_ascii=False) + ":" + _encode(value[key])
            for key in sorted(value)
        ) + "}"
    raise TypeError("unsupported activation JSON type: {0}".format(type(value).__name__))


def serialize_activations(activations: Iterable[dict]) -> bytes:
    """Return canonical UTF-8 JSON bytes for an activation array."""

    return _encode(list(activations)).encode("utf-8")
