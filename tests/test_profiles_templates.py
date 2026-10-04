# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from native_cli import invoke
from tools import json_contract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
SCHEMA_ROOT = ROOT / "contracts" / "schema" / "factorio"


def invoke_json(workspace: Path, *args: str, success: bool = True) -> dict:
    code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
    if success and code != 0:
        raise AssertionError(stderr or stdout)
    if not success and code == 0:
        raise AssertionError(f"command unexpectedly succeeded: {stdout}")
    return json.loads(stdout or stderr)


def assert_schema(test: unittest.TestCase, value: dict, name: str) -> None:
    schema = json_contract.load_schema(SCHEMA_ROOT / name)
    test.assertEqual([], json_contract.validate(value, schema), name)


def create_instance(workspace: Path) -> Path:
    invoke_json(workspace, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture")
    invoke_json(workspace, "instances", "create", "Main", "--id", "main", "--install", "fixture")
    return workspace / "instances" / "main"


class ProfileTemplateTests(unittest.TestCase):
    def test_reviewed_preparation_binds_profile_overrides_and_requested_values(self) -> None:
        for changed in ("profile", "existing_overrides", "requested_values"):
            with self.subTest(changed=changed):
                with tempfile.TemporaryDirectory(prefix="facman reviewed profile ") as value:
                    workspace = Path(value)
                    instance = create_instance(workspace)
                    invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
                    if changed == "existing_overrides":
                        invoke_json(workspace, "profiles", "apply", "main", "gui", "--audio", "disabled")
                    planned = invoke_json(workspace, "profiles", "plan", "main", "quiet")
                    assert_schema(self, planned, "factorio_effective_profile.v1.schema.json")
                    self.assertRegex(planned["plan_sha256"], "^[0-9a-f]{64}$")
                    self.assertEqual(planned["plan_sha256"], invoke_json(
                        workspace, "profiles", "plan", "main", "quiet")["plan_sha256"])
                    self.assertEqual(hashlib.sha256((workspace / "profiles" / "quiet" /
                                                     "profile.v1.json").read_bytes()).hexdigest(),
                                     planned["source_profile_sha256"])
                    options: tuple[str, ...] = ()
                    if changed == "profile":
                        invoke_json(workspace, "profiles", "archive", "quiet")
                        invoke_json(workspace, "profiles", "create", "quiet", "--selection-mode",
                                    "load-save", "--selection", "selected.zip")
                    elif changed == "existing_overrides":
                        invoke_json(workspace, "profiles", "apply", "main", "gui", "--audio", "enabled")
                    else:
                        options = ("--window-mode", "fullscreen")
                    self.assertEqual(planned["source_manifest_sha256"],
                                     hashlib.sha256((instance / "instance.v1.json").read_bytes()).hexdigest())
                    before = {p.relative_to(workspace): p.read_bytes()
                              for p in workspace.rglob("*") if p.is_file()}
                    for action in ("plan", "apply"):
                        refused = invoke_json(workspace, "profiles", action, "main", "quiet", *options,
                                              "--expected-plan", planned["plan_sha256"], success=False)
                        self.assertEqual("profile_preparation_revision_changed", refused["refusal"]["code"])
                    self.assertEqual(before, {p.relative_to(workspace): p.read_bytes()
                                             for p in workspace.rglob("*") if p.is_file()})
                    fresh = invoke_json(workspace, "profiles", "plan", "main", "quiet", *options)
                    self.assertNotEqual(planned["plan_sha256"], fresh["plan_sha256"])
                    applied = invoke_json(workspace, "profiles", "apply", "main", "quiet", *options,
                                          "--expected-plan", fresh["plan_sha256"],
                                          "--expected-revision", fresh["source_manifest_sha256"])
                    assert_schema(self, applied, "factorio_effective_profile.v1.schema.json")
                    self.assertEqual(fresh["plan_sha256"], applied["plan_sha256"])
                    self.assertEqual(fresh["settings"], applied["settings"])
                    self.assertTrue(applied["mutation_executed"])
                    self.assertFalse(applied["execution_enabled"])

    def test_gui_preparation_plan_binds_override_absence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile absence ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            absent = invoke_json(workspace, "profiles", "plan", "main", "gui")
            (instance / "instance-overrides.v1.json").write_bytes(b"")
            present = invoke_json(workspace, "profiles", "plan", "main", "gui")
            self.assertNotEqual(absent["plan_sha256"], present["plan_sha256"])
            self.assertEqual(absent["source_profile_sha256"], present["source_profile_sha256"])
            before = {p.relative_to(workspace): p.read_bytes()
                      for p in workspace.rglob("*") if p.is_file()}
            refused = invoke_json(workspace, "profiles", "apply", "main", "gui",
                                  "--expected-plan", absent["plan_sha256"], success=False)
            self.assertEqual("profile_preparation_revision_changed", refused["refusal"]["code"])
            self.assertEqual(before, {p.relative_to(workspace): p.read_bytes()
                                     for p in workspace.rglob("*") if p.is_file()})

    def test_late_profile_change_preserves_inputs_through_explicit_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile late input ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            invoke_json(workspace, "profiles", "apply", "main", "gui", "--audio", "disabled")
            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
            planned = invoke_json(workspace, "profiles", "plan", "main", "quiet")
            originals = {name: (instance / name).read_bytes()
                         for name in ("instance.v1.json", "instance-overrides.v1.json")}
            profile = workspace / "profiles" / "quiet" / "profile.v1.json"
            environment = os.environ.copy()
            environment["FACMAN_TEST_PROFILE_BEFORE_PUBLICATION_PAUSE"] = "1"
            outcome: list[tuple[int, str, str]] = []
            worker = threading.Thread(target=lambda: outcome.append(invoke([
                "--workspace", str(workspace), "profiles", "apply", "main", "quiet",
                "--expected-plan", planned["plan_sha256"], "--json",
            ], env=environment)))
            worker.start()
            marker = instance / ".facman-test-profile-before-publication"
            release = instance / ".facman-test-profile-publication-release"
            try:
                for _ in range(100):
                    if marker.is_file():
                        break
                    time.sleep(0.05)
                self.assertTrue(marker.is_file(), "profile apply did not reach publication boundary")
                changed = json.loads(profile.read_text(encoding="utf-8"))
                changed["settings"]["audio"] = "enabled"
                profile.write_text(json.dumps(changed) + "\n", encoding="utf-8")
                preserved_profile = profile.read_bytes()
            finally:
                release.write_text("continue\n", encoding="utf-8")
                worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
            self.assertEqual(1, len(outcome))
            self.assertNotEqual(0, outcome[0][0])
            refusal = json.loads(outcome[0][1] or outcome[0][2])["refusal"]
            self.assertEqual("profile_transaction_recovery_required", refusal["code"])
            self.assertIn("Profile preparation inputs changed before publication: "
                          "Profile preparation inputs changed since the plan was reviewed", refusal["detail"])
            self.assertEqual(originals, {name: (instance / name).read_bytes() for name in originals})
            self.assertEqual(preserved_profile, profile.read_bytes())
            pending = invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]
            transaction = next(item for item in pending if item["command_id"] == "profiles.apply")
            self.assertEqual("recovery_required", transaction["state"])
            stages = tuple(instance.glob(f".profile*-{transaction['transaction_id']}.json"))
            self.assertEqual(2, len(stages))
            recovered = invoke_json(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("rolled_back", recovered["transactions"][0]["state"])
            self.assertTrue(all(not stage.exists() for stage in stages))
            self.assertEqual(originals, {name: (instance / name).read_bytes() for name in originals})
            self.assertEqual(preserved_profile, profile.read_bytes())
            refused = invoke_json(workspace, "profiles", "apply", "main", "quiet",
                                  "--expected-plan", planned["plan_sha256"], success=False)
            self.assertEqual("profile_preparation_revision_changed", refused["refusal"]["code"])
            fresh = invoke_json(workspace, "profiles", "plan", "main", "quiet")
            self.assertNotEqual(planned["plan_sha256"], fresh["plan_sha256"])
            applied = invoke_json(workspace, "profiles", "apply", "main", "quiet",
                                  "--expected-plan", fresh["plan_sha256"])
            self.assertEqual("enabled", applied["settings"]["audio"])
            self.assertEqual(fresh["plan_sha256"], applied["plan_sha256"])

    def test_menu_readiness_blocks_profile_and_override_save_selection(self) -> None:
        for selected, options in (
            ("load_save", ("--selection-mode", "load-save", "--selection", "selected.zip")),
            ("benchmark", ("--selection-mode", "benchmark-save", "--selection", "selected.zip",
                           "--launch-mode", "benchmark-preview", "--benchmark-ticks", "1")),
        ):
            for inherited in (False, True):
                with self.subTest(intent=selected, inherited=inherited):
                    with tempfile.TemporaryDirectory(prefix="facman menu intent ") as value:
                        workspace = Path(value)
                        instance = create_instance(workspace)
                        baseline = invoke_json(workspace, "instances", "readiness", "main")
                        self.assertEqual("satisfied", next(
                            item["state"] for item in baseline["dimensions"] if item["id"] == "profile"))
                        if inherited:
                            invoke_json(workspace, "profiles", "create", "selected", *options)
                            invoke_json(workspace, "profiles", "apply", "main", "selected")
                        else:
                            invoke_json(workspace, "profiles", "apply", "main", "gui", *options)
                        before = {p.relative_to(workspace): p.read_bytes()
                                  for p in workspace.rglob("*") if p.is_file()}
                        readiness = invoke_json(workspace, "instances", "readiness", "main")
                        assert_schema(self, readiness, "factorio_instance_readiness.v1.schema.json")
                        self.assertEqual("menu", readiness["launch_intent"])
                        self.assertEqual("blocked", readiness["configuration_state"])
                        self.assertEqual("blocked", next(
                            item["state"] for item in readiness["dimensions"] if item["id"] == "profile"))
                        blocker = next(item for item in readiness["blockers"]
                                       if item["code"] == "instance_launch_intent_mismatch")
                        self.assertIn(selected, blocker["detail"])
                        self.assertEqual("configure_menu_profile", blocker["safe_next_action"])
                        self.assertNotEqual(baseline["readiness_digest"], readiness["readiness_digest"])
                        described = invoke_json(workspace, "instances", "describe", "main")
                        self.assertEqual(readiness, described["instance_readiness"])
                        for action in ("readiness", "describe"):
                            code, text, error = invoke([
                                "--workspace", str(workspace), "instances", action, "main"])
                            self.assertEqual(0, code, error)
                            self.assertIn("Configuration: blocked", text)
                            self.assertIn("instance_launch_intent_mismatch", text)
                            self.assertIn(blocker["detail"], text)
                            self.assertIn("configure_menu_profile", text)
                            self.assertIn("facman profiles plan main gui --json", text)
                        self.assertTrue(all(v is False for v in readiness["operation_guarantees"].values()))
                        self.assertFalse((instance / "saves" / "selected.zip").exists())
                        self.assertEqual(before, {p.relative_to(workspace): p.read_bytes()
                                                 for p in workspace.rglob("*") if p.is_file()})
                        invoke_json(workspace, "profiles", "apply", "main", "gui")
                        restored = invoke_json(workspace, "instances", "readiness", "main")
                        self.assertEqual("satisfied", next(
                            item["state"] for item in restored["dimensions"] if item["id"] == "profile"))
                        self.assertNotIn("instance_launch_intent_mismatch",
                                         {item["code"] for item in restored["blockers"]})

    def test_human_profile_plan_and_apply_show_effective_values_and_sources(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile human ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled",
                        "--arg", "--low-vram")
            before = (instance / "instance.v1.json").read_bytes()
            commands = ("profiles", "plan", "main", "quiet", "--window-mode", "fullscreen",
                        "--arg", "--disable-audio")
            code, output, error = invoke(["--workspace", str(workspace), *commands])
            self.assertEqual(0, code, error)
            self.assertIn("Planned profile quiet for instance main", output)
            self.assertIn("window_mode: fullscreen [request override]", output)
            self.assertIn("audio: disabled [profile]", output)
            self.assertIn("--low-vram [profile]", output)
            self.assertIn("--disable-audio [request override]", output)
            self.assertIn("No files changed.", output)
            self.assertEqual(before, (instance / "instance.v1.json").read_bytes())

            code, output, error = invoke(["--workspace", str(workspace), "profiles", "apply",
                                          "main", "quiet", "--window-mode", "fullscreen",
                                          "--arg", "--disable-audio"])
            self.assertEqual(0, code, error)
            self.assertIn("Applied profile quiet for instance main", output)
            self.assertIn("Source manifest SHA-256:", output)
            self.assertNotIn("No files changed.", output)
            self.assertEqual("quiet", json.loads((instance / "instance.v1.json").read_text(encoding="utf-8"))["profile"])

    def test_profile_apply_crash_after_journal_recovers_without_effect(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile journal recovery ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            original = (instance / "instance.v1.json").read_bytes()
            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
            environment = os.environ.copy()
            environment["FACMAN_TEST_PROFILE_APPLY_EXIT_AFTER_JOURNAL"] = "1"
            code, _, _ = invoke([
                "--workspace", str(workspace), "profiles", "apply", "main", "quiet", "--json",
            ], env=environment)
            self.assertEqual(85, code)
            pending = invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]
            transaction = next(item for item in pending if item["command_id"] == "profiles.apply")
            self.assertEqual("requested", transaction["state"])
            recovered = invoke_json(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("rolled_back", recovered["transactions"][0]["state"])
            self.assertEqual(original, (instance / "instance.v1.json").read_bytes())
            self.assertFalse((instance / "instance-overrides.v1.json").exists())

    def test_profile_apply_crash_after_pair_closes_verified_journal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile pair recovery ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
            environment = os.environ.copy()
            environment["FACMAN_TEST_PROFILE_APPLY_EXIT_AFTER_PAIR"] = "1"
            code, _, _ = invoke([
                "--workspace", str(workspace), "profiles", "apply", "main", "quiet", "--json",
            ], env=environment)
            self.assertEqual(87, code)
            pending = invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]
            transaction = next(item for item in pending if item["command_id"] == "profiles.apply")
            self.assertEqual("committing", transaction["state"])
            self.assertEqual("quiet", json.loads((instance / "instance.v1.json").read_text())["profile"])
            self.assertEqual("quiet", json.loads((instance / "instance-overrides.v1.json").read_text())["profile_id"])
            recovered = invoke_json(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("complete", recovered["transactions"][0]["state"])
            self.assertEqual("quiet", invoke_json(workspace, "launch", "plan", "main")["profile_id"])

    def test_profile_apply_interruption_before_effect_rolls_back_staging(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile staged recovery ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            original = (instance / "instance.v1.json").read_bytes()
            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
            environment = os.environ.copy()
            environment["FACMAN_TEST_TRANSACTION_FAIL_STATE"] = "committing"
            code, _, _ = invoke([
                "--workspace", str(workspace), "profiles", "apply", "main", "quiet", "--json",
            ], env=environment)
            self.assertNotEqual(0, code)
            pending = invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]
            transaction = next(item for item in pending if item["command_id"] == "profiles.apply")
            self.assertEqual("recovery_required", transaction["state"])
            recovered = invoke_json(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("rolled_back", recovered["transactions"][0]["state"])
            self.assertEqual(original, (instance / "instance.v1.json").read_bytes())
            self.assertFalse((instance / "instance-overrides.v1.json").exists())
            self.assertFalse((instance / (".profile-apply-" + transaction["transaction_id"] + ".json")).exists())
            self.assertEqual("gui", invoke_json(workspace, "launch", "plan", "main")["profile_id"])

    def test_profile_recovery_refuses_changed_staging(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile changed staging ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
            environment = os.environ.copy()
            environment["FACMAN_TEST_PROFILE_APPLY_EXIT_AFTER_MANIFEST"] = "1"
            code, _, _ = invoke([
                "--workspace", str(workspace), "profiles", "apply", "main", "quiet", "--json",
            ], env=environment)
            self.assertEqual(86, code)
            pending = invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]
            transaction = next(item for item in pending if item["command_id"] == "profiles.apply")
            stage = instance / (".profile-overrides-" + transaction["transaction_id"] + ".json")
            stage.write_text('{"unowned":true}\n', encoding="utf-8")
            refused = invoke_json(workspace, "workspace", "recovery", "apply",
                                  transaction["transaction_id"], success=False)
            self.assertEqual("recovery_profile_pair_unsafe", refused["refusal"]["code"])
            self.assertEqual("quiet", json.loads((instance / "instance.v1.json").read_text())["profile"])
            self.assertFalse((instance / "instance-overrides.v1.json").exists())
            pending_again = invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]
            self.assertEqual("committing", next(item for item in pending_again if
                             item["transaction_id"] == transaction["transaction_id"])["state"])

    def test_interrupted_profile_apply_recovers_from_delivered_cli(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile recovery ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            original = (instance / "instance.v1.json").read_bytes()
            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
            environment = os.environ.copy()
            environment["FACMAN_TEST_PROFILE_APPLY_EXIT_AFTER_MANIFEST"] = "1"
            code, _, _ = invoke([
                "--workspace", str(workspace), "profiles", "apply", "main", "quiet", "--json",
            ], env=environment)
            self.assertEqual(86, code)
            self.assertEqual("quiet", json.loads((instance / "instance.v1.json").read_text())["profile"])
            self.assertFalse((instance / "instance-overrides.v1.json").exists())
            pending = invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]
            transaction = next(item for item in pending if item["command_id"] == "profiles.apply")
            self.assertEqual("committing", transaction["state"])
            planned = invoke_json(workspace, "workspace", "recovery", "plan", transaction["transaction_id"])
            self.assertIn("verify_and_reconcile_profile_pair", planned["transactions"][0]["actions"])
            recovered = invoke_json(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("complete", recovered["transactions"][0]["state"])
            self.assertEqual("quiet", json.loads((instance / "instance-overrides.v1.json").read_text())["profile_id"])
            backups = list((workspace / "backups" / "profiles").rglob("instance.v1.json"))
            self.assertEqual(1, len(backups))
            self.assertEqual(original, backups[0].read_bytes())
            self.assertEqual("quiet", invoke_json(workspace, "launch", "plan", "main")["profile_id"])
            self.assertTrue(all(item["state"] in {"complete", "refused", "rolled_back", "cancelled"}
                                for item in invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]))

    def test_interrupted_profile_reapply_preserves_original_overrides(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile reapply recovery ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
            invoke_json(workspace, "profiles", "create", "fast", "--graphics-quality", "low")
            invoke_json(workspace, "profiles", "apply", "main", "quiet", "--audio", "disabled")
            original_overrides = (instance / "instance-overrides.v1.json").read_bytes()
            environment = os.environ.copy()
            environment["FACMAN_TEST_PROFILE_APPLY_EXIT_AFTER_MANIFEST"] = "1"
            code, _, _ = invoke([
                "--workspace", str(workspace), "profiles", "apply", "main", "fast",
                "--graphics-quality", "low", "--json",
            ], env=environment)
            self.assertEqual(86, code)
            self.assertEqual(original_overrides, (instance / "instance-overrides.v1.json").read_bytes())
            pending = invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]
            transaction = next(item for item in pending if item["command_id"] == "profiles.apply" and
                               item["state"] == "committing")
            recovered = invoke_json(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("complete", recovered["transactions"][0]["state"])
            self.assertEqual("fast", json.loads((instance / "instance-overrides.v1.json").read_text())["profile_id"])
            backup = workspace / "backups" / "profiles" / (transaction["transaction_id"] + "-main")
            self.assertEqual(original_overrides, (backup / "instance-overrides.v1.json").read_bytes())
            self.assertEqual("fast", invoke_json(workspace, "launch", "plan", "main")["profile_id"])

    def test_apply_preserves_cloned_instance_manifest_provenance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profile provenance ") as value:
            workspace = Path(value)
            create_instance(workspace)
            invoke_json(workspace, "instances", "clone", "main", "copy")
            manifest_path = workspace / "instances" / "copy" / "instance.v1.json"
            before = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("main", before["source_instance"])
            self.assertIn("cloned_at", before)
            self.assertIn("save_policy", before)
            self.assertIn("export_policy", before)

            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
            applied = invoke_json(workspace, "profiles", "apply", "copy", "quiet")
            self.assertTrue(applied["mutation_executed"])
            after = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("quiet", after.pop("profile"))
            before.pop("profile")
            self.assertEqual(before, after)
            self.assertEqual("copy", invoke_json(workspace, "instances", "inspect", "copy")["instance_id"])

    def test_shipped_template_and_existing_gui_instance_remain_compatible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman templates ") as value:
            workspace = Path(value)
            create_instance(workspace)
            listed = invoke_json(workspace, "templates", "list")
            inspected = invoke_json(workspace, "templates", "inspect", "vanilla")
            validated = invoke_json(workspace, "templates", "validate", "vanilla")
            assert_schema(self, listed, "factorio_instance_templates.v1.schema.json")
            assert_schema(self, inspected, "factorio_instance_template.v1.schema.json")
            assert_schema(self, validated, "factorio_instance_template_validation.v1.schema.json")
            self.assertEqual(["vanilla"], listed["templates"])
            self.assertTrue(all(inspected["forbidden_capabilities"].values()))
            self.assertNotIn('"executable":', json.dumps(inspected).lower())

            preview = invoke_json(workspace, "launch", "plan", "main")
            self.assertEqual("gui", preview["profile_id"])
            self.assertEqual("gui", preview["mode"])
            self.assertEqual("--config", preview["args"][0])
            self.assertEqual("--mod-directory", preview["args"][2])

    def test_profile_lifecycle_plan_apply_and_safe_argument_boundary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman profiles ") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            before = (instance / "instance.v1.json").read_bytes()

            created = invoke_json(
                workspace, "profiles", "create", "quiet", "--audio", "disabled",
                "--graphics-quality", "low", "--arg", "--low-vram",
            )
            assert_schema(self, created, "factorio_launch_profile_report.v1.schema.json")
            profile_path = workspace / "profiles" / "quiet" / "profile.v1.json"
            document = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual("factorio.launch_profile.v1", document["schema"])
            assert_schema(self, document, "factorio_launch_profile.v1.schema.json")
            self.assertFalse(document["portability"]["machine_local_paths"])
            self.assertFalse(document["portability"]["credentials"])
            self.assertNotIn(str(workspace), profile_path.read_text(encoding="utf-8"))

            refused = invoke_json(workspace, "profiles", "create", "unsafe", "--arg", "--config", success=False)
            self.assertEqual("profile_arguments_invalid", refused["refusal"]["code"])
            self.assertFalse((workspace / "profiles" / "unsafe").exists())

            planned = invoke_json(
                workspace, "profiles", "plan", "main", "quiet",
                "--window-mode", "fullscreen", "--arg", "--low-vram", "--arg", "--disable-audio",
            )
            assert_schema(self, planned, "factorio_effective_profile.v1.schema.json")
            self.assertFalse(planned["mutation_executed"])
            self.assertFalse(planned["execution_enabled"])
            self.assertEqual(hashlib.sha256(before).hexdigest(), planned["source_manifest_sha256"])
            self.assertEqual("quiet", planned["provenance"]["base_profile_id"])
            self.assertEqual("request_override", planned["provenance"]["setting_sources"]["window_mode"])
            self.assertEqual("profile", planned["provenance"]["setting_sources"]["audio"])
            self.assertEqual([
                {"value": "--low-vram", "source": "profile"},
                {"value": "--disable-audio", "source": "request_override"},
            ], planned["provenance"]["additional_argument_sources"])
            self.assertEqual(before, (instance / "instance.v1.json").read_bytes())

            applied = invoke_json(
                workspace, "profiles", "apply", "main", "quiet",
                "--window-mode", "fullscreen", "--arg", "--disable-audio",
                "--expected-revision", planned["source_manifest_sha256"],
            )
            assert_schema(self, applied, "factorio_effective_profile.v1.schema.json")
            self.assertTrue(applied["mutation_executed"])
            self.assertEqual(planned["source_manifest_sha256"], applied["source_manifest_sha256"])
            self.assertEqual(planned["provenance"], applied["provenance"])
            self.assertEqual("quiet", json.loads((instance / "instance.v1.json").read_text(encoding="utf-8"))["profile"])
            overrides = json.loads((instance / "instance-overrides.v1.json").read_text(encoding="utf-8"))
            self.assertEqual("factorio.instance_overrides.v1", overrides["schema"])
            assert_schema(self, overrides, "factorio_instance_overrides.v1.schema.json")
            self.assertTrue(any((workspace / "backups" / "profiles").rglob("instance.v1.json")))
            changed_manifest = (instance / "instance.v1.json").read_bytes()
            changed_overrides = (instance / "instance-overrides.v1.json").read_bytes()
            stale = invoke_json(
                workspace, "profiles", "apply", "main", "quiet",
                "--expected-revision", planned["source_manifest_sha256"], success=False,
            )
            self.assertEqual("profile_instance_revision_changed", stale["refusal"]["code"])
            self.assertEqual(changed_manifest, (instance / "instance.v1.json").read_bytes())
            self.assertEqual(changed_overrides, (instance / "instance-overrides.v1.json").read_bytes())
            selected = invoke_json(workspace, "profiles", "inspect", "quiet")
            self.assertEqual("profiles.inspect", selected["command"])
            self.assertFalse(selected["mutation_executed"])

            preview = invoke_json(workspace, "launch", "plan", "main")
            self.assertEqual("quiet", preview["profile_id"])
            self.assertEqual(["--config", "--mod-directory"], [preview["args"][0], preview["args"][2]])
            self.assertIn("--low-vram", preview["args"])
            self.assertIn("--disable-audio", preview["args"])
            self.assertEqual(1, preview["args"].count("--config"))
            self.assertEqual(1, preview["args"].count("--mod-directory"))

            cloned = invoke_json(workspace, "profiles", "clone", "quiet", "archivable")
            assert_schema(self, cloned, "factorio_launch_profile_report.v1.schema.json")
            difference = invoke_json(workspace, "profiles", "diff", "gui", "quiet")
            assert_schema(self, difference, "factorio_launch_profile_diff.v1.schema.json")
            self.assertEqual({"audio", "graphics_quality", "additional_arguments"}, {
                item["field"] for item in difference["differences"]
            })
            archived = invoke_json(workspace, "profiles", "archive", "archivable")
            assert_schema(self, archived, "factorio_launch_profile_archive.v1.schema.json")
            self.assertFalse(archived["permanent_delete"])
            self.assertFalse((workspace / "profiles" / "archivable").exists())
            self.assertEqual(1, len(list((workspace / "trash" / "profiles").rglob("profile.v1.json"))))


if __name__ == "__main__":
    unittest.main()
