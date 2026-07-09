from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "tests" / "golden" / "discovery_reports"
FIXTURE_GOLDEN_DIR = ROOT / "tests" / "golden" / "discovery"

EXPECTED = {
    "steam_windows.discovery_report.v1.json": {
        "source": "steam",
        "ownership": "foreign_owned",
        "platform": "windows-x64",
        "status": "structural",
    },
    "portable_windows.discovery_report.v1.json": {
        "source": "portable",
        "ownership": "portable",
        "platform": "windows-x64",
        "status": "structural",
    },
    "macos_app.discovery_report.v1.json": {
        "source": "app_bundle",
        "ownership": "imported",
        "platform": "macos",
        "status": "structural",
    },
    "linux_headless.discovery_report.v1.json": {
        "source": "headless",
        "ownership": "imported",
        "platform": "linux-x64",
        "status": "structural",
    },
    "invalid.discovery_report.v1.json": {
        "source": "manual",
        "ownership": "imported",
        "platform": "linux-x64",
        "status": "invalid",
    },
}

EXPECTED_FIXTURE_GOLDENS = {
    "imported_adoptable.discovery_report.v1.json",
    "invalid.discovery_report.v1.json",
    "linux_headless.discovery_report.v1.json",
    "linux_package_foreign.discovery_report.v1.json",
    "linux_tarball.discovery_report.v1.json",
    "macos_app_bundle.discovery_report.v1.json",
    "macos_invalid_bundle.discovery_report.v1.json",
    "windows_portable.discovery_report.v1.json",
    "windows_standalone.discovery_report.v1.json",
    "windows_steam.discovery_report.v1.json",
}


def main() -> int:
    problems: list[str] = []
    if not GOLDEN_DIR.is_dir():
        problems.append(f"{GOLDEN_DIR}: missing discovery golden directory")
    else:
        actual_names = {path.name for path in GOLDEN_DIR.glob("*.json")}
        missing = sorted(set(EXPECTED) - actual_names)
        extra = sorted(actual_names - set(EXPECTED))
        for name in missing:
            problems.append(f"{GOLDEN_DIR / name}: missing required golden")
        for name in extra:
            problems.append(f"{GOLDEN_DIR / name}: unexpected discovery golden")
        for name in sorted(set(EXPECTED) & actual_names):
            problems.extend(validate_golden(GOLDEN_DIR / name, EXPECTED[name]))
    problems.extend(validate_fixture_golden_set())

    if problems:
        for problem in problems:
            print(f"discovery-golden-check: {problem}", file=sys.stderr)
        return 1
    print("discovery-golden-check: ok")
    return 0


def validate_fixture_golden_set() -> list[str]:
    problems: list[str] = []
    if not FIXTURE_GOLDEN_DIR.is_dir():
        return [f"{FIXTURE_GOLDEN_DIR}: missing discovery fixture golden directory"]

    actual_names = {path.name for path in FIXTURE_GOLDEN_DIR.glob("*.json")}
    for name in sorted(EXPECTED_FIXTURE_GOLDENS - actual_names):
        problems.append(f"{FIXTURE_GOLDEN_DIR / name}: missing required fixture golden")
    for name in sorted(actual_names - EXPECTED_FIXTURE_GOLDENS):
        problems.append(f"{FIXTURE_GOLDEN_DIR / name}: unexpected fixture golden")
    for name in sorted(actual_names & EXPECTED_FIXTURE_GOLDENS):
        problems.extend(validate_fixture_golden(FIXTURE_GOLDEN_DIR / name))
    return problems


