"""Unknown-birth-time degradation regression from section 11.3."""

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from layer1 import compute_activations
from layer1.tests.synthetic_inputs import SYNTHETIC_INPUT


def test_unknown_birth_time_disables_houses_angles_and_returns() -> None:
    request = deepcopy(SYNTHETIC_INPUT)
    request["birth"]["time_known"] = False
    result = compute_activations(request)
    assert {item["primary_life_area"] for item in result} == {"career", "wealth", "relationships", "family"}
    for activation in result:
        assert activation["birth_data_precision"] == "placeholder"
        assert activation["house_precision"] == "whole_sign_fallback"
        assert activation["confidence"] <= 0.7
        assert {"no_birth_time", "house_system_fallback", "return_angles_unavailable"} <= set(activation["degraded_flags"])
        assert not ({"solar_return", "lunar_return"} & set(activation["techniques"]))
        for driver in activation["drivers"]:
            assert driver.get("target_type") not in {"angle", "house"}


def test_unknown_birth_time_output_validates_against_schema() -> None:
    request = deepcopy(SYNTHETIC_INPUT)
    request["birth"]["time_known"] = False
    schema_path = Path(__file__).parents[1] / "schema" / "activation.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for activation in compute_activations(request):
        validator.validate(activation)
