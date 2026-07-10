from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import (
    check_artifact_names,
    check_dependency_lock,
    check_frontend_bundle_contents,
    check_workspace_lock,
    check_install_modes,
    check_no_workspace_in_system_package,
    check_package_manifest,
    check_release_profiles,
)


def main() -> int:
    checks: list[tuple[str, Callable[[], int]]] = [
        ("artifact-names", check_artifact_names.main),
        ("package-manifest", check_package_manifest.main),
        ("dependency-lock", check_dependency_lock.main),
        ("workspace-lock", check_workspace_lock.main),
        ("release-profiles", check_release_profiles.main),
        ("install-modes", check_install_modes.main),
        ("system-workspace", check_no_workspace_in_system_package.main),
        ("frontend-bundle", check_frontend_bundle_contents.main),
    ]
    failed: list[str] = []
    for name, check in checks:
        if check() != 0:
            failed.append(name)
    if failed:
        print(f"release-contract-check: failed checks: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("release-contract-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
