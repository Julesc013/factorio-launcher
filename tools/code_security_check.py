# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/codeql.yml"


def validate() -> list[str]:
    if not WORKFLOW.is_file():
        return ["CodeQL workflow is missing"]
    text = WORKFLOW.read_text(encoding="utf-8")
    problems: list[str] = []
    for anchor in [
        "name: code-security",
        "security-events: write",
        "github/codeql-action/init@v4",
        "github/codeql-action/analyze@v4",
        "languages: c-cpp",
        "languages: python",
        "languages: csharp",
        "build-mode: manual",
        "build-mode: none",
        "cmake --build build/codeql",
        "verify_dependency_revisions.py --align",
        "FacMan.WinForms.csproj",
    ]:
        if anchor not in text:
            problems.append(f"CodeQL workflow is missing: {anchor}")
    security_policy = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
    if "github/codeql-action" in security_policy:
        problems.append("security-policy workflow must remain separate from CodeQL evidence")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"code-security-check: {problem}", file=sys.stderr)
        return 1
    print("code-security-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
