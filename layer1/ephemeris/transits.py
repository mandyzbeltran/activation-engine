"""Daily deterministic transit sampling and event window extraction."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Dict, List, Tuple

from layer1.aggregate.scoring import orb_factor, score_transit_through_house, score_transit_to_natal
from layer1.config import ORB_LIMITS
from layer1.enums import ASPECTS, PLANETS
from layer1.ephemeris.common import (
    angular_distance,
    house_for,
    iso_z,
    iter_days,
    planet_positions,
    sample_stationary,
    sign_for,
)

EXACT_ANGLES = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}


def _peak_precision(body: str) -> int:
    if body == "moon":
        return 6
    if body in ("sun", "mercury", "venus", "mars"):
        return 48
    if body in ("jupiter", "saturn"):
        return 120
    return 240


def _phase(samples: List[dict], peak_index: int, aspect: str) -> str:
    miss = abs(samples[peak_index]["distance"] - EXACT_ANGLES[aspect])
    if miss <= 0.01:
        return "exact"
    if peak_index == len(samples) - 1:
        return "applying"
    if peak_index == 0:
        return "separating"
    before = abs(samples[peak_index - 1]["distance"] - EXACT_ANGLES[aspect])
    after = abs(samples[peak_index + 1]["distance"] - EXACT_ANGLES[aspect])
    return "applying" if after < before else "separating"


def _targets(natal: Dict[str, Any]) -> Dict[str, dict]:
    targets = {
        name: {
            "lon": values["lon"],
            "target_type": "planet",
            "house": values.get("house"),
            "sign": values.get("sign"),
        }
        for name, values in natal["planets"].items()
    }
    targets.update({
        name: {"lon": lon, "target_type": "angle", "house": {"asc": 1, "dsc": 7, "mc": 10, "ic": 4}[name], "sign": None}
        for name, lon in natal["angles"].items()
    })
    return targets


def compute_transit_events(natal: Dict[str, Any], start: datetime, end: datetime) -> List[dict]:
    days = list(iter_days(start, end))
    if not days:
        return []
    daily = [(day, planet_positions(day)) for day in days]
    events: List[dict] = []
    targets = _targets(natal)

    for body in PLANETS:
        for target, target_data in targets.items():
            for aspect in ASPECTS:
                active: List[dict] = []
                for day, positions in daily:
                    distance = angular_distance(positions[body]["lon"], target_data["lon"])
                    factor = float(orb_factor(aspect, target, distance))
                    sample = {"day": day, "distance": distance, "factor": factor, "position": positions[body]}
                    if not active and factor >= 0.15:
                        active = [sample]
                    elif active and factor >= 0.10:
                        active.append(sample)
                    elif active:
                        events.append(_transit_event(body, target, target_data, aspect, active, natal))
                        active = []
                if active:
                    events.append(_transit_event(body, target, target_data, aspect, active, natal))

    if natal["houses"]:
        for body in ("jupiter", "saturn", "uranus", "neptune", "pluto"):
            segments: List[Tuple[datetime, dict, int]] = []
            previous_house = None
            for day, positions in daily:
                current_house = house_for(positions[body]["lon"], natal["houses"])
                if previous_house is None or current_house == previous_house:
                    segments.append((day, positions[body], current_house))
                else:
                    events.append(_house_event(body, segments, natal))
                    segments = [(day, positions[body], current_house)]
                previous_house = current_house
            if segments:
                events.append(_house_event(body, segments, natal))
    return events


def _interpolated_peak(
    body: str,
    target_data: dict,
    aspect: str,
    samples: List[dict],
    peak_index: int,
) -> Tuple[datetime, dict, float, float]:
    """Refine a daily factor maximum with the three-point parabola from section 6.1."""
    peak_sample = samples[peak_index]
    peak = peak_sample["day"]
    position = peak_sample["position"]
    distance = peak_sample["distance"]
    factor = peak_sample["factor"]
    if 0 < peak_index < len(samples) - 1:
        before = samples[peak_index - 1]["factor"]
        center = peak_sample["factor"]
        after = samples[peak_index + 1]["factor"]
        denominator = before - 2.0 * center + after
        if denominator < 0.0:
            offset_days = 0.5 * (before - after) / denominator
            offset_days = max(-1.0, min(1.0, offset_days))
            offset_hours = int(
                Decimal(str(offset_days * 24.0)).quantize(
                    Decimal("1"), ROUND_HALF_EVEN
                )
            )
            peak = peak + timedelta(hours=offset_hours)
            position = planet_positions(peak)[body]
            distance = angular_distance(position["lon"], target_data["lon"])
            factor = float(orb_factor(aspect, target_data["name"], distance))
    return peak, position, distance, factor


def _transit_event(body: str, target: str, target_data: dict, aspect: str, samples: List[dict], natal: Dict[str, Any]) -> dict:
    peak_index = max(range(len(samples)), key=lambda index: (samples[index]["factor"], -index))
    peak, peak_position, peak_distance, peak_factor = _interpolated_peak(
        body, dict(target_data, name=target), aspect, samples, peak_index
    )
    phase = _phase(samples, peak_index, aspect)
    stationary = sample_stationary(body, peak)
    prominent = target in ("sun", "moon", natal.get("chart_ruler"), natal.get("mc_ruler"))
    weight = score_transit_to_natal(
        transiting_body=body,
        natal_target=target,
        aspect=aspect,
        angular_distance_deg=peak_distance,
        phase=phase,
        stationary=stationary,
        natal_prominent=prominent,
    )
    return {
        "kind": "transit_to_natal",
        "technique": "transit",
        "start": samples[0]["day"],
        "end": samples[-1]["day"] + timedelta(days=1),
        "peak": peak,
        "peak_precision_hours": _peak_precision(body),
        "transiting_body": body,
        "transiting_sign": sign_for(peak_position["lon"]),
        "transiting_house": house_for(peak_position["lon"], natal["houses"]) if natal["houses"] else None,
        "aspect": aspect,
        "natal_target": target,
        "target_type": target_data["target_type"],
        "house": target_data["house"],
        "sign": target_data["sign"],
        "orb_deg": abs(peak_distance - EXACT_ANGLES[aspect]),
        "_orb_factor_at_peak": peak_factor,
        "phase": phase,
        "transiting_retrograde": peak_position["speed"] < 0,
        "stationary": stationary,
        "weight": float(weight),
        "kb_lookup_id": "t-{0}-{1}-n-{2}".format(body, aspect, target),
        "ephemeris_snapshot": {
            "transiting_lon_deg": peak_position["lon"],
            "transiting_speed_deg_per_day": peak_position["speed"],
            "natal_target_lon_deg": target_data["lon"],
            "angular_distance_deg": peak_distance,
            "retrograde": peak_position["speed"] < 0,
        },
    }


def _house_event(body: str, samples: List[Tuple[datetime, dict, int]], natal: Dict[str, Any]) -> dict:
    start, _, house = samples[0]
    end = samples[-1][0] + timedelta(days=1)
    peak_index = len(samples) // 2
    peak, position, _ = samples[peak_index]
    expected = max(len(samples), 1)
    weight = score_transit_through_house(
        transiting_body=body,
        days_remaining_in_house=expected - peak_index,
        expected_dwell_days=expected,
    )
    return {
        "kind": "transit_through_house",
        "technique": "transit",
        "start": start,
        "end": end,
        "peak": peak,
        "peak_precision_hours": _peak_precision(body),
        "transiting_body": body,
        "transiting_sign": sign_for(position["lon"]),
        "transiting_house": house,
        "target_type": "house",
        "house": house,
        "transiting_retrograde": position["speed"] < 0,
        "stationary": sample_stationary(body, peak),
        "weight": float(weight),
        "kb_lookup_id": "t-{0}-in-house-{1:02d}".format(body, house),
        "ephemeris_snapshot": {
            "transiting_lon_deg": position["lon"],
            "transiting_speed_deg_per_day": position["speed"],
            "natal_target_lon_deg": natal["houses"][house]["lon"],
            "angular_distance_deg": angular_distance(position["lon"], natal["houses"][house]["lon"]),
            "retrograde": position["speed"] < 0,
        },
    }
