# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import gzip
import os
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def write(root: Path, destination: Path, package_type: str, source_timestamp: str) -> Path:
    epoch = int(datetime.fromisoformat(source_timestamp.replace("Z", "+00:00")).timestamp())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    if package_type == "tarball":
        with destination.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
                        relative = path.relative_to(root).as_posix()
                        info = archive.gettarinfo(str(path), arcname=relative)
                        info.uid = info.gid = 0
                        info.uname = info.gname = "root"
                        info.mtime = epoch
                        info.mode = 0o755 if path.is_dir() or os.access(path, os.X_OK) else 0o644
                        with (path.open("rb") if path.is_file() else _null_context()) as handle:
                            archive.addfile(info, handle if path.is_file() else None)
    else:
        stamp = datetime.fromtimestamp(max(epoch, 315532800), tz=timezone.utc)
        date_time = (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
                info = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time)
                info.create_system = 3
                info.external_attr = (0o755 if os.access(path, os.X_OK) else 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return destination


class _null_context:
    def __enter__(self):
        return None

    def __exit__(self, *_args):
        return False
