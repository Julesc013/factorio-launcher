# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Plan and execute the Windows Technical Preview qualification obligations.

The release compiler owns the obligation set.  This runner only binds each
resolved obligation to an existing evidence producer and records the exact
inputs and outputs.  A repaired-provider canary may prove implementation
readiness, but package-custody obligations remain blocked until that provider
is canonical in the tracked release inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release_compiler.compiler import load_inputs, resolve  # noqa: E402
from tools import json_contract  # noqa: E402

TARGET = "windows_winforms_technical_preview_x64"
ARTIFACT = "windows_winforms_technical_preview_zip"
SCHEMA = ROOT / "contracts/schema/release/preview_obligation_ledger.v1.schema.json"
PACKAGE_OBLIGATIONS = {
    "forbidden_payload_scan",
    "package_adapter_round_trip",
    "package_relocation_smoke",
    "package_reproducibility_proof",
    "package_runtime_smoke",
    "windows_linkage_check",
    "winforms_backend_identity_check",
    "zip_structure_check",
}


@dataclass(frozen=True)
class ObligationSpec:
    commands: tuple[tuple[str, ...], ...]
    requirements: frozenset[str]
    invalidation_paths: tuple[str, ...]


def _python(*arguments: str) -> tuple[str, ...]:
    return (sys.executable, *arguments)


def _ctest(name: str) -> tuple[str, ...]:
    return (
        "ctest", "--test-dir", "{build_root}", "-C", "{configuration}",
        "--output-on-failure", "-R", f"^{name}$",
    )


SPECS: dict[str, ObligationSpec] = {
    "bounded_human_cli_smoke": ObligationSpec(
        (_python("-m", "unittest", "-v", "tests.test_cli", "tests.test_terminal_frontend_foundation"),),
        frozenset({"build_root"}), ("apps/cli/", "runtime/frontend/"),
    ),
    "cli_json_transport_response_v2": ObligationSpec(
        (_python("-m", "unittest", "-v", "tests.test_cli_machine_result"),),
        frozenset({"build_root"}), ("apps/cli/", "contracts/schema/transport/"),
    ),
    "facman_cli_smoke": ObligationSpec(
        (_ctest("facman_client_smoke"),), frozenset({"build_root"}),
        ("apps/cli/", "runtime/client/"),
    ),
    "factorio_binding_smoke": ObligationSpec(
        (_ctest("flb_command_bridge_smoke"),), frozenset({"build_root"}),
        ("runtime/factorio/", "runtime/client/"),
    ),
    "factorio_content_contract": ObligationSpec(
        (_python("-m", "unittest", "-v", "tests.test_factorio_version_capability_corpus"),),
        frozenset(), ("content/factorio/", "contracts/schema/factorio/"),
    ),
    "flb_abi_layout": ObligationSpec(
        (_ctest("facman_abi_layout_smoke"),), frozenset({"build_root"}),
        ("include/", "runtime/factorio/"),
    ),
    "forbidden_payload_scan": ObligationSpec(
        (_python("tools/package_runtime_smoke.py", "--root", "{package_root}"),),
        frozenset({"package_root"}), ("tools/package/", "release/profiles/"),
    ),
    "frontend_contract": ObligationSpec(
        (_python("tools/frontend_contract_check.py"),), frozenset(),
        ("contracts/command/frontend/", "runtime/frontend/", "apps/"),
    ),
    "package_adapter_round_trip": ObligationSpec(
        (_python("tools/facman_release.py", "verify-package", "--resolution", "{resolution}",
                 "--artifact", ARTIFACT, "--package", "{artifact}"),),
        frozenset({"resolution", "artifact"}), ("tools/release_compiler/", "tools/package/"),
    ),
    "package_relocation_smoke": ObligationSpec(
        (_python("tools/package_runtime_smoke.py", "--root", "{package_root}"),),
        frozenset({"package_root"}), ("tools/package_runtime_smoke.py", "runtime/package/"),
    ),
    "package_reproducibility_proof": ObligationSpec(
        (_python("tools/package_reproducibility_proof.py", "--profile",
                 "windows_legacy_winforms_x64", "--build-root", "{build_root}"),),
        frozenset({"build_root"}), ("tools/package/", "release/profiles/windows_legacy_winforms_x64/"),
    ),
    "package_runtime_smoke": ObligationSpec(
        (_python("tools/package_runtime_smoke.py", "--root", "{package_root}"),),
        frozenset({"package_root"}), ("tools/package_runtime_smoke.py", "runtime/package/"),
    ),
    "presentation_contract_conformance": ObligationSpec(
        (_python("tools/cross_frontend_journey_conformance.py"),),
        frozenset({"build_root"}), ("runtime/factorio/application/", "apps/tui/", "apps/gui/windows/"),
    ),
    "reuse_compliance": ObligationSpec(
        (_python("tools/compliance_check.py"),), frozenset(),
        ("LICENSE", "LICENSES/", "THIRD_PARTY_NOTICES.md"),
    ),
    "same_binary_tui_smoke": ObligationSpec(
        (
            _ctest("facman_tui_smoke"),
            _python("-m", "unittest", "-v", "tests.test_tui_product",
                    "tests.test_terminal_frontend_foundation"),
        ),
        frozenset({"build_root"}), ("apps/cli/", "apps/tui/", "runtime/frontend/"),
    ),
    "schema_validate": ObligationSpec(
        (_python("tools/schema_validate.py"),), frozenset(),
        ("contracts/schema/",),
    ),
    "source_vs_sdk_conformance": ObligationSpec(
        (_ctest("facman_installed_sdk_smoke"),), frozenset({"build_root"}),
        ("cmake/FacManProviders.cmake", "release/index/workspace_lock.v1.toml"),
    ),
    "ulk_provider_contract_fixture": ObligationSpec(
        (_ctest("facman_ulk_session_last_run_provider_smoke"),),
        frozenset({"build_root"}), ("runtime/factorio/application/last_run_provider.cpp",),
    ),
    "usk_provider_contract_fixture": ObligationSpec(
        (_ctest("m1_three_repository_system_proof"),), frozenset({"build_root"}),
        ("cmake/FacManProviders.cmake", "runtime/factorio/setup_gateway.cpp"),
    ),
    "windows_linkage_check": ObligationSpec(
        (_ctest("facman_runtime_package_identity_smoke"),),
        frozenset({"build_root", "package_root"}), ("tools/package/", "CMakeLists.txt"),
    ),
    "winforms_backend_identity_check": ObligationSpec(
        (_python("tools/winforms_backend_identity_check.py", "--package", "{package_root}"),),
        frozenset({"package_root"}), ("apps/gui/windows/winforms/", "tools/winforms_backend_identity_check.py"),
    ),
    "winforms_command_client_smoke": ObligationSpec(
        (_python("tools/winforms_command_client_smoke.py"),), frozenset(),
        ("apps/gui/windows/winforms/",),
    ),
    "zip_structure_check": ObligationSpec(
        (_python("tools/facman_release.py", "inspect-package", "--package", "{artifact}"),),
        frozenset({"artifact"}), ("tools/release_compiler/packages.py", "tools/package/archive.py"),
    ),
}


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolved_qualification_plan() -> dict[str, Any]:
    inputs = load_inputs(ROOT / "release/index", ROOT)
    graph = resolve(inputs, TARGET)
    return dict(graph["qualification_plan"])


