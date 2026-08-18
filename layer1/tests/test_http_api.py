from fastapi.testclient import TestClient

from layer1.http_api import BirthInput, create_app, normalized_birth
from layer1.tests.synthetic_inputs import SYNTHETIC_CIVIL_BIRTH


BIRTH = SYNTHETIC_CIVIL_BIRTH


def test_normalized_birth_uses_synthetic_utc_reference_point():
    result = normalized_birth(BirthInput.model_validate(BIRTH))
    assert result["utc_iso"] == "2000-01-01T12:00:00Z"
    assert result["tz_iana"] == "Etc/UTC"


def test_http_activations_and_natal_summary_are_real_ephemeris_outputs():
    client = TestClient(create_app())
    response = client.post("/v1/activations", json={
        "birth": BIRTH,
        "window": {
            "start_utc": "2026-09-01T00:00:00Z",
            "end_utc": "2026-10-01T00:00:00Z",
        },
        "mode": "forecast",
        "locale": "zh-Hans",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "swiss_ephemeris"
    assert len(payload["activations"]) >= 4
    assert payload["activations"][0]["provenance"]["se_version"] != "mock-2.10.03"

    response = client.post("/v1/natal-summary", json={"birth": BIRTH})
    assert response.status_code == 200
    summary = response.json()["natal_summary"]
    assert len(summary["planets"]) == 10
    assert len(summary["angles"]) == 4
    assert summary["aspects"]
