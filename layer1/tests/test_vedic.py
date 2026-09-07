"""D1 tests use only the synthetic J2000 equatorial reference fixture."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta

from fastapi.testclient import TestClient
import pytest
import swisseph as swe

from layer1.ephemeris.common import iso_z, julian_day, parse_utc
from layer1.ephemeris.natal import summarize_natal_chart
from layer1.ephemeris.vedic import (
    CLASSICAL_BODIES,
    NAKSHATRAS,
    NAKSHATRA_LORDS,
    VEDIC_CONFIG_VERSION,
    nakshatra_for,
    summarize_vedic_natal_chart,
)
from layer1.http_api import create_app
from layer1.tests.synthetic_inputs import SYNTHETIC_CIVIL_BIRTH, SYNTHETIC_INPUT


def test_d1_fixed_configuration_and_synthetic_reference():
    summary = summarize_vedic_natal_chart(SYNTHETIC_INPUT["birth"])
    assert summary["system"] == "vedic"
    assert summary["zodiac_system"] == "sidereal"
    assert summary["ayanamsha"] == "lahiri"
    assert summary["node_type"] == "mean"
    assert summary["house_system"] == "whole_sign"
    assert summary["config_version"] == VEDIC_CONFIG_VERSION
    assert summary["ayanamsha_deg"] == pytest.approx(23.853222, abs=0.000002)
    assert summary["planets"]["sun"]["longitude_deg"] == pytest.approx(256.515696, abs=0.000002)
    assert summary["planets"]["sun"]["sign"] == "sagittarius"
    assert summary["planets"]["sun"]["nakshatra"] == {
        "index": 20, "name": "purva_ashadha", "pada": 1, "lord": "venus",
    }
    assert summary["ascendant"]["longitude_deg"] == pytest.approx(347.520677, abs=0.000002)
    assert summary["ascendant"]["sign"] == "pisces"
    assert summary["ascendant"]["house"] == 1
    assert set(summary["planets"]) == set(CLASSICAL_BODIES) | {"ketu"}
    assert "aspects" not in summary
    assert "confidence" not in summary
    assert "angles" not in summary
    assert summary["birth_data_precision"] == "known"


def test_d1_whole_sign_geometry_and_opposite_mean_nodes():
    summary = summarize_vedic_natal_chart(SYNTHETIC_INPUT["birth"])
    assert list(summary["houses"]) == [str(number) for number in range(1, 13)]
    first = summary["houses"]["1"]["lon"]
    for number, house in summary["houses"].items():
        assert house["size"] == 30.0
        assert house["lon"] == (first + (int(number) - 1) * 30) % 360
    for point in summary["planets"].values():
        longitude = point["longitude_deg"]
        assert 0 <= longitude < 360
        assert 1 <= point["house"] <= 12
        house_start = summary["houses"][str(point["house"])]["lon"]
        assert (longitude - house_start) % 360 < 30
    rahu, ketu = (summary["planets"][name] for name in ("rahu", "ketu"))
    assert (ketu["longitude_deg"] - rahu["longitude_deg"]) % 360 == pytest.approx(180)
    assert rahu["retrograde"] is True
    assert ketu["retrograde"] is True


def test_all_nakshatra_pada_boundaries_and_wraparound():
    for quarter in range(108):
        longitude = quarter * 10 / 3
        mansion = nakshatra_for(longitude)
        assert mansion == {
            "index": quarter // 4 + 1,
            "name": NAKSHATRAS[quarter // 4],
            "pada": quarter % 4 + 1,
            "lord": NAKSHATRA_LORDS[(quarter // 4) % 9],
        }
        before = nakshatra_for(longitude - 1e-8)
        previous = (quarter - 1) % 108
        assert before["index"] == previous // 4 + 1
        assert before["pada"] == previous % 4 + 1
    assert nakshatra_for(360) == nakshatra_for(0)
    assert nakshatra_for(-0.000001)["name"] == "revati"
    assert nakshatra_for(-1e-14) == {
        "index": 27, "name": "revati", "pada": 4, "lord": "mercury",
    }


def test_d1_matches_direct_lahiri_sidereal_api_and_mean_node():
    birth = SYNTHETIC_INPUT["birth"]
    jd = julian_day(parse_utc(birth["utc_iso"]))
    summary = summarize_vedic_natal_chart(birth)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    try:
        for name, body in CLASSICAL_BODIES.items():
            position, _ = swe.calc_ut(jd, body, swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL)
            assert summary["planets"][name]["longitude_deg"] == pytest.approx(position[0], abs=1e-10)
            assert summary["planets"][name]["retrograde"] is (position[3] < 0)
        true_node, _ = swe.calc_ut(jd, swe.TRUE_NODE, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
        assert abs(summary["planets"]["rahu"]["longitude_deg"] - true_node[0]) > 0.01
    finally:
        swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY)


def test_mode_reset_and_unchanged_tropical_results_after_d1():
    birth = SYNTHETIC_INPUT["birth"]
    jd = julian_day(parse_utc(birth["utc_iso"]))
    swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY)
    baseline_ayanamsha = swe.get_ayanamsa_ut(jd)
    baseline_tropical = swe.calc_ut(jd, swe.MOON)
    baseline_western = summarize_natal_chart(birth, SYNTHETIC_INPUT["config"])
    summarize_vedic_natal_chart(birth)
    assert swe.get_ayanamsa_ut(jd) == baseline_ayanamsha
    assert swe.calc_ut(jd, swe.MOON) == baseline_tropical
    assert summarize_natal_chart(birth, SYNTHETIC_INPUT["config"]) == baseline_western


def test_mode_reset_even_when_native_calculation_fails(monkeypatch):
    birth = SYNTHETIC_INPUT["birth"]
    jd = julian_day(parse_utc(birth["utc_iso"]))
    swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY)
    baseline = swe.get_ayanamsa_ut(jd)

    def unavailable(*args, **kwargs):
        raise swe.Error("synthetic unavailable ephemeris")

    monkeypatch.setattr(swe, "calc_ut", unavailable)
    with pytest.raises(ValueError, match="sidereal ephemeris calculation is unavailable"):
        summarize_vedic_natal_chart(birth)
    assert swe.get_ayanamsa_ut(jd) == baseline


def test_concurrent_tropical_and_sidereal_calculations_remain_separate():
    cases = []
    for days in range(8):
        birth = deepcopy(SYNTHETIC_INPUT["birth"])
        birth["utc_iso"] = iso_z(parse_utc(birth["utc_iso"]) + timedelta(days=days))
        cases.extend([(False, birth), (True, birth)])

    def calculate(case):
        sidereal, birth = case
        if sidereal:
            return summarize_vedic_natal_chart(birth)
        jd = julian_day(parse_utc(birth["utc_iso"]))
        return swe.calc_ut(jd, swe.MOON)

    expected = [calculate(case) for case in cases]
    with ThreadPoolExecutor(max_workers=4) as pool:
        actual = list(pool.map(calculate, cases * 4))
    assert actual == expected * 4


def test_http_d1_no_birth_input_echo_and_no_western_fallback():
    client = TestClient(create_app())
    response = client.post("/v1/vedic/natal-summary", json={"birth": SYNTHETIC_CIVIL_BIRTH})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data_source", "natal_summary"}
    assert payload["data_source"] == "swiss_ephemeris"
    assert payload["natal_summary"]["system"] == "vedic"
    assert payload["natal_summary"]["config_version"] == "vedic-d1@1"
    assert "local_date" not in response.text
    assert "latitude" not in response.text
    assert "utc_iso" not in response.text


def test_unknown_time_uses_local_noon_and_removes_ascendant_and_houses():
    client = TestClient(create_app())
    birth = dict(SYNTHETIC_CIVIL_BIRTH, time_known=False, local_time=None, tz_iana="Etc/GMT-3")
    response = client.post("/v1/vedic/natal-summary", json={"birth": birth})
    assert response.status_code == 200
    summary = response.json()["natal_summary"]
    known_noon = dict(birth, time_known=True, local_time="12:00:00")
    reference = client.post("/v1/vedic/natal-summary", json={"birth": known_noon}).json()["natal_summary"]
    assert summary["birth_data_precision"] == "placeholder"
    assert summary["ascendant"] is None
    assert summary["houses"] == {}
    assert {"no_birth_time", "nakshatra_time_uncertain"} <= set(summary["degraded_flags"])
    for name, point in summary["planets"].items():
        assert point["house"] is None
        assert point["longitude_deg"] == reference["planets"][name]["longitude_deg"]
    ignored_time = client.post("/v1/vedic/natal-summary", json={
        "birth": dict(birth, local_time="01:00:00"),
    }).json()["natal_summary"]
    assert ignored_time == summary


@pytest.mark.parametrize("extra", [
    {"system": "western"}, {"ayanamsha": "raman"},
    {"config": {"house_system": "placidus"}}, {"node_type": "true"},
])
def test_http_d1_rejects_unsupported_configuration(extra):
    response = TestClient(create_app()).post("/v1/vedic/natal-summary", json={
        "birth": SYNTHETIC_CIVIL_BIRTH, **extra,
    })
    assert response.status_code == 422


@pytest.mark.parametrize("field, invalid_value", [
    ("system", "western"), ("local_time", None), ("tz_iana", "Not/A_Timezone"),
    ("latitude", SYNTHETIC_CIVIL_BIRTH["latitude"] + 90),
    ("latitude", SYNTHETIC_CIVIL_BIRTH["latitude"] - 90),
    ("longitude", SYNTHETIC_CIVIL_BIRTH["longitude"] + 181),
])
def test_http_d1_rejects_invalid_or_unavailable_birth_configuration(field, invalid_value):
    birth = dict(SYNTHETIC_CIVIL_BIRTH)
    birth[field] = invalid_value
    response = TestClient(create_app()).post("/v1/vedic/natal-summary", json={
        "birth": birth,
    })
    assert response.status_code == 422


def test_http_d1_does_not_change_existing_tropical_natal_endpoint():
    client = TestClient(create_app())
    body = {"birth": SYNTHETIC_CIVIL_BIRTH}
    baseline = client.post("/v1/natal-summary", json=body).json()
    assert client.post("/v1/vedic/natal-summary", json=body).status_code == 200
    assert client.post("/v1/natal-summary", json=body).json() == baseline
