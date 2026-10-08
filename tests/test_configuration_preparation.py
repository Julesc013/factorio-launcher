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
from pathlib import Path
import jsonschema

import test_readiness_builtin_content as fixtures
from tools.winforms_build import msbuild_executable
from native_cli import invoke_machine
from test_local_modset_solver import snapshot
from test_presentation_profile_preparation import factorio_validator
import test_selected_save_preparation as selected_save_fixtures


class ConfigurationPreparationTests(unittest.TestCase):
    def prepare(self, workspace: Path, intent: str = "menu", raw: bool = False) -> tuple[Path, bytes]:
        if intent == "load_save":
            instance = selected_save_fixtures.SelectedSavePreparationTests.prepare(self, workspace)
        else:
            instance, _ = fixtures.ReadinessBuiltinContentTests.prepare(self, workspace, mixed=True)
        patch = instance / "instance-overrides.v1.json"
        if raw:
            text = patch.read_text() if patch.exists() else json.dumps(dict(
                schema="factorio.instance_overrides.v1", instance_id="main", profile_id="gui", values={}))
            patch.write_bytes((" \n" + text + "\n\n").encode())
        old = (instance / "config/config.ini").read_bytes()
        (instance / "config/config.ini").unlink()
        return instance, old

    def query(self, workspace: Path, scope: str = "instances", intent: str = "menu") -> dict:
        return fixtures.ReadinessBuiltinContentTests.query(self, workspace, scope, intent)

    def args(self, workspace: Path, revision: str, identity: str = "configuration", scope: str = "instances",
             intent: str = "menu", confirmation: bool = True) -> list[str]:
        result = ["--workspace", str(workspace), "presentation", "action", "readiness.prepare_configuration",
                  "--scope", scope, "--instance", "main", "--intent", intent, "--expected-revision", revision,
                  "--request-id", identity, "--idempotency-key", identity, "--operation-id", identity,
                  "--attempt-id", identity, "--json"]
        if confirmation: result.extend(["--confirmation", "explicit"])
        return result

    def journal(self, workspace: Path) -> tuple[Path, dict]:
        for path in (workspace / "transactions").glob("*.transaction.v1.json"):
            record = json.loads(path.read_text())
            if record["command_id"] == "readiness.prepare_configuration": return path, record
        self.fail("Configuration transaction not recorded")

    def recover(self, workspace: Path, record: dict) -> tuple[int, dict]:
        code, out, err = invoke_machine(["--workspace", str(workspace), "workspace", "recovery", "apply",
                                       record["transaction_id"], "--json"])
        self.assertEqual("", err, out)
        result = json.loads(out)
        if code == 0:
            repository = Path(__file__).resolve().parents[1]
            schema = json.loads((repository / "contracts/schema/facman/facman_workspace_recovery.v1.schema.json").read_text())
            jsonschema.Draft202012Validator(schema).validate(result["payload"])
            self.assertEqual("workspace.recovery.apply", result["payload"]["command"])
            self.assertEqual([record["transaction_id"]], [r["transaction_id"] for r in result["payload"]["transactions"]])
            self.assertEqual("complete", result["payload"]["transactions"][0]["state"])
        return code, result

    def preserved(self, instance: Path) -> dict[str, bytes]:
        return {p.relative_to(instance).as_posix(): p.read_bytes() for p in instance.rglob("*") if p.is_file()
                and p.relative_to(instance).as_posix() != "config/config.ini"
                and not p.name.startswith((".facman-configuration-", ".facman-test-"))
                and "locks" not in p.relative_to(instance).parts}

    def test_readonly_query_advertises_exact_missing_component_and_host_boundary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="configuration-plan-") as value:
            workspace = Path(value); self.prepare(workspace)
            before = snapshot(workspace)
            for scope in ("instances", "launch_deck"):
                projected = self.query(workspace, scope)
                descriptor = next(a for a in projected["available_semantic_actions"]
                                  if a["action_id"] == "readiness.prepare_configuration")
                self.assertEqual("available" if os.name == "nt" else "refused", descriptor["availability"])
                component = projected["dependency_identities"]["configuration_preparation"]
                if os.name == "nt":
                    plan = component["plan"]
                    factorio_validator("factorio_configuration_preparation_plan.v1.schema.json").validate(plan)
                    self.assertEqual("missing_routing_configuration", plan["component"])
                    self.assertEqual(hashlib.sha256(plan["config_text"].encode()).hexdigest(), plan["config_sha256"])
                else:
                    self.assertEqual("configuration_publication_unavailable", component["refusal"]["code"])
                self.assertFalse(projected["readiness"]["preparation_available"])
                self.assertFalse(projected["readiness"]["execution_available"])
            self.assertEqual(before, snapshot(workspace))

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_ordinary_repair_preserves_absent_and_raw_overrides_content_and_selected_context(self) -> None:
        for scope in ("instances", "launch_deck"):
            for intent, raw in (("menu", False), ("menu", True), ("load_save", True)):
                with self.subTest(scope=scope, intent=intent, raw=raw), tempfile.TemporaryDirectory(prefix="configuration-apply-") as value:
                    workspace = Path(value); instance, expected = self.prepare(workspace, intent, raw)
                    before = self.preserved(instance); old = self.query(workspace, scope, intent)
                    args = self.args(workspace, old["revision"], scope=scope, intent=intent)
                    code, out, err = invoke_machine(args)
                    self.assertEqual((0, ""), (code, err), out)
                    result = json.loads(out)["payload"]
                    self.assertEqual("completed", result["outcome"])
                    factorio_validator("factorio_configuration_preparation_result.v1.schema.json").validate(result["action_payload"])
                    self.assertEqual(expected, (instance / "config/config.ini").read_bytes())
                    self.assertEqual(before, self.preserved(instance))
                    ready = result["replacement_snapshot"]["readiness"]
                    self.assertNotIn("instance_effective_config_invalid", [b["code"] for b in ready["blockers"]])
                    self.assertFalse(ready["preparation_available"]); self.assertFalse(ready["execution_available"])
                    self.assertEqual("unavailable", ready["play_authority_state"])
                    frozen = snapshot(workspace)
                    replay_code, replay, replay_err = invoke_machine(args)
                    self.assertEqual((0, ""), (replay_code, replay_err), replay)
                    self.assertEqual(result, json.loads(replay)["payload"])
                    self.assertEqual(frozen, snapshot(workspace))

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_interruption_recovers_owned_effect_and_preserves_unbound_creation(self) -> None:
        for phase in ("after_manifest", "after_file_create", "before_publication", "after_publication", "before_finalization"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(prefix="configuration-loss-") as value:
                workspace = Path(value); instance, expected = self.prepare(workspace, "load_save", True)
                before = self.preserved(instance)
                args = self.args(workspace, self.query(workspace, intent="load_save")["revision"], intent="load_save")
                code, _, _ = invoke_machine(args, env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT=phase))
                self.assertEqual(74, code)
                _, record = self.journal(workspace); held = snapshot(instance / "config")
                recovered, output = self.recover(workspace, record)
                self.assertEqual(3 if phase == "after_file_create" else 0, recovered, output)
                if phase == "after_file_create":
                    self.assertEqual(held, snapshot(instance / "config"))
                    self.assertFalse((instance / "config/config.ini").exists())
                else:
                    self.assertEqual(expected, (instance / "config/config.ini").read_bytes())
                    frozen = snapshot(workspace); again, output = self.recover(workspace, record)
                    self.assertEqual(0, again, output); self.assertEqual(frozen, snapshot(workspace))
                self.assertEqual(before, self.preserved(instance))

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_existing_custom_wrong_routing_and_legacy_configuration_are_preserved(self) -> None:
        for variant in ("valid", "custom", "wrong", "legacy", "missing_parent"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix="configuration-existing-") as value:
                workspace = Path(value); instance, original = self.prepare(workspace)
                if variant == "valid": (instance / "config/config.ini").write_bytes(original)
                elif variant == "custom": (instance / "config/config.ini").write_bytes(original + b"\n; user settings\n[graphics]\nmax-texture-size=4096\n")
                elif variant == "wrong": (instance / "config/config.ini").write_bytes(b"; preserve me\n[path]\nread-data=wrong\nwrite-data=wrong\n")
                elif variant == "legacy": (instance / "config-path.cfg").write_bytes(b"config-path=foreign\n")
                else: (instance / "config").rmdir()
                old = self.query(workspace); before = snapshot(workspace)
                self.assertIsNone(old["dependency_identities"]["configuration_preparation"]["plan"])
                code, out, err = invoke_machine(self.args(workspace, old["revision"]))
                self.assertIn(code, (1, 3), out); self.assertEqual("", err, out)
                self.assertEqual(before, snapshot(workspace))

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_foreign_same_byte_objects_directories_and_strategy_drift_are_preserved(self) -> None:
        for variant in ("stage", "target", "directory", "strategy"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix="configuration-foreign-") as value:
                workspace = Path(value); instance, _ = self.prepare(workspace)
                code, _, _ = invoke_machine(self.args(workspace, self.query(workspace)["revision"]),
                    env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT="before_publication"))
                self.assertEqual(74, code)
                path, record = self.journal(workspace); stage = Path(record["owned_staging_roots"][0])
                data = stage.read_bytes()
                if variant == "target": Path(record["target"]).write_bytes(data)
                elif variant == "strategy":
                    record["commit_strategy"] = "durable_sidecar_create_no_save_mutation"
                    path.write_text(json.dumps(record)+"\n")
                else:
                    stage.rename(stage.with_name(stage.name+".preserved-original"))
                    if variant == "stage": stage.write_bytes(data)
                    else:
                        stage.mkdir(); (stage/"foreign.txt").write_bytes(b"foreign custody\n")
                held = snapshot(instance)
                code, output = self.recover(workspace, record)
                self.assertIn(code, (1, 3), output); self.assertEqual(held, snapshot(instance))
                if variant == "directory": self.assertEqual(["foreign.txt"], [p.name for p in stage.iterdir()])

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_terminal_missing_effect_is_never_recreated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="configuration-terminal-") as value:
            workspace = Path(value); instance, _ = self.prepare(workspace)
            code, out, _ = invoke_machine(self.args(workspace, self.query(workspace)["revision"]))
            self.assertEqual(0, code, out)
            _, record = self.journal(workspace); (instance / "config/config.ini").unlink()
            held = snapshot(instance); code, output = self.recover(workspace, record)
            self.assertEqual(3, code, output); self.assertEqual(held, snapshot(instance))
            self.assertFalse((instance / "config/config.ini").exists())

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_configuration_lock_custody_preserves_unfamiliar_and_compatible_files(self) -> None:
        for content in (b"", b"foreign\n", b"facman.instance_configuration_lock.v1\ninstance_id=main\n"):
            with self.subTest(content=content), tempfile.TemporaryDirectory(prefix="configuration-lock-") as value:
                workspace = Path(value); instance, expected = self.prepare(workspace)
                path = instance / "locks/configuration.write.lock"; path.write_bytes(content)
                inode = path.stat().st_ino
                code, out, err = invoke_machine(self.args(workspace, self.query(workspace)["revision"]))
                compatible = content.startswith(b"facman.instance_configuration_lock.v1")
                self.assertEqual((0 if compatible else 3, ""), (code, err), out)
                self.assertEqual(content, path.read_bytes()); self.assertEqual(inode, path.stat().st_ino)
                self.assertEqual(compatible, (instance / "config/config.ini").exists())
                if compatible: self.assertEqual(expected, (instance / "config/config.ini").read_bytes())

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_final_observation_holds_exact_published_target_against_replacement_and_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="configuration-pin-") as value:
            workspace = Path(value); instance, expected = self.prepare(workspace)
            args = self.args(workspace, self.query(workspace)["revision"])
            results = []
            worker = threading.Thread(target=lambda: results.append(invoke_machine(args,
                env=dict(os.environ, FACMAN_TEST_CONFIGURATION_PAUSE="before_final_observation"))))
            worker.start()
            release = instance / ".facman-test-configuration-release"
            try:
                marker = instance / ".facman-test-configuration-before_final_observation"
                deadline = time.monotonic() + 15
                while not marker.exists() and time.monotonic() < deadline: time.sleep(0.01)
                self.assertTrue(marker.exists(), "final held-target seam not reached")
                target = instance / "config/config.ini"; inode = target.stat().st_ino
                with self.assertRaises(PermissionError): target.rename(target.with_name("foreign.ini"))
                with self.assertRaises(PermissionError): target.write_bytes(expected)
                release.write_bytes(b"release"); worker.join(30)
                self.assertFalse(worker.is_alive()); self.assertEqual((0, ""), (results[0][0], results[0][2]), results)
                self.assertEqual(expected, target.read_bytes()); self.assertEqual(inode, target.stat().st_ino)
            finally:
                release.write_bytes(b"release"); worker.join(30)

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_late_context_drift_preserves_unpublished_or_published_effect_and_changed_inputs(self) -> None:
        for phase in ("before_publication", "after_publication"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(prefix="configuration-drift-") as value:
                workspace = Path(value); instance, expected = self.prepare(workspace, "load_save", True)
                args = self.args(workspace, self.query(workspace, intent="load_save")["revision"], intent="load_save")
                results = []
                worker = threading.Thread(target=lambda: results.append(invoke_machine(args,
                    env=dict(os.environ, FACMAN_TEST_CONFIGURATION_PAUSE=phase))))
                worker.start(); release = instance / ".facman-test-configuration-release"
                try:
                    marker = instance / (".facman-test-configuration-"+phase)
                    deadline = time.monotonic() + 15
                    while not marker.exists() and time.monotonic() < deadline: time.sleep(0.01)
                    self.assertTrue(marker.exists(), "late context seam not reached")
                    patch = instance / "instance-overrides.v1.json"; changed = patch.read_bytes()+b"\n"
                    patch.write_bytes(changed); release.write_bytes(b"release"); worker.join(30)
                    self.assertFalse(worker.is_alive()); self.assertEqual((3, ""), (results[0][0], results[0][2]), results)
                    self.assertEqual("recovery_required", json.loads(results[0][1])["payload"]["outcome"])
                    self.assertEqual(changed, patch.read_bytes())
                    target = instance / "config/config.ini"
                    self.assertEqual(phase == "after_publication", target.exists())
                    if target.exists(): self.assertEqual(expected, target.read_bytes())
                    _, record = self.journal(workspace); held = snapshot(instance)
                    recovered, output = self.recover(workspace, record)
                    self.assertEqual(3, recovered, output); self.assertEqual(held, snapshot(instance))
                finally:
                    release.write_bytes(b"release"); worker.join(30)

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_stale_snapshot_and_missing_confirmation_refuse_before_effects(self) -> None:
        for variant in ("stale", "confirmation"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix="configuration-admission-") as value:
                workspace = Path(value); instance, _ = self.prepare(workspace, raw=True)
                old = self.query(workspace)
                if variant == "stale":
                    path = instance / "instance-overrides.v1.json"; path.write_bytes(path.read_bytes()+b"\n")
                before = snapshot(workspace)
                code, out, err = invoke_machine(self.args(workspace, old["revision"], confirmation=variant != "confirmation"))
                self.assertIn(code, (1, 3), out); self.assertEqual("", err, out)
                self.assertEqual(before, snapshot(workspace)); self.assertFalse((instance / "config/config.ini").exists())


    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_immutable_reload_drift_refuses_under_the_original_recovery_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="configuration-reload-") as value:
            workspace = Path(value); instance, _ = self.prepare(workspace)
            code, _, _ = invoke_machine(self.args(workspace, self.query(workspace)["revision"]),
                env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT="before_publication"))
            self.assertEqual(74, code)
            path, record = self.journal(workspace); results = []
            args = ["--workspace", str(workspace), "workspace", "recovery", "apply", record["transaction_id"], "--json"]
            worker = threading.Thread(target=lambda: results.append(invoke_machine(args,
                env=dict(os.environ, FACMAN_TEST_CONFIGURATION_PAUSE="before_journal_reload"))))
            worker.start(); release = workspace / ".facman-test-configuration-release"
            try:
                marker = workspace / ".facman-test-configuration-before_journal_reload"
                deadline = time.monotonic() + 15
                while not marker.exists() and time.monotonic() < deadline: time.sleep(0.01)
                self.assertTrue(marker.exists(), "immutable reload seam not reached")
                contended, out, err = invoke_machine(args)
                self.assertEqual((3, ""), (contended, err), out)
                self.assertEqual("recovery_lock_contended", json.loads(out)["error"]["code"])
                nonce = record["marker_nonce"]
                record["marker_nonce"] = ("1" if nonce[0] != "1" else "2") + nonce[1:]
                path.write_text(json.dumps(record)+"\n", encoding="utf-8")
                held = snapshot(instance); changed = path.read_bytes()
                release.write_bytes(b"release"); worker.join(30)
                self.assertFalse(worker.is_alive()); self.assertEqual((3, ""), (results[0][0], results[0][2]), results)
                self.assertEqual("recovery_journal_identity_changed", json.loads(results[0][1])["error"]["code"])
                self.assertEqual(changed, path.read_bytes()); self.assertEqual(held, snapshot(instance))
                self.assertFalse((instance / "config/config.ini").exists())
            finally:
                release.write_bytes(b"release"); worker.join(30)

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_same_path_new_parent_object_invalidates_the_snapshot_without_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="configuration-parent-") as value:
            workspace = Path(value); instance, _ = self.prepare(workspace)
            old = self.query(workspace)
            (instance / "config").rename(instance / "preserved-config-parent")
            (instance / "config").mkdir()
            fresh = self.query(workspace)
            self.assertNotEqual(old["revision"], fresh["revision"])
            before = snapshot(workspace)
            code, out, err = invoke_machine(self.args(workspace, old["revision"]))
            self.assertEqual((1, ""), (code, err), out)
            self.assertEqual("stale_snapshot_revision", json.loads(out)["error"]["code"])
            self.assertEqual(before, snapshot(workspace)); self.assertFalse((instance / "config/config.ini").exists())

    @unittest.skipUnless(os.name == "nt", "unsupported: missing configuration publication is qualified only on Windows")
    def test_compiled_fixed_control_dispatches_ordinary_owner_and_keeps_captured_intent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="configuration-control-") as value:
            root = Path(value); workspace = root / "workspace"; self.prepare(workspace, "load_save", True)
            scopes = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")
            gallery = root / "gallery.json"
            gallery.write_text(json.dumps(dict(schema="facman.control_gallery_case.v1", state="blocked",
                variant="configuration-component", observed_at="2026-10-08T00:00:00Z",
                snapshots={scope: self.query(workspace, scope, "load_save") for scope in scopes}))+"\n", encoding="utf-8")
            code, out, err = invoke_machine(self.args(workspace, self.query(workspace, intent="load_save")["revision"], intent="load_save"))
            self.assertEqual((0, ""), (code, err), out)
            receipt = root / "receipt.json"; receipt.write_text(out, encoding="utf-8")
            before = snapshot(workspace); repository = Path(__file__).resolve().parents[1]
            project = repository / "tests/winforms_control_gallery/FacMan.SelectedSave.Harness.csproj"
            build = subprocess.run([str(msbuild_executable()), str(project), "/p:Configuration=Release", "/p:Platform=x64",
                "/p:OutputPath="+str(root / "bin")+"\\", "/p:BaseIntermediateOutputPath="+str(root / "obj")+"\\",
                "/nr:false", "/m:2", "/v:quiet"], cwd=repository, text=True, capture_output=True)
            self.assertEqual(0, build.returncode, build.stdout+build.stderr)
            check = subprocess.run([str(root / "bin/FacMan.SelectedSave.Harness.exe"), str(gallery), str(receipt), "configuration"],
                cwd=repository, text=True, capture_output=True)
            self.assertEqual(0, check.returncode, check.stdout+check.stderr)
            self.assertEqual(before, snapshot(workspace))


if __name__ == "__main__": unittest.main()