def resolved_obligations() -> tuple[str, ...]:
    plan = resolved_qualification_plan()
    return tuple(sorted(str(value) for value in plan["obligations"]))


def validate_registry() -> list[str]:
    resolved = set(resolved_obligations())
    registered = set(SPECS)
    problems = []
    if resolved != registered:
        problems.append(
            f"registry differs from release compiler: missing={sorted(resolved - registered)} "
            f"extra={sorted(registered - resolved)}"
        )
    for obligation, spec in SPECS.items():
        if not spec.commands:
            problems.append(f"{obligation}: no evidence command")
        if not spec.invalidation_paths:
            problems.append(f"{obligation}: no invalidation path")
        if obligation in PACKAGE_OBLIGATIONS and not (
            spec.requirements & {"package_root", "artifact", "resolution"}
            or obligation == "package_reproducibility_proof"
        ):
            problems.append(f"{obligation}: package obligation has no package custody input")
    return problems


def _expand(command: tuple[str, ...], values: dict[str, str]) -> list[str]:
    return [part.format_map(values) for part in command]


def _source_identity(build_root: Path | None, provider_class: str) -> dict[str, Any]:
    status = _git("status", "--porcelain")
    result: dict[str, Any] = {
        "repository": "https://github.com/Julesc013/factorio-launcher.git",
        "commit": _git("rev-parse", "HEAD"),
        "tree": _git("rev-parse", "HEAD^{tree}"),
        "dirty": bool(status),
        "provider_class": provider_class,
    }
    if build_root is not None:
        identity = build_root / "facman-build-identity.v1.txt"
        if identity.is_file():
            result["build_identity_sha256"] = _digest(identity)
            result["build_identity"] = identity.read_text(encoding="utf-8").strip()
    return result


