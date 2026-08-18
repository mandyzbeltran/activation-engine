"""Cross-host canonical output golden used by the two-OS CI matrix."""

from copy import deepcopy
import hashlib
from pathlib import Path

from layer1 import compute_activations, serialize_activations
from layer1.tests.synthetic_inputs import SYNTHETIC_INPUT


def test_canonical_output_matches_cross_host_golden() -> None:
    request = deepcopy(SYNTHETIC_INPUT)
    request["birth"]["time_known"] = False
    request["window"]["end_utc"] = "2026-09-03T00:00:00Z"
    digest = hashlib.sha256(serialize_activations(compute_activations(request))).hexdigest()
    expected_path = Path(__file__).parent / "golden" / "cross_host_sha256.txt"
    assert digest == expected_path.read_text(encoding="utf-8").strip()
