# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""F11 partial preparation regression; does not admit game execution."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from native_cli import facman_executable, invoke_machine
from test_configuration_reconciliation import ExistingConfigurationTests
from test_local_modset_solver import snapshot
from test_selected_save_preparation import SelectedSavePreparationTests
from tools.winforms_build import msbuild_executable
from test_presentation_profile_preparation import factorio_validator


@unittest.skipUnless(os.name == "nt", "unsupported: preparation owners are Windows qualified")
class MakeReadyPreparationTests(unittest.TestCase):
    prepare = ExistingConfigurationTests.prepare
    query = ExistingConfigurationTests.query

    def workspace(self, variable: str, prefix: str) -> Path:
        if variable in os.environ:
            workspace = Path(os.environ[variable])
            workspace.mkdir(exist_ok=False)
            return workspace
        directory = tempfile.TemporaryDirectory(prefix=prefix)
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def preserved_inputs(self, instance: Path) -> dict[str, bytes]:
        effects = {"config/config.ini", "metadata/save-refs/selected.zip.save-ref.v1.json"}
        return {p.relative_to(instance).as_posix(): p.read_bytes()
                for p in instance.rglob("*") if p.is_file()
                and p.relative_to(instance).as_posix() not in effects
                and "locks" not in p.relative_to(instance).parts
                and not p.name.startswith(".facman-test-")}

    def arguments(self, workspace: Path, revision: str, identity: str, intent="load_save") -> list[str]:
        return ["--workspace", str(workspace), "presentation", "action", "readiness.prepare",
                "--scope", "instances", "--instance", "main", "--intent", intent,
                "--expected-revision", revision, "--request-id", identity,
                "--idempotency-key", identity, "--operation-id", identity,
                "--attempt-id", identity, "--confirmation", "explicit", "--json"]

    def action(self, args: list[str], component: str) -> dict:
        code, out, err = invoke_machine(args)
        self.assertEqual((0, ""), (code, err), out)
        result = json.loads(out)["payload"]
        self.assertEqual("completed", result["outcome"])
        payload = result["action_payload"]
        factorio_validator("factorio_make_ready_preparation_result.v1.schema.json").validate(payload)
        self.assertEqual("partial", payload["composition"])
        self.assertFalse(payload["execution_started"])
        self.assertFalse(payload["permit_issued"])
        self.assertFalse(payload["readiness_complete"])
        self.assertTrue(payload["fresh_revision_required"])
        self.assertEqual(1, len(payload["completed_components"]))
        effect = payload["completed_components"][0]
        self.assertEqual(component, effect["component"])
        self.assertTrue(effect["transaction_id"])
        self.assertEqual(effect["transaction_id"], effect["owner_result"]["transaction_id"])
        self.assertEqual("main", effect["owner_result"]["instance_id"])
        owners = [json.loads(p.read_bytes()) for p in
                  (Path(args[1]) / "transactions").glob("*.transaction.v1.json")]
        matching = [r for r in owners if r["transaction_id"] == effect["transaction_id"]]
        self.assertEqual(1, len(matching))
        owner = matching[0]
        self.assertEqual(effect["owner_command"], owner["command_id"])
        self.assertEqual("complete", owner["state"])
        return result

    def test_ordinary_revision_bound_preparation_preserves_custom_inputs(self) -> None:
        workspace = self.workspace("FACMAN_MAKE_READY_FIXTURE_ROOT", "make-ready-selected-")
        instance, _, expected = self.prepare(workspace, "load_save", raw=True, crlf=True)
        target = instance / "config/config.ini"
        identity = (target.stat().st_dev, target.stat().st_ino)
        inputs = self.preserved_inputs(instance)
        sidecar = instance / "metadata/save-refs/selected.zip.save-ref.v1.json"
        self.assertFalse(sidecar.exists())
        before = snapshot(workspace)
        initial = self.query(workspace, "instances", "load_save")
        self.assertEqual(before, snapshot(workspace), "Planning must remain read-only")
        descriptor = next((a for a in initial["available_semantic_actions"]
                           if a["action_id"] == "readiness.prepare"), None)
        self.assertIsNotNone(descriptor, "Ordinary Make Ready action readiness.prepare is missing")
        self.assertEqual("available", descriptor["availability"])
        self.assertEqual(["workspace_write"], descriptor["effects"])
        self.assertEqual("explicit", descriptor["confirmation"])

        first_args = self.arguments(workspace, initial["revision"], "make-ready-routing")
        first = self.action(first_args, "routing_configuration")
        self.assertEqual([{"component": "selected_save_declared_context", "reason": "fresh_revision_required"}],
                         first["action_payload"]["deferred_components"])
        self.assertEqual(expected, target.read_bytes())
        self.assertEqual(identity, (target.stat().st_dev, target.stat().st_ino))
        self.assertEqual(inputs, self.preserved_inputs(instance))
        self.assertFalse(sidecar.exists(), "New selected-world planning requires fresh admission")
        self.assertFalse(first["replacement_snapshot"]["readiness"]["execution_available"])

        current = self.query(workspace, "instances", "load_save")
        self.assertNotEqual(initial["revision"], current["revision"])
        fresh = next(a for a in current["available_semantic_actions"] if a["action_id"] == "readiness.prepare")
        self.assertEqual("available", fresh["availability"])
        selected_plan = current["dependency_identities"]["selected_save_preparation"]["plan"]
        second = self.action(self.arguments(workspace, current["revision"], "make-ready-selected-world"),
                             "selected_save_declared_context")
        self.assertEqual([], second["action_payload"]["deferred_components"])
        document = json.loads(sidecar.read_bytes())
        factorio_validator("factorio_save_ref.v1.schema.json").validate(document)
        self.assertEqual(str(sidecar), selected_plan["target"])
        self.assertEqual(selected_plan["selected_save"] + ".save-ref.v1.json", sidecar.name)
        self.assertEqual(hashlib.sha256((instance / "saves" / selected_plan["selected_save"]).read_bytes()).hexdigest(),
                         document["save_sha256"])
        self.assertEqual(selected_plan["profile_id"], document["profile_id"])
        registry = json.loads((instance / "instance.v1.json").read_bytes())
        self.assertEqual(registry["factorio_version"], document["factorio_version"])
        lock = instance / "mods/modset-lock.v1.json"
        self.assertEqual(hashlib.sha256(lock.read_bytes()).hexdigest(), document["modset_lock_sha256"])
        self.assertEqual("readiness.prepare_selected_save", document["source_operation"])
        self.assertEqual(inputs, self.preserved_inputs(instance))
        self.assertEqual(expected, target.read_bytes())
        self.assertFalse(second["replacement_snapshot"]["readiness"]["execution_available"])
        self.assertEqual("unavailable", second["replacement_snapshot"]["readiness"]["play_authority_state"])
        frozen = snapshot(workspace)
        self.assertEqual(first, self.action(first_args, "routing_configuration"))
        self.assertEqual(frozen, snapshot(workspace), "Exact old receipt replay must not write again")

    def test_menu_preparation_preserves_genuinely_absent_overrides(self) -> None:
        workspace = self.workspace("FACMAN_MAKE_READY_ABSENT_FIXTURE_ROOT", "make-ready-menu-")
        instance, _, expected = self.prepare(workspace, "menu", raw=False)
        override = instance / "instance-overrides.v1.json"
        self.assertFalse(override.exists())
        inputs = self.preserved_inputs(instance)
        current = self.query(workspace, "instances", "menu")
        result = self.action(self.arguments(workspace, current["revision"], "make-ready-menu", "menu"),
                             "routing_configuration")
        self.assertEqual([], result["action_payload"]["deferred_components"])
        self.assertFalse(override.exists())
        self.assertEqual(inputs, self.preserved_inputs(instance))
        self.assertEqual(expected, (instance / "config/config.ini").read_bytes())

    def test_admission_refusals_preserve_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="make-ready-admission-") as value:
            workspace = Path(value)
            instance, _, _ = self.prepare(workspace, "load_save", raw=True)
            initial = self.query(workspace, "instances", "load_save")
            arguments = self.arguments(workspace, initial["revision"], "make-ready-refusal")
            without_confirmation = arguments.copy()
            index = without_confirmation.index("--confirmation")
            del without_confirmation[index:index + 2]
            frozen = snapshot(workspace)
            code, out, err = invoke_machine(without_confirmation)
            self.assertEqual((1, ""), (code, err), out)
            self.assertEqual("semantic_action_effect_confirmation_required", json.loads(out)["error"]["code"])
            self.assertEqual(frozen, snapshot(workspace))
            # Dry-run is a transport input, rather than a CLI command option.
            request = {
                "schema": "facman.transport_request.v2", "protocol_version": 2,
                "request_id": "make-ready-dry-run", "operation_id": "make-ready-dry-run-operation",
                "attempt_id": "make-ready-dry-run-attempt", "workspace": str(workspace),
                "command": "presentation.action", "dry_run": True,
                "payload": {
                    "action_id": "readiness.prepare", "scope": "instances", "selected_instance_id": "main",
                    "launch_intent": "load_save", "expected_snapshot_revision": initial["revision"],
                    "request_id": "make-ready-dry-run", "idempotency_key": "make-ready-dry-run",
                    "durable_operation_id": "make-ready-dry-run-operation",
                    "attempt_id": "make-ready-dry-run-attempt",
                    "confirmation": "explicit",
                },
            }
            transported = subprocess.run(
                [str(facman_executable()), "--workspace", str(workspace), "rpc", "--stdio"],
                input=json.dumps(request), encoding="utf-8", check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45,
            )
            self.assertEqual((1, ""), (transported.returncode, transported.stderr), transported.stdout)
            response = json.loads(transported.stdout)
            self.assertEqual("presentation.action", response["command"])
            self.assertEqual(request["request_id"], response["request_id"])
            self.assertEqual("semantic_action_effect_confirmation_required", response["error"]["code"])
            self.assertEqual("refused_before_effects", response["payload"]["outcome"])
            self.assertEqual(request["request_id"], response["payload"]["request_id"])
            self.assertEqual(request["operation_id"], response["payload"]["operation"]["operation_id"])
            self.assertEqual(request["attempt_id"], response["payload"]["operation"]["attempt_id"])
            self.assertEqual(frozen, snapshot(workspace))
            override = instance / "instance-overrides.v1.json"
            override.write_bytes(override.read_bytes() + b"\n")
            frozen = snapshot(workspace)
            code, out, err = invoke_machine(arguments)
            self.assertEqual((1, ""), (code, err), out)
            self.assertEqual("stale_snapshot_revision", json.loads(out)["error"]["code"])
            self.assertEqual(frozen, snapshot(workspace))
            # Ambiguous operator settings are not a satisfied routing observation.
            (instance / "config/config.ini").write_bytes(
                b"[path]\nread-data=X\nread-data=Y\nwrite-data=Z\n")
            current = self.query(workspace, "instances", "load_save")
            descriptor = next(a for a in current["available_semantic_actions"] if a["action_id"] == "readiness.prepare")
            self.assertEqual("refused", descriptor["availability"])
            frozen = snapshot(workspace)
            code, out, err = invoke_machine(self.arguments(workspace, current["revision"], "make-ready-ambiguous"))
            self.assertEqual((1, ""), (code, err), out)
            self.assertEqual(descriptor["refusal"]["code"], json.loads(out)["error"]["code"])
            self.assertEqual(frozen, snapshot(workspace))

    def test_conflicting_attempt_cannot_reuse_completed_action_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="make-ready-conflict-") as value:
            workspace = Path(value)
            self.prepare(workspace, "load_save", raw=True)
            initial = self.query(workspace, "instances", "load_save")
            args = self.arguments(workspace, initial["revision"], "make-ready-conflict")
            self.action(args, "routing_configuration")
            changed = args.copy()
            changed[changed.index("--attempt-id") + 1] = "different-attempt"
            frozen = snapshot(workspace)
            code, out, err = invoke_machine(changed)
            self.assertEqual((1, ""), (code, err), out)
            self.assertEqual("idempotency_key_conflict", json.loads(out)["error"]["code"])
            self.assertEqual(frozen, snapshot(workspace))

    def test_each_interrupted_owner_recovers_without_replaying_unknown_dispatch(self) -> None:
        for component, command, seam, phase in [
            ("routing_configuration", "readiness.prepare_configuration", "FACMAN_TEST_CONFIGURATION_EXIT", "rewrite_after_prefix"),
            ("selected_save_declared_context", "readiness.prepare_selected_save", "FACMAN_TEST_SELECTED_CONTEXT_EXIT", "before_publication")]:
            with self.subTest(component=component), tempfile.TemporaryDirectory(prefix="make-ready-recovery-") as value:
                workspace = Path(value)
                instance, _, expected = self.prepare(workspace, "load_save", raw=True)
                inputs = self.preserved_inputs(instance)
                target = instance / "config/config.ini"
                identity = (target.stat().st_dev, target.stat().st_ino)
                if component == "selected_save_declared_context":
                    initial = self.query(workspace, "instances", "load_save")
                    self.action(self.arguments(workspace, initial["revision"], "make-ready-routing-first"), "routing_configuration")
                initial = self.query(workspace, "instances", "load_save")
                args = self.arguments(workspace, initial["revision"], "make-ready-loss")
                code, out, err = invoke_machine(args, env=dict(os.environ, **{seam: phase}))
                self.assertEqual((74, ""), (code, err), out)
                owners = [json.loads(p.read_bytes()) for p in (workspace / "transactions").glob("*.transaction.v1.json")]
                owner = next(r for r in owners if r["command_id"] == command)
                self.assertNotEqual("complete", owner["state"])
                frozen = snapshot(workspace)
                code, unknown, err = invoke_machine(args)
                self.assertEqual((4, ""), (code, err), unknown)
                self.assertEqual("outcome_unknown", json.loads(unknown)["payload"]["outcome"])
                self.assertEqual(frozen, snapshot(workspace), "An uncertain receipt must not re-dispatch its owner")
                code, recovered = ExistingConfigurationTests.recover(self, workspace, owner)
                self.assertEqual(0, code, recovered)
                self.assertEqual(expected, target.read_bytes())
                self.assertEqual(identity, (target.stat().st_dev, target.stat().st_ino))
                self.assertEqual(inputs, self.preserved_inputs(instance))
                frozen = snapshot(workspace)
                code, replay, err = invoke_machine(args)
                self.assertEqual((4, ""), (code, err), replay)
                self.assertEqual(unknown, replay)
                self.assertEqual(frozen, snapshot(workspace))
                current = self.query(workspace, "instances", "load_save")
                if component == "routing_configuration":
                    self.action(self.arguments(workspace, current["revision"], "make-ready-world-after-recovery"),
                                "selected_save_declared_context")
                else:
                    self.assertEqual("satisfied", current["readiness"]["selected_save"]["state"])

    def test_compiled_preparation_controls_preserve_actual_receipts_in_all_modes(self) -> None:
        # One compiled harness checks the new button and both existing modes.
        # Gallery clicks plus separately supplied receipts do not prove live dispatch.
        with tempfile.TemporaryDirectory(prefix="make-ready-controls-") as value:
            root = Path(value)
            repository = Path(__file__).resolve().parents[1]
            project = repository / "tests/winforms_control_gallery/FacMan.SelectedSave.Harness.csproj"
            build = subprocess.run([msbuild_executable(), str(project), "/m:2", "/nr:false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={root / 'bin'}{os.sep}",
                f"/p:IntermediateOutputPath={root / 'obj'}{os.sep}", f"/p:BaseIntermediateOutputPath={root / 'obj'}{os.sep}"],
                cwd=repository, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            scopes = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")
            for mode, action in (("make-ready", "readiness.prepare"),
                                 ("configuration", "readiness.prepare_configuration"),
                                 ("selected-save", "readiness.prepare_selected_save")):
                with self.subTest(mode=mode):
                    workspace = root / mode
                    if mode == "selected-save":
                        SelectedSavePreparationTests.prepare(self, workspace)
                    else:
                        self.prepare(workspace, "load_save", raw=True, crlf=True)
                    gallery = root / (mode + "-gallery.json")
                    gallery.write_text(json.dumps(dict(schema="facman.control_gallery_case.v1", state="blocked",
                        variant="make-ready-component", observed_at="2026-10-10T00:00:00Z",
                        snapshots={scope: self.query(workspace, scope, "load_save") for scope in scopes})) + "\n", encoding="utf-8")
                    args = self.arguments(workspace, self.query(workspace, "instances", "load_save")["revision"], "control-" + mode)
                    args[args.index("action") + 1] = action
                    code, out, err = invoke_machine(args)
                    self.assertEqual((0, ""), (code, err), out)
                    if mode == "make-ready":
                        result = json.loads(out)["payload"]["action_payload"]
                        factorio_validator("factorio_make_ready_preparation_result.v1.schema.json").validate(result)
                        self.assertEqual("partial", result["composition"])
                        self.assertFalse(result["readiness_complete"])
                    receipt = root / (mode + "-receipt.json")
                    receipt.write_text(out, encoding="utf-8")
                    before = snapshot(workspace)
                    command = [str(root / "bin/FacMan.SelectedSave.Harness.exe"), str(gallery), str(receipt)]
                    if mode != "selected-save": command.append(mode)
                    run = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                         encoding="utf-8", errors="replace", timeout=60)
                    self.assertEqual(0, run.returncode, run.stdout + run.stderr)
                    self.assertEqual(1, run.stdout.count("PASS "))
                    self.assertEqual(before, snapshot(workspace))
