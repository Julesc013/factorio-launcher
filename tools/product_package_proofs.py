# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Run both product lifecycle proof families against one supplied package."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--profile", choices=("windows_product_x64", "linux_product_x64",
                                              "macos_product_x64"), required=True)
    parser.add_argument("--package-mode", choices=("portable", "installed_stage"), required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args(argv)
    platform = args.profile.split("_", 1)[0]
    spelling = "installed" if args.package_mode == "installed_stage" else "portable"
    failures = []
    for helper, suffix in (("workspace_lifecycle_package_proof.py", "workspace-lifecycle"),
                           ("resource_package_proof.py", "resource-package")):
        receipt = args.evidence_root / f"{platform}-{spelling}-{suffix}.v1.json"
        command = [sys.executable, str(ROOT / "tools" / helper),
                   "--executable", str(args.executable), "--profile", args.profile,
                   "--package-mode", args.package_mode, "--evidence", str(receipt)]
        try:
            result = subprocess.run(command, check=False, timeout=900)
            if result.returncode:
                failures.append(helper)
        except (OSError, subprocess.SubprocessError) as error:
            print(f"{helper}: {error}", file=sys.stderr)
            failures.append(helper)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
