"""Versioned scoring constants frozen by the Layer 1 specification."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict

CONFIG_VERSION = "layer1@2026.08.17.1"
MAX_DRIVERS_PER_ACTIVATION = 8
BASE_PROFECTION = Decimal("0.35")

PLANET_WEIGHTS: Dict[str, Decimal] = {
    "sun": Decimal("1.00"),
    "moon": Decimal("1.00"),
    "mercury": Decimal("0.50"),
    "venus": Decimal("0.60"),
    "mars": Decimal("0.70"),
    "jupiter": Decimal("0.85"),
    "saturn": Decimal("0.90"),
    "uranus": Decimal("0.85"),
    "neptune": Decimal("0.85"),
    "pluto": Decimal("0.90"),
}

ANGLE_WEIGHTS: Dict[str, Decimal] = {
    "asc": Decimal("1.00"),
    "mc": Decimal("1.00"),
    "ic": Decimal("0.85"),
    "dsc": Decimal("0.85"),
}

TECHNIQUE_WEIGHTS: Dict[str, Decimal] = {
    "transit_outer": Decimal("0.70"),
    "transit_jupiter": Decimal("0.55"),
    "transit_inner": Decimal("0.30"),
    "solar_return": Decimal("0.55"),
    "lunar_return": Decimal("0.35"),
    "progression": Decimal("0.50"),
    "foundation": Decimal("0.00"),
}

# Rows are aspect families; columns describe the natal target category.
ORB_LIMITS: Dict[str, Dict[str, Decimal]] = {
    "conjunction_opposition": {
        "luminary": Decimal("10"),
        "inner": Decimal("7"),
        "social": Decimal("6"),
        "outer": Decimal("5"),
        "angle": Decimal("4"),
    },
    "square": {
        "luminary": Decimal("8"),
        "inner": Decimal("6"),
        "social": Decimal("5"),
        "outer": Decimal("4"),
        "angle": Decimal("3"),
    },
    "trine_sextile": {
        "luminary": Decimal("6"),
        "inner": Decimal("5"),
        "social": Decimal("4"),
        "outer": Decimal("3"),
        "angle": Decimal("2"),
    },
}
