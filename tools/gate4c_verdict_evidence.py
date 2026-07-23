# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Stable Gate 4C baseline and comparison evidence.

This evidence-only tool prepares one exact operator session from a fresh ready
preflight and compares the same protected and writable resources after the
reviewed native candidate returns.  It cannot issue a permit, start Factorio,
or self-attest a human result.  Its finalizer can derive an evidence-only
verdict only from two explicit, independently bound human observations.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SESSION_SCHEMA = "factorio.gate4c_verdict_session.v1"
BASELINE_SCHEMA = "factorio.gate4c_baseline_bundle.v1"
COMPARISON_SCHEMA = "factorio.gate4c_baseline_comparison.v1"
HUMAN_OBSERVATION_SCHEMA = "factorio.gate4c_human_observation.v1"
VERDICT_SCHEMA = "factorio.gate4c_human_verdict.v1"
CLASSIFICATION_SCHEMA = "factorio.gate4c_effect_classification.v1"
WORK_UNIT = "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01"
POLICY_DIGEST = "6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2"
WINDOWS_REPARSE_ATTRIBUTE = 0x400
MAXIMUM_MANIFEST_ENTRIES = 250_000
MAXIMUM_MANIFEST_BYTES = 16 * 1024 * 1024 * 1024

WRITABLE_PATHS = {
    "instance.config": "{instance}/config",
    "instance.locks": "{instance}/locks",
    "instance.logs": "{instance}/logs",
    "instance.mods": "{instance}/mods",
    "instance.saves": "{instance}/saves",
    "instance.state": "{instance}/state",
    "operation.record": "{workspace}/operations/{operation}",
    "operation.temporary": "{workspace}/temporary/{operation}",
}

PROTECTED_IDS = {
    "effects.external_filesystem",
    "effects.external_registry",
    "facman.package",
    "factorio.appdata",
    "factorio.default_user_data",
    "factorio.localappdata",
    "factorio.programdata",
    "factorio.source_material",
    "host.external_unobserved",
    "installation.selected",
    "installation.siblings",
    "instances.other",
    "registry.factorio",
    "registry.factorio_uninstall",
    "registry.steam",
    "steam.cloud_cache",
    "steam.install_roots",
    "steam.userdata",
}

FIRST_LAUNCH_CHECKS = {
    "normal_menu_observed",
    "no_save_inferred",
    "disposable_game_created",
    "save_completed",
    "returned_to_menu",
    "exited_normally",
    "last_run_accurate",
}
SECOND_LAUNCH_CHECKS = {
    "normal_menu_observed",
    "no_save_inferred",
    "saved_game_visible",
    "returned_to_menu",
    "exited_normally",
    "last_run_accurate",
}


class EvidenceError(RuntimeError):
    pass


