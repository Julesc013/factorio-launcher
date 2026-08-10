# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import datetime
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release/index/component_ownership.v1.toml"

OWNERS = {
    "universal_setup",
    "universal_launcher",
    "factorio_binding",
    "facman_frontend",
    "product_packaging",
    "development_governance",
    "temporary_incubator",
}
IMPLEMENTATION_STATES = {
    "census_pending",
    "placeholder",
    "partial",
    "implemented",
}
MATURITIES = {
    "experimental",
    "fixture_qualified",
    "consumer_qualified",
    "release_qualified",
    "stable",
}
PUBLIC_SURFACES = {
    "public_api",
    "public_contract",
    "product_interface",
    "private_internal",
    "development_only",
}
REPOSITORIES = {
    "factorio-launcher",
    "universal-launcher",
    "universal-setup",
}
TEMPORARY_FIELDS = {
    "final_owner",
    "reason",
    "public_contract",
    "extraction_dependency",
    "expires_at",
}
EXPECTED_BRANCH_MODELS = {
    "factorio-launcher": "main + integration dev + short-lived task and hotfix branches",
    "universal-launcher": "main + integration dev + short-lived task and hotfix branches",
    "universal-setup": "main + integration dev + short-lived task and hotfix branches",
}


def sibling_root(name: str) -> Path | None:
    specific = os.environ.get(
        {
            "universal-launcher": "FLAUNCH_UNIVERSAL_LAUNCHER_ROOT",
            "universal-setup": "FLAUNCH_UNIVERSAL_SETUP_ROOT",
        }[name]
    )
    candidates = []
    if specific:
        candidates.append(Path(specific))
    universal = os.environ.get("FLAUNCH_UNIVERSAL_ROOT")
    if universal:
        candidates.append(Path(universal) / name)
    candidates.extend(
        [
            ROOT / "external" / name,
            ROOT.parent / name,
            ROOT.parent.parent / "Universal" / name,
        ]
    )
    return next((path for path in candidates if (path / "CMakeLists.txt").is_file()), None)


def repository_roots(require_siblings: bool) -> tuple[dict[str, Path], list[str]]:
    roots = {"factorio-launcher": ROOT}
    problems = []
    for name in ("universal-launcher", "universal-setup"):
        root = sibling_root(name)
        if root is None:
            if require_siblings:
                problems.append(f"required sibling repository is unavailable: {name}")
        else:
            roots[name] = root
    return roots, problems


def coverage_paths() -> list[str]:
    paths = []
    for parent in (
        ROOT / "runtime",
        ROOT / "runtime/core",
        ROOT / "runtime/factorio",
        ROOT / "contracts",
        ROOT / "contracts/command",
        ROOT / "contracts/schema",
    ):
        paths.extend(
            path.relative_to(ROOT).as_posix()
            for path in parent.iterdir()
            if path.is_dir()
        )
    return paths


def is_covered(path: str, components: list[dict[str, Any]]) -> bool:
    return any(
        component.get("repository") == "factorio-launcher"
        and (
            path == component.get("path")
            or path.startswith(f"{component.get('path')}/")
            or str(component.get("path", "")).startswith(f"{path}/")
        )
        for component in components
    )


