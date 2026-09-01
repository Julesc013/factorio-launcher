# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    problems: list[str] = []
    required = [
        ROOT / "tools" / "development_layout.py",
        ROOT / "tools" / "workspace_hygiene.py",
        ROOT / "docs" / "development" / "workspace-hygiene.md",
        ROOT / "AGENTS.md",
    ]
    for path in required:
        if not path.is_file():
            problems.append(f"missing workspace hygiene surface: {path.relative_to(ROOT)}")

    dev = (ROOT / "tools" / "dev.py").read_text(encoding="utf-8")
    pipeline = (ROOT / "tools" / "package" / "pipeline.py").read_text(encoding="utf-8")
    if "development_layout.default_task_root(ROOT)" not in dev:
        problems.append("tools/dev.py must use the canonical external development layout")
    if "DEFAULT_TASK_ROOT = development_layout.default_task_root(ROOT)" not in pipeline:
        problems.append("package pipeline defaults must use the canonical external task root")
    hygiene = (ROOT / "tools" / "workspace_hygiene.py").read_text(encoding="utf-8")
    if '"managed_location"' not in hygiene or "IN_TREE_OUTPUT_NAMES" not in hygiene:
        problems.append("workspace doctor must audit managed worktrees and in-tree output roots")
    if "command_preset_root" not in hygiene or '"preset-root"' not in hygiene:
        problems.append("workspace hygiene must provision the owned CMake preset root")
    presets = (ROOT / "CMakePresets.json").read_text(encoding="utf-8")
    if "$env{FACMAN_TASK_ROOT}/cmake/${presetName}" not in presets:
        problems.append("CMake presets must keep build output under FACMAN_TASK_ROOT")
    if "${sourceDir}/build" in presets:
        problems.append("CMake presets must not write to an in-checkout build root")
    guidance = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    if "workspace_hygiene.py worktree-add" not in guidance:
        problems.append("agent guidance must require the bounded worktree helper")

    workflows = ROOT / ".github" / "workflows"
    for path in sorted(workflows.glob("*.yml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "uses: actions/upload-artifact@" not in line:
                continue
            window = lines[index + 1 : index + 16]
            retention = [item for item in window if "retention-days:" in item]
            if not retention:
                problems.append(f"{path.relative_to(ROOT)}:{index + 1}: artifact retention is absent")
                continue
            try:
                days = int(retention[0].split(":", 1)[1].strip())
            except ValueError:
                problems.append(f"{path.relative_to(ROOT)}:{index + 1}: artifact retention is not numeric")
                continue
            maximum = 30 if path.name == "release.yml" else 14
            if days > maximum:
                problems.append(
                    f"{path.relative_to(ROOT)}:{index + 1}: retention {days} exceeds {maximum} days"
                )

    if problems:
        for problem in problems:
            print(f"workspace-hygiene-check: {problem}")
        return 1
    print("workspace-hygiene-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
