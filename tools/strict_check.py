from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import command_contract_check, gui_surface_check, package_check, release_readiness_check, schema_validate, security_policy_check, structure_policy_check


def main() -> int:
    checks: list[tuple[str, Callable[[], int]]] = [
        ("structure", structure_policy_check.main),
        ("schema", schema_validate.main),
        ("security", security_policy_check.main),
        ("package", package_check.main),
        ("gui-surface", gui_surface_check.main),
        ("command-contract", command_contract_check.main),
        ("release-readiness", release_readiness_check.main),
    ]
    failed: list[str] = []
    for name, check in checks:
        if check() != 0:
            failed.append(name)
    if failed:
        print(f"strict-check: failed checks: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("strict-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
