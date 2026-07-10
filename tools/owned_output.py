from __future__ import annotations

import json
import shutil
from pathlib import Path

MARKER_NAME = ".facman-owned-output.v1.json"
SCHEMA = "facman.owned_output.v1"


def ensure_owned_output_root(path: Path, kind: str) -> None:
    path = path.resolve()
    if path.exists() and not path.is_dir():
        raise ValueError(f"output root is not a directory: {path}")
    if path.exists():
        marker = path / MARKER_NAME
        if marker.is_file():
            _validate_marker(marker, kind)
            return
        if any(path.iterdir()):
            raise ValueError(f"refusing unowned output root with existing content: {path}")
    else:
        path.mkdir(parents=True)
    _write_marker(path, kind)


def reset_owned_output_root(path: Path, kind: str) -> None:
    path = path.resolve()
    if path.exists():
        marker = path / MARKER_NAME
        if not marker.is_file():
            raise ValueError(f"refusing to clean unowned output root: {path}")
        _validate_marker(marker, kind)
        shutil.rmtree(path)
    path.mkdir(parents=True)
    _write_marker(path, kind)


def assert_owned_output_root(path: Path, kind: str) -> None:
    marker = path.resolve() / MARKER_NAME
    if not marker.is_file():
        raise ValueError(f"refusing destructive operation without output ownership marker: {path.resolve()}")
    _validate_marker(marker, kind)


def _write_marker(path: Path, kind: str) -> None:
    marker = {"schema": SCHEMA, "owner": "facman", "kind": kind}
    (path / MARKER_NAME).write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_marker(path: Path, kind: str) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid output ownership marker {path}: {exc}") from exc
    expected = {"schema": SCHEMA, "owner": "facman", "kind": kind}
    if data != expected:
        raise ValueError(f"output ownership marker does not authorize {kind}: {path}")
