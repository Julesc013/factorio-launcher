# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tui_executable() -> Path | None:
    configured = os.environ.get("FACMAN_TUI_EXE") or os.environ.get("FACMAN_CLI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/r37-ux/Release/facman.exe",
        ROOT / "build/r36-tui/Debug/facman.exe",
        ROOT / "build/native-smoke/Debug/facman.exe",
        ROOT / "build/native-smoke/facman",
        ROOT / "build/macos-native/facman",
    ]
    return next((path for path in candidates if path.is_file()), None)


def cli_executable() -> Path | None:
    configured = os.environ.get("FACMAN_CLI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/r37-ux/Release/facman.exe",
        ROOT / "build/Release/facman.exe",
        ROOT / "build/native-smoke/Debug/facman.exe",
        ROOT / "build/native-smoke/facman",
        ROOT / "build/macos-native/facman",
    ]
    return next((path for path in candidates if path.is_file()), None)


def ordinary_action_tabs(projected: dict, action_id: str) -> str:
    """Navigate from the Refresh action preserved when opening an ordinary page."""
    actions = projected["available_semantic_actions"]
    current = next(i for i, action in enumerate(actions)
                   if action["action_id"] == "presentation.refresh")
    target = next(i for i, action in enumerate(actions) if action["action_id"] == action_id)
    return "tab\n" * ((target - current) % len(actions))


