# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the canonical FacMan plan and generate its operational views."""

from __future__ import annotations

import argparse
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "release" / "index" / "plan.v1.toml"
OUTPUTS = {
    ROOT / "todo.md": "dashboard",
    ROOT / "docs" / "roadmap" / "current.md": "roadmap",
}

WORK_STATUSES = {"planned", "ready", "active", "blocked", "complete", "cancelled"}
EPIC_STATUSES = {"planned", "active", "blocked", "complete", "cancelled"}
RELEASE_STATUSES = {"planned", "active", "complete", "cancelled"}
GATE_STATUSES = {"planned", "active", "blocked", "complete", "cancelled"}
GATE_SCOPES = {"authority_only"}
DECISION_STATUSES = {"open", "accepted", "rejected", "deferred", "superseded"}
PRIORITIES = {"P0", "P1", "P2", "P3", "P4"}
SIZES = {"S", "M", "L", "XL"}


def load_plan(path: Path = PLAN) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _records(plan: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = plan.get(key, [])
    return value if isinstance(value, list) else []


def _path_error(root: Path, value: str, label: str) -> str | None:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return f"{label} must be a repository-relative path: {value}"
    if not (root / candidate).is_file():
        return f"{label} does not exist: {value}"
    return None


def _find_dependency_cycle(workunits: dict[str, dict[str, Any]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(workunit_id: str) -> list[str] | None:
        if workunit_id in visiting:
            index = stack.index(workunit_id)
            return stack[index:] + [workunit_id]
        if workunit_id in visited:
            return None
        visiting.add(workunit_id)
        stack.append(workunit_id)
        for dependency in workunits[workunit_id].get("depends_on", []):
            if dependency in workunits:
                cycle = visit(dependency)
                if cycle:
                    return cycle
        stack.pop()
        visiting.remove(workunit_id)
        visited.add(workunit_id)
        return None

    for workunit_id in workunits:
        cycle = visit(workunit_id)
        if cycle:
            return cycle
    return None


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    """Return deterministic validation errors for the canonical plan."""

    errors: list[str] = []
    if plan.get("schema") != "facman.plan.v1":
        errors.append("schema must be facman.plan.v1")

    for field in (
        "document_id",
        "generated_by",
        "last_reviewed",
        "active_release",
        "north_star",
        "archive",
        "operating_model",
        "interface_design_system",
        "c1_release_contract",
    ):
        if not plan.get(field):
            errors.append(f"top-level field is required: {field}")

    for field in ("wip_limit", "ready_limit", "large_migration_limit", "next_workunit_limit"):
        value = plan.get(field)
        if not isinstance(value, int) or value < 1:
            errors.append(f"{field} must be a positive integer")

    for field in (
        "archive",
        "operating_model",
        "interface_design_system",
        "c1_release_contract",
    ):
        value = plan.get(field)
        if isinstance(value, str):
            error = _path_error(root, value, field)
            if error:
                errors.append(error)

    categories = ("release", "gate", "epic", "workunit", "decision", "risk", "later")
    seen_ids: dict[str, str] = {}
    for category in categories:
        for record in _records(plan, category):
            record_id = record.get("id")
            if not isinstance(record_id, str) or not record_id:
                errors.append(f"{category} record is missing an id")
                continue
            if record_id in seen_ids:
                errors.append(
                    f"duplicate id {record_id}: {seen_ids[record_id]} and {category}"
                )
            seen_ids[record_id] = category

    releases = {
        record["id"]: record
        for record in _records(plan, "release")
        if isinstance(record.get("id"), str)
    }
    epics = {
        record["id"]: record
        for record in _records(plan, "epic")
        if isinstance(record.get("id"), str)
    }
    workunits = {
        record["id"]: record
        for record in _records(plan, "workunit")
        if isinstance(record.get("id"), str)
    }
    decisions = {
        record["id"]: record
        for record in _records(plan, "decision")
        if isinstance(record.get("id"), str)
    }
    later_ids = {
        record["id"]
        for record in _records(plan, "later")
        if isinstance(record.get("id"), str)
    }

    active_release = plan.get("active_release")
    if active_release not in releases:
        errors.append(f"active_release is unknown: {active_release}")
    active_releases = [
        record["id"]
        for record in releases.values()
        if record.get("status") == "active"
    ]
    if active_releases != [active_release]:
        errors.append(
            "exactly active_release must have active status; found "
            + ", ".join(active_releases or ["none"])
        )

    for release in releases.values():
        release_id = release["id"]
        if release.get("status") not in RELEASE_STATUSES:
            errors.append(f"{release_id} has invalid release status")
        for field in ("title", "owner", "objective", "platform_cut", "frontend_cut"):
            if not release.get(field):
                errors.append(f"{release_id} is missing {field}")
        for field in ("cut_line", "non_goals", "exit", "journeys", "claim_seed"):
            value = release.get(field)
            if not isinstance(value, list) or not value:
                errors.append(f"{release_id} requires a non-empty {field}")

    for gate in _records(plan, "gate"):
        gate_id = gate.get("id", "<unknown-gate>")
        if gate.get("status") not in GATE_STATUSES:
            errors.append(f"{gate_id} has invalid gate status")
        for field in ("title", "owner", "summary", "exit"):
            if not gate.get(field):
                errors.append(f"{gate_id} is missing {field}")
        scope = gate.get("gate_scope")
        if scope not in GATE_SCOPES:
            errors.append(f"{gate_id} has invalid gate_scope {scope!r}")
        blocks = gate.get("blocks")
        non_blocking = gate.get("non_blocking_work")
        if not isinstance(blocks, list) or not blocks:
            errors.append(f"{gate_id} requires a non-empty blocks list")
            blocks = []
        if not isinstance(non_blocking, list) or not non_blocking:
            errors.append(f"{gate_id} requires a non-empty non_blocking_work list")
            non_blocking = []
        if len(blocks) != len(set(blocks)):
            errors.append(f"{gate_id} blocks contains duplicate identifiers")
        if len(non_blocking) != len(set(non_blocking)):
            errors.append(f"{gate_id} non_blocking_work contains duplicate identifiers")
        overlap = sorted(set(blocks) & set(non_blocking))
        if overlap:
            errors.append(
                f"{gate_id} cannot both block and permit: " + ", ".join(overlap)
            )

    for epic in epics.values():
        epic_id = epic["id"]
        if epic.get("release") not in releases:
            errors.append(f"{epic_id} references unknown release {epic.get('release')}")
        if epic.get("status") not in EPIC_STATUSES:
            errors.append(f"{epic_id} has invalid epic status")
        for field in ("title", "owner", "outcome"):
            if not epic.get(field):
                errors.append(f"{epic_id} is missing {field}")
        if not epic.get("repos"):
            errors.append(f"{epic_id} has no repository ownership")
        if not epic.get("exit"):
            errors.append(f"{epic_id} has no exit criteria")

    for decision in decisions.values():
        decision_id = decision["id"]
        if decision.get("status") not in DECISION_STATUSES:
            errors.append(f"{decision_id} has invalid decision status")
        for field in (
            "title",
            "owner",
            "question",
            "default",
            "de_scope",
            "due_workunit",
            "resolution_workunit",
        ):
            if not decision.get(field):
                errors.append(f"{decision_id} is missing {field}")
        for field in ("due_workunit", "resolution_workunit"):
            target = decision.get(field)
            if target not in workunits and target not in later_ids:
                errors.append(f"{decision_id} references unknown {field} {target}")

    for workunit in workunits.values():
        workunit_id = workunit["id"]
        epic_id = workunit.get("epic")
        epic = epics.get(epic_id)
        if epic is None:
            errors.append(f"{workunit_id} references unknown epic {epic_id}")
        status = workunit.get("status")
        if status not in WORK_STATUSES:
            errors.append(f"{workunit_id} has invalid work-unit status")
        if workunit.get("priority") not in PRIORITIES:
            errors.append(f"{workunit_id} has invalid priority")
        size = workunit.get("size")
        if size not in SIZES:
            errors.append(f"{workunit_id} has invalid size")
        if status in {"ready", "active"} and size == "XL":
            errors.append(f"{workunit_id} is XL and cannot be {status}")
        for field in ("title", "owner", "outcome"):
            if not workunit.get(field):
                errors.append(f"{workunit_id} is missing {field}")
        if not workunit.get("repos"):
            errors.append(f"{workunit_id} has no repository ownership")
        if not workunit.get("acceptance"):
            errors.append(f"{workunit_id} has no acceptance criteria")
        branch = workunit.get("branch")
        base_revision = workunit.get("base_revision")
        if branch is not None or base_revision is not None:
            if not isinstance(branch, str) or not branch.startswith("task/"):
                errors.append(f"{workunit_id} branch must match task/*")
            if (
                not isinstance(base_revision, str)
                or len(base_revision) != 40
                or any(character not in "0123456789abcdef" for character in base_revision)
            ):
                errors.append(
                    f"{workunit_id} base_revision must be an exact lowercase Git revision"
                )

        if epic and status in {"ready", "active"} and epic.get("release") != active_release:
            errors.append(f"{workunit_id} is {status} outside the active release")

        dependencies = workunit.get("depends_on", [])
        blockers = workunit.get("decision_blockers", [])
        if not isinstance(dependencies, list):
            errors.append(f"{workunit_id} depends_on must be a list")
            dependencies = []
        if not isinstance(blockers, list):
            errors.append(f"{workunit_id} decision_blockers must be a list")
            blockers = []

        for dependency in dependencies:
            if dependency in later_ids:
                errors.append(f"{workunit_id} depends on Later item {dependency}")
            elif dependency not in workunits:
                errors.append(f"{workunit_id} depends on unknown work unit {dependency}")
        if status == "ready":
            incomplete = [
                dependency
                for dependency in dependencies
                if workunits.get(dependency, {}).get("status") != "complete"
            ]
            if incomplete:
                errors.append(
                    f"{workunit_id} is ready with incomplete dependencies: "
                    + ", ".join(incomplete)
                )
        for blocker in blockers:
            if blocker not in decisions:
                errors.append(f"{workunit_id} has unknown decision blocker {blocker}")
            elif status == "ready" and decisions[blocker].get("status") == "open":
                errors.append(f"{workunit_id} is ready with open decision {blocker}")

        if status == "complete":
            evidence = workunit.get("evidence", [])
            if not evidence:
                errors.append(f"{workunit_id} is complete without evidence")
            for evidence_path in evidence:
                if not isinstance(evidence_path, str):
                    errors.append(f"{workunit_id} has a non-string evidence path")
                    continue
                error = _path_error(root, evidence_path, f"{workunit_id} evidence")
                if error:
                    errors.append(error)

    cycle = _find_dependency_cycle(workunits)
    if cycle:
        errors.append("work-unit dependency cycle: " + " -> ".join(cycle))

    active_work = [
        workunit["id"]
        for workunit in workunits.values()
        if workunit.get("status") == "active"
    ]
    active_gates = [
        gate["id"]
        for gate in _records(plan, "gate")
        if gate.get("status") == "active"
    ]
    if len(active_work) + len(active_gates) > plan.get("wip_limit", 0):
        errors.append(
            "WIP limit exceeded: "
            f"{len(active_work) + len(active_gates)} > {plan.get('wip_limit')}"
        )
    ready_work = [
        workunit["id"]
        for workunit in workunits.values()
        if workunit.get("status") == "ready"
    ]
    if len(ready_work) > plan.get("ready_limit", 0):
        errors.append(
            f"ready limit exceeded: {len(ready_work)} > {plan.get('ready_limit')}"
        )
    pending_work = [
        workunit["id"]
        for workunit in workunits.values()
        if workunit.get("status") not in {"complete", "cancelled"}
    ]
    next_limit = plan.get("next_workunit_limit", 0)
    pending_limit = next_limit + len(active_work)
    if len(pending_work) > pending_limit:
        errors.append(
            f"near-term work-unit limit exceeded: {len(pending_work)} > {pending_limit}"
        )

    active_large_migrations = [
        workunit["id"]
        for workunit in workunits.values()
        if workunit.get("status") == "active"
        and workunit.get("migration_class") == "large"
    ]
    if len(active_large_migrations) > plan.get("large_migration_limit", 0):
        errors.append(
            "large-migration limit exceeded: "
            f"{len(active_large_migrations)} > {plan.get('large_migration_limit')}"
        )

    for risk in _records(plan, "risk"):
        risk_id = risk.get("id", "<unknown-risk>")
        for field in ("owner", "severity", "summary", "mitigation"):
            if not risk.get(field):
                errors.append(f"{risk_id} is missing {field}")

    for later in _records(plan, "later"):
        later_id = later.get("id", "<unknown-later>")
        for field in ("summary", "rationale", "trigger"):
            if not later.get(field):
                errors.append(f"{later_id} is missing {field}")

    return errors


def _bullet_lines(values: Iterable[str], prefix: str = "- ") -> list[str]:
    return [f"{prefix}{value}" for value in values]


def _work_marker(status: str) -> str:
    return "x" if status == "complete" else " "


def render_dashboard(plan: dict[str, Any]) -> str:
    releases = {item["id"]: item for item in _records(plan, "release")}
    release = releases[plan["active_release"]]
    workunits = _records(plan, "workunit")
    active = [item for item in workunits if item["status"] == "active"]
    ready = [item for item in workunits if item["status"] == "ready"]
    planned = [item for item in workunits if item["status"] == "planned"]
    completed = [item for item in workunits if item["status"] == "complete"]
    gates = [
        item for item in _records(plan, "gate") if item["status"] in {"active", "blocked"}
    ]

    lines = [
        "---",
        "document_id: FACMAN-GENERATED-EXECUTION-DASHBOARD",
        'schema_version: "1.0"',
        "status: generated",
        f"canonical_source: {PLAN.relative_to(ROOT).as_posix()}",
        f"active_release: {plan['active_release']}",
        f"last_reviewed: {plan['last_reviewed']}",
        "---",
        "",
        "# FacMan execution dashboard",
        "",
        "> Generated by `tools/generate_plan_views.py`. Do not edit this file.",
        "> Change `release/index/plan.v1.toml`, regenerate, and review the diff.",
        "> This dashboard is planning state, not implementation or mutation authority.",
        "",
        "## Control plane",
        "",
        f"- Canonical plan: `release/index/plan.v1.toml`",
        f"- Operating model: `{plan['operating_model']}`",
        f"- Interface design system: `{plan['interface_design_system']}`",
        f"- C1 release contract: `{plan['c1_release_contract']}`",
        f"- Active release: `{release['id']}` — {release['title']}",
        f"- WIP: {len(active) + len([g for g in gates if g['status'] == 'active'])}/{plan['wip_limit']} including external gates",
        f"- Ready: {len(ready)}/{plan['ready_limit']}",
        f"- Near-term work units: {len([w for w in workunits if w['status'] not in {'complete', 'cancelled'}])}/{plan['next_workunit_limit']}",
        "",
        "## North star",
        "",
        plan["north_star"],
        "",
        f"## Active release — {release['id']}: {release['title']}",
        "",
        release["objective"],
        "",
        f"- Platform cut: {release['platform_cut']}",
        f"- Frontend cut: {release['frontend_cut']}",
        f"- Release-blocking journey: `{release['journeys'][0]}`",
        "",
        "### Product cut-line",
        "",
    ]
    lines.extend(_bullet_lines(release["cut_line"], "- [ ] "))
    lines.extend(["", "### Explicit non-goals", ""])
    lines.extend(_bullet_lines(release["non_goals"]))
    lines.extend(["", "## Current external gate", ""])
    if gates:
        for gate in gates:
            lines.extend(
                [
                    f"### {gate['id']} — {gate['status'].upper()}",
                    "",
                    gate["summary"],
                    "",
                    f"- Owner: `{gate['owner']}`; scope: `{gate['gate_scope']}`",
                    f"- External task observed: `{gate.get('external_ref', 'none')}`; source: `{gate.get('source', 'none')}`",
                    "- Blocks only:",
                    "  " + ", ".join(f"`{item}`" for item in gate["blocks"]),
                    f"- Non-blocking product work: {len(gate['non_blocking_work'])} named items may continue independently.",
                    f"- Exit: {gate['exit']}",
                    "",
                ]
            )
    else:
        lines.extend(["_No active or blocked external gate._", ""])

    lines.extend(["## Active work units", ""])
    if active:
        for item in active:
            lines.extend(
                [
                    f"- [{_work_marker(item['status'])}] `{item['id']}` [{item['priority']}/{item['size']}] — {item['title']}",
                    f"  - Owner: `{item['owner']}`; repositories: {', '.join(f'`{repo}`' for repo in item['repos'])}",
                    f"  - Outcome: {item['outcome']}",
                ]
            )
    else:
        lines.append(
            "_No internal work unit is active. An authority-only external gate "
            "does not block ready product work._"
        )

    lines.extend(["", "## Ready queue", ""])
    if ready:
        for index, item in enumerate(ready, 1):
            lines.extend(
                [
                    f"{index}. `{item['id']}` [{item['priority']}/{item['size']}] — {item['title']}",
                    f"   - Owner: `{item['owner']}`; outcome: {item['outcome']}",
                ]
            )
    else:
        lines.append("_No work unit satisfies the Definition of Ready._")

    lines.extend(["", "## Critical path after the current unit", ""])
    for item in ready + planned:
        dependencies = ", ".join(f"`{value}`" for value in item["depends_on"]) or "none"
        lines.append(
            f"- [{_work_marker(item['status'])}] `{item['id']}` — {item['status']}; depends on {dependencies}"
        )

    lines.extend(["", "## Blocking decisions", ""])
    for decision in _records(plan, "decision"):
        lines.extend(
            [
                f"### {decision['id']} — {decision['status'].upper()}",
                "",
                decision["question"],
                "",
                f"- Owner: `{decision['owner']}`",
                f"- Due by: `{decision['due_workunit']}`; resolution work: `{decision['resolution_workunit']}`",
                f"- Default: {decision['default']}",
                f"- De-scope: {decision['de_scope']}",
                "",
            ]
        )

    lines.extend(["## Current risks", ""])
    for risk in _records(plan, "risk"):
        lines.extend(
            [
                f"- **{risk['id']} ({risk['severity']})** — {risk['summary']}",
                f"  - Owner: `{risk['owner']}`; mitigation: {risk['mitigation']}",
            ]
        )

    lines.extend(["", "## Release exit", ""])
    lines.extend(_bullet_lines(release["exit"], "- [ ] "))
    lines.extend(["", "## Completed planning evidence", ""])
    if completed:
        for item in completed:
            lines.append(f"- [x] `{item['id']}` — {item['title']}")
    else:
        lines.append("_No canonical work unit is complete yet._")

    lines.extend(
        [
            "",
            "## Validation commands",
            "",
            "```powershell",
            "py -3 tools/generate_plan_views.py --check",
            "py -3 -m unittest tests.test_plan_views",
            "```",
            "",
            "## Rules of engagement",
            "",
            "- Do not hand-edit this generated view.",
            "- Do not start a planned item as if it were ready.",
            "- Do not exceed WIP by relabeling work as research or documentation.",
            "- An authority-only gate blocks only its named authorities; it is not a global product mutex.",
            "- Do not infer stable contracts from fixture or single-consumer evidence.",
            "- Do not add C1 scope without explicit scope substitution.",
            "- Do not treat archived checklist items as authorized work.",
            "",
        ]
    )
    return "\n".join(lines)


def render_roadmap(plan: dict[str, Any]) -> str:
    release = next(
        item
        for item in _records(plan, "release")
        if item["id"] == plan["active_release"]
    )
    epics = _records(plan, "epic")
    workunits = _records(plan, "workunit")
    lines = [
        "# Current FacMan roadmap",
        "",
        "> Generated by `tools/generate_plan_views.py` from",
        "> `release/index/plan.v1.toml`. Do not edit this file.",
        "",
        f"Last reviewed: {plan['last_reviewed']}",
        "",
        f"## {release['id']} — {release['title']} ({release['status']})",
        "",
        release["objective"],
        "",
        "### Capability boundary",
        "",
        f"- Platform: {release['platform_cut']}",
        f"- Frontend: {release['frontend_cut']}",
        "",
        "Included:",
        "",
    ]
    lines.extend(_bullet_lines(release["cut_line"]))
    lines.extend(["", "Excluded:", ""])
    lines.extend(_bullet_lines(release["non_goals"]))
    lines.extend(["", "### Epics and work units", ""])
    for epic in epics:
        lines.extend(
            [
                f"#### {epic['id']} — {epic['title']} ({epic['status']})",
                "",
                epic["outcome"],
                "",
                f"Owner: `{epic['owner']}`. Repositories: "
                + ", ".join(f"`{repo}`" for repo in epic["repos"])
                + ".",
                "",
            ]
        )
        epic_work = [item for item in workunits if item["epic"] == epic["id"]]
        if not epic_work:
            lines.extend(["_No near-term work unit._", ""])
            continue
        for item in epic_work:
            dependencies = ", ".join(f"`{dep}`" for dep in item["depends_on"]) or "none"
            lines.extend(
                [
                    f"- [{_work_marker(item['status'])}] **{item['id']}** — {item['title']}",
                    f"  - State: `{item['status']}`; priority/size: `{item['priority']}/{item['size']}`",
                    f"  - Owner: `{item['owner']}`; dependencies: {dependencies}",
                    f"  - Outcome: {item['outcome']}",
                ]
            )
        lines.append("")

    lines.extend(["### Decisions", ""])
    for decision in _records(plan, "decision"):
        lines.extend(
            [
                f"- **{decision['id']}** (`{decision['status']}`): {decision['question']}",
                f"  - Default: {decision['default']}",
                f"  - De-scope: {decision['de_scope']}",
            ]
        )

    lines.extend(["", "### Later horizon", ""])
    for item in _records(plan, "later"):
        lines.extend(
            [
                f"- **{item['id']}** — {item['summary']}",
                f"  - Revisit: {item['trigger']}",
            ]
        )

    lines.extend(
        [
            "",
            "### Release exit",
            "",
        ]
    )
    lines.extend(_bullet_lines(release["exit"], "- [ ] "))
    lines.extend(
        [
            "",
            "For planning doctrine, capability levels, journeys, claims, contract",
            "maturity, migration, evidence, WIP, and validation rules, see",
            "`docs/roadmap/planning-operating-model.md`.",
            "",
            "For native shell profiles, HIG mappings, OEM+ appearance, theming,",
            "accessibility, performance, and frontend authority rules, see",
            "`docs/product/interface_design_system.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def render_outputs(plan: dict[str, Any]) -> dict[Path, str]:
    return {
        ROOT / "todo.md": render_dashboard(plan),
        ROOT / "docs" / "roadmap" / "current.md": render_roadmap(plan),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the plan and fail if generated views are stale",
    )
    args = parser.parse_args(argv)

    plan = load_plan()
    errors = validate_plan(plan)
    if errors:
        for error in errors:
            print(f"plan-views: error: {error}")
        return 1

    outputs = render_outputs(plan)
    if args.check:
        stale = [
            path
            for path, expected in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            for path in stale:
                print(f"plan-views: generated file is stale: {path.relative_to(ROOT)}")
            return 1
        print("plan-views: canonical plan and generated views are current")
        return 0

    for path, output in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8", newline="\n")
        print(f"plan-views: wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
