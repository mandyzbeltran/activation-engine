"""Regression checks for the section 11.2 multi-pass fixture."""

from decimal import Decimal

from layer1.aggregate.scoring import noisy_or
from layer1.aggregate.time_bucket import classify_time_scale


def test_saturn_three_pass_time_scale_is_year() -> None:
    drivers = [{
        "kind": "transit_to_natal", "technique": "transit",
        "transiting_body": "saturn", "target_type": "planet",
        "start": __import__("datetime").datetime(2026, 8, 1),
        "end": __import__("datetime").datetime(2027, 5, 15),
    }]
    assert classify_time_scale(drivers) == "year"


def test_fixture_weights_follow_noisy_or_formula() -> None:
    # The corrected section 11.2 fixture follows the mandatory noisy-OR formula.
    assert noisy_or((("drv_1", "0.480"), ("drv_2", "0.408"), ("drv_3", "0.470"))) == Decimal("0.837000")
