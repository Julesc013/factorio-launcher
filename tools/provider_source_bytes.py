# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Observe physical provider inputs against HEAD without invoking Git clean filters."""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path

from tools import provider_canary_process

MAX_FILES = 10000
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
TEXT_SUFFIXES = {".c", ".cmake", ".cpp", ".h", ".in", ".json", ".md", ".py", ".toml",
                 ".txt", ".yaml", ".yml"}
TEXT_NAMES = {".gitattributes", ".gitignore", "CMakeLists.txt", "LICENSE"}


def git_bytes(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    command = ["git", "-c", "safe.directory=" + root.as_posix(), "-c", "core.fsmonitor=false", *args]
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1")
    if os.environ.get("FACMAN_CANARY_OWNED_JOB") == "1":
        result = provider_canary_process.require(provider_canary_process.command(
            command, cwd=root, environment=environment, timeout=30,
            input_bytes=input_bytes or b"", output_limit=8 * 1024 * 1024))
    else:
        # Portable observation remains supported. This finite individual wait does
        # not qualify descendant containment or autonomous POSIX scheduling.
        result = subprocess.run(command, cwd=root, input=input_bytes,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            check=False, timeout=30)
    if result.returncode:
        raise ValueError("physical provider Git observation failed: " +
                         result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def reject_indirection(path: Path) -> None:
    for current in (path, *path.parents):
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("physical provider source has symlink or reparse indirection")


def blob_id(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def observe(root: Path, revision: str = "HEAD") -> dict:
    reject_indirection(root)
    entries = []
    for record in git_bytes(root, "ls-tree", "-r", "-z", revision).split(b"\0"):
        if not record:
            continue
        header, raw_name = record.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split()
        name = raw_name.decode("utf-8")
        parts = name.split("/")
        if (mode not in {"100644", "100755"} or kind != "blob" or not parts or
                name.startswith("/") or "\\" in name or ":" in name or
                any(ord(char) < 32 or ord(char) == 127 for char in name) or
                any(part in {"", ".", "..", ".git"} for part in parts)):
            raise ValueError("physical provider source has unsupported path or nonregular entry")
        entries.append((name, oid))
    if not entries or len(entries) > MAX_FILES:
        raise ValueError("physical provider source entry budget exceeded")
    names = b"".join(name.encode("utf-8") + b"\0" for name, _ in entries)
    attrs = git_bytes(root, "check-attr", "-z", "--stdin", "filter", "working-tree-encoding",
                      input_bytes=names).split(b"\0")
    if attrs[-1] != b"" or len(attrs[:-1]) != len(entries) * 6:
        raise ValueError("physical provider source attribute observation is incomplete")
    for index in range(0, len(attrs) - 1, 3):
        if attrs[index + 2] not in {b"unspecified", b"unset"}:
            raise ValueError("physical provider source custom filter or encoding is unsupported")
    files = []
    total = 0
    for name, expected in entries:
        path = root / name
        reject_indirection(path)
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("physical provider source is not a regular file")
        with path.open("rb") as source:
            raw = source.read(MAX_FILE_BYTES + 1)
        total += len(raw)
        if len(raw) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError("physical provider source byte budget exceeded")
        normalization = "raw"
        if blob_id(raw) != expected:
            if (path.suffix not in TEXT_SUFFIXES and path.name not in TEXT_NAMES) or b"\0" in raw:
                raise ValueError("physical provider bytes differ from reviewed Git blob")
            raw.decode("utf-8")
            if blob_id(raw.replace(b"\r\n", b"\n")) != expected:
                raise ValueError("physical provider bytes differ from reviewed Git blob")
            normalization = "utf8_crlf_to_lf_v1"
        files.append({"path": name, "git_blob": expected, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                      "bytes": len(raw), "normalization": normalization})
    return {"policy": "regular_source_utf8_lf_or_crlf_v1", "files": files,
            "total_bytes": total, "atomic_build_lease": False}
