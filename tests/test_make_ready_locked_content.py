# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""One confirmed request reconciles the exact locked activation through its owner."""
from __future__ import annotations

import hashlib
import copy
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import test_make_ready_joined as joined
import test_readiness_content_activation as activation
from native_cli import invoke_machine
from test_local_modset_solver import call, snapshot, write_mod
from test_presentation_profile_preparation import factorio_validator
from native_cli import ROOT, facman_executable
from tools.winforms_build import msbuild_executable


class LockedContentMakeReadyTests(unittest.TestCase):
    query = joined.JoinedMakeReadyTests.query
    arguments = joined.JoinedMakeReadyTests.arguments
    journals = joined.JoinedMakeReadyTests.journals

    def prepare(self, workspace: Path, kind: str = "missing") -> Path:
        instance = activation.ContentActivationReadinessTests.prepare(self, workspace)
        path = instance / "mods/mod-list.json"
        if kind == "missing":
            path.unlink()
        else:
            path.write_text('{"mods":[{"name":"base","enabled":true},{"name":"simple","enabled":false}]}\n', encoding="utf-8")
        return instance

    def result(self, response: tuple[int, str, str], code: int = 0) -> dict:
        actual, output, error = response
        self.assertEqual((code, ""), (actual, error), output)
        value = json.loads(output)["payload"]
        payload = value["action_payload"]
        version = payload["schema"].rsplit(".", 1)[1]
        factorio_validator(f"factorio_make_ready_joined_result.{version}.schema.json").validate(payload)
        return value

    def assert_content_effect(self, workspace: Path, result: dict) -> dict:
        payload = result["action_payload"]
        effect = payload["completed_components"][0]
        self.assertEqual(("locked_content_activation", "modsets.apply"), (effect["component"], effect["owner_command"]))
        receipt = effect["owner_result"]
        journal = next(j for j in self.journals(workspace) if j["transaction_id"] == receipt["transaction_id"])
        self.assertEqual(("modsets.apply", "complete"), (journal["command_id"], journal["state"]))
        self.assertEqual(effect["transaction_id"], journal["transaction_id"])
        self.assertNotEqual(receipt["history_id"], journal["transaction_id"])
        context = json.loads(journal["operation_context"])
        self.assertEqual("factorio.locked_content_activation_commit.v1", context["schema"])
        self.assertEqual(payload["plan"]["content_plan"], context["plan"])
        self.assertEqual(result["operation"]["operation_id"], context["operation_id"])
        self.assertEqual(result["operation"]["attempt_id"], context["attempt_id"])
        self.assertEqual(receipt["effect_binding_sha256"], hashlib.sha256(journal["operation_context"].encode()).hexdigest())
        history = workspace / "instances/main/mods/.facman-modset-history" / receipt["history_id"]
        retained = json.loads((history / "activation.v1.json").read_bytes())
        self.assertEqual(receipt["history_id"], retained["transaction_id"])
        for bound, original in zip(context["effects"], retained["files"], strict=True):
            target = Path(bound["target"])
            self.assertEqual(original["target"], str(target))
            self.assertEqual(bound["sha256"], hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertTrue(bound["identity"].startswith("file:" + joined.file_identity(target) + ":"))
            if original["before_present"]:
                backup = history / (bound["key"] + ".before")
                self.assertEqual(original["before_sha256"], hashlib.sha256(backup.read_bytes()).hexdigest())
                self.assertTrue(bound["backup_identity"].startswith("file:" + joined.file_identity(backup) + ":"))
        return journal

    def test_one_confirmed_request_restores_exact_lock_then_configuration_and_selected_save(self) -> None:
        for kind in ("missing", "disabled"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="joined-content-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace, kind)
                write_mod(instance / "mods/simple_2.0.0.zip", "simple", "2.0.0")
                foreign = instance / "mods/unrelated-user-file.txt"
                foreign.write_bytes(b"preserve unrelated local content\n")
                locks = {p: p.read_bytes() for p in (instance / "mods/modset-lock.v1.json", workspace / "modsets/main.modset-lock.v1.json")}
                protected = {p: p.read_bytes() for p in instance.rglob("*") if p.is_file() and
                             (p.suffix == ".zip" or p.name in ("instance-overrides.v1.json", "mod-settings.dat", foreign.name))}
                install = snapshot(workspace / "fixture-install")
                frozen = snapshot(workspace)
                initial = self.query(workspace, "instances", "load_save")
                self.assertEqual("verification_failed", initial["readiness"]["preparation_preview"]["modset"]["status"])
                plan = initial["dependency_identities"]["joined_preparation"]["plan"]
                factorio_validator("factorio_make_ready_joined_plan.v2.schema.json").validate(plan)
                self.assertEqual(initial["revision"], self.query(workspace, "instances", "load_save")["revision"])
                self.assertEqual(frozen, snapshot(workspace))
                args = self.arguments(workspace, initial, "joined-content")
                unconfirmed = args.copy()
                offset = unconfirmed.index("--confirmation")
                del unconfirmed[offset:offset + 2]
                code, output, error = invoke_machine(unconfirmed)
                self.assertEqual((1, ""), (code, error), output)
                self.assertEqual("semantic_action_effect_confirmation_required", json.loads(output)["error"]["code"])
                self.assertEqual(frozen, snapshot(workspace))
                result = self.result(invoke_machine(args))
                self.assertEqual("completed", result["outcome"])
                payload = result["action_payload"]
                self.assertEqual(["modsets.apply", "readiness.prepare_configuration", "readiness.prepare_selected_save"],
                                 [c["owner_command"] for c in payload["completed_components"]])
                self.assertTrue(payload["content_effect_verified"])
                self.assertTrue(payload["completed_effects_verified"])
                self.assertEqual(plan["desired_state"], payload["joined_result"]["plan"]["desired_state"])
                self.assert_content_effect(workspace, result)
                joined.JoinedMakeReadyTests.assert_effects(self, workspace,
                    {**result, "action_payload": payload["joined_result"]},
                    ["readiness.prepare_configuration", "readiness.prepare_selected_save"])
                self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])
                selected = json.loads((instance / "mods/modset-lock.v1.json").read_bytes())
                self.assertEqual(["1.0.0"], [m["version"] for m in selected["mods"] if m["name"] == "simple"])
                self.assertEqual(locks, {p: p.read_bytes() for p in locks})
                self.assertEqual(protected, {p: p.read_bytes() for p in protected})
                self.assertEqual(install, snapshot(workspace / "fixture-install"))
                self.assertEqual("locked_verified", self.query(workspace, "instances", "load_save")["readiness"]["preparation_preview"]["modset"]["status"])
                frozen = snapshot(workspace)
                replay = self.result(invoke_machine(args))
                self.assertEqual(result, replay)
                self.assertEqual(payload, replay["action_payload"])
                self.assertEqual(frozen, snapshot(workspace))

    def test_content_only_pending_repair_keeps_current_configuration_save_and_healthy_v1(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-content-only-") as value:
            workspace = Path(value)
            instance = activation.ContentActivationReadinessTests.prepare(self, workspace)
            initial = self.query(workspace, "instances", "load_save")
            self.result(invoke_machine(self.arguments(workspace, initial, "initial-v1")))
            protected = {p: (p.read_bytes(), joined.file_identity(p)) for p in
                         (instance / "config/config.ini", instance / "metadata/save-refs/selected.zip.save-ref.v1.json")}
            (instance / "mods/mod-list.json").unlink()
            pending = self.query(workspace, "instances", "load_save")
            result = self.result(invoke_machine(self.arguments(workspace, pending, "content-only")))
            payload = result["action_payload"]
            self.assertEqual("completed", result["outcome"])
            self.assertEqual(["modsets.apply"], [e["owner_command"] for e in payload["completed_components"]])
            self.assertEqual([], payload["joined_result"]["completed_components"])
            self.assertFalse(payload["joined_result"]["completed_effects_verified"])
            self.assertTrue(payload["completed_effects_verified"])
            self.assert_content_effect(workspace, result)
            self.assertEqual(protected, {p: (p.read_bytes(), joined.file_identity(p)) for p in protected})
            current = self.query(workspace, "instances", "load_save")
            self.assertEqual("factorio.make_ready_joined_plan.v1", current["dependency_identities"]["joined_preparation"]["plan"]["schema"])
            ordinary = self.result(invoke_machine(self.arguments(workspace, current, "healthy-noop-v1")))
            self.assertEqual("factorio.make_ready_joined_result.v1", ordinary["action_payload"]["schema"])
            self.assertEqual([], ordinary["action_payload"]["completed_components"])

    def test_content_only_repair_keeps_association_and_archive_native_identity_protected(self) -> None:
        for kind in ("association", "archive"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="joined-content-context-id-") as value:
                workspace = Path(value)
                instance = activation.ContentActivationReadinessTests.prepare(self, workspace)
                self.result(invoke_machine(self.arguments(workspace, self.query(workspace, "instances", "load_save"), "context-initial")))
                config = instance / "config/config.ini"
                original_config = (config.read_bytes(), joined.file_identity(config))
                (instance / "mods/mod-list.json").unlink()
                args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "context-identity")
                worker = joined.PausedAction(args, dict(os.environ, FACMAN_TEST_MAKE_READY_PAUSE_AFTER_CONTENT="1"))
                release = instance / ".facman-test-make-ready-content-release"
                try:
                    joined.wait_for_owned_marker(worker, instance / ".facman-test-make-ready-after-content", release)
                    target = instance / ("metadata/save-refs/selected.zip.save-ref.v1.json" if kind == "association" else "saves/selected.zip")
                    original = target.read_bytes()
                    old_id = joined.file_identity(target)
                    target.rename(workspace / "retained-original-selected-input")
                    target.write_bytes(original)
                    foreign_id = joined.file_identity(target)
                    self.assertNotEqual(old_id, foreign_id)
                    release.touch()
                finally:
                    release.touch(exist_ok=True)
                    worker.finish()
                result = self.result(worker.response, 3)
                payload = result["action_payload"]
                self.assertEqual("fresh_request_after_input_correction", payload["continuation"])
                self.assertTrue(payload["content_effect_verified"])
                self.assertTrue(payload["completed_effects_verified"])
                self.assertEqual(["modsets.apply"], [e["owner_command"] for e in payload["completed_components"]])
                self.assertIsNone(payload["joined_result"])
                self.assertEqual((original, foreign_id), (target.read_bytes(), joined.file_identity(target)))
                self.assertEqual(original_config, (config.read_bytes(), joined.file_identity(config)))
                self.assert_content_effect(workspace, result)
                self.assertFalse(any(j["command_id"].startswith("readiness.prepare_") and
                    json.loads(j.get("operation_context") or "{}").get("operation_id") == "context-identity" for j in self.journals(workspace)))
                frozen = snapshot(workspace)
                self.assertEqual(result, self.result(invoke_machine(args), 3))
                self.assertEqual(frozen, snapshot(workspace))

    def test_identical_archive_in_earlier_instance_binds_only_selected_instance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-content-duplicate-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            record = json.loads((workspace / "instances/main/instance.v1.json").read_bytes())
            call(workspace, "instances", "create", "Earlier", "--id", "aaa", "--install", record["install_ref"])
            own = instance / "mods/simple_1.0.0.zip"
            other = workspace / "instances/aaa/mods/simple_1.0.0.zip"
            other.parent.mkdir(parents=True, exist_ok=True)
            other.write_bytes(own.read_bytes())
            foreign = snapshot(workspace / "instances/aaa")
            observation = self.query(workspace, "instances", "load_save")
            content = observation["dependency_identities"]["joined_preparation"]["plan"]["content_plan"]
            physical = [a for a in content["artifact_inputs"] if a["path"].endswith(".zip")]
            self.assertEqual([str(own)], [a["path"] for a in physical])
            self.assertTrue(physical[0]["identity"].startswith("file:" + joined.file_identity(own) + ":"))
            # A foreign duplicate's identity is outside this instance's pinned content plan.
            other.rename(other.with_suffix(".retained"))
            other.write_bytes(own.read_bytes())
            current = self.query(workspace, "instances", "load_save")
            self.assertEqual(content, current["dependency_identities"]["joined_preparation"]["plan"]["content_plan"])
            foreign = snapshot(workspace / "instances/aaa")
            result = self.result(invoke_machine(self.arguments(workspace, current, "own-archive")))
            self.assertEqual("completed", result["outcome"])
            journal = self.assert_content_effect(workspace, result)
            self.assertEqual([str(own)], journal["source_identities"])
            self.assertEqual(foreign, snapshot(workspace / "instances/aaa"))

    def test_prepublication_same_byte_stage_and_backup_replacement_requires_recovery(self) -> None:
        for kind in ("stage", "backup"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="joined-content-stage-id-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                locks = {p: p.read_bytes() for p in (instance / "mods/modset-lock.v1.json", workspace / "modsets/main.modset-lock.v1.json")}
                args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "stage-identity")
                worker = joined.PausedAction(args, dict(os.environ, FACMAN_TEST_MODSET_APPLY_BEFORE_PUBLICATION_PAUSE="1"))
                stage = None
                try:
                    deadline = time.monotonic() + 10
                    while worker.thread.is_alive() and stage is None and time.monotonic() < deadline:
                        stage = next((p for p in (instance / "mods").glob(".facman-modset-stage-*")
                                      if (p / ".facman-modset-apply-paused").is_file()), None)
                        worker.thread.join(0.01)
                    self.assertIsNotNone(stage, "content owner did not reach its publication boundary")
                    journal = next(j for j in self.journals(workspace) if j["command_id"] == "modsets.apply" and j.get("operation_context"))
                    history = Path(journal["owned_staging_roots"][1])
                    target = stage / "mod-list.json" if kind == "stage" else history / "local-lock.before"
                    original = target.read_bytes()
                    old_id = joined.file_identity(target)
                    target.rename(workspace / "retained-original-owner-input")
                    target.write_bytes(original)
                    foreign_id = joined.file_identity(target)
                    self.assertNotEqual(old_id, foreign_id)
                    release = stage / ".facman-modset-apply-release"
                    release.touch()
                finally:
                    if stage is not None: (stage / ".facman-modset-apply-release").touch(exist_ok=True)
                    worker.finish()
                result = self.result(worker.response, 3)
                self.assertEqual("recovery_required", result["outcome"])
                self.assertEqual([], result["action_payload"]["completed_components"])
                self.assertTrue(stage.is_dir())
                self.assertTrue(history.is_dir())
                self.assertEqual((original, foreign_id), (target.read_bytes(), joined.file_identity(target)))
                self.assertEqual(locks, {p: p.read_bytes() for p in locks})
                self.assertFalse((instance / "mods/mod-list.json").exists())
                self.assertFalse((instance / "config/config.ini").exists())
                self.assertFalse((instance / "metadata/save-refs/selected.zip.save-ref.v1.json").exists())
                frozen = snapshot(workspace)
                self.assertEqual(result, self.result(invoke_machine(args), 3))
                self.assertEqual(frozen, snapshot(workspace))

    def test_protected_drift_before_owner_refuses_and_during_owner_retains_only_content(self) -> None:
        for boundary in ("before", "during"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory(prefix="joined-content-guard-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "protected-guard")
                variable = "FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_CONTENT" if boundary == "before" else "FACMAN_TEST_MODSET_APPLY_BEFORE_PUBLICATION_PAUSE"
                worker = joined.PausedAction(args, dict(os.environ, **{variable: "1"}))
                release = None
                try:
                    if boundary == "before":
                        release = instance / ".facman-test-make-ready-before-content-release"
                        joined.wait_for_owned_marker(worker, instance / ".facman-test-make-ready-before-content", release)
                    else:
                        deadline = time.monotonic() + 10
                        stage = None
                        while worker.thread.is_alive() and stage is None and time.monotonic() < deadline:
                            stage = next((p for p in (instance / "mods").glob(".facman-modset-stage-*")
                                          if (p / ".facman-modset-apply-paused").is_file()), None)
                            worker.thread.join(0.01)
                        self.assertIsNotNone(stage)
                        release = stage / ".facman-modset-apply-release"
                    settings = instance / "mods/mod-settings.dat"
                    settings.write_bytes(b"external protected settings change\n")
                    release.touch()
                finally:
                    if release is not None: release.touch(exist_ok=True)
                    worker.finish()
                result = self.result(worker.response, 1 if boundary == "before" else 3)
                self.assertEqual("refused_before_effects" if boundary == "before" else "recovery_required", result["outcome"])
                self.assertEqual(0 if boundary == "before" else 1, len(result["action_payload"]["completed_components"]))
                self.assertEqual(boundary == "during", (instance / "mods/mod-list.json").exists())
                self.assertEqual(b"external protected settings change\n", settings.read_bytes())
                self.assertFalse((instance / "config/config.ini").exists())
                self.assertFalse((instance / "metadata/save-refs/selected.zip.save-ref.v1.json").exists())
                self.assertFalse(any(j["command_id"].startswith("readiness.prepare_") for j in self.journals(workspace)))
                if boundary == "before":
                    self.assertFalse(any(j["command_id"] == "modsets.apply" and j.get("operation_context") for j in self.journals(workspace)))
                else:
                    self.assert_content_effect(workspace, result)
                    self.assertEqual("fresh_request_after_input_correction", result["action_payload"]["continuation"])
                frozen = snapshot(workspace)
                self.assertEqual(result, self.result(invoke_machine(args), 1 if boundary == "before" else 3))
                self.assertEqual(frozen, snapshot(workspace))

    def test_ordinary_tui_reports_pending_content_and_content_only_completion(self) -> None:
        for content_only in (False, True):
            with self.subTest(content_only=content_only), tempfile.TemporaryDirectory(prefix="joined-content-tui-") as value:
                workspace = Path(value)
                if content_only:
                    instance = activation.ContentActivationReadinessTests.prepare(self, workspace)
                    self.result(invoke_machine(self.arguments(workspace, self.query(workspace, "instances", "load_save"), "prepare-v1")))
                    (instance / "mods/mod-list.json").unlink()
                else:
                    instance = self.prepare(workspace)
                observation = self.query(workspace, "instances", "load_save")
                index = next(i for i, a in enumerate(observation["available_semantic_actions"]) if a["action_id"] == "readiness.prepare_joined")
                refresh_index = next(i for i, a in enumerate(observation["available_semantic_actions"]) if a["action_id"] == "presentation.refresh")
                run = subprocess.run([str(facman_executable()), "tui", "--workspace", str(workspace), "--ordinary", "--plain"],
                    input="s\n2\n" + "tab\n" * (index - refresh_index) + "space\nspace\nq\n", cwd=ROOT, capture_output=True, text=True, timeout=45)
                self.assertEqual((0, ""), (run.returncode, run.stderr), run.stdout)
                self.assertIn("Confirm Make Ready with current settings", run.stdout)
                self.assertIn("review remaining readiness checks", run.stdout)
                receipts = [json.loads(p.read_bytes()) for p in (workspace / ".facman/action-receipts-v2").glob("*.v2.json")]
                result = next(json.loads(r["result_json"]) for r in receipts if
                              json.loads(r["result_json"])["action_payload"]["schema"] == "factorio.make_ready_joined_result.v2")
                self.assertEqual("completed", result["outcome"])
                self.assertEqual(1 if content_only else 3, len(result["action_payload"]["completed_components"]))
                self.assert_content_effect(workspace, result)

    @unittest.skipUnless(os.name == "nt", "unsupported: WinForms requires Windows")
    def test_compiled_adapters_accept_actual_v2_and_refuse_malformed_continuations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-content-adapters-") as value:
            root = Path(value)
            project = ROOT / "tests/winforms_control_gallery/FacMan.SelectedSave.Harness.csproj"
            build = subprocess.run([msbuild_executable(), str(project), "/m:2", "/nr:false", "/p:UseSharedCompilation=false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={root / 'bin'}{os.sep}",
                f"/p:IntermediateOutputPath={root / 'obj'}{os.sep}", f"/p:BaseIntermediateOutputPath={root / 'obj'}{os.sep}"],
                cwd=ROOT, capture_output=True, text=True, timeout=120)
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            executable = root / "bin/FacMan.SelectedSave.Harness.exe"
            completed = []
            for content_only in (False, True):
                workspace = root / ("content-only" if content_only else "complete")
                if content_only:
                    instance = activation.ContentActivationReadinessTests.prepare(self, workspace)
                    self.result(invoke_machine(self.arguments(workspace, self.query(workspace, "instances", "load_save"), "initial-v1")))
                    (instance / "mods/mod-list.json").unlink()
                else:
                    instance = self.prepare(workspace)
                scopes = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")
                gallery = root / "gallery.json"
                gallery.write_text(json.dumps(dict(schema="facman.control_gallery_case.v1", state="blocked",
                    variant="make-ready-current-settings", observed_at="2026-10-18T00:00:00Z",
                    snapshots={scope: self.query(workspace, scope, "load_save") for scope in scopes})), encoding="utf-8")
                response = invoke_machine(self.arguments(workspace, self.query(workspace, "instances", "load_save"), "adapter-complete"))
                self.result(response)
                completed.append(json.loads(response[1]))
                receipt = root / "receipt.json"
                receipt.write_text(response[1], encoding="utf-8")
                frozen = snapshot(workspace)
                run = subprocess.run([str(executable), str(gallery), str(receipt), "make-ready-content-complete"],
                    cwd=root, capture_output=True, text=True, timeout=60)
                self.assertEqual(0, run.returncode, run.stdout + run.stderr)
                self.assertEqual(frozen, snapshot(workspace))
            workspace = root / "partial"
            instance = self.prepare(workspace)
            args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "content-adapter-partial")
            worker = joined.PausedAction(args, dict(os.environ, FACMAN_TEST_MAKE_READY_PAUSE_AFTER_CONTENT="1"))
            release = instance / ".facman-test-make-ready-content-release"
            try:
                joined.wait_for_owned_marker(worker, instance / ".facman-test-make-ready-after-content", release)
                (instance / "mods/mod-settings.dat").write_bytes(b"external changed settings\n")
                release.touch()
            finally:
                release.touch(exist_ok=True)
                worker.finish()
            actual = self.result(worker.response, 3)
            envelope = json.loads(worker.response[1])
            original = workspace / ".facman/action-receipts-v2" / (hashlib.sha256(b"content-adapter-partial").hexdigest() + ".v2.json")
            inputs = json.loads(json.loads(original.read_bytes())["request_json"])
            cases = []
            def case(name, mutate=None, expected=False):
                modified = copy.deepcopy(envelope)
                if mutate: mutate(modified["payload"]["action_payload"])
                cases.append(dict(name=name, envelope=json.dumps(modified), input=inputs, exit_code=3, expected_clear=expected))
            case("actual-content-known-partial", expected=True)
            case("unknown-owner", lambda p: p.update(content_effect_verified=False, continuation="inspect_domain_recovery"))
            case("missing-content-proof", lambda p: p.pop("content_effect_verified"))
            case("wrong-proof-type", lambda p: p.update(content_effect_verified="true"))
            case("extra-clearing-authority", lambda p: p.update(extra=True))
            case("foreign-plan-field", lambda p: p["plan"].update(extra=True))
            case("foreign-content-field", lambda p: p["plan"]["content_plan"].update(extra=True))
            case("foreign-owner-field", lambda p: p["completed_components"][0]["owner_result"].update(extra=True))
            case("foreign-journal", lambda p: p["completed_components"][0].update(transaction_id="foreign"))
            case("foreign-history", lambda p: p["completed_components"][0]["owner_result"].update(history_id="a" * 64))
            case("foreign-operation", lambda p: p["completed_components"][0]["owner_result"].update(operation_id="foreign"))
            case("foreign-attempt", lambda p: p["completed_components"][0]["owner_result"].update(attempt_id="foreign"))
            case("foreign-pin", lambda p: p["completed_components"][0]["owner_result"]["apply_result"].update(plan_id="a" * 64))
            case("foreign-selection", lambda p: p["completed_components"][0]["owner_result"]["apply_result"].update(desired_mods=[]))
            case("duplicate-content", lambda p: p["completed_components"].append(copy.deepcopy(p["completed_components"][0])))
            case("nested-mismatch", lambda p: p.update(joined_result={}))
            case("execution-authority", lambda p: p.update(permit_issued=True))
            for field, value in (("operation_id", "foreign"), ("target_instance_id", "foreign"), ("target_installation_id", "foreign")):
                modified = copy.deepcopy(envelope)
                modified["payload"]["operation"][field] = value
                cases.append(dict(name="semantic-" + field, envelope=json.dumps(modified), input=inputs, exit_code=3, expected_clear=False))
            modified = copy.deepcopy(envelope)
            modified["payload"]["request_id"] = "foreign"
            cases.append(dict(name="semantic-request", envelope=json.dumps(modified), input=inputs, exit_code=3, expected_clear=False))

            # The existing nested-v1 pause yields a real refusal with zero later
            # effects. V2 still retains a verified content effect and can safely
            # offer the backend's correlated fresh-request continuation.
            zero_workspace = root / "zero-partial"
            zero_instance = activation.ContentActivationReadinessTests.prepare(self, zero_workspace)
            self.result(invoke_machine(self.arguments(zero_workspace, self.query(zero_workspace, "instances", "load_save"), "zero-initial")))
            (zero_instance / "mods/mod-list.json").unlink()
            zero_args = self.arguments(zero_workspace, self.query(zero_workspace, "instances", "load_save"), "zero-content-partial")
            settings = zero_instance / "mods/mod-settings.dat"
            original_settings = settings.read_bytes() if settings.exists() else None
            zero_worker = joined.PausedAction(zero_args, dict(os.environ, FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_CONTEXT="1"))
            zero_release = zero_instance / ".facman-test-make-ready-context-release"
            try:
                joined.wait_for_owned_marker(zero_worker, zero_instance / ".facman-test-make-ready-before-context", zero_release)
                settings.write_bytes(b"external zero-effect protected drift\n")
                zero_release.touch()
            finally:
                zero_release.touch(exist_ok=True)
                zero_worker.finish()
            zero_result = self.result(zero_worker.response, 3)
            zero_payload = zero_result["action_payload"]
            self.assertEqual("fresh_request_after_input_correction", zero_payload["continuation"])
            self.assertTrue(zero_payload["completed_effects_verified"])
            self.assertEqual([], zero_payload["joined_result"]["completed_components"])
            self.assertFalse(zero_payload["joined_result"]["completed_effects_verified"])
            self.assert_content_effect(zero_workspace, zero_result)
            zero_receipt = zero_workspace / ".facman/action-receipts-v2" / (hashlib.sha256(b"zero-content-partial").hexdigest() + ".v2.json")
            retained_receipt = zero_receipt.read_bytes()
            zero_input = json.loads(json.loads(retained_receipt)["request_json"])
            zero_envelope = json.loads(zero_worker.response[1])
            zero_ids = dict(request_id="zero-content-partial", operation_id="zero-content-partial", attempt_id="zero-content-partial")
            def zero_case(name, mutate=None, expected=False):
                changed = copy.deepcopy(zero_envelope)
                if mutate: mutate(changed["payload"]["action_payload"])
                cases.append(dict(name=name, envelope=json.dumps(changed), input=zero_input, identity=zero_ids,
                                  exit_code=3, expected_clear=expected))
            zero_case("actual-content-zero-nested-partial", expected=True)
            zero_case("zero-nested-preparation-invented", lambda p: p["joined_result"].update(preparation_complete=True))
            zero_case("zero-nested-not-fresh", lambda p: p["joined_result"].update(fresh_revision_required=False))
            zero_case("zero-nested-readiness-invented", lambda p: p["joined_result"].update(readiness_observation={}))
            zero_case("zero-aggregate-unverified", lambda p: p.update(completed_effects_verified=False))
            zero_case("zero-nested-effect-proof-invented", lambda p: p["joined_result"].update(completed_effects_verified=True))
            zero_frozen = snapshot(zero_workspace)
            self.assertEqual(zero_result, self.result(invoke_machine(zero_args), 3))
            self.assertEqual(zero_frozen, snapshot(zero_workspace))
            if original_settings is None: settings.unlink()
            else: settings.write_bytes(original_settings)
            retained_journals = snapshot(zero_workspace / "transactions")
            self.assertEqual("completed", self.result(invoke_machine(self.arguments(zero_workspace,
                self.query(zero_workspace, "instances", "load_save"), "zero-corrected")))["outcome"])
            self.assertEqual(retained_receipt, zero_receipt.read_bytes())
            self.assertEqual(retained_journals, snapshot(zero_workspace / "transactions"))

            # Completion feedback must reject invented or untyped readiness,
            # while displaying actual degraded completed owner work truthfully.
            for index, source in enumerate(completed):
                for name, mutate, expected in (("actual", None, True), ("empty", lambda r: r.clear(), False),
                        ("unknown", lambda r: r.update(schema="foreign.readiness.v1"), False),
                        ("illegal-state", lambda r: r.update(configuration_state="invented"), False),
                        ("foreign-instance", lambda r: r.update(instance_id="foreign"), False),
                        ("contradictory-prepared", lambda r: r.update(configuration_state="ready", preparation_state="already_prepared"), False)):
                    changed = copy.deepcopy(source)
                    payload = changed["payload"]["action_payload"]
                    self.assertFalse(payload["preparation_complete"])
                    if mutate:
                        mutate(payload["readiness_observation"])
                        mutate(payload["joined_result"]["readiness_observation"])
                    cases.append(dict(name=f"completed-{index}-{name}", envelope=json.dumps(changed), input=inputs,
                        identity=dict(request_id="adapter-complete", operation_id="adapter-complete", attempt_id="adapter-complete"),
                        exit_code=0, expected_clear=False, expected_summary=expected))
            # Windows owners may publish equivalent mixed-separator target text.
            # Keep foreign targets and device namespace aliases conservative.
            for component, plan_key in (("routing_configuration", "configuration_plan"),
                                        ("selected_save_declared_context", "selected_context_target")):
                for spelling in ("mixed", "foreign", "extended", "device", "nt-device"):
                    changed = copy.deepcopy(completed[0])
                    payload = changed["payload"]["action_payload"]
                    nested = payload["joined_result"]
                    owner = next(e for e in nested["completed_components"] if e["component"] == component)
                    original = owner["owner_result"]["target"].replace("/", "\\")
                    target = original.replace("\\", "/") if spelling == "mixed" else original + ".foreign"
                    if spelling in ("extended", "device", "nt-device"):
                        target = {"extended": "\\\\?\\", "device": "\\\\.\\", "nt-device": "\\??\\"}[spelling] + original
                        if plan_key == "configuration_plan": nested["plan"][plan_key]["target"] = target
                        else: nested["plan"][plan_key] = target
                    owner["owner_result"]["target"] = target
                    flat = next(e for e in payload["completed_components"] if e["component"] == component)
                    flat["owner_result"]["target"] = target
                    cases.append(dict(name=f"completed-target-{component}-{spelling}", envelope=json.dumps(changed), input=inputs,
                        identity=dict(request_id="adapter-complete", operation_id="adapter-complete", attempt_id="adapter-complete"),
                        exit_code=0, expected_clear=False, expected_summary=spelling == "mixed"))
            corpus = root / "continuations.json"
            corpus.write_text(json.dumps(dict(request_id="content-adapter-partial", operation_id="content-adapter-partial",
                attempt_id="content-adapter-partial", cases=cases)), encoding="utf-8")
            frozen = snapshot(workspace)
            run = subprocess.run([str(executable), "make-ready-continuation", str(corpus)], cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)
            self.assertIn(f"PASS {len(cases)}", run.stdout)
            model = facman_executable().with_name("facman_tui_product_model_smoke.exe")
            run = subprocess.run([str(model), str(corpus)], cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)
            self.assertEqual(frozen, snapshot(workspace))

    def test_pending_repair_preserves_foreign_metadata_and_unselected_entries(self) -> None:
        for kind in ("root-field", "entry-field", "disabled-extra", "enabled-extra"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="joined-content-foreign-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace, "disabled")
                path = instance / "mods/mod-list.json"
                document = json.loads(path.read_bytes())
                if kind == "root-field": document["user_metadata"] = "preserve"
                elif kind == "entry-field": document["mods"][0]["user_metadata"] = "preserve"
                else: document["mods"].append(dict(name="foreign", enabled=kind == "enabled-extra"))
                path.write_text(json.dumps(document), encoding="utf-8")
                before = snapshot(workspace)
                observed = self.query(workspace, "instances", "load_save")
                self.assertIsNone(observed["dependency_identities"]["joined_preparation"]["plan"])
                self.assertEqual(before, snapshot(workspace))

    def test_stale_activation_archive_and_lock_identity_refuse_before_effects(self) -> None:
        for kind in ("list-bytes", "archive-identity", "lock-identity"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="joined-content-stale-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace, "disabled")
                observation = self.query(workspace, "instances", "load_save")
                args = self.arguments(workspace, observation, "content-stale")
                path = instance / ("mods/simple_1.0.0.zip" if kind == "archive-identity" else
                                   "mods/modset-lock.v1.json" if kind == "lock-identity" else "mods/mod-list.json")
                original = path.read_bytes()
                if kind == "list-bytes": path.write_bytes(original + b"\n")
                else:
                    held = path.with_name(path.name + ".original-retained")
                    path.rename(held)
                    path.write_bytes(original)
                    self.assertNotEqual(joined.file_identity(path), joined.file_identity(held))
                before = snapshot(workspace)
                code, output, error = invoke_machine(args)
                self.assertEqual((1, ""), (code, error), output)
                self.assertEqual("stale_snapshot_revision", json.loads(output)["error"]["code"])
                self.assertEqual(before, snapshot(workspace))

    def test_changed_protected_inputs_and_unverifiable_content_stop_before_later_owners(self) -> None:
        for kind in ("configuration", "overrides", "settings", "activation", "backup", "foreign-stage"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="joined-content-partial-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                observation = self.query(workspace, "instances", "load_save")
                args = self.arguments(workspace, observation, "content-partial")
                env = dict(os.environ, FACMAN_TEST_MAKE_READY_PAUSE_AFTER_CONTENT="1")
                worker = joined.PausedAction(args, env)
                release = instance / ".facman-test-make-ready-content-release"
                try:
                    joined.wait_for_owned_marker(worker, instance / ".facman-test-make-ready-after-content", release)
                    journal = next(j for j in self.journals(workspace) if j["command_id"] == "modsets.apply" and j.get("operation_context"))
                    context = json.loads(journal["operation_context"])
                    if kind == "configuration": target = instance / "config/config.ini"
                    elif kind == "overrides": target = instance / "instance-overrides.v1.json"
                    elif kind == "settings": target = instance / "mods/mod-settings.dat"
                    elif kind == "activation": target = instance / "mods/mod-list.json"
                    elif kind == "backup": target = Path(journal["owned_staging_roots"][1]) / "local-lock.before"
                    else: target = Path(journal["owned_staging_roots"][0]) / "foreign-user-file.txt"
                    if kind == "overrides": target.write_bytes(target.read_bytes() + b"\n")
                    else: target.write_bytes(b"foreign input retained after content checkpoint\n")
                    changed = target.read_bytes()
                    release.write_text("continue\n", encoding="utf-8")
                finally:
                    if not release.exists(): release.write_text("continue\n", encoding="utf-8")
                    worker.finish()
                result = self.result(worker.response, 3)
                payload = result["action_payload"]
                self.assertEqual("recovery_required", result["outcome"])
                self.assertEqual(["modsets.apply"], [e["owner_command"] for e in payload["completed_components"]])
                verified = kind in ("configuration", "overrides", "settings")
                self.assertEqual(verified, payload["content_effect_verified"])
                self.assertEqual(verified, payload["completed_effects_verified"])
                self.assertEqual("fresh_request_after_input_correction" if verified else "inspect_domain_recovery", payload["continuation"])
                self.assertFalse(payload["preparation_complete"])
                self.assertIsNone(payload["joined_result"])
                self.assertEqual(changed, target.read_bytes())
                self.assertFalse((instance / "metadata/save-refs/selected.zip.save-ref.v1.json").exists())
                if kind != "configuration": self.assertFalse((instance / "config/config.ini").exists())
                self.assertFalse(any(j["command_id"].startswith("readiness.prepare_") for j in self.journals(workspace)))
                frozen = snapshot(workspace)
                replay = self.result(invoke_machine(args), 3)
                self.assertEqual(result, replay)
                self.assertEqual(payload, replay["action_payload"])
                self.assertEqual(frozen, snapshot(workspace))

    def test_owner_unknown_and_declared_interruptions_never_redispatch_content(self) -> None:
        for kind in ("unknown", "owner-exit", "checkpoint-exit", "configuration-exit"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="joined-content-unknown-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                observation = self.query(workspace, "instances", "load_save")
                args = self.arguments(workspace, observation, "content-unknown")
                variable = {"unknown": "FACMAN_TEST_MAKE_READY_OWNER_RESULT_UNKNOWN",
                            "owner-exit": "FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONTENT_OWNER",
                            "checkpoint-exit": "FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONTENT",
                            "configuration-exit": "FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONFIGURATION"}[kind]
                response = invoke_machine(args, env=dict(os.environ, **{variable: "content" if kind == "unknown" else "1"}))
                if kind == "unknown":
                    first = self.result(response, 3)
                    self.assertEqual("recovery_required", first["outcome"])
                    self.assertEqual("make_ready_owner_result_unknown", first["problems"][0]["code"])
                else:
                    self.assertEqual({"owner-exit": 90, "checkpoint-exit": 89, "configuration-exit": 88}[kind], response[0], response)
                content = [j for j in self.journals(workspace) if j["command_id"] == "modsets.apply" and j.get("operation_context")]
                self.assertEqual(1, len(content))
                self.assertEqual("complete", content[0]["state"])
                self.assertEqual("content-unknown", json.loads(content[0]["operation_context"])["operation_id"])
                self.assertEqual(kind == "configuration-exit", (instance / "config/config.ini").exists())
                self.assertFalse((instance / "metadata/save-refs/selected.zip.save-ref.v1.json").exists())
                frozen = snapshot(workspace)
                replay = self.result(invoke_machine(args), 3 if kind == "unknown" else 4)
                if kind == "unknown": self.assertEqual(first, replay)
                self.assertEqual(replay, self.result(invoke_machine(args), 3 if kind == "unknown" else 4))
                self.assertEqual("recovery_required" if kind == "unknown" else "outcome_unknown", replay["outcome"])
                self.assertEqual({"unknown": 0, "owner-exit": 0, "checkpoint-exit": 1, "configuration-exit": 2}[kind],
                                 len(replay["action_payload"]["completed_components"]))
                self.assertEqual(frozen, snapshot(workspace))

    def test_existing_content_owner_restores_its_declared_fault_without_running_configuration(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-content-owner-fault-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            locks = {p: p.read_bytes() for p in (instance / "mods/modset-lock.v1.json", workspace / "modsets/main.modset-lock.v1.json")}
            observation = self.query(workspace, "instances", "load_save")
            args = self.arguments(workspace, observation, "content-owner-fault")
            result = self.result(invoke_machine(args, env=dict(os.environ, FACMAN_MODSET_FAULT="after_first_commit")), 1)
            self.assertEqual("refused_before_effects", result["outcome"])
            self.assertEqual([], result["action_payload"]["completed_components"])
            self.assertEqual(locks, {p: p.read_bytes() for p in locks})
            self.assertFalse((instance / "mods/mod-list.json").exists())
            self.assertFalse((instance / "config/config.ini").exists())
            self.assertFalse((instance / "metadata/save-refs/selected.zip.save-ref.v1.json").exists())
            self.assertFalse(any(j["command_id"].startswith("readiness.prepare_") for j in self.journals(workspace)))
            frozen = snapshot(workspace)
            self.assertEqual(result, self.result(invoke_machine(args), 1))
            self.assertEqual(frozen, snapshot(workspace))


    def test_later_unverifiable_owner_result_keeps_content_but_never_claims_all_effects_verified(self) -> None:
        for owner in ("configuration", "selected_save"):
            with self.subTest(owner=owner), tempfile.TemporaryDirectory(prefix="joined-content-later-unknown-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "content-later-unknown")
                result = self.result(invoke_machine(args, env=dict(os.environ,
                    FACMAN_TEST_MAKE_READY_OWNER_RESULT_UNKNOWN=owner)), 3)
                payload = result["action_payload"]
                self.assertEqual("recovery_required", result["outcome"])
                self.assertTrue(payload["content_effect_verified"])
                self.assertFalse(payload["completed_effects_verified"])
                self.assertFalse(payload["preparation_complete"])
                self.assertEqual("inspect_domain_recovery", payload["continuation"])
                self.assertIsNone(payload["readiness_observation"])
                self.assertEqual(1 if owner == "configuration" else 2, len(payload["completed_components"]))
                self.assertTrue((instance / "config/config.ini").exists())
                self.assertEqual(owner == "selected_save", (instance / "metadata/save-refs/selected.zip.save-ref.v1.json").exists())
                self.assert_content_effect(workspace, result)
                frozen = snapshot(workspace)
                self.assertEqual(payload, self.result(invoke_machine(args), 3)["action_payload"])
                self.assertEqual(frozen, snapshot(workspace))


if __name__ == "__main__":
    unittest.main()
