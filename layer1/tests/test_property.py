"""Layer 1 deterministic and contract properties."""

from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import random

from layer1 import compute_activations, serialize_activations
from layer1.aggregate.scoring import noisy_or, score_transit_to_natal
from layer1.aggregate.time_bucket import classify_time_scale
from layer1.ephemeris.profection import profection_house
from layer1.post.sort_hash import activation_hash
from layer1.tests.synthetic_inputs import SYNTHETIC_INPUT


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def test_p1_idempotent_byte_output() -> None:
    first = compute_activations(SYNTHETIC_INPUT)
    second = compute_activations(SYNTHETIC_INPUT)
    assert serialize_activations(first) == serialize_activations(second)
    assert b'"intensity":0.' in serialize_activations(first)


def test_p2_decreasing_orb_does_not_decrease_score() -> None:
    closer = score_transit_to_natal(transiting_body="saturn", natal_target="venus", aspect="square", angular_distance_deg="90.2", phase="applying")
    farther = score_transit_to_natal(transiting_body="saturn", natal_target="venus", aspect="square", angular_distance_deg="91.2", phase="applying")
    assert closer >= farther


def test_p3_unsupported_config_version_fails_loudly() -> None:
    first = deepcopy(SYNTHETIC_INPUT)
    first["birth"]["time_known"] = False
    first["window"]["end_utc"] = "2026-09-03T00:00:00Z"
    second = deepcopy(first)
    second["config"]["version"] = "layer1@2026.08.17.2"
    try:
        compute_activations(second)
    except ValueError as error:
        assert "unsupported config version" in str(error)
    else:
        raise AssertionError("unsupported config versions must fail loudly")


def test_p6_every_driver_has_deterministic_fallback_keywords() -> None:
    activations = compute_activations(SYNTHETIC_INPUT)
    assert all(
        driver.get("keywords")
        for activation in activations
        for driver in activation["drivers"]
    )


def test_p7_life_area_scores_are_mvp_only() -> None:
    allowed = {"career", "wealth", "relationships", "family"}
    assert all(set(item["life_area_scores"]) <= allowed for item in compute_activations(SYNTHETIC_INPUT))


def test_p8_emit_reparse_hash_is_stable_and_boundary_sensitive() -> None:
    activation = next(
        item
        for item in compute_activations(SYNTHETIC_INPUT)
        if all(driver["kind"] != "foundation" for driver in item["drivers"])
    )
    reparsed_drivers = json.loads(json.dumps(activation["drivers"]))
    assert (
        activation_hash(activation, SYNTHETIC_INPUT["config"], reparsed_drivers)
        == activation["activation_id"]
    )
    changed = deepcopy(reparsed_drivers)
    changed[0]["weight"] = round(changed[0]["weight"] + 0.001, 6)
    assert (
        activation_hash(activation, SYNTHETIC_INPUT["config"], changed)
        != activation["activation_id"]
    )


def test_p9_profection_formula_for_ages_zero_to_100() -> None:
    assert all(profection_house(age) == age % 12 + 1 for age in range(101))


def test_p10_noisy_or_eight_halves_does_not_reach_one() -> None:
    result = noisy_or((("drv_{0}".format(index), "0.5") for index in range(8)))
    assert result == Decimal("0.996000")


def test_p11_year_lord_match_only_changes_profection_channel() -> None:
    from layer1.aggregate.scoring import score_profection
    transit = score_transit_to_natal(transiting_body="saturn", natal_target="venus", aspect="square", angular_distance_deg="90.7", phase="applying")
    without_match = score_profection(year_lord_match=False, profection_house=11)
    with_match = score_profection(year_lord_match=True, profection_house=11)
    assert transit == score_transit_to_natal(transiting_body="saturn", natal_target="venus", aspect="square", angular_distance_deg="90.7", phase="applying")
    assert with_match > without_match


def test_p12_time_scale_is_order_independent() -> None:
    start = datetime(2026, 1, 1)
    drivers = [
        {"kind": "transit_to_natal", "technique": "transit", "transiting_body": "mars", "target_type": "planet", "start": start, "end": start + timedelta(days=12)},
        {"kind": "profection", "technique": "profection", "start": start, "end": start + timedelta(days=365)},
    ]
    assert classify_time_scale(drivers) == classify_time_scale(reversed(drivers)) == "year"


def test_twenty_seeded_short_windows_do_not_crash() -> None:
    rng = random.Random(20260813)
    for index in range(20):
        request = deepcopy(SYNTHETIC_INPUT)
        request["birth"]["lat"] = rng.uniform(-65, 65)
        request["birth"]["lon"] = rng.uniform(-179, 179)
        request["birth"]["time_known"] = bool(index % 2)
        start = datetime(2026, 1, 1) + timedelta(days=rng.randrange(300))
        request["window"]["start_utc"] = start.isoformat() + "Z"
        request["window"]["end_utc"] = (start + timedelta(days=2)).isoformat() + "Z"
        assert compute_activations(request)
