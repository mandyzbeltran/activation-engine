"""Controlled-vocabulary equality gate."""

import json
from pathlib import Path

from layer1 import enums
from layer1.aggregate.mapping import MVP_AREAS, contribution
from layer1.aggregate.polarity import _base


def test_layer1_enums_equal_checked_in_controlled_vocab() -> None:
    path = Path(__file__).parents[1] / "schema" / "controlled-vocab.yaml"
    vocab = json.loads(path.read_text(encoding="utf-8"))
    actual = {
        "systems": list(enums.SYSTEMS), "techniques": list(enums.TECHNIQUES),
        "planets": list(enums.PLANETS), "signs": list(enums.SIGNS),
        "aspects": list(enums.ASPECTS), "houses": list(enums.HOUSES),
        "angles": list(enums.ANGLES), "life_areas": list(enums.LIFE_AREAS),
        "time_scales": list(enums.TIME_SCALES), "polarities": list(enums.POLARITIES),
        "intensities": list(enums.INTENSITIES), "target_types": list(enums.TARGET_TYPES),
    }
    assert actual == vocab


def test_coarse_public_life_area_fallbacks_are_self_contained() -> None:
    assert MVP_AREAS == ("career", "wealth", "relationships", "family")
    assert contribution({"kind": "transit_to_natal", "house": 10}) == {"career": 1.0}
    assert contribution({"kind": "transit_to_natal", "natal_target": "mc"}) == {"career": 1.0}


def test_public_polarity_fallback_does_not_require_kb_metadata() -> None:
    vector = _base(
        {
            "kind": "transit_to_natal",
            "technique": "transit",
            "transiting_body": "uranus",
            "aspect": "square",
        }
    )
    assert float(vector["growth"]) == 0.5
    assert float(vector["challenging"]) == 0.5
    assert float(vector["neutral"]) == 0.0