@unittest.skipUnless(tui_executable(), "optional: functional TUI build is not available")
class TuiProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.executable = tui_executable()
        assert cls.executable is not None

    def invoke(
        self,
        args: list[str],
        *,
        stdin: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        process_environment = os.environ.copy()
        if environment:
            process_environment.update(environment)
        return subprocess.run(
            [str(self.executable), "tui", *args],
            cwd=ROOT,
            input=stdin,
            check=False,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            env=process_environment,
        )

    def test_ordinary_shell_pages_launch_deck_and_advanced_handoff(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-tui-ordinary-") as temporary:
            workspace = Path(temporary) / "ordinary workspace"
            ordinary = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="2\n7\n8\nenter\nq\n",
            )
            self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
            self.assertIn("FacMan - Factorio Manager", ordinary.stdout)
            self.assertIn("Launch Deck", ordinary.stdout)
            self.assertIn("[2 Instances]", ordinary.stdout)
            self.assertIn("[7 Settings]", ordinary.stdout)
            self.assertIn("[8 Advanced]", ordinary.stdout)
            self.assertIn("FacMan guided terminal", ordinary.stdout)
            self.assertNotIn("\x1b[", ordinary.stdout)
            self.assertFalse(workspace.exists())

            semantic_pages = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="4\n5\n7\nq\n",
            )
            self.assertEqual(semantic_pages.returncode, 0, semantic_pages.stderr)
            self.assertIn("Launch profiles and instance-local content", semantic_pages.stdout)
            self.assertIn("gui - launch_profile", semantic_pages.stdout)
            self.assertIn("Select an instance to inspect saves", semantic_pages.stdout)
            self.assertIn("Preferences, support, and exact runtime identity", semantic_pages.stdout)
            self.assertIn("Preferred transport", semantic_pages.stdout)
            self.assertNotIn("Open Advanced for the complete generated content", semantic_pages.stdout)
            self.assertNotIn("Open Advanced for all save inspection", semantic_pages.stdout)
            self.assertFalse(workspace.exists())

            doctor_action = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="tab\nshift-tab\nspace\nq\n",
            )
            self.assertEqual(doctor_action.returncode, 0, doctor_action.stderr)
            self.assertIn("Actions", doctor_action.stdout)
            self.assertIn("Run Doctor", doctor_action.stdout)
            self.assertIn("Doctor completed:", doctor_action.stdout)
            self.assertFalse(workspace.exists())

            refresh_action = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="4\nspace\nq\n",
            )
            self.assertEqual(refresh_action.returncode, 0, refresh_action.stderr)
            self.assertIn("Refresh completed", refresh_action.stdout)
            self.assertIn("Launch profiles and instance-local content", refresh_action.stdout)
            self.assertFalse(workspace.exists())

            cli = cli_executable()
            if cli is not None:
                doctor_process = self.invoke(
                    [
                        "--workspace", str(workspace), "--ordinary", "--plain",
                        "--transport", "process", "--cli-path", str(cli),
                    ],
                    stdin="space\nq\n",
                )
                self.assertEqual(doctor_process.returncode, 0, doctor_process.stderr)
                self.assertIn("Doctor completed:", doctor_process.stdout)
                self.assertFalse(workspace.exists())

            no_color = self.invoke(
                ["--workspace", str(workspace), "--ordinary"],
                stdin="/main\nq\n",
                environment={"NO_COLOR": "1"},
            )
            self.assertEqual(no_color.returncode, 0, no_color.stderr)
            self.assertIn("Filter: main", no_color.stdout)
            self.assertNotIn("\x1b[", no_color.stdout)
            self.assertFalse(workspace.exists())

            cli = cli_executable()
            if cli is not None:
                process = self.invoke(
                    [
                        "--workspace", str(workspace), "--ordinary", "--plain",
                        "--transport", "process", "--cli-path", str(cli),
                    ],
                    stdin="q\n",
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertIn("FacMan - Factorio Manager", process.stdout)
                self.assertIn("Authoritative snapshot", process.stdout)
                self.assertFalse(workspace.exists())

    def test_ordinary_observation_choice_preserves_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-tui-observation-") as temporary:
            workspace = Path(temporary) / "absent"
            result = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="s\n2\nmenu\nselected-save\nm\nq\n",
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Observation: Selected Save", result.stdout)
            self.assertIn("Observation: Menu", result.stdout)
            self.assertNotIn("observation did not match", result.stderr)
            self.assertFalse(workspace.exists())

    def test_ordinary_offline_pack_import_cancels_then_reconstructs_without_selected_instance(self) -> None:
        from test_presentation_pack_import import PresentationPackImportTests, FIXTURE_INSTALL
        from test_portable_modpack_import import PortableModpackImportTests
        from test_local_modset_solver import snapshot
        from test_make_ready_joined import file_identity

        owner = PresentationPackImportTests()
        backend = cli_executable()
        self.assertIsNotNone(backend, "Ordinary process transport requires its paired CLI")
        with tempfile.TemporaryDirectory(prefix="tui offline pack \u03a9 ") as temporary:
            producer, consumer, archive = owner.prepare(Path(temporary), b"\x00binary settings\xff")
            sentinel = consumer / "user-owned/sentinel.bin"
            sentinel.parent.mkdir()
            sentinel.write_bytes(b"foreign player bytes\x00\xff")
            sentinel_before = sentinel.read_bytes(), file_identity(sentinel)
            projected = owner.query(consumer)
            self.assertIsNone(projected["selected_context"]["instance_id"])
            index = next(i for i, action in enumerate(projected["available_semantic_actions"])
                         if action["action_id"] == "modsets.import")
            label = "Import offline pack into new instance"
            form = "4\n" + "tab\n" * index + "space\n"
            form += "source_path=" + str(archive) + "\nnew_instance_id=reconstructed\n"
            form += "installation_id=fixture\ndisplay_name=Restored pack\n"
            args = ["--workspace", str(consumer), "--ordinary", "--plain",
                    "--transport", "process", "--cli-path", str(backend)]
            before = snapshot(consumer)
            protected = snapshot(producer), snapshot(FIXTURE_INSTALL)
            for suffix, marker in (("6\nq\n", "Action input: " + label),
                                   ("space\n6\nq\n", "Confirm " + label)):
                with self.subTest(cancel=marker):
                    cancelled = self.invoke(args, stdin=form + suffix)
                    self.assertEqual(0, cancelled.returncode, cancelled.stderr)
                    self.assertIn(marker, cancelled.stdout)
                    self.assertEqual(before, snapshot(consumer))
                    self.assertEqual(sentinel_before, (sentinel.read_bytes(), file_identity(sentinel)))
            confirmed = self.invoke(args, stdin=form + "space\nspace\nq\n")
            self.assertEqual(0, confirmed.returncode, confirmed.stderr)
            self.assertIn("Confirm " + label, confirmed.stdout)
            self.assertIn("Instance: Restored pack", confirmed.stdout)
            receipts = list((consumer / ".facman/action-receipts-v2").glob("*.v2.json"))
            self.assertEqual(1, len(receipts))
            recorded = json.loads(receipts[0].read_bytes())
            request, outcome = json.loads(recorded["request_json"]), json.loads(recorded["result_json"])
            self.assertEqual(("modsets.import", "content", "explicit", str(archive), "reconstructed", "fixture"),
                             tuple(request[k] for k in ("action_id", "scope", "confirmation", "source_path",
                                                        "new_instance_id", "installation_id")))
            self.assertEqual("completed", outcome["outcome"])
            self.assertEqual("reconstructed", outcome["replacement_snapshot"]["selected_context"]["instance_id"])
            PortableModpackImportTests().assert_reconstruction(consumer, archive)
            self.assertEqual(protected, (snapshot(producer), snapshot(FIXTURE_INSTALL)))
            self.assertEqual(sentinel_before, (sentinel.read_bytes(), file_identity(sentinel)))

    def test_ordinary_snapshot_producer_cancels_then_roundtrips_through_restore(self) -> None:
        from test_presentation_snapshot_create import PresentationSnapshotCreateTests
        from test_presentation_snapshot_restore import PresentationSnapshotRestoreTests
        from test_instance_snapshots import FIXTURE_INSTALL, FIXTURE_SAVE, call
        from test_local_modset_solver import snapshot

        owner = PresentationSnapshotCreateTests()
        with tempfile.TemporaryDirectory(prefix="tui producer \u03a9 ") as temporary:
            root = Path(temporary)
            workspace, instance = owner.prepare(root)
            projected = owner.query(workspace)
            index = next(i for i,a in enumerate(projected["available_semantic_actions"])
                         if a["action_id"] == "snapshots.create")
            fields = "selected_instance_id=main\nsnapshot_id=world\nsave=starter.zip\n"
            opening = "5\n" + "tab\n" * index + "space\n" + fields
            before, inputs = snapshot(workspace), (snapshot(instance), snapshot(workspace / "installs"))
            for suffix, marker in (("6\nq\n", "Action input: Create instance snapshot"),
                                   ("space\n6\nq\n", "Confirm Create instance snapshot")):
                cancelled = self.invoke(["--workspace", str(workspace), "--ordinary", "--plain"], stdin=opening+suffix)
                self.assertEqual(0, cancelled.returncode, cancelled.stderr)
                self.assertIn(marker, cancelled.stdout)
                self.assertEqual(before, snapshot(workspace))
            created = self.invoke(["--workspace", str(workspace), "--ordinary", "--plain"], stdin=opening+"space\nspace\nq\n")
            self.assertEqual(0, created.returncode, created.stderr)
            saved = json.loads(owner.receipt(workspace).read_bytes())
            request, outcome = json.loads(saved["request_json"]), json.loads(saved["result_json"])
            self.assertEqual(("world", "starter.zip", "explicit"),
                             (request["snapshot_id"], request["save"], request["confirmation"]))
            self.assertEqual("completed", outcome["outcome"])
            prefix = "  Operation: Snapshot created: "
            paths = [line[len(prefix):] for line in created.stdout.splitlines() if line.startswith(prefix)]
            self.assertTrue(paths, created.stdout)
            self.assertEqual(outcome["action_payload"]["path"], paths[-1])
            archive = Path(paths[-1])
            self.assertEqual(workspace / "snapshots/main/world.zip", archive)
            destination = root / "destination"
            call(destination, "installs", "import", str(FIXTURE_INSTALL), "--id", "local")
            restore = PresentationSnapshotRestoreTests()
            projected = restore.query(destination)
            self.assertIsNone(projected["selected_context"]["instance_id"])
            index = next(i for i,a in enumerate(projected["available_semantic_actions"])
                         if a["action_id"] == "snapshots.restore")
            text = "5\n" + "tab\n" * index + "space\nsource_path=" + str(archive)
            text += "\nnew_instance_id=restored\ninstallation_id=local\nspace\nspace\nq\n"
            restored = self.invoke(["--workspace", str(destination), "--ordinary", "--plain"], stdin=text)
            self.assertEqual(0, restored.returncode, restored.stderr)
            result = json.loads(json.loads(restore.semantic_receipt(destination).read_bytes())["result_json"])
            self.assertEqual("restored", result["replacement_snapshot"]["selected_context"]["instance_id"])
            self.assertEqual("local", json.loads((destination / "instances/restored/instance.v1.json").read_bytes())["install_ref"])
            self.assertEqual(FIXTURE_SAVE.read_bytes(), (destination / "instances/restored/saves/starter.zip").read_bytes())
            self.assertEqual(inputs, (snapshot(instance), snapshot(workspace / "installs")))

    def test_ordinary_edited_snapshot_name_requires_fresh_confirmation_before_cancel(self) -> None:
        from test_presentation_snapshot_create import PresentationSnapshotCreateTests
        from test_local_modset_solver import snapshot

        owner = PresentationSnapshotCreateTests()
        with tempfile.TemporaryDirectory(prefix="tui-edited-cancel-") as temporary:
            workspace, instance = owner.prepare(Path(temporary))
            projected = owner.query(workspace)
            index = next(i for i,a in enumerate(projected["available_semantic_actions"])
                         if a["action_id"] == "snapshots.create")
            opening = "5\n" + "tab\n" * index + "space\n"
            opening += "selected_instance_id=main\nsnapshot_id=first\nsave=starter.zip\nspace\n"
            before = snapshot(workspace)
            paths_before = sorted(p.relative_to(workspace).as_posix() for p in workspace.rglob("*"))
            protected = snapshot(instance), snapshot(workspace / "installs")
            result = self.invoke(["--workspace", str(workspace), "--ordinary", "--plain"],
                                 stdin=opening + "snapshot_id=second\nspace\n6\nq\n")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(2, result.stdout.count("Status: Confirm Create instance snapshot:"), result.stdout)
            self.assertIn("snapshot_id=second (required)", result.stdout)
            self.assertNotIn("Snapshot created:", result.stdout)
            self.assertEqual(before, snapshot(workspace))
            self.assertEqual(paths_before, sorted(p.relative_to(workspace).as_posix() for p in workspace.rglob("*")))
            self.assertEqual(protected, (snapshot(instance), snapshot(workspace / "installs")))

    @unittest.skipUnless(os.name == "nt" or sys.platform in ("linux", "darwin"),
                         "unsupported: selected-context publication requires Windows, Linux or macOS")
    def test_ordinary_selected_context_refresh_keeps_its_action_feedback(self) -> None:
        from test_selected_context_refresh import SelectedContextRefreshTests

        owner = SelectedContextRefreshTests()
        cli = cli_executable()
        self.assertIsNotNone(cli)
        with tempfile.TemporaryDirectory(prefix="tui-refresh-feedback-") as temporary:
            workspace = Path(temporary)
            instance, _, _ = owner.owned(workspace)
            owner.drift(instance)
            world = (instance / "saves/selected.zip").read_bytes()
            projected = owner.query(workspace)
            actions = projected["available_semantic_actions"]
            index = next(i for i, action in enumerate(actions)
                         if action["action_id"] == "readiness.prepare_selected_save")
            self.assertEqual("Refresh selected save context", actions[index]["label"])
            result = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain",
                 "--transport", "process", "--cli-path", str(cli)],
                stdin="s\n2\n" + ordinary_action_tabs(projected, "readiness.prepare_selected_save") + "space\nspace\nq\n",
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Status: Refresh selected save context completed", result.stdout)
            self.assertNotIn("Doctor completed:", result.stdout)
            self.assertEqual(world, (instance / "saves/selected.zip").read_bytes())
            self.assertEqual("satisfied", owner.query(workspace)["readiness"]["selected_save"]["state"])

    def test_ordinary_edited_snapshot_name_completes_only_after_renewed_confirmation(self) -> None:
        from test_presentation_snapshot_create import PresentationSnapshotCreateTests
        from test_local_modset_solver import snapshot
        from test_instance_snapshots import FIXTURE_SAVE

        owner = PresentationSnapshotCreateTests()
        with tempfile.TemporaryDirectory(prefix="tui-edited-confirm-") as temporary:
            workspace, instance = owner.prepare(Path(temporary))
            projected = owner.query(workspace)
            index = next(i for i,a in enumerate(projected["available_semantic_actions"])
                         if a["action_id"] == "snapshots.create")
            opening = "5\n" + "tab\n" * index + "space\n"
            opening += "selected_instance_id=main\nsnapshot_id=first\nsave=starter.zip\nspace\n"
            protected = snapshot(instance), snapshot(workspace / "installs")
            result = self.invoke(["--workspace", str(workspace), "--ordinary", "--plain"],
                                 stdin=opening + "snapshot_id=second\nspace\nspace\nq\n")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(2, result.stdout.count("Status: Confirm Create instance snapshot:"), result.stdout)
            receipts = list((workspace / ".facman/action-receipts-v2").glob("*.v2.json"))
            self.assertEqual(1, len(receipts))
            recorded = json.loads(receipts[0].read_bytes())
            request, outcome = json.loads(recorded["request_json"]), json.loads(recorded["result_json"])
            self.assertEqual(("main", "second", "starter.zip", "explicit"),
                             tuple(request[k] for k in ("selected_instance_id", "snapshot_id", "save", "confirmation")))
            self.assertEqual(("snapshots.create", "completed"), (outcome["action_id"], outcome["outcome"]))
            archive = workspace / "snapshots/main/second.zip"
            with zipfile.ZipFile(archive) as zipped:
                manifest = json.loads(zipped.read("manifest/snapshot.v1.json"))
                self.assertEqual(["starter.zip"], manifest["selected_saves"])
                self.assertEqual(FIXTURE_SAVE.read_bytes(), zipped.read("saves/starter.zip"))
                self.assertEqual(set(zipped.namelist()) - {"manifest/snapshot.v1.json"},
                                 {entry["path"] for entry in manifest["file_hashes"]})
                self.assertNotIn("mods/mod-settings.dat", zipped.namelist())
                for entry in manifest["file_hashes"]:
                    data = zipped.read(entry["path"])
                    self.assertEqual((entry["size"], entry["sha256"]), (len(data), hashlib.sha256(data).hexdigest()))
            self.assertEqual(dict(schema="factorio.snapshot_report.v1", command="snapshots.create", status="ok",
                instance_id="main", snapshot_id="second", path=str(archive), archive_bytes=archive.stat().st_size,
                file_count=len(manifest["file_hashes"]), selected_saves=["starter.zip"], deterministic=True,
                portable=True, secret_content_included=False, mutation_executed=True), outcome["action_payload"])
            self.assertIn("  Operation: Snapshot created: " + str(archive), result.stdout)
            self.assertIn("Status: Snapshot created: " + str(archive), result.stdout)
            self.assertNotIn("Doctor completed:", result.stdout)
            self.assertFalse((workspace / "snapshots/main/first.zip").exists())
            self.assertFalse((workspace / "snapshots/main/first.record.json").exists())
            self.assertEqual(protected, (snapshot(instance), snapshot(workspace / "installs")))

    def test_ordinary_saves_snapshot_form_navigation_cancel_and_confirm_without_selected_instance(self) -> None:
        from test_presentation_snapshot_restore import PresentationSnapshotRestoreTests
        from test_local_modset_solver import snapshot

        owner = PresentationSnapshotRestoreTests()
        with tempfile.TemporaryDirectory(prefix="tui-snapshot-") as temporary:
            archive, workspace, local = owner.prepare(Path(temporary))
            projected = owner.query(workspace)
            self.assertIsNone(projected["selected_context"]["instance_id"])
            index = next(i for i, action in enumerate(projected["available_semantic_actions"])
                         if action["action_id"] == "snapshots.restore")
            form = "5\n" + "tab\n" * index + "space\n"
            form += "source_path=" + str(archive) + "\nnew_instance_id=restored\ninstallation_id=local\nspace\n"
            before, inputs = snapshot(workspace), (snapshot(archive.parents[2]), snapshot(local))
            cancelled = self.invoke(["--workspace", str(workspace), "--ordinary", "--plain"],
                                    stdin=form + "6\nq\n")
            self.assertEqual(0, cancelled.returncode, cancelled.stderr)
            self.assertIn("Confirm Restore snapshot into new instance", cancelled.stdout)
            self.assertEqual(before, snapshot(workspace))
            confirmed = self.invoke(["--workspace", str(workspace), "--ordinary", "--plain"],
                                    stdin=form + "space\nq\n")
            self.assertEqual(0, confirmed.returncode, confirmed.stderr)
            self.assertIn("Confirm Restore snapshot into new instance", confirmed.stdout)
            receipt = json.loads(owner.semantic_receipt(workspace).read_bytes())
            request = json.loads(receipt["request_json"])
            semantic = json.loads(receipt["result_json"])
            self.assertEqual((str(archive), "restored", "local", "explicit"),
                             (request["source_path"], request["new_instance_id"], request["installation_id"], request["confirmation"]))
            self.assertEqual("completed", semantic["outcome"])
            self.assertEqual("restored", semantic["replacement_snapshot"]["selected_context"]["instance_id"])
            target = workspace / "instances/restored"
            self.assertEqual("local", json.loads((target / "instance.v1.json").read_bytes())["install_ref"])
            self.assertEqual((archive.parents[2] / "instances/main/saves/starter.zip").read_bytes(),
                             (target / "saves/starter.zip").read_bytes())
            self.assertEqual(inputs, (snapshot(archive.parents[2]), snapshot(local)))

    @unittest.skipUnless(sys.platform == "linux", "unsupported: ordinary POSIX publication is Linux only")
    def test_ordinary_selected_save_missing_configuration_then_context_linux(self) -> None:
        self.exercise_ordinary_selected_save_missing_configuration_then_context()

    def exercise_ordinary_selected_save_missing_configuration_then_context(
        self, *, evidence: list[dict] | None = None,
    ) -> None:
        from test_configuration_preparation import ConfigurationPreparationTests
        from test_local_modset_solver import snapshot

        owner = ConfigurationPreparationTests()

        def make_ready_input(projected: dict) -> str:
            actions = projected["available_semantic_actions"]
            self.assertIn("presentation.refresh", [action["action_id"] for action in actions])
            index = next(i for i, action in enumerate(actions)
                         if action["action_id"] == "readiness.prepare")
            descriptor = actions[index]
            self.assertEqual("available", descriptor["availability"])
            self.assertEqual("explicit", descriptor["confirmation"])
            self.assertEqual(["selected_instance_id"],
                             [field["field_id"] for field in descriptor["input_fields"]])
            self.assertEqual("main", descriptor["input_fields"][0]["default"])
            return ordinary_action_tabs(projected, "readiness.prepare")

        with tempfile.TemporaryDirectory(prefix="tui-posix-make-ready-") as temporary:
            workspace = Path(temporary)
            instance, _ = owner.prepare(workspace, "load_save", True)
            target = instance / "config/config.ini"
            sidecar = instance / "metadata/save-refs/selected.zip.save-ref.v1.json"
            effects = {"config/config.ini", "metadata/save-refs/selected.zip.save-ref.v1.json"}

            def preserved() -> dict[str, bytes]:
                return {p.relative_to(instance).as_posix(): p.read_bytes() for p in instance.rglob("*")
                        if p.is_file() and p.relative_to(instance).as_posix() not in effects
                        and "locks" not in p.relative_to(instance).parts}

            inputs = preserved()
            install_inputs = snapshot(workspace / "fixture-install")
            selected = owner.query(workspace, intent="load_save")
            before = snapshot(workspace)
            cancelled = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="s\n2\n" + make_ready_input(selected) + "space\nm\ns\nspace\nq\n")
            self.assertEqual(0, cancelled.returncode, cancelled.stderr)
            self.assertIn("Confirm Make Ready", cancelled.stdout)
            self.assertFalse(target.exists())
            self.assertFalse(sidecar.exists())
            self.assertEqual(before, snapshot(workspace), "Observation changes must invalidate pending confirmation")
            receipt_root = workspace / ".facman/action-receipts-v2"
            old_receipts = set(receipt_root.glob("*.v2.json"))
            revisions = []
            configuration_identity = None
            for component, dependency, owner_command, published in (
                ("routing_configuration", "configuration_preparation", "readiness.prepare_configuration", target),
                ("selected_save_declared_context", "selected_save_preparation", "readiness.prepare_selected_save", sidecar),
            ):
                frozen = snapshot(workspace)
                reviewed = owner.query(workspace, intent="load_save")
                self.assertEqual(frozen, snapshot(workspace), "Fresh planning must be read only")
                if revisions:
                    self.assertNotEqual(revisions[-1], reviewed["revision"])
                    configuration = reviewed["dependency_identities"]["configuration_preparation"]
                    self.assertIsNone(configuration["plan"])
                    self.assertEqual("configuration_already_current", configuration["refusal"]["code"])
                revisions.append(reviewed["revision"])
                plan = reviewed["dependency_identities"][dependency]["plan"]
                result = self.invoke(
                    ["--workspace", str(workspace), "--ordinary", "--plain"],
                    stdin="s\n2\n" + make_ready_input(reviewed) + "space\nspace\nq\n")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("Observation: Selected Save", result.stdout)
                self.assertIn("Confirm Make Ready", result.stdout)
                new_receipts = set(receipt_root.glob("*.v2.json")) - old_receipts
                self.assertEqual(1, len(new_receipts), result.stdout)
                receipt = json.loads(new_receipts.pop().read_bytes())
                request = json.loads(receipt["request_json"])
                semantic = json.loads(receipt["result_json"])
                self.assertEqual("readiness.prepare", request["action_id"])
                self.assertTrue(request["request_id"].startswith("tui-readiness-prepare-"))
                self.assertEqual("instances", request["scope"])
                self.assertEqual("main", request["selected_instance_id"])
                self.assertEqual("explicit", request["confirmation"])
                self.assertEqual("load_save", request["launch_intent"])
                self.assertEqual(reviewed["revision"], request["expected_snapshot_revision"])
                self.assertEqual(hashlib.sha256(receipt["request_json"].encode()).hexdigest(), receipt["request_fingerprint"])
                self.assertEqual(hashlib.sha256(receipt["result_json"].encode()).hexdigest(), receipt["result_digest"])
                self.assertEqual(request["request_id"], semantic["request_id"])
                self.assertEqual("completed", semantic["outcome"])
                payload = semantic["action_payload"]
                self.assertEqual("load_save", payload["launch_intent"])
                self.assertEqual("partial", payload["composition"])
                self.assertFalse(payload["readiness_complete"])
                self.assertFalse(payload["execution_started"])
                self.assertFalse(payload["permit_issued"])
                effect, = payload["completed_components"]
                self.assertEqual(component, effect["component"])
                self.assertEqual(plan["plan_sha256"], effect["plan_sha256"])
                self.assertEqual(owner_command, effect["owner_command"])
                journal = workspace / "transactions" / (effect["transaction_id"] + ".transaction.v1.json")
                transaction = json.loads(journal.read_bytes())
                self.assertEqual(effect["owner_result"]["transaction_id"], transaction["transaction_id"])
                self.assertEqual(owner_command, transaction["command_id"])
                self.assertEqual("complete", transaction["state"])
                self.assertEqual(str(published), plan["target"])
                self.assertEqual(plan["target"], transaction["target"])
                context = json.loads(transaction["operation_context"])
                self.assertEqual(plan["inputs_sha256"], context["inputs_sha256"])
                self.assertEqual(plan["parent_before_identity"], context["parent_before_identity"])
                self.assertEqual(request["durable_operation_id"], context["operation_id"])
                self.assertEqual(request["attempt_id"], context["attempt_id"])
                self.assertEqual(request["durable_operation_id"], semantic["operation"]["durable_operation_id"])
                self.assertEqual(request["attempt_id"], semantic["operation"]["attempt_id"])
                text_key = "config_text" if published == target else "sidecar_text"
                if published == target:
                    self.assertEqual(plan[text_key].encode(), published.read_bytes())
                self.assertEqual(context[text_key].encode(), published.read_bytes())
                manifest, = transaction["expected_files"]
                self.assertEqual(published.name, manifest["path"])
                self.assertEqual(hashlib.sha256(published.read_bytes()).hexdigest(), manifest["sha256"])
                self.assertEqual(len(published.read_bytes()), manifest["size"])
                self.assertEqual(1, published.stat().st_nlink)
                self.assertEqual(f"{published.stat().st_dev}:{published.stat().st_ino}",
                                 transaction["effect_file_identity"])
                replacement = semantic["replacement_snapshot"]
                self.assertEqual("load_save", replacement["selected_context"]["launch_intent"])
                self.assertNotEqual(reviewed["revision"], replacement["revision"])
                self.assertFalse(replacement["readiness"]["execution_available"])
                self.assertEqual(inputs, preserved())
                self.assertEqual(install_inputs, snapshot(workspace / "fixture-install"))
                if published == target:
                    self.assertFalse(sidecar.exists())
                    configuration_identity = (target.stat().st_dev, target.stat().st_ino, target.stat().st_nlink, target.read_bytes())
                else:
                    self.assertEqual("selected.zip", plan["selected_save"])
                    self.assertEqual("gui", plan["profile_id"])
                    self.assertEqual("satisfied", replacement["readiness"]["selected_save"]["state"])
                    self.assertEqual(configuration_identity,
                                     (target.stat().st_dev, target.stat().st_ino, target.stat().st_nlink, target.read_bytes()))
                old_receipts = set(receipt_root.glob("*.v2.json"))
                if evidence is not None:
                    evidence.append({"component": component, "receipt": receipt,
                                     "owner_journal": transaction, "reviewed_plan": plan,
                                     "published_sha256": hashlib.sha256(published.read_bytes()).hexdigest(),
                                     "published_file_identity": transaction["effect_file_identity"],
                                     "preserved_instance_sha256": {
                                         name: hashlib.sha256(value).hexdigest() for name, value in inputs.items()},
                                     "install_preservation_verified": True})
            document = json.loads(sidecar.read_bytes())
            self.assertEqual(hashlib.sha256((instance / "saves/selected.zip").read_bytes()).hexdigest(), document["save_sha256"])
            self.assertEqual("gui", document["profile_id"])
            registry = json.loads((instance / "instance.v1.json").read_bytes())
            self.assertEqual(registry["factorio_version"], document["factorio_version"])
            self.assertEqual(hashlib.sha256((instance / "mods/modset-lock.v1.json").read_bytes()).hexdigest(), document["modset_lock_sha256"])

    @unittest.skipUnless(os.name == "nt", "unsupported: preparation owners are Windows qualified")
    def test_ordinary_selected_save_preparation_and_changed_observation_confirmation(self) -> None:
        from test_configuration_reconciliation import ExistingConfigurationTests
        from test_make_ready_preparation import MakeReadyPreparationTests
        from test_local_modset_solver import snapshot

        def make_ready_input(projected: dict) -> str:
            actions = projected["available_semantic_actions"]
            self.assertIn("presentation.refresh", [action["action_id"] for action in actions])
            index = next(i for i, action in enumerate(actions)
                         if action["action_id"] == "readiness.prepare")
            descriptor = actions[index]
            self.assertEqual("available", descriptor["availability"])
            self.assertEqual("explicit", descriptor["confirmation"])
            self.assertEqual(["selected_instance_id"],
                             [field["field_id"] for field in descriptor["input_fields"]])
            self.assertEqual("main", descriptor["input_fields"][0]["default"])
            return ordinary_action_tabs(projected, "readiness.prepare")

        for intent in ("menu", "load_save"):
            with self.subTest(intent=intent), tempfile.TemporaryDirectory(prefix="tui-make-ready-") as temporary:
                workspace = Path(temporary)
                instance, original, expected = ExistingConfigurationTests.prepare(
                    self, workspace, "load_save", raw=True, crlf=True)
                target = instance / "config/config.ini"
                identity = (target.stat().st_dev, target.stat().st_ino)
                preserved = MakeReadyPreparationTests.preserved_inputs(self, instance)
                sidecar = instance / "metadata/save-refs/selected.zip.save-ref.v1.json"
                selected = ExistingConfigurationTests.query(self, workspace, "instances", "load_save")
                tabs = make_ready_input(selected)
                before = snapshot(workspace)
                # Open the actual Make Ready form and confirmation, then switch away/back.
                cancelled = self.invoke(
                    ["--workspace", str(workspace), "--ordinary", "--plain"],
                    stdin="s\n2\n" + tabs + "space\nm\ns\nspace\nq\n")
                self.assertEqual(0, cancelled.returncode, cancelled.stderr)
                self.assertIn("Confirm Make Ready", cancelled.stdout)
                self.assertEqual(original, target.read_bytes())
                self.assertFalse(sidecar.exists())
                self.assertEqual(before, snapshot(workspace))
                receipt_root = workspace / ".facman/action-receipts-v2"
                old_receipts = set(receipt_root.glob("*.v2.json"))
                choice = "s\n" if intent == "load_save" else ""
                components = ["routing_configuration"]
                if intent == "load_save":
                    components.append("selected_save_declared_context")
                for component in components:
                    reviewed = ExistingConfigurationTests.query(self, workspace, "instances", intent)
                    tabs = make_ready_input(reviewed)
                    result = self.invoke(
                        ["--workspace", str(workspace), "--ordinary", "--plain"],
                        stdin=choice + "2\n" + tabs + "space\nspace\nq\n")
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn("Confirm Make Ready", result.stdout)
                    new_receipts = set(receipt_root.glob("*.v2.json")) - old_receipts
                    self.assertEqual(1, len(new_receipts), result.stdout)
                    receipt = json.loads(new_receipts.pop().read_bytes())
                    request = json.loads(receipt["request_json"])
                    semantic = json.loads(receipt["result_json"])
                    self.assertEqual("readiness.prepare", request["action_id"])
                    self.assertTrue(request["request_id"].startswith("tui-readiness-prepare-"))
                    self.assertEqual("instances", request["scope"])
                    self.assertEqual("main", request["selected_instance_id"])
                    self.assertEqual("explicit", request["confirmation"])
                    self.assertEqual(intent, request.get("launch_intent", "menu"))
                    self.assertEqual(reviewed["revision"], request["expected_snapshot_revision"])
                    self.assertEqual(hashlib.sha256(receipt["request_json"].encode()).hexdigest(),
                                     receipt["request_fingerprint"])
                    self.assertEqual(hashlib.sha256(receipt["result_json"].encode()).hexdigest(),
                                     receipt["result_digest"])
                    self.assertEqual(request["request_id"], semantic["request_id"])
                    self.assertEqual("completed", semantic["outcome"])
                    payload = semantic["action_payload"]
                    self.assertEqual(intent, payload["launch_intent"])
                    self.assertEqual("partial", payload["composition"])
                    self.assertFalse(payload["execution_started"])
                    self.assertFalse(payload["permit_issued"])
                    effect, = payload["completed_components"]
                    self.assertEqual(component, effect["component"])
                    dependency = ("configuration_preparation" if component == "routing_configuration"
                                  else "selected_save_preparation")
                    self.assertEqual(reviewed["dependency_identities"][dependency]["plan"]["plan_sha256"],
                                     effect["plan_sha256"])
                    owner_command = ("readiness.prepare_configuration" if component == "routing_configuration"
                                     else "readiness.prepare_selected_save")
                    self.assertEqual(owner_command, effect["owner_command"])
                    owner_path = workspace / "transactions" / (effect["transaction_id"] + ".transaction.v1.json")
                    owner = json.loads(owner_path.read_bytes())
                    self.assertEqual(effect["owner_result"]["transaction_id"], owner["transaction_id"])
                    self.assertEqual(owner_command, owner["command_id"])
                    self.assertEqual("complete", owner["state"])
                    context = json.loads(owner["operation_context"])
                    self.assertEqual(request["durable_operation_id"], context["operation_id"])
                    self.assertEqual(request["attempt_id"], context["attempt_id"])
                    self.assertEqual(request["durable_operation_id"], semantic["operation"]["durable_operation_id"])
                    self.assertEqual(request["attempt_id"], semantic["operation"]["attempt_id"])
                    replacement = semantic["replacement_snapshot"]
                    self.assertEqual(intent, replacement["selected_context"]["launch_intent"])
                    self.assertNotEqual(reviewed["revision"], replacement["revision"])
                    self.assertFalse(replacement["readiness"]["execution_available"])
                    old_receipts = set(receipt_root.glob("*.v2.json"))
                self.assertEqual(expected, target.read_bytes())
                if intent == "menu":
                    self.assertFalse(sidecar.exists())
                    self.assertIn("selected_context_load_save_required", result.stdout)
                else:
                    document = json.loads(sidecar.read_bytes())
                    self.assertEqual(hashlib.sha256((instance / "saves/selected.zip").read_bytes()).hexdigest(),
                                     document["save_sha256"])
                    self.assertEqual("gui", document["profile_id"])
                    registry = json.loads((instance / "instance.v1.json").read_bytes())
                    self.assertEqual(registry["factorio_version"], document["factorio_version"])
                    self.assertEqual(hashlib.sha256((instance / "mods/modset-lock.v1.json").read_bytes()).hexdigest(),
                                     document["modset_lock_sha256"])
                self.assertEqual(identity, (target.stat().st_dev, target.stat().st_ino))
                self.assertEqual(preserved, MakeReadyPreparationTests.preserved_inputs(self, instance))

    def test_catalog_and_empty_unicode_workspace(self) -> None:
        version = self.invoke(["--version"])
        self.assertEqual(version.returncode, 0, version.stderr)
        with (ROOT / "release/index/version.v2.toml").open("rb") as handle:
            expected_version = tomllib.load(handle)["semver"]
        self.assertEqual(version.stdout.strip(), f"FacMan {expected_version} TUI")
        catalog = self.invoke(["--list", "--json"])
        self.assertEqual(catalog.returncode, 0, catalog.stderr)
        report = json.loads(catalog.stdout)
        self.assertGreaterEqual(len(report["commands"]), 56)
        run = next(item for item in report["commands"] if item["runtime_id"] == "run.execute")
        self.assertEqual(run["availability_reason"], "isolation_not_proven")

        with tempfile.TemporaryDirectory(prefix="facman-tui-Ω-") as temporary:
            workspace = Path(temporary) / "uncreated workspace"
            status = self.invoke(
                ["--workspace", str(workspace), "--command", "workspace.status", "--json"]
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["observations"]["workspace"], str(workspace))
            self.assertFalse(workspace.exists())

            doctor = self.invoke(["--workspace", str(workspace), "--command", "doctor", "--json"])
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            self.assertEqual(json.loads(doctor.stdout)["schema"], "factorio.diagnostic_report.v1")

    def test_redirected_default_unavailable_and_cancellation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-tui-redirected-") as temporary:
            workspace = Path(temporary) / "workspace"
            redirected = self.invoke(["--workspace", str(workspace), "--json"], stdin="")
            self.assertEqual(redirected.returncode, 0, redirected.stderr)
            self.assertEqual(json.loads(redirected.stdout)["command"], "workspace.status")

            dry_run_refusal = self.invoke(
                [
                    "--workspace", str(workspace), "--command", "run.execute",
                    "--payload", '{"instance_id":"space-age-main"}', "--json",
                ]
            )
            self.assertEqual(dry_run_refusal.returncode, 1)
            self.assertEqual(
                json.loads(dry_run_refusal.stdout)["refusal"]["code"],
                "dry_run_write_not_executed",
            )

            unavailable = self.invoke(
                [
                    "--workspace", str(workspace), "--command", "run.execute",
                    "--payload", '{"instance_id":"space-age-main"}', "--apply", "--json",
                ]
            )
            self.assertEqual(unavailable.returncode, 2)
            self.assertEqual(unavailable.stdout, "")
            self.assertIn("remains human-gated", unavailable.stderr)

            cancelled = self.invoke(
                ["--workspace", str(workspace), "--command", "workspace.status", "--cancel", "--json"]
            )
            self.assertEqual(cancelled.returncode, 1)
            cancelled_payload = json.loads(cancelled.stdout)
            self.assertEqual(cancelled_payload["outcome"], "cancelled")
            self.assertEqual(
                cancelled_payload["operation"]["outcome"],
                "cancelled_before_dispatch",
            )
            self.assertFalse(
                cancelled_payload["operation"]["effects_may_have_occurred"],
            )
            self.assertFalse(workspace.exists())

    def test_generated_guided_forms_plain_mode_and_transport_refusal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-tui-guided-") as temporary:
            workspace = Path(temporary) / "guided workspace"
            guided = self.invoke(
                ["--workspace", str(workspace), "--interactive", "--plain", "--page-size", "5"],
                stdin="/workspace.status\n1\n\nq\n",
            )
            self.assertEqual(guided.returncode, 0, guided.stderr)
            self.assertIn("FacMan guided terminal", guided.stdout)
            self.assertIn("Commands matching search", guided.stdout)
            self.assertIn("Review", guided.stdout)
            self.assertIn("Risk: read_only", guided.stdout)
            self.assertIn("[progress]", guided.stdout)
            self.assertNotIn("JSON payload", guided.stdout)
            self.assertNotIn("\x1b[", guided.stdout)
            self.assertFalse(workspace.exists())

            cancelled_write = self.invoke(
                ["--workspace", str(workspace), "--interactive", "--plain"],
                stdin="/instances.rename\n1\nmain\nRenamed\nno\nq\n",
            )
            self.assertEqual(cancelled_write.returncode, 0, cancelled_write.stderr)
            self.assertIn("Type APPLY to confirm this local write", cancelled_write.stdout)
            self.assertIn("Command cancelled before dispatch", cancelled_write.stdout)
            self.assertFalse(workspace.exists())

            daemon = self.invoke(
                ["--workspace", str(workspace), "--command", "workspace.status", "--transport", "daemon", "--json"]
            )
            self.assertEqual(daemon.returncode, 1)
            refusal = json.loads(daemon.stdout)
            self.assertEqual(refusal["code"], "daemon_transport_unavailable")
            self.assertEqual(
                refusal["operation"]["outcome"],
                "refused_before_effects",
            )
            self.assertFalse(refusal["operation"]["effects_may_have_occurred"])

            cli = cli_executable()
            if cli is not None:
                process = self.invoke(
                    [
                        "--workspace", str(workspace), "--command", "workspace.status",
                        "--transport", "process", "--cli-path", str(cli), "--json",
                    ]
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(json.loads(process.stdout)["observations"]["workspace"], str(workspace))

            invalid = self.invoke(["--color", "sometimes", "--command", "workspace.status"])
            self.assertEqual(invalid.returncode, 2)


if __name__ == "__main__":
    unittest.main()
