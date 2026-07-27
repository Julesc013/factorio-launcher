# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Python orchestration for the native Play-evidence I/O boundary.

The native probe owns file/object identity, bounded handle reads, directory
manifests, archive inspection/extraction, and durable writes.  This module
only constructs closed requests and validates the probe's closed response.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RESULT_SCHEMA = "facman.play_evidence_io_result.v1"
LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_JSON_BYTES = 64 * 1024 * 1024
DEFAULT_FILE_BYTES = 16 * 1024 * 1024 * 1024
DEFAULT_MANIFEST_ENTRIES = 250_000
DEFAULT_MANIFEST_BYTES = 16 * 1024 * 1024 * 1024
DEFAULT_MANIFEST_ENTRY_BYTES = 4 * 1024 * 1024 * 1024
DEFAULT_MANIFEST_DEPTH = 64
DEFAULT_ARCHIVE_BYTES = 8 * 1024 * 1024 * 1024
DEFAULT_ARCHIVE_ENTRIES = 100_000
DEFAULT_ARCHIVE_EXPANDED_BYTES = 64 * 1024 * 1024 * 1024
DEFAULT_ARCHIVE_ENTRY_BYTES = 4 * 1024 * 1024 * 1024
DEFAULT_ARCHIVE_DEPTH = 64
DEFAULT_ARCHIVE_RATIO = 1000
DEFAULT_ARCHIVE_ELAPSED_MS = 120_000


