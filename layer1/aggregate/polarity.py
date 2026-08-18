"""Weight-aware polarity pipeline from Layer 1 specification section 5."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Tuple

from layer1.aggregate.scoring import quantize6
from layer1.enums import POLARITIES


def _base(driver: dict) -> dict:
    if driver["kind"] == "foundation":
        labels = ("neutral",)
    elif driver["technique"] == "profection":
        lord = driver.get("profection_lord_active")
        if lord in ("saturn", "pluto"):
            labels = ("challenging", "growth")
        elif lord in ("jupiter", "venus"):
            labels = ("supportive",)
        elif lord == "mars":
            labels = ("challenging",)
        else:
            labels = ("neutral",)
    elif driver.get("aspect") in ("square", "opposition"):
        labels = ("challenging", "growth")
    elif driver.get("aspect") in ("trine", "sextile"):
        labels = ("supportive",)
    elif driver.get("transiting_body") in ("saturn", "pluto"):
        labels = ("challenging", "growth")
    elif driver["technique"] in ("progression", "solar_return"):
        labels = ("growth",)
    else:
        labels = ("neutral",)
    share = Decimal("1") / Decimal(len(labels))
    return {name: (share if name in labels else Decimal("0")) for name in POLARITIES}


def polarity_pipeline(drivers: Iterable[dict], intensity: float) -> Tuple[dict, str]:
    totals = {name: Decimal("0") for name in POLARITIES}
    for driver in drivers:
        vector = _base(driver)
        if driver.get("aspect") in ("square", "opposition"):
            vector["challenging"] += Decimal("0.15")
        elif driver.get("aspect") in ("trine", "sextile"):
            vector["supportive"] += Decimal("0.15")
        if driver.get("transiting_body") in ("saturn", "pluto"):
            vector["challenging"] += Decimal("0.10")
        elif driver.get("transiting_body") in ("jupiter", "venus"):
            vector["supportive"] += Decimal("0.10")
        weight = Decimal(str(driver["weight"]))
        for name in POLARITIES:
            totals[name] += vector[name] * weight
    total = sum(totals.values())
    if not total:
        totals["neutral"] = Decimal("1")
        total = Decimal("1")
    mix = {name: float(quantize6(totals[name] / total)) for name in POLARITIES}
    # Make the six-decimal vector sum exactly to one without changing ordering.
    difference = round(1.0 - sum(mix.values()), 6)
    mix[max(POLARITIES, key=lambda name: mix[name])] = round(mix[max(POLARITIES, key=lambda name: mix[name])] + difference, 6)
    challenging, supportive = mix["challenging"], mix["supportive"]
    if challenging >= 0.60 and supportive < 0.15:
        label = "challenging"
    elif supportive >= 0.60 and challenging < 0.15:
        label = "supportive"
    elif 0.30 <= challenging <= 0.60 and 0.15 <= supportive <= 0.50:
        label = "growth"
    elif all(value < 0.30 for value in mix.values()) and intensity < 0.30:
        label = "neutral"
    else:
        label = max(POLARITIES, key=lambda name: (mix[name], -POLARITIES.index(name)))
    return mix, label
