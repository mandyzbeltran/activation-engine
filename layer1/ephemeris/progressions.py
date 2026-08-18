"""Secondary progression sign and natal-house ingress events."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from immanuel.const import calc, chart
from immanuel.tools import ephemeris, forecast

from layer1.aggregate.scoring import (
    score_progressed_moon_house,
    score_progressed_moon_sign,
    score_progressed_sun_sign_change,
)
from layer1.ephemeris.common import house_for, iter_days, julian_day, q6, sign_for


def _progressed_positions(natal: Dict[str, Any], value: datetime) -> dict:
    birth_jd = julian_day(natal["birth_time"])
    target_jd = julian_day(value)
    progressed_jd, _ = forecast.progression(
        jd=birth_jd,
        lat=0.0,
        lon=0.0,
        pjd=target_jd,
        house_system=chart.PLACIDUS,
        method=calc.NAIBOD,
    )
    moon = ephemeris.get_planet(chart.MOON, progressed_jd)
    sun = ephemeris.get_planet(chart.SUN, progressed_jd)
    return {
        "moon_lon": q6(moon["lon"]),
        "sun_lon": q6(sun["lon"]),
    }


def compute_progression_events(natal: Dict[str, Any], start: datetime, end: datetime) -> List[dict]:
    samples = [(day, _progressed_positions(natal, day)) for day in iter_days(start, end)]
    if len(samples) < 2:
        return []
    events: List[dict] = []
    previous_day, previous = samples[0]
    previous_moon_sign = sign_for(previous["moon_lon"])
    previous_sun_sign = sign_for(previous["sun_lon"])
    previous_house = house_for(previous["moon_lon"], natal["houses"]) if natal["houses"] else None

    for day, current in samples[1:]:
        moon_sign = sign_for(current["moon_lon"])
        sun_sign = sign_for(current["sun_lon"])
        moon_house = house_for(current["moon_lon"], natal["houses"]) if natal["houses"] else None
        if moon_sign != previous_moon_sign:
            events.append({
                "kind": "progressed_moon_sign",
                "technique": "progression",
                "start": day - timedelta(days=30),
                "end": day + timedelta(days=31),
                "peak": day,
                "peak_precision_hours": 24,
                "sign": moon_sign,
                "target_type": "planet",
                "natal_target": "moon",
                "weight": float(score_progressed_moon_sign(ingress_recent=True)),
                "kb_lookup_id": "pm-in-sign-{0}".format(moon_sign),
            })
        if moon_house is not None and moon_house != previous_house:
            events.append({
                "kind": "progressed_moon_house",
                "technique": "progression",
                "start": day - timedelta(days=30),
                "end": day + timedelta(days=31),
                "peak": day,
                "peak_precision_hours": 24,
                "house": moon_house,
                "target_type": "house",
                "natal_target": None,
                "weight": float(score_progressed_moon_house(ingress_recent=True)),
                "kb_lookup_id": "pm-in-house-{0:02d}".format(moon_house),
            })
        if sun_sign != previous_sun_sign:
            events.append({
                "kind": "progressed_sun_sign_change",
                "technique": "progression",
                "start": day - timedelta(days=180),
                "end": day + timedelta(days=181),
                "peak": day,
                "peak_precision_hours": 24,
                "sign": sun_sign,
                "target_type": "planet",
                "natal_target": "sun",
                "weight": float(score_progressed_sun_sign_change()),
                "kb_lookup_id": "progressed-sun-sign-change",
            })
        previous_day, previous = day, current
        previous_moon_sign = moon_sign
        previous_sun_sign = sun_sign
        previous_house = moon_house
    return events
