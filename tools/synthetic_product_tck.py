# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Run the development-only cross-provider synthetic product TCK."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "synthetic-product-tck"
ORCHESTRATION = FIXTURE_ROOT / "orchestration.v1.json"
JOURNAL = FIXTURE_ROOT / "interrupted-setup-journal.v1.json"
OBSERVATION_STEM = "synthetic-product-tck-observation.v1"
EXPECTED_ULK_SHA = "5479939ca5cbc9ee0f901608a92012778b4752ae"
EXPECTED_USK_SHA = "d2a2aae7e61c47035c92334b0522143b4fea3880"
FORBIDDEN_TERMS = {
    "factorio",
    "dominium",
    "domino",
    "c3",
    "cassette",
    "catalogue",
    "game",
    "simulation",
}
OBLIGATIONS = (
    "package_authoring",
    "inspection",
    "plan_preview",
    "installation_fixture",
    "reference_composition",
    "launch_preview",
    "structured_refusal",
    "recovery_fixture",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _text_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            values.extend(_text_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_text_values(child))
    elif isinstance(value, str):
        values.append(value)
    return values


def validate_cross_provider_contracts(
    composition: dict[str, Any],
    package: dict[str, Any],
    recipe: dict[str, Any],
    orchestration: dict[str, Any],
    journal: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    product = composition.get("product", {})
    expected = {
        "product_id": "org.example.fixture",
        "product_version": "1.0.0",
        "upgrade_version": "1.1.0",
        "component_id": "core",
        "entrypoint": "bin/fixture",
        "data_file": "share/message.txt",
        "launch_capability": "single_process",
    }
    for key, value in expected.items():
        if orchestration.get(key) != value:
            problems.append(f"orchestration must bind {key} to {value}")

    product_id = expected["product_id"]
    version = expected["product_version"]
    if product.get("product_id") != product_id or product.get("exact_version") != version:
        problems.append("ULK composition does not bind the fixture product and version")
    if package.get("product_id") != product_id or package.get("product_version") != version:
        problems.append("USK package does not bind the fixture product and version")
    if recipe.get("product_id") != product_id or recipe.get("product_version") != version:
        problems.append("USK recipe does not bind the fixture product and version")

    components = package.get("components", [])
    component = components[0] if len(components) == 1 else {}
    if component.get("component_id") != expected["component_id"]:
        problems.append("USK package must contain exactly the core component")
    entries = {
        entry.get("path")
        for entry in component.get("entries", [])
        if isinstance(entry, dict)
    }
    required_entries = {expected["entrypoint"], expected["data_file"]}
    if entries != required_entries:
        problems.append("USK component entries do not match the neutral fixture closure")
    if set(package.get("immutable_paths", [])) != required_entries:
        problems.append("USK immutable paths do not match the installation fixture")
    if set(orchestration.get("installation_projection", [])) != required_entries:
        problems.append("installation projection does not match the package closure")

    entrypoints = composition.get("entrypoints", [])
    entrypoint = entrypoints[0] if len(entrypoints) == 1 else {}
    if entrypoint.get("relative_path") != expected["entrypoint"]:
        problems.append("ULK entrypoint does not bind bin/fixture")
    if entrypoint.get("artifact_set_id") != expected["component_id"]:
        problems.append("ULK artifact set does not bind the USK core component")
    capabilities = {
        item.get("kind")
        for item in entrypoint.get("capabilities", [])
        if isinstance(item, dict)
    }
    if capabilities != {expected["launch_capability"]}:
        problems.append("ULK launch preview must bind only single_process")

    if recipe.get("component_ids") != [expected["component_id"]]:
        problems.append("USK recipe does not select exactly the core component")
    migrations = recipe.get("migrations", [])
    migration = migrations[0] if len(migrations) == 1 else {}
    if (
        migration.get("from_version") != version
        or migration.get("to_version") != expected["upgrade_version"]
    ):
        problems.append("USK recipe does not bind the 1.0.0 to 1.1.0 upgrade")

    if set(orchestration.get("proof_obligations", {})) != set(OBLIGATIONS):
        problems.append("orchestration proof obligations do not match the closed TCK set")
    refusal = orchestration.get("structured_refusal", {})
    if refusal.get("code") != "authority_not_granted":
        problems.append("structured refusal must use authority_not_granted")
    if refusal.get("mutation_executed") is not False:
        problems.append("structured refusal must prove no setup mutation")
    if refusal.get("process_started") is not False:
        problems.append("structured refusal must prove no process start")
    authority = orchestration.get("authority", {})
    if not authority or any(value is not False for value in authority.values()):
        problems.append("all TCK authority booleans must remain false")

    journal_expected = {
        "product_id": product_id,
        "component_id": expected["component_id"],
        "from_version": version,
        "to_version": expected["upgrade_version"],
        "state": "interrupted_before_apply",
        "mutation_executed": False,
    }
    for key, value in journal_expected.items():
        if journal.get(key) != value:
            problems.append(f"interrupted journal must bind {key} to {value}")
    recovery = journal.get("recovery", {})
    if recovery.get("disposition") != "required" or recovery.get("applied") is not False:
        problems.append("interrupted journal must preview required recovery without applying it")

    scanned_values = _text_values(orchestration) + _text_values(journal)
    for value in scanned_values:
        lowered = value.lower()
        for term in FORBIDDEN_TERMS:
            if re.search(rf"(^|[^a-z0-9]){re.escape(term)}([^a-z0-9]|$)", lowered):
                problems.append(f"synthetic fixture contains forbidden product term {term}")
    return problems


def _run(command: list[str], cwd: Path) -> str:
    environment = dict(os.environ)
    environment["GIT_NO_LAZY_FETCH"] = "1"
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=environment,
    )
    if completed.returncode != 0:
        output = completed.stdout.strip()
        raise RuntimeError(f"command failed in {cwd}: {' '.join(command)}\n{output}")
    return completed.stdout.strip()


def _provider_head(root: Path, expected: str) -> str:
    observed = _run(["git", "rev-parse", "HEAD"], root)
    if observed != expected:
        raise ValueError(f"{root.name} HEAD is {observed}; expected {expected}")
    main_refs = ("refs/remotes/origin/main", "refs/heads/main")
    available = []
    for ref in main_refs:
        exists = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", ref],
            cwd=root,
            check=False,
        ).returncode == 0
        if exists:
            available.append(ref)
    if not available:
        raise ValueError(f"{root.name} has no local main ref for reachability proof")
    if not any(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected, ref],
            cwd=root,
            check=False,
        ).returncode == 0
        for ref in available
    ):
        raise ValueError(f"{root.name} expected commit is not reachable from main")
    return observed