def run_factory(args: argparse.Namespace) -> dict[str, Any]:
    problems = validate_registry()
    if problems:
        raise ValueError("; ".join(problems))
    paths = {
        "build_root": args.build_root.resolve() if args.build_root else None,
        "package_root": args.package_root.resolve() if args.package_root else None,
        "artifact": args.artifact.resolve() if args.artifact else None,
        "resolution": args.resolution.resolve() if args.resolution else None,
    }
    values = {
        name: str(path) if path is not None else f"<{name}>"
        for name, path in paths.items()
    }
    values["configuration"] = args.configuration
    evidence_dir = args.evidence_dir.resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    python_paths = [str(ROOT / "tests"), str(ROOT)]
    if environment.get("PYTHONPATH"):
        python_paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    if paths["build_root"] is not None:
        build_root = paths["build_root"]
        assert build_root is not None
        candidates = (
            build_root / args.configuration / "facman.exe",
            build_root / "facman.exe", build_root / "facman",
        )
        executable = next((item for item in candidates if item.is_file()), None)
        environment["FACMAN_NATIVE_BUILD_ROOT"] = str(build_root)
        environment["FACMAN_NATIVE_CONFIGURATION"] = args.configuration
        if executable is not None:
            environment["FACMAN_CLI_EXE"] = str(executable)
            environment["FACMAN_NATIVE_CLI"] = str(executable)
            environment["FACMAN_TUI_EXE"] = str(executable)

    qualification_plan = resolved_qualification_plan()
    results = []
    for obligation in sorted(str(value) for value in qualification_plan["obligations"]):
        spec = SPECS[obligation]
        commands = [_expand(command, values) for command in spec.commands]
        missing = sorted(
            requirement for requirement in spec.requirements
            if paths.get(requirement) is None or not paths[requirement].exists()
        )
        status = "planned"
        classification = "not_executed"
        command_results: list[dict[str, Any]] = []
        if args.provider_class == "repaired_provider_canary" and obligation in PACKAGE_OBLIGATIONS:
            status = "blocked"
            classification = "canonical_provider_identity_pending"
        elif missing:
            status = "blocked"
            classification = "missing_input"
        elif args.execute:
            status = "pass"
            classification = "implementation_evidence_ready"
            for index, command in enumerate(commands, start=1):
                started = time.perf_counter()
                completed = subprocess.run(
                    command, cwd=ROOT, env=environment, check=False, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                log = evidence_dir / f"{obligation}.{index}.log"
                log.write_text(
                    f"command={json.dumps(command)}\nreturncode={completed.returncode}\n"
                    f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
                    encoding="utf-8", newline="\n",
                )
                command_results.append({
                    "command": command,
                    "returncode": completed.returncode,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "evidence": log.name,
                    "evidence_sha256": _digest(log),
                })
                if completed.returncode:
                    status = "fail"
                    classification = "command_failed"
                    break
        results.append({
            "id": obligation,
            "status": status,
            "classification": classification,
            "commands": commands,
            "requirements": sorted(spec.requirements),
            "missing_inputs": missing,
            "invalidation_paths": list(spec.invalidation_paths),
            "command_results": command_results,
        })

    counts = {value: sum(item["status"] == value for item in results)
              for value in ("pass", "fail", "blocked", "planned")}
    return {
        "schema": "facman.preview_obligation_ledger.v1",
        "target": TARGET,
        "qualification_plan": {
            "schema": qualification_plan["schema"],
            "product_version": qualification_plan["product_version"],
            "environment": qualification_plan["environment"],
            "resolution_digest": qualification_plan["resolution_digest"],
            "qualified": qualification_plan["qualified"],
        },
        "authority": {
            "release_authorized": False,
            "factorio_execution": False,
            "setup_mutation": False,
            "signing": False,
            "publication": False,
        },
        "source": _source_identity(paths["build_root"], args.provider_class),
        "inputs": {name: str(path) if path is not None else None for name, path in paths.items()},
        "configuration": args.configuration,
        "executed": bool(args.execute),
        "counts": counts,
        "obligations": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--resolution", type=Path)
    parser.add_argument("--configuration", default="Debug")
    parser.add_argument(
        "--provider-class", choices=("canonical", "repaired_provider_canary"),
        default="canonical",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-blocked", action="store_true")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_factory(args)
        schema = json_contract.load_schema(SCHEMA)
        schema_problems = json_contract.validate(report, schema)
        if schema_problems:
            raise ValueError("ledger schema invalid: " + "; ".join(schema_problems))
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"preview-obligation-factory: {exc}", file=sys.stderr)
        return 1
    counts = report["counts"]
    print(
        "preview-obligation-factory: "
        f"pass={counts['pass']} fail={counts['fail']} blocked={counts['blocked']} "
        f"planned={counts['planned']} -> {output}"
    )
    if counts["fail"]:
        return 1
    if counts["blocked"] and not args.allow_blocked:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