class StableIoError(RuntimeError):
    """The native boundary refused or returned a malformed result."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def native_result_digest_value(value: Any) -> str:
    """Mirror the native JSON serializer for closed probe-result digests.

    The C++ JSON serializer escapes forward slashes as ``\/``. JSON parsing
    makes that escape semantically invisible, so Python's normal serializer
    would otherwise hash different bytes for URL and POSIX-style path values.
    This helper is intentionally limited to the native result envelope;
    project document canonicalization continues to use ``digest_value``.
    """

    return hashlib.sha256(canonical_bytes(value).replace(b"/", b"\\/")).hexdigest()


def _positive(value: int, context: str) -> str:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise StableIoError(f"{context} must be a positive integer")
    return str(value)


def _exact_member(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or value.startswith("/")
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise StableIoError("exact archive member path is unsafe")
    return value


@dataclass(frozen=True)
class ArchiveBudgets:
    maximum_archive_bytes: int = DEFAULT_ARCHIVE_BYTES
    maximum_entries: int = DEFAULT_ARCHIVE_ENTRIES
    maximum_total_bytes: int = DEFAULT_ARCHIVE_EXPANDED_BYTES
    maximum_entry_bytes: int = DEFAULT_ARCHIVE_ENTRY_BYTES
    maximum_depth: int = DEFAULT_ARCHIVE_DEPTH
    maximum_ratio: int = DEFAULT_ARCHIVE_RATIO
    maximum_elapsed_ms: int = DEFAULT_ARCHIVE_ELAPSED_MS

    def arguments(self) -> list[str]:
        return [
            _positive(self.maximum_archive_bytes, "maximum archive bytes"),
            _positive(self.maximum_entries, "maximum archive entries"),
            _positive(self.maximum_total_bytes, "maximum expanded bytes"),
            _positive(self.maximum_entry_bytes, "maximum entry bytes"),
            _positive(self.maximum_depth, "maximum archive depth"),
            _positive(self.maximum_ratio, "maximum compression ratio"),
            _positive(self.maximum_elapsed_ms, "maximum elapsed milliseconds"),
        ]


class EvidenceIo:
    """One immutable native evidence-probe binding."""

    def __init__(self, probe: Path):
        absolute = Path(os.path.abspath(probe))
        if not absolute.is_file():
            raise StableIoError(f"native evidence probe is missing: {absolute}")
        self._probe = absolute

    @property
    def probe(self) -> Path:
        return self._probe

    def _run(
        self,
        operation: str,
        arguments: list[str],
        *,
        content: bytes | None = None,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        result = subprocess.run(
            [str(self._probe), *arguments],
            input=content,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
        try:
            value = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise StableIoError(
                f"native evidence probe returned no strict result: {detail}"
            ) from exc
        if (
            not isinstance(value, dict)
            or set(value)
            not in (
                {
                    "schema",
                    "operation",
                    "status",
                    "payload",
                    "record_digest",
                },
                {
                    "schema",
                    "operation",
                    "status",
                    "error",
                    "record_digest",
                },
            )
            or value.get("schema") != RESULT_SCHEMA
            or value.get("operation") != operation
            or value.get("status") not in {"ok", "refused"}
            or LOWERCASE_SHA256.fullmatch(
                str(value.get("record_digest", ""))
            )
            is None
        ):
            raise StableIoError("native evidence result is not a closed record")
        core = dict(value)
        claimed = core.pop("record_digest")
        if native_result_digest_value(core) != claimed:
            raise StableIoError("native evidence result digest is invalid")
        if result.returncode != 0 or value["status"] != "ok":
            error = value.get("error")
            raise StableIoError(
                "native evidence I/O refused: "
                + (
                    f"{error.get('code')}: {error.get('message')} "
                    f"({error.get('path')})"
                    if isinstance(error, dict)
                    else result.stderr.decode("utf-8", errors="replace")
                )
            )
        payload = value.get("payload")
        if not isinstance(payload, dict):
            raise StableIoError("native evidence result payload is not an object")
        return value

    def inspect_file(
        self,
        path: Path,
        *,
        maximum_bytes: int = DEFAULT_FILE_BYTES,
    ) -> dict[str, Any]:
        return self._run(
            "inspect_file",
            ["inspect-file", str(Path(os.path.abspath(path))), _positive(maximum_bytes, "maximum bytes")],
        )

    def hash_file(
        self,
        path: Path,
        *,
        maximum_bytes: int = DEFAULT_FILE_BYTES,
    ) -> dict[str, Any]:
        return self._run(
            "hash_file",
            ["hash-file", str(Path(os.path.abspath(path))), _positive(maximum_bytes, "maximum bytes")],
        )

    def read_json(
        self,
        path: Path,
        *,
        maximum_bytes: int = DEFAULT_JSON_BYTES,
    ) -> dict[str, Any]:
        result = self._run(
            "read_bounded_json",
            [
                "read-bounded-json",
                str(Path(os.path.abspath(path))),
                _positive(maximum_bytes, "maximum JSON bytes"),
            ],
        )
        document = result["payload"].get("document")
        if not isinstance(document, dict):
            raise StableIoError("native stable JSON input is not an object")
        return result

    def read_text(
        self,
        path: Path,
        *,
        maximum_bytes: int = DEFAULT_JSON_BYTES,
    ) -> dict[str, Any]:
        result = self._run(
            "read_bounded_text",
            [
                "read-bounded-text",
                str(Path(os.path.abspath(path))),
                _positive(maximum_bytes, "maximum text bytes"),
            ],
        )
        if not isinstance(result["payload"].get("text"), str):
            raise StableIoError("native stable text input is not text")
        return result

    def inspect_directory(self, path: Path) -> dict[str, Any]:
        return self._run(
            "inspect_directory",
            ["inspect-directory", str(Path(os.path.abspath(path)))],
        )

    def capture_path(
        self,
        path: Path,
        *,
        maximum_entries: int = DEFAULT_MANIFEST_ENTRIES,
        maximum_total_bytes: int = DEFAULT_MANIFEST_BYTES,
        maximum_entry_bytes: int = DEFAULT_MANIFEST_ENTRY_BYTES,
        maximum_depth: int = DEFAULT_MANIFEST_DEPTH,
    ) -> dict[str, Any]:
        return self._run(
            "capture_directory_manifest",
            [
                "capture-directory-manifest",
                str(Path(os.path.abspath(path))),
                _positive(maximum_entries, "maximum manifest entries"),
                _positive(maximum_total_bytes, "maximum manifest bytes"),
                _positive(maximum_entry_bytes, "maximum manifest entry bytes"),
                _positive(maximum_depth, "maximum manifest depth"),
            ],
            timeout_seconds=600,
        )

    def write_new_bytes(
        self,
        path: Path,
        content: bytes,
        *,
        maximum_bytes: int = DEFAULT_JSON_BYTES,
    ) -> dict[str, Any]:
        return self._run(
            "write_new_durable",
            [
                "write-new-durable",
                str(Path(os.path.abspath(path))),
                _positive(maximum_bytes, "maximum output bytes"),
            ],
            content=content,
        )

    def replace_bytes(
        self,
        path: Path,
        content: bytes,
        *,
        maximum_bytes: int = DEFAULT_JSON_BYTES,
    ) -> dict[str, Any]:
        return self._run(
            "replace_durable",
            [
                "replace-durable",
                str(Path(os.path.abspath(path))),
                _positive(maximum_bytes, "maximum output bytes"),
            ],
            content=content,
        )

    def write_new_json(
        self,
        path: Path,
        value: dict[str, Any],
        *,
        maximum_bytes: int = DEFAULT_JSON_BYTES,
    ) -> dict[str, Any]:
        content = (
            json.dumps(
                value,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        return self.write_new_bytes(
            path, content, maximum_bytes=maximum_bytes
        )

    def replace_json(
        self,
        path: Path,
        value: dict[str, Any],
        *,
        maximum_bytes: int = DEFAULT_JSON_BYTES,
    ) -> dict[str, Any]:
        content = (
            json.dumps(
                value,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        return self.replace_bytes(
            path, content, maximum_bytes=maximum_bytes
        )

    def copy_file(
        self,
        source: Path,
        destination: Path,
        *,
        maximum_bytes: int = 512 * 1024 * 1024,
    ) -> dict[str, Any]:
        return self._run(
            "copy_file_durable",
            [
                "copy-file-durable",
                str(Path(os.path.abspath(source))),
                str(Path(os.path.abspath(destination))),
                _positive(maximum_bytes, "maximum copy bytes"),
            ],
        )

    def inspect_zip(
        self,
        path: Path,
        *,
        budgets: ArchiveBudgets = ArchiveBudgets(),
    ) -> dict[str, Any]:
        return self._run(
            "inspect_zip",
            [
                "inspect-zip",
                str(Path(os.path.abspath(path))),
                *budgets.arguments(),
            ],
            timeout_seconds=max(
                180, budgets.maximum_elapsed_ms // 1000 + 30
            ),
        )

    def extract_exact_member(
        self,
        archive: Path,
        member: str,
        destination: Path,
        *,
        budgets: ArchiveBudgets = ArchiveBudgets(),
    ) -> dict[str, Any]:
        return self._run(
            "extract_exact_member",
            [
                "extract-exact-member",
                str(Path(os.path.abspath(archive))),
                _exact_member(member),
                str(Path(os.path.abspath(destination))),
                *budgets.arguments(),
            ],
            timeout_seconds=max(
                180, budgets.maximum_elapsed_ms // 1000 + 30
            ),
        )

    def inspect_exact_member(
        self,
        archive: Path,
        member: str,
        *,
        budgets: ArchiveBudgets = ArchiveBudgets(),
    ) -> dict[str, Any]:
        return self._run(
            "inspect_exact_member",
            [
                "inspect-exact-member",
                str(Path(os.path.abspath(archive))),
                _exact_member(member),
                *budgets.arguments(),
            ],
            timeout_seconds=max(
                180, budgets.maximum_elapsed_ms // 1000 + 30
            ),
        )

    def revalidate_resource_specification(
        self,
        preflight: Path,
        preflight_digest: str,
        resource_set_digest: str,
    ) -> dict[str, Any]:
        for value, context in (
            (preflight_digest, "preflight digest"),
            (resource_set_digest, "resource-set digest"),
        ):
            if LOWERCASE_SHA256.fullmatch(value) is None:
                raise StableIoError(f"{context} is not lowercase SHA-256")
        return self._run(
            "revalidate_resource_specification",
            [
                "revalidate-resource-specification",
                str(Path(os.path.abspath(preflight))),
                preflight_digest,
                resource_set_digest,
            ],
        )


def file_payload_sha256(result: dict[str, Any]) -> str:
    file_value = result.get("payload", {}).get("file")
    digest = (
        file_value.get("content_sha256")
        if isinstance(file_value, dict)
        else None
    )
    if not isinstance(digest, str) or LOWERCASE_SHA256.fullmatch(digest) is None:
        raise StableIoError("native file result has no content digest")
    return digest


def file_payload_size(result: dict[str, Any]) -> int:
    file_value = result.get("payload", {}).get("file")
    size = file_value.get("bytes_read") if isinstance(file_value, dict) else None
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise StableIoError("native file result has no exact byte count")
    return size
