from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = PROJECT_ROOT / "scripts" / "privacy_gate.py"
SPEC = importlib.util.spec_from_file_location("privacy_gate", GATE_PATH)
assert SPEC is not None and SPEC.loader is not None
privacy_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(privacy_gate)


def test_public_path_allowlist_is_fail_closed():
    assert privacy_gate.path_errors("layer1/api.py") == []
    assert privacy_gate.path_errors("layer1/schema/activation.schema.json") == []
    assert privacy_gate.path_errors("README.md") == []
    assert privacy_gate.path_errors("layer2/service.py")
    assert privacy_gate.path_errors("docs/internal.md")
    assert privacy_gate.path_errors("layer1/schema/polarity-map.json")


def test_secret_and_private_context_patterns_are_blocked():
    fake_key = ("sk-" + "ant-" + "A" * 32).encode()
    local_path = ("/" + "Users/example/private.txt").encode()
    private_repo = ("astrology-" + "narrative-app").encode()
    assert "Anthropic API key" in privacy_gate.content_errors("layer1/api.py", fake_key)
    assert "local home path" in privacy_gate.content_errors("README.md", local_path)
    assert "private repository name" in privacy_gate.content_errors("README.md", private_repo)


def test_literal_birth_data_is_only_allowed_in_the_synthetic_source():
    field = "local_" + "date"
    value = "1988" + "-04-03"
    content = f'{{"{field}": "{value}"}}'.encode()
    assert "literal birth data outside the approved synthetic input" in privacy_gate.content_errors(
        "layer1/tests/example.py", content
    )
    synthetic = (PROJECT_ROOT / privacy_gate.SYNTHETIC_INPUT_PATH).read_bytes()
    assert privacy_gate.content_errors(privacy_gate.SYNTHETIC_INPUT_PATH, synthetic) == []


def test_full_history_scan_rejects_a_file_deleted_in_a_later_commit(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "Privacy Test"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "privacy@example.invalid"], cwd=repository, check=True)
    (repository / "README.md").write_text("public\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "public"], cwd=repository, check=True)

    private_file = repository / "layer2" / "secret.txt"
    private_file.parent.mkdir()
    private_file.write_text("private\n", encoding="utf-8")
    subprocess.run(["git", "add", "layer2/secret.txt"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "private"], cwd=repository, check=True)
    private_file.unlink()
    subprocess.run(["git", "add", "-u"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "remove"], cwd=repository, check=True)

    result = subprocess.run(
        ["python3", str(GATE_PATH), "--all-history"],
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "PUBLIC PRIVACY GATE: BLOCKED" in result.stderr
    assert "layer2/secret.txt" in result.stderr
