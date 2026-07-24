# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import project_state, structure_policy_check

ROOT_POLICY = ROOT / ".aide" / "policies" / "facman-root-authority.yaml"
PROFILE = ROOT / ".aide" / "profile.yaml"
CLAIM_LEDGER = ROOT / "docs" / "quality" / "safety_claim_ledger.md"
DISCOVERY_README = ROOT / "runtime" / "factorio" / "discovery" / "README.md"


def main() -> int:
    problems: list[str] = []
    problems.extend(validate_root_authority_text(ROOT_POLICY.read_text(encoding="utf-8")))
    problems.extend(validate_profile_text(PROFILE.read_text(encoding="utf-8")))
    problems.extend(project_state.validate())
    problems.extend(validate_claim_ledger_text(CLAIM_LEDGER.read_text(encoding="utf-8")))
    problems.extend(validate_discovery_text(DISCOVERY_README.read_text(encoding="utf-8")))
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


def yaml_scalar(text: str, key: str, indent: int) -> str:
    prefix = " " * indent
    match = re.search(rf"(?m)^{prefix}{re.escape(key)}:\s*([^\n#]+?)\s*$", text)
    return match.group(1).strip() if match else ""


def yaml_list(text: str, key: str, indent: int) -> list[str]:
    lines = text.splitlines()
    marker = " " * indent + key + ":"
    for index, line in enumerate(lines):
        if line != marker:
            continue
        values = []
        item_prefix = " " * (indent + 2) + "- "
        for candidate in lines[index + 1 :]:
            if candidate.startswith(item_prefix):
                values.append(candidate[len(item_prefix) :].strip())
                continue
            if candidate.strip() and len(candidate) - len(candidate.lstrip()) <= indent:
                break
        return values
    return []


def validate_profile_text(text: str) -> list[str]:
    problems: list[str] = []
    phase = yaml_scalar(text, "phase", 2)
    allowed_phases = {
        "product-convergence",
        "execution-foundation",
        "real-play-gates",
        "multi-version-install-lifecycle",
        "instance-spec-and-readiness",
        "operation-permit",
        "hermetic-standalone-play-policy",
        "hermetic-standalone-play-policy-closeout",
        "hermetic-standalone-play-candidate",
        "hermetic-standalone-play-verdict",
        "hermetic-standalone-play-observer-start-repair",
        "hermetic-standalone-play-verdict-repeat",
        "gate4c-privilege-separation-repair",
    }
    if phase not in allowed_phases:
        problems.append(f"profile phase is {phase!r}, expected a current product or real-play gate phase")
    quarantined = set(yaml_list(text, "quarantined_capabilities", 2))
    for capability in {
        "launch.execute.instance_isolated",
        "launch.execute.hermetic",
        "process.execute",
        "network.mod_portal.read",
    } - quarantined:
        problems.append(f"profile quarantine is missing {capability}")
    evidence = {
        "workspace_lock": "release/index/workspace_lock.v1.toml",
        "threat_model": "docs/architecture/threat_model.md",
        "claim_ledger": "docs/quality/safety_claim_ledger.md",
        "proof_gates": "docs/quality/safety_proof_gates.md",
    }
    for key, expected in evidence.items():
        value = yaml_scalar(text, key, 4)
        if value != expected:
            problems.append(f"profile {key} is {value!r}, expected {expected!r}")
        elif not (ROOT / value).is_file():
            problems.append(f"profile evidence authority does not exist: {value}")
    for stale in (
        "pre-code-structure-governance",
        "apps/python_cli",
        "C-compatible stable ABI",
        "r3.6-product-readiness-complete",
    ):
        if stale in text:
            problems.append(f"profile retains stale target state {stale!r}")
    return problems


def parse_claim_rows(text: str) -> dict[str, dict[str, str]]:
    claims: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("| ---") or "| Claim |" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 4:
            claims[cells[0]] = {"level": cells[1], "proof": cells[2], "limitation": cells[3]}
    return claims


def validate_claim_ledger_text(text: str) -> list[str]:
    problems: list[str] = []
    claims = parse_claim_rows(text)
    abi_claim = "Experimental FLB ABI and installed SDK have a correctness floor"
    required = {
        "Command registry introspection matches dispatch",
        "Run preview uses the authoritative route",
        abi_claim,
        "Windows, Linux, and macOS install discovery is read-only",
    }
    for claim in sorted(required - claims.keys()):
        problems.append(f"claim ledger is missing structured row {claim!r}")
    abi = claims.get(abi_claim, {})
    if abi and "stable compatibility" not in abi.get("limitation", ""):
        problems.append("experimental ABI claim must retain the stable-compatibility limitation")
    if "Public C ABI is stable" in claims:
        problems.append("claim ledger promotes the experimental ABI to stable")
    return problems


def validate_discovery_text(text: str) -> list[str]:
    problems: list[str] = []
    stale = "Real Steam VDF, Windows registry, macOS Spotlight, and Linux package-manager"
    if stale in text:
        problems.append("discovery documentation defers the implemented Windows provider")
    if "Windows read-only discovery is not implemented" in text:
        problems.append("discovery documentation denies the implemented Windows provider")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
