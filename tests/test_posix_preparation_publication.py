# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Linux owner inode/custody fixtures; not physical-host or game acceptance."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import test_configuration_preparation as configuration
import test_selected_save_preparation as selected
from native_cli import invoke_machine


@unittest.skipUnless(sys.platform == "linux", "unsupported: same-inode POSIX publication recovery is Linux only")
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

    def test_existing_ini_reconciliation_remains_refused_before_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="posix-existing-ini-refusal-") as value:
            workspace = Path(value)
            owner, instance, _, _, _ = self.prepare_owner("configuration", workspace)
            target = instance / "config/config.ini"
            target.write_bytes(b"; foreign settings\n[path]\nread-data=foreign\nwrite-data=foreign\n")
            frozen = self.filesystem(workspace)
            projection = owner.query(workspace, intent="load_save")
            component = projection["dependency_identities"]["configuration_preparation"]
            self.assertIsNone(component["plan"])
            self.assertEqual("configuration_publication_unavailable", component["refusal"]["code"])
            code, out, err = invoke_machine(owner.args(workspace, projection["revision"], intent="load_save"))
            self.assertIn(code, (1, 3), out)
            self.assertEqual("", err)
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
                        self.assertEqual(frozen, self.filesystem(target.parent))
                    finally:
                        release.write_bytes(b"release")
                        worker.join(30)


if __name__ == "__main__": unittest.main()
