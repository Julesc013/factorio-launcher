#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "release/index/foundation_public_beta_scope.v2.toml"
VERSION = ROOT / "release/index/version.v2.toml"


def detect() -> list[str]:
    with SCOPE.open("rb") as stream:
        scope = tomllib.load(stream)
    with VERSION.open("rb") as stream:
        version = tomllib.load(stream)
    problems: list[str] = []
    if scope.get("schema") != "facman.foundation_public_beta_scope.v2":
        problems.append("foundation scope has the wrong schema")
    if scope.get("candidate_version") != version.get("semver"):
        problems.append("foundation scope candidate must match canonical version")
    identity = scope.get("identity", {})
    expected_identity = {
        "public_gui": "FacMan",
        "public_terminal": "facman",
        "tui_invocation": "facman tui",
        "daemon_is_public_product": False,
        "toolkit_names_are_public": False,
        "downloads_per_platform": ["portable", "setup"],
    }
    if identity != expected_identity:
        problems.append("foundation public identity or two-download law has drifted")
    architecture = scope.get("architecture", {})
    required_true = {
        "facman_owns_factorio_domain",
        "universal_launcher_owns_generic_process_lifecycle",
        "universal_setup_owns_installed_software_mutation",
        "same_stage_feeds_portable_and_setup",
        "providers_are_exact_and_external",
        "provider_workspaces_are_detached_and_marker_owned",
        "runtime_resources_are_deterministic",
        "foreign_installations_are_read_only",
        "facman_owned_mutation_requires_plan_confirmation_and_recovery",
    }
    for field in sorted(required_true):
        if architecture.get(field) is not True:
            problems.append(f"foundation architecture.{field} must be true")
    if architecture.get("presentation_owns_policy") is not False:
        problems.append("presentation must not own product policy")
    if architecture.get("runtime_resources") != "facman.resources":
        problems.append("runtime resource identity must be facman.resources")
    authority = scope.get("authority", {})
    if not authority or any(value is not False for value in authority.values()):
        problems.append("external execution, acceptance, signing, and publication authority must remain false")
    if len(scope.get("required_user_outcomes", [])) < 15:
        problems.append("foundation scope omits essential local-first user outcomes")
    deferred = set(scope.get("deferred_features", []))
    for feature in {
        "network_mod_portal_acquisition",
        "automatic_self_update",
        "daemon_or_remote_administration",
        "plugin_marketplace",
    }:
        if feature not in deferred:
            problems.append(f"foundation scope must explicitly defer {feature}")
    if not (ROOT / str(scope.get("contract", ""))).is_file():
        problems.append("foundation scope contract document is missing")
    return problems


def main() -> int:
    problems = detect()
    if problems:
        for problem in problems:
            print(f"foundation-scope-check: {problem}", file=sys.stderr)
        return 1
    print("foundation-scope-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
