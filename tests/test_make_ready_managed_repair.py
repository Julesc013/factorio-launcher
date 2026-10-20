# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Actual Setup owner composition using generated, non-executable ZIP fixtures."""
from __future__ import annotations

import datetime
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager

from native_cli import ROOT, facman_executable, invoke_machine
from test_local_modset_solver import snapshot
from test_make_ready_joined import JoinedMakeReadyTests, PausedAction, wait_for_owned_marker
from test_presentation_profile_preparation import factorio_validator
from test_save_index_retention import write_save
from tools.winforms_build import msbuild_executable


@unittest.skipUnless(os.name == "nt", "unsupported: generated managed Setup fixture uses the Windows Factorio recipe")
class ManagedRepairMakeReadyTests(unittest.TestCase):
    version = "2.0.77"
    executable_bytes = b"Generated inert installation fixture; never execute.\n"

    def call(self, workspace: Path, *arguments: str, code: int = 0) -> dict:
        actual, output, error = invoke_machine(["--workspace", str(workspace), *arguments, "--json"])
        self.assertEqual((code, ""), (actual, error), output)
        return json.loads(output)

    def prepare(self, root: Path, content_pending: bool = False, selected_world: bool = False) -> tuple[Path, Path, Path]:
        archive = root / "source.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as output:
            output.writestr("factorio/bin/x64/factorio.exe", self.executable_bytes)
            output.writestr("factorio/data/base/info.json", json.dumps({"name": "base", "version": self.version}))
        workspace = root / "workspace"
        target = root / "target"
        plan = self.call(workspace, "installs", "install", "plan", self.version, "--archive", str(archive),
                         "--target", str(target), "--id", "managed")["payload"]
        applied_at = (datetime.datetime.fromisoformat(plan["created_at"].replace("Z", "+00:00")) +
                      datetime.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.call(workspace, "installs", "install", "apply", plan["plan_id"], "--version", self.version,
                  "--archive", str(archive), "--target", str(target), "--id", "managed", "--digest", plan["plan_digest"],
                  "--plan-created-at", plan["created_at"], "--transaction-id", "tx-install-fixture", "--applied-at", applied_at,
                  "--confirm", "APPLY")
        self.call(workspace, "instances", "create", "Main", "--id", "main", "--install", "managed")
        self.call(workspace, "modsets", "apply", "main", "--enable", "base")
        instance = workspace / "instances/main"
        if selected_world:
            write_save(instance / "saves/selected.zip", b"Generated selected world")
            self.call(workspace, "profiles", "apply", "main", "gui", "--selection-mode", "load-save", "--selection", "selected.zip")
        (instance / "config/config.ini").unlink()
        if content_pending:
            (instance / "mods/mod-list.json").unlink()
        (target / "operator-note.txt").write_bytes(b"Preserve unowned local information.\n")
        (target / "bin/x64/factorio.exe").unlink()
        return workspace, target, archive

    def environment(self, root: Path) -> dict[str, str]:
        return dict(FACMAN_SETUP_STATE_ROOT=str(root / "setup-state"),
                    FACMAN_SETUP_ACCEPTANCE_ROOT=str(root),
                    FACMAN_SETUP_POLICY_ACTIVATION="operator_acceptance_candidate")

    @contextmanager
    def pre_admitted_controls(self, workspace: Path):
        executable = facman_executable().parent / "facman_execution_foundation_smoke.exe"
        self.assertTrue(executable.is_file())
        children = []
        try:
            for identity in ("main", "other"):
                instance = workspace / "instances" / identity
                child = subprocess.Popen([str(executable), "--pre-admitted-lock-control", str(instance)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                children.append((instance, child))
                deadline = time.monotonic() + 20
                while not (instance / ".facman-test-pre-admitted-launch").is_file():
                    self.assertIsNone(child.poll(), "owned admitted-launch control exited before its barrier")
                    self.assertLess(time.monotonic(), deadline, "owned admitted-launch barrier timed out")
                    time.sleep(0.01)
            yield children
        finally:
            for _, child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)

    def query(self, workspace: Path, review: str = "", intent: str = "menu") -> dict:
        args = ["presentation", "query", "instances", "--instance", "main", "--intent", intent]
        if review:
            args += ["--repair-review-id", review]
        return self.call(workspace, *args)["payload"]

    def review_args(self, workspace: Path, archive: Path, key: str = "review") -> list[str]:
        return ["--workspace", str(workspace), "presentation", "action", "readiness.review_install_repair",
                "--scope", "instances", "--instance", "main", "--installation", "managed", "--source-path", str(archive),
                "--expected-revision", self.query(workspace)["revision"], "--request-id", key, "--idempotency-key", key,
                "--operation-id", key, "--attempt-id", key, "--confirmation", "explicit", "--json"]

    def review(self, workspace: Path, archive: Path, key: str = "review") -> tuple[list[str], dict]:
        args = self.review_args(workspace, archive, key)
        response = invoke_machine(args)
        self.assertEqual((0, ""), (response[0], response[2]), response[1])
        receipt = json.loads(response[1])["payload"]
        self.assertEqual("completed", receipt["outcome"])
        factorio_validator("factorio_managed_repair_review.v1.schema.json").validate(receipt["action_payload"])
        return args, receipt

    def apply_args(self, workspace: Path, key: str = "review", identity: str = "joined", intent: str = "menu") -> list[str]:
        observed = self.query(workspace, key, intent)
        plan = observed["dependency_identities"]["joined_preparation"]["plan"]
        self.assertIsNotNone(plan, observed["dependency_identities"]["joined_preparation"])
        factorio_validator("factorio_make_ready_joined_plan.v3.schema.json").validate(plan)
        args = JoinedMakeReadyTests.arguments(self, workspace, observed, identity)
        args += ["--repair-review-id", key, "--installation-path", plan["installation_root"],
                 "--source-path", plan["installation_plan"]["plan_request"]["archive"]["path"]]
        return args

    def test_exact_owner_repair_then_current_preparation_and_replay(self) -> None:
        for content_pending in (False, True):
            with self.subTest(content_pending=content_pending), tempfile.TemporaryDirectory(prefix="joined-repair-") as value:
                root = Path(value)
                with patch.dict(os.environ, self.environment(root)):
                    workspace, target, archive = self.prepare(root, content_pending, selected_world=content_pending)
                    before = snapshot(target)
                    review_args, reviewed = self.review(workspace, archive)
                    self.assertEqual(["workspace_write", "setup_preview"], reviewed["effects"])
                    self.assertEqual(before, snapshot(target))
                    frozen = snapshot(root)
                    intent = "load_save" if content_pending else "menu"
                    initial = self.query(workspace, "review", intent)
                    descriptor = next(action for action in initial["available_semantic_actions"] if action["action_id"] == "readiness.prepare_joined")
                    self.assertEqual(["setup_mutation", "workspace_write"], descriptor["effects"])
                    self.assertEqual(initial["revision"], self.query(workspace, "review", intent)["revision"])
                    self.assertEqual(frozen, snapshot(root))
                    self.assertIsNone(self.query(workspace)["dependency_identities"]["joined_preparation"]["plan"])
                    args = self.apply_args(workspace, intent=intent)
                    time.sleep(1.05)  # Owner requires actual advancing UTC seconds.
                    result = invoke_machine(args)
                    self.assertEqual((0, ""), (result[0], result[2]), result[1])
                    receipt = json.loads(result[1])["payload"]
                    self.assertEqual("completed", receipt["outcome"])
                    self.assertEqual(["workspace_write", "setup_mutation"], receipt["effects"])
                    payload = receipt["action_payload"]
                    factorio_validator("factorio_make_ready_joined_result.v3.schema.json").validate(payload)
                    self.assertTrue(payload["installation_effect_verified"])
                    self.assertTrue(payload["completed_effects_verified"])
                    self.assertFalse(payload["execution_started"])
                    self.assertFalse(payload["permit_issued"])
                    expected = ["installs.repair.apply"] + (["modsets.apply"] if content_pending else []) + ["readiness.prepare_configuration"] + (["readiness.prepare_selected_save"] if content_pending else [])
                    self.assertEqual(expected, [effect["owner_command"] for effect in payload["completed_components"]])
                    self.assertEqual(self.executable_bytes, (target / "bin/x64/factorio.exe").read_bytes())
                    self.assertEqual(b"Preserve unowned local information.\n", (target / "operator-note.txt").read_bytes())
                    repair = payload["completed_components"][0]
                    journal = json.loads((workspace / "transactions" / (repair["transaction_id"] + ".transaction.v1.json")).read_bytes())
                    context = json.loads(journal["operation_context"])
                    owner_plan = reviewed["action_payload"]["owner_plan"]
                    self.assertEqual("complete", journal["state"])
                    self.assertEqual(owner_plan["plan_request"], context["plan_request"])
                    self.assertEqual(owner_plan["provider_plan"], context["provider_plan"])
                    self.assertEqual(owner_plan["plan_digest"], context["reviewed_plan_digest"])
                    frozen = snapshot(root)
                    self.assertEqual(receipt, json.loads(invoke_machine(args)[1])["payload"])
                    self.assertEqual(reviewed, json.loads(invoke_machine(review_args)[1])["payload"])
                    self.assertEqual(frozen, snapshot(root))

    def test_setup_domain_admission_refuses_before_planning_or_repair_receipt_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-repair-admission-") as value:
            root = Path(value)
            with patch.dict(os.environ, self.environment(root)):
                workspace, target, archive = self.prepare(root)
                args = self.review_args(workspace, archive, "denied-review")
                frozen = snapshot(root)
                with patch.dict(os.environ, {"FACMAN_SETUP_POLICY_ACTIVATION": ""}):
                    result = invoke_machine(args)
                self.assertEqual(1, result[0], result[1])
                self.assertEqual("setup_repair_plan_authority_required", json.loads(result[1])["error"]["code"])
                self.assertEqual(frozen, snapshot(root))
                self.review(workspace, archive)
                args = self.apply_args(workspace, identity="denied-apply")
                frozen = snapshot(root)
                with patch.dict(os.environ, {"FACMAN_SETUP_POLICY_ACTIVATION": ""}):
                    result = invoke_machine(args)
                self.assertEqual(1, result[0], result[1])
                self.assertEqual("setup_authority_required", json.loads(result[1])["error"]["code"])
                self.assertEqual(frozen, snapshot(root))
                self.assertFalse((target / "bin/x64/factorio.exe").exists())

    def test_retained_archive_and_all_registered_run_leases_survive_after_owner_guard(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-repair-custody-") as value:
            root = Path(value)
            with patch.dict(os.environ, self.environment(root)):
                workspace, target, archive = self.prepare(root)
                # Register a second ordinary instance before repair takes its census.
                self.call(workspace, "instances", "create", "Other", "--id", "other", "--install", "managed")
                with self.pre_admitted_controls(workspace) as launchers:
                    self.review(workspace, archive)
                    args = self.apply_args(workspace)
                    time.sleep(1.05)
                    marker = workspace / ".facman-test-joined-repair-before-provider"
                    release = marker.with_name(marker.name + "-release")
                    worker = PausedAction(args, dict(os.environ, FACMAN_TEST_JOINED_REPAIR_PAUSE_BEFORE_PROVIDER="1"))
                    try:
                        wait_for_owned_marker(worker, marker, release)
                        self.assertFalse((target / "bin/x64/factorio.exe").exists(), "provider entered before the deterministic barrier")
                        # This is AFTER the callback returned. Windows custody must
                        # deny rename/replacement, not merely detect it next time.
                        with self.assertRaises(OSError):
                            archive.rename(archive.with_suffix(".substituted"))
                        with self.assertRaises(OSError):
                            archive.write_bytes(archive.read_bytes())
                        substituted_parent = root.with_name(root.name + "-substituted-parent")
                        try:
                            root.rename(substituted_parent)
                        except OSError:
                            pass
                        else:
                            substituted_parent.rename(root)
                            self.fail("retained archive parent custody allowed namespace replacement")
                        for instance_id in ("main", "other"):
                            run_lock = workspace / "instances" / instance_id / "locks/run.lock"
                            self.assertTrue(run_lock.is_file())
                            with self.assertRaises(OSError):
                                run_lock.unlink()
                        for instance, child in launchers:
                            (instance / ".facman-test-pre-admitted-launch-release").write_bytes(b"release\n")
                            output, error = child.communicate(timeout=10)
                            self.assertEqual((0, ""), (child.returncode, error), output)
                            self.assertIn("supervisor calls=0", output)
                        release.write_bytes(b"release\n")
                    finally:
                        if not release.exists(): release.write_bytes(b"release\n")
                        worker.finish()
                        for _, child in launchers:
                            if child.poll() is None:
                                child.kill()
                                child.communicate(timeout=10)
                    self.assertEqual(0, worker.response[0], worker.response[1])
                    self.assertEqual(self.executable_bytes, (target / "bin/x64/factorio.exe").read_bytes())
                    for instance_id in ("main", "other"):
                        self.assertFalse((workspace / "instances" / instance_id / "locks/run.lock").exists())

    def test_new_reference_after_census_cannot_launch_and_invalidates_repair_before_provider(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-repair-new-reference-") as value:
            root = Path(value)
            with patch.dict(os.environ, self.environment(root)):
                workspace, target, archive = self.prepare(root)
                self.review(workspace, archive)
                args = self.apply_args(workspace)
                time.sleep(1.05)
                marker = workspace / ".facman-test-joined-repair-before-provider"
                release = marker.with_name(marker.name + "-release")
                worker = PausedAction(args, dict(os.environ, FACMAN_TEST_JOINED_REPAIR_PAUSE_BEFORE_PROVIDER="1"))
                try:
                    wait_for_owned_marker(worker, marker, release)
                    self.call(workspace, "instances", "create", "Late", "--id", "late", "--install", "managed")
                    observed = self.call(workspace, "presentation", "query", "instances", "--instance", "late")["payload"]
                    action = next(item for item in observed["available_semantic_actions"] if item["action_id"] == "launch.play")
                    self.assertEqual("instance_recovery_required", action["refusal"]["code"])
                    response = self.call(workspace, "presentation", "action", "launch.play", "--scope", "instances", "--instance", "late",
                        "--expected-revision", observed["revision"], "--request-id", "late-launch", "--idempotency-key", "late-launch",
                        "--operation-id", "late-launch", "--attempt-id", "late-launch", "--confirmation", "explicit", code=1)
                    self.assertEqual("instance_recovery_required", response["error"]["code"])
                    release.write_bytes(b"release\n")
                finally:
                    if not release.exists(): release.write_bytes(b"release\n")
                    worker.finish()
                self.assertEqual(1, worker.response[0], worker.response[1])
                self.assertFalse((target / "bin/x64/factorio.exe").exists())
                self.assertTrue((workspace / "instances/late").is_dir())
                self.assertFalse((workspace / "instances/main/locks/run.lock").exists())

    def test_checkpoint_persistence_failure_retains_owner_effect_and_foreign_receipt_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-repair-checkpoint-") as value:
            root = Path(value)
            with patch.dict(os.environ, self.environment(root)):
                workspace, target, archive = self.prepare(root)
                self.review(workspace, archive)
                args = self.apply_args(workspace)
                time.sleep(1.05)
                marker = workspace / ".facman-test-joined-repair-before-provider"
                release = marker.with_name(marker.name + "-release")
                receipt = workspace / ".facman/action-receipts-v2" / (hashlib.sha256(b"joined").hexdigest() + ".v2.json")
                retained = receipt.with_suffix(".retained-fixture")
                worker = PausedAction(args, dict(os.environ, FACMAN_TEST_JOINED_REPAIR_PAUSE_BEFORE_PROVIDER="1"))
                try:
                    wait_for_owned_marker(worker, marker, release)
                    original = receipt.read_bytes()
                    receipt.rename(retained)
                    receipt.mkdir()
                    release.write_bytes(b"release\n")
                finally:
                    if not release.exists(): release.write_bytes(b"release\n")
                    worker.finish()
                self.assertEqual(4, worker.response[0], worker.response[1])
                self.assertEqual(self.executable_bytes, (target / "bin/x64/factorio.exe").read_bytes())
                self.assertFalse((workspace / "instances/main/config/config.ini").exists())
                self.assertTrue(receipt.is_dir())
                self.assertEqual(original, retained.read_bytes())
                frozen = snapshot(root)
                replay = invoke_machine(args)
                self.assertNotEqual(0, replay[0], replay[1])
                self.assertEqual(frozen, snapshot(root))

    def test_actual_v3_receipts_require_recursive_ordinary_frontend_owner_validation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-repair-feedback-") as value:
            root = Path(value)
            cases = []
            for pending in (False, True):
                case_root = root / ("content" if pending else "routing")
                case_root.mkdir()
                with patch.dict(os.environ, self.environment(case_root)):
                    workspace, _, archive = self.prepare(case_root, pending, selected_world=True)
                    self.review(workspace, archive)
                    identity = "feedback-v3"
                    args = self.apply_args(workspace, identity=identity, intent="load_save")
                    time.sleep(1.05)
                    actual = invoke_machine(args)
                    self.assertEqual(0, actual[0], actual[1])
                    envelope = json.loads(actual[1])
                    stored = workspace / ".facman/action-receipts-v2" / (hashlib.sha256(identity.encode()).hexdigest() + ".v2.json")
                    inputs = json.loads(json.loads(stored.read_bytes())["request_json"])
                    ids = dict(request_id=identity, operation_id=identity, attempt_id=identity)
                    def add(name, mutation=None, expected=False):
                        changed = copy.deepcopy(envelope)
                        if mutation: mutation(changed["payload"]["action_payload"])
                        cases.append(dict(name=f"{'v2' if pending else 'v1'}-{name}", envelope=json.dumps(changed),
                            input=inputs, identity=ids, exit_code=0, expected_clear=False, expected_installation_summary=expected))
                    add("actual-completed", expected=True)
                    add("missing-installation-effect", lambda p: p["completed_components"].pop(0))
                    add("foreign-installation", lambda p: p["completed_components"][0]["owner_result"].update(install_id="foreign"))
                    add("foreign-original-plan", lambda p: p["plan"]["installation_plan"].update(plan_digest="0" * 64))
                    add("flattened-effect-substitution", lambda p: p["completed_components"][-1]["owner_result"].update(instance_id="foreign"))
                    add("missing-nested-effects", lambda p: p["joined_result"].update(completed_components=[]))
                    add("missing-nested-configuration-world", lambda p: p["joined_result"].update(joined_result={}) if pending else p["joined_result"].update(completed_components=[]))
                    add("foreign-nested-desired", lambda p: p["joined_result"]["plan"]["desired_state"].update(profile_id="foreign"))
                    add("unverified-installation", lambda p: p.update(installation_effect_verified=False))
                    add("invented-permit", lambda p: p.update(permit_issued=True))
            corpus = root / "v3-feedback.json"
            corpus.write_text(json.dumps(dict(request_id="feedback-v3", operation_id="feedback-v3", attempt_id="feedback-v3", cases=cases)), encoding="utf-8")
            native = facman_executable().parent / "facman_tui_product_model_smoke.exe"
            self.assertTrue(native.is_file(), "paired native TUI feedback proof must be built by the admitted owner")
            checked = subprocess.run([str(native), str(corpus)], capture_output=True, text=True, timeout=60)
            self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)
            project = ROOT / "tests/winforms_control_gallery/FacMan.SelectedSave.Harness.csproj"
            build = subprocess.run([msbuild_executable(), str(project), "/m:2", "/nr:false", "/p:UseSharedCompilation=false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={root / 'bin'}{os.sep}",
                f"/p:IntermediateOutputPath={root / 'obj'}{os.sep}", f"/p:BaseIntermediateOutputPath={root / 'obj'}{os.sep}"],
                cwd=ROOT, capture_output=True, text=True, timeout=120)
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            checked = subprocess.run([str(root / "bin/FacMan.SelectedSave.Harness.exe"), "make-ready-continuation", str(corpus)],
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)

    def test_changed_source_preimage_and_foreign_reviews_refuse_without_repair(self) -> None:
        for mutation in ("source-replacement", "source-bytes", "source-missing", "record", "foreign-review", "read-only", "foreign", "run-lock"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(prefix="joined-repair-refuse-") as value:
                root = Path(value)
                with patch.dict(os.environ, self.environment(root)):
                    workspace, target, archive = self.prepare(root)
                    self.review(workspace, archive)
                    if mutation == "source-replacement":
                        retained = archive.with_suffix(".retained")
                        archive.rename(retained)
                        archive.write_bytes(retained.read_bytes())
                    elif mutation == "source-bytes":
                        archive.write_bytes(archive.read_bytes() + b"changed")
                    elif mutation == "source-missing":
                        archive.unlink()
                    elif mutation in ("record", "read-only", "foreign"):
                        record = next((workspace / "installs/refs").glob("*.json"))
                        content = json.loads(record.read_bytes())
                        content["state_revision" if mutation == "record" else "ownership"] = "changed" if mutation == "record" else "imported" if mutation == "read-only" else "foreign"
                        record.write_text(json.dumps(content), encoding="utf-8")
                    elif mutation == "run-lock":
                        (workspace / "instances/main/locks/run.lock").write_bytes(b"active fixture writer\n")
                    frozen = snapshot(target)
                    observation = self.query(workspace, "other-review" if mutation == "foreign-review" else "review")
                    joined = observation["dependency_identities"]["joined_preparation"]
                    self.assertIsNone(joined["plan"])
                    self.assertIsNotNone(joined["refusal"])
                    self.assertEqual(frozen, snapshot(target))
                    self.assertFalse((target / "bin/x64/factorio.exe").exists())

    def test_concurrent_retry_and_stale_inputs_at_actual_dispatch_boundaries(self) -> None:
        for boundary in ("before-installation", "after-installation"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory(prefix="joined-repair-race-") as value:
                root = Path(value)
                with patch.dict(os.environ, self.environment(root)):
                    workspace, target, archive = self.prepare(root)
                    self.review(workspace, archive)
                    args = self.apply_args(workspace)
                    time.sleep(1.05)
                    instance = workspace / "instances/main"
                    marker = instance / (".facman-test-make-ready-" + boundary)
                    release = marker.with_name(marker.name + "-release")
                    variable = "FACMAN_TEST_MAKE_READY_PAUSE_" + boundary.replace("-", "_").upper()
                    worker = PausedAction(args, dict(os.environ, **{variable: "1"}))
                    try:
                        wait_for_owned_marker(worker, marker, release)
                        # The accepted identity is already owned. A competing replay
                        # must observe uncertainty rather than dispatch a second owner.
                        repeated = invoke_machine(args)
                        self.assertEqual(4, repeated[0], repeated[1])
                        self.assertEqual("outcome_unknown", json.loads(repeated[1])["payload"]["outcome"])
                        if boundary == "before-installation":
                            retained = archive.with_suffix(".retained")
                            archive.rename(retained)
                            archive.write_bytes(retained.read_bytes())
                        else:
                            (instance / "mods/mod-settings.dat").write_bytes(b"changed after retained installation effect\n")
                        release.write_bytes(b"release\n")
                    finally:
                        if not release.exists():
                            release.write_bytes(b"release\n")
                        worker.finish()
                    actual, output, error = worker.response
                    self.assertEqual("", error, output)
                    payload = json.loads(output)["payload"]
                    self.assertNotEqual(0, actual, output)
                    if boundary == "before-installation":
                        self.assertEqual("refused_before_effects", payload["outcome"])
                        self.assertFalse((target / "bin/x64/factorio.exe").exists())
                    else:
                        self.assertEqual("recovery_required", payload["outcome"])
                        self.assertEqual("fresh_request_after_input_correction", payload["action_payload"]["continuation"])
                        self.assertEqual(["installs.repair.apply"], [effect["owner_command"] for effect in payload["action_payload"]["completed_components"]])
                        self.assertEqual(self.executable_bytes, (target / "bin/x64/factorio.exe").read_bytes())
                    self.assertFalse((instance / "config/config.ini").exists())
                    frozen = snapshot(root)
                    self.assertEqual(payload, json.loads(invoke_machine(args)[1])["payload"])
                    self.assertEqual(frozen, snapshot(root))

    def test_provider_partial_checkpoint_and_retry_preserve_accepted_work(self) -> None:
        for fault in ("FACMAN_TEST_REPAIR_INTERRUPT_AFTER_PROVIDER", "FACMAN_TEST_MAKE_READY_OWNER_RESULT_UNKNOWN",
                      "FACMAN_TEST_MAKE_READY_EXIT_AFTER_INSTALLATION", "FACMAN_TEST_MAKE_READY_EXIT_AFTER_INSTALLATION_OWNER"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix="joined-repair-partial-") as value:
                root = Path(value)
                with patch.dict(os.environ, self.environment(root)):
                    workspace, target, archive = self.prepare(root)
                    self.review(workspace, archive)
                    args = self.apply_args(workspace)
                    time.sleep(1.05)
                    with patch.dict(os.environ, {fault: "installation" if fault.endswith("UNKNOWN") else "1"}):
                        actual, output, error = invoke_machine(args)
                    self.assertEqual("", error, output)
                    if "EXIT_AFTER_INSTALLATION" in fault:
                        self.assertEqual(91 if fault.endswith("OWNER") else 92, actual, output)
                    else:
                        self.assertNotEqual(0, actual, output)
                        self.assertEqual("recovery_required", json.loads(output)["payload"]["outcome"])
                    self.assertEqual(self.executable_bytes, (target / "bin/x64/factorio.exe").read_bytes())
                    self.assertFalse((workspace / "instances/main/config/config.ini").exists())
                    frozen = snapshot(root)
                    replay = invoke_machine(args)
                    self.assertNotEqual(0, replay[0], replay[1])
                    self.assertEqual(frozen, snapshot(root))

    def test_ordinary_tui_review_automatically_prepares_executable_content_configuration_and_selected_world(self) -> None:
        from test_windows_delivered_joined_gui import OwnedProcessJob
        with tempfile.TemporaryDirectory(prefix="joined-repair-tui-") as value:
            root = Path(value)
            with patch.dict(os.environ, self.environment(root)):
                workspace, target, archive = self.prepare(root, content_pending=True, selected_world=True)
                initial = self.query(workspace, intent="load_save")
                actions = initial["available_semantic_actions"]
                index = next(i for i, action in enumerate(actions) if action["action_id"] == "readiness.review_install_repair")
                refresh_index = next(i for i, action in enumerate(actions) if action["action_id"] == "presentation.refresh")
                joined_index = next(i for i, action in enumerate(actions) if action["action_id"] == "readiness.prepare_joined")
                navigation = "tab\n" * max(0, index - refresh_index) + "shift-tab\n" * max(0, refresh_index - index)
                script = "s\n2\n" + navigation + "space\nsource_path=" + str(archive) + "\nspace\nspace\n2\n"
                before = snapshot(target)
                with (root / "ordinary-tui.log").open("w+", encoding="utf-8") as transcript:
                    process = subprocess.Popen([str(facman_executable()), "tui", "--workspace", str(workspace), "--ordinary", "--plain"],
                        stdin=subprocess.PIPE, stdout=transcript, stderr=subprocess.PIPE, text=True, cwd=ROOT, creationflags=0x4)
                    job = None
                    try:
                        job = OwnedProcessJob(process, facman_executable(), require_backend=False)
                        process.stdin.write(script)
                        process.stdin.flush()
                        deadline = time.monotonic() + 45
                        reviews = []
                        while not reviews:
                            job.observe()
                            self.assertIsNone(process.poll(), "ordinary TUI exited before review completed")
                            self.assertLess(time.monotonic(), deadline, "ordinary review did not publish a completed receipt")
                            for path in (workspace / ".facman/action-receipts-v2").glob("*.v2.json"):
                                stored = json.loads(path.read_bytes())
                                if stored["action_id"] == "readiness.review_install_repair" and stored["state"] == "terminal":
                                    reviews.append(stored)
                            time.sleep(.025)
                        self.assertEqual(1, len(reviews))
                        self.assertEqual(before, snapshot(target), "ordinary review must retain installation preimage")
                        reviewed = json.loads(reviews[0]["result_json"])["action_payload"]
                        observation = self.query(workspace, reviews[0]["idempotency_key"], "load_save")
                        plan = observation["dependency_identities"]["joined_preparation"]["plan"]
                        self.assertEqual(reviewed["owner_plan"], plan["installation_plan"])
                        self.assertEqual(reviewed["archive_source_identity"], plan["archive_source_identity"])
                        time.sleep(1.05)  # Retain the existing owner timestamp contract.
                        continuation = "tab\n" * (joined_index - index) + "space\nspace\nq\n"
                        _, error = process.communicate(continuation, timeout=45)
                        self.assertEqual((0, ""), (process.returncode, error))
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.communicate(timeout=10)
                        if job is not None:
                            job.finish()
                    transcript.seek(0)
                    output = transcript.read()
                self.assertIn("Confirm Review installation repair from local archive", output)
                self.assertIn("Confirm Repair registered installation executable", output)
                receipts = [json.loads(p.read_bytes()) for p in (workspace / ".facman/action-receipts-v2").glob("*.v2.json")]
                applied = [r for r in receipts if r["action_id"] == "readiness.prepare_joined"]
                self.assertEqual(1, len(applied), output)
                outcome = json.loads(applied[0]["result_json"])
                request = json.loads(applied[0]["request_json"])
                self.assertEqual("completed", outcome["outcome"], output)
                self.assertEqual(reviews[0]["idempotency_key"], request["repair_review_id"])
                self.assertEqual(str(archive), request["source_path"])
                self.assertEqual(reviewed["owner_plan"], outcome["action_payload"]["plan"]["installation_plan"])
                self.assertEqual(["installs.repair.apply", "modsets.apply", "readiness.prepare_configuration", "readiness.prepare_selected_save"],
                    [effect["owner_command"] for effect in outcome["action_payload"]["completed_components"]])
                self.assertEqual(self.executable_bytes, (target / "bin/x64/factorio.exe").read_bytes())
                self.assertTrue((workspace / "instances/main/config/config.ini").is_file())
                current = self.query(workspace, intent="load_save")
                self.assertEqual("satisfied", current["readiness"]["selected_save"]["state"])
                self.assertFalse(current["readiness"]["execution_available"])


if __name__ == "__main__":
    unittest.main()
