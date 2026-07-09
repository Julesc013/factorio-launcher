from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import package_manifest_check
from tools.validators.release import _common

TOOL = "release-package-manifest-check"

REQUIRED_INDEX_KEYS = {
    "product_manifest",
    "build_manifest",
    "dependency_lock",
    "install_modes",
    "update_report",
    "offline_bundle",
    "artifact_matrix",
    "profile_catalog",
    "package_manifest",
    "support_matrix",
    "distribution_lanes",
}

REQUIRED_PATHS = {
    "docs/release/RELEASE_MODEL.md",
    "docs/release/DISTRIBUTION_MATRIX.md",
    "docs/release/INSTALL_MODES.md",
    "docs/release/VERSIONING.md",
    "docs/release/UPDATE_MODEL.md",
    "docs/release/PACKAGE_LAYOUT.md",
    "docs/release/OFFLINE_BUNDLES.md",
    "docs/release/SUPPORT_POLICY.md",
    "release/index/product_manifest.v1.toml",
    "release/index/build_manifest.v1.toml",
    "release/index/dependency_lock.v1.toml",
    "release/index/install_modes.v1.toml",
    "release/index/update_report.v1.toml",
    "release/index/offline_bundle.v1.toml",
    "release/index/artifact_matrix.v1.toml",
    "release/profiles/profile_catalog.v1.toml",
}


def main() -> int:
    try:
        problems = validate()
    except (OSError, ValueError) as exc:
        problems = [str(exc)]
    return _common.report(TOOL, problems)


def validate() -> list[str]:
    problems: list[str] = []
    if package_manifest_check.main() != 0:
        problems.append("base package manifest check failed")

    release_index = _common.release_index()
    for key in sorted(REQUIRED_INDEX_KEYS):
        value = str(release_index.get(key, ""))
        if not value:
            problems.append(f"release/index/release_index.v1.toml: missing {key}")
            continue
        if not (_common.ROOT / value).exists():
            problems.append(f"release/index/release_index.v1.toml: missing path for {key}: {value}")

    package_manifest_path = _common.index_path("package_manifest")
    package_manifest = _common.load_toml(package_manifest_path)
    required_paths = set(_common.string_list(package_manifest.get("required_paths")))
    for required in sorted(REQUIRED_PATHS - required_paths):
        problems.append(f"{relative(package_manifest_path)}: required_paths missing {required}")
    return problems


def relative(path: Path) -> str:
    return path.relative_to(_common.ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
