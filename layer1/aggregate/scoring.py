"""Deterministic implementation of Layer 1 specification section 4."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable, Tuple, Union

from layer1.config import (
    ANGLE_WEIGHTS,
    BASE_PROFECTION,
    ORB_LIMITS,
    PLANET_WEIGHTS,
    TECHNIQUE_WEIGHTS,
)

DecimalLike = Union[Decimal, str, int, float]
SIX_PLACES = Decimal("0.000001")
THREE_PLACES = Decimal("0.001")
ZERO = Decimal("0")
ONE = Decimal("1")


def decimal(value: DecimalLike) -> Decimal:
    """Convert without inheriting binary floating-point representation noise."""

    return value if isinstance(value, Decimal) else Decimal(str(value))


def quantize6(value: DecimalLike) -> Decimal:
    return decimal(value).quantize(SIX_PLACES, rounding=ROUND_HALF_EVEN)


def quantize3(value: DecimalLike) -> Decimal:
    return decimal(value).quantize(THREE_PLACES, rounding=ROUND_HALF_EVEN)


def clamp01(value: DecimalLike) -> Decimal:
    return min(ONE, max(ZERO, decimal(value)))


def _aspect_family(aspect: str) -> str:
    if aspect in ("conjunction", "opposition"):
        return "conjunction_opposition"
    if aspect == "square":
        return "square"
    if aspect in ("trine", "sextile"):
        return "trine_sextile"
    raise ValueError("unsupported aspect: {0}".format(aspect))


def _target_category(target: str) -> str:
    if target in ANGLE_WEIGHTS:
        return "angle"
    if target in ("sun", "moon"):
        return "luminary"
    if target in ("mercury", "venus", "mars"):
        return "inner"
    if target in ("jupiter", "saturn"):
        return "social"
    if target in ("uranus", "neptune", "pluto"):
        return "outer"
    raise ValueError("unsupported natal target: {0}".format(target))


def _transit_channel(body: str) -> str:
    if body in ("saturn", "uranus", "neptune", "pluto"):
        return "transit_outer"
    if body == "jupiter":
        return "transit_jupiter"
    if body in ("sun", "moon", "mercury", "venus", "mars"):
        return "transit_inner"
    raise ValueError("unsupported transiting body: {0}".format(body))


def orb_factor(aspect: str, target: str, angular_distance_deg: DecimalLike) -> Decimal:
    """Return ``max(0, 1 - abs(delta - exact_angle) / orb_limit)``."""

    exact_angles = {
        "conjunction": Decimal("0"),
        "sextile": Decimal("60"),
        "square": Decimal("90"),
        "trine": Decimal("120"),
        "opposition": Decimal("180"),
    }
    try:
        exact = exact_angles[aspect]
    except KeyError as exc:
        raise ValueError("unsupported aspect: {0}".format(aspect)) from exc
    orb = ORB_LIMITS[_aspect_family(aspect)][_target_category(target)]
    distance_from_exact = abs(decimal(angular_distance_deg) - exact)
    return quantize6(max(ZERO, ONE - distance_from_exact / orb))


def score_transit_to_natal(
    *,
    transiting_body: str,
    natal_target: str,
    aspect: str,
    angular_distance_deg: DecimalLike,
    phase: str,
    stationary: bool = False,
    natal_prominent: bool = False,
) -> Decimal:
    """Calculate a canonical emitted transit driver weight.

    The checkpoint fixture explicitly rounds the driver score to 3 decimals
    before emitting it at 6 decimals. This behavior is isolated here pending
    owner resolution of the section 4.3 precision ambiguity.
    """

    if phase not in ("applying", "exact", "separating"):
        raise ValueError("unsupported phase: {0}".format(phase))
    target_weight = ANGLE_WEIGHTS.get(natal_target, PLANET_WEIGHTS.get(natal_target))
    if target_weight is None:
        raise ValueError("unsupported natal target: {0}".format(natal_target))
    factors = (
        TECHNIQUE_WEIGHTS[_transit_channel(transiting_body)],
        PLANET_WEIGHTS[transiting_body],
        target_weight,
        orb_factor(aspect, natal_target, angular_distance_deg),
        Decimal("1.10") if phase == "applying" else ONE,
        Decimal("1.20") if stationary else ONE,
        Decimal("1.10") if natal_prominent else ONE,
    )
    result = ONE
    for factor in factors:
        result = quantize6(result * factor)
    return quantize6(quantize3(clamp01(result)))


def score_profection(*, year_lord_match: bool, profection_house: int) -> Decimal:
    if not 1 <= profection_house <= 12:
        raise ValueError("profection_house must be in 1..12")
    result = BASE_PROFECTION
    result = quantize6(result * (Decimal("1.20") if year_lord_match else ONE))
    result = quantize6(
        result * (Decimal("1.10") if profection_house in (1, 4, 7, 10) else ONE)
    )
    return quantize6(quantize3(clamp01(result)))


def score_progressed_moon_house(*, ingress_recent: bool) -> Decimal:
    bonus = Decimal("1.15") if ingress_recent else ONE
    return quantize6(quantize3(clamp01(Decimal("0.45") * bonus)))


def score_progressed_moon_sign(*, ingress_recent: bool) -> Decimal:
    bonus = Decimal("1.15") if ingress_recent else ONE
    return quantize6(quantize3(clamp01(Decimal("0.50") * bonus)))


def score_progressed_sun_sign_change() -> Decimal:
    return Decimal("0.850000")


def score_return(*, technique: str, specific_factor: DecimalLike) -> Decimal:
    if technique == "solar_return":
        cap = Decimal("0.70")
    elif technique == "lunar_return":
        cap = Decimal("0.50")
    else:
        raise ValueError("technique must be solar_return or lunar_return")
    result = TECHNIQUE_WEIGHTS[technique] * decimal(specific_factor)
    return quantize6(quantize3(min(cap, clamp01(result))))


def score_transit_through_house(
    *,
    transiting_body: str,
    days_remaining_in_house: DecimalLike,
    expected_dwell_days: DecimalLike,
) -> Decimal:
    expected = decimal(expected_dwell_days)
    if expected <= ZERO:
        raise ValueError("expected_dwell_days must be positive")
    dwell_factor = min(ONE, max(ZERO, decimal(days_remaining_in_house) / expected))
    result = (
        TECHNIQUE_WEIGHTS[_transit_channel(transiting_body)]
        * PLANET_WEIGHTS[transiting_body]
        * Decimal("0.85")
        * dwell_factor
    )
    return quantize6(quantize3(clamp01(result)))


def score_foundation() -> Decimal:
    return Decimal("0.150000")


def noisy_or(weighted_drivers: Iterable[Tuple[str, DecimalLike]]) -> Decimal:
    """Combine weights in deterministic ``driver_id`` order."""

    complement_product = ONE
    for _, weight in sorted(weighted_drivers, key=lambda item: item[0]):
        complement_product = quantize6(
            complement_product * (ONE - clamp01(weight))
        )
    return quantize6(quantize3(clamp01(ONE - complement_product)))

