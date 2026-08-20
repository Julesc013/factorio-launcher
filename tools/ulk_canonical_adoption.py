# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Fail closed before adopting the repaired ULK canonical main revision."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "facman.ulk_canonical_adoption_gate.v1"
REPOSITORY = "Julesc013/universal-launcher"
REMOTE = "https://github.com/Julesc013/universal-launcher.git"
REPAIR_SHA = "7babf28bcda41186704868417743c39464a84e65"
REQUIRED_REF = "refs/heads/main"
EXPECTED_PACKAGE_VERSION = "1.8.0"
EXPECTED_CMAKE_VERSION = "1.9.0"
EXPECTED_ABI = (1, 9)
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_CHECKS = {
    "test (ubuntu-latest)",
    "test (windows-latest)",
    "test (macos-latest)",
    "test (windows-latest, Win32)",
}
SESSION_CONTRACTS = (
    "contracts/schema/session/session_record.v1.schema.json",
    "contracts/schema/session/session_list.v1.schema.json",
)
ATOMIC_PROJECTIONS = (
    "release/index/workspace_lock.v1.toml",
    "release/index/dependency_lock.v1.toml",
    "release/index/providers.lock.v2.toml",
    "release/index/sbom.components.v1.json",
    "release/index/current_state.v1.toml",
    "release/index/project_status.v2.toml",
    "apps/gui/windows/winforms/provider_identity.tracked.v1.txt",
    ".github/workflows/provider-conformance.yml",
    ".github/workflows/provider-sdk-consumption.yml",
    ".github/workflows/synthetic-product-tck.yml",
    "tools/provider_conformance.py",
    "tools/provider_pin_reconciliation.py",
    "tools/synthetic_product_tck.py",
    "tools/synthetic_product_tck_check.py",
    "tools/validators/release/check_workspace_lock.py",
    "tools/validators/release/check_dependency_lock.py",
)


@dataclass(frozen=True)
class Observation:
    origin_remote: str
    canonical_main_sha: str
    resolved_tree: str
    parent_count: int
    repair_is_ancestor: bool
    cmake_version: str
    package_version: str
    abi_major: int
    abi_minor: int
    abi_manifest_sha256: str
    current_abi_manifest_sha256: str
    session_contracts_present: bool
    tracked_identity_consistent: bool
    tracked_revision: str
    tracked_tree: str


def _git(root: Path, *args: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=text,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() if text else completed.stderr.decode(errors="replace").strip()
        raise ValueError(f"git {' '.join(args)} failed: {stderr}")
    return completed.stdout.strip() if text else completed.stdout


def _normal_remote(value: str) -> str:
    return value.removesuffix("/").removesuffix(".git")


def _component(rows: Any, identity: str) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise ValueError("provider identity rows must be an array")
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == identity]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {identity} identity row")
    return matches[0]


def tracked_identity(root: Path = ROOT) -> tuple[bool, str, str]:
    index = root / "release" / "index"
    with (index / "workspace_lock.v1.toml").open("rb") as handle:
        workspace = _component(tomllib.load(handle).get("component"), "universal_launcher")
    with (index / "dependency_lock.v1.toml").open("rb") as handle:
        dependency = _component(tomllib.load(handle).get("component"), "universal_launcher")
    with (index / "providers.lock.v2.toml").open("rb") as handle:
        provider_lock = tomllib.load(handle)
    provider = _component(provider_lock.get("provider"), "universal_launcher")
    sdk_rows = [
        row
        for row in provider_lock.get("sdk_package", [])
        if isinstance(row, dict) and row.get("provider_id") == "universal_launcher"
    ]
    sbom = json.loads((index / "sbom.components.v1.json").read_text(encoding="utf-8"))
    sbom_row = _component(sbom.get("components"), "universal_launcher")
    pairs = {
        (str(workspace.get("pin", "")), str(workspace.get("tree", ""))),
        (str(dependency.get("pin", "")), str(dependency.get("tree", ""))),
        (str(provider.get("source_revision", "")), str(provider.get("source_tree", ""))),
        (str(sbom_row.get("commit", "")), str(sbom_row.get("tree", ""))),
        *{
            (str(row.get("source_revision", "")), str(row.get("source_tree", "")))
            for row in sdk_rows
        },
    }
    valid = len(pairs) == 1 and len(sdk_rows) == 6
    revision, tree = next(iter(pairs)) if len(pairs) == 1 else ("", "")
    return valid, revision, tree


