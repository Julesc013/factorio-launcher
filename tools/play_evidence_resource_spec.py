# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Closed preflight resource discovery for Play evidence.

Environment and Steam discovery happen once in preflight.  Baseline and
provider code consume the resulting closed resource specification and never
reinterpret process environment variables.
"""

from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, Mapping

from tools.play_evidence_stable_io import EvidenceIo, digest_value
from tools.play_verdict_route import HERMETIC_VERDICT03, PlayVerdictRoute


VDF_PATH = re.compile(r'"path"\s+"([^"]+)"', re.IGNORECASE)


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(path))


def _normalized(path: Path | str) -> str:
    return str(PureWindowsPath(_absolute(path))).casefold()


def startup_environment_snapshot(
    values: Mapping[str, str | None],
) -> dict[str, Any]:
    observed = {
        name: (value if isinstance(value, str) else "")
        for name, value in sorted(values.items())
    }
    core: dict[str, Any] = {
        "provider": "facman.process_start_environment.v1",
        "values": observed,
    }
    return {**core, "snapshot_digest": digest_value(core)}


def _stable_directory_children(
    root: Path,
    evidence_io: EvidenceIo,
) -> list[Path]:
    before = evidence_io.inspect_directory(root)["payload"]
    if not before["before_identity"]["present"]:
        return []
    children = sorted(
        (Path(item.path) for item in os.scandir(root) if item.is_dir(follow_symlinks=False)),
        key=_normalized,
    )
    after = evidence_io.inspect_directory(root)["payload"]
    if (
        before["before_identity"] != after["before_identity"]
        or before["after_identity"] != after["after_identity"]
    ):
        raise RuntimeError(f"resource discovery root changed: {root}")
    return children


def _installation_siblings(
    workspace: Path,
    selected: Path,
    evidence_io: EvidenceIo,
) -> list[Path]:
    records = workspace / "installs" / "refs"
    output: list[Path] = []
    before = evidence_io.inspect_directory(records)["payload"]
    if before["before_identity"]["present"]:
        for record in sorted(records.glob("*.json"), key=_normalized):
            document = evidence_io.read_json(record)["payload"]["document"]
            candidate = document.get("root")
            if (
                isinstance(candidate, str)
                and candidate
                and _normalized(candidate) != _normalized(selected)
            ):
                output.append(_absolute(candidate))
    after = evidence_io.inspect_directory(records)["payload"]
    if (
        before["before_identity"] != after["before_identity"]
        or before["after_identity"] != after["after_identity"]
    ):
        raise RuntimeError("installation records changed during resource discovery")
    return output


def _steam_roots(
    environment: Mapping[str, str],
) -> list[Path]:
    candidates: set[Path] = set()
    program_files = environment.get("ProgramFiles(x86)", "")
    if program_files:
        candidates.add(_absolute(Path(program_files) / "Steam"))
    if os.name == "nt":
        import winreg

        for hive, subkey, name in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Valve\Steam",
                "InstallPath",
            ),
        ):
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
                    candidates.add(_absolute(winreg.QueryValueEx(key, name)[0]))
            except OSError:
                continue
    return sorted(candidates, key=_normalized)


def _steam_libraries(
    roots: Iterable[Path],
    evidence_io: EvidenceIo,
) -> list[Path]:
    libraries = {_absolute(root) for root in roots}
    for root in roots:
        record = root / "steamapps" / "libraryfolders.vdf"
        if not record.is_file():
            continue
        text = evidence_io.read_text(
            record, maximum_bytes=16 * 1024 * 1024
        )["payload"]["text"]
        for match in VDF_PATH.finditer(text):
            libraries.add(_absolute(match.group(1).replace("\\\\", "\\")))
    return sorted(libraries, key=_normalized)


def _member(
    path: Path,
    evidence_io: EvidenceIo,
) -> dict[str, Any]:
    absolute = _absolute(path)
    if absolute.is_file():
        payload = evidence_io.inspect_file(absolute)["payload"]["file"]
    else:
        payload = evidence_io.inspect_directory(absolute)["payload"]
    return {
        "path": str(absolute),
        "root_identity": payload["before_identity"],
    }


def _filesystem_resource(
    resource_id: str,
    paths: Iterable[Path],
    evidence_io: EvidenceIo,
    *,
    source: str,
) -> dict[str, Any]:
    unique = {
        _normalized(path): _absolute(path)
        for path in paths
    }
    return {
        "resource_id": resource_id,
        "kind": "filesystem",
        "source": source,
        "members": [
            _member(unique[key], evidence_io) for key in sorted(unique)
        ],
    }


def _registry_resource(
    resource_id: str,
    members: list[tuple[str, str]],
) -> dict[str, Any]:
    return {
        "resource_id": resource_id,
        "kind": "registry",
        "source": "preflight_registry_discovery",
        "members": [
            {"hive": hive, "subkey": subkey}
            for hive, subkey in sorted(set(members))
        ],
    }


def build_resource_specification(
    *,
    preflight: dict[str, Any],
    workspace: Path,
    operation_id: str,
    route: PlayVerdictRoute,
    evidence_io: EvidenceIo,
    environment_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Create the one closed resource set consumed by baseline and provider."""

    environment = environment_snapshot["values"]
    description = preflight["instance"]["description"]
    binding = description["instance_binding"]
    instance_id = description["instance_id"]
    instance_root = _absolute(binding["write_data_path"])
    installation_root = _absolute(Path(binding["read_data_path"]).parent)
    source = _absolute(preflight["source_evidence"]["path_audit"]["path"])
    source_copy = _absolute(
        preflight["source_evidence"]["source_member"]["inspection_copy"][
            "path_audit"
        ]["path"]
    )
    facman_package = _absolute(Path(preflight["facman_artifact"]["path"]).parent)
    for required in ("APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "SystemRoot"):
        if not environment.get(required):
            raise RuntimeError(
                f"startup environment has no required {required} path"
            )
    appdata = _absolute(Path(environment["APPDATA"]) / "Factorio")
    localappdata = _absolute(Path(environment["LOCALAPPDATA"]) / "Factorio")
    programdata = _absolute(Path(environment["PROGRAMDATA"]) / "Factorio")
    steam_roots = _steam_roots(environment)
    libraries = _steam_libraries(steam_roots, evidence_io)
    steam_factorio = [
        root / "steamapps" / "common" / "Factorio" for root in libraries
    ]
    steam_userdata = [root / "userdata" for root in steam_roots]
    steam_cache = [root / "appcache" for root in steam_roots]
    other_instances = [
        path
        for path in _stable_directory_children(
            workspace / "instances", evidence_io
        )
        if path.name != instance_id
    ]
    filesystem = {
        "installation.selected": [installation_root],
        "installation.siblings": _installation_siblings(
            workspace, installation_root, evidence_io
        ),
        "instances.other": other_instances,
        "factorio.default_user_data": [appdata],
        "factorio.appdata": [appdata],
        "factorio.localappdata": [localappdata],
        "factorio.programdata": [programdata],
        "steam.installation": steam_factorio,
        "steam.userdata": steam_userdata + steam_cache,
        "facman.package": [facman_package],
        "factorio.source_artifacts": [source, source_copy],
    }
    if route is HERMETIC_VERDICT03:
        raise RuntimeError(
            "historical hermetic resource discovery remains immutable"
        )
    protected = [
        _filesystem_resource(
            resource_id,
            paths,
            evidence_io,
            source="startup_environment_snapshot"
            if resource_id.startswith(("factorio.", "steam."))
            else "preflight_candidate_projection",
        )
        for resource_id, paths in sorted(filesystem.items())
    ]
    protected.append(
        _registry_resource(
            "registry.factorio_uninstall",
            [
                ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (
                    "HKLM",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                ),
            ],
        )
    )
    writable = [
        _filesystem_resource(
            resource_id,
            [
                Path(
                    selector.format(
                        workspace=str(workspace),
                        instance=str(instance_root),
                        operation=operation_id,
                    ).replace("/", os.sep)
                )
            ],
            evidence_io,
            source="frozen_route_writable_mapping",
        )
        for resource_id, selector in sorted(route.writable_mapping().items())
    ]
    if {item["resource_id"] for item in protected} != route.protected_ids:
        raise RuntimeError("preflight resource specification is not exact")
    core: dict[str, Any] = {
        "schema": "facman.play_evidence_resource_specification.v1",
        "startup_environment": environment_snapshot,
        "protected_resources": protected,
        "writable_resources": writable,
    }
    return {**core, "resource_set_digest": digest_value(core)}


def baseline_specs(
    specification: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Project capture inputs without consulting environment or discovery."""

    protected: dict[str, Any] = {
        "filesystem": {},
        "registry": {},
        "conceptual": {},
    }
    for resource in specification["protected_resources"]:
        if resource["kind"] == "filesystem":
            protected["filesystem"][resource["resource_id"]] = [
                member["path"] for member in resource["members"]
            ]
        elif resource["kind"] == "registry":
            protected["registry"][resource["resource_id"]] = [
                {"hive": member["hive"], "subkey": member["subkey"]}
                for member in resource["members"]
            ]
        else:
            protected["conceptual"][resource["resource_id"]] = resource[
                "disclosure"
            ]
    writable = {
        resource["resource_id"]: [
            member["path"] for member in resource["members"]
        ]
        for resource in specification["writable_resources"]
    }
    return protected, writable
