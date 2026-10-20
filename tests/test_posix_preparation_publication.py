# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Linux/macOS owner inode/custody fixtures; not physical-host or game acceptance."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import test_configuration_preparation as configuration
import test_selected_save_preparation as selected
from native_cli import ROOT, facman_executable, invoke_machine


@unittest.skipUnless(sys.platform in ("linux", "darwin"), "unsupported: same-inode POSIX publication recovery requires Linux or macOS")
class PosixPreparationPublicationTests(unittest.TestCase):
    def prepare_owner(self, kind: str, workspace: Path):
        if kind == "configuration":
            owner = configuration.ConfigurationPreparationTests()
            instance, _ = owner.prepare(workspace, "load_save", True)
            args = owner.args(workspace, owner.query(workspace, intent="load_save")["revision"], intent="load_save")
            return owner, instance, args, "FACMAN_TEST_CONFIGURATION", "config_text"
        owner = selected.SelectedSavePreparationTests()
        instance = owner.prepare(workspace)
        args = owner.arguments(workspace, owner.query(workspace)["revision"])
        return owner, instance, args, "FACMAN_TEST_SELECTED_CONTEXT", "sidecar_text"

    def test_ordinary_make_ready_prepares_missing_ini_then_selected_context_with_fresh_revision(self) -> None:
        with tempfile.TemporaryDirectory(prefix="posix-make-ready-") as value:
            workspace = Path(value)
            owner, instance, args, _, _ = self.prepare_owner("configuration", workspace)
            effects = {"config/config.ini", "metadata/save-refs/selected.zip.save-ref.v1.json"}
            def preserved():
                return {p.relative_to(instance).as_posix(): p.read_bytes() for p in instance.rglob("*")
                        if p.is_file() and p.relative_to(instance).as_posix() not in effects
                        and "locks" not in p.relative_to(instance).parts}
            before = preserved()
            args[4] = "readiness.prepare"
            code, out, err = invoke_machine(args)
            self.assertEqual((0, ""), (code, err), out)
            first = json.loads(out)["payload"]
            self.assertEqual("completed", first["outcome"])
            self.assertEqual("readiness.prepare_configuration", first["action_payload"]["completed_components"][0]["owner_command"])
            self.assertFalse((instance / "metadata/save-refs/selected.zip.save-ref.v1.json").exists())
            target = instance / "config/config.ini"
            configuration_identity = (target.stat().st_dev, target.stat().st_ino, target.stat().st_nlink, target.read_bytes())
            frozen = self.filesystem(workspace)
            current = owner.query(workspace, intent="load_save")
            self.assertEqual(frozen, self.filesystem(workspace), "Fresh planning must preserve the completed configuration and workspace")
            configuration_component = current["dependency_identities"]["configuration_preparation"]
            self.assertIsNone(configuration_component["plan"])
            self.assertEqual("configuration_already_current", configuration_component["refusal"]["code"])
            for action_id in ("readiness.prepare_selected_save", "readiness.prepare"):
                descriptor = next(action for action in current["available_semantic_actions"] if action["action_id"] == action_id)
                self.assertEqual("available", descriptor["availability"])
            self.assertNotEqual(args[args.index("--expected-revision") + 1], current["revision"])
            if sys.platform == "darwin":
                stale = selected.SelectedSavePreparationTests().arguments(workspace,
                    args[args.index("--expected-revision") + 1], identity="selected-stale")
                stale[4] = "readiness.prepare"
                code, out, err = invoke_machine(stale)
                self.assertEqual((1, ""), (code, err), out)
                self.assertEqual("stale_snapshot_revision", json.loads(out)["error"]["code"])
                self.assertFalse(json.loads(out)["operation"]["effects_may_have_occurred"])
                self.assertEqual(frozen, self.filesystem(workspace))
            second_args = selected.SelectedSavePreparationTests().arguments(workspace, current["revision"], identity="selected-next")
            second_args[4] = "readiness.prepare"
            code, out, err = invoke_machine(second_args)
            self.assertEqual((0, ""), (code, err), out)
            second = json.loads(out)["payload"]
            self.assertEqual("completed", second["outcome"])
            self.assertEqual("readiness.prepare_selected_save", second["action_payload"]["completed_components"][0]["owner_command"])
            for result in (first, second):
                self.assertFalse(result["action_payload"]["readiness_complete"])
                self.assertFalse(result["action_payload"]["execution_started"])
                self.assertFalse(result["action_payload"]["permit_issued"])
            self.assertEqual("satisfied", second["replacement_snapshot"]["readiness"]["selected_save"]["state"])
            self.assertEqual(configuration_identity, (target.stat().st_dev, target.stat().st_ino, target.stat().st_nlink, target.read_bytes()))
            for relative in effects:
                self.assertEqual(1, (instance / relative).stat().st_nlink)
            self.assertEqual(before, preserved())

    def test_existing_ini_reconciliation_plan_requires_explicit_confirmation_before_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="posix-existing-ini-refusal-") as value:
            workspace = Path(value)
            owner, instance, _, _, _ = self.prepare_owner("configuration", workspace)
            target = instance / "config/config.ini"
            target.write_bytes(b"; foreign settings\n[path]\nread-data=foreign\nwrite-data=foreign\n")
            frozen = self.filesystem(workspace)
            projection = owner.query(workspace, intent="load_save")
            component = projection["dependency_identities"]["configuration_preparation"]
            plan = component["plan"]
            self.assertIsNotNone(plan, component["refusal"])
            self.assertEqual("existing_routing_configuration", plan["component"])
            self.assertEqual(str(target), plan["target"])
            self.assertEqual(target.read_text(), plan["original_config_text"])
            self.assertEqual(str(target.stat().st_dev), plan["original_device"])
            self.assertEqual(str(target.stat().st_ino), plan["original_object"])
            self.assertTrue(plan["original_metadata_identity"])
            descriptor = next(action for action in projection["available_semantic_actions"]
                              if action["action_id"] == "readiness.prepare_configuration")
            self.assertEqual("available", descriptor["availability"])
            self.assertEqual(frozen, self.filesystem(workspace), "Query must preserve existing INI and workspace")
            code, out, err = invoke_machine(owner.args(workspace, projection["revision"], intent="load_save",
                                                      confirmation=False))
            self.assertIn(code, (1, 3), out)
            self.assertEqual("", err)
            self.assertEqual("semantic_action_effect_confirmation_required", json.loads(out)["error"]["code"])
            self.assertEqual(frozen, self.filesystem(workspace))

    def filesystem(self, root: Path) -> dict:
        result = {}
        for path in root.rglob("*"):
            info = path.lstat()
            value = (info.st_dev, info.st_ino, info.st_nlink, info.st_mode)
            if path.is_symlink(): value += (os.readlink(path),)
            elif path.is_file(): value += (path.read_bytes(),)
            result[path.relative_to(root).as_posix()] = value
        return result

    def link_pair(self, kind: str, workspace: Path):
        owner, instance, args, variable, text_key = self.prepare_owner(kind, workspace)
        code, _, _ = invoke_machine(args, env=dict(os.environ, **{variable + "_EXIT": "after_publication"}))
        self.assertEqual(74, code)
        _, record = owner.journal(workspace)
        stage, target = Path(record["owned_staging_roots"][0]), Path(record["target"])
        expected = json.loads(record["operation_context"])[text_key].encode()
        identity = (target.stat().st_dev, target.stat().st_ino)
        self.assertEqual(identity, (stage.stat().st_dev, stage.stat().st_ino))
        self.assertEqual(f"{identity[0]}:{identity[1]}", record["effect_file_identity"])
        self.assertEqual((2, 2), (stage.stat().st_nlink, target.stat().st_nlink))
        self.assertEqual(expected, target.read_bytes())
        return owner, instance, record, stage, target, expected, identity

    def test_interrupted_link_pair_finishes_exact_inode_and_fresh_recovery_is_read_only(self) -> None:
        for kind in ("configuration", "selected"):
            with self.subTest(owner=kind), tempfile.TemporaryDirectory(prefix="posix-preparation-pair-") as value:
                workspace = Path(value)
                owner, instance, record, stage, target, expected, identity = self.link_pair(kind, workspace)
                preserved = owner.preserved(instance)
                code, output = owner.recover(workspace, record)
                self.assertEqual(0, code, output)
                self.assertFalse(stage.exists())
                self.assertEqual(identity, (target.stat().st_dev, target.stat().st_ino))
                self.assertEqual(1, target.stat().st_nlink)
                self.assertEqual(expected, target.read_bytes())
                self.assertEqual(preserved, owner.preserved(instance))
                frozen = self.filesystem(workspace)
                code, output = owner.recover(workspace, record)
                self.assertEqual(0, code, output)
                self.assertEqual(frozen, self.filesystem(workspace))
                projection = owner.query(workspace, intent="load_save")
                self.assertFalse(projection["readiness"]["execution_available"])
                self.assertEqual("unavailable", projection["readiness"]["play_authority_state"])

    def test_foreign_objects_extra_links_symlinks_and_changed_bytes_are_preserved(self) -> None:
        for kind in ("configuration", "selected"):
            for variant in ("foreign_stage", "foreign_target", "third_link", "missing_stage",
                            "linked_stage", "linked_target", "changed_bytes"):
                with self.subTest(owner=kind, variant=variant), tempfile.TemporaryDirectory(prefix="posix-preparation-foreign-") as value:
                    workspace = Path(value)
                    owner, instance, record, stage, target, expected, _ = self.link_pair(kind, workspace)
                    if variant in ("foreign_stage", "linked_stage"):
                        stage.rename(stage.with_name("preserved-staging"))
                        if variant == "foreign_stage": stage.write_bytes(expected)
                        else: stage.symlink_to(target.name)
                    elif variant in ("foreign_target", "linked_target"):
                        target.rename(target.with_name("preserved-target"))
                        if variant == "foreign_target": target.write_bytes(expected)
                        else: target.symlink_to(stage.name)
                    elif variant in ("third_link", "missing_stage"):
                        os.link(target, target.with_name("foreign-alias"))
                        if variant == "missing_stage": stage.unlink()
                    else: target.write_bytes(expected[:-1] + b"!")
                    frozen = self.filesystem(instance)
                    code, output = owner.recover(workspace, record)
                    self.assertIn(code, (1, 3), output)
                    self.assertEqual(frozen, self.filesystem(instance))

    def test_actual_target_substitution_or_write_during_final_observation_refuses(self) -> None:
        for kind in ("configuration", "selected"):
            for variant in ("replace", "write"):
                with self.subTest(owner=kind, variant=variant), tempfile.TemporaryDirectory(prefix="posix-preparation-final-") as value:
                    workspace = Path(value)
                    owner, instance, args, variable, _ = self.prepare_owner(kind, workspace)
                    results = []
                    worker = threading.Thread(target=lambda: results.append(invoke_machine(args,
                        env=dict(os.environ, **{variable + "_PAUSE": "before_final_observation"}))))
                    worker.start()
                    marker_prefix = ".facman-test-configuration-" if kind == "configuration" else ".facman-test-selected-context-"
                    marker, release = instance / (marker_prefix + "before_final_observation"), instance / (marker_prefix + "release")
                    try:
                        deadline = time.monotonic() + 15
                        while not marker.exists() and time.monotonic() < deadline: time.sleep(0.01)
                        self.assertTrue(marker.exists(), "Owner final observation seam was not reached")
                        _, record = owner.journal(workspace)
                        target = Path(record["target"])
                        data = target.read_bytes()
                        if variant == "replace":
                            previous_inode = target.stat().st_ino
                            target.rename(target.with_name("preserved-published"))
                            target.write_bytes(data)
                            self.assertNotEqual(previous_inode, target.stat().st_ino)
                        else: target.write_bytes(data[:-1] + b"!")
                        frozen = self.filesystem(target.parent)
                        release.write_bytes(b"release")
                        worker.join(30)
                        self.assertFalse(worker.is_alive())
                        self.assertEqual((3, ""), (results[0][0], results[0][2]), results)
                        self.assertEqual("recovery_required", json.loads(results[0][1])["payload"]["outcome"])
                        self.assertTrue(json.loads(results[0][1])["operation"]["effects_may_have_occurred"])
                        self.assertEqual(frozen, self.filesystem(target.parent))
                    finally:
                        release.write_bytes(b"release")
                        worker.join(30)

    def start_paused(self, args: list[str], instance: Path, variable: str, phase: str) -> subprocess.Popen:
        process = subprocess.Popen([str(facman_executable()), *args], cwd=ROOT,
            env=dict(os.environ, **{variable + "_PAUSE": phase}), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        prefix = ".facman-test-configuration-" if variable == "FACMAN_TEST_CONFIGURATION" else ".facman-test-selected-context-"
        marker = instance / (prefix + phase)
        deadline = time.monotonic() + 18
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        if not marker.exists():
            process.kill(); out, err = process.communicate(timeout=10)
            self.fail(f"Owner pause {phase} not reached: {process.returncode}: {out}: {err}")
        return process

    @unittest.skipUnless(sys.platform == "darwin", "unsupported: actual Darwin publication SIGKILL qualification")
    def test_darwin_actual_sigkill_and_recovery_loss_preserve_bound_effect_and_unknown_request(self) -> None:
        for kind in ("configuration", "selected"):
            for phase in ("before_publication", "after_publication", "before_final_observation"):
                with self.subTest(owner=kind, phase=phase), tempfile.TemporaryDirectory(prefix="darwin-publication-kill-") as value:
                    workspace = Path(value).resolve()
                    owner, instance, args, variable, text_key = self.prepare_owner(kind, workspace)
                    args[4] = "readiness.prepare"
                    before = owner.preserved(instance)
                    process = self.start_paused(args, instance, variable, phase)
                    try:
                        _, record = owner.journal(workspace)
                        stage, target = Path(record["owned_staging_roots"][0]), Path(record["target"])
                        expected = json.loads(record["operation_context"])[text_key].encode()
                        bound = record["effect_file_identity"]
                        effect = target if target.exists() else stage
                        self.assertEqual(bound, f"{effect.stat().st_dev}:{effect.stat().st_ino}")
                        self.assertEqual(expected, effect.read_bytes())
                        process.kill(); process.communicate(timeout=10)
                        self.assertEqual(-signal.SIGKILL, process.returncode)
                    finally:
                        if process.poll() is None: process.kill(); process.communicate(timeout=10)
                    frozen = self.filesystem(workspace)
                    code, out, err = invoke_machine(args)
                    self.assertEqual((4, ""), (code, err), out)
                    self.assertEqual("outcome_unknown", json.loads(out)["payload"]["outcome"])
                    self.assertEqual(frozen, self.filesystem(workspace), "Unknown Make Ready replay must not redispatch")
                    prefix = ".facman-test-configuration-" if kind == "configuration" else ".facman-test-selected-context-"
                    (instance / (prefix + phase)).unlink()
                    recovery_args = ["--workspace", str(workspace), "workspace", "recovery", "apply",
                                     record["transaction_id"], "--json"]
                    process = self.start_paused(recovery_args, instance, variable, "before_final_observation")
                    try:
                        self.assertFalse(stage.exists())
                        self.assertEqual(1, target.stat().st_nlink)
                        self.assertEqual(bound, f"{target.stat().st_dev}:{target.stat().st_ino}")
                        process.kill(); process.communicate(timeout=10)
                        self.assertEqual(-signal.SIGKILL, process.returncode)
                    finally:
                        if process.poll() is None: process.kill(); process.communicate(timeout=10)
                    code, output = owner.recover(workspace, record)
                    self.assertEqual(0, code, output)
                    self.assertEqual(expected, target.read_bytes())
                    self.assertEqual(bound, f"{target.stat().st_dev}:{target.stat().st_ino}")
                    self.assertEqual(before, owner.preserved(instance))
                    frozen = self.filesystem(workspace)
                    code, output = owner.recover(workspace, record)
                    self.assertEqual(0, code, output)
                    self.assertEqual(frozen, self.filesystem(workspace))

    @unittest.skipUnless(sys.platform == "darwin", "unsupported: actual Darwin concurrent recovery qualification")
    def test_darwin_live_recovery_lock_contention_preserves_exact_published_pair(self) -> None:
        for kind in ("configuration", "selected"):
            with self.subTest(owner=kind), tempfile.TemporaryDirectory(prefix="darwin-publication-contention-") as value:
                workspace = Path(value).resolve()
                owner, instance, args, variable, _ = self.prepare_owner(kind, workspace)
                process = self.start_paused(args, instance, variable, "after_publication")
                try:
                    _, record = owner.journal(workspace)
                    target, stage = Path(record["target"]), Path(record["owned_staging_roots"][0])
                    self.assertEqual((2, 2), (target.stat().st_nlink, stage.stat().st_nlink))
                    frozen = self.filesystem(instance)
                    code, output = owner.recover(workspace, record)
                    self.assertEqual(3, code, output)
                    self.assertEqual(frozen, self.filesystem(instance))
                    process.kill(); process.communicate(timeout=10)
                    self.assertEqual(-signal.SIGKILL, process.returncode)
                finally:
                    if process.poll() is None: process.kill(); process.communicate(timeout=10)
                code, output = owner.recover(workspace, record)
                self.assertEqual(0, code, output)
                self.assertFalse(stage.exists())
                self.assertEqual(1, target.stat().st_nlink)


if __name__ == "__main__": unittest.main()
