"""Precision, provenance, and fail-soft edge cases."""

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from layer1 import compute_activations
from layer1.tests.synthetic_inputs import SYNTHETIC_INPUT


def _validator() -> Draft202012Validator:
    path = Path(__file__).parents[1] / "schema" / "activation.schema.json"
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")), format_checker=FormatChecker())


def test_known_birth_time_output_validates_and_has_locked_provenance() -> None:
    result = compute_activations(SYNTHETIC_INPUT)
    validator = _validator()
    for activation in result:
        validator.validate(activation)
        assert activation["provenance"]["se_version"] == "2.10.03"
        assert activation["provenance"]["immanuel_version"] == "1.5.4"
        assert len(activation["provenance"]["se_ephe_files_sha256"]) == 64


def test_high_latitude_uses_whole_sign_fallback() -> None:
    request = deepcopy(SYNTHETIC_INPUT)
    request["birth"]["lat"] = 70.0
    request["window"]["end_utc"] = "2026-09-03T00:00:00Z"
    result = compute_activations(request)
    assert result
    assert all(item["house_system"] == "whole_sign" for item in result)
    assert all(item["house_precision"] == "whole_sign_fallback" for item in result)
    assert all("placidus_undefined_at_latitude" in item["degraded_flags"] for item in result)


def test_retrospective_drivers_include_snapshot_or_explicit_null() -> None:
    request = deepcopy(SYNTHETIC_INPUT)
    request["mode"] = "retrospective"
    request["window"]["end_utc"] = "2026-09-03T00:00:00Z"
    for activation in compute_activations(request):
        assert all("ephemeris_snapshot" in driver for driver in activation["drivers"])