def _load_preflight() -> Any:
    location = ROOT / "tools" / "gate4c_verdict_preflight.py"
    spec = importlib.util.spec_from_file_location("gate4c_verdict_preflight", location)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREFLIGHT = _load_preflight()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EvidenceError("timestamp is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EvidenceError("timestamp is malformed") from exc
    return parsed.astimezone(timezone.utc)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def lowercase_digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    os.replace(temporary, path)


def prepare_new_output(
    path: Path,
    *,
    root: Path,
    expected_parent: Path,
) -> Path:
    absolute = Path(os.path.abspath(path))
    boundary = Path(os.path.abspath(root))
    parent = Path(os.path.abspath(expected_parent))
    if (
        not PREFLIGHT.path_is_within(absolute, boundary)
        or normalized_path(absolute.parent) != normalized_path(parent)
        or absolute.exists()
    ):
        raise EvidenceError("evidence output is not one new exact task-owned file")
    root_audit = PREFLIGHT.audit_no_follow(boundary, require_file=False)
    if not root_audit["safe"]:
        raise EvidenceError("evidence output root is unsafe")
    relative_parent = parent.relative_to(boundary)
    current = boundary
    for component in relative_parent.parts:
        current = current / component
        if not current.exists():
            current.mkdir()
        current_audit = PREFLIGHT.audit_no_follow(current, require_file=False)
        if not current_audit["safe"]:
            raise EvidenceError("evidence output parent crosses a reparse boundary")
    return absolute


def read_strict_json(path: Path) -> dict[str, Any]:
    audit = PREFLIGHT.audit_no_follow(path, require_file=True)
    if not audit["safe"]:
        raise EvidenceError(f"unsafe evidence input: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidenceError(f"evidence input is not an object: {path}")
    return value


def normalized_path(value: Path | str) -> str:
    return str(PureWindowsPath(os.path.abspath(value))).casefold()


def reparse(metadata: os.stat_result) -> bool:
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & WINDOWS_REPARSE_ATTRIBUTE)


def identity(metadata: os.stat_result) -> dict[str, Any]:
    return {
        "device": int(metadata.st_dev),
        "object": int(metadata.st_ino),
        "size": int(metadata.st_size),
        "last_write_ns": int(metadata.st_mtime_ns),
        "mode": int(metadata.st_mode),
        "reparse": reparse(metadata),
    }


def hash_file_stable(path: Path, maximum_bytes: int) -> tuple[str, int, dict[str, Any]]:
    before = path.lstat()
    if reparse(before) or not stat.S_ISREG(before.st_mode):
        raise EvidenceError(f"file is not a regular no-follow object: {path}")
    if before.st_size > maximum_bytes:
        raise EvidenceError(f"file exceeds the manifest byte budget: {path}")
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                digest.update(block)
    finally:
        os.close(descriptor)
    after = path.lstat()
    if identity(before) != identity(after):
        raise EvidenceError(f"file changed during stable hashing: {path}")
    return digest.hexdigest(), int(before.st_size), identity(before)


def capture_path(path: Path) -> dict[str, Any]:
    absolute = Path(os.path.abspath(path))
    if not absolute.exists():
        core = {
            "path": str(absolute),
            "present": False,
            "complete": True,
            "root_identity": digest_value({"path": normalized_path(absolute), "absent": True}),
            "entries": [],
            "bytes_hashed": 0,
            "gaps": [],
        }
        core["manifest_digest"] = digest_value(core)
        return core
    root_metadata = absolute.lstat()
    if reparse(root_metadata):
        core = {
            "path": str(absolute),
            "present": True,
            "complete": False,
            "root_identity": digest_value(identity(root_metadata)),
            "entries": [],
            "bytes_hashed": 0,
            "gaps": ["root_link_or_reparse_refused"],
        }
        core["manifest_digest"] = digest_value(core)
        return core
    root_before = identity(root_metadata)
    entries: list[dict[str, Any]] = []
    gaps: list[str] = []
    bytes_hashed = 0
    if stat.S_ISREG(root_metadata.st_mode):
        try:
            content, size, observed = hash_file_stable(
                absolute, MAXIMUM_MANIFEST_BYTES
            )
            entries.append(
                {
                    "relative_path": ".",
                    "kind": "file",
                    "identity": digest_value(observed),
                    "content_sha256": content,
                    "size": size,
                }
            )
            bytes_hashed = size
        except (OSError, EvidenceError) as exc:
            gaps.append(f"stable_file_failed:{exc}")
    elif stat.S_ISDIR(root_metadata.st_mode):
        pending = [absolute]
        while pending and not gaps:
            directory = pending.pop()
            try:
                directory_before = identity(directory.lstat())
                if directory_before["reparse"]:
                    gaps.append(f"directory_link_or_reparse:{directory}")
                    break
                children = sorted(
                    list(os.scandir(directory)),
                    key=lambda item: item.name.casefold(),
                )
            except OSError as exc:
                gaps.append(f"directory_read_failed:{directory}:{exc}")
                break
            for child in children:
                if len(entries) >= MAXIMUM_MANIFEST_ENTRIES:
                    gaps.append("entry_limit_exceeded")
                    break
                child_path = Path(child.path)
                try:
                    metadata = child_path.lstat()
                except OSError as exc:
                    gaps.append(f"entry_lstat_failed:{child_path}:{exc}")
                    break
                if reparse(metadata):
                    gaps.append(f"entry_link_or_reparse:{child_path}")
                    break
                relative = child_path.relative_to(absolute).as_posix()
                observed = identity(metadata)
                if stat.S_ISDIR(metadata.st_mode):
                    entries.append(
                        {
                            "relative_path": relative,
                            "kind": "directory",
                            "identity": digest_value(observed),
                            "content_sha256": "",
                            "size": int(metadata.st_size),
                        }
                    )
                    pending.append(child_path)
                elif stat.S_ISREG(metadata.st_mode):
                    try:
                        content, size, stable = hash_file_stable(
                            child_path, MAXIMUM_MANIFEST_BYTES - bytes_hashed
                        )
                    except (OSError, EvidenceError) as exc:
                        gaps.append(f"stable_file_failed:{child_path}:{exc}")
                        break
                    bytes_hashed += size
                    entries.append(
                        {
                            "relative_path": relative,
                            "kind": "file",
                            "identity": digest_value(stable),
                            "content_sha256": content,
                            "size": size,
                        }
                    )
                else:
                    gaps.append(f"unsupported_object:{child_path}")
                    break
            try:
                if directory_before != identity(directory.lstat()):
                    gaps.append(f"directory_changed_during_capture:{directory}")
            except OSError as exc:
                gaps.append(f"directory_revalidation_failed:{directory}:{exc}")
        entries.sort(key=lambda item: (item["relative_path"].casefold(), item["kind"]))
    else:
        gaps.append("root_unsupported_object")
    try:
        root_after = identity(absolute.lstat())
        if root_before != root_after:
            gaps.append("root_changed_during_capture")
    except OSError as exc:
        gaps.append(f"root_revalidation_failed:{exc}")
    core = {
        "path": str(absolute),
        "present": True,
        "complete": not gaps,
        "root_identity": digest_value(root_before),
        "entries": entries,
        "bytes_hashed": bytes_hashed,
        "gaps": sorted(set(gaps)),
    }
    core["manifest_digest"] = digest_value(core)
    return core


def capture_filesystem_resource(resource_id: str, members: Iterable[Path]) -> dict[str, Any]:
    unique = {
        normalized_path(path): Path(os.path.abspath(path))
        for path in members
    }
    manifests = [
        capture_path(unique[key])
        for key in sorted(unique)
    ]
    core = {
        "resource_id": resource_id,
        "kind": "filesystem",
        "complete": all(item["complete"] for item in manifests),
        "members": manifests,
    }
    core["resource_digest"] = digest_value(core)
    return core


def registry_value(value: Any, kind: int) -> dict[str, Any]:
    if isinstance(value, bytes):
        encoded: Any = base64.b64encode(value).decode("ascii")
        encoding = "base64"
    elif isinstance(value, list):
        encoded = [str(item) for item in value]
        encoding = "strings"
    else:
        encoded = value
        encoding = "native"
    return {"type": kind, "encoding": encoding, "value": encoded}


def capture_registry_tree(hive_name: str, subkey: str) -> dict[str, Any]:
    if os.name != "nt":
        return {
            "hive": hive_name,
            "subkey": subkey,
            "present": False,
            "complete": False,
            "entries": [],
            "gaps": ["windows_registry_unavailable"],
        }
    import winreg

    hives = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
    }
    no_more_items = 259

    def enumerate_once() -> tuple[bool, list[dict[str, Any]], list[str]]:
        entries: list[dict[str, Any]] = []
        gaps: list[str] = []
        present = True

        def visit(relative: str) -> None:
            nonlocal present
            if len(entries) >= MAXIMUM_MANIFEST_ENTRIES:
                gaps.append("registry_entry_limit_exceeded")
                return
            try:
                with winreg.OpenKey(
                    hives[hive_name],
                    relative,
                    0,
                    winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
                ) as key:
                    entries.append(
                        {
                            "key": relative.casefold(),
                            "name": "",
                            "kind": "key",
                            "value": None,
                        }
                    )
                    value_index = 0
                    while len(entries) < MAXIMUM_MANIFEST_ENTRIES:
                        try:
                            name, value, kind = winreg.EnumValue(key, value_index)
                        except OSError as exc:
                            if exc.winerror != no_more_items:
                                gaps.append(
                                    "registry_value_enumeration_failed:"
                                    f"{hive_name}\\{relative}:{exc.winerror}"
                                )
                            break
                        entries.append(
                            {
                                "key": relative.casefold(),
                                "name": name.casefold(),
                                "kind": "value",
                                "value": registry_value(value, kind),
                            }
                        )
                        value_index += 1
                    children: list[str] = []
                    child_index = 0
                    while len(entries) + len(children) < MAXIMUM_MANIFEST_ENTRIES:
                        try:
                            children.append(winreg.EnumKey(key, child_index))
                        except OSError as exc:
                            if exc.winerror != no_more_items:
                                gaps.append(
                                    "registry_key_enumeration_failed:"
                                    f"{hive_name}\\{relative}:{exc.winerror}"
                                )
                            break
                        child_index += 1
                    if (
                        len(entries) >= MAXIMUM_MANIFEST_ENTRIES
                        or len(entries) + len(children) >= MAXIMUM_MANIFEST_ENTRIES
                    ):
                        gaps.append("registry_entry_limit_exceeded")
            except FileNotFoundError:
                if relative == subkey:
                    present = False
                else:
                    gaps.append(
                        f"registry_key_disappeared:{hive_name}\\{relative}"
                    )
                return
            except OSError as exc:
                gaps.append(
                    f"registry_read_failed:{hive_name}\\{relative}:{exc.winerror}"
                )
                return
            for child in sorted(children, key=str.casefold):
                visit(relative + "\\" + child)

        visit(subkey)
        entries.sort(key=lambda item: (item["key"], item["kind"], item["name"]))
        return present, entries, gaps

    present, entries, gaps = enumerate_once()
    revalidated_present, revalidated_entries, revalidation_gaps = enumerate_once()
    gaps.extend(revalidation_gaps)
    if present != revalidated_present or entries != revalidated_entries:
        gaps.append("registry_changed_during_capture")
    return {
        "hive": hive_name,
        "subkey": subkey,
        "present": present,
        "complete": not gaps,
        "entries": entries,
        "gaps": sorted(set(gaps)),
    }


