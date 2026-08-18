"""Deterministic helpers around Immanuel's Swiss Ephemeris adapters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, Iterable, Iterator, Tuple

import swisseph as swe
from immanuel.const import chart
from immanuel.tools import date, ephemeris, position

from layer1.enums import PLANETS, SIGNS

PLANET_INDEX = {
    "sun": chart.SUN,
    "moon": chart.MOON,
    "mercury": chart.MERCURY,
    "venus": chart.VENUS,
    "mars": chart.MARS,
    "jupiter": chart.JUPITER,
    "saturn": chart.SATURN,
    "uranus": chart.URANUS,
    "neptune": chart.NEPTUNE,
    "pluto": chart.PLUTO,
}
ANGLE_INDEX = {
    "asc": chart.ASC,
    "dsc": chart.DESC,
    "mc": chart.MC,
    "ic": chart.IC,
}
HOUSE_SYSTEM_INDEX = {
    "placidus": chart.PLACIDUS,
    "whole_sign": chart.WHOLE_SIGN,
}

TRADITIONAL_RULERS = {
    "aries": "mars", "taurus": "venus", "gemini": "mercury",
    "cancer": "moon", "leo": "sun", "virgo": "mercury",
    "libra": "venus", "scorpio": "mars", "sagittarius": "jupiter",
    "capricorn": "saturn", "aquarius": "saturn", "pisces": "jupiter",
}
MODERN_RULERS = dict(
    TRADITIONAL_RULERS,
    scorpio="pluto",
    aquarius="uranus",
    pisces="neptune",
)


def q6(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.000001"), ROUND_HALF_EVEN))


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    value = value.astimezone(timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def iter_days(start: datetime, end: datetime) -> Iterator[datetime]:
    current = start
    while current < end:
        yield current
        current += timedelta(days=1)


def julian_day(value: datetime) -> float:
    return date.to_jd(value.astimezone(timezone.utc))


def planet_positions(value: datetime) -> Dict[str, dict]:
    raw = ephemeris.get_objects(
        [PLANET_INDEX[name] for name in PLANETS],
        julian_day(value),
    )
    return {
        name: {
            "lon": q6(raw[index]["lon"]),
            "speed": q6(raw[index]["speed"]),
        }
        for name, index in PLANET_INDEX.items()
    }


def angle_positions(value: datetime, lat: float, lon: float, house_system: str) -> Dict[str, float]:
    raw = ephemeris.get_angles(
        julian_day(value), lat, lon, HOUSE_SYSTEM_INDEX[house_system]
    )
    return {name: q6(raw[index]["lon"]) for name, index in ANGLE_INDEX.items()}


def house_cusps(value: datetime, lat: float, lon: float, house_system: str) -> Dict[int, dict]:
    raw = ephemeris.get_houses(
        julian_day(value), lat, lon, HOUSE_SYSTEM_INDEX[house_system]
    )
    return {
        item["number"]: {
            "lon": q6(item["lon"]),
            "size": q6(item["size"]),
        }
        for item in raw.values()
    }


def house_for(longitude: float, houses: Dict[int, dict]) -> int:
    compatible = {
        chart.HOUSE + number: dict(values, number=number)
        for number, values in houses.items()
    }
    result = position.house(longitude, compatible)
    if not result:
        raise ValueError("longitude did not resolve to a house")
    return int(result["number"])


def sign_for(longitude: float) -> str:
    return SIGNS[int(longitude % 360) // 30]


def angular_distance(first: float, second: float) -> float:
    return q6(abs(swe.difdeg2n(first, second)))


def signed_difference(first: float, second: float) -> float:
    return q6(swe.difdeg2n(first, second))


def ruler_for_sign(sign: str, mode: str) -> str:
    return (MODERN_RULERS if mode == "modern" else TRADITIONAL_RULERS)[sign]


def sample_stationary(body: str, peak: datetime) -> bool:
    for offset in range(-72, 73, 6):
        sample = peak + timedelta(hours=offset)
        raw = ephemeris.get_planet(PLANET_INDEX[body], julian_day(sample))
        if abs(raw["speed"]) < 0.01:
            return True
    return False

