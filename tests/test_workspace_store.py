# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from native_cli import invoke, invoke_machine

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


def validate_facman_schema(name: str, value: dict[str, object]) -> None:
    schema_root = ROOT / "contracts" / "schema" / "facman"
    resources: list[tuple[str, Resource[dict[str, object]]]] = []
    for path in schema_root.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schema_id = schema.get("$id")
        if isinstance(schema_id, str):
            resources.append((schema_id, Resource.from_contents(schema)))
    target = json.loads((schema_root / name).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        target, registry=Registry().with_resources(resources)
    ).validate(value)


def snapshot(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


def apply_args(workspace: str, plan: dict[str, object], suffix: str) -> list[str]:
    return [
        "--workspace", workspace, "workspace", "migration", "apply",
        "--expected-revision", str(plan["expected_workspace_revision"]),
        "--expected-root", str(plan["expected_root_identity"]),
        "--plan-digest", str(plan["plan_digest"]),
        "--confirmation", "explicit",
        "--request-id", f"request-{suffix}",
        "--operation-id", f"operation-{suffix}",
        "--attempt-id", f"attempt-{suffix}",
        "--idempotency-key", f"idempotency-{suffix}",
        "--json",
    ]


def control_args(
    workspace: str,
    action: str,
    target_operation_id: str,
    expected_revision: str,
    suffix: str,
) -> list[str]:
    return [
        "--workspace", workspace, "workspace", "migration", action,
        target_operation_id,
        "--expected-revision", expected_revision,
        "--confirmation", "explicit",
        "--request-id", f"request-{suffix}",
        "--operation-id", f"operation-{suffix}",
        "--attempt-id", f"attempt-{suffix}",
        "--idempotency-key", f"idempotency-{suffix}",
        "--json",
    ]


def interrupted_journal(
    workspace: Path,
    plan: dict[str, object],
    suffix: str,
    completed_steps: int = 0,
) -> dict[str, object]:
    effects: list[dict[str, object]] = []
    staged: list[dict[str, str]] = []
    for action in plan["actions"]:
        effect = dict(action)
        effect["source"] = Path(str(action["source"])).relative_to(workspace).as_posix()
        effect["target"] = Path(str(action["target"])).relative_to(workspace).as_posix()
        for key in ("backup_required", "journal_required", "backup_disposition", "rollback_disposition"):
            effect.pop(key)
        effects.append(effect)
        staged.append({"path": str(effect["target"]), "sha256": str(effect["target_sha256"])})
    completed = [str(effect["step_id"]) for effect in effects[:completed_steps]]
    committed = staged[:completed_steps]
    boundary = "staged_only" if completed_steps == 0 else "partially_committed_recoverable"
    operation = {
        "schema": "facman.workspace_migration_operation.v1",
        "operation_id": f"operation-{suffix}",
        "attempt_id": f"attempt-{suffix}",
        "request_id": f"request-{suffix}",
        "idempotency_key": f"idempotency-{suffix}",
        "migration_id": plan["migration_id"],
        "plan_digest": plan["plan_digest"],
        "expected_workspace_revision": plan["expected_workspace_revision"],
        "expected_root_identity": plan["expected_root_identity"],
        "current_phase": "applying",
        "terminal_classification": "none",
        "completed_steps": completed,
        "staged_outputs": staged,
        "committed_outputs": committed,
        "verification_results": ["staged_payloads_verified"],
        "recovery_boundary": boundary,
    }
    return {
        "schema": "facman.workspace_migration_journal.v2",
        "operation": operation,
        "input_identities": {
            "root_identity": plan["expected_root_identity"],
            "workspace_revision": plan["expected_workspace_revision"],
            "inventory_digest": plan["inventory_digest"],
            "plan_digest": plan["plan_digest"],
        },
        "effects": effects,
        "completed_steps": completed,
        "staged_outputs": staged,
        "committed_outputs": committed,
        "verification_results": ["staged_payloads_verified"],
        "recovery_boundary": boundary,
        "rollback_retained": True,
        "resulting_workspace_revision": None,
        "rollback_operation": None,
    }


def rebind_interrupted_journal(
    workspace: Path,
    plan: dict[str, object],
    journal: dict[str, object],
) -> None:
    current_format = "facman.factorio.workspace.v1"
    manifest = (workspace / "workspace.v1.json").read_bytes()
    effects = journal["effects"]
    plan_actions = {
        str(action["step_id"]): action for action in plan["actions"]
    }
    inventory_material = (
        f"{current_format}\nworkspace.v1.json\n"
        f"{hashlib.sha256(manifest).hexdigest()}\n"
    )
    for effect in effects:
        planned = plan_actions[str(effect["step_id"])]
        inventory_material += (
            f"{effect['step_id']}\n{effect['kind']}\n"
            f"{planned['source']}\n{planned['target']}\n"
            f"{effect['source_sha256']}\n{effect['target_sha256']}\n"
        )
    inventory_digest = hashlib.sha256(
        inventory_material.encode("utf-8")
    ).hexdigest()
    root_identity = str(journal["operation"]["expected_root_identity"])
    workspace_revision = hashlib.sha256(
        (
            f"{root_identity}\n{inventory_digest}\n"
            f"{current_format}\n"
        ).encode("utf-8")
    ).hexdigest()
    plan_material = (
        "facman.workspace_migration_plan.v2\n"
        f"{root_identity}\n{workspace_revision}\n{inventory_digest}\n"
        f"{current_format}\n{current_format}\n"
    )
    for effect in effects:
        planned = plan_actions[str(effect["step_id"])]
        plan_material += (
            f"{effect['step_id']}\n{effect['kind']}\n"
            f"{planned['source']}\n{planned['target']}\n"
            f"{effect['source_sha256']}\n{effect['target_sha256']}\n"
            "backup\njournal\n"
        )
    plan_digest = hashlib.sha256(plan_material.encode("utf-8")).hexdigest()
    operation = journal["operation"]
    operation["expected_workspace_revision"] = workspace_revision
    operation["plan_digest"] = plan_digest
    operation["migration_id"] = f"workspace-migration-{plan_digest[:24]}"
    identities = journal["input_identities"]
    identities["workspace_revision"] = workspace_revision
    identities["inventory_digest"] = inventory_digest
    identities["plan_digest"] = plan_digest


class WorkspaceStoreTests(unittest.TestCase):
    def test_explicit_workspace_creation_is_planned_bound_and_journaled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "new workspace \u03a9"
            before = snapshot(workspace)
            for operation in ("inspect", "plan"):
                code, stdout, stderr = invoke(
                    ["--workspace", str(workspace), "workspace", "migration", operation, "--json"]
                )
                self.assertEqual(code, 0, stderr or stdout)
                data = json.loads(stdout)
                self.assertEqual(data["command"], f"workspace.migration.{operation}")
                self.assertEqual(data["schema"], "facman.workspace_migration.v2")
                self.assertEqual(data["status"], "changes_detected")
                self.assertTrue(data["apply_enabled"])
                self.assertEqual(data["actions"][0]["kind"], "create_workspace_identity")
                self.assertEqual(snapshot(workspace), before)

            code, stdout, _stderr = invoke(
                ["--workspace", str(workspace), "workspace", "migration", "apply", "--json"]
            )
            self.assertEqual(code, 2)
            self.assertEqual(
                json.loads(stdout)["refusal"]["code"],
                "cli_invalid_invocation",
            )
            self.assertEqual(snapshot(workspace), before)

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "migration", "plan", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            plan = json.loads(stdout)
            code, stdout, stderr = invoke(apply_args(str(workspace), plan, "create"))
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["state"], "completed")
            self.assertTrue(result["mutation_executed"])
            self.assertRegex(result["resulting_workspace_revision"], r"^[0-9a-f]{64}$")
            self.assertNotEqual(
                result["resulting_workspace_revision"],
                result["expected_workspace_revision"],
            )
            self.assertTrue((workspace / "workspace.v1.json").is_file())
            journals = list((workspace / "transactions" / "workspace-migrations").glob(
                "*.workspace-creation.v1.json"
            ))
            self.assertEqual(len(journals), 1)
            journal = json.loads(journals[0].read_text(encoding="utf-8"))
            self.assertEqual(journal["state"], "completed")
            self.assertEqual(journal["operation_id"], "operation-create")
            self.assertEqual(
                journal["resulting_workspace_revision"],
                result["resulting_workspace_revision"],
            )
            validate_facman_schema(
                "facman_workspace_creation_journal.v1.schema.json", journal
            )
            code, stdout, stderr = invoke(apply_args(str(workspace), plan, "create"))
            self.assertEqual(code, 0, stderr)
            replayed = json.loads(stdout)
            self.assertEqual(replayed, result)
            self.assertEqual(len(list(
                (workspace / "transactions" / "workspace-migrations").glob(
                    "*.workspace-creation.v1.json"
                )
            )), 1)

            journal["state"] = "applying"
            journal["resulting_workspace_revision"] = None
            journals[0].write_text(json.dumps(journal), encoding="utf-8")
            (workspace / "workspace.v1.json").unlink()
            code, stdout, stderr = invoke(apply_args(str(workspace), plan, "create"))
            self.assertEqual(code, 0, stderr)
            recovered = json.loads(stdout)
            self.assertEqual(recovered, result)
            self.assertTrue((workspace / "workspace.v1.json").is_file())

    def test_startup_help_and_version_do_not_create_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "must remain absent"
            for args in (
                ["--workspace", str(workspace)],
                ["--workspace", str(workspace), "--help"],
                ["--workspace", str(workspace), "--version"],
            ):
                code, stdout, stderr = invoke(args)
                self.assertEqual(code, 0, stderr or stdout)
                self.assertFalse(workspace.exists())

    def test_legacy_record_canonicalization_is_journaled_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            canonical_install = workspace / "installs" / "refs" / "fixture.json"
            legacy_install = workspace / "installs" / "installed_state" / "fixture.json"
            legacy_install.parent.mkdir(parents=True, exist_ok=True)
            canonical_install.replace(legacy_install)
            legacy_instance = workspace / "instances" / "legacy" / "instance.manifest.json"
            legacy_instance.parent.mkdir(parents=True, exist_ok=True)
            legacy_instance.write_text(
                json.dumps(
                    {
                        "instance_id": "legacy",
                        "install_ref": "fixture",
                        "factorio_version": "2.0",
                        "extension": {"preserved": True},
                    }
                ),
                encoding="utf-8",
            )
            install_before = legacy_install.read_bytes()
            instance_before = legacy_instance.read_bytes()

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "plan", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            plan = json.loads(stdout)
            self.assertTrue(plan["apply_enabled"])
            self.assertEqual(len(plan["actions"]), 2)

            code, stdout, stderr = invoke(apply_args(tmp, plan, "legacy"))
            self.assertEqual(code, 0, stderr)
            applied = json.loads(stdout)
            self.assertTrue(applied["apply_enabled"])
            self.assertEqual(len(applied["actions"]), 2)
            self.assertRegex(applied["resulting_workspace_revision"], r"^[0-9a-f]{64}$")
            self.assertNotEqual(
                applied["resulting_workspace_revision"],
                applied["expected_workspace_revision"],
            )
            self.assertEqual(legacy_install.read_bytes(), install_before)
            self.assertEqual(legacy_instance.read_bytes(), instance_before)
            self.assertTrue(canonical_install.is_file())
            canonical_instance = json.loads(
                (workspace / "instances" / "legacy" / "instance.v1.json").read_text(encoding="utf-8")
            )
            self.assertEqual(canonical_instance["schema"], "factorio.instance.v1")
            self.assertEqual(canonical_instance["extension"], {"preserved": True})
            journals = list(
                (workspace / "transactions" / "workspace-migrations").glob(
                    "*.workspace-migration.v2.json"
                )
            )
            self.assertEqual(len(journals), 1)
            journal = json.loads(journals[0].read_text(encoding="utf-8"))
            validate_facman_schema(
                "facman_workspace_migration_journal.v2.schema.json", journal
            )
            self.assertEqual(journal["operation"]["operation_id"], "operation-legacy")
            self.assertEqual(journal["operation"]["current_phase"], "completed")
            self.assertEqual(journal["recovery_boundary"], "fully_committed")
            self.assertEqual(len(journal["staged_outputs"]), 2)
            self.assertEqual(journal["staged_outputs"], journal["committed_outputs"])
            self.assertTrue(journal["rollback_retained"])
            self.assertEqual(
                journal["resulting_workspace_revision"],
                applied["resulting_workspace_revision"],
            )

            code, stdout, stderr = invoke(apply_args(tmp, plan, "legacy"))
            self.assertEqual(code, 0, stderr)
            replayed = json.loads(stdout)
            self.assertEqual(replayed, applied)
            self.assertEqual(len(list(
                (workspace / "transactions" / "workspace-migrations").glob(
                    "*.workspace-migration.v2.json"
                )
            )), 1)

            conflicting = apply_args(tmp, plan, "legacy")
            root_index = conflicting.index("--expected-root") + 1
            conflicting[root_index] = "0" * 64
            code, stdout, stderr = invoke_machine(conflicting)
            self.assertEqual((code, stderr), (1, ""), stdout)
            conflict = json.loads(stdout)
            self.assertEqual(conflict["outcome"], "conflict")
            self.assertEqual(conflict["error"]["code"], "workspace_migration_conflict")

            rollback_args = control_args(
                tmp,
                "rollback",
                "operation-legacy",
                str(applied["resulting_workspace_revision"]),
                "rollback-legacy",
            )
            code, stdout, stderr = invoke(rollback_args)
            self.assertEqual(code, 0, stderr)
            rolled_back = json.loads(stdout)
            validate_facman_schema(
                "facman_workspace_migration.v2.schema.json", rolled_back
            )
            self.assertEqual(rolled_back["command"], "workspace.migration.rollback")
            self.assertEqual(rolled_back["state"], "rolled_back")
            self.assertEqual(
                rolled_back["operation"]["verification_results"],
                ["rollback_state_verified"],
            )
            self.assertFalse(canonical_install.exists())
            self.assertFalse(
                (workspace / "instances" / "legacy" / "instance.v1.json").exists()
            )
            self.assertEqual(legacy_install.read_bytes(), install_before)
            self.assertEqual(legacy_instance.read_bytes(), instance_before)

            code, stdout, stderr = invoke(rollback_args)
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout), rolled_back)

            code, stdout, stderr = invoke([
                "--workspace", tmp, "workspace", "migration", "operation", "inspect",
                "operation-legacy", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            inspected = json.loads(stdout)
            validate_facman_schema(
                "facman_workspace_migration.v2.schema.json", inspected
            )
            self.assertEqual(inspected["state"], "rolled_back")
            self.assertEqual(inspected["recovery"]["safe_actions"], ["inspect"])

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "plan", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            repeated_plan = json.loads(stdout)
            code, stdout, stderr = invoke(apply_args(tmp, repeated_plan, "legacy-repeat"))
            self.assertEqual(code, 0, stderr)
            repeated = json.loads(stdout)
            self.assertEqual(repeated["status"], "changes_detected")
            self.assertEqual(len(repeated["actions"]), 2)

            rollback_fault_args = control_args(
                tmp,
                "rollback",
                "operation-legacy-repeat",
                str(repeated["resulting_workspace_revision"]),
                "rollback-fault",
            )
            environment = os.environ.copy()
            environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = "during_rollback:1"
            code, stdout, stderr = invoke_machine(
                rollback_fault_args, env=environment
            )
            self.assertEqual((code, stderr), (1, ""), stdout)
            interrupted_rollback = json.loads(stdout)
            self.assertEqual(
                interrupted_rollback["error"]["code"],
                "workspace_migration_interrupted",
            )

            code, stdout, stderr = invoke([
                "--workspace", tmp, "workspace", "migration", "operation", "inspect",
                "operation-legacy-repeat", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            rollback_inspection = json.loads(stdout)
            self.assertEqual(rollback_inspection["state"], "rollback_available")
            self.assertIn("recover", rollback_inspection["recovery"]["safe_actions"])

            code, stdout, stderr = invoke(control_args(
                tmp,
                "recover",
                "operation-legacy-repeat",
                str(rollback_inspection["observed_workspace_revision"]),
                "rollback-recover",
            ))
            self.assertEqual(code, 0, stderr)
            recovered_rollback = json.loads(stdout)
            validate_facman_schema(
                "facman_workspace_migration.v2.schema.json", recovered_rollback
            )
            self.assertEqual(
                recovered_rollback["command"], "workspace.migration.recover"
            )
            self.assertEqual(recovered_rollback["state"], "rolled_back")
            self.assertFalse(canonical_install.exists())

    def test_recovery_required_is_recoverable_but_not_directly_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            migration_root = Path(tmp) / "transactions" / "workspace-migrations"
            migration_root.mkdir(parents=True, exist_ok=True)
            journal = migration_root / "manual.workspace-migration.v1.json"
            journal.write_text(
                json.dumps(
                    {
                        "schema": "facman.workspace_migration_journal.v1",
                        "migration_id": "manual",
                        "state": "recovery_required",
                        "completed_actions": 0,
                        "actions": [],
                    }
                ),
                encoding="utf-8",
            )
            code, plan_stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "plan", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            code, stdout, stderr = invoke_machine(
                apply_args(tmp, json.loads(plan_stdout), "manual-recovery")
            )
            self.assertEqual((code, stderr), (1, ""), stdout)
            envelope = json.loads(stdout)
            self.assertEqual(envelope["outcome"], "refused")
            self.assertEqual(envelope["error"]["code"], "workspace_migration_recovery_required")
            refusal = envelope["payload"]["refusal"]
            self.assertTrue(refusal["recoverable"])
            self.assertFalse(refusal["retryable"])
            self.assertNotIn("suggested_next_command", refusal)
            self.assertFalse(envelope["operation"]["recovery"]["required"])
            self.assertEqual(envelope["operation"]["recovery"]["inspect_command"], "")

    def test_interrupted_v2_staging_resumes_the_exact_operation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            canonical = workspace / "installs" / "refs" / "fixture.json"
            legacy = workspace / "installs" / "installed_state" / "fixture.json"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            canonical.replace(legacy)
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "plan", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            plan = json.loads(stdout)
            journal = interrupted_journal(workspace, plan, "resume")
            validate_facman_schema(
                "facman_workspace_migration_journal.v2.schema.json", journal
            )
            migration_root = workspace / "transactions" / "workspace-migrations"
            data_root = migration_root / "operation-resume.data"
            data_root.mkdir(parents=True, exist_ok=True)
            payload = legacy.read_bytes()
            (data_root / "0.source.json").write_bytes(payload)
            (data_root / "0.target.json").write_bytes(payload)
            journal_path = migration_root / "operation-resume.workspace-migration.v2.json"
            journal_path.write_text(json.dumps(journal), encoding="utf-8")

            code, stdout, stderr = invoke([
                "--workspace", tmp, "workspace", "migration", "operation", "inspect",
                "operation-resume", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            inspection = json.loads(stdout)
            validate_facman_schema(
                "facman_workspace_migration.v2.schema.json", inspection
            )
            self.assertEqual(inspection["state"], "interrupted_recoverable")
            self.assertEqual(
                inspection["recovery"]["safe_actions"],
                ["inspect", "resume", "recover"],
            )
            code, stdout, stderr = invoke(control_args(
                tmp,
                "resume",
                "operation-resume",
                str(inspection["observed_workspace_revision"]),
                "resume-control",
            ))
            self.assertEqual(code, 0, stderr)
            recovered = json.loads(stdout)
            self.assertEqual(recovered["command"], "workspace.migration.resume")
            self.assertEqual(recovered["state"], "completed")
            self.assertTrue(recovered["mutation_executed"])
            self.assertTrue(canonical.is_file())
            terminal = json.loads(journal_path.read_text(encoding="utf-8"))
            validate_facman_schema(
                "facman_workspace_migration_journal.v2.schema.json", terminal
            )
            self.assertEqual(terminal["operation"]["current_phase"], "completed")
            self.assertEqual(
                terminal["resulting_workspace_revision"],
                recovered["resulting_workspace_revision"],
            )

    def test_interrupted_v2_resume_rejects_rewritten_bindings_without_effects(self) -> None:
        corruptions = {
            "root": lambda journal: (
                journal["operation"].__setitem__("expected_root_identity", "0" * 64),
                journal["input_identities"].__setitem__("root_identity", "0" * 64),
            ),
            "revision": lambda journal: (
                journal["operation"].__setitem__("expected_workspace_revision", "0" * 64),
                journal["input_identities"].__setitem__("workspace_revision", "0" * 64),
            ),
            "inventory": lambda journal: journal["input_identities"].__setitem__(
                "inventory_digest", "0" * 64
            ),
            "plan": lambda journal: (
                journal["operation"].__setitem__("plan_digest", "0" * 64),
                journal["input_identities"].__setitem__("plan_digest", "0" * 64),
            ),
            "source": lambda journal: journal["effects"][0].__setitem__(
                "source_sha256", "0" * 64
            ),
        }
        for name, corrupt in corruptions.items():
            with self.subTest(binding=name), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                code, _stdout, stderr = invoke([
                    "--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL),
                    "--id", "fixture", "--json",
                ])
                self.assertEqual(code, 0, stderr)
                canonical = workspace / "installs" / "refs" / "fixture.json"
                legacy = workspace / "installs" / "installed_state" / "fixture.json"
                legacy.parent.mkdir(parents=True, exist_ok=True)
                canonical.replace(legacy)
                original = legacy.read_bytes()
                code, stdout, stderr = invoke([
                    "--workspace", tmp, "workspace", "migration", "plan", "--json",
                ])
                self.assertEqual(code, 0, stderr)
                plan = json.loads(stdout)
                journal = interrupted_journal(workspace, plan, f"binding-{name}")
                migration_root = workspace / "transactions" / "workspace-migrations"
                data_root = migration_root / f"operation-binding-{name}.data"
                data_root.mkdir(parents=True, exist_ok=True)
                (data_root / "0.source.json").write_bytes(original)
                (data_root / "0.target.json").write_bytes(original)
                corrupt(journal)
                journal_path = (
                    migration_root /
                    f"operation-binding-{name}.workspace-migration.v2.json"
                )
                journal_before = json.dumps(journal)
                journal_path.write_text(journal_before, encoding="utf-8")

                code, stdout, stderr = invoke_machine(control_args(
                    tmp,
                    "resume",
                    f"operation-binding-{name}",
                    str(plan["expected_workspace_revision"]),
                    f"resume-binding-{name}",
                ))
                self.assertEqual((code, stderr), (1, ""), stdout)
                refusal = json.loads(stdout)
                self.assertEqual(
                    refusal["error"]["code"],
                    "workspace_migration_apply_unproven",
                )
                self.assertFalse(canonical.exists())
                self.assertEqual(legacy.read_bytes(), original)
                self.assertEqual(journal_path.read_text(encoding="utf-8"), journal_before)

    def test_v2_rollback_rejects_self_consistent_rewrites_without_effects(self) -> None:
        for variant in ("changed-target", "duplicate-action"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                code, _stdout, stderr = invoke([
                    "--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL),
                    "--id", "fixture", "--json",
                ])
                self.assertEqual(code, 0, stderr)
                canonical = workspace / "installs" / "refs" / "fixture.json"
                legacy = workspace / "installs" / "installed_state" / "fixture.json"
                legacy.parent.mkdir(parents=True, exist_ok=True)
                canonical.replace(legacy)
                original = legacy.read_bytes()
                code, stdout, stderr = invoke([
                    "--workspace", tmp, "workspace", "migration", "plan", "--json",
                ])
                self.assertEqual(code, 0, stderr)
                plan = json.loads(stdout)
                journal = interrupted_journal(
                    workspace, plan, f"self-consistent-{variant}", completed_steps=1
                )
                forged = b"{}"
                forged_digest = hashlib.sha256(forged).hexdigest()
                canonical.write_bytes(forged)
                journal["effects"][0]["target_sha256"] = forged_digest
                journal["staged_outputs"][0]["sha256"] = forged_digest
                journal["committed_outputs"][0]["sha256"] = forged_digest
                if variant == "duplicate-action":
                    duplicate = dict(journal["effects"][0])
                    duplicate["step_id"] = "step-2"
                    journal["effects"].append(duplicate)
                    journal["completed_steps"].append("step-2")
                    duplicate_output = dict(journal["staged_outputs"][0])
                    journal["staged_outputs"].append(duplicate_output)
                    journal["committed_outputs"].append(dict(duplicate_output))
                    plan["actions"].append({
                        **plan["actions"][0],
                        "step_id": "step-2",
                    })
                rebind_interrupted_journal(workspace, plan, journal)
                journal["operation"]["plan_digest"] = journal["input_identities"][
                    "plan_digest"
                ]
                data_root = (
                    workspace / "transactions" / "workspace-migrations" /
                    f"operation-self-consistent-{variant}.data"
                )
                data_root.mkdir(parents=True, exist_ok=True)
                for index in range(len(journal["effects"])):
                    (data_root / f"{index}.source.json").write_bytes(original)
                    (data_root / f"{index}.target.json").write_bytes(forged)
                journal_path = data_root.with_suffix(".workspace-migration.v2.json")
                journal_before = json.dumps(journal)
                journal_path.write_text(journal_before, encoding="utf-8")

                code, stdout, stderr = invoke([
                    "--workspace", tmp, "workspace", "migration", "operation",
                    "inspect", f"operation-self-consistent-{variant}", "--json",
                ])
                self.assertEqual(code, 0, stderr or stdout)
                observed_revision = json.loads(stdout)["observed_workspace_revision"]

                code, stdout, stderr = invoke_machine(control_args(
                    tmp,
                    "rollback",
                    f"operation-self-consistent-{variant}",
                    str(observed_revision),
                    f"rollback-self-consistent-{variant}",
                ))
                self.assertEqual((code, stderr), (1, ""), stdout)
                refusal = json.loads(stdout)
                self.assertEqual(
                    refusal["error"]["code"],
                    "workspace_migration_apply_unproven",
                )
                self.assertEqual(canonical.read_bytes(), forged)
                self.assertEqual(legacy.read_bytes(), original)
                self.assertEqual(journal_path.read_text(encoding="utf-8"), journal_before)

    def test_fault_boundaries_resume_without_duplicate_effects(self) -> None:
        for boundary in (
            "after_journal_creation",
            "after_backup:1",
            "after_staged_file:1",
            "after_staging_verification",
            "before_first_commit",
            "after_commit:1",
            "before_terminal_receipt",
        ):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                code, _stdout, stderr = invoke(
                    ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
                )
                self.assertEqual(code, 0, stderr)
                canonical = workspace / "installs" / "refs" / "fixture.json"
                legacy = workspace / "installs" / "installed_state" / "fixture.json"
                legacy.parent.mkdir(parents=True, exist_ok=True)
                canonical.replace(legacy)
                code, stdout, stderr = invoke(
                    ["--workspace", tmp, "workspace", "migration", "plan", "--json"]
                )
                self.assertEqual(code, 0, stderr)
                plan = json.loads(stdout)
                suffix = "fault-" + boundary.replace(":", "-")
                args = apply_args(tmp, plan, suffix)
                environment = os.environ.copy()
                environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = boundary
                code, stdout, stderr = invoke_machine(args, env=environment)
                self.assertEqual((code, stderr), (1, ""), stdout)
                interrupted = json.loads(stdout)
                self.assertEqual(
                    interrupted["error"]["code"], "workspace_migration_interrupted"
                )
                self.assertTrue(interrupted["payload"]["refusal"]["recoverable"])
                self.assertTrue(interrupted["payload"]["refusal"]["retryable"])

                code, stdout, stderr = invoke([
                    "--workspace", tmp, "workspace", "migration", "operation", "inspect",
                    f"operation-{suffix}", "--json",
                ])
                self.assertEqual(code, 0, stderr)
                inspection = json.loads(stdout)
                self.assertEqual(inspection["state"], "interrupted_recoverable")
                self.assertIn("recover", inspection["recovery"]["safe_actions"])
                code, stdout, stderr = invoke(control_args(
                    tmp,
                    "recover",
                    f"operation-{suffix}",
                    str(inspection["observed_workspace_revision"]),
                    f"recover-{suffix}",
                ))
                self.assertEqual(code, 0, stderr or stdout)
                resumed = json.loads(stdout)
                self.assertEqual(resumed["command"], "workspace.migration.recover")
                self.assertEqual(resumed["state"], "completed")
                self.assertTrue(canonical.is_file())
                self.assertEqual(len(list(
                    (workspace / "transactions" / "workspace-migrations").glob(
                        "*.workspace-migration.v2.json"
                    )
                )), 1)

    def test_prejournal_faults_have_no_effects_and_retry_exactly(self) -> None:
        for boundary in ("after_lock_acquisition", "before_journal_creation"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                code, _stdout, stderr = invoke(
                    ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
                )
                self.assertEqual(code, 0, stderr)
                canonical = workspace / "installs" / "refs" / "fixture.json"
                legacy = workspace / "installs" / "installed_state" / "fixture.json"
                legacy.parent.mkdir(parents=True, exist_ok=True)
                canonical.replace(legacy)
                code, stdout, stderr = invoke(
                    ["--workspace", tmp, "workspace", "migration", "plan", "--json"]
                )
                self.assertEqual(code, 0, stderr)
                plan = json.loads(stdout)
                args = apply_args(tmp, plan, "prejournal-" + boundary)
                environment = os.environ.copy()
                environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = boundary
                code, stdout, stderr = invoke_machine(args, env=environment)
                self.assertEqual((code, stderr), (1, ""), stdout)
                self.assertEqual(
                    json.loads(stdout)["error"]["code"],
                    "workspace_migration_interrupted",
                )
                self.assertFalse(canonical.exists())
                self.assertEqual(list(
                    (workspace / "transactions" / "workspace-migrations").glob(
                        "*.workspace-migration.v2.json"
                    )
                ), [])
                code, stdout, stderr = invoke(args)
                self.assertEqual(code, 0, stderr or stdout)
                self.assertEqual(json.loads(stdout)["state"], "completed")
                self.assertTrue(canonical.is_file())

    def test_workspace_creation_fault_boundaries_recover_safely(self) -> None:
        for boundary in (
            "after_creation_lock_acquisition",
            "before_creation_journal",
            "after_creation_journal",
            "after_workspace_creation",
            "before_creation_terminal_receipt",
        ):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp) / "new workspace \u03a9"
                code, stdout, stderr = invoke([
                    "--workspace", str(workspace), "workspace", "migration", "plan", "--json",
                ])
                self.assertEqual(code, 0, stderr)
                plan = json.loads(stdout)
                args = apply_args(str(workspace), plan, "creation-" + boundary)
                environment = os.environ.copy()
                environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = boundary
                code, stdout, stderr = invoke_machine(args, env=environment)
                self.assertEqual((code, stderr), (1, ""), stdout)
                self.assertEqual(
                    json.loads(stdout)["error"]["code"],
                    "workspace_migration_interrupted",
                )
                code, stdout, stderr = invoke(args)
                if boundary in {
                    "after_creation_lock_acquisition",
                    "before_creation_journal",
                }:
                    self.assertEqual(code, 1, stderr or stdout)
                    self.assertEqual(
                        json.loads(stdout)["refusal"]["code"],
                        "workspace_migration_stale_plan",
                    )
                    code, stdout, stderr = invoke([
                        "--workspace", str(workspace), "workspace", "migration", "plan", "--json",
                    ])
                    self.assertEqual(code, 0, stderr or stdout)
                    args = apply_args(
                        str(workspace),
                        json.loads(stdout),
                        "creation-replan-" + boundary,
                    )
                    code, stdout, stderr = invoke(args)
                self.assertEqual(code, 0, stderr or stdout)
                replayed = json.loads(stdout)
                self.assertEqual(replayed["state"], "completed")
                self.assertTrue((workspace / "workspace.v1.json").is_file())

    def test_rollback_terminal_boundary_recovers_to_exact_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            canonical = workspace / "installs" / "refs" / "fixture.json"
            legacy = workspace / "installs" / "installed_state" / "fixture.json"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            canonical.replace(legacy)
            original = legacy.read_bytes()
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "plan", "--json"]
            )
            self.assertEqual(code, 0, stderr or stdout)
            plan = json.loads(stdout)
            code, stdout, stderr = invoke(apply_args(tmp, plan, "rollback-terminal"))
            self.assertEqual(code, 0, stderr or stdout)
            applied = json.loads(stdout)
            rollback = control_args(
                tmp,
                "rollback",
                "operation-rollback-terminal",
                str(applied["resulting_workspace_revision"]),
                "rollback-terminal-control",
            )
            environment = os.environ.copy()
            environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = (
                "after_rollback_before_receipt"
            )
            code, stdout, stderr = invoke_machine(rollback, env=environment)
            self.assertEqual((code, stderr), (1, ""), stdout)
            self.assertEqual(
                json.loads(stdout)["error"]["code"],
                "workspace_migration_interrupted",
            )
            self.assertFalse(canonical.exists())
            self.assertEqual(legacy.read_bytes(), original)

            code, stdout, stderr = invoke([
                "--workspace", tmp, "workspace", "migration", "operation", "inspect",
                "operation-rollback-terminal", "--json",
            ])
            self.assertEqual(code, 0, stderr or stdout)
            inspection = json.loads(stdout)
            self.assertEqual(inspection["state"], "rollback_available")
            code, stdout, stderr = invoke(control_args(
                tmp,
                "recover",
                "operation-rollback-terminal",
                str(inspection["observed_workspace_revision"]),
                "recover-rollback-terminal",
            ))
            self.assertEqual(code, 0, stderr or stdout)
            recovered = json.loads(stdout)
            self.assertEqual(recovered["state"], "rolled_back")
            self.assertFalse(canonical.exists())
            self.assertEqual(legacy.read_bytes(), original)

    def test_divergent_recovery_target_is_retryable_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            target = workspace / "installs" / "refs" / "fixture.json"
            source = workspace / "installs" / "installed_state" / "fixture.json"
            source.parent.mkdir(parents=True, exist_ok=True)
            target.replace(source)
            payload = source.read_bytes()
            target.write_text("{}\n", encoding="utf-8")
            digest = hashlib.sha256(payload).hexdigest()
            migration_root = workspace / "transactions" / "workspace-migrations"
            data_root = migration_root / "conflict.data"
            data_root.mkdir(parents=True, exist_ok=True)
            (data_root / "0.source.json").write_bytes(payload)
            (data_root / "0.target.json").write_bytes(payload)
            (migration_root / "conflict.workspace-migration.v1.json").write_text(
                json.dumps(
                    {
                        "schema": "facman.workspace_migration_journal.v1",
                        "migration_id": "conflict",
                        "state": "applying",
                        "completed_actions": 0,
                        "actions": [
                            {
                                "kind": "canonicalize_legacy_install_ref",
                                "source": "installs/installed_state/fixture.json",
                                "target": "installs/refs/fixture.json",
                                "source_sha256": digest,
                                "target_sha256": digest,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            code, plan_stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "plan", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            code, stdout, stderr = invoke_machine(
                apply_args(tmp, json.loads(plan_stdout), "conflict")
            )
            self.assertEqual((code, stderr), (1, ""), stdout)
            envelope = json.loads(stdout)
            self.assertEqual(envelope["outcome"], "conflict")
            self.assertEqual(envelope["error"]["code"], "workspace_migration_conflict")
            refusal = envelope["payload"]["refusal"]
            self.assertTrue(refusal["recoverable"])
            self.assertTrue(refusal["retryable"])
            self.assertEqual(target.read_text(encoding="utf-8"), "{}\n")

    def test_new_workspace_gets_stable_random_uuid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            manifest = json.loads((Path(tmp) / "workspace.v1.json").read_text(encoding="utf-8"))
            self.assertNotEqual(manifest["workspace_id"], "local")
            self.assertRegex(
                manifest["workspace_id"],
                re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
            )
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "migration", "inspect", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["status"], "no_changes")

    def test_future_workspace_refuses_before_creating_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "workspace.v1.json").write_text(
                json.dumps(
                    {
                        "schema": "facman.factorio.workspace.v2",
                        "workspace_id": "future",
                        "layout_version": 2,
                    }
                ),
                encoding="utf-8",
            )
            before = snapshot(workspace)
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "workspace_layout_future_or_unknown")
            self.assertEqual(snapshot(workspace), before)


if __name__ == "__main__":
    unittest.main()