def capture_registry_resource(
    resource_id: str,
    keys: Iterable[tuple[str, str]],
) -> dict[str, Any]:
    members = [
        capture_registry_tree(hive, subkey)
        for hive, subkey in sorted(set(keys))
    ]
    core = {
        "resource_id": resource_id,
        "kind": "registry",
        "complete": all(item["complete"] for item in members),
        "members": members,
    }
    core["resource_digest"] = digest_value(core)
    return core


def existing_steam_roots() -> list[Path]:
    candidates: set[Path] = set()
    program_files = os.environ.get("ProgramFiles(x86)")
    if program_files:
        candidates.add(Path(program_files) / "Steam")
    if os.name == "nt":
        import winreg

        for hive, subkey, name in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
                    candidates.add(Path(winreg.QueryValueEx(key, name)[0]))
            except OSError:
                pass
    return sorted(
        {Path(os.path.abspath(path)) for path in candidates if path.exists()},
        key=lambda path: normalized_path(path),
    )


def steam_libraries(steam_roots: Iterable[Path]) -> list[Path]:
    libraries = set(steam_roots)
    pattern = re.compile(r'"path"\s+"([^"]+)"', re.IGNORECASE)
    for root in steam_roots:
        value = root / "steamapps" / "libraryfolders.vdf"
        if not value.is_file():
            continue
        try:
            text = value.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in pattern.finditer(text):
            libraries.add(Path(match.group(1).replace("\\\\", "\\")))
    return sorted(
        {Path(os.path.abspath(path)) for path in libraries},
        key=lambda path: normalized_path(path),
    )


