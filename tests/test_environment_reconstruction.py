# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Join portable content, declared profile and world owners in a clean workspace.

Structural fixtures qualify reconstruction and preparation, never real Play.
The world input is the existing snapshot/WorldBundle contract. Profile settings
are explicitly declared through public inspection, not hidden inside modpack v1.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import invoke_machine
from test_local_modset_solver import FIXTURE_INSTALL, call, setup, snapshot, write_mod
from test_save_index_retention import write_save
from test_presentation_profile_preparation import factorio_validator


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EnvironmentReconstructionTests(unittest.TestCase):
    def declare(self, source: Path) -> tuple[Path, Path, dict]:
        instance = setup(source)
        write_mod(instance / "mods/simple_1.0.0.zip", "simple", "1.0.0")
        write_mod(instance / "mods/unselected_1.0.0.zip", "unselected", "1.0.0")
        call(source, "modsets", "plan", "solver", "--enable", "simple")
        call(source, "modsets", "apply", "solver", "--enable", "simple")
        (instance / "mods/mod-settings.dat").write_bytes(b"\x01declared settings\x00\xff")
        write_save(instance / "saves/world.zip", b"declared opaque world")
        write_save(instance / "saves/unselected.zip", b"unselected opaque world")
        call(source, "profiles", "create", "declared", "--audio", "disabled",
             "--graphics-quality", "medium", "--selection-mode", "load-save",
             "--selection", "world.zip", "--arg", "--low-vram")
        profile = call(source, "profiles", "inspect", "declared")
        factorio_validator("factorio_launch_profile_report.v1.schema.json").validate(profile)
        self.assertTrue(profile["portable"])
        plan = call(source, "profiles", "plan", "solver", "declared")
        call(source, "profiles", "apply", "solver", "declared", "--expected-plan", plan["plan_sha256"])
        call(source, "saves", "associate", "world.zip", "--instance", "solver", "--profile", "declared")
        pack = source / "content.zip"
        call(source, "modsets", "export", "solver", str(pack))
        call(source, "snapshots", "create", "solver", "world", "--save", "world.zip")
        world = call(source, "snapshots", "inspect", "solver", "world")
        self.assertEqual("available", world["world_bundle_state"])
        bundle = world["world_bundle"]
        factorio_validator("factorio_world_bundle.v1.schema.json").validate(bundle)
        self.assertEqual(["world.zip"], bundle["selected_saves"])
        self.assertEqual(sha256(instance / "saves/world.zip"), bundle["world_files"][0]["sha256"])
        call(source, "snapshots", "verify", "solver", "world")
        return pack, source / "snapshots/solver/world.zip", profile

    def reconstruct(self, destination: Path, pack: Path, world: Path, profile: dict) -> Path:
        self.assertFalse(destination.exists())
        call(destination, "installs", "import", str(FIXTURE_INSTALL), "--id", "local")
        self.assertEqual([], call(destination, "instances", "list")["instances"])
        call(destination, "modsets", "import", str(pack), "--instance", "main", "--install", "local")
        # Recreate exactly the inspected safe settings through their current owner.
        args = ["profiles", "create", profile["profile_id"], "--template", profile["template_id"]]
        for key, value in profile["settings"].items():
            if key == "additional_arguments":
                for argument in value:
                    args.extend(["--arg", argument])
            else:
                args.extend(["--" + key.replace("_", "-"), str(value)])
        call(destination, *args)
        observed = call(destination, "profiles", "inspect", "declared")
        self.assertEqual(profile["settings"], observed["settings"])
        plan = call(destination, "profiles", "plan", "main", "declared")
        call(destination, "profiles", "apply", "main", "declared", "--expected-plan", plan["plan_sha256"],
             "--expected-revision", plan["source_manifest_sha256"])
        preserved = snapshot(destination)
        missing = call(destination, "snapshots", "restore", str(world), "carrier", success=False)
        self.assertEqual("snapshot_install_incompatible", missing["refusal"]["code"])
        self.assertEqual(preserved, snapshot(destination))
        # The archive keeps its original provenance while reconstruction binds
        # the explicitly selected compatible installation already registered here.
        call(destination, "snapshots", "restore", str(world), "carrier", "--install", "local")
        backup = call(destination, "saves", "backup", "world", "--instance", "carrier")
        cloned = call(destination, "saves", "clone", "world.backup.zip", "--instance", "carrier",
                      "--to-instance", "main", "--source-kind", "owned_backup", "--as", "world.zip")
        self.assertEqual("owned_backup", cloned["source_kind"])
        self.assertEqual("carrier", cloned["source_instance_id"])
        self.assertEqual("main", cloned["target_instance_id"])
        self.assertEqual("world.zip", cloned["destination_save"])
        self.assertEqual(sha256(Path(backup["destination_path"])), cloned["sha256"])
        carrier_manifest = json.loads((destination / "instances/carrier/instance.v1.json").read_bytes())
        self.assertEqual("world", carrier_manifest["restored_from_snapshot"])
        self.assertEqual("local", carrier_manifest["install_ref"])
        self.assertEqual("fixture", carrier_manifest["restored_from_install_ref"])
        self.assertEqual(["local"], [item["install_id"] for item in call(destination, "installs", "list")["install_refs"]])
        self.assertEqual(sha256(destination / "instances/carrier/saves/world.zip"), cloned["sha256"])
        return destination / "instances/main"

    def query(self, workspace: Path) -> dict:
        return call(workspace, "presentation", "query", "instances", "--instance", "main", "--intent", "load_save")

    def arguments(self, workspace: Path, observation: dict, identity: str) -> list[str]:
        return ["--workspace", str(workspace), "presentation", "action", "readiness.prepare_joined",
                "--scope", "instances", "--instance", "main", "--intent", "load_save",
                "--installation", "local", "--profile", "declared", "--save", "world.zip",
                "--expected-revision", observation["revision"], "--request-id", identity,
                "--idempotency-key", identity, "--operation-id", identity, "--attempt-id", identity,
                "--confirmation", "explicit", "--json"]

    def result(self, args: list[str], code: int = 0, env: dict | None = None) -> dict:
        actual, output, error = invoke_machine(args, env=env)
        self.assertEqual((code, ""), (actual, error), output)
        response = json.loads(output)["payload"]
        factorio_validator("factorio_make_ready_joined_result.v1.schema.json").validate(response["action_payload"])
        return response

    def assert_environment(self, source: Path, destination: Path, result: dict) -> None:
        original, target = source / "instances/solver", destination / "instances/main"
        for name in ("mods/simple_1.0.0.zip", "mods/mod-list.json", "mods/mod-settings.dat", "saves/world.zip"):
            self.assertEqual((original / name).read_bytes(), (target / name).read_bytes(), name)
        self.assertFalse((target / "mods/unselected_1.0.0.zip").exists())
        self.assertFalse((target / "saves/unselected.zip").exists())
        receipt = json.loads((target / "modpack-import.v1.json").read_bytes())
        factorio_validator("factorio_modpack_import.v1.schema.json").validate(receipt)
        self.assertEqual("solver", receipt["source_instance_id"])
        self.assertEqual("local", receipt["install_ref"])
        self.assertTrue(receipt["offline"])
        self.assertEqual(sha256(source / "content.zip"), receipt["archive_sha256"])
        self.assertEqual((source / "content.zip").stat().st_size, receipt["archive_size"])
        with zipfile.ZipFile(source / "content.zip") as archive:
            for name, field in (("modpack-manifest.v1.json", "source_manifest_sha256"),
                                ("modset-lock.v1.json", "source_lock_sha256")):
                self.assertEqual(archive.read(name), (target / name).read_bytes())
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), receipt[field])
        self.assertEqual((original / "mods/modset-lock.v1.json").read_bytes(), (target / "modset-lock.v1.json").read_bytes())
        self.assertEqual(sha256(target / "mods/modset-lock.v1.json"), receipt["target_lock_sha256"])
        lock = json.loads((target / "mods/modset-lock.v1.json").read_bytes())
        self.assertEqual("main", lock["instance_id"])
        self.assertEqual("install-data:local", next(mod["source"] for mod in lock["mods"] if mod["name"] == "base"))
        manifest = json.loads((target / "instance.v1.json").read_bytes())
        self.assertEqual("declared", manifest["profile"])
        call(destination, "instances", "verify", "main")
        self.assertEqual([], call(destination, "modsets", "verify", "main")["problems"])
        save = call(destination, "saves", "verify", "world.zip", "--instance", "main")["saves"][0]
        self.assertEqual("current", save["association"]["status"])
        self.assertEqual("match", save["association"]["context"]["status"])
        sidecar = json.loads((target / "metadata/save-refs/world.zip.save-ref.v1.json").read_bytes())
        self.assertEqual(sha256(target / "saves/world.zip"), sidecar["save_sha256"])
        self.assertEqual(sha256(target / "mods/modset-lock.v1.json"), sidecar["modset_lock_sha256"])
        self.assertEqual("declared", sidecar["profile_id"])
        ready = self.query(destination)["readiness"]
        self.assertEqual("satisfied", ready["selected_save"]["state"])
        self.assertEqual("locked_verified", ready["preparation_preview"]["modset"]["status"])
        self.assertFalse(ready["execution_available"])
        self.assertIn("real_play_gate_not_passed", [blocker["code"] for blocker in ready["blockers"]])
        for name in ("preparation_complete", "readiness_complete", "execution_started", "permit_issued"):
            self.assertFalse(result["action_payload"][name])

    def test_clean_workspace_reconstructs_declared_content_profile_world_and_joined_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="environment-") as value:
            root = Path(value); source, destination = root / "source", root / "clean"
            pack, world, profile = self.declare(source)
            preserved, install = snapshot(source), snapshot(FIXTURE_INSTALL)
            target = self.reconstruct(destination, pack, world, profile)
            selected = snapshot(target / "mods"), (target / "saves/world.zip").read_bytes()
            observed = self.query(destination)
            args = self.arguments(destination, observed, "reconstructed")
            result = self.result(args)
            self.assertEqual("completed", result["outcome"])
            self.assertEqual(["readiness.prepare_selected_save"],
                             [item["owner_command"] for item in result["action_payload"]["completed_components"]])
            self.assert_environment(source, destination, result)
            self.assertEqual(selected, (snapshot(target / "mods"), (target / "saves/world.zip").read_bytes()))
            frozen = snapshot(destination)
            self.assertEqual(result, self.result(args))
            self.assertEqual(frozen, snapshot(destination))
            self.assertEqual(preserved, snapshot(source))
            self.assertEqual(install, snapshot(FIXTURE_INSTALL))

    def test_reconstructed_world_context_interruption_recovers_without_reimporting_or_recloning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="environment-recovery-") as value:
            root = Path(value); source, destination = root / "source", root / "clean"
            pack, world, profile = self.declare(source)
            target = self.reconstruct(destination, pack, world, profile)
            inputs = snapshot(source), snapshot(target / "mods"), (target / "saves/world.zip").read_bytes(), snapshot(FIXTURE_INSTALL)
            args = self.arguments(destination, self.query(destination), "interrupted")
            actual, output, error = invoke_machine(args, env=dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_EXIT="after_publication"))
            self.assertEqual((74, ""), (actual, error), output)
            pending = call(destination, "workspace", "recovery", "inspect")
            tx = next(item["transaction_id"] for item in pending["transactions"]
                      if item["command_id"] == "readiness.prepare_selected_save")
            call(destination, "workspace", "recovery", "plan", tx)
            recovered = call(destination, "workspace", "recovery", "apply", tx)
            self.assertEqual("complete", recovered["transactions"][0]["state"])
            # The interrupted semantic receipt remains unknown even after owner
            # recovery. A fresh ordinary request observes its already owned effect.
            unknown = self.result(args, 4)
            self.assertEqual("outcome_unknown", unknown["outcome"])
            result = self.result(self.arguments(destination, self.query(destination), "after-recovery"))
            self.assert_environment(source, destination, result)
            self.assertEqual(inputs, (snapshot(source), snapshot(target / "mods"), (target / "saves/world.zip").read_bytes(), snapshot(FIXTURE_INSTALL)))
            frozen = snapshot(destination)
            call(destination, "workspace", "recovery", "apply", tx)
            self.assertEqual(frozen, snapshot(destination))

    def test_reconstruction_owners_preserve_foreign_destinations_and_refuse_invalid_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="environment-refusals-") as value:
            root = Path(value); source, destination = root / "source", root / "clean"
            pack, world, profile = self.declare(source)
            source_before, install = snapshot(source), snapshot(FIXTURE_INSTALL)
            target = self.reconstruct(destination, pack, world, profile)
            foreign_instance = destination / "instances/foreign"
            foreign_instance.mkdir()
            (foreign_instance / "user.dat").write_bytes(b"foreign instance content")
            foreign_save = target / "saves/foreign.zip"
            write_save(foreign_save, b"foreign world bytes")
            corrupt_world = root / "corrupt-world.zip"
            with zipfile.ZipFile(world) as original, zipfile.ZipFile(corrupt_world, "w") as corrupted:
                for item in original.infolist():
                    corrupted.writestr(item, b"corrupt save" if item.filename == "saves/world.zip" else original.read(item))
            cases = [
                (("modsets", "import", str(pack), "--instance", "foreign", "--install", "local"), "persistent_target_exists"),
                (("snapshots", "restore", str(world), "foreign", "--install", "local"), "snapshot_restore_target_exists"),
                (("snapshots", "restore", str(corrupt_world), "invalid", "--install", "local"), "snapshot_hash_closure_mismatch"),
                (("saves", "clone", "world.backup.zip", "--instance", "carrier", "--to-instance", "main",
                  "--source-kind", "owned_backup", "--as", "foreign.zip"), "save_clone_target_exists"),
                (("saves", "clone", "missing.backup.zip", "--instance", "carrier", "--to-instance", "main",
                  "--source-kind", "owned_backup", "--as", "missing.zip"), "save_backup_not_found"),
                (("profiles", "plan", "main", "missing"), "unknown_profile"),
            ]
            for arguments, expected in cases:
                with self.subTest(owner=arguments[:2]):
                    preserved = snapshot(destination), corrupt_world.read_bytes()
                    refused = call(destination, *arguments, success=False)
                    self.assertEqual(expected, refused["refusal"]["code"])
                    self.assertEqual(preserved, (snapshot(destination), corrupt_world.read_bytes()))
            # Correct input/destination selection continues through the ordinary
            # joined route while preserving all foreign bytes from these refusals.
            foreign_before = snapshot(foreign_instance), foreign_save.read_bytes()
            result = self.result(self.arguments(destination, self.query(destination), "after-refusals"))
            self.assert_environment(source, destination, result)
            self.assertEqual(foreign_before, (snapshot(foreign_instance), foreign_save.read_bytes()))
            self.assertEqual(source_before, snapshot(source))
            self.assertEqual(install, snapshot(FIXTURE_INSTALL))


if __name__ == "__main__":
    unittest.main()
