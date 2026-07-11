from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract, package_hash_manifest

SECRET_CORPUS = ROOT / "tests" / "fixtures" / "redaction" / "secrets_corpus.v1.json"


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Smoke-test a built FacMan package root.")
    parser.add_argument("--root", required=True, help="package root")
    parser.add_argument("--workspace", help="external workspace root")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    workspace = Path(args.workspace).resolve() if args.workspace else None
    try:
        report = smoke_package(root, workspace)
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"package-runtime-smoke: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def smoke_package(root: Path, workspace: Path | None = None) -> dict[str, object]:
    if not root.is_dir():
        raise ValueError(f"missing package root: {root}")
    facman = facman_executable(root)
    assert_required_layout(root)
    hash_problems = package_hash_manifest.verify_manifest(root)
    if hash_problems:
        raise ValueError("package hash verification failed: " + "; ".join(hash_problems))
    assert_no_python_runtime(root)
    assert_no_forbidden_payloads(root)
    with tempfile.TemporaryDirectory(prefix="facman-package-workspace-") as tmp:
        workspace_root = workspace or Path(tmp) / "workspace"
        external_cwd = Path(tmp) / "arbitrary current directory"
        external_cwd.mkdir()
        package_verify = run_command(external_cwd, [str(facman), "package", "verify", "--json"], pathless=True)
        version = run_command(external_cwd, [str(facman), "--version"], pathless=True)
        doctor = run_command(external_cwd, [str(facman), "--workspace", str(workspace_root), "doctor", "--json"], pathless=True)
        product = run_command(external_cwd, [str(facman), "product", "inspect", "--json"], pathless=True)
        package_verify_json = json.loads(package_verify.stdout)
        verify_schema = json_contract.load_schema(
            root / "contracts" / "schema" / "release" / "package_verify_report.v1.schema.json"
        )
        schema_problems = json_contract.validate(package_verify_json, verify_schema)
        if schema_problems:
            raise ValueError("package verify response failed its contract: " + "; ".join(schema_problems))
        doctor_json = json.loads(doctor.stdout)
        product_json = json.loads(product.stdout)
        combined_output = "\n".join([package_verify.stdout, version.stdout, doctor.stdout, product.stdout])
        normalized_output = combined_output.replace("\\\\", "\\")
        assert_workspace_reported(doctor_json, workspace_root)
        assert_no_source_paths(root, normalized_output)
        assert_no_secret_corpus(combined_output)
        if workspace_root.exists():
            raise ValueError("read-only doctor unexpectedly initialized external workspace")
        if root in workspace_root.parents or workspace_root == root:
            raise ValueError("workspace must be outside package root")
        if package_verify_json.get("status") != "pass":
            raise ValueError("packaged CLI did not verify its package")
    return {
        "schema": "facman.package_runtime_smoke.v1",
        "package_root": str(root),
        "facman": facman.relative_to(root).as_posix(),
        "version": version.stdout.strip(),
        "doctor_status": doctor_json.get("status"),
        "product_id": product_json.get("product_id"),
        "contracts_found": True,
        "content_found": True,
        "python_runtime": False,
        "doctor_workspace_write": False,
        "integrity": package_verify_json.get("integrity"),
        "authenticity": package_verify_json.get("authenticity"),
        "files_verified": package_verify_json.get("files_verified"),
        "pathless_runtime": True,
        "arbitrary_cwd": True,
    }


def assert_workspace_reported(doctor_json: dict[str, object], workspace: Path) -> None:
    reported = doctor_json.get("workspace")
    if not isinstance(reported, str):
        raise ValueError("doctor output did not include the external workspace path")
    if Path(reported).resolve() != workspace.resolve():
        raise ValueError(f"doctor reported the wrong workspace path: {reported}")


def facman_executable(root: Path) -> Path:
    candidates = [
        root / "bin" / "facman.exe",
        root / "bin" / "facman",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValueError("package root has no facman executable under bin/")


def assert_required_layout(root: Path) -> None:
    required = [
        root / "contracts" / "schema",
        root / "content" / "factorio",
        root / "manifest" / "package.v1.toml",
        root / "manifest" / "components.v1.json",
        root / "manifest" / "hashes.sha256",
        root / "manifest" / "sbom.spdx.v2.3.json",
    ]
    for path in required:
        if not path.exists():
            raise ValueError(f"missing package runtime path: {path.relative_to(root).as_posix()}")


def assert_no_python_runtime(root: Path) -> None:
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix().lower()
        if "__pycache__" in relative or relative.endswith((".py", ".pyc", ".pyo")):
            raise ValueError(f"Python runtime file leaked into package: {relative}")
        if path.name.lower() in {"python.exe", "python3", "python"}:
            raise ValueError(f"Python runtime executable leaked into package: {relative}")


def assert_no_forbidden_payloads(root: Path) -> None:
    forbidden = ["factorio.exe", "Factorio.app", "steamapps", "mod_portal_credentials"]
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        lowered = relative.lower()
        for marker in forbidden:
            if marker.lower() in lowered:
                raise ValueError(f"forbidden Factorio payload marker in package: {relative}")


def assert_no_source_paths(root: Path, output: str) -> None:
    repo_root = str(ROOT.resolve())
    package_parent = str(root.parent.resolve())
    for forbidden in [repo_root, package_parent]:
        if forbidden and forbidden in output:
            raise ValueError(f"package command output leaked build/source path: {forbidden}")
    if str(root.resolve()) in output:
        raise ValueError("package command output leaked package root path")


def assert_no_secret_corpus(text: str) -> None:
    if not SECRET_CORPUS.is_file():
        return
    values = json.loads(SECRET_CORPUS.read_text(encoding="utf-8")).get("values", [])
    for value in values:
        if str(value) in text:
            raise ValueError(f"package command output leaked secret corpus value: {value}")


def run_command(cwd: Path, command: list[str], pathless: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if pathless:
        env["PATH"] = ""
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


if __name__ == "__main__":
    raise SystemExit(main())
