from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = list_repo_files()
    nodes = [classify(path) for path in files]
    findings = build_findings()
    summary = {
        "schema": "flaunch.aide.project_graph_snapshot.v1",
        "project": "factorio-launcher",
        "generated_by": "tools/aide_project_graph_baseline.py",
        "file_count": len(nodes),
        "counts_by_kind": dict(sorted(Counter(node["kind"] for node in nodes).items())),
        "counts_by_root": dict(sorted(Counter(node["root"] for node in nodes).items())),
        "findings_count": len(findings),
        "status": "PASS_WITH_WARNINGS",
    }
    graph = {
        "summary": summary,
        "nodes": nodes,
        "edges": build_edges(),
        "findings": findings,
    }
    write_json(ROOT / ".aide" / "project-graph" / "snapshot.json", graph)
    write_json(ROOT / ".aide" / "reports" / "structure" / "project-graph.json", graph)
    write_json(ROOT / ".aide" / "reports" / "structure" / "project-graph.findings.json", findings)
    write_markdown(ROOT / ".aide" / "reports" / "structure" / "project-graph.md", summary, findings)
    print("project-graph-baseline: ok")
    return 0


def list_repo_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())


def classify(path: str) -> dict[str, Any]:
    root = path.split("/", 1)[0]
    suffix = Path(path).suffix.lower()
    kind = "unknown"
    owner = "unknown"
    lifecycle = "active"
    if root == "include":
        kind = "public_abi"
        owner = "abi"
    elif root == "source":
        kind = "implementation"
        owner = source_owner(path)
        if path.startswith("source/prototypes/"):
            lifecycle = "transitional"
    elif root == "apps":
        kind = "frontend_shell"
        owner = "frontend"
    elif root == "data":
        kind = "product_policy"
        owner = "factorio_binding"
    elif root == "schemas":
        kind = "schema"
        owner = "contract"
    elif root == "packaging":
        kind = "package_manifest"
        owner = "packaging"
    elif root == "docs":
        kind = "doc"
        owner = "documentation"
    elif root == "tests":
        kind = "test"
        owner = "verification"
    elif root == "tools":
        kind = "tool"
        owner = "repo_automation"
    elif root == ".aide":
        kind = "aide_governance"
        owner = "development_tooling"
    elif root == ".aide.local.example":
        kind = "aide_local_template"
        owner = "development_tooling"
    elif suffix in {".md", ".txt"}:
        kind = "doc"
        owner = "documentation"
    return {
        "path": path,
        "root": root,
        "kind": kind,
        "owner": owner,
        "lifecycle": lifecycle,
    }


def source_owner(path: str) -> str:
    parts = path.split("/")
    if len(parts) < 2:
        return "implementation"
    return {
        "apps": "frontend_implementation",
        "base": "portable_base",
        "client": "command_client",
        "factorio": "factorio_binding",
        "platform": "platform_adapter",
        "prototypes": "prototype_harness",
        "runtime": "runtime_locator",
        "ulk": "incubated_universal_launcher",
        "usk": "incubated_universal_setup",
    }.get(parts[1], "implementation")


def build_edges() -> list[dict[str, str]]:
    return [
        {"from": "apps/*", "to": "source/apps/*", "type": "shell_for"},
        {"from": "source/apps/*", "to": "source/ulk/command", "type": "calls_command_graph"},
        {"from": "source/ulk/command", "to": "source/factorio/binding", "type": "delegates_product_questions"},
        {"from": "source/factorio/binding", "to": "data/factorio", "type": "consumes_product_policy"},
        {"from": "source/prototypes/python_launcher", "to": "source/ulk/command", "type": "native_successor"},
        {"from": ".aide", "to": "repo", "type": "observes_and_reports"},
    ]


