# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
import jsonschema
from pathlib import Path

import test_readiness_builtin_content as fixtures
from native_cli import invoke_machine
from test_local_modset_solver import call, snapshot
from test_save_index_retention import write_save
from test_presentation_profile_preparation import factorio_validator
from tools.winforms_build import msbuild_executable


class SelectedSavePreparationTests(unittest.TestCase):
    def prepare(self, workspace: Path) -> Path:
        instance, _ = fixtures.ReadinessBuiltinContentTests.prepare(self, workspace, mixed=True)
        write_save(instance / "saves/selected.zip", b"selected world")
        write_save(instance / "saves/selected-other.zip", b"unselected world")
        call(workspace, "profiles", "apply", "main", "gui", "--selection-mode", "load-save",
             "--selection", "selected.zip", "--arg", "--low-vram")
        return instance

    def query(self, workspace: Path, scope: str = "instances", intent: str = "load_save") -> dict:
        return fixtures.ReadinessBuiltinContentTests.query(self, workspace, scope, intent)

    def arguments(self, workspace: Path, revision: str, identity: str = "prepare", scope: str = "instances",
                  intent: str = "load_save", confirmation: str = "explicit") -> list[str]:
        args = ["--workspace", str(workspace), "presentation", "action", "readiness.prepare_selected_save",
                "--scope", scope, "--instance", "main", "--intent", intent, "--expected-revision", revision,
                "--request-id", identity, "--idempotency-key", identity, "--operation-id", identity,
                "--attempt-id", identity, "--json"]
        if confirmation != "none": args.extend(["--confirmation", confirmation])
        return args

    def journal(self, workspace: Path) -> tuple[Path, dict]:
        matches = [(path, json.loads(path.read_text())) for path in
                   (workspace / "transactions").glob("*.transaction.v1.json")]
        return next(item for item in matches if item[1]["command_id"] == "readiness.prepare_selected_save")

    def recover(self, workspace: Path, transaction: dict) -> tuple[int, dict]:
        code, out, err = invoke_machine(["--workspace", str(workspace), "workspace", "recovery", "apply",
                                      transaction["transaction_id"], "--json"])
        self.assertEqual("", err, out)
        output = json.loads(out)
        if code == 0:
            schema = json.loads((Path(__file__).resolve().parents[1] /
                "contracts/schema/facman/facman_workspace_recovery.v1.schema.json").read_text())
            jsonschema.Draft202012Validator(schema).validate(output["payload"])
            self.assertEqual("workspace.recovery.apply", output["payload"]["command"])
            self.assertEqual(1, len(output["payload"]["transactions"]))
            self.assertEqual(transaction["transaction_id"], output["payload"]["transactions"][0]["transaction_id"])
            self.assertEqual("complete", output["payload"]["transactions"][0]["state"])
        return code, output

    def preserved(self, instance: Path) -> dict[str, bytes]:
        return {path.relative_to(instance).as_posix(): path.read_bytes() for path in instance.rglob("*")
                if path.is_file() and "metadata" not in path.relative_to(instance).parts and
                not path.name.startswith(".facman-test-") and "locks" not in path.relative_to(instance).parts}

    def test_query_is_read_only_and_host_capability_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="selected-context-plan-") as value:
            workspace = Path(value)
            self.prepare(workspace)
            before = snapshot(workspace)
            for intent in ("menu", "load_save"):
                projected = self.query(workspace, intent=intent)
                descriptor = next(a for a in projected["available_semantic_actions"]
                                  if a["action_id"] == "readiness.prepare_selected_save")
                identity = projected["dependency_identities"]["selected_save_preparation"]
                available = os.name == "nt" and intent == "load_save"
                self.assertEqual("available" if available else "refused", descriptor["availability"])
                if available:
                    plan = identity["plan"]
                    factorio_validator("factorio_selected_save_preparation_plan.v1.schema.json").validate(plan)
                    self.assertEqual("selected.zip", plan["selected_save"])
                    self.assertEqual("partial", plan["composition"])
                else:
                    self.assertIsNone(identity["plan"])
                    self.assertIsInstance(identity["refusal"]["code"], str)
                self.assertFalse(projected["readiness"]["preparation_available"])
                self.assertFalse(projected["readiness"]["execution_available"])
            self.assertEqual(before, snapshot(workspace))

    @unittest.skipUnless(os.name == "nt", "unsupported: selected context publication is qualified only on Windows")
    def test_ordinary_selected_context_and_fresh_process_replay_preserve_all_selected_inputs(self) -> None:
        for scope in ("instances", "launch_deck"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory(prefix="selected-context-apply-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                before = self.preserved(instance)
                old = self.query(workspace, scope)
                self.assertEqual("degraded", old["readiness"]["selected_save"]["state"])
                args = self.arguments(workspace, old["revision"], scope=scope)
                code, out, err = invoke_machine(args)
                self.assertEqual((code, err), (0, ""), out)
                result = json.loads(out)["payload"]
                self.assertEqual("completed", result["outcome"])
                factorio_validator("factorio_selected_save_preparation_result.v1.schema.json").validate(result["action_payload"])
                ready = result["replacement_snapshot"]["readiness"]
                self.assertEqual("satisfied", ready["selected_save"]["state"])
                self.assertFalse(ready["execution_available"])
                self.assertEqual("unavailable", ready["play_authority_state"])
                self.assertEqual("partial", result["action_payload"]["composition"])
                sidecar = instance / "metadata/save-refs/selected.zip.save-ref.v1.json"
                document = json.loads(sidecar.read_text())
                self.assertEqual(hashlib.sha256((instance / "saves/selected.zip").read_bytes()).hexdigest(), document["save_sha256"])
                self.assertEqual("gui", document["profile_id"])
                self.assertEqual("readiness.prepare_selected_save", document["source_operation"])
                self.assertFalse((sidecar.parent / "selected-other.zip.save-ref.v1.json").exists())
                self.assertEqual(before, self.preserved(instance))
                frozen = snapshot(workspace)
                replay_code, replay, replay_err = invoke_machine(args)
                self.assertEqual((replay_code, replay_err), (0, ""), replay)
                self.assertEqual(result, json.loads(replay)["payload"])
                self.assertEqual(frozen, snapshot(workspace))

    @unittest.skipUnless(os.name == "nt", "unsupported: selected context publication is qualified only on Windows")
    def test_process_loss_resumes_exact_owned_effect_and_preserves_ambiguous_creation(self) -> None:
        for phase in ("after_manifest", "after_directory_create", "after_file_create",
                      "before_publication", "after_publication", "before_finalization"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(prefix="selected-context-loss-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                before = self.preserved(instance)
                old = self.query(workspace)
                code, _, _ = invoke_machine(self.arguments(workspace, old["revision"]),
                    env=dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_EXIT=phase))
                self.assertEqual(74, code)
                _, transaction = self.journal(workspace)
                target = Path(transaction["target"])
                retained = snapshot(instance / "metadata")
                recovered, output = self.recover(workspace, transaction)
                ambiguous = phase in ("after_directory_create", "after_file_create")
                self.assertEqual(3 if ambiguous else 0, recovered, output)
                if ambiguous:
                    self.assertEqual(retained, snapshot(instance / "metadata"))
                    self.assertFalse(target.exists())
                else:
                    self.assertEqual("satisfied", self.query(workspace)["readiness"]["selected_save"]["state"])
                    frozen = snapshot(workspace)
                    again, output = self.recover(workspace, transaction)
                    self.assertEqual(0, again, output)
                    self.assertEqual(frozen, snapshot(workspace))
                self.assertEqual(before, self.preserved(instance))

    @unittest.skipUnless(os.name == "nt", "unsupported: selected context publication is qualified only on Windows")
    def test_same_byte_foreign_objects_and_mismatched_strategy_are_preserved(self) -> None:
        for variant in ("stage", "target", "strategy"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix="selected-context-foreign-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                code, _, _ = invoke_machine(self.arguments(workspace, self.query(workspace)["revision"]),
                    env=dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_EXIT="before_publication"))
                self.assertEqual(74, code)
                path, transaction = self.journal(workspace)
                stage = Path(transaction["owned_staging_roots"][0])
                if variant == "strategy":
                    transaction["commit_strategy"] = "durable_sidecar_create_no_save_mutation"
                    path.write_text(json.dumps(transaction) + "\n", encoding="utf-8")
                else:
                    data = stage.read_bytes()
                    if variant == "stage":
                        stage.rename(stage.with_name(stage.name + ".preserved-original"))
                        stage.write_bytes(data)
                    else:
                        Path(transaction["target"]).write_bytes(data)
                retained = snapshot(instance)
                code, output = self.recover(workspace, transaction)
                self.assertIn(code, (1, 3), output)
                self.assertEqual(retained, snapshot(instance))

    @unittest.skipUnless(os.name == "nt", "unsupported: selected context publication is qualified only on Windows")
    def test_unsupported_selected_filenames_refuse_during_read_only_admission(self) -> None:
        for name in ("My World.zip", "selected-\u2603.zip"):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix="selected-context-name-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                write_save(instance / "saves" / name, b"supported selected archive; unsupported context leaf")
                call(workspace, "profiles", "apply", "main", "gui", "--selection-mode", "load-save", "--selection", name)
                before = snapshot(workspace)
                projected = self.query(workspace)
                identity = projected["dependency_identities"]["selected_save_preparation"]
                self.assertIsNone(identity["plan"])
                self.assertEqual("selected_context_filename_unsupported", identity["refusal"]["code"])
                self.assertEqual("degraded", projected["readiness"]["selected_save"]["state"])
                code, out, err = invoke_machine(self.arguments(workspace, projected["revision"]))
                self.assertEqual((1, ""), (code, err), out)
                self.assertEqual(before, snapshot(workspace))
                self.assertFalse((instance / "metadata").exists())

    @unittest.skipUnless(os.name == "nt", "unsupported: selected context publication is qualified only on Windows")
    def test_finalization_retains_pinned_target_against_same_byte_replacement_and_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="selected-context-final-pin-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            args = self.arguments(workspace, self.query(workspace)["revision"])
            results = []
            worker = threading.Thread(target=lambda: results.append(invoke_machine(args,
                env=dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_PAUSE="before_final_observation"))))
            worker.start()
            try:
                marker = instance / ".facman-test-selected-context-before_final_observation"
                deadline = time.monotonic() + 15
                while not marker.exists() and time.monotonic() < deadline: time.sleep(0.01)
                self.assertTrue(marker.exists(), "final target pin seam was not reached")
                target = instance / "metadata/save-refs/selected.zip.save-ref.v1.json"
                data = target.read_bytes()
                identity = target.stat().st_ino
                with self.assertRaises(PermissionError):
                    target.rename(target.with_name(target.name + ".foreign-replacement"))
                with self.assertRaises(PermissionError):
                    target.write_bytes(data)
                (instance / ".facman-test-selected-context-release").write_bytes(b"release")
                worker.join(30)
                self.assertFalse(worker.is_alive())
                self.assertEqual((0, ""), (results[0][0], results[0][2]), results)
                self.assertEqual("completed", json.loads(results[0][1])["payload"]["outcome"])
                self.assertEqual(data, target.read_bytes())
                self.assertEqual(identity, target.stat().st_ino)
            finally:
                (instance / ".facman-test-selected-context-release").write_bytes(b"release")
                worker.join(30)

    @unittest.skipUnless(os.name == "nt", "unsupported: selected context publication is qualified only on Windows")
    def test_terminal_invalid_or_missing_owned_effect_never_creates_directories_or_republishes(self) -> None:
        for state in ("complete", "refused", "cancelled", "rolled_back"):
            with self.subTest(state=state), tempfile.TemporaryDirectory(prefix="selected-context-terminal-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                code, _, _ = invoke_machine(self.arguments(workspace, self.query(workspace)["revision"]),
                    env=dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_EXIT="after_manifest"))
                self.assertEqual(74, code)
                path, transaction = self.journal(workspace)
                transaction["state"] = state
                path.write_text(json.dumps(transaction) + "\n", encoding="utf-8")
                before = snapshot(instance)
                code, output = self.recover(workspace, transaction)
                self.assertEqual(3, code, output)
                self.assertEqual(before, snapshot(instance))
                self.assertFalse((instance / "metadata").exists())
        with tempfile.TemporaryDirectory(prefix="selected-context-missing-effect-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            code, out, _ = invoke_machine(self.arguments(workspace, self.query(workspace)["revision"]))
            self.assertEqual(0, code, out)
            _, transaction = self.journal(workspace)
            target = Path(transaction["target"])
            target.rename(target.with_name(target.name + ".retained-original"))
            before = snapshot(instance)
            code, output = self.recover(workspace, transaction)
            self.assertEqual(3, code, output)
            self.assertEqual(before, snapshot(instance))
            self.assertFalse(target.exists())

    @unittest.skipUnless(os.name == "nt", "unsupported: selected context publication is qualified only on Windows")
    def test_shared_configuration_lock_preserves_empty_unfamiliar_and_borrowed_compatible_objects(self) -> None:
        for content in (b"", b"foreign owner\n", b"facman.instance_configuration_lock.v1\ninstance_id=main\n"):
            with self.subTest(content=content), tempfile.TemporaryDirectory(prefix="selected-context-lock-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                lock = instance / "locks/configuration.write.lock"
                lock.write_bytes(content)
                old = self.query(workspace)
                code, out, err = invoke_machine(self.arguments(workspace, old["revision"]))
                compatible = content.startswith(b"facman.instance_configuration_lock.v1")
                self.assertEqual((0 if compatible else 3, ""), (code, err), out)
                self.assertTrue(lock.exists())
                self.assertEqual(content, lock.read_bytes())
                if not compatible:
                    self.assertFalse((instance / "metadata").exists())

    @unittest.skipUnless(os.name == "nt", "unsupported: selected context publication is qualified only on Windows")
    def test_compiled_fixed_control_preserves_selected_intent_and_uncertain_request(self) -> None:
        with tempfile.TemporaryDirectory(prefix="selected-context-control-") as value:
            root = Path(value)
            workspace = root / "workspace"
            self.prepare(workspace)
            scopes = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")
            gallery = root / "gallery.json"
            gallery.write_text(json.dumps(dict(schema="facman.control_gallery_case.v1", state="blocked",
                variant="selected-save-component", observed_at="2026-10-08T00:00:00Z",
                snapshots={scope: self.query(workspace, scope) for scope in scopes})) + "\n", encoding="utf-8")
            code, out, err = invoke_machine(self.arguments(workspace, self.query(workspace)["revision"]))
            self.assertEqual((code, err), (0, ""), out)
            receipt = root / "receipt.json"
            receipt.write_text(out, encoding="utf-8")
            before = snapshot(workspace)
            repository = Path(__file__).resolve().parents[1]
            project = repository / "tests/winforms_control_gallery/FacMan.SelectedSave.Harness.csproj"
            build = subprocess.run([msbuild_executable(), str(project), "/m:2", "/nr:false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={root / 'bin'}{os.sep}",
                f"/p:IntermediateOutputPath={root / 'obj'}{os.sep}", f"/p:BaseIntermediateOutputPath={root / 'obj'}{os.sep}"],
                cwd=repository, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            result = subprocess.run([str(root / "bin/FacMan.SelectedSave.Harness.exe"), str(gallery), str(receipt)],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(1, result.stdout.count("PASS "))
            self.assertEqual(before, snapshot(workspace))

    @unittest.skipUnless(os.name == "nt", "unsupported: selected context publication is qualified only on Windows")
    def test_stale_inputs_confirmation_and_late_context_drift_do_not_claim_completion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="selected-context-admission-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            old = self.query(workspace)
            before = snapshot(workspace)
            code, out, _ = invoke_machine(self.arguments(workspace, old["revision"], confirmation="none"))
            self.assertEqual(1, code, out)
            self.assertEqual("semantic_action_effect_confirmation_required", json.loads(out)["error"]["code"])
            self.assertEqual(before, snapshot(workspace))
            overrides = instance / "instance-overrides.v1.json"
            overrides.write_bytes(overrides.read_bytes() + b"\n")
            before = snapshot(workspace)
            code, out, _ = invoke_machine(self.arguments(workspace, old["revision"]))
            self.assertEqual(1, code, out)
            self.assertEqual("stale_snapshot_revision", json.loads(out)["error"]["code"])
            self.assertEqual(before, snapshot(workspace))
        for phase in ("before_publication", "after_publication"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(prefix="selected-context-drift-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                results = []
                args = self.arguments(workspace, self.query(workspace)["revision"])
                worker = threading.Thread(target=lambda: results.append(invoke_machine(args,
                    env=dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_PAUSE=phase))))
                worker.start()
                try:
                    marker = instance / (".facman-test-selected-context-" + phase)
                    deadline = time.monotonic() + 15
                    while not marker.exists() and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue(marker.exists(), "publication seam was not reached")
                    journal_path, transaction = self.journal(workspace)
                    journal_bytes = journal_path.read_bytes()
                    contention, output = self.recover(workspace, transaction)
                    self.assertEqual(3, contention, output)
                    self.assertEqual("recovery_lock_contended", output["error"]["code"])
                    self.assertEqual(journal_bytes, journal_path.read_bytes())
                    overrides = instance / "instance-overrides.v1.json"
                    overrides.write_bytes(overrides.read_bytes() + b"\n")
                    (instance / ".facman-test-selected-context-release").write_bytes(b"release")
                    worker.join(30)
                    self.assertFalse(worker.is_alive())
                    self.assertEqual(3, results[0][0], results)
                    self.assertEqual("recovery_required", json.loads(results[0][1])["payload"]["outcome"])
                    target = instance / "metadata/save-refs/selected.zip.save-ref.v1.json"
                    self.assertEqual(phase == "after_publication", target.exists())
                    retained = snapshot(instance)
                    _, transaction = self.journal(workspace)
                    code, output = self.recover(workspace, transaction)
                    self.assertEqual(3, code, output)
                    self.assertEqual(retained, snapshot(instance))
                finally:
                    (instance / ".facman-test-selected-context-release").write_bytes(b"release")
                    worker.join(30)


if __name__ == "__main__":
    unittest.main()