def installation_siblings(workspace: Path, selected: Path) -> list[Path]:
    output: list[Path] = []
    for record in sorted((workspace / "installs" / "refs").glob("*.json")):
        try:
            value = read_strict_json(record)
            root = Path(value.get("root", ""))
        except (OSError, ValueError, json.JSONDecodeError, EvidenceError):
            continue
        if root and normalized_path(root) != normalized_path(selected):
            output.append(root)
    return output


def other_instances(workspace: Path, selected_id: str) -> list[Path]:
    root = workspace / "instances"
    if not root.is_dir():
        return []
    return [
        path
        for path in root.iterdir()
        if path.is_dir() and path.name != selected_id
    ]


def protected_specs(preflight: dict[str, Any], workspace: Path) -> dict[str, Any]:
    description = preflight["instance"]["description"]
    binding = description["instance_binding"]
    instance_id = description["instance_id"]
    instance_root = Path(binding["write_data_path"])
    installation_root = Path(binding["read_data_path"]).parent
    source = Path(preflight["source_evidence"]["path_audit"]["path"])
    source_copy = Path(
        preflight["source_evidence"]["source_member"]["inspection_copy"]["path_audit"]["path"]
    )
    facman_package = Path(preflight["facman_artifact"]["path"]).parent
    appdata = Path(os.environ.get("APPDATA", "")) / "Factorio"
    localappdata = Path(os.environ.get("LOCALAPPDATA", "")) / "Factorio"
    programdata = Path(os.environ.get("PROGRAMDATA", "")) / "Factorio"
    steam_roots = existing_steam_roots()
    libraries = steam_libraries(steam_roots)
    steam_factorio = [path / "steamapps" / "common" / "Factorio" for path in libraries]
    steam_userdata = [path / "userdata" for path in steam_roots]
    steam_cache = [path / "appcache" for path in steam_roots]
    filesystem = {
        "installation.selected": [installation_root],
        "installation.siblings": installation_siblings(workspace, installation_root),
        "factorio.default_user_data": [appdata],
        "factorio.appdata": [appdata],
        "factorio.localappdata": [localappdata],
        "factorio.programdata": [programdata],
        "steam.install_roots": steam_factorio,
        "steam.userdata": steam_userdata,
        "steam.cloud_cache": steam_cache,
        "facman.package": [facman_package],
        "instances.other": other_instances(workspace, instance_id),
        "factorio.source_material": [source, source_copy],
    }
    registry = {
        "registry.factorio": [
            ("HKCU", r"Software\Wube Software"),
            ("HKLM", r"SOFTWARE\Wube Software"),
            ("HKLM", r"SOFTWARE\WOW6432Node\Wube Software"),
        ],
        "registry.factorio_uninstall": [
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ],
        "registry.steam": [
            ("HKCU", r"Software\Valve\Steam"),
            ("HKLM", r"SOFTWARE\Valve\Steam"),
            ("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam"),
        ],
    }
    conceptual = {
        "effects.external_filesystem": "event-only:filesystem",
        "effects.external_registry": "event-only:registry",
        "host.external_unobserved": "disclosed:outside-process-tree-claim",
    }
    return {
        "filesystem": {
            key: [str(Path(os.path.abspath(path))) for path in values]
            for key, values in filesystem.items()
        },
        "registry": {
            key: [{"hive": hive, "subkey": subkey} for hive, subkey in values]
            for key, values in registry.items()
        },
        "conceptual": conceptual,
    }


def writable_specs(
    workspace: Path,
    instance_root: Path,
    operation_id: str,
) -> dict[str, list[str]]:
    return {
        resource_id: [
            selector.format(
                workspace=str(workspace),
                instance=str(instance_root),
                operation=operation_id,
            ).replace("/", os.sep)
        ]
        for resource_id, selector in WRITABLE_PATHS.items()
    }


