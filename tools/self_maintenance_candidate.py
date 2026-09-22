#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build an exact predecessor and qualify a real Windows maintenance chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import time
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import development_layout
from tools import resource_package_cases as path_cases
from tools.release_programme_check import SEMVER_PATTERN


HEX_REVISION = re.compile(r"[0-9a-f]{40}\Z")
HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
DESCRIPTOR_KEYS = {
    "schema", "product_id", "product_version", "generation_relative_path",
    "facman_source_revision", "universal_setup_revision", "setup_protocol",
    "package_layout", "entrypoints", "automatic_update",
}
ENTRYPOINT_KEYS = {
    "gui_relative_path", "cli_relative_path", "maintenance_relative_path",
}
CURRENT_KEYS = {
    "schema", "product_id", "version", "generation", "portable_package",
    "portable_sha256", "facman_source_revision", "universal_setup_revision",
    "workspace_preserved", "automatic_update",
}
MAX_IDENTITY_BYTES = 64 * 1024
GIT_COMMAND = ("git", "-c", "core.longpaths=true")


def git_command(*arguments: str) -> list[str]:
    """Return a Git invocation safe for long Windows checkout paths."""

    return [*GIT_COMMAND, *arguments]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def setup_overlay_sha256(path: Path) -> str:
    """Hash the exact ZIP overlay materialized by the Windows setup runtime."""

    observed = exact_regular(path, "setup overlay")
    metadata = observed.lstat()
    identity = (
        metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns,
    )
    maximum_tail = 22 + 65535
    tail_size = min(metadata.st_size, maximum_tail)
    if tail_size < 22:
        raise ValueError("setup overlay is too small to contain a ZIP payload")
    with observed.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != identity:
            raise ValueError("setup overlay changed before it was read")
        source.seek(metadata.st_size - tail_size)
        tail = source.read(tail_size)
        eocd = next((
            position for position in range(len(tail) - 22, -1, -1)
            if tail[position:position + 4] == b"PK\x05\x06"
            and position + 22 + struct.unpack_from("<H", tail, position + 20)[0]
            == len(tail)
        ), None)
        if eocd is None:
            raise ValueError("setup overlay has no bounded ZIP end record")
        disk, central_disk, disk_entries, total_entries, central_size, central_offset = \
            struct.unpack_from("<HHHHII", tail, eocd + 4)
        if (
            disk != 0 or central_disk != 0 or disk_entries != total_entries
            or total_entries in (0, 0xffff)
            or central_size == 0xffffffff or central_offset == 0xffffffff
        ):
            raise ValueError("setup overlay uses an unsupported split or ZIP64 payload")
        absolute_eocd = metadata.st_size - tail_size + eocd
        relative_span = central_size + central_offset
        if relative_span > absolute_eocd:
            raise ValueError("setup overlay ZIP offsets are inconsistent")
        archive_start = absolute_eocd - relative_span
        source.seek(archive_start)
        if source.read(4) != b"PK\x03\x04":
            raise ValueError("setup overlay has no ZIP local header at its payload boundary")
        source.seek(archive_start + central_offset)
        if source.read(4) != b"PK\x01\x02":
            raise ValueError("setup overlay has no ZIP central directory at its payload boundary")
        source.seek(archive_start)
        digest = hashlib.sha256()
        remaining_bytes = metadata.st_size - archive_start
        while remaining_bytes:
            chunk = source.read(min(1024 * 1024, remaining_bytes))
            if not chunk:
                raise ValueError("setup overlay ended before its declared payload boundary")
            digest.update(chunk)
            remaining_bytes -= len(chunk)
        closed = os.fstat(source.fileno())
        if (closed.st_dev, closed.st_ino, closed.st_size, closed.st_mtime_ns) != identity:
            raise ValueError("setup overlay changed while it was read")
    final = observed.lstat()
    if (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) != identity:
        raise ValueError("setup overlay pathname changed while it was read")
    return digest.hexdigest()