def validate_fixture_golden(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: {exc}"]
    problems: list[str] = []
    if data.get("schema") != "factorio.discovery_report.v1":
        problems.append(f"{path}: schema must be factorio.discovery_report.v1")
    if data.get("command") != "installs.scan":
        problems.append(f"{path}: command must be installs.scan")
    if data.get("read_only") is not True:
        problems.append(f"{path}: read_only must be true")
    install = data.get("install")
    if not isinstance(install, dict):
        return problems + [f"{path}: fixture golden must contain install object"]
    required = [
        "candidate_id",
        "source",
        "ownership",
        "platform",
        "capabilities",
        "executable_path_kind",
        "app_dir_kind",
        "validation_status",
        "setup_mutation_allowed",
    ]
    for key in required:
        if key not in install:
            problems.append(f"{path}: install missing {key}")
    if install.get("setup_mutation_allowed") is not False:
        problems.append(f"{path}: setup_mutation_allowed must be false")
    if install.get("validation_status") == "invalid":
        refusal = install.get("refusal")
        if not isinstance(refusal, dict):
            problems.append(f"{path}: invalid fixture golden must include refusal")
        elif refusal.get("code") != "invalid_factorio_install":
            problems.append(f"{path}: invalid fixture refusal code must be invalid_factorio_install")
    return problems


def validate_golden(path: Path, expected: dict[str, str]) -> list[str]:
    problems: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: {exc}"]

    if report.get("schema") != "factorio.discovery_report.v1":
        problems.append(f"{path}: schema must be factorio.discovery_report.v1")
    if report.get("command") != "installs.scan":
        problems.append(f"{path}: command must be installs.scan")
    if report.get("read_only") is not True:
        problems.append(f"{path}: report must be read_only")

    installs = report.get("installs")
    if not isinstance(installs, list):
        return problems + [f"{path}: installs must be an array"]
    if report.get("candidate_count") != len(installs):
        problems.append(f"{path}: candidate_count must match installs length")

    structural_count = sum(1 for install in installs if verification_status(install) == "structural")
    invalid_count = sum(1 for install in installs if verification_status(install) == "invalid")
    if report.get("structural_count") != structural_count:
        problems.append(f"{path}: structural_count must match installs")
    if report.get("invalid_count") != invalid_count:
        problems.append(f"{path}: invalid_count must match installs")

    if len(installs) != 1:
        return problems + [f"{path}: fixture golden must contain exactly one install"]

    install = installs[0]
    for key in ["source", "ownership", "platform"]:
        if install.get(key) != expected[key]:
            problems.append(f"{path}: install {key} must be {expected[key]}")
    if verification_status(install) != expected["status"]:
        problems.append(f"{path}: install verification status must be {expected['status']}")
    problems.extend(validate_install(path, install, expected["status"]))
    return problems


def verification_status(install: object) -> str:
    if not isinstance(install, dict):
        return ""
    verification = install.get("verification")
    if not isinstance(verification, dict):
        return ""
    status = verification.get("status")
    return status if isinstance(status, str) else ""


def validate_install(path: Path, install: object, expected_status: str) -> list[str]:
    if not isinstance(install, dict):
        return [f"{path}: install must be an object"]

    problems: list[str] = []
    if install.get("schema") != "factorio.install_ref.v1":
        problems.append(f"{path}: install schema must be factorio.install_ref.v1")
    if install.get("product_id") != "factorio":
        problems.append(f"{path}: install product_id must be factorio")

    discovery = install.get("discovery")
    if not isinstance(discovery, dict) or discovery.get("read_only") is not True:
        problems.append(f"{path}: install discovery must be read_only")

    safe_actions = install.get("safe_actions")
    if not isinstance(safe_actions, dict):
        problems.append(f"{path}: install safe_actions must be an object")
    else:
        if safe_actions.get("repair") is not False or safe_actions.get("uninstall") is not False:
            problems.append(f"{path}: fixture installs must refuse repair and uninstall")

    root = install.get("root")
    if not isinstance(root, str) or not root:
        problems.append(f"{path}: install root must be a non-empty string")
    elif not (ROOT / root).exists():
        problems.append(f"{path}: install root fixture does not exist: {root}")

    executable = install.get("executable")
    if expected_status == "structural":
        if not isinstance(executable, str) or not executable:
            problems.append(f"{path}: structural install must include executable")
        elif not (ROOT / executable).is_file():
            problems.append(f"{path}: executable fixture does not exist: {executable}")
    elif executable not in ("", None):
        problems.append(f"{path}: invalid install should not include executable")

    return problems


if __name__ == "__main__":
    raise SystemExit(main())