def inspect_repository(ulk_root: Path, facman_root: Path = ROOT) -> Observation:
    root = ulk_root.resolve()
    remote = str(_git(root, "remote", "get-url", "origin"))
    canonical_main = str(_git(root, "rev-parse", "refs/remotes/origin/main^{commit}"))
    resolved_tree = str(_git(root, "rev-parse", f"{canonical_main}^{{tree}}"))
    parents = str(_git(root, "rev-list", "--parents", "-n", "1", canonical_main)).split()
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", REPAIR_SHA, canonical_main],
        check=False,
        capture_output=True,
    ).returncode == 0
    cmake = str(_git(root, "show", f"{canonical_main}:CMakeLists.txt"))
    cmake_match = re.search(r"project\(universal_launcher VERSION ([0-9.]+) LANGUAGES C\)", cmake)
    if not cmake_match:
        raise ValueError("ULK CMake project version is missing")
    package = tomllib.loads(
        str(_git(root, "show", f"{canonical_main}:release/index/sdk_package_workunit.v1.toml"))
    )
    abi_bytes = _git(root, "show", f"{canonical_main}:contracts/abi/ulk_c_abi.v1.toml", text=False)
    assert isinstance(abi_bytes, bytes)
    abi = tomllib.loads(abi_bytes.decode("utf-8"))
    consistent, tracked_revision, tracked_tree = tracked_identity(facman_root)
    current_abi = b""
    if re.fullmatch(r"[0-9a-f]{40}", tracked_revision):
        current_abi = _git(
            root,
            "show",
            f"{tracked_revision}:contracts/abi/ulk_c_abi.v1.toml",
            text=False,
        )
        assert isinstance(current_abi, bytes)
    contracts_present = all(
        subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"{canonical_main}:{path}"],
            check=False,
            capture_output=True,
        ).returncode == 0
        for path in SESSION_CONTRACTS
    )
    return Observation(
        origin_remote=remote,
        canonical_main_sha=canonical_main,
        resolved_tree=resolved_tree,
        parent_count=max(0, len(parents) - 1),
        repair_is_ancestor=ancestor,
        cmake_version=cmake_match.group(1),
        package_version=str(package.get("package_version", "")),
        abi_major=int(abi.get("abi_major", -1)),
        abi_minor=int(abi.get("abi_minor", -1)),
        abi_manifest_sha256=hashlib.sha256(abi_bytes).hexdigest(),
        current_abi_manifest_sha256=hashlib.sha256(current_abi).hexdigest(),
        session_contracts_present=contracts_present,
        tracked_identity_consistent=consistent,
        tracked_revision=tracked_revision,
        tracked_tree=tracked_tree,
    )


def _check_head(row: dict[str, Any]) -> str:
    if isinstance(row.get("head_sha"), str):
        return str(row["head_sha"])
    suite = row.get("check_suite")
    if isinstance(suite, dict) and isinstance(suite.get("head_sha"), str):
        return str(suite["head_sha"])
    return ""


def check_run_problems(value: dict[str, Any], expected_sha: str) -> list[str]:
    problems: list[str] = []
    rows = value.get("check_runs")
    if not isinstance(rows, list):
        return ["merge-head CI response has no check_runs array"]
    by_name: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if isinstance(row, dict):
            by_name.setdefault(str(row.get("name", "")), []).append(row)
    for name in sorted(REQUIRED_CHECKS):
        matches = by_name.get(name, [])
        if not matches:
            problems.append(f"merge-head CI is missing required check: {name}")
            continue
        for row in matches:
            row_head = _check_head(row)
            if row_head and row_head != expected_sha:
                problems.append(f"merge-head check {name} is bound to the wrong SHA")
            if row.get("status") != "completed" or row.get("conclusion") != "success":
                problems.append(f"merge-head check {name} is not green")
    return problems


