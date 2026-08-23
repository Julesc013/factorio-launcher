# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import jsonschema

from native_cli import ROOT, facman_executable, invoke_machine
from test_diagnostic_redaction import assert_no_secret_values


def tree(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


def write_installation_fixture(root: Path) -> None:
    executable = (
        root / "bin" / "x64" / "factorio.exe"
        if sys.platform == "win32"
        else root / "Factorio.app" / "Contents" / "MacOS" / "factorio"
        if sys.platform == "darwin"
        else root / "bin" / "x64" / "factorio"
    )
    executable.parent.mkdir(parents=True)
    executable.write_text("synthetic fixture; never executed\n", encoding="utf-8")
    (root / "data" / "base").mkdir(parents=True)
    (root / "data" / "base" / "info.json").write_text(
        '{"name":"base","version":"2.0.77"}\n', encoding="utf-8"
    )
    (root / "config-path.cfg").write_text(
        "use-system-read-write-data-directories=false\n", encoding="utf-8"
    )


class PresentationServiceTests(unittest.TestCase):
    def test_local_content_and_save_lifecycle_is_descriptor_driven_and_replayable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-content-saves-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            installation = root / "factorio-fixture"
            write_installation_fixture(installation)
            installation = installation.resolve()

            def query(
                scope: str, *, selected: bool = True
            ) -> dict[str, object]:
                arguments = [
                    "--workspace", str(workspace), "presentation", "query", scope,
                ]
                if selected:
                    arguments.extend(["--instance", "fixture-isolated"])
                arguments.append("--json")
                code, stdout, stderr = invoke_machine(arguments)
                self.assertEqual((code, stderr), (0, ""), stdout)
                return json.loads(stdout)["payload"]

            def action(
                scope: str,
                action_id: str,
                identity: str,
                inputs: list[str],
                *,
                effectful: bool = False,
            ) -> tuple[str, dict[str, object], list[str]]:
                snapshot = query(scope)
                arguments = [
                    "--workspace", str(workspace), "presentation", "action",
                    action_id, "--scope", scope,
                    "--expected-revision", str(snapshot["revision"]),
                    "--request-id", f"request-{identity}",
                    "--instance", "fixture-isolated",
                    *inputs,
                ]
                if effectful:
                    arguments.extend([
                        "--idempotency-key", f"idempotency-{identity}",
                        "--operation-id", f"operation-{identity}",
                        "--attempt-id", f"attempt-{identity}",
                        "--confirmation", "explicit",
                    ])
                arguments.append("--json")
                code, stdout, stderr = invoke_machine(arguments)
                self.assertEqual((code, stderr), (0, ""), stdout)
                return stdout, json.loads(stdout)["payload"], arguments

            initial_installations = query("installations", selected=False)
            register = [
                "--workspace", str(workspace), "presentation", "action",
                "installation.register_read_only", "--scope", "installations",
                "--expected-revision", str(initial_installations["revision"]),
                "--request-id", "request-register-content-fixture",
                "--idempotency-key", "idempotency-register-content-fixture",
                "--operation-id", "operation-register-content-fixture",
                "--attempt-id", "attempt-register-content-fixture",
                "--confirmation", "explicit",
                "--installation", "fixture-read-only",
                "--installation-path", str(installation), "--json",
            ]
            code, stdout, stderr = invoke_machine(register)
            self.assertEqual((code, stderr), (0, ""), stdout)

            instances = query("instances", selected=False)
            create = [
                "--workspace", str(workspace), "presentation", "action",
                "instance.create_isolated", "--scope", "instances",
                "--expected-revision", str(instances["revision"]),
                "--request-id", "request-create-content-fixture",
                "--idempotency-key", "idempotency-create-content-fixture",
                "--operation-id", "operation-create-content-fixture",
                "--attempt-id", "attempt-create-content-fixture",
                "--confirmation", "explicit",
                "--installation", "fixture-read-only",
                "--new-instance", "fixture-isolated",
                "--display-name", "Fixture Isolated", "--json",
            ]
            code, stdout, stderr = invoke_machine(create)
            self.assertEqual((code, stderr), (0, ""), stdout)

            instance_root = workspace / "instances" / "fixture-isolated"
            shutil.copyfile(
                ROOT / "tests/fixtures/factorio_mods/valid_simple/simple_mod_1.0.0.zip",
                instance_root / "mods" / "simple_mod_1.0.0.zip",
            )
            source_save = instance_root / "saves" / "starter.zip"
            shutil.copyfile(
                ROOT / "tests/fixtures/factorio_saves/valid_simple_save/starter.zip",
                source_save,
            )
            source_save_digest = hashlib.sha256(source_save.read_bytes()).hexdigest()

            content = query("content")
            local_mod = next(
                item for item in content["page"]["items"]
                if item.get("kind") == "local_mod"
            )
            self.assertEqual(local_mod["identity"], "simple_mod@1.0.0")
            self.assertFalse(local_mod["portal_access"])
            content_actions = {
                item["action_id"]: item
                for item in content["available_semantic_actions"]
            }
            self.assertIn(
                "simple_mod@1.0.0",
                content_actions["mods.inspect"]["input_fields"][0]["choices"],
            )
            apply_fields = {
                field["field_id"]: field
                for field in content_actions["modsets.apply"]["input_fields"]
            }
            self.assertEqual(
                apply_fields["mod_identity"]["choices"],
                ["simple_mod"],
            )

            _, inspected, _ = action(
                "content", "mods.inspect", "inspect-mod",
                ["--mod", "simple_mod@1.0.0"],
            )
            self.assertEqual(
                inspected["action_payload"]["schema"],
                "factorio.mod_inventory_record.v1",
            )
            self.assertFalse(inspected["action_payload"]["portal_access"])

            _, planned, _ = action(
                "content", "modsets.plan", "plan-modset",
                ["--mod", "simple_mod"],
            )
            self.assertEqual(
                planned["action_payload"]["schema"], "factorio.modset_plan.v1"
            )
            self.assertTrue(planned["action_payload"]["local_artifacts_only"])
            self.assertFalse(planned["action_payload"]["portal_access"])

            applied_text, applied, applied_arguments = action(
                "content", "modsets.apply", "apply-modset",
                ["--mod", "simple_mod"], effectful=True,
            )
            self.assertEqual(applied["outcome"], "completed")
            self.assertEqual(applied["action_payload"]["status"], "applied")
            code, replay, stderr = invoke_machine(applied_arguments)
            self.assertEqual((code, stderr, replay), (0, "", applied_text))

            _, verified, _ = action(
                "content", "modsets.verify", "verify-modset", [],
            )
            self.assertEqual(
                verified["action_payload"]["schema"], "factorio.modset_verify.v1"
            )
            self.assertEqual(verified["action_payload"]["status"], "ok")

            saves = query("saves")
            save = next(
                item for item in saves["page"]["items"]
                if item.get("name") == "starter.zip"
            )
            self.assertEqual(save["association_status"], "absent")
            self.assertEqual(save["backup_status"], "absent")
            save_actions = {
                item["action_id"]: item
                for item in saves["available_semantic_actions"]
            }
            inspect_save_fields = {
                field["field_id"]: field
                for field in save_actions["saves.inspect"]["input_fields"]
            }
            self.assertEqual(
                inspect_save_fields["save"]["choices"],
                ["starter.zip"],
            )

            _, inspected_save, _ = action(
                "saves", "saves.inspect", "inspect-save",
                ["--save", "starter.zip"],
            )
            self.assertEqual(
                inspected_save["action_payload"]["schema"],
                "factorio.save_intelligence.v1",
            )
            _, associated, _ = action(
                "saves", "saves.associate", "associate-save",
                ["--save", "starter.zip"], effectful=True,
            )
            self.assertEqual(associated["action_payload"]["status"], "associated")
            self.assertEqual(
                hashlib.sha256(source_save.read_bytes()).hexdigest(), source_save_digest
            )

            config_root = instance_root / "config"
            logs_root = instance_root / "logs"
            config_root.mkdir(exist_ok=True)
            logs_root.mkdir(exist_ok=True)
            shutil.copyfile(
                ROOT / "tests/fixtures/redaction/server_settings_with_rcon_password.json",
                config_root / "server-settings.json",
            )
            shutil.copyfile(
                ROOT / "tests/fixtures/redaction/log_with_token.txt",
                logs_root / "factorio-current.log",
            )

            settings = query("settings_support")
            settings_actions = {
                item["action_id"]: item
                for item in settings["available_semantic_actions"]
            }
            support_export = settings_actions["support.export_redacted_bundle"]
            self.assertEqual(
                support_export["input_contract"],
                "facman.semantic_action_input.v1",
            )
            support_fields = {
                field["field_id"]: field
                for field in support_export["input_fields"]
            }
            self.assertEqual(
                set(support_fields), {"selected_instance_id", "output_path"}
            )
            self.assertTrue(support_fields["output_path"]["required"])

            support_path = root / "facman-support.zip"
            exported_text, exported, export_arguments = action(
                "settings_support", "support.export_redacted_bundle",
                "export-support", ["--output", str(support_path)],
                effectful=True,
            )
            export_payload = exported["action_payload"]
            self.assertEqual(
                export_payload["schema"], "factorio.diagnostic_bundle_export.v1"
            )
            self.assertEqual(Path(export_payload["path"]), support_path)
            self.assertTrue(export_payload["self_verified"])
            self.assertTrue(export_payload["manifest_sha256"])
            self.assertGreaterEqual(
                export_payload["redaction_summary"]["redacted_fields"], 2
            )
            assert_no_secret_values(self, exported_text)
            with zipfile.ZipFile(support_path) as archive:
                bundled = b"".join(
                    archive.read(name) for name in archive.namelist()
                )
            assert_no_secret_values(self, bundled)

            code, replay, stderr = invoke_machine(export_arguments)
            self.assertEqual((code, stderr, replay), (0, "", exported_text))
            support_before = support_path.read_bytes()
            refused_snapshot = query("settings_support")
            refusal_arguments = [
                "--workspace", str(workspace), "presentation", "action",
                "support.export_redacted_bundle", "--scope", "settings_support",
                "--expected-revision", str(refused_snapshot["revision"]),
                "--request-id", "request-export-support-no-clobber",
                "--instance", "fixture-isolated", "--output", str(support_path),
                "--idempotency-key", "idempotency-export-support-no-clobber",
                "--operation-id", "operation-export-support-no-clobber",
                "--attempt-id", "attempt-export-support-no-clobber",
                "--confirmation", "explicit", "--json",
            ]
            code, stdout, stderr = invoke_machine(refusal_arguments)
            self.assertEqual((code, stderr), (1, ""), stdout)
            refusal = json.loads(stdout)
            self.assertEqual(
                refusal["error"]["code"], "diagnostic_bundle_target_exists"
            )
            self.assertEqual(support_path.read_bytes(), support_before)

            backup_path = root / "output" / "starter.backup.zip"
            backup_path.parent.mkdir()
            backed_up_text, backed_up, backup_arguments = action(
                "saves", "saves.backup", "backup-save",
                ["--save", "starter.zip", "--output", str(backup_path)],
                effectful=True,
            )
            self.assertEqual(
                backed_up["action_payload"]["schema"], "factorio.save_backup.v1"
            )
            self.assertEqual(backup_path.read_bytes(), source_save.read_bytes())
            code, replay, stderr = invoke_machine(backup_arguments)
            self.assertEqual((code, stderr, replay), (0, "", backed_up_text))
            self.assertEqual(
                hashlib.sha256(source_save.read_bytes()).hexdigest(), source_save_digest
            )

    def test_semantic_action_forms_are_schema_backed_and_frontend_consumed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-form-") as temporary:
            workspace = Path(temporary) / "workspace"
            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query", "content", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            snapshot = json.loads(stdout)["payload"]
            actions = {
                action["action_id"]: action
                for action in snapshot["available_semantic_actions"]
            }
            create = actions["profile.create"]
            self.assertEqual(
                create["input_contract"], "facman.semantic_action_input.v1"
            )
            field_schema = json.loads((
                ROOT / "contracts/schema/presentation/semantic_action_input.v1.schema.json"
            ).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(field_schema).validate({
                "schema": create["input_contract"],
                "fields": create["input_fields"],
            })
            self.assertEqual(
                create["input_fields"],
                [{
                    "choices": [],
                    "default": "new-profile",
                    "field_id": "profile_id",
                    "label": "New profile ID",
                    "required": True,
                    "type": "identifier",
                }],
            )
            self.assertFalse(workspace.exists())

            sources = {
                "tui": (ROOT / "apps/tui/tui_product_shell.cpp").read_text(encoding="utf-8"),
                "winforms_model": (ROOT / "apps/gui/windows/winforms/PresentationModels.cs").read_text(encoding="utf-8"),
                "winforms_shell": (ROOT / "apps/gui/windows/winforms/C1ShellForm.cs").read_text(encoding="utf-8"),
            }
            self.assertIn("action.input_fields", sources["tui"])
            self.assertIn("PresentationActionInputField", sources["winforms_model"])
            self.assertIn("PromptActionInputs", sources["winforms_shell"])

    def test_ordinary_content_saves_and_settings_scopes_are_backend_snapshots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-ordinary-") as temporary:
            workspace = Path(temporary) / "workspace"
            before = tree(workspace)
            schema = json.loads((
                ROOT / "contracts/schema/presentation/presentation_snapshot.v1.schema.json"
            ).read_text(encoding="utf-8"))

            snapshots: dict[str, dict[str, object]] = {}
            for scope in ("content", "saves", "settings_support"):
                code, stdout, stderr = invoke_machine([
                    "--workspace", str(workspace), "presentation", "query", scope, "--json",
                ])
                self.assertEqual((code, stderr), (0, ""), stdout)
                snapshot = json.loads(stdout)["payload"]
                jsonschema.Draft202012Validator(schema).validate(snapshot)
                self.assertEqual(snapshot["page"]["scope"], scope)
                self.assertEqual(snapshot["freshness"]["refresh_kind"], "repository_read_no_scan")
                self.assertFalse(snapshot["selected_context"]["workspace_mutated"])
                snapshots[scope] = snapshot

            self.assertIn(
                "profile:gui",
                {item["id"] for item in snapshots["content"]["page"]["items"]},
            )
            self.assertIn(
                "no_instance_selected",
                {item["code"] for item in snapshots["saves"]["specific_blockers"]},
            )
            self.assertIn(
                "preferred_transport",
                {item["id"] for item in snapshots["settings_support"]["page"]["items"]},
            )
            settings = snapshots["settings_support"]
            self.assertEqual(settings["workspace_health"]["status"], "uninitialized")
            self.assertFalse(settings["workspace_health"]["initialized"])
            self.assertEqual(
                {"doctor.run", "workspace.initialize"},
                {action["action_id"] for action in settings["available_semantic_actions"]}
                & {"doctor.run", "workspace.initialize"},
            )
            self.assertEqual(before, tree(workspace))

    def test_workspace_initialization_is_explicit_replayable_and_doctor_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-onboarding-") as temporary:
            workspace = Path(temporary) / "workspace"
            query = [
                "--workspace", str(workspace), "presentation", "query",
                "settings_support", "--json",
            ]
            code, stdout, stderr = invoke_machine(query)
            self.assertEqual((code, stderr), (0, ""), stdout)
            snapshot = json.loads(stdout)["payload"]
            self.assertFalse(workspace.exists())
            self.assertFalse(snapshot["workspace_health"]["initialized"])

            doctor = [
                "--workspace", str(workspace), "presentation", "action",
                "doctor.run", "--scope", "settings_support",
                "--expected-revision", snapshot["revision"],
                "--request-id", "request-doctor-onboarding", "--json",
            ]
            code, stdout, stderr = invoke_machine(doctor)
            self.assertEqual((code, stderr), (0, ""), stdout)
            diagnosis = json.loads(stdout)["payload"]
            self.assertEqual(
                diagnosis["action_payload"]["schema"],
                "factorio.diagnostic_report.v1",
            )
            self.assertFalse(workspace.exists())

            initialize = [
                "--workspace", str(workspace), "presentation", "action",
                "workspace.initialize", "--scope", "settings_support",
                "--expected-revision", snapshot["revision"],
                "--request-id", "request-workspace-initialize",
                "--idempotency-key", "idempotency-workspace-initialize",
                "--operation-id", "operation-workspace-initialize",
                "--attempt-id", "attempt-workspace-initialize",
                "--confirmation", "explicit", "--json",
            ]
            code, initialized, stderr = invoke_machine(initialize)
            self.assertEqual((code, stderr), (0, ""), initialized)
            payload = json.loads(initialized)["payload"]
            self.assertEqual(payload["outcome"], "completed")
            self.assertEqual(
                payload["action_payload"]["schema"],
                "facman.workspace_initialization.v1",
            )
            self.assertTrue(payload["replacement_snapshot"]["workspace_health"]["initialized"])
            self.assertTrue(workspace.is_dir())

            code, replay, stderr = invoke_machine(initialize)
            self.assertEqual((code, stderr, replay), (0, "", initialized))
            code, stdout, stderr = invoke_machine(query)
            self.assertEqual((code, stderr), (0, ""), stdout)
            refreshed = json.loads(stdout)["payload"]
            self.assertTrue(refreshed["workspace_health"]["initialized"])
            self.assertNotIn(
                "workspace.initialize",
                {action["action_id"] for action in refreshed["available_semantic_actions"]},
            )

    def test_query_is_deterministic_read_only_schema_valid_and_transport_equivalent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-") as temporary:
            workspace = Path(temporary) / "workspace"
            before = tree(workspace)
            arguments = [
                "--workspace", str(workspace), "presentation", "query",
                "launch_deck", "--instance", "main", "--json",
            ]
            code, stdout, stderr = invoke_machine(arguments)
            self.assertEqual((code, stderr), (0, ""), stdout)
            envelope = json.loads(stdout)
            snapshot = envelope["payload"]
            schema = json.loads((
                ROOT / "contracts/schema/presentation/presentation_snapshot.v1.schema.json"
            ).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(snapshot)
            self.assertEqual(snapshot["freshness"]["refresh_kind"], "repository_read_no_scan")
            self.assertFalse(snapshot["selected_context"]["workspace_mutated"])
            self.assertEqual(snapshot["last_run"]["authority_state"], "no_record")
            self.assertEqual(
                snapshot["last_run"]["provider_id"],
                "ulk.session.journal.v1.authoritative",
            )

            code, repeated, stderr = invoke_machine(arguments)
            self.assertEqual((code, stderr), (0, ""), repeated)
            self.assertEqual(snapshot, json.loads(repeated)["payload"])
            self.assertEqual(before, tree(workspace))

            request = {
                "schema": "facman.transport_request.v2",
                "protocol_version": 2,
                "request_id": "presentation-parity",
                "operation_id": "presentation-parity-operation",
                "attempt_id": "presentation-parity-attempt",
                "workspace": str(workspace),
                "command": "presentation.query",
                "dry_run": True,
                "payload": {"scope": "launch_deck", "selected_instance_id": "main"},
            }
            transported = subprocess.run(
                [str(facman_executable()), "rpc", "--stdio"],
                cwd=ROOT,
                input=json.dumps(request),
                text=True,
                encoding="utf-8",
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            self.assertEqual((transported.returncode, transported.stderr), (0, ""), transported.stdout)
            self.assertEqual(json.loads(transported.stdout)["payload"], snapshot)

    def test_refresh_stale_revision_and_explicit_scan_action(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-action-") as temporary:
            workspace = Path(temporary) / "workspace"
            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query", "installations", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            revision = json.loads(stdout)["payload"]["revision"]

            common = [
                "--workspace", str(workspace), "presentation", "action",
                "presentation.refresh", "--scope", "installations",
                "--request-id", "request-1", "--json",
            ]
            code, stdout, stderr = invoke_machine([
                *common, "--expected-revision", "0" * 64,
            ])
            self.assertEqual((code, stderr), (1, ""), stdout)
            refusal = json.loads(stdout)
            self.assertEqual(refusal["outcome"], "conflict")
            self.assertEqual(refusal["error"]["code"], "stale_snapshot_revision")
            self.assertEqual(refusal["payload"]["outcome"], "refused_before_effects")

            launch_code, launch_stdout, launch_stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query",
                "launch_deck", "--json",
            ])
            self.assertEqual((launch_code, launch_stderr), (0, ""), launch_stdout)
            launch_revision = json.loads(launch_stdout)["payload"]["revision"]
            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "action",
                "installations.scan", "--scope", "launch_deck",
                "--expected-revision", launch_revision,
                "--request-id", "request-wrong-scope", "--json",
            ])
            self.assertEqual((code, stderr), (2, ""), stdout)
            self.assertEqual(
                json.loads(stdout)["error"]["code"],
                "semantic_action_unknown",
            )

            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "action",
                "installations.scan", "--scope", "installations",
                "--expected-revision", revision, "--request-id", "request-2",
                "--idempotency-key", "scan-1", "--root", str(workspace), "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            result = json.loads(stdout)["payload"]
            schema = json.loads((
                ROOT / "contracts/schema/presentation/semantic_action_result.v1.schema.json"
            ).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(result)
            self.assertEqual(result["outcome"], "completed")
            self.assertEqual(result["invalidation"]["reason"], "explicit_installation_scan_completed")
            self.assertIsNone(result["replacement_snapshot"])

    def test_effectful_actions_are_correlated_and_replay_across_cli_processes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-presentation-durable-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            installation = root / "factorio-fixture"
            write_installation_fixture(installation)

            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query",
                "installations", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            revision = json.loads(stdout)["payload"]["revision"]
            register = [
                "--workspace", str(workspace), "presentation", "action",
                "installation.register_read_only", "--scope", "installations",
                "--expected-revision", revision,
                "--request-id", "request-register-fixture",
                "--idempotency-key", "idempotency-register-fixture",
                "--operation-id", "operation-register-fixture",
                "--attempt-id", "attempt-register-fixture",
                "--confirmation", "explicit",
                "--installation", "fixture-read-only",
                "--installation-path", str(installation),
                "--json",
            ]
            code, first, stderr = invoke_machine(register)
            self.assertEqual((code, stderr), (0, ""), first)
            first_envelope = json.loads(first)
            self.assertEqual(first_envelope["request_id"], "request-register-fixture")
            self.assertEqual(
                first_envelope["operation"]["operation_id"],
                "operation-register-fixture",
            )
            self.assertEqual(
                first_envelope["operation"]["attempt_id"],
                "attempt-register-fixture",
            )
            self.assertEqual(first_envelope["payload"]["outcome"], "completed")

            code, projected, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query",
                "installations", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), projected)
            installation_snapshot = json.loads(projected)["payload"]
            self.assertEqual(
                installation_snapshot["freshness"]["refresh_kind"],
                "repository_and_registered_install_observation",
            )
            identity = installation_snapshot["page"]["items"][0]
            self.assertEqual(identity["installation_id"], "fixture-read-only")
            self.assertEqual(identity["ownership"], "imported")
            self.assertEqual(identity["root"], str(installation.resolve()))
            self.assertEqual(identity["installation_layout"], "portable_archive")
            self.assertEqual(identity["data_routing"], "install_local")
            self.assertEqual(identity["strict_isolation_eligibility"], "candidate")

            code, replay, stderr = invoke_machine(register)
            self.assertEqual((code, stderr, replay), (0, "", first))
            receipt_root = workspace / ".facman" / "action-receipts-v2"
            self.assertTrue(receipt_root.is_dir())
            receipts = list(receipt_root.glob("*.v2.json"))
            self.assertEqual(len(receipts), 1)
            receipt_path = receipts[0]
            receipt_text = receipt_path.read_text(encoding="utf-8")
            receipt = json.loads(receipt_text)
            receipt_schema = json.loads((
                ROOT / "contracts/schema/presentation/presentation_action_receipt.v2.schema.json"
            ).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(receipt_schema).validate(receipt)
            self.assertEqual(receipt["key_digest"], hashlib.sha256(
                receipt["idempotency_key"].encode("utf-8")
            ).hexdigest())
            self.assertEqual(receipt["result_length"], len(
                receipt["result_json"].encode("utf-8")
            ))
            self.assertEqual(receipt["result_digest"], hashlib.sha256(
                receipt["result_json"].encode("utf-8")
            ).hexdigest())
            self.assertEqual(receipt["effect_set"], json.loads(
                receipt["result_json"]
            )["effects"])

            def assert_receipt_refused(mutated: str) -> None:
                receipt_path.write_text(mutated, encoding="utf-8")
                invalid_code, invalid_stdout, invalid_stderr = invoke_machine(register)
                self.assertEqual((invalid_code, invalid_stderr), (3, ""), invalid_stdout)
                self.assertEqual(
                    json.loads(invalid_stdout)["error"]["code"],
                    "idempotency_receipt_invalid",
                )
                receipt_path.write_text(receipt_text, encoding="utf-8")

            unknown_field = dict(receipt)
            unknown_field["future_field"] = True
            assert_receipt_refused(json.dumps(unknown_field, separators=(",", ":")))
            future_schema = dict(receipt)
            future_schema["schema"] = "facman.presentation_action_receipt.v3"
            assert_receipt_refused(json.dumps(future_schema, separators=(",", ":")))
            assert_receipt_refused(
                '{"schema":"facman.presentation_action_receipt.v2",' + receipt_text.lstrip()[1:]
            )
            assert_receipt_refused("x" * (8 * 1024 * 1024 + 1))

            symlink_target = receipt_root / "receipt-substitution-target.json"
            symlink_target.write_text(receipt_text, encoding="utf-8")
            try:
                receipt_path.unlink()
                os.symlink(symlink_target, receipt_path)
            except OSError:
                receipt_path.write_text(receipt_text, encoding="utf-8")
            else:
                invalid_code, invalid_stdout, invalid_stderr = invoke_machine(register)
                self.assertEqual((invalid_code, invalid_stderr), (3, ""), invalid_stdout)
                self.assertEqual(
                    json.loads(invalid_stdout)["error"]["code"],
                    "idempotency_receipt_invalid",
                )
                receipt_path.unlink()
                receipt_path.write_text(receipt_text, encoding="utf-8")
            finally:
                symlink_target.unlink(missing_ok=True)

            pending = dict(receipt)
            pending_result = json.loads(pending["result_json"])
            pending_result["outcome"] = "outcome_unknown"
            pending_result["operation"]["outcome"] = "outcome_unknown"
            pending_result["problems"] = [{
                "code": "semantic_action_dispatch_uncertain",
                "summary": "Accepted action awaits durable finalization",
                "detail": None,
            }]
            pending_json = json.dumps(pending_result, separators=(",", ":"))
            pending["state"] = "accepted_outcome_unknown"
            pending["result_json"] = pending_json
            pending["result_length"] = len(pending_json.encode("utf-8"))
            pending["result_digest"] = hashlib.sha256(
                pending_json.encode("utf-8")
            ).hexdigest()
            receipt_path.write_text(json.dumps(pending, separators=(",", ":")), encoding="utf-8")
            unknown_code, unknown_stdout, unknown_stderr = invoke_machine(register)
            self.assertEqual((unknown_code, unknown_stderr), (4, ""), unknown_stdout)
            unknown_envelope = json.loads(unknown_stdout)
            self.assertEqual(unknown_envelope["outcome"], "outcome_unknown")
            self.assertEqual(unknown_envelope["payload"]["outcome"], "outcome_unknown")
            self.assertEqual(unknown_envelope["operation"]["outcome"], "outcome_unknown")
            receipt_path.write_text(receipt_text, encoding="utf-8")

            conflict = list(register)
            conflict[conflict.index("request-register-fixture")] = (
                "request-register-fixture-conflict"
            )
            code, conflict_stdout, stderr = invoke_machine(conflict)
            self.assertEqual((code, stderr), (1, ""), conflict_stdout)
            self.assertEqual(
                json.loads(conflict_stdout)["error"]["code"],
                "idempotency_key_conflict",
            )

            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query",
                "instances", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            revision = json.loads(stdout)["payload"]["revision"]
            create = [
                "--workspace", str(workspace), "presentation", "action",
                "instance.create_isolated", "--scope", "instances",
                "--expected-revision", revision,
                "--request-id", "request-create-fixture",
                "--idempotency-key", "idempotency-create-fixture",
                "--operation-id", "operation-create-fixture",
                "--attempt-id", "attempt-create-fixture",
                "--confirmation", "explicit",
                "--installation", "fixture-read-only",
                "--new-instance", "fixture-isolated",
                "--display-name", "Fixture Isolated",
                "--json",
            ]
            code, created, stderr = invoke_machine(create)
            self.assertEqual((code, stderr), (0, ""), created)
            self.assertEqual(json.loads(created)["payload"]["outcome"], "completed")
            code, replayed, stderr = invoke_machine(create)
            self.assertEqual((code, stderr, replayed), (0, "", created))

            code, stdout, stderr = invoke_machine([
                "--workspace", str(workspace), "presentation", "query",
                "launch_deck", "--instance", "fixture-isolated", "--json",
            ])
            self.assertEqual((code, stderr), (0, ""), stdout)
            selected = json.loads(stdout)["payload"]["selected_context"]
            self.assertEqual(selected["instance_id"], "fixture-isolated")
            self.assertEqual(selected["display_name"], "Fixture Isolated")
            self.assertEqual(selected["installation_id"], "fixture-read-only")


if __name__ == "__main__":
    unittest.main()
