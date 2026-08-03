# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build a deterministic, unsigned WinForms C1 portable ZIP prototype."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "apps/gui/windows/winforms/bin/Debug/FacMan.WinForms.exe"
DEFAULT_OUT = ROOT / "out/facman-c1-winforms-x64-portable-prototype.zip"
FIXED_ZIP_TIME = (2026, 8, 1, 0, 0, 0)
PROTOTYPE_NAME = "facman-c1-winforms-x64-portable-prototype.zip"


def prototype_files(executable: Path, cli: Path | None = None) -> dict[str, bytes]:
    exe_bytes = executable.read_bytes()
    files: dict[str, bytes] = {
        "bin/FacMan.WinForms.exe": exe_bytes,
        "PROTOTYPE-NOTICE.txt": (
            "FacMan Windows 10/11 x64 WinForms C1 portable prototype\n"
            "\n"
            "The product shell embeds deterministic facman.presentation.v0 fixtures.\n"
            "Fixture Play starts no Factorio process and grants no live Play authority.\n"
            "The generated command explorer is available under Advanced. Production\n"
            "dispatch requires the full package manifest and hash-closed bin/facman.exe;\n"
            "this presentation prototype intentionally grants no backend override.\n"
            "This archive is unsigned, unpublished, and not a release artifact.\n"
        ).encode("utf-8"),
    }
    if cli is not None:
        files["bin/facman.exe"] = cli.read_bytes()
    manifest = {
        "schema": "facman.winforms_c1_portable_prototype.v0",
        "target": "windows_10_11_x64",
        "frontend": "winforms_net_framework_4_8",
        "presentation_contract": "facman.presentation.v0",
        "presentation_states": [
            "positive",
            "refused",
            "running",
            "exited",
            "interrupted",
        ],
        "presentation_storage": "embedded_resources",
        "transport": "bounded_process_rpc",
        "fixture_play_authority": "fixture_only",
        "live_play_authority": False,
        "signed": False,
        "published": False,
        "files": {
            path: hashlib.sha256(payload).hexdigest()
            for path, payload in sorted(files.items())
        },
    }
    files["manifest/facman.winforms-c1-prototype.v0.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return files


def build(executable: Path, output: Path, cli: Path | None = None) -> Path:
    if not executable.is_file():
        raise ValueError(f"WinForms executable does not exist: {executable}")
    if cli is not None and not cli.is_file():
        raise ValueError(f"FacMan CLI executable does not exist: {cli}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(prototype_files(executable, cli).items()):
            entry = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 0
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, payload)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        output = build(args.exe.resolve(), args.out.resolve(), args.cli.resolve() if args.cli else None)
    except (OSError, ValueError) as exc:
        print(f"winforms-c1-portable: {exc}")
        return 1
    print(f"winforms-c1-portable: ok {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
