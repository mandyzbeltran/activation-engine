"""Solar and lunar return event calculations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from immanuel.const import chart
from immanuel.tools import date, ephemeris, forecast

from layer1.aggregate.scoring import score_return
from layer1.ephemeris.common import (
    HOUSE_SYSTEM_INDEX,
    PLANET_INDEX,
    angle_positions,
    house_cusps,
    house_for,
    julian_day,
    q6,
    ruler_for_sign,
    sign_for,
    signed_difference,
)


def _solar_return_jd(natal: Dict[str, Any], year: int) -> float:
    return forecast.solar_return(julian_day(natal["birth_time"]), year)


def compute_solar_return_events(natal: Dict[str, Any], start: datetime, end: datetime) -> List[dict]:
    if not natal["houses"]:
        return []
    lat = float(natal.get("lat", 0.0))
    lon = float(natal.get("lon", 0.0))
    events: List[dict] = []
    for year in range(start.year - 1, end.year + 1):
        sr_jd = _solar_return_jd(natal, year)
        next_jd = _solar_return_jd(natal, year + 1)
        sr_time = date.to_datetime(sr_jd)
        next_time = date.to_datetime(next_jd)
        if next_time <= start or sr_time >= end:
            continue
        houses = house_cusps(sr_time, lat, lon, natal["house_system"])
        angles = angle_positions(sr_time, lat, lon, natal["house_system"])
        objects = {
            name: ephemeris.get_planet(index, sr_jd)
            for name, index in PLANET_INDEX.items()
        }
        asc_sign = sign_for(angles["asc"])
        asc_ruler = ruler_for_sign(asc_sign, "traditional")
        asc_ruler_house = house_for(objects[asc_ruler]["lon"], houses)
        moon_house = house_for(objects["moon"]["lon"], houses)
        common = {
            "technique": "solar_return", "start": sr_time, "end": next_time,
            "peak": sr_time, "peak_precision_hours": 24,
            "weight": float(score_return(technique="solar_return", specific_factor="1")),
        }
        events.extend((
            dict(common, kind="solar_return_asc", sign=asc_sign, target_type="angle", natal_target="asc", kb_lookup_id="sr-asc-{0}".format(asc_sign)),
            dict(common, kind="solar_return_asc_ruler_house", house=asc_ruler_house, target_type="house", natal_target=None, kb_lookup_id="sr-asc-ruler-house-{0:02d}".format(asc_ruler_house)),
            dict(common, kind="solar_return_moon_house", house=moon_house, target_type="house", natal_target="moon", kb_lookup_id="sr-moon-house-{0:02d}".format(moon_house)),
        ))
        counts: Dict[int, int] = {}
        for values in objects.values():
            house = house_for(values["lon"], houses)
            counts[house] = counts.get(house, 0) + 1
        for house, count in sorted(counts.items()):
            if count >= 3:
                events.append(dict(common, kind="solar_return_stellium_house", house=house, target_type="house", natal_target=None, kb_lookup_id="sr-stellium-house-{0:02d}".format(house)))
    return events


def _lunar_crossings(natal_moon_lon: float, start: datetime, end: datetime) -> List[datetime]:
    crossings: List[datetime] = []
    step = timedelta(hours=6)
    left = start
    left_diff = signed_difference(
        ephemeris.get_planet(chart.MOON, julian_day(left))["lon"], natal_moon_lon
    )
    current = left + step
    while current <= end:
        current_diff = signed_difference(
            ephemeris.get_planet(chart.MOON, julian_day(current))["lon"], natal_moon_lon
        )
        if left_diff == 0 or (left_diff * current_diff < 0 and abs(left_diff) < 30 and abs(current_diff) < 30):
            low, high = left, current
            for _ in range(24):
                middle = low + (high - low) / 2
                middle_diff = signed_difference(
                    ephemeris.get_planet(chart.MOON, julian_day(middle))["lon"], natal_moon_lon
                )
                if left_diff * middle_diff <= 0:
                    high = middle
                    current_diff = middle_diff
                else:
                    low = middle
                    left_diff = middle_diff
            found = (low + (high - low) / 2).replace(microsecond=0)
            if not crossings or found - crossings[-1] > timedelta(days=20):
                crossings.append(found)
        left, left_diff = current, current_diff
        current += step
    return crossings


def compute_lunar_return_events(natal: Dict[str, Any], start: datetime, end: datetime) -> List[dict]:
    if not natal["houses"]:
        return []
    crossings = _lunar_crossings(natal["planets"]["moon"]["lon"], start - timedelta(days=32), end + timedelta(days=32))
    events = []
    for index in range(len(crossings) - 1):
        peak, next_peak = crossings[index], crossings[index + 1]
        if next_peak <= start or peak >= end:
            continue
        moon = ephemeris.get_planet(chart.MOON, julian_day(peak))
        house = house_for(moon["lon"], natal["houses"])
        events.append({
            "kind": "lunar_return_moon_house",
            "technique": "lunar_return",
            "start": peak,
            "end": next_peak,
            "peak": peak,
            "peak_precision_hours": 24,
            "house": house,
            "target_type": "house",
            "natal_target": "moon",
            "weight": float(score_return(technique="lunar_return", specific_factor="1")),
            "kb_lookup_id": "lr-moon-house-{0:02d}".format(house),
        })
    return events
