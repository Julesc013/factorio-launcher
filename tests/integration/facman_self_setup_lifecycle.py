#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise the real FacManSetup/USK lifecycle against a stored fixture payload."""

from __future__ import annotations

import argparse
import base64
import contextlib
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
REAL_COMMANDS: list[dict[str, object]] = []
REAL_CHILD_ROOT: Path | None = None
PROCESS_CALL_COUNT = 0


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
    result = bounded.command(command, cwd=ROOT, timeout=CANARY_TIMEOUT, directory=directory)
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


def stored_payload(path: Path, executable: Path, version: str, compression: int = zipfile.ZIP_STORED) -> None:
    files = {
        f"facman/generations/{version}/bin/facman.exe": b"synthetic-cli-v1\n",
        f"facman/generations/{version}/FacMan.exe": b"synthetic-gui-v1\n",
        "facman/maintenance/FacManSetup.exe": executable.read_bytes(),
        "facman/state/current-generation.v1.json": (
            json.dumps(
                {
                    "schema": "facman.current_generation.v1",
                    "version": version,
                    "workspace_preserved": True,
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
    return isinstance(left, str) and os.path.normcase(os.path.normpath(left)) == \
        os.path.normcase(os.path.normpath(str(right)))


def assert_owned_native(shortcut: dict[str, object], registry: dict[str, object],
                        install: Path, version: str, phase: str) -> None:
    generation = install / "generations" / version
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
    expected = {
        "DisplayName": ("FacMan", 1),
        "DisplayVersion": (version, 1),
        "Publisher": ("Jules C", 1),
        "InstallLocation": (str(install), 1),
        "DisplayIcon": (f'"{generation / "FacMan.exe"}"', 1),
        "UninstallString": (f'"{install / "maintenance/FacManSetup.exe"}" uninstall --yes', 1),
        "QuietUninstallString": (f'"{install / "maintenance/FacManSetup.exe"}" uninstall --yes --json', 1),
        "ModifyPath": (f'"{install / "maintenance/FacManSetup.exe"}" repair --yes', 1),
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
            observations.append({"path": str(path), "state": value.get("state"),
                                 "boundary": value.get("recovery_boundary"),
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
        raise AssertionError(f"qualification boundary {boundary} did not report self_setup_interrupted")


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
        assert_owned_native(shortcut, registry, install, version, "files-boundary resume")
        if file_inventory(install) != files_boundary_inventory:
            raise AssertionError("files-boundary resume replayed provider-visible install content")

        cleanup_a = invoke(executable, "uninstall", *common, shell_integration=True,
                           noninteractive=True)
        if cleanup_a.get("status") != "ok":
            raise AssertionError("ordinary uninstall after files-boundary resume failed")
        shortcut, registry = observe("uninstall_after_files_boundary")
        assert_absent_native(shortcut, registry, "uninstall after files boundary")
        if install.exists() or not keep.is_file() or not state_root.is_dir():
            raise AssertionError("first ordinary uninstall exceeded its owned fixture scope")

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
        assert_owned_native(shortcut, registry, install, version, "shortcut-boundary resume")
        if shortcut != shortcut_boundary_observation or \
                file_inventory(install) != shortcut_boundary_inventory:
            raise AssertionError("shortcut-boundary resume replayed an observable native or provider effect")

        gui = install / "generations" / version / "FacMan.exe"
        gui.write_bytes(b"deliberate real-mode owned damage\n")
        damaged = invoke(executable, "verify", "--root", install, "--state-root", state_root,
                         "--acceptance-root", root, shell_integration=True, noninteractive=True)
        if damaged.get("provider", {}).get("payload", {}).get("status") != "fail":
            raise AssertionError("real-mode owned damage was not detected")
        repaired = invoke(executable, "repair", "--package", payload, *common,
                          shell_integration=True, noninteractive=True)
        if repaired.get("provider", {}).get("payload", {}).get("status") != "completed":
            raise AssertionError("real-mode repair did not complete")
        shortcut, registry = observe("repair_completed")
        assert_owned_native(shortcut, registry, install, version, "repair")

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
        assert_owned_native(shortcut, registry, install, version, "pre-clean-uninstall")
        removed = invoke(executable, "uninstall", *common, shell_integration=True,
                         noninteractive=True)
        if removed.get("status") != "ok":
            raise AssertionError("ordinary clean uninstall failed")
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
    global CALL_EVIDENCE, CANARY_TIMEOUT
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
    parser.add_argument("--fixture-root", type=Path,
                        help="New disposable fixture path; retain all effects including failed runs.")
    parser.add_argument("--real-current-user-integration", action="store_true",
                        help="Windows disposable-runner qualification of current-user shell integration.")
    parser.add_argument("--evidence", type=Path,
                        help="Absent evidence JSON path, required by real current-user integration.")
    parser.add_argument("--canary-command-timeout", type=float,
                         help="Windows source-canary only: finite owned command containment.")
    parser.add_argument("--real-command-timeout", type=float,
                        help="Required finite setup-child deadline for real current-user integration.")
    args = parser.parse_args()
    if args.real_current_user_integration:
        if os.name != "nt":
            parser.error("--real-current-user-integration is Windows-only")
        if args.payload is None or not args.payload.is_absolute() or not args.payload.is_file():
            parser.error("real current-user integration requires an exact absolute --payload file")
        if args.fixture_root is None or not args.fixture_root.is_absolute() or args.fixture_root.exists():
            parser.error("real current-user integration requires an absent absolute retained --fixture-root")
        if args.evidence is None or not args.evidence.is_absolute() or args.evidence.exists():
            parser.error("real current-user integration requires an absent absolute --evidence path")
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
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from tools import provider_canary_process as bounded
        CANARY_TIMEOUT = bounded.seconds(args.real_command_timeout, "real setup-child deadline")
        executable = args.setup_exe.resolve(strict=True)
        args.payload = args.payload.resolve(strict=True)
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
               else tempfile.TemporaryDirectory(prefix="facman-self-setup-"))
    with fixture as temporary:
        root = Path(temporary)
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

        plan = invoke(
            executable, "install", "--package", package, "--root", install,
            "--state-root", state, "--acceptance-root", root,
        )
        if plan.get("phase") != "plan" or install.exists():
            raise AssertionError("install preview changed the target or returned the wrong phase")

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

        workspace = root / "FacManWorkspace"
        workspace.mkdir()
        keep = workspace / "keep.txt"
        keep.write_text("preserve\n", encoding="utf-8")
        unknown = install / "operator-note.txt"
        unknown.write_text("retain\n", encoding="utf-8")
        refusal = invoke(
            executable, "uninstall", "--root", install, "--state-root", state,
            "--acceptance-root", root, "--yes", expected=4,
        )
        if refusal.get("status") != "error" or not unknown.is_file() or not keep.is_file():
            raise AssertionError("foreign-content uninstall refusal did not preserve data")
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
