"""Stable activation hashing, emission cleanup, and sorting."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable

from layer1.config import TECHNIQUE_WEIGHTS
from layer1.enums import LIFE_AREAS, TECHNIQUES

INTERNAL_DRIVER_KEYS = {
    "start", "end", "peak", "peak_precision_hours", "raw_area_scores",
    "tentative_area", "retrograde_passes", "foundation_area",
    "year_lord_match", "_natal_anchor_lon_deg", "_orb_factor_at_peak",
}


def _round_tree(value, places: int):
    if isinstance(value, float):
        quantum = Decimal("1").scaleb(-places)
        return float(Decimal(str(value)).quantize(quantum, ROUND_HALF_EVEN))
    if isinstance(value, dict):
        return {key: _round_tree(item, places) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_round_tree(item, places) for item in value]
    return value


def emit_driver(driver: dict) -> dict:
    return {
        key: _round_tree(value, 6)
        for key, value in driver.items()
        if key not in INTERNAL_DRIVER_KEYS and (value is not None or key == "ephemeris_snapshot")
    }


def activation_hash(activation: dict, config: dict, raw_drivers: Iterable[dict]) -> str:
    hash_drivers = []
    for driver in sorted(raw_drivers, key=lambda item: item["driver_id"]):
        emitted = emit_driver(driver)
        if "orb_deg" in emitted:
            emitted["orb_deg"] = _round_tree(driver["orb_deg"], 3)
        emitted["weight"] = _round_tree(driver["weight"], 3)
        if "ephemeris_snapshot" in emitted:
            emitted["ephemeris_snapshot"] = _round_tree(driver["ephemeris_snapshot"], 3)
        if driver.get("_natal_anchor_lon_deg") is not None:
            emitted["natal_anchor_lon_deg"] = _round_tree(driver["_natal_anchor_lon_deg"], 3)
        hash_drivers.append(emitted)
    payload = (
        activation["config_version"], activation["zodiac_system"],
        activation["house_system"], config["profection_rulership"],
        config["node_type"], activation["primary_life_area"],
        activation["window"]["start_utc"], activation["window"]["end_utc"],
        hash_drivers,
    )
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]


def sort_activations(activations: list[dict]) -> list[dict]:
    def priority(activation: dict) -> float:
        channels = []
        for technique in activation["techniques"]:
            if technique == "transit":
                bodies = {driver.get("transiting_body") for driver in activation["drivers"]}
                if bodies & {"saturn", "uranus", "neptune", "pluto"}:
                    channels.append(float(TECHNIQUE_WEIGHTS["transit_outer"]))
                elif "jupiter" in bodies:
                    channels.append(float(TECHNIQUE_WEIGHTS["transit_jupiter"]))
                else:
                    channels.append(float(TECHNIQUE_WEIGHTS["transit_inner"]))
            elif technique in TECHNIQUE_WEIGHTS:
                channels.append(float(TECHNIQUE_WEIGHTS[technique]))
            elif technique == "profection":
                channels.append(0.35)
        return max(channels or [0.0])
    return sorted(activations, key=lambda item: (
        -item["intensity"], item["window"]["peak_utc"],
        LIFE_AREAS.index(item["primary_life_area"]), -priority(item),
        item["activation_id"],
    ))
