"""Public deterministic Layer 1 computation pipeline."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
import hashlib
import importlib.metadata
import importlib.util
from pathlib import Path
import re
from typing import Any, Dict, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe

from .aggregate.drivers import normalize_events
from .aggregate.mapping import MVP_AREAS, project_driver
from .aggregate.merge import connected_buckets
from .aggregate.polarity import polarity_pipeline
from .aggregate.scoring import noisy_or, score_profection
from .aggregate.time_bucket import classify_time_scale
from .config import CONFIG_VERSION
from .enums import TECHNIQUES
from .ephemeris.common import iso_z, parse_utc, q6
from .ephemeris.natal import compute_natal_chart
from .ephemeris.profection import compute_profection_events
from .ephemeris.progressions import compute_progression_events
from .ephemeris.returns import compute_lunar_return_events, compute_solar_return_events
from .ephemeris.transits import compute_transit_events
from .post.headline import localized_text
from .post.hints import build_hints
from .post.sort_hash import activation_hash, emit_driver, sort_activations
from .types import Activation, ComputeInput


def compute_activations(input: ComputeInput) -> List[Activation]:
    """Compute activations without hidden clock or mutable global state."""

    _validate_input(input)
    start = parse_utc(input["window"]["start_utc"])
    end = parse_utc(input["window"]["end_utc"])
    natal = compute_natal_chart(input["birth"], input["config"])
    events = _safe_events(natal, "transits", compute_transit_events, natal, start, end)
    events.extend(_safe_events(natal, "progressions", compute_progression_events, natal, start, end))
    if input["birth"]["time_known"]:
        events.extend(_safe_events(natal, "solar_return", compute_solar_return_events, natal, start, end))
        events.extend(_safe_events(natal, "lunar_return", compute_lunar_return_events, natal, start, end))
        profections = _safe_events(natal, "profection", compute_profection_events, natal, start, end, input["config"])
        _apply_year_lord_matches(profections, events)
        events.extend(profections)
    drivers = [project_driver(driver) for driver in normalize_events(events)]
    activations = [
        _activation_from_bucket(bucket, natal, input)
        for bucket in connected_buckets(drivers)
    ]
    activations = [activation for activation in activations if activation is not None]
    _fill_empty_areas(activations, natal, input, start, end)
    return sort_activations(activations)


def _validate_input(input: ComputeInput) -> None:
    start = parse_utc(input["window"]["start_utc"])
    end = parse_utc(input["window"]["end_utc"])
    if end <= start:
        raise ValueError("window.end_utc must be after window.start_utc")
    if input["window"]["granularity"] != "day":
        raise ValueError("MVP only supports day granularity")
    if input["mode"] not in ("forecast", "retrospective"):
        raise ValueError("unsupported mode")
    if input["locale"] not in ("zh-Hans", "en"):
        raise ValueError("unsupported locale")
    config = input["config"]
    if not re.fullmatch(r"layer1@[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?", config["version"]):
        raise ValueError("invalid config version")
    if config["version"] != CONFIG_VERSION:
        raise ValueError("unsupported config version: {0}".format(config["version"]))
    if config["zodiac_system"] != "tropical" or config["house_system"] != "placidus":
        raise ValueError("MVP requires tropical zodiac and placidus houses")
    if config["profection_rulership"] not in ("traditional", "modern"):
        raise ValueError("unsupported profection rulership")
    if config["node_type"] not in ("true", "mean"):
        raise ValueError("unsupported node type")
    try:
        ZoneInfo(input["birth"]["tz_iana"])
    except ZoneInfoNotFoundError as exc:
        raise ValueError("unknown IANA timezone") from exc


def _safe_events(natal: dict, label: str, function, *args) -> List[dict]:
    try:
        return function(*args)
    except Exception:
        natal["degraded_flags"].append("ephemeris_error:{0}".format(label))
        return []


def _apply_year_lord_matches(profections: List[dict], transit_events: List[dict]) -> None:
    for profection in profections:
        lord = profection["profection_lord_active"]
        matched = any(
            event["kind"] == "transit_to_natal"
            and event.get("natal_target") == lord
            and event.get("orb_deg", 99) < 3
            for event in transit_events
        )
        profection["year_lord_match"] = matched
        profection["weight"] = float(score_profection(
            year_lord_match=matched,
            profection_house=profection["profection_house"],
        ))


def _activation_from_bucket(bucket: List[dict], natal: dict, input: ComputeInput):
    ranked = sorted(bucket, key=lambda item: (-item["weight"], item["driver_id"]))
    truncated = max(0, len(ranked) - 8)
    bucket = sorted(ranked[:8], key=lambda item: item["driver_id"])
    if input["mode"] == "retrospective":
        for driver in bucket:
            driver.setdefault("ephemeris_snapshot", None)
    scores = {}
    for driver in bucket:
        for area, value in driver["raw_area_scores"].items():
            if area in MVP_AREAS:
                scores[area] = min(1.0, round(scores.get(area, 0.0) + value, 6))
    if not scores or max(scores.values()) < 0.30:
        return None
    scores = dict(sorted(scores.items(), key=lambda item: (-item[1], MVP_AREAS.index(item[0])))[:3])
    primary = min(scores, key=lambda area: (-scores[area], MVP_AREAS.index(area)))
    intensity = float(noisy_or((driver["driver_id"], driver["weight"]) for driver in bucket))
    mix, polarity = polarity_pipeline(bucket, intensity)
    start = min(driver["start"] for driver in bucket)
    end = max(driver["end"] for driver in bucket)
    peak_driver = max(bucket, key=lambda item: (item["weight"], -int(item["peak"].timestamp())))
    passes = []
    for driver in bucket:
        passes.extend(driver.get("retrograde_passes", []))
    passes = sorted({(item["peak_utc"], item["phase"]): item for item in passes}.values(), key=lambda item: item["peak_utc"])
    headline, one_line = localized_text(primary, input["locale"])
    techniques = [name for name in TECHNIQUES if any(driver["technique"] == name for driver in bucket)]
    activation = {
        "activation_id": "0" * 16,
        "config_version": input["config"]["version"],
        "provenance": _provenance(),
        "zodiac_system": input["config"]["zodiac_system"],
        "house_system": natal["house_system"],
        "mode": input["mode"],
        "primary_life_area": primary,
        "life_area_scores": scores,
        "time_scale": classify_time_scale(bucket),
        "window": {
            "start_utc": iso_z(start), "end_utc": iso_z(end),
            "peak_utc": iso_z(peak_driver["peak"]),
            "peak_precision_hours": peak_driver["peak_precision_hours"],
            "retrograde_passes": passes,
        },
        "polarity": polarity,
        "polarity_mix": mix,
        "intensity": q6(intensity),
        "confidence": q6(natal["confidence"]),
        "birth_data_precision": natal["birth_data_precision"],
        "house_precision": natal["house_precision"],
        "techniques": techniques,
        "headline": headline,
        "one_line": one_line,
        "drivers": [emit_driver(driver) for driver in bucket],
        "kb_context_ids": _context_ids(primary, bucket),
        "narrative_hints": build_hints(primary, polarity, input["mode"], bucket, truncated),
        "degraded_flags": sorted(set(natal["degraded_flags"])),
    }
    activation["activation_id"] = activation_hash(activation, input["config"], bucket)
    return activation


def _context_ids(area: str, drivers: List[dict]) -> List[str]:
    values = {"life-area-{0}".format(area)}
    for driver in drivers:
        if driver.get("house"):
            values.add("houses/house-{0:02d}".format(driver["house"]))
        for key in ("transiting_body", "natal_target", "profection_lord_active"):
            if driver.get(key) in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"):
                values.add("planets/{0}".format(driver[key]))
    return sorted(values)


def _fill_empty_areas(activations: List[dict], natal: dict, input: ComputeInput, start, end) -> None:
    present = {activation["primary_life_area"] for activation in activations}
    anchors = {
        "career": ("mc", "angle", 10),
        "wealth": (None, "house", 2),
        "relationships": ("venus", "planet", natal["planets"]["venus"].get("house")),
        "family": ("moon", "planet", natal["planets"]["moon"].get("house")),
    }
    for area in MVP_AREAS:
        if area in present:
            continue
        target, target_type, house = anchors[area]
        if not input["birth"]["time_known"] or not natal["houses"]:
            target = {"career": "saturn", "wealth": "venus", "relationships": "venus", "family": "moon"}[area]
            target_type, house = "planet", None
        anchor_lon = natal["angles"].get(target) if target in natal["angles"] else natal["planets"].get(target, {}).get("lon")
        driver = project_driver(normalize_events([{
            "kind": "foundation", "technique": "foundation", "start": start,
            "end": end, "peak": start + (end - start) / 2,
            "peak_precision_hours": 24, "natal_target": target,
            "target_type": target_type, "house": house, "weight": 0.15,
            "kb_lookup_id": "life-area-{0}".format(area),
            "foundation_area": area, "_natal_anchor_lon_deg": anchor_lon,
        }])[0])
        activation = _activation_from_bucket([driver], natal, input)
        if activation is None:
            # Foundation activations deliberately sit below the normal rescue threshold.
            driver["raw_area_scores"] = {area: 0.30}
            activation = _activation_from_bucket([driver], natal, input)
            activation["life_area_scores"] = {area: 0.15}
            activation["intensity"] = 0.15
            activation["polarity"] = "neutral"
            activation["polarity_mix"] = {"supportive": 0.0, "challenging": 0.0, "neutral": 1.0, "growth": 0.0}
            activation["degraded_flags"] = sorted(set(activation["degraded_flags"] + ["empty_life_area_filler"]))
            activation["activation_id"] = activation_hash(activation, input["config"], [driver])
        activations.append(activation)


@lru_cache(maxsize=1)
def _provenance() -> dict:
    ephe_dir = Path(importlib.util.find_spec("immanuel").origin).parent / "resources" / "ephemeris"
    digest = hashlib.sha256()
    for path in sorted(ephe_dir.glob("*.se1")):
        digest.update(path.name.encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    try:
        tzdb_version = importlib.metadata.version("tzdata")
    except importlib.metadata.PackageNotFoundError:
        tzdb_version = "system"
    return {
        "se_version": swe.version,
        "se_ephe_files_sha256": digest.hexdigest(),
        "deltat_source": "SE_builtin",
        "tzdb_version": tzdb_version,
        "immanuel_version": importlib.metadata.version("immanuel"),
    }
