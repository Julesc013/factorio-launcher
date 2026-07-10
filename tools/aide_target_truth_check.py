from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import structure_policy_check

ROOT_POLICY = ROOT / ".aide" / "policies" / "flaunch-root-authority.yaml"
PROFILE = ROOT / ".aide" / "profile.yaml"
PROJECT_STATE = ROOT / ".aide" / "memory" / "project-state.md"


def main() -> int:
    problems: list[str] = []
    problems.extend(validate_root_authority_text(ROOT_POLICY.read_text(encoding="utf-8")))
    problems.extend(validate_profile_text(PROFILE.read_text(encoding="utf-8")))
    problems.extend(validate_project_state_text(PROJECT_STATE.read_text(encoding="utf-8")))
    if problems:
        for problem in problems:
            print(f"aide-target-truth-check: {problem}", file=sys.stderr)
        return 1
    print("aide-target-truth-check: ok")
    return 0


def parse_root_authorities(text: str) -> tuple[dict[str, bool], list[str]]:
    roots: dict[str, bool] = {}
    problems: list[str] = []
    in_roots = False
    current: str | None = None
    for line_number, line in enumerate(text.splitlines(), 1):
        if line == "roots:":
            in_roots = True
            continue
        if not in_roots:
            continue
        if line and not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            current = line.strip()[:-1]
            if current in roots:
                problems.append(f"duplicate root authority entry {current!r} on line {line_number}")
            continue
        if current is not None and line.startswith("    canonical:"):
            value = line.split(":", 1)[1].strip()
            if value not in {"true", "false"}:
                problems.append(f"root {current!r} has a non-boolean canonical value")
            else:
                roots[current] = value == "true"
    return roots, problems


def validate_root_authority_text(text: str) -> list[str]:
    roots, problems = parse_root_authorities(text)
    expected = structure_policy_check.AIDE_ROOT_AUTHORITY
    for retired in sorted(structure_policy_check.RETIRED_ROOTS & roots.keys()):
        problems.append(f"retired root is declared authoritative: {retired}/")
    for root, canonical in sorted(expected.items()):
        if root not in roots:
            problems.append(f"missing root authority entry: {root}/")
        elif roots[root] is not canonical:
            problems.append(
                f"root authority mismatch for {root}/: expected canonical={str(canonical).lower()}"
            )
    for root in sorted(roots.keys() - expected.keys()):
        problems.append(f"unexpected root authority entry: {root}/")
    return problems


def validate_profile_text(text: str) -> list[str]:
    problems: list[str] = []
    required = [
        "phase: r3-post-gate4-truth-hardening",
        "authoritative_command_slice:",
        "install_refs.scan",
        "launch_plan.build",
        "quarantined_capabilities:",
        "run.execute",
        "diagnostics.export",
        "workspace_lock: release/index/workspace_lock.v1.toml",
        "threat_model: docs/architecture/threat_model.md",
        "claim_ledger: docs/quality/safety_claim_ledger.md",
        "proof_gates: docs/quality/safety_proof_gates.md",
    ]
    for anchor in required:
        if anchor not in text:
            problems.append(f"profile is missing current-truth anchor {anchor!r}")
    for stale in ["pre-code-structure-governance", "apps/python_cli"]:
        if stale in text:
            problems.append(f"profile retains stale target state {stale!r}")
    evidence_paths = [
        "release/index/workspace_lock.v1.toml",
        "docs/architecture/threat_model.md",
        "docs/quality/safety_claim_ledger.md",
        "docs/quality/safety_proof_gates.md",
    ]
    for relative in evidence_paths:
        if not (ROOT / relative).is_file():
            problems.append(f"profile evidence authority does not exist: {relative}")
    return problems


def validate_project_state_text(text: str) -> list[str]:
    problems: list[str] = []
    required = [
        "R3 post-Gate-4 truth hardening",
        "authoritative Universal Launcher route",
        "Windows x64 static-first package proof",
        "release/index/workspace_lock.v1.toml",
    ]
    for anchor in required:
        if anchor not in text:
            problems.append(f"project state is missing current-truth anchor {anchor!r}")
    for stale in [
        "pre-code structure governance",
        "apps/python_cli/` is the current runnable prototype",
        "Native command graph implementation is still the major gap",
    ]:
        if stale in text:
            problems.append(f"project state retains stale claim {stale!r}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
