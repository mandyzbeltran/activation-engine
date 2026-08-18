"""Natal chart calculation and precision degradation."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from layer1.ephemeris.common import (
    angular_distance,
    angle_positions,
    house_cusps,
    house_for,
    parse_utc,
    planet_positions,
    ruler_for_sign,
    sign_for,
)
from layer1.aggregate.scoring import orb_factor
from layer1.enums import ASPECTS, PLANETS


EXACT_ANGLES = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}


def compute_natal_chart(birth: dict, config: dict) -> Dict[str, Any]:
    birth_time = parse_utc(birth["utc_iso"])
    time_known = bool(birth["time_known"])
    lat = birth.get("lat")
    lon = birth.get("lon")
    flags = []
    confidence = 1.0

    if lat is None or lon is None:
        house_system = "placidus"
        houses = None
        angles = {}
        flags.append("no_geolocation")
        confidence *= 0.80
        house_precision = "no_houses"
    elif not time_known:
        house_system = "whole_sign"
        houses = None
        angles = {}
        flags.extend(("no_birth_time", "house_system_fallback", "return_angles_unavailable"))
        confidence *= 0.70
        house_precision = "whole_sign_fallback"
    elif abs(float(lat)) > 66.5:
        house_system = "whole_sign"
        flags.append("placidus_undefined_at_latitude")
        confidence *= 0.90
        houses = house_cusps(birth_time, float(lat), float(lon), house_system)
        angles = angle_positions(birth_time, float(lat), float(lon), house_system)
        house_precision = "whole_sign_fallback"
    else:
        house_system = config["house_system"]
        houses = house_cusps(birth_time, float(lat), float(lon), house_system)
        angles = angle_positions(birth_time, float(lat), float(lon), house_system)
        house_precision = "placidus"

    planets = planet_positions(birth_time)
    for name, values in planets.items():
        values["sign"] = sign_for(values["lon"])
        values["house"] = house_for(values["lon"], houses) if houses else None

    asc_ruler = ruler_for_sign(sign_for(angles["asc"]), "traditional") if angles else None
    mc_ruler = ruler_for_sign(sign_for(angles["mc"]), "traditional") if angles else None
    if birth_time.year < 1972:
        flags.append("pre_tzdb_lmt_fallback")
        confidence *= 0.95
    return {
        "birth_time": birth_time,
        "lat": lat,
        "lon": lon,
        "planets": planets,
        "angles": angles,
        "houses": houses,
        "house_system": house_system,
        "house_precision": house_precision,
        "birth_data_precision": "known" if time_known else "placeholder",
        "confidence": confidence,
        "degraded_flags": flags,
        "chart_ruler": asc_ruler,
        "mc_ruler": mc_ruler,
    }


def summarize_natal_chart(birth: dict, config: dict) -> Dict[str, Any]:
    """Return the stable, presentation-safe natal subset requested by UCR-3."""

    natal = compute_natal_chart(birth, config)
    planets = {
        name: {
            "longitude_deg": values["lon"],
            "sign": values["sign"],
            "house": values["house"],
            "retrograde": values["speed"] < 0,
        }
        for name, values in natal["planets"].items()
    }
    angles = {
        name: {
            "longitude_deg": longitude,
            "sign": sign_for(longitude),
            "house": {"asc": 1, "dsc": 7, "mc": 10, "ic": 4}[name],
        }
        for name, longitude in natal["angles"].items()
    }
    aspects = []
    for left_index, left in enumerate(PLANETS):
        for right in PLANETS[left_index + 1:]:
            distance = angular_distance(
                natal["planets"][left]["lon"], natal["planets"][right]["lon"]
            )
            for aspect in ASPECTS:
                if orb_factor(aspect, right, distance) > 0:
                    aspects.append({
                        "body_a": left,
                        "body_b": right,
                        "aspect": aspect,
                        "orb_deg": round(abs(distance - EXACT_ANGLES[aspect]), 6),
                    })
    aspects.sort(key=lambda item: (item["orb_deg"], item["body_a"], item["body_b"], item["aspect"]))
    return {
        "planets": planets,
        "angles": angles,
        "houses": natal["houses"] or {},
        "aspects": aspects,
        "house_system": natal["house_system"],
        "birth_data_precision": natal["birth_data_precision"],
        "house_precision": natal["house_precision"],
        "confidence": natal["confidence"],
        "degraded_flags": sorted(set(natal["degraded_flags"])),
    }
