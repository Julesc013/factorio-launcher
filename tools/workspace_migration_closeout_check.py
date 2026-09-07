# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Accept only the independently reviewed historical workspace completion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK = "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01"
RECEIPT = ".aide/queue/active/FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01/evidence/package-integration-closeout.json"
# These immutable reviewed pins bind source87aa, mergecd2936 and run34048385176.
# Later source/package qualification needs a separately reviewed record.
RECEIPT_SEMANTIC_SHA256 = "8259a695712fb089d144c00177add7fa40870f609e859686362840d2f93a2d3a"
ARCHIVE_SHA256 = "bb852350a8112b4165ae9df4086e45d125d9f97a155b86a6c4a4c72979e0e1e2"


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate completion receipt field")
        result[key] = value
    return result


def validate(workunit: dict[str, Any], root: Path = ROOT) -> list[str]:
    """An active leaf has no completion claim; this exact completed leaf has proof."""
    if workunit.get("id") != TASK:
        return ["workspace completion validator received another WorkUnit"]
    if workunit.get("status") == "active":
        return ["active workspace WorkUnit must not claim completion evidence"] if "evidence" in workunit else []
    if workunit.get("status") != "complete" or workunit.get("evidence") != [RECEIPT]:
        return ["workspace completion requires its exact reviewed evidence binding"]
    try:
        with (root / RECEIPT).open("rb") as stream:
            raw = stream.read(64 * 1024 + 1)
        if len(raw) > 64 * 1024:
            raise ValueError("completion receipt exceeds its byte budget")
        value = json.loads(raw, object_pairs_hook=_unique)
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        if hashlib.sha256(canonical).hexdigest() != RECEIPT_SEMANTIC_SHA256:
            raise ValueError("completion source, merge, package or authority receipt changed")
        archive = root / Path(RECEIPT).parent / "package-integration-custody.zip"
        digest = hashlib.sha256()
        size = 0
        with archive.open("rb") as stream:
            while block := stream.read(64 * 1024):
                size += len(block)
                if size > 16 * 1024 * 1024:
                    raise ValueError("completion custody exceeds its byte budget")
                digest.update(block)
        if digest.hexdigest() != ARCHIVE_SHA256:
            raise ValueError("completion raw source and package custody changed")
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        return [f"workspace completion evidence refused: {error}"]
    return []