def remaining(deadline: float, label: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError(f"{label} exceeded the outer candidate deadline")
    return value


def run(
    command: list[str], *, cwd: Path, deadline: float,
    env: dict[str, str] | None = None,
) -> None:
    subprocess.run(
        command, cwd=cwd, env=env, check=True,
        timeout=remaining(deadline, "candidate subprocess"),
    )


def capture(command: list[str], *, cwd: Path, deadline: float) -> str:
    return subprocess.run(
        command, cwd=cwd, check=True, text=True, capture_output=True,
        timeout=remaining(deadline, "candidate observation"),
    ).stdout.strip()


def revision(value: str, *, cwd: Path, deadline: float) -> str:
    if not HEX_REVISION.fullmatch(value):
        raise ValueError(f"revision must be exact lowercase 40-hex: {value!r}")
    resolved = capture(
        git_command("rev-parse", "--verify", f"{value}^{{commit}}"),
        cwd=cwd, deadline=deadline,
    )
    if resolved != value:
        raise ValueError(f"revision does not resolve to itself: {value!r}")
    return resolved


def head_revision(*, cwd: Path, deadline: float) -> str:
    resolved = capture(
        git_command("rev-parse", "--verify", "HEAD^{commit}"),
        cwd=cwd, deadline=deadline,
    )
    if not HEX_REVISION.fullmatch(resolved):
        raise ValueError("checkout HEAD is not a lowercase full Git revision")
    return resolved


def clean_source(root: Path, expected_revision: str, *, deadline: float) -> None:
    if head_revision(cwd=root, deadline=deadline) != expected_revision:
        raise ValueError("baseline checkout does not retain its requested revision")
    if capture(
        git_command("status", "--porcelain=v1", "--untracked-files=all"),
        cwd=root, deadline=deadline,
    ):
        raise ValueError("baseline checkout is not clean")


def clone_clean_detached(
    source_root: Path, destination: Path, expected_revision: str, *, deadline: float,
) -> None:
    """Clone an exact detached revision with long-path support persisted locally."""

    run(
        git_command(
            "clone", "--no-checkout", "--no-local", "-c", "core.longpaths=true",
            str(source_root), str(destination),
        ),
        cwd=source_root,
        deadline=deadline,
    )
    run(
        git_command("checkout", "--detach", expected_revision),
        cwd=destination,
        deadline=deadline,
    )
    clean_source(destination, expected_revision, deadline=deadline)


def version_at(root: Path) -> str:
    with (root / "release/index/version.v2.toml").open("rb") as source:
        value = tomllib.load(source)
    version = value.get("semver")
    if not isinstance(version, str) or not re.fullmatch(SEMVER_PATTERN, version):
        raise ValueError(f"source has no exact semantic version: {root}")
    return version


def exact_regular(path: Path, label: str) -> Path:
    observed = path_cases.plain_path(path)
    if not observed.is_absolute():
        raise ValueError(f"{label} must be absolute")
    metadata = observed.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError(f"{label} must be an exact single-link regular file")
    return observed


def exact_directory(path: Path, label: str) -> Path:
    observed = path_cases.plain_path(path)
    metadata = observed.lstat()
    if not observed.is_absolute() or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label} must be an exact absolute directory")
    return observed


