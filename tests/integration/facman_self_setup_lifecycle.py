#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise the real FacManSetup/USK lifecycle against a stored fixture payload."""

from __future__ import annotations

import argparse
import base64
import contextlib
import ctypes
import hashlib
import os
import secrets
import stat
import struct
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CALL_EVIDENCE: Path | None = None
CALL_COUNT = 0
CANARY_TIMEOUT: float | None = None
REAL_DEADLINE: float | None = None
REAL_COMMANDS: list[dict[str, object]] = []
REAL_CHILD_ROOT: Path | None = None
PROCESS_CALL_COUNT = 0
HOSTED_WINDOWS_FAILURE_ROOT = (
    r"C:\Users\RUNNER~1\AppData\Local\Temp\facman-self-setup-oq9k_8n0"
)


def utf16_units(path: Path | str) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def provider_payload_path(root: Path, version: str, *, predecessor: bool) -> Path:
    physical = "FacMan.generation." + "0" * 64
    if predecessor:
        physical += "." + "0" * 64
    return root / "Programs" / physical / "generations" / version / "bin" / "facman.exe"


def ci_length_child_root(parent: Path) -> tuple[Path, int]:
    required_units = utf16_units(Path(HOSTED_WINDOWS_FAILURE_ROOT))
    candidate = parent / "ci"
    deficit = max(0, required_units - utf16_units(candidate))
    return parent / ("ci-" + "x" * deficit), required_units


def run_command(command: list[str]):
    if CANARY_TIMEOUT is None:
        return subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools import provider_canary_process as bounded
    global PROCESS_CALL_COUNT
    directory = None
    if REAL_CHILD_ROOT is not None:
        PROCESS_CALL_COUNT += 1
        directory = REAL_CHILD_ROOT / f"{PROCESS_CALL_COUNT:03d}-setup-child"
    timeout = CANARY_TIMEOUT
    if REAL_DEADLINE is not None:
        timeout = min(timeout, REAL_DEADLINE - time.monotonic())
        if timeout <= 0:
            raise AssertionError("real current-user qualification exhausted its total deadline")
    result = bounded.command(command, cwd=ROOT, timeout=timeout, directory=directory)
    if result.receipt["termination"] != "completed":
        raise bounded.CommandFailure(result)
    completed = subprocess.CompletedProcess(command, result.returncode,
        result.stdout.decode("utf-8"), result.stderr.decode("utf-8"))
    setattr(completed, "facman_bounded_receipt", result.receipt)
    return completed


def invoke(executable: Path, *arguments: object, expected: int = 0,
           shell_integration: bool = False, noninteractive: bool = False,
           qualification: tuple[str, Path] | None = None) -> dict[str, object]:
    command = [
        str(executable),
        *(str(value) for value in arguments),
    ]
    if shell_integration:
        command.append("--shell-integration")
    else:
        command.append("--no-shell-integration")
    if noninteractive:
        command.append("--noninteractive")
    if qualification is not None:
        boundary, permit = qualification
        command.extend(("--qualification-interrupt-after", boundary,
                        "--qualification-interrupt-permit", str(permit)))
    command.append("--json")
    result = run_command(command)
    global CALL_COUNT
    if CALL_EVIDENCE is not None:
        CALL_COUNT += 1
        prefix = CALL_EVIDENCE / f"{CALL_COUNT:03d}"
        prefix.with_suffix(".stdout").write_text(result.stdout, encoding="utf-8")
        prefix.with_suffix(".stderr").write_text(result.stderr, encoding="utf-8")
        prefix.with_suffix(".json").write_text(json.dumps(
            {"command": command, "exit_code": result.returncode}, indent=2) + "\n", encoding="utf-8")
    if result.returncode != expected:
        raise AssertionError(
            f"command returned {result.returncode}, expected {expected}: {command}\n"
            f"stdout={result.stdout[-8000:]}\nstderr={result.stderr[-8000:]}"
        )
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"command did not return JSON: {command}\n{result.stdout[-8000:]}") from exc
    if shell_integration:
        REAL_COMMANDS.append({
            "command": command,
            "exit_code": result.returncode,
            "response": response,
            "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
            "bounded_process_receipt": getattr(result, "facman_bounded_receipt", None),
        })
    return response


def windows_command_argv(command_line: str) -> list[str]:
    argc = ctypes.c_int()
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    values = shell32.CommandLineToArgvW(command_line, ctypes.byref(argc))
    if not values:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [values[index] for index in range(argc.value)]
    finally:
        kernel32.LocalFree(ctypes.cast(values, ctypes.c_void_p))


def invoke_registered(command_line: str, *extra: object,
                      expected: int = 0) -> subprocess.CompletedProcess[str]:
    command = windows_command_argv(command_line) + [str(value) for value in extra]
    result = run_command(command)
    REAL_COMMANDS.append({
        "registered_command": command_line,
        "command": command,
        "exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
        "bounded_process_receipt": getattr(result, "facman_bounded_receipt", None),
    })
    if result.returncode != expected:
        raise AssertionError(
            f"registered command returned {result.returncode}, expected {expected}: {command_line}\n"
            f"stdout={result.stdout[-8000:]}\nstderr={result.stderr[-8000:]}"
        )
    return result


def registry_text(registry: dict[str, object], name: str) -> str:
    values = registry.get("values")
    if not isinstance(values, list):
        raise AssertionError(f"registry values are unavailable while reading {name}")
    matches = [item.get("value") for item in values
               if isinstance(item, dict) and item.get("name") == name]
    if len(matches) != 1 or not isinstance(matches[0], str):
        raise AssertionError(f"registry value {name} is absent or ambiguous")
    return matches[0]


