#!/usr/bin/env python3
"""Fail closed when a public Layer 1 ref contains private or secret material."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable, NamedTuple


ROOT_FILES = {
    ".gitignore",
    "LICENSE",
    "README.md",
    "pyproject.toml",
}
REPOSITORY_FILES = {
    ".github/workflows/ci.yml",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    "scripts/privacy_gate.py",
}
SCHEMA_FILES = {
    "layer1/schema/activation.schema.json",
    "layer1/schema/controlled-vocab.yaml",
}
TEST_DATA_FILES = {
    "layer1/tests/golden/cross_host_sha256.txt",
}
FORBIDDEN_PARTS = {
    ".env",
    "docs",
    "handoff",
    "kb",
    "layer2",
    "mobile",
    "notes",
    "private",
    "prompts",
    "report",
}
FORBIDDEN_BASENAMES = {
    "fixtures.py",
    "life-area-mapping.yaml",
    "polarity-map.json",
}
SYNTHETIC_INPUT_PATH = "layer1/tests/synthetic_inputs.py"

SECRET_PATTERNS = (
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}")),
    ("OpenAI API key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"(?:gh[opusr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("local home path", re.compile(r"/(?:Users|home)/[^/\s]+/")),
)
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(?:ANTHROPIC_API_KEY|OPENAI_API_KEY|GITHUB_TOKEN|API_KEY)"
    r"\s*[:=]\s*['\"]?(?!<|your-|replace-|example)[A-Za-z0-9_./+-]{8,}"
)
LITERAL_BIRTH_VALUE = re.compile(
    r"['\"](?:utc_iso|local_date|local_time|latitude|longitude|lat|lon|tz_iana)['\"]"
    r"\s*:\s*(?:['\"][^'\"]+['\"]|-?[0-9]+(?:\.[0-9]+)?)"
)
PRIVATE_REPOSITORY_NAME = "astrology-" + "narrative-app"
MAX_TEXT_BYTES = 1_000_000


class Entry(NamedTuple):
    mode: str
    object_type: str
    object_id: str
    path: str


def git(*args: str, input_text: str | None = None) -> bytes:
    result = subprocess.run(
        ["git", *args],
        input=None if input_text is None else input_text.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def allowed_path(path: str) -> bool:
    if path in ROOT_FILES | REPOSITORY_FILES | SCHEMA_FILES | TEST_DATA_FILES:
        return True
    if path.startswith("layer1/") and path.endswith(".py"):
        return True
    return False


def path_errors(path: str) -> list[str]:
    errors = []
    pure = PurePosixPath(path)
    lowered_parts = {part.lower() for part in pure.parts}
    lowered_name = pure.name.lower()
    if not allowed_path(path):
        errors.append("path is outside the public allowlist")
    if lowered_name in FORBIDDEN_BASENAMES:
        errors.append("private artifact filename")
    if lowered_parts & FORBIDDEN_PARTS:
        errors.append("private artifact path segment")
    return errors


def content_errors(path: str, content: bytes) -> list[str]:
    if len(content) > MAX_TEXT_BYTES:
        return [f"file exceeds {MAX_TEXT_BYTES} bytes"]
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return ["non-UTF-8 or binary content is not allowed"]

    errors = [label for label, pattern in SECRET_PATTERNS if pattern.search(text)]
    if SENSITIVE_ASSIGNMENT.search(text):
        errors.append("credential assignment")
    if PRIVATE_REPOSITORY_NAME in text:
        errors.append("private repository name")
    if path != SYNTHETIC_INPUT_PATH and LITERAL_BIRTH_VALUE.search(text):
        errors.append("literal birth data outside the approved synthetic input")
    if path == SYNTHETIC_INPUT_PATH:
        errors.extend(validate_synthetic_input(text))
    return errors


def validate_synthetic_input(text: str) -> list[str]:
    try:
        module = ast.parse(text)
    except SyntaxError:
        return ["synthetic input file is not valid Python"]
    assignments = {
        node.targets[0].id: node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"SYNTHETIC_INPUT", "SYNTHETIC_CIVIL_BIRTH"}
    }
    utc_field = "utc_" + "iso"
    time_known_field = "time_" + "known"
    latitude_short = "l" + "at"
    longitude_short = "l" + "on"
    timezone_field = "tz_" + "iana"
    local_date_field = "local_" + "date"
    local_time_field = "local_" + "time"
    latitude_field = "lati" + "tude"
    longitude_field = "longi" + "tude"
    expected_birth = {
        utc_field: "2000-01-01T12:00:00Z",
        time_known_field: True,
        latitude_short: 0.0,
        longitude_short: 0.0,
        timezone_field: "Etc/UTC",
    }
    expected_civil = {
        local_date_field: "2000-01-01",
        local_time_field: "12:00:00",
        time_known_field: True,
        latitude_field: 0.0,
        longitude_field: 0.0,
        timezone_field: "Etc/UTC",
    }
    errors = []
    synthetic_input = assignments.get("SYNTHETIC_INPUT")
    actual_birth = None
    if isinstance(synthetic_input, ast.Dict):
        for key, value in zip(synthetic_input.keys, synthetic_input.values):
            if isinstance(key, ast.Constant) and key.value == "birth":
                actual_birth = ast.literal_eval(value)
                break
    if actual_birth != expected_birth:
        errors.append("SYNTHETIC_INPUT.birth is not the approved public reference point")
    civil_birth = assignments.get("SYNTHETIC_CIVIL_BIRTH")
    if civil_birth is not None and ast.literal_eval(civil_birth) != expected_civil:
        errors.append("SYNTHETIC_CIVIL_BIRTH is not the approved public reference point")
    return errors


def parse_tree(commit: str) -> list[Entry]:
    entries = []
    for record in git("ls-tree", "-r", "-z", commit).split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split()
        entries.append(Entry(mode, object_type, object_id, raw_path.decode("utf-8")))
    return entries


def parse_index() -> list[Entry]:
    entries = []
    for record in git("ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        if stage != "0":
            raise RuntimeError("unmerged index entries cannot pass the privacy gate")
        entries.append(Entry(mode, "blob", object_id, raw_path.decode("utf-8")))
    return entries


def scan_entries(entries: Iterable[Entry], *, context: str, seen_blobs: set[str]) -> list[str]:
    failures = []
    for entry in entries:
        for reason in path_errors(entry.path):
            failures.append(f"{context}: {entry.path}: {reason}")
        if entry.object_type != "blob" or entry.mode not in {"100644", "100755"}:
            failures.append(f"{context}: {entry.path}: symlinks and submodules are not allowed")
            continue
        if entry.object_id in seen_blobs:
            continue
        seen_blobs.add(entry.object_id)
        content = git("cat-file", "blob", entry.object_id)
        for reason in content_errors(entry.path, content):
            failures.append(f"{context}: {entry.path}: {reason}")
    return failures


def commits_for_all_history() -> list[str]:
    output = git("rev-list", "--all").decode("ascii").splitlines()
    return list(dict.fromkeys(output))


def commits_for_pre_push(lines: Iterable[str]) -> list[str]:
    commits = []
    zero = "0" * 40
    for line in lines:
        fields = line.split()
        if len(fields) != 4:
            continue
        local_sha = fields[1]
        if local_sha == zero:
            continue
        reachable = git("rev-list", local_sha).decode("ascii").splitlines()
        commits.extend(reachable)
    return list(dict.fromkeys(commits)) or commits_for_all_history()


def scan_commits(commits: Iterable[str]) -> list[str]:
    failures = []
    seen_blobs: set[str] = set()
    for commit in commits:
        failures.extend(
            scan_entries(parse_tree(commit), context=commit[:12], seen_blobs=seen_blobs)
        )
    return failures


def scan_working_tree() -> list[str]:
    failures = []
    paths = git(
        "ls-files", "--cached", "--others", "--exclude-standard", "-z"
    ).split(b"\0")
    for raw_path in paths:
        if not raw_path:
            continue
        path = raw_path.decode("utf-8")
        for reason in path_errors(path):
            failures.append(f"working-tree: {path}: {reason}")
        local_path = Path(path)
        if local_path.is_symlink() or not local_path.is_file():
            failures.append(f"working-tree: {path}: symlinks and non-files are not allowed")
            continue
        for reason in content_errors(path, local_path.read_bytes()):
            failures.append(f"working-tree: {path}: {reason}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--pre-push", action="store_true")
    mode.add_argument("--all-history", action="store_true")
    mode.add_argument("--working-tree", action="store_true")
    args = parser.parse_args()

    try:
        if args.staged:
            failures = scan_entries(parse_index(), context="index", seen_blobs=set())
        elif args.pre_push:
            failures = scan_commits(commits_for_pre_push(sys.stdin))
        elif args.all_history:
            failures = scan_commits(commits_for_all_history())
        else:
            failures = scan_working_tree()
    except RuntimeError as exc:
        print(f"privacy gate error: {exc}", file=sys.stderr)
        return 2

    if failures:
        print("PUBLIC PRIVACY GATE: BLOCKED", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("PUBLIC PRIVACY GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
