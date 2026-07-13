# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".aide" / "local" / "evidence" / "factorio-version-capability-corpus.v1.json"
MAX_TREE_ENTRIES = 200_000
MAX_CAPTURE_BYTES = 128 * 1024


def version_key(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts) if parts else (2**31 - 1,)


def reported_version(text: str) -> str:
    match = re.search(r"(?i)(?:version\s*:\s*)?(\d+\.\d+(?:\.\d+)?)", text)
    return match.group(1) if match else "unknown"


def metadata_version(root: Path) -> str:
    candidates = (
        root / "data" / "base" / "info.json",
        root / "Factorio.app" / "Contents" / "Resources" / "data" / "base" / "info.json",
    )
    for candidate in candidates:
        try:
            if not candidate.is_file() or candidate.stat().st_size > 1024 * 1024:
                continue
            document = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        version = document.get("version") if isinstance(document, dict) else None
        if isinstance(version, str) and re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version):
            return version
    return "unknown"


def help_capabilities(text: str) -> dict[str, bool]:
    lower = text.lower()
    return {
        "config_option": "--config" in lower,
        "mod_directory_option": "--mod-directory" in lower,
        "start_server_option": "--start-server" in lower,
        "map_gen_settings_option": "--map-gen-settings" in lower,
        "benchmark_option": "--benchmark" in lower,
        "dump_data_option": "--dump-data" in lower,
        "load_game_option": "--load-game" in lower,
    }


def tree_fingerprint(root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    for directory, directories, files in os.walk(root, followlinks=False):
        directories.sort()
        files.sort()
        base = Path(directory)
        for name in [*directories, *files]:
            path = base / name
            count += 1
            if count > MAX_TREE_ENTRIES:
                raise RuntimeError(f"tree entry budget exceeded ({MAX_TREE_ENTRIES})")
            relative = path.relative_to(root).as_posix()
            stat = path.lstat()
            kind = "link" if path.is_symlink() else "directory" if path.is_dir() else "file"
            digest.update(f"{kind}\0{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8"))
    return digest.hexdigest(), count


def executable_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_executable(root: Path) -> Path | None:
    relative_candidates = (
        "bin/x64/factorio.exe",
        "bin/x64/factorio",
        "bin/Win32/factorio.exe",
        "bin/x86/factorio.exe",
        "bin/factorio.exe",
        "Factorio.app/Contents/MacOS/factorio",
    )
    for relative in relative_candidates:
        candidate = root / Path(relative)
        if candidate.is_file():
            return candidate
    visited = 0
    for directory, directories, files in os.walk(root, followlinks=False):
        directories.sort()
        files.sort()
        for name in files:
            visited += 1
            if visited > MAX_TREE_ENTRIES:
                return None
            if name.lower() in {"factorio", "factorio.exe"}:
                return Path(directory) / name
    return None


def steam_marker_present(root: Path) -> bool:
    return any(
        (root / relative).is_file()
        for relative in (
            "bin/x64/steam_api64.dll",
            "bin/x64/steam_api.dll",
            "steam_api64.dll",
            "steam_api.dll",
        )
    )


def probe_process(
    executable: Path,
    argument: str,
    install_root: Path,
    environment: dict[str, str],
    timeout_seconds: float,
) -> tuple[dict[str, object], str]:
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        completed = subprocess.run(
            [str(executable), argument],
            cwd=install_root,
            env=environment,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            creationflags=creation_flags,
        )
        captured = (completed.stdout + b"\n" + completed.stderr)[:MAX_CAPTURE_BYTES]
        return {
            "status": "completed",
            "exit_code": completed.returncode,
            "timed_out": False,
            "captured_bytes": len(captured),
        }, captured.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as exc:
        captured = ((exc.stdout or b"") + b"\n" + (exc.stderr or b""))[:MAX_CAPTURE_BYTES]
        return {
            "status": "timeout",
            "exit_code": None,
            "timed_out": True,
            "captured_bytes": len(captured),
        }, captured.decode("utf-8", errors="replace")
    except OSError as exc:
        return {
            "status": "error",
            "exit_code": None,
            "timed_out": False,
            "captured_bytes": 0,
            "error_kind": type(exc).__name__,
        }, ""


