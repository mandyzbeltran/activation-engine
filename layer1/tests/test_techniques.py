"""Direct smoke coverage for every MVP technique adapter."""

from copy import deepcopy
from datetime import timedelta

from layer1.aggregate.drivers import _merge_multipass
from layer1.ephemeris.common import parse_utc
from layer1.ephemeris.natal import compute_natal_chart
from layer1.ephemeris.profection import compute_profection_events
from layer1.ephemeris.progressions import compute_progression_events
from layer1.ephemeris.returns import compute_lunar_return_events, compute_solar_return_events
from layer1.ephemeris.transits import compute_transit_events
from layer1.post.hints import build_hints
from layer1.tests.synthetic_inputs import SYNTHETIC_INPUT


def test_all_mvp_technique_adapters_produce_events() -> None:
    natal = compute_natal_chart(SYNTHETIC_INPUT["birth"], SYNTHETIC_INPUT["config"])
    start = parse_utc("2026-01-01T00:00:00Z")
    one_year = parse_utc("2027-01-01T00:00:00Z")
    three_years = parse_utc("2029-01-01T00:00:00Z")
    assert compute_transit_events(natal, start, one_year)
    assert compute_profection_events(natal, start, one_year, SYNTHETIC_INPUT["config"])
    assert compute_progression_events(natal, start, three_years)
    assert compute_solar_return_events(natal, start, one_year)
    assert compute_lunar_return_events(natal, start, one_year)


def _pass_event(peak, *, retrograde: bool, body: str = "saturn") -> dict:
    return {
        "kind": "transit_to_natal",
        "transiting_body": body,
        "aspect": "square",
        "natal_target": "moon",
        "start": peak - timedelta(days=1),
        "end": peak + timedelta(days=1),
        "peak": peak,
        "weight": 1.0,
        "transiting_retrograde": retrograde,
        "_orb_factor_at_peak": 0.9,
    }


def test_multipass_requires_a_real_direct_retrograde_direct_sequence() -> None:
    start = parse_utc("2026-01-01T00:00:00Z")
    ordinary = [
        _pass_event(start + timedelta(days=index * 20), retrograde=False, body="moon")
        for index in range(3)
    ]
    _merge_multipass(ordinary)
    assert all("retrograde_passes" not in event for event in ordinary)
    assert [event["weight"] for event in ordinary] == [1.0, 1.0, 1.0]

    genuine = [
        _pass_event(start, retrograde=False),
        _pass_event(start + timedelta(days=60), retrograde=True),
        _pass_event(start + timedelta(days=120), retrograde=False),
    ]
    _merge_multipass(genuine)
    assert [event["weight"] for event in genuine] == [1.0, 0.85, 1.0]
    assert [item["phase"] for item in genuine[0]["retrograde_passes"]] == [
        "direct-1",
        "retrograde",
        "direct-2",
    ]
    assert len({event["start"] for event in genuine}) == 1
    assert len({event["end"] for event in genuine}) == 1

    partial = [
        _pass_event(start, retrograde=True),
        _pass_event(start + timedelta(days=60), retrograde=False),
    ]
    _merge_multipass(partial)
    assert [event["weight"] for event in partial] == [0.85, 1.0]
    assert [item["phase"] for item in partial[0]["retrograde_passes"]] == [
        "retrograde",
        "direct-2",
    ]


def test_planetary_return_is_not_filtered_from_transits() -> None:
    natal = compute_natal_chart(SYNTHETIC_INPUT["birth"], SYNTHETIC_INPUT["config"])
    natal = deepcopy(natal)
    start = parse_utc("2026-01-01T00:00:00Z")
    from layer1.ephemeris.common import planet_positions

    natal["planets"]["saturn"]["lon"] = planet_positions(start)["saturn"]["lon"]
    natal["houses"] = {}
    events = compute_transit_events(natal, start, start + timedelta(days=2))
    assert any(
        event["kb_lookup_id"] == "t-saturn-conjunction-n-saturn"
        for event in events
    )


def test_saturn_return_gets_the_contract_hint() -> None:
    hints = build_hints(
        "career",
        "growth",
        "forecast",
        [
            {
                "transiting_body": "saturn",
                "aspect": "conjunction",
                "natal_target": "saturn",
            }
        ],
    )
    assert hints["why_high_intensity"] == "saturn_return"