def _require_out_of_tree(output_dir: Path, roots: list[Path]) -> Path:
    resolved = output_dir.resolve()
    for root in roots:
        if resolved == root.resolve() or resolved.is_relative_to(root.resolve()):
            raise ValueError("--output-dir must be outside every source/provider checkout")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _markdown(observation: dict[str, Any]) -> str:
    results = observation["proof_obligations"]
    lines = [
        "# Synthetic product TCK observation",
        "",
        f"- Result: `{observation['result']}`",
        f"- FacMan source: `{observation['source']['facman']}`",
        f"- Universal Launcher: `{observation['source']['universal_launcher']}`",
        f"- Universal Setup: `{observation['source']['universal_setup']}`",
        "- Development-only: `true`",
        "- Stable provider pins changed: `false`",
        "- Setup mutation executed: `false`",
        "- Product process started: `false`",
        "",
        "## Proof obligations",
        "",
    ]
    lines.extend(f"- `{name}`: `{results[name]}`" for name in OBLIGATIONS)
    lines.extend(
        [
            "",
            "Provider contracts remain `fixture-qualified`; this observation does not",
            "promote contract maturity or grant consumer adoption authority.",
            "",
        ]
    )
    return "\n".join(lines)


def execute(
    ulk_root: Path,
    usk_root: Path,
    expected_ulk_sha: str,
    expected_usk_sha: str,
    output_dir: Path,
) -> dict[str, Any]:
    roots = [ROOT.resolve(), ulk_root.resolve(), usk_root.resolve()]
    output = _require_out_of_tree(output_dir, roots)
    ulk_head = _provider_head(ulk_root, expected_ulk_sha)
    usk_head = _provider_head(usk_root, expected_usk_sha)

    _run([sys.executable, "tools/product_composition_contract_check.py"], ulk_root)
    _run([sys.executable, "tools/product_package_contract_check.py"], usk_root)

    composition_path = (
        ulk_root / "tests" / "fixtures" / "product-composition" / "neutral-product.v1.json"
    )
    package_root = usk_root / "tests" / "fixtures" / "product-package"
    fixture_paths = [
        ORCHESTRATION,
        JOURNAL,
        composition_path,
        package_root / "neutral-product.v1.json",
        package_root / "neutral-recipe.v1.json",
    ]
    composition = load_json(composition_path)
    package = load_json(package_root / "neutral-product.v1.json")
    recipe = load_json(package_root / "neutral-recipe.v1.json")
    orchestration = load_json(ORCHESTRATION)
    journal = load_json(JOURNAL)
    problems = validate_cross_provider_contracts(
        composition, package, recipe, orchestration, journal
    )
    if problems:
        raise ValueError("; ".join(problems))

    facman_head = _run(["git", "rev-parse", "HEAD"], ROOT)
    observation = {
        "schema": "facman.synthetic_product_tck_observation.v1",
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "development_only": True,
        "result": "pass",
        "source": {
            "facman": facman_head,
            "universal_launcher": ulk_head,
            "universal_setup": usk_head,
        },
        "fixture_digest_sha256": _digest(fixture_paths),
        "provider_local_fixtures": {
            "universal_launcher": "pass",
            "universal_setup": "pass",
        },
        "proof_obligations": {name: "pass" for name in OBLIGATIONS},
        "contract_maturity": {
            "universal_launcher": "fixture-qualified",
            "universal_setup": "fixture-qualified",
            "promoted": False,
        },
        "stable_provider_pins_changed": False,
        "consumer_adoption": False,
        "authority": orchestration["authority"],
        "mutation_executed": False,
        "process_started": False,
    }
    json_path = output / f"{OBSERVATION_STEM}.json"
    md_path = output / f"{OBSERVATION_STEM}.md"
    json_path.write_text(json.dumps(observation, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(observation), encoding="utf-8", newline="\n")
    print(f"synthetic-product-tck: pass; evidence: {output}")
    return observation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ulk-root", type=Path, required=True)
    parser.add_argument("--usk-root", type=Path, required=True)
    parser.add_argument("--expected-ulk-sha", default=EXPECTED_ULK_SHA)
    parser.add_argument("--expected-usk-sha", default=EXPECTED_USK_SHA)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        for value in (args.expected_ulk_sha, args.expected_usk_sha):
            if re.fullmatch(r"[0-9a-f]{40}", value) is None:
                raise ValueError("expected provider SHAs must be lowercase 40-hex commits")
        execute(
            args.ulk_root.resolve(),
            args.usk_root.resolve(),
            args.expected_ulk_sha,
            args.expected_usk_sha,
            args.output_dir,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"synthetic-product-tck: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
