# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Compare executed backend identity with independent package metadata and bytes."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import tomllib


def require_backend_identity(root: Path, executable: Path, product: dict[str, object]) -> dict[str, object]:
    with (root / "manifest/package.v1.toml").open("rb") as stream:
        manifest = tomllib.load(stream)
    build_info = json.loads((root / "manifest/build_info.v1.json").read_bytes())
    backend = product.get("backend_identity")
    if not isinstance(backend, dict):
        raise ValueError("product.inspect has no compiled backend identity")
    build, package = backend.get("build"), backend.get("package")
    if not isinstance(build, dict) or not isinstance(package, dict):
        raise ValueError("product.inspect has no compiled build/package identity")

    def equal(actual: object, expected: object, label: str) -> None:
        if actual != expected or type(actual) is not type(expected):
            raise ValueError(f"compiled backend identity mismatch: {label}")

    for key in ("source_revision", "source_dirty", "universal_launcher_revision", "universal_setup_revision"):
        equal(build.get(key), manifest[key], "build." + key)
        equal(package.get(key), manifest[key], "package." + key)
    equal(build.get("build_identity"), build_info["build_identity"], "build_identity")
    for key in ("verified", "build_matches_package", "contract_set_matches_build"):
        equal(package.get(key), True, "package." + key)
    equal(package.get("mode"), "packaged", "package.mode")
    equal(package.get("integrity"), "sha256_consistent", "package.integrity")
    equal(package.get("profile_id"), manifest["profile_id"], "package.profile_id")
    for key, path in (("manifest_sha256", root / "manifest/package.v1.toml"),
                      ("closure_sha256", root / "manifest/hashes.sha256"),
                      ("backend_sha256", executable)):
        equal(package.get(key), hashlib.sha256(path.read_bytes()).hexdigest(), "package." + key)
    equal(package.get("backend_relative_path"), executable.relative_to(root).as_posix(),
          "package.backend_relative_path")
    digest = backend.get("contract_set_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("compiled backend contract digest is invalid")
    equal(package.get("contract_set_sha256"), digest, "package.contract_set_sha256")
    # Independent manifest record count, not a self-reported success flag.
    rows = (root / "manifest/hashes.sha256").read_text(encoding="utf-8").splitlines()
    equal(package.get("files_verified"), len(rows), "package.files_verified")
    return {"compiled_source_revision": build["source_revision"],
            "compiled_source_dirty": build["source_dirty"], "contract_set_sha256": digest,
            "backend_sha256": package["backend_sha256"], "package_verified": True}
