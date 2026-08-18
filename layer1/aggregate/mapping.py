"""Project normalized drivers onto MVP life areas."""

from __future__ import annotations

from typing import Dict

from layer1.enums import LIFE_AREAS

MVP_AREAS = LIFE_AREAS[:4]

# Coarse public fallbacks only. The detailed Track A weights remain private.
_TARGET_AREAS = {
    "mc": "career",
    "ic": "family",
    "venus": "relationships",
    "moon": "family",
}
_HOUSE_AREAS = {
    2: "wealth",
    3: "family",
    4: "family",
    5: "relationships",
    6: "career",
    7: "relationships",
    8: "wealth",
    9: "career",
    10: "career",
    11: "relationships",
}
_PLANET_AREAS = {
    "sun": "career",
    "moon": "family",
    "mercury": "career",
    "venus": "relationships",
    "mars": "career",
    "jupiter": "wealth",
    "saturn": "career",
    "uranus": "career",
    "neptune": "family",
    "pluto": "wealth",
}


def contribution(driver: dict) -> Dict[str, float]:
    if driver["kind"] == "foundation":
        return {driver["foundation_area"]: 1.0}
    target_area = _TARGET_AREAS.get(driver.get("natal_target"))
    if target_area:
        return {target_area: 1.0}
    house_area = _HOUSE_AREAS.get(driver.get("house"))
    if house_area:
        return {house_area: 1.0}
    planet_area = _PLANET_AREAS.get(driver.get("natal_target"))
    if planet_area:
        return {planet_area: 1.0}
    transiting_area = _PLANET_AREAS.get(driver.get("transiting_body"))
    if transiting_area:
        return {transiting_area: 1.0}
    return {}


def project_driver(driver: dict) -> dict:
    values = contribution(driver)
    ranked = sorted(values.items(), key=lambda item: (-item[1], LIFE_AREAS.index(item[0])))[:2]
    driver = dict(driver)
    driver["raw_area_scores"] = {
        area: min(1.0, round(driver["weight"] * factor, 6))
        for area, factor in ranked
    }
    driver["tentative_area"] = (
        min(driver["raw_area_scores"], key=lambda area: (-driver["raw_area_scores"][area], LIFE_AREAS.index(area)))
        if driver["raw_area_scores"] else "self"
    )
    return driver