def probe_install(label: str, install_root: Path, timeout_seconds: float) -> dict[str, object]:
    executable = discover_executable(install_root)
    if executable is None:
        return {
            "label": label,
            "status": "missing_executable",
            "install_tree_unchanged": True,
        }
    before_digest, entry_count = tree_fingerprint(install_root)
    with tempfile.TemporaryDirectory(prefix="facman-factorio-probe-") as temporary:
        redirected = Path(temporary)
        environment = os.environ.copy()
        for name, relative in {
            "APPDATA": "AppData/Roaming",
            "LOCALAPPDATA": "AppData/Local",
            "HOME": "Home",
            "USERPROFILE": "Home",
            "XDG_CONFIG_HOME": "xdg/config",
            "XDG_DATA_HOME": "xdg/data",
            "XDG_CACHE_HOME": "xdg/cache",
        }.items():
            target = redirected / relative
            target.mkdir(parents=True, exist_ok=True)
            environment[name] = str(target)
        version_probe, version_text = probe_process(
            executable, "--version", install_root, environment, timeout_seconds
        )
        help_probe, help_text = probe_process(
            executable, "--help", install_root, environment, timeout_seconds
        )
    after_digest, after_entry_count = tree_fingerprint(install_root)
    steam = steam_marker_present(install_root)
    unchanged = before_digest == after_digest and entry_count == after_entry_count
    cli_version = reported_version(version_text)
    detected_version = cli_version if cli_version != "unknown" else metadata_version(install_root)
    return {
        "label": label,
        "status": "probed" if unchanged else "install_tree_changed",
        "executable_relative": executable.relative_to(install_root).as_posix(),
        "executable_sha256": executable_digest(executable),
        "executable_size": executable.stat().st_size,
        "reported_version": detected_version,
        "version_source": (
            "cli" if cli_version != "unknown" else
            "base_info_json" if detected_version != "unknown" else
            "unknown"
        ),
        "version_probe": version_probe,
        "help_probe": help_probe,
        "capabilities": help_capabilities(help_text),
        "distribution_origin": "steam" if steam else "unknown",
        "platform_integration": "steam" if steam else "none_detected",
        "strict_isolation_eligibility": "ineligible" if steam else "unproven",
        "external_state_domains": (
            ["default_factorio_data", "steam_cloud"] if steam else ["default_factorio_data"]
        ),
        "install_tree_fingerprint_before": before_digest,
        "install_tree_fingerprint_after": after_digest,
        "install_tree_entry_count": entry_count,
        "install_tree_unchanged": unchanged,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build a bounded, read-only Factorio version capability corpus")
    value.add_argument("--root", type=Path, required=True, help="Parent directory containing version-labelled installs")
    value.add_argument("--expected", nargs="*", default=[], help="Expected version directory labels")
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    value.add_argument("--timeout-seconds", type=float, default=8.0)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"factorio-version-corpus: root is not a directory: {root}")
    labels = sorted(
        set(args.expected) | {path.name for path in root.iterdir() if path.is_dir()},
        key=version_key,
    )
    installations: list[dict[str, object]] = []
    for label in labels:
        install_root = root / label
        if not install_root.is_dir():
            installations.append({
                "label": label,
                "status": "missing_install",
                "install_tree_unchanged": True,
            })
            continue
        try:
            installations.append(probe_install(label, install_root, args.timeout_seconds))
        except (OSError, RuntimeError) as exc:
            installations.append({
                "label": label,
                "status": "probe_refused",
                "error_kind": type(exc).__name__,
                "install_tree_unchanged": False,
            })
    complete = all(
        item["status"] == "probed" and item["install_tree_unchanged"]
        for item in installations
    )
    document = {
        "schema": "factorio.version_capability_corpus.v1",
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "complete" if complete else "incomplete",
        "read_only_install_probe": True,
        "user_state_environment_redirected": True,
        "raw_process_output_persisted": False,
        "absolute_paths_persisted": False,
        "corpus_root_label": root.name,
        "expected_labels": labels,
        "installation_count": len(installations),
        "installations": installations,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"factorio-version-corpus: {document['status']} ({len(installations)} installs) -> {output}")
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
