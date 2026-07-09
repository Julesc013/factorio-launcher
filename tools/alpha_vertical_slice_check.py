from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden" / "commands"

REQUIRED_GOLDENS = {
    "product.inspect.success.json": {"command": "product.inspect"},
    "command_graph.inspect.success.json": {"command": "command_graph.inspect"},
    "diagnostics.report.success.json": {"command": "diagnostics.report"},
    "installs.import.success.json": {"command": "installs.import"},
    "installs.inspect.success.json": {"command": "installs.inspect"},
    "instances.create.success.json": {"command": "instances.create"},
    "launch.plan.success.json": {"command": "launch.plan"},
    "run.preview.success.json": {"command": "run.preview"},
    "run.execute.success.json": {"command": "run.execute"},
    "run.execute.refusal.json": {"command": "run.execute", "refusal_code": "preflight_failed"},
    "modsets.lock.success.json": {"command": "modsets.lock"},
    "modsets.export.success.json": {"command": "modsets.export"},
    "saves.backup.success.json": {"command": "saves.backup"},
    "export.instance.success.json": {"command": "export.instance"},
    "import.instance.success.json": {"command": "import.instance"},
    "installs.install-version.success.json": {"command": "installs.install-version"},
    "installs.repair.refusal.json": {"command": "installs.repair", "refusal_code": "ownership_denied"},
    "mods.search.refusal.json": {"command": "mods.search", "refusal_code": "network_forbidden"},
    "servers.start.refusal.json": {"command": "servers.start", "refusal_code": "execution_not_enabled"},
    "dev.dump-data.refusal.json": {"command": "dev.dump-data", "refusal_code": "execution_not_enabled"},
}


def main() -> int:
    problems: list[str] = []
    for name, expected in REQUIRED_GOLDENS.items():
        path = GOLDEN_ROOT / name
        problems.extend(validate_golden(path, expected))

    if problems:
        for problem in problems:
            print(f"alpha-vertical-slice-check: {problem}", file=sys.stderr)
        return 1
    print(f"alpha-vertical-slice-check: ok ({len(REQUIRED_GOLDENS)} goldens)")
    return 0


def validate_golden(path: Path, expected: dict[str, str]) -> list[str]:
    if not path.is_file():
        return [f"{path.relative_to(ROOT)}: missing required alpha golden"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path.relative_to(ROOT)}: {exc}"]
    if not isinstance(data, dict):
        return [f"{path.relative_to(ROOT)}: golden output must be a JSON object"]

    problems: list[str] = []
    command = expected["command"]
    if data.get("command") != command:
        problems.append(f"{path.relative_to(ROOT)}: command must be {command}")
    if "schema" not in data:
        problems.append(f"{path.relative_to(ROOT)}: missing schema")

    refusal_code = expected.get("refusal_code")
    if refusal_code is not None:
        problems.extend(validate_refusal(path, data, refusal_code))
    else:
        if data.get("status") == "refused":
            problems.append(f"{path.relative_to(ROOT)}: success golden must not have refused status")
    return problems


def validate_refusal(path: Path, data: dict, code: str) -> list[str]:
    problems: list[str] = []
    if data.get("status") != "refused":
        problems.append(f"{path.relative_to(ROOT)}: refusal golden must have status refused")
    refusal = data.get("refusal")
    if not isinstance(refusal, dict):
        return problems + [f"{path.relative_to(ROOT)}: refusal golden missing refusal object"]
    if refusal.get("code") != code:
        problems.append(f"{path.relative_to(ROOT)}: refusal code must be {code}")
    if not refusal.get("reason"):
        problems.append(f"{path.relative_to(ROOT)}: refusal must include reason")
    if "recoverable" not in refusal and "retryable" not in refusal:
        problems.append(f"{path.relative_to(ROOT)}: refusal must declare recoverable or retryable")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
