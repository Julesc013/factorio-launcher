# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "runtime/core/fl_identity.h"
DIRECT_CONSTRUCTION = re.compile(
    r"\b(?:WorkspaceId|TransactionId|InstallId|InstanceId)\s*[({]"
)


def validate() -> list[str]:
    problems: list[str] = []
    header = HEADER.read_text(encoding="utf-8")
    for marker in [
        "static Result<StrongId> parse(",
        "static Result<StrongId> parse_legacy(",
        "explicit StrongId(std::string value)",
        "invalid_identifier",
        "invalid_legacy_identifier",
        "reserved(value)",
    ]:
        if marker not in header:
            problems.append(f"strong ID contract is missing marker: {marker}")
    private = header.find("private:")
    constructor = header.find("explicit StrongId(std::string value)")
    if private < 0 or constructor < private:
        problems.append("StrongId string constructor is not private")

    for root in [ROOT / "runtime", ROOT / "tests"]:
        for path in sorted((*root.rglob("*.cpp"), *root.rglob("*.h"))):
            if path == HEADER:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if DIRECT_CONSTRUCTION.search(text):
                problems.append(f"direct strong ID construction: {path.relative_to(ROOT)}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"strong-id-check: {problem}", file=sys.stderr)
        return 1
    print("strong-id-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