def stored_payload(path: Path, executable: Path, version: str, compression: int = zipfile.ZIP_STORED) -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.self_setup_package import source_revision, universal_setup_revision
    facman_revision = source_revision()
    provider_revision = universal_setup_revision()
    files = {
        f"facman/generations/{version}/bin/facman.exe": b"synthetic-cli-v1\n",
        f"facman/generations/{version}/FacMan.exe": b"synthetic-gui-v1\n",
        "facman/maintenance/FacManSetup.exe": executable.read_bytes(),
        "facman/state/current-generation.v1.json": (
            json.dumps(
                {
                    "schema": "facman.current_generation.v1",
                    "product_id": "facman",
                    "version": version,
                    "generation": f"generations/{version}",
                    "portable_package": "synthetic-portable.zip",
                    "portable_sha256": "a" * 64,
                    "facman_source_revision": facman_revision,
                    "universal_setup_revision": provider_revision,
                    "workspace_preserved": True,
                    "automatic_update": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8"),
    }
    with zipfile.ZipFile(path, "w", allowZip64=True) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = compression
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def stored_maintenance_payload(path: Path, executable: Path, version: str) -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.self_setup_package import (
        maintenance_descriptor,
        source_revision,
        universal_setup_revision,
    )
    facman_revision = source_revision()
    provider_revision = universal_setup_revision()
    current = {
        "schema": "facman.current_generation.v1",
        "product_id": "facman",
        "version": version,
        "generation": f"generations/{version}",
        "portable_package": "synthetic-portable.zip",
        "portable_sha256": "b" * 64,
        "facman_source_revision": facman_revision,
        "universal_setup_revision": provider_revision,
        "workspace_preserved": True,
        "automatic_update": False,
    }
    files = {
        f"facman/generations/{version}/bin/facman.exe": b"synthetic-cli-v2\n",
        f"facman/generations/{version}/FacMan.exe": b"synthetic-gui-v2\n",
        "facman/maintenance/FacManSetup.exe": executable.read_bytes(),
        "facman/state/current-generation.v1.json": (
            json.dumps(current, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8"),
        "facman/state/self-maintenance-package.v1.json": (
            json.dumps(
                maintenance_descriptor(
                    version=version,
                    facman_revision=facman_revision,
                    usk_revision=provider_revision,
                ),
                sort_keys=True,
                separators=(",", ":"),
            ) + "\n"
        ).encode("utf-8"),
    }
    with zipfile.ZipFile(path, "w", allowZip64=True) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def damaged_archive_controls(root: Path, executable: Path, package: Path) -> None:
    """Exercise a consistent but wrong CRC and a truncated archive via real apply."""
    original = package.read_bytes()
    crc_bytes = bytearray(original)
    with zipfile.ZipFile(package) as archive:
        first = archive.infolist()[0]
        local = first.header_offset
        central = archive.start_dir
    # Both header records agree; decoded payload integrity must detect this.
    wrong_crc = first.CRC ^ 1
    struct.pack_into("<I", crc_bytes, local + 14, wrong_crc)
    struct.pack_into("<I", crc_bytes, central + 16, wrong_crc)
    for name, raw in (("bad-crc", bytes(crc_bytes)), ("truncated", original[:-8])):
        case = root / name
        case.mkdir()
        broken = case / "payload.zip"
        broken.write_bytes(raw)
        sentinel = case / "foreign.txt"
        sentinel.write_bytes(b"preserve foreign fixture bytes\n")
        target, state = case / "target", case / "state"
        response = invoke(executable, "install", "--package", broken, "--root", target,
                          "--state-root", state, "--acceptance-root", case, "--yes", expected=4)
        error = response.get("error", {})
        if name == "bad-crc":
            detail = json.loads(error.get("detail", "{}"))
            if (error.get("code") != "self_setup_provider_refused" or
                    detail.get("error", {}).get("code") != "lifecycle_refused" or
                    "CRC" not in detail.get("error", {}).get("message", "")):
                raise AssertionError("CRC fixture did not reach the provider payload-integrity refusal")
        elif error.get("code") != "self_setup_payload_invalid":
            raise AssertionError("truncation fixture did not reach the FacMan payload refusal")
        if (response.get("status") != "error" or target.exists() or
                sentinel.read_bytes() != b"preserve foreign fixture bytes\n" or
                broken.read_bytes() != raw or package.read_bytes() != original):
            raise AssertionError("damaged archive refusal changed foreign input or published target")
        inventory = [{"path": p.relative_to(case).as_posix(),
                      "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                     for p in sorted(case.rglob("*")) if p.is_file()]
        (case / "refusal-effects.json").write_text(json.dumps(
            {"response": response, "target_exists": False, "files": inventory}, indent=2) + "\n",
            encoding="utf-8")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _plain_metadata(path: Path, label: str, *, directory: bool) -> os.stat_result:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise AssertionError(f"{label} could not be observed without following links") from exc
    reparse = bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
    expected = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    if stat.S_ISLNK(metadata.st_mode) or reparse or not expected:
        kind = "directory" if directory else "regular file"
        raise AssertionError(f"{label} is not a plain {kind}")
    if not directory and metadata.st_nlink != 1:
        raise AssertionError(f"{label} is not a single-link regular file")
    return metadata


def _retained_file_metadata(
        path: Path, state_root: Path, acceptance_root: Path,
        label: str) -> os.stat_result:
    repair_root = state_root / "repair-sources"
    if (os.path.normcase(os.path.abspath(path.parent)) !=
            os.path.normcase(os.path.abspath(repair_root))):
        raise AssertionError(f"{label} is outside the exact retained repair directory")
    authority = Path(os.path.abspath(acceptance_root))
    repair = Path(os.path.abspath(repair_root))
    try:
        relative = Path(os.path.relpath(repair, authority))
    except ValueError as exc:
        raise AssertionError(f"{label} is outside retained repair authority") from exc
    if relative.is_absolute() or relative == Path("..") or ".." in relative.parts:
        raise AssertionError(f"{label} is outside retained repair authority")
    current = authority
    _plain_metadata(current, "retained repair acceptance root", directory=True)
    for component in relative.parts:
        current = current / component
        _plain_metadata(current, "retained repair ancestry", directory=True)
    return _plain_metadata(path, label, directory=False)


def stable_retained_digest(
        path: Path, state_root: Path, acceptance_root: Path, label: str) -> str:
    metadata = _retained_file_metadata(path, state_root, acceptance_root, label)
    identity = (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
    digest = hashlib.sha256()
    observed = 0
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != identity:
            raise AssertionError(f"{label} changed before it was read")
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            observed += len(chunk)
            digest.update(chunk)
        closed = os.fstat(source.fileno())
        if (closed.st_dev, closed.st_ino, closed.st_size, closed.st_mtime_ns) != identity:
            raise AssertionError(f"{label} changed while it was read")
    final = _retained_file_metadata(path, state_root, acceptance_root, label)
    if ((final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) != identity or
            observed != metadata.st_size):
        raise AssertionError(f"{label} pathname changed while it was read")
    return digest.hexdigest()


def stable_retained_bytes(
        path: Path, state_root: Path, acceptance_root: Path,
        label: str, maximum: int) -> bytes:
    metadata = _retained_file_metadata(
        path, state_root, acceptance_root, label
    )
    if metadata.st_size > maximum:
        raise AssertionError(f"{label} exceeds its bounded read size")
    identity = (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != identity:
            raise AssertionError(f"{label} changed before it was read")
        content = source.read(maximum + 1)
        closed = os.fstat(source.fileno())
        if (closed.st_dev, closed.st_ino, closed.st_size, closed.st_mtime_ns) != identity:
            raise AssertionError(f"{label} changed while it was read")
    final = _retained_file_metadata(path, state_root, acceptance_root, label)
    if ((final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) != identity or
            len(content) != metadata.st_size or len(content) > maximum):
        raise AssertionError(f"{label} pathname changed while it was read")
    return content


def windows_start_menu_shortcut() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        raise AssertionError("APPDATA is unavailable for current-user integration inspection")
    return Path(appdata) / "Microsoft/Windows/Start Menu/Programs/FacMan.lnk"


def powershell_shortcut_fields(path: Path) -> dict[str, object]:
    encoded_path = base64.b64encode(str(path).encode("utf-16-le")).decode("ascii")
    script = (
        f"$path = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('{encoded_path}')); "
        "$shell = New-Object -ComObject WScript.Shell; "
        "$shortcut = $shell.CreateShortcut($path); "
        "[ordered]@{target=$shortcut.TargetPath;working_directory=$shortcut.WorkingDirectory;"
        "arguments=$shortcut.Arguments} | ConvertTo-Json -Compress"
    )
    encoded_script = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    result = run_command([
        "powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_script,
    ])
    if result.returncode:
        raise AssertionError("WScript.Shell shortcut inspection failed: " + result.stderr[-2000:])
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError("WScript.Shell shortcut inspection did not return JSON") from exc
    if not isinstance(value, dict) or set(value) != {"target", "working_directory", "arguments"}:
        raise AssertionError("WScript.Shell shortcut inspection returned an invalid shape")
    return value


def inspect_shortcut_no_follow(path: Path) -> dict[str, object]:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return {"state": "absent", "path": str(path)}
    reparse = bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
    if stat.S_ISLNK(metadata.st_mode) or reparse or not stat.S_ISREG(metadata.st_mode):
        return {"state": "unreadable", "path": str(path), "no_follow": {
            "mode": metadata.st_mode, "reparse": reparse,
        }}
    fields = powershell_shortcut_fields(path)
    return {
        "state": "present",
        "path": str(path),
        "no_follow": {
            "mode": metadata.st_mode,
            "size": metadata.st_size,
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "modified_ns": metadata.st_mtime_ns,
            "reparse": False,
        },
        "sha256": sha256_path(path),
        "fields": fields,
    }


def registry_json_value(value: object) -> object:
    if isinstance(value, bytes):
        return {"encoding": "hex", "value": value.hex()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def inspect_registry_64() -> dict[str, object]:
    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\FacMan"
    access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    try:
        hive = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(hive, key_path, 0, access)
    except FileNotFoundError:
        return {"state": "absent", "view": "64-bit", "path": "HKCU\\" + key_path}
    except OSError as exc:
        return {"state": "unreadable", "view": "64-bit", "path": "HKCU\\" + key_path,
                "error": repr(exc)}
    try:
        values: list[dict[str, object]] = []
        index = 0
        while True:
            try:
                name, value, kind = winreg.EnumValue(key, index)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 259:
                    break
                raise
            values.append({"name": name, "type": kind, "value": registry_json_value(value)})
            index += 1
        subkeys: list[str] = []
        index = 0
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, index))
            except OSError as exc:
                if getattr(exc, "winerror", None) == 259:
                    break
                raise
            index += 1
        return {"state": "present", "view": "64-bit", "path": "HKCU\\" + key_path,
                "values": values, "subkeys": subkeys}
    except OSError as exc:
        return {"state": "unreadable", "view": "64-bit", "path": "HKCU\\" + key_path,
                "error": repr(exc)}
    finally:
        key.Close()
        hive.Close()


def assert_absent_native(shortcut: dict[str, object], registry: dict[str, object], phase: str) -> None:
    if shortcut.get("state") != "absent" or registry.get("state") != "absent":
        raise AssertionError(f"{phase}: current-user integration is present or unreadable; preserving it")


def same_windows_path(left: object, right: Path) -> bool:
    if not isinstance(left, str):
        return False
    try:
        return os.path.samefile(left, right)
    except OSError:
        return os.path.normcase(os.path.realpath(left)) == \
            os.path.normcase(os.path.realpath(right))


def assert_owned_native(shortcut: dict[str, object], registry: dict[str, object],
                        install: Path, state_root: Path, acceptance_root: Path,
                        version: str, phase: str, *,
                        active_root: Path | None = None,
                        active_package_sha256: str | None = None,
                        retained_package_sha256s: set[str] | None = None) -> None:
    active_root = active_root or install
    generation = active_root / "generations" / version
    fields = shortcut.get("fields") if shortcut.get("state") == "present" else None
    if not isinstance(fields, dict) or not same_windows_path(fields.get("target"), generation / "FacMan.exe") or \
            not same_windows_path(fields.get("working_directory"), generation) or fields.get("arguments") != "":
        raise AssertionError(f"{phase}: shortcut is not owned by this exact fixture/version")
    if registry.get("state") != "present" or registry.get("view") != "64-bit" or registry.get("subkeys") != []:
        raise AssertionError(f"{phase}: 64-bit uninstall registration is absent, foreign, or unreadable")
    values = registry.get("values")
    if not isinstance(values, list):
        raise AssertionError(f"{phase}: uninstall registration values are unreadable")
    table = {item["name"]: item for item in values if isinstance(item, dict) and "name" in item}
    repair_root = state_root / "repair-sources"
    _plain_metadata(state_root, "retained repair state root", directory=True)
    _plain_metadata(repair_root, "retained repair directory", directory=True)
    try:
        source_names = sorted(
            entry.name for entry in os.scandir(repair_root)
            if entry.name.endswith(".zip")
        )
    except OSError as exc:
        raise AssertionError(f"{phase}: retained repair directory is unreadable") from exc
    sources = [repair_root / name for name in source_names]
    source_table: dict[str, Path] = {}
    for source in sources:
        observed_digest = stable_retained_digest(
            source, state_root, acceptance_root, f"{phase} retained repair ZIP"
        )
        if source.stem == observed_digest:
            source_table[source.stem] = source
    expected_sources = retained_package_sha256s
    if expected_sources is None:
        expected_sources = set(source_table)
        if len(expected_sources) != 1:
            raise AssertionError(f"{phase}: exact digest-named offline repair source is absent")
    if set(source_table) != expected_sources or len(sources) != len(source_table):
        raise AssertionError(f"{phase}: exact digest-named offline repair source is absent")
    if active_package_sha256 is None:
        active_package_sha256 = next(iter(expected_sources))
    repair_source = source_table.get(active_package_sha256)
    if repair_source is None:
        raise AssertionError(f"{phase}: active generation repair source is absent")
    for retained_sha256, retained_source in source_table.items():
        retained_launcher = retained_source.with_name(
            f"{retained_sha256}.FacManSetup.exe"
        )
        retained_receipt = retained_source.with_name(
            f"{retained_sha256}.maintenance.v1"
        )
        launcher_sha256 = stable_retained_digest(
            retained_launcher, state_root, acceptance_root,
            f"{phase} retained maintenance launcher"
        )
        expected_receipt = (
            "facman-repair-source-receipt-v1\n"
            f"source_sha256={retained_sha256}\n"
            f"launcher_sha256={launcher_sha256}\n"
        ).encode("utf-8")
        if stable_retained_bytes(
                retained_receipt, state_root, acceptance_root,
                f"{phase} retained maintenance receipt", 4096) != expected_receipt:
            raise AssertionError(f"{phase}: retained maintenance custody receipt is invalid")
    maintenance = repair_source.with_name(f"{repair_source.stem}.FacManSetup.exe")
    uninstall = (
        f'"{maintenance}" uninstall --root "{install}" --state-root "{state_root}" '
        f'--acceptance-root "{acceptance_root}" --yes --noninteractive --shell-integration'
    )
    modify = (
        f'"{maintenance}" repair --package "{repair_source}" --root "{install}" '
        f'--state-root "{state_root}" --acceptance-root "{acceptance_root}" '
        f'--yes --noninteractive --shell-integration'
    )
    expected = {
        "DisplayName": ("FacMan", 1),
        "DisplayVersion": (version, 1),
        "Publisher": ("Jules C", 1),
        "InstallLocation": (str(install), 1),
        "DisplayIcon": (f'"{generation / "FacMan.exe"}"', 1),
        "UninstallString": (uninstall, 1),
        "QuietUninstallString": (uninstall + " --json", 1),
        "ModifyPath": (modify, 1),
        "NoModify": (1, 4),
        "NoRepair": (0, 4),
    }
    if set(table) != set(expected) or any(
            table[name].get("value") != value or table[name].get("type") != kind
            for name, (value, kind) in expected.items()):
        raise AssertionError(f"{phase}: uninstall registration does not exactly bind this fixture/version")


def qualification_permit(root: Path, boundary: str, operation: str, version: str,
                         install: Path, state_root: Path) -> Path:
    nonce = secrets.token_hex(32)
    now = int(time.time())
    permit = root / f"{nonce}.permit.v1.json"
    permit.write_text(json.dumps({
        "schema": "facman.self_setup_qualification_interrupt_permit.v1",
        "nonce": nonce,
        "operation": operation,
        "boundary": boundary,
        "product_version": version,
        "install_root": str(install),
        "state_root": str(state_root),
        "acceptance_root": str(root),
        "issued_at_unix_seconds": now,
        "expires_at_unix_seconds": now + 60,
    }, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return permit


def maintenance_qualification_permit(
        root: Path, operation: str, apply: bool, version: str,
        install: Path, state: Path) -> Path:
    marker = root / ".facman-self-maintenance-qualification-root.v1"
    marker.write_bytes(b"facman-self-maintenance-qualification-root-v1\n")
    nonce = secrets.token_hex(32)
    now = int(time.time())
    permit = root / f"{nonce}.maintenance-fixture.v1.json"
    permit.write_text(json.dumps({
        "schema": "facman.self_maintenance_qualification_fixture.v1",
        "nonce": nonce,
        "operation": operation,
        "apply": apply,
        "product_version": version,
        "install_root": str(install),
        "state_root": str(state),
        "acceptance_root": str(root),
        "fixture_marker_sha256": hashlib.sha256(marker.read_bytes()).hexdigest(),
        "issued_at_unix_seconds": now,
        "expires_at_unix_seconds": now + 120,
    }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return permit


def journal_observation(install: Path) -> list[dict[str, object]]:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return []
    root = Path(local) / "FacMan/setup-coordinator.v1/setup-operations"
    if not root.is_dir():
        return []
    observations: list[dict[str, object]] = []
    for path in sorted(root.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if same_windows_path(value.get("install_root"), install):
            provider = value.get("provider")
            observations.append({"path": str(path), "state": value.get("state"),
                                 "boundary": value.get("recovery_boundary"),
                                 "provider_phase": provider.get("phase")
                                 if isinstance(provider, dict) else None,
                                 "operation": value.get("operation")})
    return observations


def file_inventory(root: Path) -> list[dict[str, object]]:
    if not root.is_dir():
        return []
    return [{"path": path.relative_to(root).as_posix(), "sha256": sha256_path(path)}
            for path in sorted(root.rglob("*")) if path.is_file()]


def assert_interrupted(response: dict[str, object], boundary: str) -> None:
    error = response.get("error")
    if response.get("status") != "error" or not isinstance(error, dict) or \
            error.get("code") != "self_setup_interrupted":
        compact_response = json.dumps(response, sort_keys=True, separators=(",", ":"))
        raise AssertionError(
            f"qualification boundary {boundary} did not report self_setup_interrupted: {compact_response}"
        )


def self_maintenance_identity(path: Path) -> dict[str, str]:
    """Read the exact immutable identity records from one produced setup overlay."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.self_maintenance_candidate import identity_from_overlay
    try:
        return identity_from_overlay(path)
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
        raise AssertionError(
            f"produced setup package has no exact self-maintenance identity: {path}"
        ) from exc


def semver_order(left: str, right: str) -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.self_maintenance_candidate import semver_order as compare
    try:
        return compare(left, right)
    except ValueError as exc:
        raise AssertionError(str(exc)) from exc


def exact_json_record(path: Path, expected: Path, keys: set[str], label: str) -> dict[str, object]:
    if not path.is_absolute() or os.path.normcase(os.path.abspath(path)) != \
            os.path.normcase(os.path.abspath(expected)):
        raise AssertionError(f"{label} path does not bind its exact coordinator location")
    metadata = os.lstat(path)
    reparse = bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
    if (stat.S_ISLNK(metadata.st_mode) or reparse or not stat.S_ISREG(metadata.st_mode) or
            metadata.st_nlink != 1 or metadata.st_size > 64 * 1024):
        raise AssertionError(f"{label} is not a bounded single-link regular file")
    identity = (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
    raw = path.read_bytes()
    observed = os.lstat(path)
    if (len(raw) != metadata.st_size or
            (observed.st_dev, observed.st_ino, observed.st_size, observed.st_mtime_ns) != identity):
        raise AssertionError(f"{label} changed while it was read")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{label} is not JSON") from exc
    if not isinstance(value, dict) or set(value) != keys:
        raise AssertionError(f"{label} does not have its exact record schema")
    return value


GENERATION_RECORD_KEYS = {
    "schema", "product_id", "generation_id", "product_version", "package_sha256",
    "facman_source_revision", "universal_setup_revision", "install_id", "install_root",
    "logical_root", "state_root", "acceptance_root", "gui", "maintenance_launcher",
}


def generation_identity(identity: dict[str, str], package_sha256: str) -> str:
    material = (
        "facman.self.generation.v1\n"
        "facman\n"
        f"{identity['version']}\n"
        f"{package_sha256}\n"
        f"{identity['source_revision']}\n"
        f"{identity['provider_revision']}\n"
        "facman.self_maintenance.v1\n"
        "versioned_generation_with_maintenance_v1\n"
        f"generations/{identity['version']}\n"
        "FacMan.exe\n"
        "bin/facman.exe\n"
        "maintenance/FacManSetup.exe\n"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def normalized_path(path: Path) -> Path:
    return Path(os.path.normpath(str(path)))


def physical_generation_root(logical_root: Path, generation_id: str) -> Path:
    logical = normalized_path(logical_root)
    logical_id = hashlib.sha256(
        ("facman.self.logical-root.v1\n" + str(logical) + "\n").encode("utf-8")
    ).hexdigest()
    physical_id = hashlib.sha256((
        "facman.self.physical-generation-root.v1\n" + logical_id + "\n" +
        generation_id + "\n"
    ).encode("utf-8")).hexdigest()
    return logical.parent / ("FacMan.generation." + physical_id)


def expected_generation_record(
        identity: dict[str, str], package_sha256: str, logical_root: Path,
        state_root: Path, acceptance_root: Path, *, legacy: bool) -> dict[str, object]:
    generation_id = generation_identity(identity, package_sha256)
    logical_root = normalized_path(logical_root)
    state_root = normalized_path(state_root)
    acceptance_root = normalized_path(acceptance_root)
    install_root = logical_root if legacy else physical_generation_root(
        logical_root, generation_id
    )
    install_id = "facman.self" if legacy else "facman.self.generation." + generation_id
    return {
        "schema": "facman.self_generation.v1",
        "product_id": "facman",
        "generation_id": generation_id,
        "product_version": identity["version"],
        "package_sha256": package_sha256,
        "facman_source_revision": identity["source_revision"],
        "universal_setup_revision": identity["provider_revision"],
        "install_id": install_id,
        "install_root": str(install_root),
        "logical_root": str(logical_root),
        "state_root": str(state_root),
        "acceptance_root": str(acceptance_root),
        "gui": str(install_root / "generations" / identity["version"] / "FacMan.exe"),
        "maintenance_launcher": str(install_root / "maintenance" / "FacManSetup.exe"),
    }


def require_transition_receipt(
        response: dict[str, object], operation: str, identity: dict[str, str],
        package_sha256: str, logical_root: Path, state_root: Path,
        acceptance_root: Path, previous: tuple[str, str] | None, *,
        migration_source: tuple[dict[str, str], str] | None = None,
        retained_legacy: dict[str, object] | None = None) -> dict[str, object]:
    response_keys = {
        "schema", "status", "operation", "phase", "operation_id",
        "generation_id", "product_version", "install_id", "install_root",
        "generation_record", "activation_record",
    }
    if (set(response) != response_keys or
            response.get("schema") != "facman.self_maintenance_cli.v1" or
            response.get("status") != "ok" or response.get("operation") != operation or
            response.get("phase") != "completed" or
            response.get("product_version") != identity["version"]):
        raise AssertionError(f"{operation} did not report an exact completed maintenance receipt")
    operation_id = response.get("operation_id")
    generation_id = response.get("generation_id")
    install_id = response.get("install_id")
    install_root_text = response.get("install_root")
    expected_generation_id = generation_identity(identity, package_sha256)
    if (not isinstance(operation_id, str) or not operation_id or
            not isinstance(generation_id, str) or len(generation_id) != 64 or
            any(value not in "0123456789abcdef" for value in generation_id) or
            generation_id != expected_generation_id or
            not isinstance(install_id, str) or not install_id or
            not isinstance(install_root_text, str) or not install_root_text):
        raise AssertionError(f"{operation} response identity is incomplete or independently invalid")
    legacy_target = retained_legacy is not None
    expected_target = expected_generation_record(
        identity, package_sha256, logical_root, state_root, acceptance_root,
        legacy=legacy_target,
    )
    if legacy_target:
        if install_id != "facman.self":
            raise AssertionError(
                f"{operation} retained legacy target changed its exact install id/root mode"
            )
    elif install_id != "facman.self.generation." + generation_id:
        raise AssertionError(f"{operation} install id does not bind the generation identity")
    install_root = Path(install_root_text)
    if (os.path.normcase(os.path.abspath(install_root)) !=
            os.path.normcase(os.path.abspath(Path(str(expected_target["install_root"]))))):
        raise AssertionError(f"{operation} physical generation root was not independently derived")
    coordinator = acceptance_root / "setup-coordinator.v1"
    generation_path = Path(str(response.get("generation_record", "")))
    activation_path = Path(str(response.get("activation_record", "")))
    generation = exact_json_record(
        generation_path,
        coordinator / "generations" / f"generation.{generation_id}.v1.json",
        GENERATION_RECORD_KEYS,
        f"{operation} generation record",
    )
    if generation != expected_target:
        raise AssertionError(f"{operation} generation record does not bind the target package/root")
    if legacy_target and generation != retained_legacy:
        raise AssertionError(f"{operation} legacy target is not the exact retained predecessor")
    activation = exact_json_record(
        activation_path,
        coordinator / "activations" / f"activation.{operation_id}.v1.json",
        {"schema", "product_id", "operation", "operation_id", "source_generation_id",
         "target_generation_id", "previous"},
        f"{operation} activation record",
    )
    previous_value = activation.get("previous")
    if (activation.get("schema") != "facman.self_activation.v1" or
            activation.get("product_id") != "facman" or
            activation.get("operation") != operation or
            activation.get("operation_id") != operation_id or
            activation.get("target_generation_id") != generation_id or
            not isinstance(activation.get("source_generation_id"), str) or
            not isinstance(previous_value, dict) or
            set(previous_value) != {"name", "sha256"}):
        raise AssertionError(f"{operation} activation record does not bind the transition")
    observed_previous = (previous_value.get("name"), previous_value.get("sha256"))
    if not all(isinstance(value, str) and value for value in observed_previous):
        raise AssertionError(f"{operation} activation has no exact predecessor")
    if (Path(str(observed_previous[0])).name != observed_previous[0] or
            not str(observed_previous[0]).startswith("activation.") or
            not str(observed_previous[0]).endswith(".v1.json") or
            len(str(observed_previous[1])) != 64 or
            any(value not in "0123456789abcdef" for value in str(observed_previous[1]))):
        raise AssertionError(f"{operation} activation predecessor identity is invalid")
    if previous is not None and observed_previous != previous:
        raise AssertionError(f"{operation} activation does not extend the reviewed chain head")
    predecessor = coordinator / "activations" / str(observed_previous[0])
    if sha256_path(predecessor) != observed_previous[1]:
        raise AssertionError(f"{operation} activation predecessor digest changed")
    observed_legacy: dict[str, object] | None = None
    if previous is None:
        if migration_source is None:
            raise AssertionError(f"{operation} has no independently bound migration source")
        migration = exact_json_record(
            predecessor, predecessor,
            {"schema", "product_id", "operation", "operation_id", "generation_id", "previous"},
            "legacy migration activation",
        )
        source_identity, source_package_sha256 = migration_source
        source_generation_id = generation_identity(
            source_identity, source_package_sha256
        )
        if (migration.get("schema") != "facman.self_activation.v1" or
                migration.get("product_id") != "facman" or
                migration.get("operation") != "migration" or
                migration.get("generation_id") != source_generation_id or
                migration.get("generation_id") != activation.get("source_generation_id") or
                migration.get("previous") != {"name": "", "sha256": ""}):
            raise AssertionError("legacy migration does not bind the update source")
        observed_legacy = exact_json_record(
            coordinator / "generations" / f"generation.{source_generation_id}.v1.json",
            coordinator / "generations" / f"generation.{source_generation_id}.v1.json",
            GENERATION_RECORD_KEYS,
            "legacy migration generation record",
        )
        expected_legacy = expected_generation_record(
            source_identity, source_package_sha256, logical_root, state_root,
            acceptance_root, legacy=True,
        )
        if observed_legacy != expected_legacy:
            raise AssertionError("legacy migration generation does not bind its package/root")
    else:
        predecessor_activation = exact_json_record(
            predecessor, predecessor,
            {"schema", "product_id", "operation", "operation_id", "source_generation_id",
             "target_generation_id", "previous"},
            f"{operation} predecessor activation",
        )
        if (predecessor_activation.get("schema") != "facman.self_activation.v1" or
                predecessor_activation.get("product_id") != "facman" or
                predecessor_activation.get("target_generation_id") !=
                activation.get("source_generation_id")):
            raise AssertionError(f"{operation} activation source does not extend its predecessor")
    return {
        "generation_id": generation_id,
        "install_root": install_root,
        "activation": (activation_path.name, sha256_path(activation_path)),
        "source_generation_id": activation["source_generation_id"],
        "retained_legacy": observed_legacy if observed_legacy is not None else retained_legacy,
    }


def run_real_self_maintenance_transition(args: argparse.Namespace, executable: Path) -> int:
    """Exercise a real current-user A -> B -> A -> B package transition.

    The runner account is intentionally disposable.  It retires the final
    chain through the public uninstaller and observes retained then active
    completion; no out-of-band deletion is allowed.
    """
    if os.name != "nt":
        raise AssertionError("--real-self-maintenance-transition is Windows-only")
    root = args.fixture_root
    evidence = args.evidence
    candidate_payload = args.payload
    baseline_executable = args.baseline_setup_exe
    baseline_payload = args.baseline_payload
    assert root is not None and evidence is not None and candidate_payload is not None
    assert baseline_executable is not None and baseline_payload is not None
    root.mkdir(parents=False)
    programs = root / "Programs"
    programs.mkdir()
    global REAL_CHILD_ROOT
    REAL_CHILD_ROOT = root / "setup-children"
    REAL_CHILD_ROOT.mkdir()
    observations: list[dict[str, object]] = []
    candidate_identity = self_maintenance_identity(candidate_payload)
    baseline_identity = self_maintenance_identity(baseline_payload)
    candidate_package_sha256 = sha256_path(candidate_payload)
    baseline_package_sha256 = sha256_path(baseline_payload)
    if (candidate_identity["source_revision"] == baseline_identity["source_revision"] or
            semver_order(baseline_identity["version"], candidate_identity["version"]) >= 0):
        raise AssertionError(
            "real maintenance transition requires source-distinct, strictly "
            "version-ordered produced setup packages"
        )

    install = programs / "FacMan"
    state_root = root / "SetupState"

    def observe(phase: str) -> tuple[dict[str, object], dict[str, object]]:
        shortcut = inspect_shortcut_no_follow(windows_start_menu_shortcut())
        registry = inspect_registry_64()
        observations.append({
            "phase": phase,
            "shortcut": shortcut,
            "registry": registry,
            "journal": journal_observation(install),
            "install_inventory": file_inventory(install),
        })
        return shortcut, registry

    try:
        pre_shortcut, pre_registry = observe("preflight")
        assert_absent_native(pre_shortcut, pre_registry, "preflight")
        for label, setup, identity in (
                ("baseline", baseline_executable, baseline_identity),
                ("candidate", executable, candidate_identity)):
            version_result = run_command([str(setup), "--version"])
            if version_result.returncode or version_result.stdout.strip() != identity["version"]:
                raise AssertionError(f"{label} setup version does not bind its produced package")

        common = ("--root", install, "--state-root", state_root,
                  "--acceptance-root", root, "--yes")
        installed = invoke(baseline_executable, "install", *common,
                           shell_integration=True, noninteractive=True)
        if installed.get("status") != "ok":
            raise AssertionError("baseline produced setup did not install from its own overlay")
        shortcut, registry = observe("baseline_install_completed")
        assert_owned_native(shortcut, registry, install, state_root, root,
                            baseline_identity["version"], "baseline install",
                            active_package_sha256=baseline_package_sha256,
                            retained_package_sha256s={baseline_package_sha256})

        updated = invoke(executable, "update", "--package", candidate_payload, *common,
                         shell_integration=True, noninteractive=True)
        update_receipt = require_transition_receipt(
            updated, "update", candidate_identity, candidate_package_sha256,
            install, state_root, root, None,
            migration_source=(baseline_identity, baseline_package_sha256),
        )
        shortcut, registry = observe("candidate_update_completed")
        assert_owned_native(shortcut, registry, install, state_root, root,
                            candidate_identity["version"], "candidate update",
                            active_root=update_receipt["install_root"],
                            active_package_sha256=candidate_package_sha256,
                            retained_package_sha256s={baseline_package_sha256,
                                                     candidate_package_sha256})

        downgraded = invoke(executable, "downgrade", "--package", baseline_payload, *common,
                            shell_integration=True, noninteractive=True)
        downgrade_receipt = require_transition_receipt(
            downgraded, "downgrade", baseline_identity, baseline_package_sha256,
            install, state_root, root, update_receipt["activation"],
            retained_legacy=update_receipt["retained_legacy"],
        )
        shortcut, registry = observe("baseline_downgrade_completed")
        assert_owned_native(shortcut, registry, install, state_root, root,
                            baseline_identity["version"], "baseline downgrade",
                            active_root=downgrade_receipt["install_root"],
                            active_package_sha256=baseline_package_sha256,
                            retained_package_sha256s={baseline_package_sha256,
                                                     candidate_package_sha256})

        rolled_back = invoke(executable, "rollback", *common,
                             shell_integration=True, noninteractive=True)
        rollback_receipt = require_transition_receipt(
            rolled_back, "rollback", candidate_identity, candidate_package_sha256,
            install, state_root, root, downgrade_receipt["activation"],
        )
        shortcut, registry = observe("candidate_rollback_completed")
        assert_owned_native(shortcut, registry, install, state_root, root,
                            candidate_identity["version"], "candidate rollback",
                            active_root=rollback_receipt["install_root"],
                            active_package_sha256=candidate_package_sha256,
                            retained_package_sha256s={baseline_package_sha256,
                                                     candidate_package_sha256})
        retained_retirement = invoke(executable, "uninstall", *common,
                                     shell_integration=True, noninteractive=True)
        if retained_retirement.get("phase") != "step_completed":
            raise AssertionError("chain retirement did not complete only its retained step")
        shortcut, registry = observe("chain_retirement_retained_completed")
        assert_owned_native(shortcut, registry, install, state_root, root,
                            candidate_identity["version"], "retained retirement",
                            active_root=rollback_receipt["install_root"],
                            active_package_sha256=candidate_package_sha256,
                            retained_package_sha256s={candidate_package_sha256})
        active_retirement = invoke(executable, "uninstall", *common,
                                   shell_integration=True, noninteractive=True)
        if active_retirement.get("phase") != "completed":
            raise AssertionError("chain retirement did not complete its active step")
        shortcut, registry = observe("chain_retirement_active_completed")
        assert_absent_native(shortcut, registry, "chain retirement")
        if install.exists():
            raise AssertionError("chain retirement retained the logical install root")
        outcome = "passed"
        return 0
    except BaseException as exc:
        outcome = "blocked_or_failed"
        observations.append({"phase": "failure", "error": repr(exc)})
        raise
    finally:
        primary_failure = sys.exc_info()[0] is not None
        try:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps({
                "schema": "facman.real_self_maintenance_transition_evidence.v1",
                "outcome": locals().get("outcome", "blocked_or_failed"),
                "source": {
                    "baseline_setup": str(baseline_executable),
                    "baseline_setup_sha256": sha256_path(baseline_executable),
                    "baseline_payload": str(baseline_payload),
                    "baseline_payload_sha256": sha256_path(baseline_payload),
                    "candidate_setup": str(executable),
                    "candidate_setup_sha256": sha256_path(executable),
                    "candidate_payload": str(candidate_payload),
                    "candidate_payload_sha256": sha256_path(candidate_payload),
                    "baseline_identity": baseline_identity,
                    "candidate_identity": candidate_identity,
                },
                "paths": {"fixture_root": str(root), "install_root": str(install),
                          "state_root": str(state_root), "evidence": str(evidence),
                          "setup_child_receipts": str(REAL_CHILD_ROOT)},
                "commands": REAL_COMMANDS,
                "observations": observations,
                "registry_view": "64-bit",
                "retained_final_state": "chain retirement completed through public setup",
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except BaseException as persistence_error:
            note = f"NOTE: real self-maintenance evidence persistence failed: {persistence_error!r}"
            if primary_failure:
                print(note, file=sys.stderr)
            else:
                raise AssertionError(note) from persistence_error


def run_real_current_user_integration(args: argparse.Namespace, executable: Path) -> int:
    if os.name != "nt":
        raise AssertionError("--real-current-user-integration is Windows-only")
    root = args.fixture_root
    evidence = args.evidence
    payload = args.payload
    assert root is not None and evidence is not None and payload is not None
    root.mkdir(parents=False)
    programs = root / "Programs"
    programs.mkdir()
    global REAL_CHILD_ROOT
    REAL_CHILD_ROOT = root / "setup-children"
    REAL_CHILD_ROOT.mkdir()
    observations: list[dict[str, object]] = []

    def observe(phase: str) -> tuple[dict[str, object], dict[str, object]]:
        shortcut = inspect_shortcut_no_follow(windows_start_menu_shortcut())
        registry = inspect_registry_64()
        observations.append({"phase": phase, "shortcut": shortcut, "registry": registry,
                             "journal": journal_observation(install),
                             "install_inventory": file_inventory(install)})
        return shortcut, registry

    install = programs / "FacMan"
    state_root = root / "SetupState"
    workspace = root / "FacManWorkspace"
    try:
        pre_shortcut, pre_registry = observe("preflight")
        assert_absent_native(pre_shortcut, pre_registry, "preflight")
        version_result = run_command([str(executable), "--version"])
        if version_result.returncode:
            raise AssertionError("setup version command failed after global-object preflight")
        version = version_result.stdout.strip()
        REAL_COMMANDS.append({
            "command": [str(executable), "--version"],
            "exit_code": version_result.returncode,
            "response": {"version": version},
            "stdout_sha256": hashlib.sha256(version_result.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(version_result.stderr.encode("utf-8")).hexdigest(),
            "bounded_process_receipt": getattr(version_result, "facman_bounded_receipt", None),
        })
        if not version.startswith("0.1.0-"):
            raise AssertionError(f"unexpected setup version: {version}")
        common = ("--root", install, "--state-root", state_root,
                  "--acceptance-root", root, "--yes")
        workspace.mkdir()
        keep = workspace / "keep.txt"
        keep.write_text("preserve\n", encoding="utf-8")

        packaged_install = invoke(executable, "install", *common,
                                  shell_integration=True, noninteractive=True)
        if packaged_install.get("status") != "ok":
            raise AssertionError("produced setup executable did not install from its own overlay")
        shortcut, registry = observe("packaged_argv0_install_completed")
        assert_owned_native(shortcut, registry, install, state_root, root, version,
                            "packaged argv0 install")
        first_sources = list((state_root / "repair-sources").glob("*.zip"))
        if len(first_sources) != 1:
            raise AssertionError("packaged install did not retain one repair package")
        withheld_first_source = root / "withheld-before-registered-uninstall.zip"
        os.replace(first_sources[0], withheld_first_source)
        invoke_registered(registry_text(registry, "UninstallString"))
        shortcut, registry = observe("registered_uninstall_without_zip_completed")
        assert_absent_native(shortcut, registry, "registered uninstall")
        if install.exists():
            raise AssertionError("registered uninstall did not remove the managed install")

        permit = qualification_permit(root, "files_applied", "install", version, install, state_root)
        boundary_a = invoke(executable, "install", "--package", payload, *common, expected=4,
                            shell_integration=True, noninteractive=True,
                            qualification=("files_applied", permit))
        assert_interrupted(boundary_a, "files_applied")
        shortcut, registry = observe("install_files_applied_interrupted")
        assert_absent_native(shortcut, registry, "files_applied")
        if not (install / "generations" / version / "FacMan.exe").is_file() or \
                not (install / "maintenance/FacManSetup.exe").is_file():
            raise AssertionError("files_applied boundary did not publish the fixture install")
        files_boundary_inventory = file_inventory(install)

        resumed_a = invoke(executable, "install", "--package", payload, *common,
                           shell_integration=True, noninteractive=True)
        if resumed_a.get("status") != "ok":
            raise AssertionError("ordinary install resume after files boundary failed")
        shortcut, registry = observe("install_files_applied_resumed")
        assert_owned_native(shortcut, registry, install, state_root, root, version, "files-boundary resume")
        if file_inventory(install) != files_boundary_inventory:
            raise AssertionError("files-boundary resume replayed provider-visible install content")

        permit = qualification_permit(root, "files_applied", "uninstall", version,
                                      install, state_root)
        registered_uninstall_a = registry_text(registry, "UninstallString")
        uninstall_boundary_a_result = invoke_registered(
            registered_uninstall_a, "--json",
            "--qualification-interrupt-after", "files_applied",
            "--qualification-interrupt-permit", permit, expected=4,
        )
        uninstall_boundary_a = json.loads(uninstall_boundary_a_result.stdout)
        assert_interrupted(uninstall_boundary_a, "files_applied")
        shortcut, registry = observe("uninstall_files_applied_interrupted")
        assert_owned_native(shortcut, registry, install, state_root, root, version,
                            "uninstall files boundary")
        if install.exists():
            raise AssertionError("uninstall files boundary retained provider-owned files")
        invoke_registered(registered_uninstall_a)
        shortcut, registry = observe("uninstall_files_applied_resumed")
        assert_absent_native(shortcut, registry, "uninstall files-boundary resume")
        if install.exists() or not keep.is_file() or not state_root.is_dir():
            raise AssertionError("uninstall files-boundary resume exceeded its owned fixture scope")

        permit = qualification_permit(root, "shortcut_applied", "install", version, install, state_root)
        boundary_b = invoke(executable, "install", "--package", payload, *common, expected=4,
                            shell_integration=True, noninteractive=True,
                            qualification=("shortcut_applied", permit))
        assert_interrupted(boundary_b, "shortcut_applied")
        shortcut, registry = observe("install_shortcut_applied_interrupted")
        if shortcut.get("state") != "present" or registry.get("state") != "absent":
            raise AssertionError("shortcut boundary did not expose exactly the shortcut effect")
        fields = shortcut.get("fields")
        generation = install / "generations" / version
        if not isinstance(fields, dict) or not same_windows_path(fields.get("target"), generation / "FacMan.exe") or \
                not same_windows_path(fields.get("working_directory"), generation) or fields.get("arguments") != "":
            raise AssertionError("shortcut boundary did not create the exact fixture shortcut")
        shortcut_boundary_observation = shortcut
        shortcut_boundary_inventory = file_inventory(install)

        resumed_b = invoke(executable, "install", "--package", payload, *common,
                           shell_integration=True, noninteractive=True)
        if resumed_b.get("status") != "ok":
            raise AssertionError("ordinary install resume after shortcut boundary failed")
        shortcut, registry = observe("install_shortcut_applied_resumed")
        assert_owned_native(shortcut, registry, install, state_root, root, version, "shortcut-boundary resume")
        if shortcut != shortcut_boundary_observation or \
                file_inventory(install) != shortcut_boundary_inventory:
            raise AssertionError("shortcut-boundary resume replayed an observable native or provider effect")

        permit = qualification_permit(root, "shortcut_applied", "uninstall", version,
                                      install, state_root)
        registered_uninstall_b = registry_text(registry, "UninstallString")
        uninstall_boundary_b_result = invoke_registered(
            registered_uninstall_b, "--json",
            "--qualification-interrupt-after", "shortcut_applied",
            "--qualification-interrupt-permit", permit, expected=4,
        )
        uninstall_boundary_b = json.loads(uninstall_boundary_b_result.stdout)
        assert_interrupted(uninstall_boundary_b, "shortcut_applied")
        shortcut, registry = observe("uninstall_shortcut_applied_interrupted")
        if shortcut.get("state") != "absent" or registry.get("state") != "present":
            raise AssertionError(
                "uninstall shortcut boundary did not expose exactly the retained registration"
            )
        invoke_registered(registered_uninstall_b)
        shortcut, registry = observe("uninstall_shortcut_applied_resumed")
        assert_absent_native(shortcut, registry, "uninstall shortcut-boundary resume")
        reinstalled = invoke(executable, "install", "--package", payload, *common,
                             shell_integration=True, noninteractive=True)
        if reinstalled.get("status") != "ok":
            raise AssertionError("install after uninstall recovery qualification failed")
        shortcut, registry = observe("install_after_uninstall_recovery")
        assert_owned_native(shortcut, registry, install, state_root, root, version,
                            "install after uninstall recovery")

        repair_source = next((state_root / "repair-sources").glob("*.zip"))
        maintenance_launcher = repair_source.with_name(
            f"{repair_source.stem}.FacManSetup.exe"
        )
        modify_path = registry_text(registry, "ModifyPath")
        withheld_repair_source = root / "withheld-before-missing-repair.zip"
        before_missing_repair = {
            "inventory": file_inventory(install),
            "shortcut": shortcut,
            "registry": registry,
            "journals": journal_observation(install),
        }
        os.replace(repair_source, withheld_repair_source)
        missing_repair_result = invoke_registered(modify_path, "--json", expected=4)
        missing_repair = json.loads(missing_repair_result.stdout)
        after_missing_shortcut, after_missing_registry = observe(
            "registered_repair_missing_payload_refused"
        )
        missing_error = missing_repair.get("error")
        if missing_repair.get("status") != "error" or not isinstance(missing_error, dict) or \
                missing_error.get("code") != "self_setup_package_missing" or \
                file_inventory(install) != before_missing_repair["inventory"] or \
                after_missing_shortcut != before_missing_repair["shortcut"] or \
                after_missing_registry != before_missing_repair["registry"] or \
                journal_observation(install) != before_missing_repair["journals"]:
            raise AssertionError("fresh registered repair with missing payload was not a typed no-effect refusal")
        os.replace(withheld_repair_source, repair_source)

        gui = install / "generations" / version / "FacMan.exe"
        gui.write_bytes(b"deliberate real-mode owned damage\n")
        damaged = invoke(executable, "verify", "--root", install, "--state-root", state_root,
                         "--acceptance-root", root, shell_integration=True, noninteractive=True)
        if damaged.get("provider", {}).get("payload", {}).get("status") != "fail":
            raise AssertionError("real-mode owned damage was not detected")
        repair_permit = qualification_permit(
            root, "provider_plan_reviewed", "repair", version, install, state_root
        )
        interrupted_repair = invoke(
            executable, "repair", "--package", payload, *common, expected=4,
            shell_integration=True, noninteractive=True,
            qualification=("provider_plan_reviewed", repair_permit),
        )
        assert_interrupted(interrupted_repair, "provider_plan_reviewed")
        if not any(
                item.get("provider_phase") == "plan_reviewed"
                for item in journal_observation(install)):
            raise AssertionError("repair plan-review interruption did not persist its provider phase")
        missing_original = root / "missing-original-repair-input.zip"
        resumed_repair = invoke(
            maintenance_launcher, "repair", "--package", missing_original, *common,
            shell_integration=True, noninteractive=True,
        )
        if resumed_repair.get("status") != "ok":
            raise AssertionError("interrupted repair did not resume from its retained source")
        repaired_verify = invoke(executable, "verify", "--root", install,
                                 "--state-root", state_root,
                                 "--acceptance-root", root,
                                 shell_integration=True, noninteractive=True)
        if repaired_verify.get("provider", {}).get("payload", {}).get("status") != "pass":
            raise AssertionError("registered offline repair did not restore the exact closure")
        shortcut, registry = observe("repair_completed")
        assert_owned_native(shortcut, registry, install, state_root, root, version, "repair")

        foreign = install / "operator-note.txt"
        foreign.write_text("retain\n", encoding="utf-8")
        before_refusal = {"foreign_sha256": sha256_path(foreign), "shortcut": shortcut,
                          "registry": registry}
        refusal = invoke(executable, "uninstall", *common, expected=4, shell_integration=True,
                         noninteractive=True)
        after_shortcut, after_registry = observe("foreign_uninstall_refusal")
        refusal_error = refusal.get("error")
        if refusal.get("status") != "error" or not isinstance(refusal_error, dict) or \
                refusal_error.get("code") != "self_setup_provider_refused" or \
                "foreign_content_review_required" not in str(refusal_error.get("detail")) or \
                not foreign.is_file() or \
                before_refusal["foreign_sha256"] != sha256_path(foreign) or \
                after_shortcut != shortcut or after_registry != registry:
            raise AssertionError("foreign-file uninstall did not return the exact refusal or preserve its fixture")
        preserved_foreign = root / "foreign-preserved-after-refusal.txt"
        foreign.rename(preserved_foreign)
        if sha256_path(preserved_foreign) != before_refusal["foreign_sha256"]:
            raise AssertionError("foreign fixture could not be preserved outside the owned install scope")

        if not journal_observation(install):
            raise AssertionError("owned cleanup requires a matching durable setup journal")
        shortcut, registry = observe("pre_clean_uninstall")
        assert_owned_native(shortcut, registry, install, state_root, root, version, "pre-clean-uninstall")
        invoke_registered(registry_text(registry, "UninstallString"))
        shortcut, registry = observe("clean_uninstall_completed")
        assert_absent_native(shortcut, registry, "clean uninstall")
        if install.exists() or not keep.is_file() or not state_root.is_dir():
            raise AssertionError("clean uninstall did not preserve workspace/state or remove only install")
        outcome = "passed"
        return 0
    except BaseException as exc:
        outcome = "blocked_or_failed"
        observations.append({"phase": "failure", "error": repr(exc)})
        raise
    finally:
        primary_failure = sys.exc_info()[0] is not None
        try:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps({
                "schema": "facman.real_current_user_integration_evidence.v1",
                "outcome": locals().get("outcome", "blocked_or_failed"),
                "source": {"setup_executable": str(executable), "setup_sha256": sha256_path(executable),
                           "payload": str(payload), "payload_sha256": sha256_path(payload)},
                "paths": {"fixture_root": str(root), "install_root": str(install),
                          "state_root": str(state_root), "evidence": str(evidence),
                          "setup_child_receipts": str(REAL_CHILD_ROOT)},
                "commands": REAL_COMMANDS,
                "observations": observations,
                "registry_view": "64-bit",
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except BaseException as persistence_error:
            note = f"NOTE: real-current-user evidence persistence failed: {persistence_error!r}"
            if primary_failure:
                print(note, file=sys.stderr)
            else:
                raise AssertionError(note) from persistence_error


def main() -> int:
    global CALL_EVIDENCE, CANARY_TIMEOUT, REAL_DEADLINE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-exe", type=Path, required=True)
    parser.add_argument(
        "--payload",
        type=Path,
        help="Exercise an exact produced self-setup payload instead of the synthetic fixture.",
    )
    parser.add_argument(
        "--workspace-lifecycle-evidence",
        type=Path,
        help="Also qualify the exact installed CLI workspace lifecycle and write its receipt.",
    )
    parser.add_argument(
        "--resource-package-evidence",
        type=Path,
        help="Qualify the exact installed CLI resources before damage and uninstall.",
    )
    parser.add_argument("--compression", choices=("stored", "deflate"), default="stored")
    parser.add_argument("--ci-length-root", action="store_true",
                        help="Use a synthetic temporary root at the hosted-Windows path length.")
    parser.add_argument("--fixture-root", type=Path,
                        help="New disposable fixture path; retain all effects including failed runs.")
    parser.add_argument("--real-current-user-integration", action="store_true",
                        help="Windows disposable-runner qualification of current-user shell integration.")
    parser.add_argument("--real-self-maintenance-transition", action="store_true",
                        help="Windows disposable-runner qualification of A -> B -> A -> B maintenance.")
    parser.add_argument("--baseline-setup-exe", type=Path,
                        help="Exact older produced setup executable for the maintenance transition.")
    parser.add_argument("--baseline-payload", type=Path,
                        help="Exact older produced setup overlay for downgrade qualification.")
    parser.add_argument("--evidence", type=Path,
                        help="Absent evidence JSON path, required by real current-user integration.")
    parser.add_argument("--canary-command-timeout", type=float,
                         help="Windows source-canary only: finite owned command containment.")
    parser.add_argument("--real-command-timeout", type=float,
                        help="Required finite setup-child deadline for real current-user integration.")
    parser.add_argument("--real-total-timeout", type=float,
                        help="Finite total deadline shared by every real current-user child.")
    args = parser.parse_args()
    if args.real_current_user_integration or args.real_self_maintenance_transition:
        if os.name != "nt":
            parser.error("real current-user qualification is Windows-only")
        if args.real_current_user_integration and args.real_self_maintenance_transition:
            parser.error("choose exactly one real current-user qualification mode")
        if args.payload is None or not args.payload.is_absolute() or not args.payload.is_file():
            parser.error(
                "real current-user integration requires an exact absolute --payload file"
                if args.real_current_user_integration else
                "real maintenance transition requires an exact absolute --payload file"
            )
        if args.fixture_root is None or not args.fixture_root.is_absolute() or args.fixture_root.exists():
            parser.error("real current-user qualification requires an absent absolute retained --fixture-root")
        if args.evidence is None or not args.evidence.is_absolute() or args.evidence.exists():
            parser.error("real current-user qualification requires an absent absolute --evidence path")
        try:
            relative_evidence = args.evidence.relative_to(args.fixture_root)
        except ValueError:
            parser.error("real current-user evidence must be beneath --fixture-root")
        if not relative_evidence.parts:
            parser.error("real current-user evidence must be a file beneath --fixture-root")
        if args.workspace_lifecycle_evidence is not None or args.resource_package_evidence is not None:
            parser.error("real current-user integration writes its own exact evidence JSON")
        if args.real_command_timeout is None:
            parser.error("real current-user integration requires --real-command-timeout")
        if args.real_total_timeout is None or args.real_total_timeout <= 0:
            parser.error("real current-user qualification requires --real-total-timeout")
        if args.real_total_timeout > 3600:
            parser.error("--real-total-timeout must not exceed 3600 seconds")
        if args.real_self_maintenance_transition:
            if (args.baseline_setup_exe is None or not args.baseline_setup_exe.is_absolute() or
                    not args.baseline_setup_exe.is_file()):
                parser.error("real maintenance transition requires an exact absolute --baseline-setup-exe")
            if (args.baseline_payload is None or not args.baseline_payload.is_absolute() or
                    not args.baseline_payload.is_file()):
                parser.error("real maintenance transition requires an exact absolute --baseline-payload")
            args.baseline_setup_exe = args.baseline_setup_exe.resolve(strict=True)
            args.baseline_payload = args.baseline_payload.resolve(strict=True)
        elif args.baseline_setup_exe is not None or args.baseline_payload is not None:
            parser.error("baseline package inputs are limited to real maintenance transition")
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from tools import provider_canary_process as bounded
        CANARY_TIMEOUT = bounded.seconds(args.real_command_timeout, "real setup-child deadline")
        REAL_DEADLINE = time.monotonic() + bounded.seconds(
            args.real_total_timeout, "real current-user total deadline"
        )
        executable = args.setup_exe.resolve(strict=True)
        args.payload = args.payload.resolve(strict=True)
        if args.real_self_maintenance_transition:
            return run_real_self_maintenance_transition(args, executable)
        return run_real_current_user_integration(args, executable)
    if args.canary_command_timeout is not None:
        if args.fixture_root is None or args.payload is not None:
            parser.error("canary deadline mode requires a retained synthetic fixture")
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from tools import provider_canary_process as bounded
        CANARY_TIMEOUT = bounded.seconds(args.canary_command_timeout)

    if args.payload is not None and args.compression != "stored":
        parser.error("--compression applies only to synthetic fixtures")
    if args.fixture_root is not None:
        if not args.fixture_root.is_absolute() or args.fixture_root.exists():
            parser.error("--fixture-root must be an absent absolute disposable path")
        args.fixture_root.mkdir(parents=False)
        CALL_EVIDENCE = args.fixture_root / "calls"
        CALL_EVIDENCE.mkdir()
    if args.ci_length_root and (args.fixture_root is not None or args.payload is not None):
        parser.error("--ci-length-root is limited to the disposable synthetic lifecycle")
    if args.ci_length_root and os.name != "nt":
        parser.error("--ci-length-root is Windows-only")

    if args.resource_package_evidence is not None and args.payload is None:
        parser.error("--resource-package-evidence requires --payload")
    executable = args.setup_exe.resolve(strict=True)
    version_result = run_command([str(executable), "--version"])
    if version_result.returncode:
        raise AssertionError("setup version command failed")
    version = version_result.stdout.strip()
    if not version.startswith("0.1.0-"):
        raise AssertionError(f"unexpected setup version: {version}")

    fixture = (contextlib.nullcontext(str(args.fixture_root)) if args.fixture_root is not None
               else tempfile.TemporaryDirectory(prefix=(
                   "facman-self-setup-ci-long-" if args.ci_length_root
                   else "facman-self-setup-")))
    with fixture as temporary:
        root = Path(temporary)
        version_prefix, version_number = version.rsplit(".", 1)
        maintenance_version = f"{version_prefix}.{int(version_number) + 1}"
        if args.ci_length_root:
            root, hosted_root_units = ci_length_child_root(root)
            root.mkdir()
            hosted_predecessor_payload_units = utf16_units(
                provider_payload_path(
                    Path(HOSTED_WINDOWS_FAILURE_ROOT), maintenance_version,
                    predecessor=True
                )
            )
            exercised_payload = provider_payload_path(
                root, maintenance_version, predecessor=False
            )
            exercised_payload_units = utf16_units(exercised_payload)
            exercised_root_units = utf16_units(root)
            if exercised_root_units < hosted_root_units:
                raise AssertionError(
                    "CI-length root did not reach the hosted failing root length"
                )
            if exercised_payload_units >= 259:
                raise AssertionError(
                    "compact physical generation root still exceeds the "
                    "Windows provider payload limit"
                )
            if hosted_predecessor_payload_units < 259:
                raise AssertionError(
                    "hosted predecessor reference no longer models the "
                    "recorded native path-limit failure"
                )
            print(
                "ci-length-root: "
                f"hosted_root_utf16={hosted_root_units} "
                f"exercised_root_utf16={exercised_root_units} "
                "hosted_predecessor_payload_utf16="
                f"{hosted_predecessor_payload_units} "
                f"exercised_payload_utf16={exercised_payload_units}"
            )
        programs = root / "Programs"
        programs.mkdir()
        install = programs / "FacMan"
        state = root / "SetupState"
        if args.payload is None:
            package = root / "setup-payload.zip"
            stored_payload(package, executable, version,
                           zipfile.ZIP_DEFLATED if args.compression == "deflate" else zipfile.ZIP_STORED)
        else:
            package = args.payload.resolve(strict=True)

        if args.fixture_root is not None and args.payload is None:
            damaged_archive_controls(root, executable, package)

        if args.payload is None:
            maintenance_refusal = invoke(
                executable, "update", "--package", package, "--root", install,
                "--state-root", state, "--acceptance-root", root,
                shell_integration=True, expected=4,
            )
            if (maintenance_refusal.get("error", {}).get("code") !=
                    "self_maintenance_package_incompatible" or
                    install.exists() or state.exists()):
                raise AssertionError(
                    "public update did not reject a package without strict "
                    "maintenance metadata before effects"
                )

        plan = invoke(
            executable, "install", "--package", package, "--root", install,
            "--state-root", state, "--acceptance-root", root,
        )
        if plan.get("phase") != "plan" or install.exists() or state.exists():
            raise AssertionError(
                "install preview changed the target/state or returned the wrong phase"
            )

        installed = invoke(
            executable, "install", "--package", package, "--root", install,
            "--state-root", state, "--acceptance-root", root, "--yes",
        )
        if installed.get("phase") != "receipt":
            raise AssertionError("install did not return a receipt")
        gui = install / "generations" / version / "FacMan.exe"
        if not gui.is_file() or not (install / "maintenance/FacManSetup.exe").is_file():
            raise AssertionError("versioned generation or maintenance shell is missing")

        verified = invoke(
            executable, "verify", "--root", install, "--state-root", state,
            "--acceptance-root", root,
        )
        if verified["provider"]["payload"]["status"] != "pass":
            raise AssertionError("fresh install did not verify")

        if args.workspace_lifecycle_evidence is not None:
            if args.payload is None:
                raise AssertionError(
                    "installed workspace lifecycle proof requires an exact produced payload"
                )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/workspace_lifecycle_package_proof.py"),
                    "--executable", str(install / "generations" / version / "bin/facman.exe"),
                    "--profile", "windows_product_x64",
                    "--package-mode", "installed_stage",
                    "--evidence", str(args.workspace_lifecycle_evidence),
                ],
                cwd=ROOT,
                check=True,
            )

        if args.resource_package_evidence is not None:
            if args.payload is None:
                raise AssertionError("installed resource proof requires an exact produced payload")
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/resource_package_proof.py"),
                    "--executable", str(install / "generations" / version / "bin/facman.exe"),
                    "--profile", "windows_product_x64",
                    "--package-mode", "installed_stage",
                    "--evidence", str(args.resource_package_evidence),
                ],
                cwd=ROOT,
                check=True,
            )

        gui.write_bytes(b"deliberate damage\n")
        damaged = invoke(
            executable, "verify", "--root", install, "--state-root", state,
            "--acceptance-root", root,
        )
        if damaged["provider"]["payload"]["status"] != "fail":
            raise AssertionError("owned-file damage was not detected")

        repaired = invoke(
            executable, "repair", "--package", package, "--root", install,
            "--state-root", state, "--acceptance-root", root, "--yes",
        )
        if repaired["provider"]["payload"]["status"] != "completed":
            raise AssertionError("repair did not complete")
        restored = invoke(
            executable, "verify", "--root", install, "--state-root", state,
            "--acceptance-root", root,
        )
        if restored["provider"]["payload"]["status"] != "pass":
            raise AssertionError("repair did not restore the exact closure")

        maintenance_chain_active = False
        if args.payload is None:
            legacy_digest = hashlib.sha256(package.read_bytes()).hexdigest()
            repair_cache = state / "repair-sources"
            repair_cache.mkdir(exist_ok=True)
            (repair_cache / ".facman-repair-sources.v1").write_bytes(
                b"facman-repair-sources-v1\n"
            )
            legacy_source = repair_cache / f"{legacy_digest}.zip"
            legacy_helper = repair_cache / f"{legacy_digest}.FacManSetup.exe"
            legacy_source.write_bytes(package.read_bytes())
            legacy_helper.write_bytes(executable.read_bytes())
            helper_digest = hashlib.sha256(
                legacy_helper.read_bytes()
            ).hexdigest()
            (repair_cache / f"{legacy_digest}.maintenance.v1").write_bytes((
                "facman-repair-source-receipt-v1\n"
                f"source_sha256={legacy_digest}\n"
                f"launcher_sha256={helper_digest}\n"
            ).encode("utf-8"))
            target_version = maintenance_version
            maintenance_package = root / "maintenance-update.zip"
            stored_maintenance_payload(
                maintenance_package, executable, target_version
            )
            coordinator = root / "setup-coordinator.v1"
            unqualified = invoke(
                executable, "update", "--package", maintenance_package,
                "--root", install, "--state-root", state,
                "--acceptance-root", root, expected=4,
            )
            if (unqualified.get("error", {}).get("code") !=
                    "self_maintenance_qualification_invalid" or coordinator.exists()):
                raise AssertionError(
                    "production-root no-shell maintenance was not refused before writes"
                )
            preview_permit = maintenance_qualification_permit(
                root, "update", False, version, install, state
            )
            preview = invoke(
                executable, "update", "--package", maintenance_package,
                "--root", install, "--state-root", state,
                "--acceptance-root", root,
                "--qualification-fixture-permit", preview_permit,
            )
            if preview.get("phase") != "plan" or coordinator.exists():
                raise AssertionError(
                    "public maintenance preview did not remain read-only"
                )
            update_permit = maintenance_qualification_permit(
                root, "update", True, version, install, state
            )
            updated = invoke(
                executable, "update", "--package", maintenance_package,
                "--root", install, "--state-root", state,
                "--acceptance-root", root, "--yes",
                "--qualification-fixture-permit", update_permit,
            )
            if updated.get("phase") != "completed":
                raise AssertionError("public maintenance update did not complete")
            rollback_preview_permit = maintenance_qualification_permit(
                root, "rollback", False, version, install, state
            )
            discovered = invoke(
                executable, "rollback", "--root", install,
                "--state-root", state, "--acceptance-root", root,
                "--qualification-fixture-permit", rollback_preview_permit,
            )
            if (discovered.get("phase") != "plan" or
                    discovered.get("generation_id") ==
                    updated.get("generation_id")):
                raise AssertionError(
                    "public rollback preview did not discover the predecessor"
                )
            rollback_permit = maintenance_qualification_permit(
                root, "rollback", True, version, install, state
            )
            rolled_back = invoke(
                executable, "rollback", "--root", install,
                "--state-root", state, "--acceptance-root", root, "--yes",
                "--qualification-fixture-permit", rollback_permit,
            )
            if (rolled_back.get("phase") != "completed" or
                    rolled_back.get("generation_id") !=
                    discovered.get("generation_id")):
                raise AssertionError("public rollback did not reactivate legacy")
            maintenance_chain_active = True

        workspace = root / "FacManWorkspace"
        workspace.mkdir()
        keep = workspace / "keep.txt"
        keep.write_text("preserve\n", encoding="utf-8")
        if maintenance_chain_active:
            retained = invoke(
                executable, "uninstall", "--root", install,
                "--state-root", state, "--acceptance-root", root, "--yes",
            )
            if retained.get("phase") != "step_completed":
                raise AssertionError("activation-chain retained uninstall did not complete")
        unknown = install / "operator-note.txt"
        unknown.write_text("retain\n", encoding="utf-8")
        refusal = invoke(
            executable, "uninstall", "--root", install, "--state-root", state,
            "--acceptance-root", root, "--yes", expected=4,
        )
        if refusal.get("status") != "error" or not unknown.is_file() or not keep.is_file():
            raise AssertionError("foreign-content uninstall refusal did not preserve data")
        if maintenance_chain_active:
            if refusal.get("error", {}).get("code") != \
                    "self_maintenance_retirement_recovery_required":
                raise AssertionError("activation-chain foreign refusal lost its recovery boundary")
            return 0
        unknown.rename(root / "operator-note-preserved.txt")

        removed = invoke(
            executable, "uninstall", "--root", install, "--state-root", state,
            "--acceptance-root", root, "--yes",
        )
        if removed["provider"]["payload"]["status"] != "completed":
            raise AssertionError("clean uninstall did not complete")
        if install.exists() or not keep.is_file() or not state.is_dir():
            raise AssertionError("uninstall scope was not ownership bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
