# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    json_contract,
    package_build,
    package_hash_manifest,
    package_runtime_smoke,
    provenance_build,
)

PROFILE = "linux_portable_cli_x64"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the zero-skip Linux x64 CLI package proof.")
    parser.add_argument("--build-root", default="build/native-smoke")
    parser.add_argument("--out", default="build/linux-package-proof/packages")
    parser.add_argument("--dist", default="build/linux-package-proof/dist")
    parser.add_argument("--evidence", default="build/linux-package-proof/evidence.v1.json")
    args = parser.parse_args(argv)
    try:
        report = prove(
            Path(args.build_root).resolve(),
            Path(args.out).resolve(),
            Path(args.dist).resolve(),
        )
        evidence = Path(args.evidence).resolve()
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print(f"linux-package-proof: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def prove(build_root: Path, out_root: Path, dist_root: Path) -> dict[str, object]:
    require_linux_x64()
    package_root = package_build.build_profile(
        profile_id=PROFILE,
        out_root=out_root,
        build_root=build_root,
        dist_root=dist_root,
    )
    verify_clean(package_root)
    linkage = json.loads(
        (package_root / "manifest" / "linux_linkage.v1.json").read_text(encoding="utf-8")
    )
    if linkage.get("rpath") is not None or linkage.get("runpath") is not None:
        raise ValueError("Linux linkage proof contains an RPATH or RUNPATH")
    if not linkage.get("needed"):
        raise ValueError("Linux linkage proof did not record system dynamic dependencies")

    checks: list[str] = []
    package_runtime_smoke.smoke_package(package_root)
    checks.extend(["spaces_unicode", "arbitrary_cwd", "empty_path"])

    with tempfile.TemporaryDirectory(prefix="facman-linux-package-proof-") as temporary:
        root = Path(temporary)
        relocated = root / "Renamed FacMan Ω package"
        shutil.copytree(package_root, relocated)
        package_runtime_smoke.smoke_package(relocated)
        checks.append("renamed_extraction_root")

        with tempfile.TemporaryDirectory(
            prefix="facman-linux-external-workspace-"
        ) as external_container:
            external_workspace = Path(external_container) / "external workspace"
            package_runtime_smoke.smoke_package(relocated, external_workspace)
            if external_workspace.exists():
                raise ValueError("read-only package smoke created the external workspace")
        checks.append("external_workspace")

        read_only = root / "read only package"
        shutil.copytree(package_root, read_only)
        make_tree_read_only(read_only)
        try:
            package_runtime_smoke.smoke_package(read_only)
        finally:
            make_tree_writable(read_only)
        checks.append("read_only_package_root")

        mutation_proofs(package_root, root)
        checks.extend(
            [
                "missing_payload_refused",
                "modified_payload_refused",
                "extra_payload_refused",
                "wrong_target_refused",
                "wrong_architecture_refused",
                "linked_payload_refused",
                "incomplete_component_closure_refused",
            ]
        )

        archives = sorted(dist_root.glob("*.tar.gz"))
        if len(archives) != 1:
            raise ValueError(f"expected one Linux tar.gz artifact, found {len(archives)}")
        archive = archives[0]
        build_info = json.loads(
            (package_root / "manifest" / "build_info.v1.json").read_text(encoding="utf-8")
        )
        expected_name = (
            f"{build_info['filename_version']}-linux-cli-x64-portable.tar.gz"
        )
        if archive.name != expected_name:
            raise ValueError(f"unexpected Linux artifact name: {archive.name}")
        provenance = archive.with_name(archive.name + ".provenance.v1.json")
        provenance_problems = provenance_build.verify_artifact_provenance(
            provenance,
            archive,
            package_root,
        )
        if provenance_problems:
            raise ValueError("Linux artifact provenance failed: " + "; ".join(provenance_problems))
        checks.append("unsigned_provenance_verified")
        extracted = root / "archive extracted Ω"
        extracted.mkdir()
        with tarfile.open(archive, "r:gz") as bundle:
            safe_extract(bundle, extracted)
        package_runtime_smoke.smoke_package(extracted)
        checks.append("archive_extraction_runtime")

        with (package_root / "manifest" / "package.v1.toml").open("rb") as handle:
            manifest = tomllib.load(handle)
        report = {
            "schema": "facman.linux_cli_package_proof.v1",
            "status": "pass",
            "profile_id": PROFILE,
            "target_os": manifest["target_os"],
            "target_arch": manifest["target_arch"],
            "package_type": manifest["package_type"],
            "linkage_model": "project_static_system_dynamic",
            "artifact": archive.name,
            "artifact_size": archive.stat().st_size,
            "artifact_sha256": sha256(archive),
            "source_revisions": build_info["source_revisions"],
            "toolchain": build_info["toolchain"],
            "dynamic_dependencies": linkage["needed"],
            "rpath": None,
            "runpath": None,
            "checks": checks,
            "required_skips": 0,
            "signed": False,
            "published": False,
            "claim_scope": "ubuntu-24.04-x64-runner-package-preview",
        }
        schema = json_contract.load_schema(
            ROOT / "contracts" / "schema" / "release" / "linux_cli_package_proof.v1.schema.json"
        )
        problems = json_contract.validate(report, schema)
        if problems:
            raise ValueError("Linux package proof violates its contract: " + "; ".join(problems))
        return report


def require_linux_x64() -> None:
    if not sys.platform.startswith("linux"):
        raise ValueError("Linux package proof must run on Linux")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        raise ValueError(f"Linux package proof requires x64, got {platform.machine()}")


def verify_clean(root: Path) -> None:
    problems = package_hash_manifest.verify_manifest(root)
    if problems:
        raise ValueError("fresh Linux package failed integrity: " + "; ".join(problems))
    required = [
        root / "bin" / "facman",
        root / "contracts" / "schema",
        root / "content" / "factorio",
        root / "licenses" / "LICENSE",
        root / "licenses" / "THIRD_PARTY_NOTICES.md",
        root / "manifest" / "linux_linkage.v1.json",
        root / "manifest" / "sbom.spdx.v2.3.json",
    ]
    for path in required:
        if not path.exists():
            raise ValueError(f"Linux package is missing {path.relative_to(root).as_posix()}")
    for forbidden in [root / "bin" / "facman-tui", root / "bin" / "facmand", root / "lib"]:
        if forbidden.exists():
            raise ValueError(f"Linux CLI package contains forbidden breadth: {forbidden.name}")


def mutation_proofs(package_root: Path, root: Path) -> None:
    missing = copy_case(package_root, root / "missing contracts")
    shutil.rmtree(missing / "contracts")
    require_integrity_failure(missing, "missing")

    modified = copy_case(package_root, root / "modified payload")
    package_layout = modified / "docs" / "release" / "PACKAGE_LAYOUT.md"
    package_layout.write_bytes(package_layout.read_bytes() + b"\nmodified\n")
    require_integrity_failure(modified, "SHA-256 mismatch")

    extra = copy_case(package_root, root / "extra payload")
    (extra / "unexpected.bin").write_bytes(b"unexpected")
    require_integrity_failure(extra, "unhashed package file")

    wrong_target = copy_case(package_root, root / "wrong target")
    rewrite_manifest(wrong_target, 'target_os = "linux"', 'target_os = "windows"')
    require_runtime_verify_failure(wrong_target, "target, linkage, or entrypoint identity")

    wrong_arch = copy_case(package_root, root / "wrong architecture")
    rewrite_manifest(wrong_arch, 'target_arch = "x64"', 'target_arch = "arm64"')
    require_runtime_verify_failure(wrong_arch, "target, linkage, or entrypoint identity")

    linked = copy_case(package_root, root / "linked payload")
    original = linked / "docs" / "README.md"
    outside = root / "outside-readme.md"
    outside.write_text("outside\n", encoding="utf-8")
    original.unlink()
    original.symlink_to(outside)
    require_integrity_failure(linked, "linked")

    incomplete = copy_case(package_root, root / "incomplete closure")
    (incomplete / "content" / "factorio" / "product" / "factorio.product.toml").unlink()
    require_integrity_failure(incomplete, "missing")


def copy_case(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    return destination


def rewrite_manifest(root: Path, old: str, new: str) -> None:
    manifest = root / "manifest" / "package.v1.toml"
    text = manifest.read_text(encoding="utf-8")
    if old not in text:
        raise ValueError(f"mutation anchor not found: {old}")
    manifest.write_text(text.replace(old, new, 1), encoding="utf-8")
    package_hash_manifest.write_hash_manifest(root)


def require_integrity_failure(root: Path, expected: str) -> None:
    problems = package_hash_manifest.verify_manifest(root)
    if not problems or expected.lower() not in "\n".join(problems).lower():
        raise ValueError(f"integrity mutation was not refused as {expected}: {problems}")


def require_runtime_verify_failure(root: Path, expected: str) -> None:
    executable = root / "bin" / "facman"
    env = os.environ.copy()
    env["PATH"] = ""
    completed = subprocess.run(
        [str(executable), "package", "verify", "--json"],
        cwd=root.parent,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode == 0 or expected not in completed.stdout:
        raise ValueError(
            f"runtime identity mutation was not refused as {expected}: "
            f"stdout={completed.stdout} stderr={completed.stderr}"
        )


def make_tree_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            path.chmod(0o555)
        elif path == root / "bin" / "facman":
            path.chmod(0o555)
        else:
            path.chmod(0o444)
    root.chmod(0o555)


def make_tree_writable(root: Path) -> None:
    root.chmod(0o755)
    for path in root.rglob("*"):
        if path.is_dir():
            path.chmod(0o755)
        else:
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def safe_extract(bundle: tarfile.TarFile, destination: Path) -> None:
    for member in bundle.getmembers():
        if member.issym() or member.islnk() or member.name.startswith("/"):
            raise ValueError(f"Linux package archive contains an unsafe member: {member.name}")
        target = (destination / member.name).resolve()
        if destination.resolve() not in target.parents and target != destination.resolve():
            raise ValueError(f"Linux package archive member escapes extraction root: {member.name}")
    bundle.extractall(destination)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