def component_truth_problems(component_id: str, component: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    implementation_state = component.get("implementation_state")
    if implementation_state not in IMPLEMENTATION_STATES:
        problems.append(
            f"component {component_id} implementation_state must be one of "
            f"{sorted(IMPLEMENTATION_STATES)}"
        )

    maturity = component.get("maturity")
    if maturity not in MATURITIES:
        problems.append(
            f"component {component_id} maturity must be one of {sorted(MATURITIES)}"
        )

    public_surface = component.get("public_surface")
    if public_surface not in PUBLIC_SURFACES:
        problems.append(
            f"component {component_id} public_surface must be one of "
            f"{sorted(PUBLIC_SURFACES)}"
        )

    evidence = component.get("evidence")
    if not isinstance(evidence, list):
        problems.append(f"component {component_id} evidence must be a list")
    elif any(not isinstance(item, str) or not item.strip() for item in evidence):
        problems.append(
            f"component {component_id} evidence entries must be non-empty strings"
        )

    support_claim_allowed = component.get("support_claim_allowed")
    if not isinstance(support_claim_allowed, bool):
        problems.append(
            f"component {component_id} support_claim_allowed must be a boolean"
        )
    elif support_claim_allowed:
        if implementation_state in {"census_pending", "placeholder"}:
            problems.append(
                f"component {component_id} cannot allow support claims while "
                f"implementation_state is {implementation_state}"
            )
        if maturity == "experimental":
            problems.append(
                f"component {component_id} cannot allow support claims while "
                "maturity is experimental"
            )
        if isinstance(evidence, list) and not evidence:
            problems.append(
                f"component {component_id} cannot allow support claims without evidence"
            )

    return problems


def check(*, require_siblings: bool = False) -> list[str]:
    if not MANIFEST.is_file():
        return [f"ownership manifest is missing: {MANIFEST}"]
    with MANIFEST.open("rb") as handle:
        data = tomllib.load(handle)

    problems = []
    if data.get("schema") != "facman.component_ownership.v1":
        problems.append("ownership manifest has the wrong schema")
    reviewed_on = data.get("reviewed_on")
    try:
        parsed_reviewed_on = datetime.date.fromisoformat(str(reviewed_on))
    except ValueError:
        problems.append("ownership manifest reviewed_on must be an ISO date")
    else:
        if parsed_reviewed_on.isoformat() != reviewed_on:
            problems.append("ownership manifest reviewed_on must use YYYY-MM-DD")
    if set(data.get("classification", [])) != OWNERS:
        problems.append("ownership manifest classification set is incomplete")

    repositories = data.get("repository", [])
    repository_ids = [item.get("id") for item in repositories]
    if set(repository_ids) != REPOSITORIES or len(repository_ids) != len(set(repository_ids)):
        problems.append("ownership manifest must define each repository exactly once")
    for repository in repositories:
        repo_id = repository.get("id")
        if EXPECTED_BRANCH_MODELS.get(repo_id) != repository.get("branch_model"):
            problems.append(f"{repo_id} branch model is missing or ambiguous")
        expected_mutator = repo_id == "universal-setup"
        if repository.get("install_mutation_authority") is not expected_mutator:
            problems.append(
                f"{repo_id} install-mutation authority must be {expected_mutator}"
            )

    roots, root_problems = repository_roots(require_siblings)
    problems.extend(root_problems)
    components = data.get("component", [])
    ids: set[str] = set()
    locations: set[tuple[str, str]] = set()
    for component in components:
        component_id = component.get("id")
        repository = component.get("repository")
        path = component.get("path")
        owner = component.get("owner")
        if not isinstance(component_id, str) or not component_id:
            problems.append("component has no stable id")
            continue
        if component_id in ids:
            problems.append(f"duplicate component id: {component_id}")
        ids.add(component_id)
        if repository not in REPOSITORIES:
            problems.append(f"{component_id} has unknown repository {repository!r}")
        if not isinstance(path, str) or not path or Path(path).is_absolute() or "\\" in path:
            problems.append(f"{component_id} path must be a relative POSIX path")
            continue
        location = (str(repository), path)
        if location in locations:
            problems.append(f"duplicate component location: {repository}:{path}")
        locations.add(location)
        if owner not in OWNERS:
            problems.append(f"{component_id} has unknown owner {owner!r}")
        if not component.get("public_contract"):
            problems.append(f"{component_id} has no public or private contract boundary")
        problems.extend(component_truth_problems(component_id, component))
        if owner == "temporary_incubator":
            missing = sorted(field for field in TEMPORARY_FIELDS if not component.get(field))
            if missing:
                problems.append(
                    f"{component_id} temporary incubator is missing {', '.join(missing)}"
                )
            if component.get("final_owner") not in OWNERS - {"temporary_incubator"}:
                problems.append(f"{component_id} has an invalid final owner")
        elif any(field in component for field in TEMPORARY_FIELDS - {"public_contract"}):
            problems.append(f"{component_id} has temporary-only metadata but is permanent")
        if repository == "factorio-launcher" and owner == "universal_setup":
            problems.append(f"{component_id} leaks Setup ownership into FacMan")
        root = roots.get(str(repository))
        if root is not None and not (root / path).exists():
            problems.append(f"component path does not exist: {repository}:{path}")

    for path in coverage_paths():
        if not is_covered(path, components):
            problems.append(f"unclassified runtime or contract component: {path}")

    expected_incubators = {
        "runtime/client": "ULK-CPP-CLIENT-ADAPTER-EXTRACTION-01",
        "runtime/platform": "ULK-EXECUTION-FOUNDATION-EXTRACTION-01",
        "runtime/workspace": "ULK-REFERENCE-PERSISTENCE-EXTRACTION-01",
        "runtime/transaction": "ULK-REFERENCE-PERSISTENCE-EXTRACTION-01",
    }
    indexed = {
        str(component.get("path")): component
        for component in components
        if component.get("repository") == "factorio-launcher"
    }
    for path, dependency in expected_incubators.items():
        component = indexed.get(path, {})
        if (
            component.get("owner") != "temporary_incubator"
            or component.get("final_owner") != "universal_launcher"
            or component.get("extraction_dependency") != dependency
        ):
            problems.append(
                f"{path} must remain an explicit Universal Launcher incubator"
            )
    application = indexed.get("runtime/factorio/application", {})
    if application.get("owner") != "factorio_binding":
        problems.append(
            "runtime/factorio/application must remain Factorio-owned after module decomposition"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate cross-repository component ownership."
    )
    parser.add_argument("--require-siblings", action="store_true")
    args = parser.parse_args([] if argv is None else argv)
    problems = check(require_siblings=args.require_siblings)
    if problems:
        for problem in problems:
            print(f"component-ownership-check: {problem}", file=sys.stderr)
        return 1
    print("component-ownership-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
