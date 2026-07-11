# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.package_runtime.test_built_package_artifacts import WindowsPortableCliPackageProofTests


def main() -> int:
    if os.name != "nt":
        print("required-package-proof: Windows host is required", file=sys.stderr)
        return 1
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if dirty.returncode != 0 or dirty.stdout.strip():
        print("required-package-proof: source checkout must be clean", file=sys.stderr)
        return 1
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WindowsPortableCliPackageProofTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.skipped:
        for test, reason in result.skipped:
            print(f"required-package-proof: forbidden skip: {test}: {reason}", file=sys.stderr)
        return 1
    if not result.wasSuccessful():
        return 1
    print(f"required-package-proof: ok ({result.testsRun} tests, zero skips)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