def evaluate(
    proposed_sha: str,
    proposed_tree: str,
    required_ref: str,
    observation: Observation,
    check_runs: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    if not HEX_40.fullmatch(proposed_sha):
        problems.append("--ulk-main-sha must be a lowercase 40-character Git SHA")
    if not HEX_40.fullmatch(proposed_tree):
        problems.append("--ulk-tree must be a lowercase 40-character Git tree")
    if required_ref != REQUIRED_REF:
        problems.append(f"required ref must be exactly {REQUIRED_REF}")
    if _normal_remote(observation.origin_remote) != _normal_remote(REMOTE):
        problems.append("ULK origin remote is not the canonical repository")
    if proposed_sha == REPAIR_SHA:
        problems.append("the #16 task SHA cannot be used as a canonical pin")
    if proposed_sha != observation.canonical_main_sha:
        problems.append("proposed SHA is not the exact current canonical ULK main tip")
    if proposed_tree != observation.resolved_tree:
        problems.append("proposed ULK tree does not match the proposed commit")
    if not observation.repair_is_ancestor:
        problems.append("canonical ULK main does not contain the #16 repair ancestry")
    if observation.parent_count < 2:
        problems.append("canonical ULK repair tip is not a history-preserving merge commit")
    if observation.cmake_version != EXPECTED_CMAKE_VERSION:
        problems.append("ULK CMake package version is incompatible")
    if observation.package_version != EXPECTED_PACKAGE_VERSION:
        problems.append("ULK SDK package version is incompatible")
    if (observation.abi_major, observation.abi_minor) != EXPECTED_ABI:
        problems.append("ULK public ABI version changed")
    if observation.abi_manifest_sha256 != observation.current_abi_manifest_sha256:
        problems.append("ULK public ABI manifest changed")
    if not observation.session_contracts_present:
        problems.append("ULK session contracts are incomplete")
    if not observation.tracked_identity_consistent:
        problems.append("FacMan currently contains mixed ULK source/package identities")
    problems.extend(check_run_problems(check_runs, proposed_sha))
    return problems


def _github_check_runs(sha: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{REPOSITORY}/commits/{sha}/check-runs?per_page=100",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(f"GitHub check-run query failed: {completed.stderr.strip()}")
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError("GitHub check-run response is not an object")
    return value


def report(
    proposed_sha: str,
    proposed_tree: str,
    required_ref: str,
    observation: Observation,
    check_runs: dict[str, Any],
) -> dict[str, Any]:
    problems = evaluate(proposed_sha, proposed_tree, required_ref, observation, check_runs)
    return {
        "schema": SCHEMA,
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": "eligible" if not problems else "refused",
        "problems": problems,
        "proposed": {
            "repository": REPOSITORY,
            "sha": proposed_sha,
            "tree": proposed_tree,
            "required_ref": required_ref,
        },
        "repair_sha": REPAIR_SHA,
        "observation": asdict(observation),
        "required_checks": sorted(REQUIRED_CHECKS),
        "atomic_projection_set": list(ATOMIC_PROJECTIONS),
        "sdk_package_evidence_required": {
            "systems": ["linux", "macos", "windows"],
            "linkages": ["static", "shared"],
            "exact_source_revision": proposed_sha,
            "exact_source_tree": proposed_tree,
        },
        "apply_performed": False,
        "canonical_release_verified": False,
        "authority": {
            "protected_branch_write": False,
            "self_merge": False,
            "production_signing": False,
            "publication": False,
        },
    }


def _write_external(path: Path, value: dict[str, Any], source_root: Path = ROOT) -> None:
    destination = path.resolve()
    source = source_root.resolve()
    if destination == source or source in destination.parents:
        raise ValueError("adoption evidence must be written outside the source repository")
    if destination.exists():
        raise ValueError(f"adoption evidence already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ulk-root", type=Path, required=True)
    parser.add_argument("--ulk-main-sha", required=True)
    parser.add_argument("--ulk-tree", required=True)
    parser.add_argument("--required-ref", required=True)
    parser.add_argument("--check-runs-json", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        observation = inspect_repository(args.ulk_root)
        checks = (
            json.loads(args.check_runs_json.read_text(encoding="utf-8"))
            if args.check_runs_json
            else _github_check_runs(args.ulk_main_sha)
        )
        if not isinstance(checks, dict):
            raise ValueError("check-run evidence must be an object")
        value = report(
            args.ulk_main_sha,
            args.ulk_tree,
            args.required_ref,
            observation,
            checks,
        )
        if args.evidence:
            _write_external(args.evidence, value)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"ulk-canonical-adoption: {error}", file=sys.stderr)
        return 2
    if value["problems"]:
        for problem in value["problems"]:
            print(f"ulk-canonical-adoption: {problem}", file=sys.stderr)
        return 1
    print(f"ulk-canonical-adoption: eligible {args.ulk_main_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