def capture_resources(specs: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for resource_id, paths in sorted(specs["filesystem"].items()):
        resources.append(
            capture_filesystem_resource(resource_id, [Path(path) for path in paths])
        )
    for resource_id, keys in sorted(specs["registry"].items()):
        resources.append(
            capture_registry_resource(
                resource_id,
                [(item["hive"], item["subkey"]) for item in keys],
            )
        )
    for resource_id, disclosure in sorted(specs["conceptual"].items()):
        core = {
            "resource_id": resource_id,
            "kind": "conceptual",
            "complete": True,
            "disclosure": disclosure,
        }
        core["resource_digest"] = digest_value(core)
        resources.append(core)
    resources.sort(key=lambda item: item["resource_id"])
    return resources


def capture_writable(specs: dict[str, list[str]]) -> list[dict[str, Any]]:
    return [
        capture_filesystem_resource(resource_id, [Path(path) for path in paths])
        for resource_id, paths in sorted(specs.items())
    ]


def resource_set_digest(resources: list[dict[str, Any]]) -> str:
    return digest_value(
        [
            {
                "resource_id": item["resource_id"],
                "resource_digest": item["resource_digest"],
                "complete": item["complete"],
            }
            for item in sorted(resources, key=lambda value: value["resource_id"])
        ]
    )


def validate_ready_preflight(path: Path) -> dict[str, Any]:
    value = read_strict_json(path)
    claimed = value.get("preflight_digest")
    core = dict(value)
    core.pop("preflight_digest", None)
    if (
        value.get("schema") != "factorio.hermetic_play_verdict_preflight.v1"
        or value.get("work_unit") != WORK_UNIT
        or value.get("status") != "ready"
        or value.get("blockers") != []
        or value.get("policy", {}).get("computed_digest") != POLICY_DIGEST
        or value.get("authority") != {
            "permit_issued": False,
            "process_started": False,
            "public_route_available": False,
            "real_factorio_execution": False,
            "verdict": "unset",
        }
        or not lowercase_digest(claimed)
        or digest_value(core) != claimed
    ):
        raise EvidenceError("ready preflight identity or authority boundary is invalid")
    deadline = parse_utc(value["readiness_lease"]["baseline_must_begin_before"])
    if datetime.now(timezone.utc) >= deadline:
        raise EvidenceError("ready preflight lease expired before baseline capture")
    if not value["host"]["process_inventory"].get("quiet"):
        raise EvidenceError("ready preflight host inventory is not quiet")
    return value


def validate_session_record(path: Path) -> dict[str, Any]:
    value = read_strict_json(path)
    claimed = value.get("session_digest")
    core = dict(value)
    core.pop("session_digest", None)
    if (
        value.get("schema") != SESSION_SCHEMA
        or value.get("work_unit") != WORK_UNIT
        or not lowercase_digest(claimed)
        or digest_value(core) != claimed
    ):
        raise EvidenceError("verdict session identity is invalid")
    return value


def validate_human_observation(
    path: Path,
    *,
    operation_id: str,
    session_digest: str,
    packet_digest: str,
    expected_checks: set[str],
) -> dict[str, Any]:
    value = read_strict_json(path)
    claimed = value.get("attestation_digest")
    core = dict(value)
    core.pop("attestation_digest", None)
    exact_keys = {
        "schema",
        "canonicalization_version",
        "work_unit",
        "operation_id",
        "session_digest",
        "packet_digest",
        "reviewer_id",
        "observed_at",
        "disposition",
        "checks",
        "notes",
        "attestation_digest",
    }
    checks = value.get("checks")
    if (
        set(value) != exact_keys
        or value.get("schema") != HUMAN_OBSERVATION_SCHEMA
        or value.get("work_unit") != WORK_UNIT
        or value.get("operation_id") != operation_id
        or value.get("session_digest") != session_digest
        or value.get("packet_digest") != packet_digest
        or value.get("disposition") not in {"Pass", "Fail", "Inconclusive"}
        or not isinstance(value.get("reviewer_id"), str)
        or not value["reviewer_id"].startswith("windows:")
        or not isinstance(value.get("notes"), str)
        or not isinstance(checks, dict)
        or set(checks) != expected_checks
        or not all(item is None or isinstance(item, bool) for item in checks.values())
        or not lowercase_digest(claimed)
        or digest_value(core) != claimed
    ):
        raise EvidenceError("human observation attestation is malformed or stale")
    parse_utc(value["observed_at"])
    if value["disposition"] == "Pass" and not all(item is True for item in checks.values()):
        raise EvidenceError("human Pass requires every frozen UI check to be true")
    if value["disposition"] == "Fail" and not any(item is False for item in checks.values()):
        raise EvidenceError("human Fail requires at least one observed false invariant")
    if value["disposition"] == "Inconclusive" and not any(
        item is None for item in checks.values()
    ):
        raise EvidenceError("human Inconclusive requires an unestablished UI invariant")
    return value


def validate_native_packet(
    session: dict[str, Any],
    packet_path: Path,
) -> dict[str, Any]:
    packet = read_strict_json(packet_path)
    packet_digest = packet.get("packet_digest")
    if (
        packet.get("schema") != "factorio.play_candidate_evidence_packet.v1"
        or not lowercase_digest(packet_digest)
        or packet.get("human_verdict") != "unset"
        or packet.get("grants_authority") is not False
        or packet.get("product_route_available") is not False
    ):
        raise EvidenceError("candidate lifecycle packet boundary is invalid")
    result = subprocess.run(
        [
            session["harness_path"],
            "--verify-packet",
            str(packet_path),
            packet_digest,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise EvidenceError(
            "native candidate packet verification failed: "
            + (result.stderr or result.stdout)
        )
    return packet


def prepare_session(args: argparse.Namespace) -> dict[str, Any]:
    if os.name != "nt" or not PREFLIGHT.is_elevated():
        raise EvidenceError("Gate 4C baseline capture requires elevated Windows")
    preflight = validate_ready_preflight(args.preflight)
    task_root = Path(preflight["task_root"]["path"])
    if task_root.name != WORK_UNIT or Path(os.path.abspath(args.task_root)) != task_root:
        raise EvidenceError("task root differs from the ready preflight")
    task_audit = PREFLIGHT.audit_no_follow(task_root, require_file=False)
    if not task_audit["safe"] or not PREFLIGHT.path_is_within(args.preflight, task_root):
        raise EvidenceError("ready preflight is outside the exact safe task root")
    description = preflight["instance"]["description"]
    binding = description["instance_binding"]
    instance_id = description["instance_id"]
    if not re.fullmatch(r"gate4c-[a-z0-9-]+", args.operation_id):
        raise EvidenceError("operation ID is not a Gate 4C identifier")
    instance_root = Path(binding["write_data_path"])
    workspace = instance_root.parents[1]
    if normalized_path(workspace) != normalized_path(task_root / "workspace"):
        raise EvidenceError("instance workspace differs from the exact Gate 4C workspace")
    sessions_root = task_root / "evidence" / "sessions"
    expected_names = {
        "baseline": args.operation_id + "-baseline.json",
        "classification": args.operation_id + "-roots.json",
        "session": args.operation_id + "-session.json",
    }
    if (
        args.baseline_out.name != expected_names["baseline"]
        or args.classification_out.name != expected_names["classification"]
        or args.session_out.name != expected_names["session"]
    ):
        raise EvidenceError("session evidence filenames do not bind the operation ID")
    baseline_out = prepare_new_output(
        args.baseline_out,
        root=task_root,
        expected_parent=sessions_root,
    )
    classification_out = prepare_new_output(
        args.classification_out,
        root=task_root,
        expected_parent=sessions_root,
    )
    session_out = prepare_new_output(
        args.session_out,
        root=task_root,
        expected_parent=sessions_root,
    )
    operation_root = workspace / "temporary" / args.operation_id
    operation_record = workspace / "operations" / args.operation_id
    if operation_root.exists() or operation_record.exists():
        raise EvidenceError("operation ID already has temporary or durable state")
    harness_audit = PREFLIGHT.audit_no_follow(args.harness, require_file=True)
    if (
        not harness_audit["safe"]
        or not PREFLIGHT.path_is_within(args.harness, task_root)
    ):
        raise EvidenceError("native verdict harness is not a stable regular file")
    observation_root = operation_root / "process" / "observation"
    observation_root.mkdir(parents=True, exist_ok=False)
    owner = operation_root / ".facman-gate4c-verdict-owner"
    owner.write_text(WORK_UNIT + "\n" + args.operation_id + "\n", encoding="utf-8")

    protected = protected_specs(preflight, workspace)
    writable = writable_specs(workspace, instance_root, args.operation_id)
    baseline_started_at = utc_now()
    protected_resources = capture_resources(protected)
    writable_resources = capture_writable(writable)
    if {item["resource_id"] for item in protected_resources} != PROTECTED_IDS:
        raise EvidenceError("protected baseline does not cover the exact frozen scope")
    if not all(item["complete"] for item in protected_resources + writable_resources):
        raise EvidenceError("baseline capture is incomplete")
    baseline = {
        "schema": BASELINE_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "work_unit": WORK_UNIT,
        "operation_id": args.operation_id,
        "preflight_digest": preflight["preflight_digest"],
        "baseline_started_at": baseline_started_at,
        "baseline_completed_at": utc_now(),
        "specs": {"protected": protected, "writable": writable},
        "protected_resources": protected_resources,
        "writable_resources": writable_resources,
        "protected_baseline_digest": resource_set_digest(protected_resources),
        "writable_baseline_digest": resource_set_digest(writable_resources),
    }
    baseline["baseline_bundle_digest"] = digest_value(baseline)
    atomic_json(baseline_out, baseline)

    classification = {
        "schema": CLASSIFICATION_SCHEMA,
        "writable_filesystem": [
            {"resource_id": resource_id, "path": path}
            for resource_id, paths in sorted(writable.items())
            for path in paths
        ],
        "protected_filesystem": [
            {"resource_id": resource_id, "path": path}
            for resource_id, paths in sorted(protected["filesystem"].items())
            for path in paths
        ],
    }
    atomic_json(classification_out, classification)

    factorio_executable = preflight["factorio_executable"]
    source = preflight["source_evidence"]
    principal = preflight["operator_attestation"]["reviewer_id"]
    repository_revision = preflight["repositories"]["facman"]["revision"]
    session = {
        "schema": SESSION_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "work_unit": WORK_UNIT,
        "prepared_at": utc_now(),
        "preflight_path": str(Path(os.path.abspath(args.preflight))),
        "preflight_digest": preflight["preflight_digest"],
        "preflight_file_sha256": PREFLIGHT.sha256_file(args.preflight),
        "task_root": str(task_root),
        "workspace": str(workspace),
        "instance_id": instance_id,
        "operation_id": args.operation_id,
        "operation_root": str(operation_root),
        "installation_root": str(Path(binding["read_data_path"]).parent),
        "executable": factorio_executable["path_audit"]["path"],
        "expected_executable_sha256": factorio_executable["sha256"],
        "authenticated_source_artifact_digest": source["artifact_sha256"],
        "source_authentication_evidence_digest": source[
            "authentication_evidence_digest"
        ],
        "facman_source_revision_digest": sha256_text(
            preflight["reviewed_artifacts"]["source_candidate_revision"]
        ),
        "facman_build_identity_digest": preflight["facman_artifact"]["sha256"],
        "evidence_tool_revision": repository_revision,
        "evidence_tool_revision_digest": sha256_text(repository_revision),
        "machine_binding_id": preflight["host"]["session_identity"][
            "machine_binding_id"
        ],
        "principal": {
            "provider_id": "windows.local-principal.v1",
            "principal_id": principal,
            "application_session_id": sha256_text(
                preflight["host"]["session_identity"]["boot_identity"]
                + ":"
                + preflight["host"]["session_identity"]["wake_identity"]
                + ":"
                + preflight["preflight_digest"]
            ),
        },
        "windows_system_root": os.environ.get("SystemRoot", r"C:\Windows"),
        "policy_path": str(
            ROOT
            / "contracts"
            / "generated-index"
            / "hermetic_standalone_play_policy.v1.canonical.json"
        ),
        "python_executable": sys.executable,
        "python_executable_sha256": PREFLIGHT.sha256_file(Path(sys.executable)),
        "observer_tool": str(ROOT / "tools" / "gate4c_verdict_session.py"),
        "observer_tool_sha256": PREFLIGHT.sha256_file(
            ROOT / "tools" / "gate4c_verdict_session.py"
        ),
        "evidence_tool": str(Path(__file__).resolve()),
        "evidence_tool_sha256": PREFLIGHT.sha256_file(Path(__file__).resolve()),
        "harness_path": str(Path(os.path.abspath(args.harness))),
        "harness_sha256": PREFLIGHT.sha256_file(args.harness),
        "classification_roots": str(classification_out),
        "classification_roots_sha256": PREFLIGHT.sha256_file(
            classification_out
        ),
        "baseline_bundle": str(baseline_out),
        "baseline_bundle_sha256": PREFLIGHT.sha256_file(baseline_out),
        "protected_baseline_digest": baseline["protected_baseline_digest"],
        "writable_baseline_digest": baseline["writable_baseline_digest"],
        "comparison_out": str(operation_root / "baseline-comparison.json"),
        "plan_out": str(session_out.parent / (args.operation_id + "-plan.json")),
    }
    session["session_digest"] = digest_value(session)
    atomic_json(session_out, session)
    return session


def finish_comparison(args: argparse.Namespace) -> dict[str, Any]:
    baseline = read_strict_json(args.baseline)
    claimed = baseline.get("baseline_bundle_digest")
    core = dict(baseline)
    core.pop("baseline_bundle_digest", None)
    if (
        baseline.get("schema") != BASELINE_SCHEMA
        or baseline.get("work_unit") != WORK_UNIT
        or not lowercase_digest(claimed)
        or digest_value(core) != claimed
    ):
        raise EvidenceError("baseline bundle identity is invalid")
    operation_values = baseline.get("specs", {}).get("writable", {}).get(
        "operation.temporary"
    )
    if not isinstance(operation_values, list) or len(operation_values) != 1:
        raise EvidenceError("baseline does not bind one operation temporary root")
    operation_root = Path(operation_values[0])
    expected_out = operation_root / "baseline-comparison.json"
    if (
        normalized_path(args.out) != normalized_path(expected_out)
        or args.out.exists()
        or not (operation_root / ".facman-gate4c-verdict-owner").is_file()
    ):
        raise EvidenceError("comparison output is not the new bound operation record")
    protected_after = capture_resources(baseline["specs"]["protected"])
    writable_after = capture_writable(baseline["specs"]["writable"])
    protected_before = {
        item["resource_id"]: item for item in baseline["protected_resources"]
    }
    writable_before = {
        item["resource_id"]: item for item in baseline["writable_resources"]
    }

    def compare(
        before: dict[str, dict[str, Any]],
        after: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "resource_id": item["resource_id"],
                "before_digest": before[item["resource_id"]]["resource_digest"],
                "after_digest": item["resource_digest"],
                "complete": bool(
                    before[item["resource_id"]]["complete"] and item["complete"]
                ),
                "changed": (
                    before[item["resource_id"]]["resource_digest"]
                    != item["resource_digest"]
                ),
            }
            for item in sorted(after, key=lambda value: value["resource_id"])
        ]

    protected_comparisons = compare(protected_before, protected_after)
    writable_comparisons = compare(writable_before, writable_after)
    output = {
        "schema": COMPARISON_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "work_unit": WORK_UNIT,
        "operation_id": baseline["operation_id"],
        "generated_at": utc_now(),
        "baseline_bundle_digest": claimed,
        "protected_resources_after": protected_after,
        "writable_resources_after": writable_after,
        "protected_comparisons": protected_comparisons,
        "writable_comparisons": writable_comparisons,
        "protected_complete": all(item["complete"] for item in protected_comparisons),
        "protected_changed": any(item["changed"] for item in protected_comparisons),
    }
    output["comparison_digest"] = digest_value(output)
    atomic_json(args.out, output)
    return output


def finalize_verdict(args: argparse.Namespace) -> dict[str, Any]:
    first_session = validate_session_record(args.first_session)
    second_session = validate_session_record(args.second_session)
    if (
        first_session["instance_id"] != second_session["instance_id"]
        or first_session["operation_id"] == second_session["operation_id"]
        or first_session["machine_binding_id"] != second_session["machine_binding_id"]
        or first_session["facman_source_revision_digest"]
        != second_session["facman_source_revision_digest"]
        or first_session["facman_build_identity_digest"]
        != second_session["facman_build_identity_digest"]
    ):
        raise EvidenceError("two-launch verdict sessions are not one exact candidate")
    task_root = Path(first_session["task_root"])
    first_packet = validate_native_packet(first_session, args.first_packet)
    second_packet = validate_native_packet(second_session, args.second_packet)
    first_human = validate_human_observation(
        args.first_human,
        operation_id=first_session["operation_id"],
        session_digest=first_session["session_digest"],
        packet_digest=first_packet["packet_digest"],
        expected_checks=FIRST_LAUNCH_CHECKS,
    )
    second_human = validate_human_observation(
        args.second_human,
        operation_id=second_session["operation_id"],
        session_digest=second_session["session_digest"],
        packet_digest=second_packet["packet_digest"],
        expected_checks=SECOND_LAUNCH_CHECKS,
    )
    if first_human["reviewer_id"] != second_human["reviewer_id"]:
        raise EvidenceError("human reviewer identity changed between launches")
    if (
        first_packet.get("permit_id") == second_packet.get("permit_id")
        or first_packet.get("permit_claims_digest")
        == second_packet.get("permit_claims_digest")
    ):
        raise EvidenceError("relaunch did not bind fresh permit authority")
    technical = [
        first_packet.get("technical_disposition"),
        second_packet.get("technical_disposition"),
    ]
    human = [first_human["disposition"], second_human["disposition"]]
    if "fail_evidence" in technical or "Fail" in human:
        derived = "Fail"
    elif (
        any(item != "eligible_for_human_verdict" for item in technical)
        or "Inconclusive" in human
    ):
        derived = "Inconclusive"
    else:
        derived = "Pass"
    if args.verdict != derived:
        raise EvidenceError(
            f"requested verdict {args.verdict} conflicts with derived {derived}"
        )
    verdict_out = prepare_new_output(
        args.out,
        root=task_root,
        expected_parent=task_root / "evidence" / "verdict",
    )
    output = {
        "schema": VERDICT_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "work_unit": WORK_UNIT,
        "policy_digest": POLICY_DIGEST,
        "instance_id": first_session["instance_id"],
        "machine_binding_id": first_session["machine_binding_id"],
        "reviewer_id": first_human["reviewer_id"],
        "recorded_at": utc_now(),
        "launches": [
            {
                "sequence": 1,
                "operation_id": first_session["operation_id"],
                "session_digest": first_session["session_digest"],
                "packet_digest": first_packet["packet_digest"],
                "permit_id": first_packet["permit_id"],
                "permit_claims_digest": first_packet["permit_claims_digest"],
                "technical_disposition": technical[0],
                "human_observation_digest": first_human["attestation_digest"],
                "human_disposition": human[0],
            },
            {
                "sequence": 2,
                "operation_id": second_session["operation_id"],
                "session_digest": second_session["session_digest"],
                "packet_digest": second_packet["packet_digest"],
                "permit_id": second_packet["permit_id"],
                "permit_claims_digest": second_packet["permit_claims_digest"],
                "technical_disposition": technical[1],
                "human_observation_digest": second_human["attestation_digest"],
                "human_disposition": human[1],
            },
        ],
        "verdict": derived,
        "grants_authority": False,
        "product_route_available": False,
    }
    output["verdict_digest"] = digest_value(output)
    atomic_json(verdict_out, output)
    return output


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Gate 4C stable baseline and comparison evidence."
    )
    commands = value.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--preflight", type=Path, required=True)
    prepare.add_argument("--task-root", type=Path, required=True)
    prepare.add_argument("--operation-id", required=True)
    prepare.add_argument("--harness", type=Path, required=True)
    prepare.add_argument("--baseline-out", type=Path, required=True)
    prepare.add_argument("--classification-out", type=Path, required=True)
    prepare.add_argument("--session-out", type=Path, required=True)
    finish = commands.add_parser("finish")
    finish.add_argument("--baseline", type=Path, required=True)
    finish.add_argument("--out", type=Path, required=True)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--first-session", type=Path, required=True)
    finalize.add_argument("--first-packet", type=Path, required=True)
    finalize.add_argument("--first-human", type=Path, required=True)
    finalize.add_argument("--second-session", type=Path, required=True)
    finalize.add_argument("--second-packet", type=Path, required=True)
    finalize.add_argument("--second-human", type=Path, required=True)
    finalize.add_argument(
        "--verdict", choices=("Pass", "Fail", "Inconclusive"), required=True
    )
    finalize.add_argument("--out", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "prepare":
        session = prepare_session(args)
        print(
            "gate4c-verdict-evidence: prepared "
            f"({session['session_digest']}; {args.session_out})"
        )
        return 0
    if args.command == "finish":
        result = finish_comparison(args)
        print(
            "gate4c-verdict-evidence: compared "
            f"({result['comparison_digest']}; {args.out})"
        )
        return 0
    result = finalize_verdict(args)
    print(
        "gate4c-verdict-evidence: verdict "
        f"{result['verdict']} ({result['verdict_digest']}; {args.out})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"gate4c-verdict-evidence: {exc}", file=sys.stderr)
        raise SystemExit(2)