def stable_regular_bytes(path: Path, label: str, limit: int) -> bytes:
    observed = path_cases.plain_path(path)
    metadata = observed.lstat()
    reparse = bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
    identity = (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
    if (stat.S_ISLNK(metadata.st_mode) or reparse or
            not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or
            metadata.st_size > limit):
        raise ValueError(f"{label} must be a bounded single-link regular file")
    with observed.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != identity:
            raise ValueError(f"{label} changed before it was read")
        content = source.read(limit + 1)
        closed = os.fstat(source.fileno())
        if (closed.st_dev, closed.st_ino, closed.st_size, closed.st_mtime_ns) != identity:
            raise ValueError(f"{label} changed while it was read")
    final = observed.lstat()
    if (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) != identity:
        raise ValueError(f"{label} pathname changed while it was read")
    if len(content) != metadata.st_size or len(content) > limit:
        raise ValueError(f"{label} exceeded its read bound")
    return content


def read_task_marker(task_root: Path) -> dict[str, object]:
    marker_path = task_root / development_layout.MARKER_NAME
    try:
        payload = json.loads(stable_regular_bytes(
            marker_path, "task ownership marker", 64 * 1024
        ))
    except json.JSONDecodeError as exc:
        raise ValueError(f"task ownership marker is not JSON: {marker_path}") from exc
    return development_layout.validate_marker_payload(task_root, payload, ROOT)


def _archive_json(archive: zipfile.ZipFile, name: str) -> dict[str, object]:
    matches = [entry for entry in archive.infolist() if entry.filename == name]
    if len(matches) != 1 or matches[0].is_dir() or matches[0].file_size > MAX_IDENTITY_BYTES:
        raise ValueError(f"produced setup has an ambiguous or oversized identity: {name}")
    value = json.loads(archive.read(matches[0]))
    if not isinstance(value, dict):
        raise ValueError(f"produced setup identity is not an object: {name}")
    return value


def identity_from_overlay(path: Path, portable: Path | None = None) -> dict[str, str]:
    path = exact_regular(path, "setup overlay")
    with zipfile.ZipFile(path) as archive:
        descriptor = _archive_json(
            archive, "facman/state/self-maintenance-package.v1.json"
        )
        current = _archive_json(archive, "facman/state/current-generation.v1.json")
    entrypoints = descriptor.get("entrypoints")
    if (
        set(descriptor) != DESCRIPTOR_KEYS
        or not isinstance(entrypoints, dict)
        or set(entrypoints) != ENTRYPOINT_KEYS
        or set(current) != CURRENT_KEYS
        or descriptor.get("schema") != "facman.self_maintenance_package.v1"
        or descriptor.get("product_id") != "facman"
        or descriptor.get("setup_protocol") != "facman.self_maintenance.v1"
        or descriptor.get("package_layout") != "versioned_generation_with_maintenance_v1"
        or descriptor.get("automatic_update") is not False
        or entrypoints != {
            "gui_relative_path": "FacMan.exe",
            "cli_relative_path": "bin/facman.exe",
            "maintenance_relative_path": "maintenance/FacManSetup.exe",
        }
        or current.get("schema") != "facman.current_generation.v1"
        or current.get("product_id") != "facman"
        or current.get("workspace_preserved") is not True
        or current.get("automatic_update") is not False
    ):
        raise ValueError("produced setup has incompatible exact identity schemas")
    version = descriptor.get("product_version")
    source_revision = descriptor.get("facman_source_revision")
    provider_revision = descriptor.get("universal_setup_revision")
    portable_name = current.get("portable_package")
    portable_sha256 = current.get("portable_sha256")
    if (
        not isinstance(version, str)
        or not re.fullmatch(SEMVER_PATTERN, version)
        or not isinstance(source_revision, str)
        or not HEX_REVISION.fullmatch(source_revision)
        or not isinstance(provider_revision, str)
        or not HEX_REVISION.fullmatch(provider_revision)
        or not isinstance(portable_name, str)
        or not portable_name
        or Path(portable_name).name != portable_name
        or not isinstance(portable_sha256, str)
        or not HEX_DIGEST.fullmatch(portable_sha256)
        or descriptor.get("generation_relative_path") != f"generations/{version}"
        or current.get("version") != version
        or current.get("generation") != f"generations/{version}"
        or current.get("facman_source_revision") != source_revision
        or current.get("universal_setup_revision") != provider_revision
    ):
        raise ValueError("produced setup has inconsistent self-maintenance identities")
    if portable is not None:
        portable = exact_regular(portable, "portable package")
        if portable.name != portable_name or sha256_file(portable) != portable_sha256:
            raise ValueError("setup identity does not bind the supplied portable package")
    return {
        "version": version,
        "source_revision": source_revision,
        "provider_revision": provider_revision,
        "portable_name": portable_name,
        "portable_sha256": portable_sha256,
    }


def identity_from_predecessor_outputs(
    predecessor: dict[str, object],
) -> dict[str, str]:
    """Bind produced package names to their hash-identical retained copies."""

    produced_setup = predecessor.get("setup")
    produced_portable = predecessor.get("portable")
    staged = predecessor.get("staged")
    if (
        not isinstance(produced_setup, Path)
        or not isinstance(produced_portable, Path)
        or not isinstance(staged, dict)
    ):
        raise ValueError("predecessor outputs have no exact produced and retained paths")
    for label, produced in (
        ("setup", produced_setup), ("portable", produced_portable),
    ):
        record = staged.get(label)
        if not isinstance(record, dict):
            raise ValueError(f"predecessor outputs have no retained {label} record")
        retained_value = record.get("path")
        recorded_bytes = record.get("bytes")
        recorded_sha256 = record.get("sha256")
        if (
            not isinstance(retained_value, str)
            or not isinstance(recorded_bytes, int)
            or isinstance(recorded_bytes, bool)
            or not isinstance(recorded_sha256, str)
            or not HEX_DIGEST.fullmatch(recorded_sha256)
        ):
            raise ValueError(f"predecessor retained {label} record is invalid")
        produced = exact_regular(produced, f"produced predecessor {label}")
        retained = exact_regular(Path(retained_value), f"retained predecessor {label}")
        produced_sha256 = sha256_file(produced)
        retained_sha256 = sha256_file(retained)
        if (
            produced.stat().st_size != recorded_bytes
            or retained.stat().st_size != recorded_bytes
            or produced_sha256 != recorded_sha256
            or retained_sha256 != recorded_sha256
        ):
            raise ValueError(f"produced and retained predecessor {label} differ")
    return identity_from_overlay(produced_setup, produced_portable)


def _semver_parts(value: str) -> tuple[tuple[int, int, int], tuple[tuple[int, object], ...] | None]:
    if not re.fullmatch(SEMVER_PATTERN, value):
        raise ValueError(f"invalid semantic version: {value!r}")
    without_build = value.split("+", 1)[0]
    core, separator, prerelease = without_build.partition("-")
    parsed = None if not separator else tuple(
        (0, int(part)) if part.isdecimal() else (1, part)
        for part in prerelease.split(".")
    )
    major, minor, patch = (int(part) for part in core.split("."))
    return (major, minor, patch), parsed


def semver_order(left: str, right: str) -> int:
    left_core, left_pre = _semver_parts(left)
    right_core, right_pre = _semver_parts(right)
    if left_core != right_core:
        return -1 if left_core < right_core else 1
    if left_pre is None or right_pre is None:
        if left_pre is right_pre:
            return 0
        return 1 if left_pre is None else -1
    for left_item, right_item in zip(left_pre, right_pre):
        if left_item == right_item:
            continue
        if left_item[0] != right_item[0]:
            return -1 if left_item[0] < right_item[0] else 1
        return -1 if left_item[1] < right_item[1] else 1
    if len(left_pre) == len(right_pre):
        return 0
    return -1 if len(left_pre) < len(right_pre) else 1


def provider_lock_bytes(root: Path) -> bytes:
    return (root / "release/index/providers.lock.v2.toml").read_bytes()


def locked_provider_revision(root: Path, provider_id: str) -> str:
    value = tomllib.loads(provider_lock_bytes(root).decode("utf-8"))
    matches = [
        item.get("source_revision") for item in value.get("provider", [])
        if isinstance(item, dict) and item.get("id") == provider_id
    ]
    if len(matches) != 1 or not isinstance(matches[0], str) or not HEX_REVISION.fullmatch(matches[0]):
        raise ValueError(f"provider lock has no exact {provider_id} revision")
    return matches[0]


def require_external_new(path: Path, label: str) -> Path:
    observed = path_cases.plain_path(path)
    if not observed.is_absolute() or observed.exists():
        raise ValueError(f"{label} must be an absent absolute non-link path")
    parent = exact_directory(observed.parent, f"{label} parent")
    candidate = parent / observed.name
    if candidate.is_relative_to(ROOT):
        raise ValueError(f"{label} must be outside the source checkout")
    return candidate


def copy_evidence(source: Path, destination: Path) -> dict[str, object]:
    source = exact_regular(source, "baseline evidence input")
    if destination.exists():
        raise ValueError(f"baseline evidence destination exists: {destination}")
    shutil.copyfile(source, destination)
    destination = exact_regular(destination, "staged baseline evidence")
    if sha256_file(source) != sha256_file(destination):
        raise ValueError("staged baseline evidence changed during copy")
    return {
        "path": str(destination),
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


def write_baseline_staging(
    evidence_root: Path, artifacts: dict[str, dict[str, object]],
    gates: dict[str, str],
) -> Path:
    path = evidence_root / "windows-self-maintenance-baseline-staging.v1.json"
    write_attempt(path, {
        "schema": "facman.self_maintenance_baseline_staging.v1",
        "status": "qualified" if gates.get("payload_equivalence") == "passed"
        else "produced_unqualified",
        "artifacts": artifacts,
        "gates": gates,
    })
    return path


def predecessor_roots(task_root: Path, baseline_revision: str) -> tuple[Path, Path]:
    """Return disjoint owned-output and external detached-checkout roots."""

    output_root = require_external_new(
        task_root / "self-maintenance-baseline-source", "baseline build root"
    )
    checkout_root = require_external_new(
        task_root.parent / ("." + task_root.name + ".predecessor." + baseline_revision[:12]),
        "baseline source checkout",
    )
    if checkout_root.is_relative_to(output_root) or output_root.is_relative_to(checkout_root):
        raise ValueError("baseline checkout and owned output roots must be disjoint")
    return checkout_root, output_root


def predecessor_environment(
    source: Path, output_root: Path, universal_launcher_root: Path,
    universal_setup_root: Path, source_revision: str,
) -> dict[str, str]:
    """Bind predecessor subprocesses to output owned by that checkout."""

    owned_output = development_layout.ensure_task_root(
        output_root, source, development_layout.current_task_id(source)
    )
    environment = dict(os.environ)
    environment["FACMAN_TASK_ROOT"] = str(owned_output)
    environment["FLAUNCH_UNIVERSAL_LAUNCHER_ROOT"] = str(universal_launcher_root)
    environment["FLAUNCH_UNIVERSAL_SETUP_ROOT"] = str(universal_setup_root)
    environment["PYTHONPATH"] = str(source)
    environment["FACMAN_CI_SOURCE_SHA"] = source_revision
    environment["FACMAN_WINFORMS_OUTPUT_ROOT"] = str(
        owned_output / "winforms-product" / "Release"
    )
    return environment


def predecessor_audit_environment(
    producer_environment: dict[str, str],
) -> dict[str, str]:
    """Use current qualification code without changing predecessor production."""

    environment = dict(producer_environment)
    environment["PYTHONPATH"] = str(ROOT)
    return environment


def build_predecessor_winforms(
    source: Path, output_root: Path, environment: dict[str, str],
    *, deadline: float,
) -> Path:
    """Build the predecessor GUI through that checkout's owned helper."""

    script = (
        "from pathlib import Path\n"
        "import subprocess\n"
        "import sys\n"
        "from tools import winforms_build\n"
        "def invoke(command):\n"
        "    subprocess.run(command, check=True)\n"
        "winforms_build.build(Path(sys.argv[1]), invoke)\n"
    )
    run(
        [sys.executable, "-c", script, str(output_root)],
        cwd=source, env=environment, deadline=deadline,
    )
    return exact_regular(
        output_root / "winforms-product/Release/FacMan.exe",
        "baseline WinForms product",
    )


def build_predecessor(
    args: argparse.Namespace, checkout_root: Path, output_root: Path, baseline_revision: str,
    *, deadline: float, evidence_root: Path,
) -> dict[str, object]:
    if checkout_root.is_relative_to(output_root) or output_root.is_relative_to(checkout_root):
        raise ValueError("baseline checkout and owned output roots must be disjoint")
    source = checkout_root
    build = output_root / "native-product"
    packages = output_root / "packages"
    dist = output_root / "dist"
    setup = output_root / "setup"
    clone_clean_detached(ROOT, source, baseline_revision, deadline=deadline)
    if provider_lock_bytes(source) != provider_lock_bytes(ROOT):
        raise ValueError("baseline provider lock differs from the candidate provider lock")
    if not (source / "runtime/self_setup/facman_self_maintenance_package.cpp").is_file():
        raise ValueError("baseline source cannot produce a self-maintenance package")
    environment = predecessor_environment(
        source, output_root, args.universal_launcher_root, args.universal_setup_root,
        baseline_revision,
    )
    checkout_observation_root = output_root / "source-observation"
    checkout_observation = checkout_observation_root / "current-checkout-observation.v2.json"
    source_observation = output_root / "release-source-observation.v1.json"
    staged: dict[str, dict[str, object]] = {}
    gates = {"payload_equivalence": "not_started"}
    candidate_origin = capture(
        git_command("remote", "get-url", "origin"), cwd=ROOT, deadline=deadline,
    )
    if not candidate_origin:
        raise ValueError("candidate source has no origin remote for baseline custody")
    run(
        git_command("remote", "set-url", "origin", candidate_origin),
        cwd=source,
        deadline=deadline,
    )
    run([
        sys.executable, str(source / "tools/current_checkout_observation.py"),
        "--provider-root", "universal_launcher=" + str(args.universal_launcher_root),
        "--provider-root", "universal_setup=" + str(args.universal_setup_root),
        "--expected-source-sha", baseline_revision,
        "--line-ending-profile", "windows_checkout",
        "--output-dir", str(checkout_observation_root),
    ], cwd=source, env=environment, deadline=deadline)
    staged["checkout_observation"] = copy_evidence(
        checkout_observation,
        evidence_root / "windows-self-maintenance-baseline-checkout-observation.v2.json",
    )
    write_baseline_staging(evidence_root, staged, gates)
    run([
        sys.executable, str(source / "tools/facman_release.py"), "source-observation",
        "--checkout-observation", str(checkout_observation),
        "--output", str(source_observation),
    ], cwd=source, env=environment, deadline=deadline)
    staged["source_observation"] = copy_evidence(
        source_observation,
        evidence_root / "windows-self-maintenance-baseline-source-observation.v1.json",
    )
    write_baseline_staging(evidence_root, staged, gates)
    run([
        "cmake", "-S", str(source), "-B", str(build), "-A", "x64",
        "-DFACMAN_BUILD_CLI=ON", "-DFACMAN_BUILD_TUI=ON",
        "-DFACMAN_BUILD_TESTS=ON", "-DFACMAN_BUILD_SELF_SETUP=ON",
        "-DFACMAN_PROVIDER_MODE=source", "-DFACMAN_PROVIDER_SOURCE_LINKAGE=shared",
        "-DFACMAN_WARNINGS_AS_ERRORS=ON",
    ], cwd=source, env=environment, deadline=deadline)
    run(["cmake", "--build", str(build), "--config", "Release", "--parallel"],
        cwd=source, env=environment, deadline=deadline)
    build_predecessor_winforms(
        source, output_root, environment, deadline=deadline,
    )
    run([
        sys.executable, str(source / "tools/package_build.py"),
        "--profile", "windows_product_x64", "--out", str(packages),
        "--build-root", str(build), "--dist", str(dist),
        "--source-observation", str(source_observation),
    ], cwd=source, env=environment, deadline=deadline)
    baseline_version = version_at(source)
    portable = dist / f"FacMan-{baseline_version}-windows-x64-portable.zip"
    staged["portable"] = copy_evidence(
        portable, evidence_root / "windows-self-maintenance-baseline-portable.zip"
    )
    gates["payload_equivalence"] = "pending_setup"
    write_baseline_staging(evidence_root, staged, gates)
    bootstrap = build / "Release/FacManSetup.exe"
    run([
        sys.executable, str(source / "tools/self_contained_setup.py"),
        "--portable", str(portable), "--bootstrap", str(bootstrap), "--out", str(setup),
    ], cwd=source, env=environment, deadline=deadline)
    result = setup / f"FacMan-{baseline_version}-windows-x64-setup.exe"
    exact_regular(result, "baseline setup package")
    staged["setup"] = copy_evidence(
        result, evidence_root / "windows-self-maintenance-baseline-setup.exe"
    )
    gates["payload_equivalence"] = "pending"
    write_baseline_staging(evidence_root, staged, gates)
    equivalence = output_root / "evidence/windows-payload-equivalence.v1.json"
    auditor_environment = predecessor_audit_environment(environment)
    try:
        run([
            sys.executable, str(ROOT / "tools/package_contract_tck.py"),
            "--profile", "windows_product_x64", "--canonical-stage",
            str(packages / "windows_product_x64"), "--payload-zip", str(result),
            "--canonical-artifact", str(portable), "--payload-artifact", str(result),
            "--adapter", "windows_setup_overlay_v1", "--version", baseline_version,
            "--receipt", str(equivalence),
        ], cwd=ROOT, env=auditor_environment, deadline=deadline)
    except BaseException:
        gates["payload_equivalence"] = "failed"
        write_baseline_staging(evidence_root, staged, gates)
        raise
    staged["payload_equivalence"] = copy_evidence(
            equivalence,
            evidence_root / "windows-self-maintenance-baseline-payload-equivalence.v1.json",
    )
    gates["payload_equivalence"] = "passed"
    write_baseline_staging(evidence_root, staged, gates)
    return {
        "setup": result,
        "portable": portable,
        "staged": staged,
        "origin_sha256": hashlib.sha256(candidate_origin.encode("utf-8")).hexdigest(),
    }


def write_attempt(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def safe_failure_detail(exc: BaseException) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        return f"subprocess exited with status {exc.returncode}"
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"subprocess exceeded {exc.timeout} seconds"
    return str(exc)


def execute(args: argparse.Namespace) -> int:
    if os.name != "nt":
        raise ValueError("self-maintenance candidate transition is Windows-only")
    started = time.monotonic()
    outer_deadline = started + args.outer_timeout
    task_input = path_cases.plain_path(args.task_root)
    task_root = exact_directory(task_input, "task root").resolve(strict=True)
    path_cases.plain_path(task_root)
    if task_input != task_root or task_root.is_relative_to(ROOT):
        raise ValueError("task root must be a canonical external non-link path")
    marker = read_task_marker(task_root)
    (task_root / "evidence").mkdir(exist_ok=True)
    evidence_root = exact_directory(task_root / "evidence", "task evidence root")
    attempt_path = evidence_root / "windows-self-maintenance-transition-attempt.v1.json"
    if attempt_path.exists():
        raise ValueError("transition attempt receipt already exists")
    attempt: dict[str, object] = {
        "schema": "facman.self_maintenance_transition_attempt.v1",
        "status": "running",
        "phase": "input-admission",
        "task_root": str(task_root),
        "task_marker": marker,
        "baseline_input_revision": args.baseline_ref,
        "candidate_input_revision": args.candidate_revision,
        "limits": {
            "outer_seconds": args.outer_timeout,
            "child_seconds": args.command_timeout,
            "transition_seconds": args.transition_timeout,
        },
    }
    write_attempt(attempt_path, attempt)
    try:
        if not HEX_REVISION.fullmatch(args.baseline_ref):
            raise ValueError("baseline revision must be exact lowercase 40-hex")
        if not HEX_REVISION.fullmatch(args.candidate_revision):
            raise ValueError("candidate revision must be exact lowercase 40-hex")
        args.candidate_setup = exact_regular(args.candidate_setup, "candidate setup")
        args.candidate_portable = exact_regular(args.candidate_portable, "candidate portable")
        args.universal_launcher_root = exact_directory(
            args.universal_launcher_root, "Universal Launcher root"
        )
        args.universal_setup_root = exact_directory(
            args.universal_setup_root, "Universal Setup root"
        )
        candidate_revision = head_revision(cwd=ROOT, deadline=outer_deadline)
        if candidate_revision != args.candidate_revision:
            raise ValueError("candidate revision does not match the clean checked-out source")
        if capture(
            git_command("status", "--porcelain=v1", "--untracked-files=all"),
            cwd=ROOT, deadline=outer_deadline,
        ):
            raise ValueError("candidate source must be clean before package transition qualification")
        baseline_revision = revision(args.baseline_ref, cwd=ROOT, deadline=outer_deadline)
        if baseline_revision == candidate_revision:
            raise ValueError("baseline and candidate source revisions must differ")
        if subprocess.run(
            git_command(
                "merge-base", "--is-ancestor", baseline_revision, candidate_revision,
            ),
            cwd=ROOT, check=False, timeout=remaining(outer_deadline, "ancestor check"),
        ).returncode:
            raise ValueError("baseline source must be an ancestor of the candidate source")
        attempt["phase"] = "baseline-build"
        write_attempt(attempt_path, attempt)
        checkout_root, baseline_root = predecessor_roots(task_root, baseline_revision)
        fixture_root = require_external_new(
            evidence_root / "real self-maintenance transition", "transition fixture root"
        )
        evidence = fixture_root / "windows-real-self-maintenance-transition.v1.json"
        baseline = build_predecessor(
            args, checkout_root, baseline_root, baseline_revision,
            deadline=outer_deadline, evidence_root=evidence_root,
        )
        staged = baseline["staged"]
        if not isinstance(staged, dict):
            raise ValueError("baseline evidence staging did not return an exact manifest")
        baseline_setup = Path(str(staged["setup"]["path"]))
        baseline_identity = identity_from_predecessor_outputs(baseline)
        candidate_identity = identity_from_overlay(args.candidate_setup, args.candidate_portable)
        locked_setup = locked_provider_revision(ROOT, "universal_setup")
        if (
            baseline_identity["source_revision"] != baseline_revision
            or candidate_identity["source_revision"] != candidate_revision
            or baseline_identity["provider_revision"] != locked_setup
            or candidate_identity["provider_revision"] != locked_setup
            or semver_order(baseline_identity["version"], candidate_identity["version"]) >= 0
        ):
            raise ValueError("produced package identities are not source-distinct strict maintenance inputs")
        attempt["phase"] = "real-transition"
        attempt["baseline"] = {
            "revision": baseline_revision,
            "setup_sha256": sha256_file(baseline_setup),
            "identity": baseline_identity,
            "staged": baseline["staged"],
            "origin_sha256": baseline["origin_sha256"],
        }
        attempt["candidate"] = {
            "revision": candidate_revision,
            "setup": str(args.candidate_setup),
            "setup_sha256": sha256_file(args.candidate_setup),
            "portable": str(args.candidate_portable),
            "portable_sha256": sha256_file(args.candidate_portable),
            "identity": candidate_identity,
        }
        write_attempt(attempt_path, attempt)
        transition_budget = min(
            args.transition_timeout,
            remaining(outer_deadline, "real transition admission"),
        )
        run([
            sys.executable, str(ROOT / "tests/integration/facman_self_setup_lifecycle.py"),
            "--real-self-maintenance-transition", "--setup-exe", str(args.candidate_setup),
            "--payload", str(args.candidate_setup),
            "--baseline-setup-exe", str(baseline_setup),
            "--baseline-payload", str(baseline_setup),
            "--fixture-root", str(fixture_root), "--evidence", str(evidence),
            "--real-command-timeout", str(args.command_timeout),
            "--real-total-timeout", str(transition_budget),
        ], cwd=ROOT, deadline=outer_deadline)
        exact_regular(evidence, "transition evidence")
        transition = json.loads(evidence.read_text(encoding="utf-8"))
        if not isinstance(transition, dict) or transition.get("outcome") != "passed":
            raise ValueError("transition harness did not retain passing exact evidence")
        attempt["transition_evidence"] = {
            "path": str(evidence), "sha256": sha256_file(evidence),
        }
        attempt["status"] = "passed"
        attempt["phase"] = "completed"
        attempt["scope"] = (
            "disposable Windows current-user package transition; "
            "no chain-aware uninstall claim"
        )
        return 0
    except BaseException as exc:
        attempt["status"] = "failed"
        attempt["failure"] = {
            "type": type(exc).__name__, "detail": safe_failure_detail(exc),
        }
        retained_evidence = locals().get("evidence")
        if isinstance(retained_evidence, Path):
            try:
                retained_evidence = exact_regular(
                    retained_evidence, "failed transition evidence"
                )
                attempt["transition_evidence"] = {
                    "path": str(retained_evidence),
                    "sha256": sha256_file(retained_evidence),
                }
            except (OSError, ValueError):
                pass
        raise
    finally:
        attempt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_attempt(attempt_path, attempt)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv == ["--workflow-environment"]:
        required = {
            name: os.environ.get(name, "") for name in (
                "FACMAN_SELF_MAINTENANCE_BASELINE_REF", "GITHUB_SHA",
                "FACMAN_TASK_ROOT", "FACMAN_CANDIDATE_VERSION",
                "FLAUNCH_UNIVERSAL_LAUNCHER_ROOT", "FLAUNCH_UNIVERSAL_SETUP_ROOT",
            )
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            print(
                "self-maintenance candidate transition failed: missing workflow environment: "
                + ", ".join(missing), file=sys.stderr,
            )
            return 2
        task_root = Path(required["FACMAN_TASK_ROOT"])
        version = required["FACMAN_CANDIDATE_VERSION"]
        argv = [
            "--baseline-ref", required["FACMAN_SELF_MAINTENANCE_BASELINE_REF"],
            "--candidate-revision", required["GITHUB_SHA"],
            "--task-root", str(task_root),
            "--candidate-setup", str(task_root / "setup" /
                f"FacMan-{version}-windows-x64-setup.exe"),
            "--candidate-portable", str(task_root / "dist" /
                f"FacMan-{version}-windows-x64-portable.zip"),
            "--universal-launcher-root", required["FLAUNCH_UNIVERSAL_LAUNCHER_ROOT"],
            "--universal-setup-root", required["FLAUNCH_UNIVERSAL_SETUP_ROOT"],
            "--command-timeout", "300", "--transition-timeout", "1800",
            "--outer-timeout", "6600",
        ]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--candidate-revision", required=True)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--candidate-setup", type=Path, required=True)
    parser.add_argument("--candidate-portable", type=Path, required=True)
    parser.add_argument("--universal-launcher-root", type=Path, required=True)
    parser.add_argument("--universal-setup-root", type=Path, required=True)
    parser.add_argument("--command-timeout", type=float, required=True)
    parser.add_argument("--transition-timeout", type=float, required=True)
    parser.add_argument("--outer-timeout", type=float, required=True)
    args = parser.parse_args(argv)
    if args.command_timeout <= 0 or args.command_timeout > 600:
        parser.error("--command-timeout must be within (0, 600]")
    if args.transition_timeout <= 0 or args.transition_timeout > 3600:
        parser.error("--transition-timeout must be within (0, 3600]")
    if args.outer_timeout <= args.transition_timeout or args.outer_timeout > 6600:
        parser.error("--outer-timeout must be greater than transition timeout and at most 6600")
    try:
        return execute(args)
    except (
        OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
        TimeoutError, ValueError, zipfile.BadZipFile,
    ) as exc:
        print(
            "self-maintenance candidate transition failed: "
            + safe_failure_detail(exc), file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
