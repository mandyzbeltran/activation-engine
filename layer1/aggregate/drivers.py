"""Normalize raw ephemeris events into deterministic driver dictionaries."""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Iterable, List, Tuple

from layer1.ephemeris.common import iso_z, q6


def normalize_events(events: Iterable[dict]) -> List[dict]:
    events = _merge_multipass(list(events))
    normalized = []
    for event in events:
        event = dict(event)
        identity = {
            key: iso_z(value) if key in ("start", "end", "peak") else value
            for key, value in event.items()
            if key not in ("weight", "ephemeris_snapshot", "year_lord_match")
        }
        event["driver_id"] = "drv_" + hashlib.sha1(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:12]
        event["weight"] = q6(event["weight"])
        event["keywords"] = _fallback_keywords(event)
        normalized.append(event)
    return sorted(normalized, key=lambda item: item["driver_id"])


def _fallback_keywords(event: dict) -> List[str]:
    """Expose deterministic structured tokens when an exact KB entry is absent."""
    values = []
    for key in (
        "kind",
        "technique",
        "transiting_body",
        "aspect",
        "natal_target",
        "transiting_sign",
        "sign",
        "house",
        "transiting_house",
        "profection_house",
        "profection_lord_active",
        "foundation_area",
    ):
        value = event.get(key)
        if value is not None:
            values.append(str(value))
    return list(dict.fromkeys(values))


def _merge_multipass(events: List[dict]) -> List[dict]:
    groups: Dict[Tuple[str, str, str], List[dict]] = {}
    for event in events:
        if event["kind"] == "transit_to_natal":
            key = (event["transiting_body"], event["aspect"], event["natal_target"])
            groups.setdefault(key, []).append(event)
    for group in groups.values():
        group.sort(key=lambda item: item["peak"])
        index = 0
        while index < len(group) - 1:
            triple = group[index : index + 3]
            if len(triple) == 3 and _retrograde_pattern(triple) == [False, True, False]:
                if _multipass_span_days(triple) <= 550:
                    _apply_multipass(triple, ("direct-1", "retrograde", "direct-2"))
                    index += 3
                    continue
            pair = group[index : index + 2]
            pattern = _retrograde_pattern(pair)
            if _multipass_span_days(pair) <= 550 and pattern in ([False, True], [True, False]):
                phases = (
                    ("direct-1", "retrograde")
                    if pattern == [False, True]
                    else ("retrograde", "direct-2")
                )
                _apply_multipass(pair, phases)
                index += 2
                continue
            index += 1
    return events


def _retrograde_pattern(events: List[dict]) -> List[bool]:
    return [bool(item.get("transiting_retrograde")) for item in events]


def _multipass_span_days(events: List[dict]) -> int:
    return (events[-1]["peak"] - events[0]["peak"]).days


def _apply_multipass(events: List[dict], phases: Tuple[str, ...]) -> None:
    envelope_start = min(item["start"] for item in events)
    envelope_end = max(item["end"] for item in events)
    passes = []
    for item, phase in zip(events, phases):
        if item.get("transiting_retrograde"):
            item["weight"] = round(item["weight"] * 0.85, 6)
        passes.append({
            "peak_utc": iso_z(item["peak"]),
            "phase": phase,
            "orb_factor_at_peak": round(
                max(0.0, min(1.0, item.get("_orb_factor_at_peak", 0.0))),
                6,
            ),
        })
    for item in events:
        item["start"] = envelope_start
        item["end"] = envelope_end
        item["retrograde_passes"] = passes
