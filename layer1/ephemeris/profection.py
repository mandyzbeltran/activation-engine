"""Annual profection calculation."""

from __future__ import annotations

from datetime import datetime
from math import floor
from typing import Any, Dict, List

from layer1.aggregate.scoring import score_profection
from layer1.ephemeris.common import ruler_for_sign, sign_for


def profection_house(age: int) -> int:
    if age < 0:
        raise ValueError("age must be non-negative")
    return age % 12 + 1


def compute_profection_events(
    natal: Dict[str, Any], start: datetime, end: datetime, config: dict
) -> List[dict]:
    if not natal["houses"]:
        return []
    age = floor((start - natal["birth_time"]).total_seconds() / (365.2425 * 86400))
    house = profection_house(age)
    cusp_sign = sign_for(natal["houses"][house]["lon"])
    traditional = ruler_for_sign(cusp_sign, "traditional")
    modern = ruler_for_sign(cusp_sign, "modern")
    active = traditional if config["profection_rulership"] == "traditional" else modern
    birthday_year = start.year if (start.month, start.day) >= (natal["birth_time"].month, natal["birth_time"].day) else start.year - 1
    birthday = natal["birth_time"].replace(year=birthday_year)
    next_birthday = birthday.replace(year=birthday_year + 1)
    year_lord_match = False
    return [{
        "kind": "profection",
        "technique": "profection",
        "start": birthday,
        "end": next_birthday,
        "peak": birthday,
        "peak_precision_hours": 24,
        "profection_house": house,
        "profection_lord_traditional": traditional,
        "profection_lord_modern": modern,
        "profection_lord_active": active,
        "year_lord_match": year_lord_match,
        "weight": float(score_profection(year_lord_match=year_lord_match, profection_house=house)),
        "kb_lookup_id": "profection-year-house-{0:02d}".format(house),
    }]
