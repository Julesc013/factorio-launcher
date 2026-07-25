# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import windows_instance_isolated_play_policy_check

OUTPUT = (
    ROOT
    / "contracts/generated-index/"
    "windows_instance_isolated_play_policy.v1.canonical.json"
)


def main() -> int:
    policy = windows_instance_isolated_play_policy_check.load_policy()
    OUTPUT.write_bytes(
        windows_instance_isolated_play_policy_check.canonical_policy_bytes(policy)
        + b"\n"
    )
    print(OUTPUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
