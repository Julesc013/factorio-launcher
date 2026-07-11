from __future__ import annotations

import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_identical(first: Path, second: Path) -> str:
    first_digest, second_digest = sha256(first), sha256(second)
    if first_digest != second_digest:
        raise ValueError(f"reproducibility failure: {first_digest} != {second_digest}")
    return first_digest
