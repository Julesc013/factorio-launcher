# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the fixture-only normalized cross-frontend journey corpus."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover - strict CI installs jsonschema
    jsonschema = None

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/cross-frontend-journeys/corpus.v1.json"
SCHEMA = ROOT / "contracts/schema/presentation/cross_frontend_journey_corpus.v1.schema.json"
REQUIRED_PROJECTIONS = {
    "application_direct",
    "process_rpc",
    "cli_json",
    "same_binary_tui",
    "winforms_typed_model",
}
REQUIRED_SCENARIOS = (
    "existing_install_happy_path",
    "no_installation",
    "foreign_installation_read_only",
    "stale_snapshot",
    "duplicate_action",
    "transport_loss_before_dispatch",
    "transport_loss_after_dispatch",
    "fake_exit_success",
    "fake_exit_nonzero",
    "frontend_close",
    "backend_restart",
    "outcome_unknown",
    "recovery_required",
    "corrupt_last_run",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_corpus(document: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if jsonschema is not None:
        validator = jsonschema.Draft202012Validator(load_json(SCHEMA))
        for error in validator.iter_errors(document):
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            problems.append(f"schema rejection at {location}: {error.message}")
    if document.get("schema") != "facman.cross_frontend_journey_corpus.v1":
        problems.append("wrong corpus schema")
    if document.get("authority_scope") != "fixture_only":
        problems.append("corpus authority must remain fixture_only")
    if document.get("real_factorio_execution") is not False:
        problems.append("real Factorio execution must remain false")
    if document.get("setup_mutation") is not False:
        problems.append("Setup mutation must remain false")
    if set(document.get("required_projections", [])) != REQUIRED_PROJECTIONS:
        problems.append("required projection set changed")

    scenarios = document.get("scenarios", [])
    scenario_ids = tuple(item.get("id") for item in scenarios if isinstance(item, dict))
    if scenario_ids != REQUIRED_SCENARIOS:
        problems.append("scenario order or identity changed")
    by_id = {
        item.get("id"): item for item in scenarios if isinstance(item, dict)
    }
    for scenario_id in REQUIRED_SCENARIOS:
        scenario = by_id.get(scenario_id)
        if not scenario:
            continue
        forbidden = set(scenario.get("forbidden", []))
        if not forbidden:
            problems.append(f"{scenario_id}: stop law is empty")
        if "factorio_process" in forbidden and document.get("real_factorio_execution"):
            problems.append(f"{scenario_id}: real execution contradicts stop law")

    stale = by_id.get("stale_snapshot", {}).get("expected", {})
    if stale.get("operation_outcome") != "refused_before_effects" or stale.get("effects") is not False:
        problems.append("stale snapshot must refuse before effects")
    duplicate = by_id.get("duplicate_action", {}).get("expected", {})
    if duplicate.get("byte_identical_replay") is not True or duplicate.get("dispatch_count") != 1:
        problems.append("duplicate action must replay one accepted dispatch")
    before = by_id.get("transport_loss_before_dispatch", {}).get("expected", {})
    if before.get("effects_may_have_occurred") is not False:
        problems.append("pre-dispatch transport loss cannot claim effects")
    after = by_id.get("transport_loss_after_dispatch", {}).get("expected", {})
    if after.get("operation_outcome") != "outcome_unknown" or after.get("recovery_required") is not True:
        problems.append("post-dispatch transport loss must require unknown/recovery")
    closed = by_id.get("frontend_close", {}).get("expected", {})
    if closed.get("ordinary_cancellation") is not False:
        problems.append("frontend close cannot become ordinary cancellation")
    corrupt = by_id.get("corrupt_last_run", {}).get("expected", {})
    if corrupt.get("last_run_authority") != "record_corrupt_or_incompatible":
        problems.append("corrupt Last Run must remain explicitly incompatible")
    return problems


def validate_projection_sources() -> list[str]:
    problems: list[str] = []
    sources = {
        "application_direct": (
            ROOT / "runtime/factorio/application/presentation_service.cpp",
            ("PresentationService::query", "PresentationService::action"),
        ),
        "process_rpc": (
            ROOT / "apps/cli/command_dispatch.cpp",
            ("facman.transport_request.v2", "facman.transport_response.v2"),
        ),
        "cli_json": (
            ROOT / "apps/cli/command_dispatch.cpp",
            ('call(options, "presentation.query"', 'options, "presentation.action"'),
        ),
        "same_binary_tui": (
            ROOT / "apps/tui/tui_product_shell.cpp",
            ("client.negotiate", 'invocation.command = "presentation.action"'),
        ),
        "winforms_typed_model": (
            ROOT / "apps/gui/windows/winforms/PresentationModels.cs",
            ("BackendPresentationSnapshot", "SemanticActionReceipt"),
        ),
    }
    for projection, (path, anchors) in sources.items():
        text = path.read_text(encoding="utf-8")
        for anchor in anchors:
            if anchor not in text:
                problems.append(f"{projection}: missing source anchor {anchor}")
    winforms = (ROOT / "apps/gui/windows/winforms/C1LivePresentationStore.cs").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        '"workspace.status"',
        '"installs.scan"',
        '"instance.list"',
        '"instances.inspect"',
        '"instances.readiness"',
        '"workspace.recovery.inspect"',
        '"run.execute"',
    ):
        if forbidden in winforms:
            problems.append(f"winforms_typed_model: direct policy route remains {forbidden}")
    for required in (
        "HasUncertainAction",
        "InspectUncertainActionAsync",
        'payload["idempotency_key"] = "winforms-" + identity.RequestId',
        'if (action.Effectful) payload["confirmation"] = "explicit"',
        'result.OperationOutcome == "outcome_unknown"',
        "semantic_action_uncertain_inspection_required",
    ):
        if required not in winforms:
            problems.append(
                f"winforms_typed_model: uncertain-action guard is missing {required}"
            )
    if 'payload["confirmation"] = action.Effectful ? "explicit" : "none"' in winforms:
        problems.append("winforms_typed_model: non-effectful action sends invalid confirmation")
    for required in (
        '"settings_support", "workspace.initialize"',
        '"settings_support", "doctor.run"',
        "item.InstallationLayout",
        "item.IsolationEligibility",
    ):
        if required not in winforms:
            problems.append(f"winforms_typed_model: onboarding projection is missing {required}")
    tui_model = (ROOT / "apps/tui/tui_product_model.cpp").read_text(encoding="utf-8")
    for required in (
        'root.find("workspace_health")',
        '"installation_layout"',
        '"strict_isolation_eligibility"',
    ):
        if required not in tui_model:
            problems.append(f"same_binary_tui: onboarding projection is missing {required}")
    return problems


def _invoke(arguments: list[str], *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    executable = os.environ.get("FACMAN_CLI_EXE")
    if not executable:
        raise RuntimeError("FACMAN_CLI_EXE is required for executable conformance")
    return subprocess.run(
        [executable, *arguments],
        cwd=ROOT,
        input=stdin,
        text=True,
        encoding="utf-8",
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )


def observe_read_projection_parity() -> list[str]:
    problems: list[str] = []
    executable = os.environ.get("FACMAN_CLI_EXE")
    if not executable:
        return problems
    with tempfile.TemporaryDirectory(prefix="facman-cross-frontend-query-") as temporary:
        workspace = Path(temporary) / "uncreated workspace"
        payload = {"scope": "launch_deck"}
        cli = _invoke([
            "--workspace", str(workspace), "presentation", "query", "launch_deck", "--json",
        ])
        rpc_request = {
            "schema": "facman.transport_request.v2",
            "protocol_version": 2,
            "request_id": "cross-frontend-query-request",
            "operation_id": "cross-frontend-query-operation",
            "attempt_id": "cross-frontend-query-attempt",
            "workspace": str(workspace),
            "command": "presentation.query",
            "dry_run": True,
            "payload": payload,
        }
        rpc = _invoke(["rpc", "--stdio"], stdin=json.dumps(rpc_request))
        tui_direct = _invoke([
            "tui", "--workspace", str(workspace), "--command", "presentation.query",
            "--payload", json.dumps(payload), "--json",
        ])
        tui_process = _invoke([
            "tui", "--workspace", str(workspace), "--command", "presentation.query",
            "--payload", json.dumps(payload), "--transport", "process", "--cli-path",
            executable, "--json",
        ])
        observations: dict[str, Any] = {}
        for name, result, envelope in (
            ("cli_json", cli, True),
            ("process_rpc", rpc, True),
            ("same_binary_tui_direct", tui_direct, False),
            ("same_binary_tui_process", tui_process, False),
        ):
            if result.returncode != 0 or result.stderr:
                problems.append(
                    f"{name}: query failed rc={result.returncode} stderr={result.stderr.strip()}"
                )
                continue
            value = json.loads(result.stdout)
            observations[name] = value["payload"] if envelope else value
        if observations and any(value != next(iter(observations.values())) for value in observations.values()):
            problems.append("normalized read snapshot differs across CLI/RPC/TUI transports")
        if workspace.exists():
            problems.append("read-only cross-frontend query created the workspace")
    return problems


def _write_installation_fixture(root: Path) -> None:
    if sys.platform == "win32":
        executable = root / "bin/x64/factorio.exe"
    elif sys.platform == "darwin":
        executable = root / "Factorio.app/Contents/MacOS/factorio"
    else:
        executable = root / "bin/x64/factorio"
    executable.parent.mkdir(parents=True)
    executable.write_text("synthetic fixture; never executed\n", encoding="utf-8")
    (root / "data/base").mkdir(parents=True)
    (root / "data/base/info.json").write_text(
        '{"name":"base","version":"2.0.77"}\n', encoding="utf-8"
    )
    (root / "config-path.cfg").write_text(
        "use-system-read-write-data-directories=false\n", encoding="utf-8"
    )


def _query_observations(
    workspace: Path, scope: str, selected_instance: str = ""
) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    executable = os.environ["FACMAN_CLI_EXE"]
    payload: dict[str, Any] = {"scope": scope}
    cli_arguments = [
        "--workspace", str(workspace), "presentation", "query", scope,
    ]
    if selected_instance:
        payload["selected_instance_id"] = selected_instance
        cli_arguments.extend(["--instance", selected_instance])
    cli_arguments.append("--json")
    rpc_request = {
        "schema": "facman.transport_request.v2",
        "protocol_version": 2,
        "request_id": f"cross-frontend-{scope}-request",
        "operation_id": f"cross-frontend-{scope}-operation",
        "attempt_id": f"cross-frontend-{scope}-attempt",
        "workspace": str(workspace),
        "command": "presentation.query",
        "dry_run": True,
        "payload": payload,
    }
    commands = (
        ("cli_json", _invoke(cli_arguments), True),
        ("process_rpc", _invoke(["rpc", "--stdio"], stdin=json.dumps(rpc_request)), True),
        (
            "same_binary_tui_direct",
            _invoke([
                "tui", "--workspace", str(workspace), "--command", "presentation.query",
                "--payload", json.dumps(payload), "--json",
            ]),
            False,
        ),
        (
            "same_binary_tui_process",
            _invoke([
                "tui", "--workspace", str(workspace), "--command", "presentation.query",
                "--payload", json.dumps(payload), "--transport", "process", "--cli-path",
                executable, "--json",
            ]),
            False,
        ),
    )
    observations: dict[str, Any] = {}
    for name, result, envelope in commands:
        if result.returncode != 0 or result.stderr:
            problems.append(
                f"{name}: {scope} failed rc={result.returncode} stderr={result.stderr.strip()}"
            )
            continue
        value = json.loads(result.stdout)
        observations[name] = value["payload"] if envelope else value
    if observations and any(value != next(iter(observations.values())) for value in observations.values()):
        problems.append(f"normalized {scope} snapshot differs across CLI/RPC/TUI transports")
    return observations, problems


def _action_observations(
    workspace: Path,
    revision: str,
    selected_instance: str,
) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    executable = os.environ["FACMAN_CLI_EXE"]
    payload = {
        "scope": "launch_deck",
        "action_id": "readiness.refresh",
        "expected_snapshot_revision": revision,
        "request_id": "cross-frontend-readiness-request",
        "idempotency_key": "cross-frontend-readiness-key",
        "durable_operation_id": "cross-frontend-readiness-operation",
        "attempt_id": "cross-frontend-readiness-attempt",
        "selected_instance_id": selected_instance,
    }
    cli = _invoke([
        "--workspace", str(workspace), "presentation", "action",
        "readiness.refresh", "--scope", "launch_deck",
        "--expected-revision", revision,
        "--request-id", payload["request_id"],
        "--idempotency-key", payload["idempotency_key"],
        "--operation-id", payload["durable_operation_id"],
        "--attempt-id", payload["attempt_id"],
        "--instance", selected_instance, "--json",
    ])
    rpc_request = {
        "schema": "facman.transport_request.v2",
        "protocol_version": 2,
        "request_id": payload["request_id"],
        "operation_id": payload["durable_operation_id"],
        "attempt_id": payload["attempt_id"],
        "workspace": str(workspace),
        "command": "presentation.action",
        "dry_run": True,
        "payload": payload,
    }
    commands = (
        ("cli_json", cli, True),
        ("process_rpc", _invoke(["rpc", "--stdio"], stdin=json.dumps(rpc_request)), True),
        (
            "same_binary_tui_direct",
            _invoke([
                "tui", "--workspace", str(workspace), "--command",
                "presentation.action", "--payload", json.dumps(payload), "--json",
            ]),
            False,
        ),
        (
            "same_binary_tui_process",
            _invoke([
                "tui", "--workspace", str(workspace), "--command",
                "presentation.action", "--payload", json.dumps(payload),
                "--transport", "process", "--cli-path", executable, "--json",
            ]),
            False,
        ),
    )
    observations: dict[str, Any] = {}
    for name, result, envelope in commands:
        if result.returncode != 0 or result.stderr:
            problems.append(
                f"{name}: readiness action failed rc={result.returncode} "
                f"stderr={result.stderr.strip()} stdout={result.stdout.strip()}"
            )
            continue
        value = json.loads(result.stdout)
        observations[name] = value["payload"] if envelope else value
    if observations and any(
        value != next(iter(observations.values())) for value in observations.values()
    ):
        problems.append("normalized readiness action differs across CLI/RPC/TUI transports")
    return observations, problems


def observe_existing_install_projection_parity() -> list[str]:
    problems: list[str] = []
    if not os.environ.get("FACMAN_CLI_EXE"):
        return problems
    with tempfile.TemporaryDirectory(prefix="facman-cross-frontend-journey-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        installation = root / "fixture installation"
        _write_installation_fixture(installation)
        fixture_digest = hashlib.sha256(
            next(path for path in installation.rglob("factorio.exe" if sys.platform == "win32" else "factorio")).read_bytes()
        ).hexdigest()

        installs, query_problems = _query_observations(workspace, "installations")
        problems.extend(query_problems)
        if not installs:
            return problems
        revision = next(iter(installs.values()))["revision"]
        register = _invoke([
            "--workspace", str(workspace), "presentation", "action",
            "installation.register_read_only", "--scope", "installations",
            "--expected-revision", revision,
            "--request-id", "cross-frontend-register-request",
            "--idempotency-key", "cross-frontend-register-key",
            "--operation-id", "cross-frontend-register-operation",
            "--attempt-id", "cross-frontend-register-attempt",
            "--confirmation", "explicit",
            "--installation", "fixture-read-only",
            "--installation-path", str(installation),
            "--json",
        ])
        if register.returncode != 0 or register.stderr:
            problems.append(
                f"registration action failed rc={register.returncode} stderr={register.stderr.strip()}"
            )
            return problems

        registered_installs, query_problems = _query_observations(
            workspace, "installations"
        )
        problems.extend(query_problems)
        if registered_installs:
            identity = next(iter(registered_installs.values()))["page"]["items"][0]
            expected_identity = {
                "installation_id": "fixture-read-only",
                "ownership": "imported",
                "root": str(installation.resolve()),
                "installation_layout": "portable_archive",
                "data_routing": "install_local",
                "strict_isolation_eligibility": "candidate",
            }
            for key, value in expected_identity.items():
                if identity.get(key) != value:
                    problems.append(
                        f"registered installation {key} projection was {identity.get(key)!r}, expected {value!r}"
                    )

        instances, query_problems = _query_observations(workspace, "instances")
        problems.extend(query_problems)
        if not instances:
            return problems
        revision = next(iter(instances.values()))["revision"]
        create_arguments = [
            "--workspace", str(workspace), "presentation", "action",
            "instance.create_isolated", "--scope", "instances",
            "--expected-revision", revision,
            "--request-id", "cross-frontend-create-request",
            "--idempotency-key", "cross-frontend-create-key",
            "--operation-id", "cross-frontend-create-operation",
            "--attempt-id", "cross-frontend-create-attempt",
            "--confirmation", "explicit",
            "--installation", "fixture-read-only",
            "--new-instance", "fixture-isolated",
            "--display-name", "Fixture Isolated",
            "--json",
        ]
        created = _invoke(create_arguments)
        replayed = _invoke(create_arguments)
        if created.returncode != 0 or created.stderr:
            problems.append(
                f"create action failed rc={created.returncode} stderr={created.stderr.strip()}"
            )
            return problems
        if (replayed.returncode, replayed.stdout, replayed.stderr) != (
            created.returncode, created.stdout, created.stderr
        ):
            problems.append("cross-process duplicate action did not replay byte-identically")
        changed_create = list(create_arguments)
        changed_create[changed_create.index("cross-frontend-create-request")] = (
            "cross-frontend-create-request-changed"
        )
        conflicted = _invoke(changed_create)
        if conflicted.returncode == 0 or "idempotency_key_conflict" not in conflicted.stdout:
            problems.append("changed request reused an idempotency key without conflict")

        stale = _invoke([
            "--workspace", str(workspace), "presentation", "action",
            "readiness.refresh", "--scope", "instances",
            "--expected-revision", revision,
            "--request-id", "cross-frontend-stale-request",
            "--idempotency-key", "cross-frontend-stale-key",
            "--operation-id", "cross-frontend-stale-operation",
            "--attempt-id", "cross-frontend-stale-attempt",
            "--instance", "fixture-isolated", "--json",
        ])
        if stale.returncode == 0 or "stale_snapshot_revision" not in stale.stdout:
            problems.append("stale snapshot did not refuse before effects")

        launch, query_problems = _query_observations(
            workspace, "launch_deck", "fixture-isolated"
        )
        problems.extend(query_problems)
        if launch:
            selected = next(iter(launch.values()))["selected_context"]
            if selected.get("instance_id") != "fixture-isolated" or selected.get(
                "installation_id"
            ) != "fixture-read-only":
                problems.append("selected instance projection differs from backend authority")
            action_observations, action_problems = _action_observations(
                workspace,
                next(iter(launch.values()))["revision"],
                "fixture-isolated",
            )
            problems.extend(action_problems)
            if action_observations and any(
                value.get("outcome") != "completed"
                for value in action_observations.values()
            ):
                problems.append("readiness action did not complete across every projection")
        executable_name = "factorio.exe" if sys.platform == "win32" else "factorio"
        after_digest = hashlib.sha256(next(installation.rglob(executable_name)).read_bytes()).hexdigest()
        if after_digest != fixture_digest:
            problems.append("read-only fixture installation was mutated")
    return problems


def observe_onboarding_projection_parity() -> list[str]:
    problems: list[str] = []
    if not os.environ.get("FACMAN_CLI_EXE"):
        return problems
    with tempfile.TemporaryDirectory(prefix="facman-cross-frontend-onboarding-") as temporary:
        workspace = Path(temporary) / "uncreated workspace"
        observations, query_problems = _query_observations(
            workspace, "settings_support"
        )
        problems.extend(query_problems)
        if observations:
            snapshot = next(iter(observations.values()))
            health = snapshot.get("workspace_health", {})
            if health.get("status") != "uninitialized" or health.get("initialized") is not False:
                problems.append("onboarding workspace health is not truthfully uninitialized")
            actions = {
                action.get("action_id")
                for action in snapshot.get("available_semantic_actions", [])
            }
            if not {"workspace.initialize", "doctor.run"}.issubset(actions):
                problems.append("onboarding semantic actions are missing from ordinary projections")
        if workspace.exists():
            problems.append("onboarding inspection created the workspace")
    return problems


def main() -> int:
    document = load_json(CORPUS)
    problems = validate_corpus(document)
    problems.extend(validate_projection_sources())
    problems.extend(observe_read_projection_parity())
    problems.extend(observe_onboarding_projection_parity())
    problems.extend(observe_existing_install_projection_parity())
    if problems:
        for problem in problems:
            print(f"cross-frontend-journey-conformance: {problem}", file=sys.stderr)
        return 1
    executable = " + executable query/journey parity" if os.environ.get("FACMAN_CLI_EXE") else ""
    print(
        "cross-frontend-journey-conformance: ok "
        f"({len(REQUIRED_SCENARIOS)} scenarios, {len(REQUIRED_PROJECTIONS)} projections{executable})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
