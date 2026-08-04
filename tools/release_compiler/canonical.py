# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


SHA256_PATTERN = "^[0-9a-f]{64}$"


def canonical_bytes(value: Any) -> bytes:
    """Return the byte representation governed by facman.canonical_json.v1."""
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


def domain_digest_value(domain: str, value: Any) -> str:
    """Hash canonical JSON under an explicit record-domain separator."""
    if not domain or "\0" in domain:
        raise ValueError("digest domain must be non-empty and contain no NUL")
    return digest_bytes(domain.encode("utf-8") + b"\0" + canonical_bytes(value))


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_relative_path(value: str, *, field: str) -> str:
    if not value or "\\" in value or ":" in value:
        raise ValueError(f"{field} must be a non-empty portable relative path: {value!r}")
    path = PurePosixPath(value.rstrip("/"))
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{field} must not escape its root: {value!r}")
    return path.as_posix()


def expand_template(value: str, variables: dict[str, str], *, field: str) -> str:
    output = value
    for name in sorted(variables):
        output = output.replace("{" + name + "}", variables[name])
    if "{" in output or "}" in output:
        raise ValueError(f"{field} contains an unresolved template token: {output!r}")
    return output
