# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build and qualify the native AppKit and GTK C1 preview packages."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import plistlib
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Iterable

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

SCHEMA = ROOT / "contracts/schema/release/classic_preview_package_proof.v1.schema.json"
GTK_PRODUCT_METADATA = ROOT / "apps/gui/linux/gtk/generated_product_metadata.h"
APPKIT_PROFILE = "macos_legacy_appkit_x64"
GTK_PROFILE = "linux_x11_gtk_x64"
REQUIRED_PROBE = {
    "pages": "pass",
    "menu_keyboard": "pass",
    "resize": "pass",
    "focus_restoration": "pass",
    "appearance_recovery": "pass",
    "accessibility": "pass",
    "fixture_journey": "pass",
    "stale_refusal": "stale_readiness",
    "bounded_rpc": "pass",
    "authority": "fixture_only",
    "live_play": "false",
    "process_transport": "rpc --stdio",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="platform", required=True)
    for platform_id in ("appkit", "gtk"):
        sub = subparsers.add_parser(platform_id)
        sub.add_argument("--build-root", required=True)
        sub.add_argument("--stage-root", required=True)
        sub.add_argument("--dist", required=True)
        sub.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    try:
        build_root = Path(args.build_root).resolve()
        stage_root = Path(args.stage_root).resolve()
        dist_root = Path(args.dist).resolve()
        evidence = Path(args.evidence).resolve()
        require_clean_source()
        source_revision = git_revision()
        if args.platform == "appkit":
            report = prove_appkit(build_root, stage_root, dist_root, source_revision)
        else:
            report = prove_gtk(build_root, stage_root, dist_root, source_revision)
        problems = validate_evidence(report)
        if problems:
            raise ValueError("classic preview evidence violates its schema: " + "; ".join(problems))
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print(f"classic-preview-package-proof: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def prove_appkit(build_root: Path, stage_root: Path, dist_root: Path, revision: str) -> dict[str, object]:
    if sys.platform != "darwin" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise ValueError("AppKit proof requires a native macOS Intel runner")
    require_new_directory(stage_root)
    dist_root.mkdir(parents=True, exist_ok=True)
    configure_appkit(build_root)
    built_app = find_appkit_bundle(build_root)
    binary = built_app / "Contents/MacOS/FacMan"
    binary_report = inspect_appkit_binary(binary, built_app / "Contents/Info.plist")

    with tempfile.TemporaryDirectory(prefix="facman-appkit-preview-proof-") as temporary:
        scratch = Path(temporary)
        success_mock = write_rpc_mock(scratch / "facman fixture rpc", timeout=False)
        initial_probe = run_appkit_probe(binary, success_mock, scratch / "arbitrary cwd Ω")
        staged_app = stage_root / "FacMan.app"
        shutil.copytree(built_app, staged_app, symlinks=True)
        signing = {
            "status": "not_requested",
            "reason": "Credential operations are deferred outside pull-request-controlled proof code.",
        }
        notarization = {
            "status": "not_requested",
            "reason": "Credential operations are deferred outside pull-request-controlled proof code.",
        }
        manifest = stage_root / "manifest/preview-files.sha256"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        file_count = write_file_manifest(stage_root, manifest)
        verify_file_manifest(stage_root, manifest)

        relocated = scratch / "Relocated FacMan Ω" / "FacMan.app"
        relocated.parent.mkdir(parents=True)
        shutil.copytree(staged_app, relocated, symlinks=True)
        helper = relocated / "Contents/Helpers/facman"
        helper.parent.mkdir(parents=True)
        shutil.copy2(success_mock, helper)
        relocated_probe = run_appkit_probe(
            relocated / "Contents/MacOS/FacMan", None, scratch / "relocated cwd with spaces"
        )
        archive = dist_root / f"facman-{revision[:12]}-macos-appkit-x64-preview.tar.gz"
        deterministic_tar(stage_root, archive)
        checksum_file = write_artifact_checksum(archive)

    return evidence_report(
        platform_id="appkit",
        profile_id=APPKIT_PROFILE,
        target_os="macos",
        revision=revision,
        artifact=archive,
        checksum_file=checksum_file,
        binary=binary_report,
        probe=initial_probe,
        relocated_probe=relocated_probe,
        manifest=manifest,
        file_count=file_count,
        signing=signing,
        notarization=notarization,
        toolchain_identity="; ".join(output(["xcodebuild", "-version"]).splitlines()),
        platform_accessibility={
            "at_spi_bridge": "not_applicable",
            "orca": "not_applicable",
            "external_at_spi": "not_applicable",
            "high_contrast": "not_applicable",
            "timeout_process_tree": "not_applicable",
        },
    )


def prove_gtk(build_root: Path, stage_root: Path, dist_root: Path, revision: str) -> dict[str, object]:
    if not sys.platform.startswith("linux") or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise ValueError("GTK proof requires a native Linux x64 runner")
    for command_name in ("meson", "file", "readelf", "ldd", "xvfb-run", "dbus-run-session", "orca"):
        if shutil.which(command_name) is None:
            raise ValueError(f"GTK proof requires {command_name}")
    require_new_directory(stage_root)
    dist_root.mkdir(parents=True, exist_ok=True)
    if not (build_root / "build.ninja").is_file():
        run(["meson", "setup", str(build_root), str(ROOT / "apps/gui/linux/gtk"), "--prefix=/usr", "--buildtype=release"])
    run(["meson", "compile", "-C", str(build_root)])
    run(["meson", "install", "-C", str(build_root), "--destdir", str(stage_root)])
    binary = stage_root / "usr/bin/FacMan"
    if not binary.is_file():
        raise ValueError("GTK install did not create the public usr/bin/FacMan entrypoint")
    desktop = stage_root / "usr/share/applications/io.github.julesc013.facman.desktop"
    if not desktop.is_file() or "Icon=io.github.julesc013.facman" not in desktop.read_text(encoding="utf-8"):
        raise ValueError("GTK package is missing the FacMan desktop icon binding")
    for size in (16, 24, 32, 48, 64, 96, 128, 192, 256, 512):
        icon = stage_root / (
            f"usr/share/icons/hicolor/{size}x{size}/apps/"
            "io.github.julesc013.facman.png"
        )
        if not icon.is_file() or icon.is_symlink():
            raise ValueError(f"GTK package is missing the {size}px FacMan hicolor icon")
    binary_report = inspect_gtk_binary(binary)

    with tempfile.TemporaryDirectory(prefix="facman-gtk-preview-proof-") as temporary:
        scratch = Path(temporary)
        success_mock = write_rpc_mock(scratch / "facman fixture rpc", timeout=False)
        initial_probe, orca_pass, at_spi_pass = run_gtk_probe(
            binary, success_mock, scratch, expect_timeout=False
        )
        manifest = stage_root / "usr/share/facman/manifest/preview-files.sha256"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        file_count = write_file_manifest(stage_root, manifest)
        verify_file_manifest(stage_root, manifest)

        relocated_root = scratch / "Relocated GTK Ω package"
        shutil.copytree(stage_root, relocated_root, symlinks=True)
        relocated_binary = relocated_root / "usr/bin/FacMan"
        relocated_probe, relocated_orca, relocated_at_spi = run_gtk_probe(
            relocated_binary, success_mock, scratch / "relocated", expect_timeout=False
        )
        timeout_mock = write_rpc_mock(scratch / "facman timeout rpc", timeout=True)
        timeout_probe, _, _ = run_gtk_probe(
            relocated_binary, timeout_mock, scratch / "timeout", expect_timeout=True
        )
        if timeout_probe.get("rpc_timeout") != "pass":
            raise ValueError("GTK timeout probe did not report outcome_unknown")
        child_pid_path = scratch / "timeout/child.pid"
        if not child_pid_path.is_file():
            raise ValueError("GTK timeout fixture did not record its descendant PID")
        require_process_gone(int(child_pid_path.read_text(encoding="utf-8").strip()))

        archive = dist_root / f"facman-{revision[:12]}-linux-gtk3-x64-preview.tar.gz"
        deterministic_tar(stage_root, archive)
        checksum_file = write_artifact_checksum(archive)

    return evidence_report(
        platform_id="gtk",
        profile_id=GTK_PROFILE,
        target_os="linux",
        revision=revision,
        artifact=archive,
        checksum_file=checksum_file,
        binary=binary_report,
        probe=initial_probe,
        relocated_probe=relocated_probe,
        manifest=manifest,
        file_count=file_count,
        signing={
            "status": "not_requested",
            "reason": "Trusted checksum signing workflow is deferred; pull-request CI receives no credentials.",
        },
        notarization={"status": "not_requested", "reason": "Notarization does not apply to GTK."},
        toolchain_identity=output(["cc", "--version"]).splitlines()[0],
        platform_accessibility={
            "at_spi_bridge": initial_probe["at_spi_bridge"],
            "orca": "pass" if orca_pass and relocated_orca else "fail",
            "external_at_spi": "pass" if at_spi_pass and relocated_at_spi else "fail",
            "high_contrast": initial_probe["high_contrast"],
            "timeout_process_tree": "pass",
        },
    )


def evidence_report(
    *, platform_id: str, profile_id: str, target_os: str, revision: str,
    artifact: Path, checksum_file: Path, binary: dict[str, object],
    probe: dict[str, str], relocated_probe: dict[str, str], manifest: Path,
    file_count: int, signing: dict[str, str], notarization: dict[str, str],
    toolchain_identity: str,
    platform_accessibility: dict[str, str],
) -> dict[str, object]:
    require_probe(probe)
    require_probe(relocated_probe)
    blockers = ["frontend_only_no_backend_closure", "credential_operations_deferred"]
    toolchain_pin = "hosted_image_label_only"
    if platform_id == "appkit":
        blockers.append("exact_supported_legacy_xcode_not_pinned")
        toolchain_pin = "mutable_macos_runner_blocker"
    else:
        blockers.append("trusted_checksum_signing_workflow_deferred")
    return {
        "schema": "facman.classic_preview_package_proof.v1",
        "status": "provisional",
        "platform": platform_id,
        "profile_id": profile_id,
        "target_os": target_os,
        "target_arch": "x64",
        "source_revision": revision,
        "source_dirty": False,
        "runner": os.environ.get("ImageOS") or f"{platform.system()}-{platform.release()}",
        "artifact_scope": "frontend_only_prototype",
        "toolchain": {
            "identity": toolchain_identity,
            "pin_status": toolchain_pin,
        },
        "blockers": blockers,
        "artifact": {
            "name": artifact.name,
            "format": "tar.gz",
            "size": artifact.stat().st_size,
            "sha256": sha256(artifact),
            "checksum_file": checksum_file.name,
            "signature_file": None,
        },
        "binary": binary,
        "runtime": {
            "probe": "pass",
            "relocated_probe": "pass",
            "menu_keyboard": probe["menu_keyboard"],
            "resize": probe["resize"],
            "focus_restoration": probe["focus_restoration"],
            "bounded_rpc": probe["bounded_rpc"],
            "fixture_journey": probe["fixture_journey"],
            "accessibility": probe["accessibility"],
            "appearance_recovery": probe["appearance_recovery"],
            "at_spi_bridge": platform_accessibility["at_spi_bridge"],
            "orca": platform_accessibility["orca"],
            "external_at_spi": platform_accessibility["external_at_spi"],
            "high_contrast": platform_accessibility["high_contrast"],
            "timeout_process_tree": platform_accessibility["timeout_process_tree"],
            "live_play": False,
        },
        "package": {
            "manifest": manifest.name,
            "manifest_sha256": sha256(manifest),
            "file_count": file_count,
            "relocated": True,
            "checksum_verified": verify_artifact_checksum(artifact, checksum_file),
            "profile_contract_satisfied": False,
            "clean_machine_backend_closure": False,
        },
        "signing": signing,
        "notarization": notarization,
        "claims": {
            "compile": "provisional",
            "runtime": "frontend_fixture_preview",
            "package": "frontend_prototype_only",
            "accessibility": "provisional",
            "support": "unavailable",
            "live_play": False,
        },
    }


def configure_appkit(build_root: Path) -> None:
    run([
        "cmake", "-S", str(ROOT / "apps/gui/macos/appkit"), "-B", str(build_root),
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OSX_ARCHITECTURES=x86_64",
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=10.13",
    ])
    run(["cmake", "--build", str(build_root), "--config", "Release", "--parallel"])


def find_appkit_bundle(build_root: Path) -> Path:
    candidates = [build_root / "FacMan.app", build_root / "Release/FacMan.app"]
    for candidate in candidates:
        if (candidate / "Contents/MacOS/FacMan").is_file():
            return candidate
    raise ValueError("AppKit build did not produce FacMan.app")


def inspect_appkit_binary(binary: Path, plist_path: Path) -> dict[str, object]:
    identity = output(["file", str(binary)])
    architectures = output(["lipo", "-archs", str(binary)]).split()
    if architectures != ["x86_64"]:
        raise ValueError(f"AppKit bundle is not x86_64-only: {architectures}")
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    if plist.get("LSMinimumSystemVersion") != "10.13":
        raise ValueError("AppKit Info.plist lost the macOS 10.13 floor")
    icon_name = plist.get("CFBundleIconFile")
    icon = plist_path.parent / "Resources" / str(icon_name)
    if icon_name != "FacMan.icns" or not icon.is_file() or icon.is_symlink():
        raise ValueError("AppKit bundle is missing its exact FacMan.icns resource")
    load_commands = output(["otool", "-l", str(binary)])
    if "LC_RPATH" in load_commands:
        raise ValueError("AppKit preview binary contains LC_RPATH")
    if "minos 10.13" not in load_commands and "version 10.13" not in load_commands:
        raise ValueError("AppKit preview binary does not record deployment floor 10.13")
    dependencies = parse_otool_dependencies(output(["otool", "-L", str(binary)]))
    if not dependencies or any(not item.startswith(("/System/Library/", "/usr/lib/")) for item in dependencies):
        raise ValueError(f"AppKit dependency closure is not system-only: {dependencies}")
    return {
        "identity": identity,
        "architectures": architectures,
        "deployment_floor": "macos_10_13",
        "dependencies": dependencies,
        "rpath": None,
        "runpath": None,
    }


def inspect_gtk_binary(binary: Path) -> dict[str, object]:
    identity = output(["file", str(binary)])
    if "x86-64" not in identity and "x86_64" not in identity:
        raise ValueError(f"GTK binary is not x86_64: {identity}")
    dynamic = output(["readelf", "-d", str(binary)])
    if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
        raise ValueError("GTK preview binary contains RPATH/RUNPATH")
    ldd = output(["ldd", str(binary)])
    if "not found" in ldd:
        raise ValueError("GTK dependency closure contains unresolved libraries")
    dependencies = sorted({line.strip() for line in ldd.splitlines() if line.strip()})
    if not dependencies:
        raise ValueError("GTK dependency closure is empty")
    return {
        "identity": identity,
        "architectures": ["x86_64"],
        "deployment_floor": "ubuntu_24_04_gtk3_x11_runner",
        "dependencies": dependencies,
        "rpath": None,
        "runpath": None,
    }


def run_appkit_probe(binary: Path, mock: Path | None, cwd: Path) -> dict[str, str]:
    cwd.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if mock is None:
        env.pop("FACMAN_CLI", None)
        isolated_path = cwd / "path-with-python-only"
        isolated_path.mkdir()
        (isolated_path / "python3").symlink_to(sys.executable)
        env["PATH"] = str(isolated_path)
    else:
        env["FACMAN_CLI"] = str(mock)
    env["FACMAN_PRESENTATION_MODE"] = "evidence"
    completed = run([str(binary), "--facman-preview-self-test"], cwd=cwd, env=env, timeout=45)
    probe = parse_probe(completed.stdout)
    require_probe(probe)
    if probe.get("window_restoration") != "pass":
        raise ValueError("AppKit window restoration probe failed")
    return probe


def run_gtk_probe(
    binary: Path, mock: Path, scratch: Path, *, expect_timeout: bool
) -> tuple[dict[str, str], bool, bool]:
    scratch.mkdir(parents=True, exist_ok=True)
    marker = scratch / "orca.running"
    at_spi_report = scratch / "external-atspi.v1.txt"
    at_spi_release = scratch / "external-atspi.release"
    for stale in (marker, at_spi_report, at_spi_release):
        stale.unlink(missing_ok=True)
    env = os.environ.copy()
    env["FACMAN_CLI"] = str(mock)
    env["FACMAN_PRESENTATION_MODE"] = "evidence"
    env["FACMAN_PREVIEW_ORCA_MARKER"] = str(marker)
    env["FACMAN_PREVIEW_ATSPI_REPORT"] = str(at_spi_report)
    env["FACMAN_PREVIEW_ATSPI_RELEASE_FILE"] = str(at_spi_release)
    env["FACMAN_PREVIEW_WINDOW_NAME"] = gtk_window_title()
    if expect_timeout:
        env["FACMAN_PREVIEW_EXPECT_TIMEOUT"] = "1"
        env["FACMAN_PREVIEW_RPC_TIMEOUT_SECONDS"] = "1"
        env["FACMAN_PREVIEW_CHILD_PID_FILE"] = str(scratch / "child.pid")
    command = [
        "xvfb-run", "-a", "dbus-run-session", "--", "bash",
        str(ROOT / "tools/ci/gtk_preview_accessibility_session.sh"),
        str(binary), "--facman-preview-self-test",
    ]
    completed = run(command, cwd=scratch, env=env, timeout=45)
    probe = parse_probe(completed.stdout)
    require_probe(probe, allow_timeout=expect_timeout)
    marker_value = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    orca_pass = marker_value.startswith("orca_pid=") and marker_value[9:].isdigit()
    if not orca_pass:
        raise ValueError("fresh Orca liveness marker was not produced after the GTK accessibility query")
    external = parse_probe(at_spi_report.read_text(encoding="utf-8")) if at_spi_report.is_file() else {}
    at_spi_pass = (
        external.get("status") == "pass"
        and external.get("window_name") == "pass"
        and external.get("launch_deck_name") == "pass"
        and external.get("primary_name") == "pass"
        and external.get("primary_role") == "push button"
    )
    if not at_spi_pass:
        raise ValueError("external AT-SPI query did not prove the running FacMan names and roles")
    return probe, orca_pass, at_spi_pass


def gtk_window_title() -> str:
    prefix = "#define FACMAN_GUI_WINDOW_TITLE "
    for line in GTK_PRODUCT_METADATA.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            value = json.loads(line.removeprefix(prefix))
            if isinstance(value, str) and value:
                return value
            break
    raise ValueError("generated GTK metadata is missing a valid FACMAN_GUI_WINDOW_TITLE")


def parse_probe(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.replace("_", "").isalnum():
            values[key] = value
    return values


def require_probe(probe: dict[str, str], *, allow_timeout: bool = False) -> None:
    for key, expected in REQUIRED_PROBE.items():
        if probe.get(key) != expected:
            raise ValueError(f"native runtime probe failed {key}: {probe.get(key)!r}")
    if allow_timeout and probe.get("rpc_timeout") != "pass":
        raise ValueError("native timeout probe did not report pass")


def validate_evidence(report: dict[str, object]) -> list[str]:
    schema = json_contract.load_schema(SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(report), key=lambda item: list(item.absolute_path))
    ]


def write_rpc_mock(path: Path, *, timeout: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if timeout:
        content = """#!/usr/bin/env python3
import os
import pathlib
import subprocess
import time
child = subprocess.Popen(["sleep", "300"])
pathlib.Path(os.environ["FACMAN_PREVIEW_CHILD_PID_FILE"]).write_text(str(child.pid), encoding="utf-8")
time.sleep(300)
"""
    else:
        content = """#!/usr/bin/env python3
import json
import os
import pathlib
import sys
import time
request = json.load(sys.stdin)
required = ("request_id", "operation_id", "attempt_id", "command")
if request.get("schema") != "facman.transport_request.v2" or request.get("protocol_version") != 2:
    raise SystemExit("fixture requires a FacMan v2 transport request")
if any(not isinstance(request.get(key), str) or not request[key] for key in required):
    raise SystemExit("fixture requires complete request correlation identity")
release = os.environ.get("FACMAN_PREVIEW_ATSPI_RELEASE_FILE")
if release:
    deadline = time.monotonic() + 20
    while not pathlib.Path(release).is_file() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not pathlib.Path(release).is_file():
        raise SystemExit("external AT-SPI probe did not release the RPC fixture")
response = {
    "schema": "facman.transport_response.v2",
    "protocol_version": 2,
    "request_id": request["request_id"],
    "command": request["command"],
    "outcome": "ok",
    "payload": {"product_id": "factorio"},
    "error": None,
    "diagnostics": [],
    "effects": [],
    "operation": {
        "schema": "ulk.operation_outcome.v1",
        "operation_id": request["operation_id"],
        "attempt_id": request["attempt_id"],
        "outcome": "completed",
        "effects_may_have_occurred": False,
        "recovery": {"required": False, "transaction_id": "", "inspect_command": ""},
    },
}
print(json.dumps(response, separators=(",", ":")))
"""
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def write_file_manifest(root: Path, manifest: Path) -> int:
    relative_manifest = manifest.relative_to(root).as_posix()
    entries = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
        relative = path.relative_to(root).as_posix()
        if relative == relative_manifest:
            continue
        entries.append(f"{sha256(path)}  {relative}")
    manifest.write_text("\n".join(entries) + "\n", encoding="utf-8", newline="\n")
    return len(entries)


def verify_file_manifest(root: Path, manifest: Path) -> None:
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        path = root / relative
        if separator != "  " or not path.is_file() or sha256(path) != digest:
            raise ValueError(f"package manifest mismatch: {relative}")


def deterministic_tar(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in sorted([source, *source.rglob("*")], key=lambda item: item.relative_to(source.parent).as_posix()):
                    arcname = path.relative_to(source.parent).as_posix()
                    info = archive.gettarinfo(str(path), arcname)
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    info.mtime = 0
                    if info.isfile():
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)
                    else:
                        archive.addfile(info)


def write_artifact_checksum(artifact: Path) -> Path:
    checksum = artifact.with_name(artifact.name + ".sha256")
    checksum.write_text(f"{sha256(artifact)}  {artifact.name}\n", encoding="utf-8", newline="\n")
    return checksum


def verify_artifact_checksum(artifact: Path, checksum: Path) -> bool:
    return checksum.read_text(encoding="utf-8").strip() == f"{sha256(artifact)}  {artifact.name}"


def require_process_gone(pid: int) -> None:
    for _ in range(30):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    raise ValueError(f"GTK timeout left descendant process {pid} alive")


def require_new_directory(path: Path) -> None:
    if path.exists():
        if any(path.iterdir()) if path.is_dir() else True:
            raise ValueError(f"refusing non-empty proof output root: {path}")
    else:
        path.mkdir(parents=True)


def parse_otool_dependencies(text: str) -> list[str]:
    dependencies = []
    for line in text.splitlines()[1:]:
        value = line.strip().split(" (compatibility version", 1)[0]
        if value:
            dependencies.append(value)
    return sorted(set(dependencies))


def git_revision() -> str:
    revision = output(["git", "rev-parse", "HEAD"], cwd=ROOT).lower()
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise ValueError("cannot resolve exact source revision")
    return revision


def require_clean_source() -> None:
    dirty = output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT)
    if dirty:
        raise ValueError("classic preview proof requires an exact clean worktree; source_dirty would be true")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output(command: list[str], *, cwd: Path | None = None) -> str:
    return run(command, cwd=cwd).stdout.strip()


def run(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd or ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


if __name__ == "__main__":
    raise SystemExit(main())