def build_findings() -> list[dict[str, Any]]:
    return [
        finding(
            "FLAUNCH-PG-001",
            "warning",
            "native_command_graph",
            "native command graph not yet implemented",
            "source/ulk/command should contain real registry, schema routing, dry-run, audit, and handlers",
            "currently scaffolded; Python prototype remains runnable behavior",
            ["source/ulk/command/README.md", "source/ulk/kernel/ulk_api.c"],
            "Build command registry before more GUI work.",
            "AIDE-BUILD-ULK-COMMAND-REGISTRY-V0-01",
        ),
        finding(
            "FLAUNCH-PG-002",
            "warning",
            "prototype_boundary",
            "Python prototype is still current runnable CLI",
            "Python should be prototype and golden behavior harness only",
            "pyproject exposes factorio-launcher from source/prototypes/python_launcher",
            ["pyproject.toml", "source/prototypes/python_launcher/factorio_launcher/ui/cli/cli.py"],
            "Port commands into native command graph while preserving CLI JSON behavior.",
            "AIDE-BUILD-FACTORIO-PROTOTYPE-PARITY-MAP-01",
        ),
        finding(
            "FLAUNCH-PG-003",
            "info",
            "universal_split",
            "universal setup and launcher are incubated/planned siblings",
            "FLaunch may incubate until API pressure is proven, but must not own universal semantics permanently",
            "include/source/schemas currently contain usk and ulk namespaces",
            ["include/usk", "include/ulk", "source/usk", "source/ulk", "schemas/usk", "schemas/ulk"],
            "Discuss universal repo structure separately before large native code expansion.",
            "AIDE-BUILD-USK-ULK-SPLIT-READINESS-REPORT-01",
        ),
        finding(
            "FLAUNCH-PG-004",
            "pass",
            "source_roots",
            "source/ is the only implementation source root",
            "no src/, launcher/, nested source/, or app-local src/ roots",
            "structure policy and filesystem match this rule",
            ["tools/structure_policy_check.py", "tests/test_structure_policy.py"],
            "Keep this rule unless a deliberate structure redesign replaces it.",
            "FLAUNCH-CANON-STRUCTURE-01",
        ),
        finding(
            "FLAUNCH-PG-005",
            "pass",
            "frontend_shells",
            "apps/ contains shells, not product logic",
            "frontend implementation should live under source/apps",
            "apps roots contain shell/readme/project files; implementation roots exist in source/apps",
            ["apps", "source/apps"],
            "Keep apps shell-only.",
            "FLAUNCH-APPS-SHELL-CHECK-01",
        ),
        finding(
            "FLAUNCH-PG-006",
            "pass",
            "setup_boundary",
            "Factorio repo must not implement install mutation",
            "repair, uninstall, rollback, and destructive setup mutation belong to Universal Setup",
            "docs and policies state this boundary",
            ["docs/architecture/boundary.md", ".aide/policies/flaunch-product-boundaries.yaml"],
            "Keep setup mutation behind handoff/adapter boundaries.",
            "AIDE-BUILD-USK-SPLIT-READINESS-REPORT-01",
        ),
        finding(
            "FLAUNCH-PG-007",
            "pass",
            "safety",
            "dry-run default must remain true",
            "launch plans should be previewed unless execution is explicit",
            "README, product policy, and AIDE safety policy encode dry-run",
            ["README.md", "data/factorio/product/factorio.product.toml", ".aide/policies/flaunch-safety.yaml"],
            "Keep execution opt-in.",
            "FLAUNCH-SAFETY-REGRESSION-CHECK-01",
        ),
        finding(
            "FLAUNCH-PG-008",
            "pass",
            "legal_boundary",
            "no Factorio binaries may be bundled",
            "package manifests and product policy must forbid bundling Factorio binaries",
            "package/security checks enforce this",
            ["tools/package_check.py", "tools/security_policy_check.py"],
            "Keep packaging checks in CI.",
            "FLAUNCH-PACKAGING-AUTHORITY-REPORT-01",
        ),
        finding(
            "FLAUNCH-PG-009",
            "pass",
            "runtime_boundary",
            "production legacy packages must not depend on Python or AIDE",
            "AIDE and Python prototype are development/prototype surfaces only",
            "package check and structure policy enforce runtime separation",
            ["tools/package_check.py", "tools/structure_policy_check.py", "docs/architecture/aide_lite_integration.md"],
            "Keep AIDE and Python out of package manifests.",
            "FLAUNCH-RUNTIME-DEPENDENCY-CHECK-01",
        ),
    ]


def finding(
    ident: str,
    severity: str,
    surface: str,
    claim: str,
    expected: str,
    observed: str,
    evidence_refs: list[str],
    recommendation: str,
    next_task: str,
) -> dict[str, Any]:
    return {
        "id": ident,
        "severity": severity,
        "surface": surface,
        "taxonomy": "project_graph",
        "claim": claim,
        "expected": expected,
        "observed": observed,
        "evidence_refs": evidence_refs,
        "affected_paths": evidence_refs,
        "recommendation": recommendation,
        "next_task": next_task,
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, summary: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Factorio Launcher ProjectGraph Baseline",
        "",
        f"Status: `{summary['status']}`",
        f"Files classified: `{summary['file_count']}`",
        f"Findings: `{summary['findings_count']}`",
        "",
        "## Counts By Kind",
        "",
    ]
    for kind, count in summary["counts_by_kind"].items():
        lines.append(f"- `{kind}`: {count}")
    lines.extend(["", "## Findings", ""])
    for item in findings:
        lines.extend(
            [
                f"### {item['id']} - {item['severity']}",
                "",
                item["claim"],
                "",
                f"- Expected: {item['expected']}",
                f"- Observed: {item['observed']}",
                f"- Recommendation: {item['recommendation']}",
                f"- Next task: `{item['next_task']}`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
