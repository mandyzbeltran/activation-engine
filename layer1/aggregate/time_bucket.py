"""Pure time-scale classification."""

from __future__ import annotations

from typing import Iterable

ORDER = {"days": 0, "weeks": 1, "months": 2, "year": 3, "multi_year": 4}


def driver_time_scale(driver: dict) -> str:
    duration_days = (driver["end"] - driver["start"]).total_seconds() / 86400
    kind = driver["kind"]
    if kind == "foundation":
        return "months"
    if kind == "profection" or driver["technique"] == "solar_return":
        return "year"
    if driver["technique"] == "lunar_return":
        return "months"
    if kind in ("progressed_moon_house", "progressed_moon_sign"):
        return "months"
    if kind == "progressed_sun_sign_change":
        return "multi_year"
    body = driver.get("transiting_body")
    if body == "moon" or duration_days <= 7:
        return "days"
    if body in ("mercury", "venus", "mars", "sun") and duration_days <= 28:
        return "weeks"
    if body in ("uranus", "neptune", "pluto"):
        return "multi_year"
    if driver.get("target_type") == "angle" and body in ("jupiter", "saturn", "uranus", "neptune", "pluto"):
        return "multi_year"
    if body in ("jupiter", "saturn") and duration_days > 180:
        return "year"
    return "months"


def classify_time_scale(drivers: Iterable[dict]) -> str:
    return max((driver_time_scale(driver) for driver in drivers), key=lambda value: ORDER[value])
