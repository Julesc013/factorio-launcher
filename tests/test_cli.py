from __future__ import annotations

import json
import hashlib
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import facman_executable, invoke
from tools import json_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
SAVE_FIXTURES = ROOT / "tests" / "fixtures" / "factorio_saves"


def relative_files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


class CliTests(unittest.TestCase):
    def test_version(self) -> None:
        code, stdout, stderr = invoke(["--version"])
        self.assertEqual(code, 0, stderr)
        self.assertIn("FacMan 0.1.0", stdout)

    def test_product_inspect_json(self) -> None:
        code, stdout, stderr = invoke(["product", "inspect", "--json"])
        self.assertEqual(code, 0, stderr)
        data = json.loads(stdout)
        self.assertEqual(data["product_id"], "factorio")
        self.assertEqual(data["binding_id"], "flb.factorio")
        self.assertFalse(data["boundaries"]["bundles_factorio_binaries"])

    def test_command_graph_and_diagnostics_route_through_flb_ulk(self) -> None:
        code, stdout, stderr = invoke(["command-graph", "inspect", "--json"])
        self.assertEqual(code, 0, stderr)
        graph = json.loads(stdout)
        self.assertEqual(graph["schema"], "ulk.command_graph.v1")
        commands = {command["command"] for command in graph["commands"]}
        self.assertIn("launch_plan.build", commands)
        self.assertIn("install_refs.scan", commands)
        self.assertIn("install_refs.import", commands)
        self.assertIn("run.preview", commands)
        self.assertIn("launch_plan.preflight", commands)
        self.assertNotIn("diagnostics.report", commands)
        self.assertNotIn("instances.list", commands)
        run_descriptor = next(command for command in graph["commands"] if command["command"] == "run.preview")
        self.assertEqual(run_descriptor["owner"], "factorio-launcher")
        self.assertEqual(run_descriptor["binding"], "flb.factorio")
        self.assertEqual(run_descriptor["handler_status"], "registered")
        self.assertEqual(run_descriptor["effects"], ["workspace_read"])
        self.assertTrue(run_descriptor["response_schema"].endswith("factorio_launch_plan.v1.schema.json"))

        code, stdout, stderr = invoke(["diagnostics", "report", "--json"])
        self.assertEqual(code, 0, stderr)
        diagnostics = json.loads(stdout)
        self.assertEqual(diagnostics["schema"], "ulk.diagnostic_report.v1")
        self.assertEqual(diagnostics["report_id"], "ulk.diagnostic.minimal")
        self.assertIn("command_graph", {check["id"] for check in diagnostics["checks"]})

    def test_doctor_warns_without_installs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr = invoke(["--workspace", tmp, "doctor"])
            self.assertEqual(code, 0, stderr)
            self.assertIn("Status: warning", stdout)
            self.assertIn("no install references registered yet", stdout)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_import_instance_and_launch_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            install_files_before = relative_files(FIXTURE_INSTALL)
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("Registered fixture", stdout)
            self.assertTrue((workspace / "workspace.v1.json").is_file())
            self.assertTrue((workspace / "installs" / "refs" / "fixture.json").is_file())
            self.assertTrue((workspace / "installs" / "setup_state_refs").is_dir())
            self.assertFalse((workspace / "installs" / "installed_state").exists())

            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "instances",
                    "create",
                    "Space Age Main",
                    "--install",
                    "fixture",
                    "--template",
                    "modded",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            instance = json.loads(stdout)
            self.assertEqual(instance["instance_id"], "space-age-main")
            instance_root = workspace / "instances" / "space-age-main"
            self.assertTrue((instance_root / "instance.v1.json").is_file())
            for child in ("config", "mods", "saves", "scenarios", "script-output", "logs", "crash", "locks", "cache"):
                self.assertTrue((instance_root / child).is_dir(), child)
            self.assertEqual(relative_files(FIXTURE_INSTALL), install_files_before)

            code, stdout, stderr = invoke(["--workspace", tmp, "launch-plan", "space-age-main", "--json"])
            self.assertEqual(code, 0, stderr)
            plan = json.loads(stdout)
            self.assertEqual(plan["instance_id"], "space-age-main")
            self.assertIn("--config", plan["args"])
            self.assertIn("--mod-directory", plan["args"])
            self.assertTrue(plan["dry_run_default"])
            self.assertEqual(plan["command"], "launch_plan.build")
            self.assertEqual(plan["execution"], "not_started")
            self.assertIn(str(instance_root / "config" / "config.ini"), plan["command_line"])
            launch_schema = json.loads(
                (ROOT / "contracts/schema/factorio/factorio_launch_plan.v1.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(json_contract.validate(plan, launch_schema), [])

            code, stdout, stderr = invoke(["--workspace", tmp, "launch", "plan", "space-age-main", "--json"])
            self.assertEqual(code, 0, stderr)
            alias_plan = json.loads(stdout)
            self.assertEqual(alias_plan["instance_id"], "space-age-main")

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "launch-plan", "space-age-main", "--preflight", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            preflight = json.loads(stdout)
            self.assertEqual(preflight["schema"], "factorio.launch_preflight.v1")
            self.assertEqual(preflight["command"], "launch_plan.preflight")
            self.assertEqual(preflight["status"], "pass")
            self.assertEqual(preflight["problems"], [])
            self.assertFalse(preflight["started"])
            preflight_schema = json.loads(
                (ROOT / "contracts/schema/factorio/factorio_launch_preflight.v1.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(json_contract.validate(preflight, preflight_schema), [])

            code, stdout, stderr = invoke(["--workspace", tmp, "run", "space-age-main", "--json"])
            self.assertEqual(code, 0, stderr)
            run_preview = json.loads(stdout)
            self.assertEqual(run_preview["command"], "run.preview")
            self.assertEqual(run_preview["args"], plan["args"])
            self.assertEqual(run_preview["command_line"], plan["command_line"])
            self.assertEqual(run_preview["execution"], "not_started")
            self.assertEqual(json_contract.validate(run_preview, launch_schema), [])

            code, stdout, stderr = invoke(["--workspace", tmp, "run", "space-age-main"])
            self.assertEqual(code, 0, stderr)
            self.assertIn("Dry-run only", stdout)
            self.assertIn(run_preview["command_line"], stdout)

    def test_run_execute_is_quarantined_until_real_factorio_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            install_root = Path(tmp) / "fake_exec_install"
            exe_dir = install_root / "bin" / "x64"
            info_dir = install_root / "data" / "base"
            exe_dir.mkdir(parents=True)
            info_dir.mkdir(parents=True)
            executable = exe_dir / ("factorio.exe" if facman_executable().suffix == ".exe" else "factorio")
            shutil.copy2(facman_executable(), executable)
            info_dir.joinpath("info.json").write_text('{"name":"base","version":"2.0.77"}\n', encoding="utf-8")

            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(install_root), "--id", "exec-fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Exec Fixture", "--install", "exec-fixture"]
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, _stderr = invoke(["--workspace", tmp, "run", "exec-fixture", "--execute", "--json"])
            refusal = json.loads(stdout)

            self.assertEqual(code, 1)
            self.assertEqual(refusal["status"], "refused")
            self.assertEqual(refusal["refusal"]["code"], "isolation_not_proven")
            history = Path(tmp) / "instances" / "exec-fixture" / "logs" / "launch_history.log"
            self.assertFalse(history.exists())
            audit = Path(tmp) / "audit" / "launch_events.log"
            self.assertFalse(audit.exists())

    def test_local_mod_import_lock_verify_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mod_zip = Path(tmp) / "metadata-example_9.8.7.zip"
            mod_info = {
                "name": "metadata-example",
                "version": "9.8.7",
                "title": "Metadata Example",
                "factorio_version": "2.0",
                "dependencies": ["base >= 2.0", "? space-age >= 2.0", "! conflict-mod"],
            }
            with zipfile.ZipFile(mod_zip, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("metadata-example_9.8.7/info.json", json.dumps(mod_info))

            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Modded", "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "mods", "import", str(mod_zip), "--instance", "modded", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            imported = json.loads(stdout)
            self.assertEqual(imported["name"], "metadata-example")
            self.assertEqual(imported["title"], "Metadata Example")
            self.assertEqual(imported["version"], "9.8.7")
            self.assertEqual(imported["factorio_version"], "2.0")
            self.assertEqual(imported["metadata_source"], "info_json")
            self.assertEqual(imported["dependencies"][0]["name"], "base")
            self.assertEqual(imported["dependencies"][0]["operator"], ">=")
            self.assertEqual(imported["optional_dependencies"][0]["name"], "space-age")
            self.assertEqual(imported["incompatibilities"][0]["name"], "conflict-mod")
            self.assertEqual(len(imported["sha1"]), 40)
            self.assertEqual(len(imported["sha256"]), 64)

            code, stdout, stderr = invoke(["--workspace", tmp, "modsets", "lock", "modded", "--json"])
            self.assertEqual(code, 0, stderr)
            lock = json.loads(stdout)
            self.assertEqual(lock["factorio_version"], "2.0.77")
            self.assertEqual(lock["mods"][0]["file_name"], "metadata-example_9.8.7.zip")
            self.assertEqual(lock["mods"][0]["name"], "metadata-example")
            self.assertEqual(lock["mods"][0]["optional_dependencies"][0]["name"], "space-age")
            self.assertEqual(len(lock["mods"][0]["sha256"]), 64)
            self.assertTrue((Path(tmp) / "modsets" / "modded.modset-lock.v1.json").is_file())

            code, stdout, stderr = invoke(["--workspace", tmp, "modsets", "verify", "modded", "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["status"], "ok")

            copied_mod = Path(tmp) / "instances" / "modded" / "mods" / "metadata-example_9.8.7.zip"
            copied_mod.write_bytes(b"tampered")
            code, stdout, _stderr = invoke(["--workspace", tmp, "modsets", "verify", "modded", "--json"])
            self.assertEqual(code, 1)
            verify = json.loads(stdout)
            self.assertEqual(verify["status"], "error")
            self.assertEqual(verify["refusal"]["code"], "mod_hash_mismatch")

            copied_mod.write_bytes(mod_zip.read_bytes())
            code, _stdout, stderr = invoke(["--workspace", tmp, "modsets", "lock", "modded"])
            self.assertEqual(code, 0, stderr)
            pack = Path(tmp) / "pack.zip"
            code, stdout, stderr = invoke(["--workspace", tmp, "modsets", "export", "modded", str(pack), "--json"])
            self.assertEqual(code, 0, stderr)
            exported = json.loads(stdout)
            self.assertEqual(exported["files"], 2)
            self.assertTrue(pack.read_bytes().startswith(b"PK\x03\x04"))

    def test_managed_install_operations_are_setup_gated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "factorio-2.0.77.zip"
            archive.write_bytes(b"fake local archive")

            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "installs",
                    "install-version",
                    "2.0.77",
                    "--archive",
                    str(archive),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            install_plan = json.loads(stdout)
            self.assertEqual(install_plan["setup_authority"], "universal-setup")
            self.assertEqual(install_plan["setup_command"], "install_local.plan")
            self.assertFalse(install_plan["mutates_install"])
            self.assertEqual(install_plan["setup_response"]["payload"]["schema"], "usk.install_plan.v1")

            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, stderr = invoke(["--workspace", tmp, "installs", "verify", "fixture", "--json"])
            self.assertEqual(code, 1, stderr)
            verify = json.loads(stdout)
            self.assertEqual(verify["refusal"]["code"], "setup_verification_not_implemented")

            code, stdout, _stderr = invoke(["--workspace", tmp, "installs", "repair", "fixture", "--json"])
            self.assertEqual(code, 1)
            repair = json.loads(stdout)
            self.assertEqual(repair["status"], "refused")
            self.assertEqual(repair["refusal"]["schema"], "common.refusal.v1")
            self.assertEqual(repair["refusal"]["code"], "ownership_denied")
            self.assertFalse(repair["mutates_install"])

            code, stdout, _stderr = invoke(["--workspace", tmp, "installs", "uninstall", "fixture", "--json"])
            self.assertEqual(code, 1)
            uninstall = json.loads(stdout)
            self.assertEqual(uninstall["status"], "refused")
            self.assertEqual(uninstall["refusal"]["code"], "ownership_denied")
            self.assertFalse(uninstall["mutates_install"])

    def test_saves_backup_clone_and_instance_export_are_portable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Source World", "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Target World", "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            fixture_root = SAVE_FIXTURES / "valid_simple_save"
            fixture_before = tree_snapshot(fixture_root)
            source_save = Path(tmp) / "instances" / "source-world" / "saves" / "starter.zip"
            shutil.copyfile(fixture_root / "starter.zip", source_save)
            source_sha1 = hashlib.sha1(source_save.read_bytes()).hexdigest()
            source_sha256 = hashlib.sha256(source_save.read_bytes()).hexdigest()
            source_config = Path(tmp) / "instances" / "source-world" / "config" / "config.ini"
            source_config.write_text(
                "[path]\ntoken=super-secret-token\nservice-token=service-secret\nrcon_password=hunter2\n",
                encoding="utf-8",
            )

            code, stdout, stderr = invoke(["--workspace", tmp, "saves", "list", "--instance", "source-world", "--json"])
            self.assertEqual(code, 0, stderr)
            saves = json.loads(stdout)
            self.assertEqual(saves["saves"][0]["file_name"], "starter.zip")

            backup = Path(tmp) / "starter.backup.zip"
            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "saves",
                    "backup",
                    "starter",
                    "--instance",
                    "source-world",
                    "--to",
                    str(backup),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            backup_result = json.loads(stdout)
            self.assertEqual(Path(backup_result["path"]), backup)
            self.assertEqual(Path(backup_result["destination_path"]), backup)
            self.assertEqual(backup_result["sha1"], source_sha1)
            self.assertEqual(backup_result["sha256"], source_sha256)
            self.assertTrue(backup_result["created_at"].endswith("Z"))
            self.assertEqual(backup.read_bytes(), source_save.read_bytes())
            backup_manifest = Path(backup_result["manifest_path"])
            self.assertTrue(backup_manifest.is_file())
            self.assertEqual(json.loads(backup_manifest.read_text(encoding="utf-8")), backup_result)

            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "saves",
                    "clone",
                    "starter",
                    "--instance",
                    "source-world",
                    "--to-instance",
                    "target-world",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            cloned = json.loads(stdout)
            self.assertEqual(cloned["target_instance_id"], "target-world")
            self.assertEqual(cloned["sha1"], source_sha1)
            self.assertEqual(cloned["sha256"], source_sha256)
            self.assertEqual(
                (Path(tmp) / "instances" / "target-world" / "saves" / "starter.zip").read_bytes(),
                source_save.read_bytes(),
            )

            pack = Path(tmp) / "instance.zip"
            code, stdout, stderr = invoke(["--workspace", tmp, "export", "instance", "source-world", str(pack), "--json"])
            self.assertEqual(code, 0, stderr)
            exported = json.loads(stdout)
            self.assertEqual(exported["schema"], "factorio.instance_export.v1")
            self.assertIn("local_data_root", exported["redactions"])
            self.assertIn("config.ini paths and secrets", exported["redactions"])
            pack_bytes = pack.read_bytes()
            self.assertTrue(pack_bytes.startswith(b"PK\x03\x04"))
            self.assertIn(b"$FACMAN_INSTANCE_ROOT", pack_bytes)
            self.assertNotIn(str(Path(tmp)).encode("utf-8"), pack_bytes)
            self.assertIn(b"[FACMAN_REDACTED]", pack_bytes)
            self.assertNotIn(b"super-secret-token", pack_bytes)
            self.assertNotIn(b"service-secret", pack_bytes)
            self.assertNotIn(b"hunter2", pack_bytes)
            with zipfile.ZipFile(pack) as archive:
                self.assertIn("manifest/export.v1.json", archive.namelist())
                self.assertIn("saves/starter.zip", archive.namelist())

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "import", "instance", str(pack), "--id", "restored-world", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            imported = json.loads(stdout)
            self.assertEqual(imported["schema"], "factorio.instance_import.v1")
            self.assertEqual(imported["instance_id"], "restored-world")
            restored_root = Path(tmp) / "instances" / "restored-world"
            self.assertEqual((restored_root / "saves" / "starter.zip").read_bytes(), source_save.read_bytes())
            restored_config = (restored_root / "config" / "config.ini").read_text(encoding="utf-8")
            self.assertIn(f"read-data={FIXTURE_INSTALL / 'data'}", restored_config)
            self.assertIn(f"write-data={restored_root}", restored_config)
            self.assertNotIn("$FACMAN_", restored_config)
            self.assertFalse((restored_root / "config" / "config-path.cfg").exists())
            restored_manifest = json.loads((restored_root / "instance.v1.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(restored_manifest["local_data_root"]), restored_root)
            self.assertEqual(tree_snapshot(fixture_root), fixture_before)

    def test_save_roundtrip_refusals_are_structured_and_non_mutating(self) -> None:
        fixtures_before = tree_snapshot(SAVE_FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Source World", "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Target World", "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            source_save = workspace / "instances" / "source-world" / "saves" / "starter.zip"
            target_save = workspace / "instances" / "target-world" / "saves" / "starter.zip"
            shutil.copyfile(SAVE_FIXTURES / "valid_simple_save" / "starter.zip", source_save)
            shutil.copyfile(SAVE_FIXTURES / "existing_target" / "existing-target.zip", target_save)
            target_before = target_save.read_bytes()

            existing_backup = workspace / "starter.backup.zip"
            existing_backup.write_bytes(b"existing backup")
            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "saves",
                    "backup",
                    "starter",
                    "--instance",
                    "source-world",
                    "--to",
                    str(existing_backup),
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            backup_refusal = json.loads(stdout)
            self.assertEqual(backup_refusal["refusal"]["code"], "save_backup_target_exists")
            self.assertEqual(existing_backup.read_bytes(), b"existing backup")

            malformed = workspace / "instances" / "source-world" / "saves" / "broken.zip"
            shutil.copyfile(SAVE_FIXTURES / "malformed_save" / "broken.zip", malformed)
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "saves", "backup", "broken", "--instance", "source-world", "--json"]
            )
            self.assertEqual(code, 1)
            malformed_refusal = json.loads(stdout)
            self.assertEqual(malformed_refusal["refusal"]["code"], "save_malformed")
            self.assertFalse((workspace / "instances" / "source-world" / "backups" / "broken.backup.zip").exists())

            malformed_pack = workspace / "malformed-export.zip"
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "export", "instance", "source-world", str(malformed_pack), "--json"]
            )
            self.assertEqual(code, 1)
            export_refusal = json.loads(stdout)
            self.assertEqual(export_refusal["refusal"]["code"], "save_malformed")
            self.assertFalse(malformed_pack.exists())

            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "saves",
                    "clone",
                    "starter",
                    "--instance",
                    "source-world",
                    "--to-instance",
                    "target-world",
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            clone_refusal = json.loads(stdout)
            self.assertEqual(clone_refusal["refusal"]["code"], "save_clone_target_exists")
            self.assertEqual(target_save.read_bytes(), target_before)

            malformed.unlink()
            pack = workspace / "source-world.zip"
            code, _stdout, stderr = invoke(["--workspace", tmp, "export", "instance", "source-world", str(pack), "--json"])
            self.assertEqual(code, 0, stderr)
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "import", "instance", str(pack), "--id", "target-world", "--json"]
            )
            self.assertEqual(code, 1)
            import_refusal = json.loads(stdout)
            self.assertEqual(import_refusal["refusal"]["code"], "instance_import_target_exists")
            self.assertEqual(target_save.read_bytes(), target_before)

        self.assertEqual(tree_snapshot(SAVE_FIXTURES), fixtures_before)

    def test_mod_portal_commands_refuse_without_network_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Portal Test", "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, _stderr = invoke(["--workspace", tmp, "mods", "search", "space", "--json"])
            self.assertEqual(code, 1)
            search = json.loads(stdout)
            self.assertEqual(search["status"], "refused")
            self.assertFalse(search["network_allowed"])
            self.assertEqual(search["refusal"]["schema"], "common.refusal.v1")
            self.assertEqual(search["refusal"]["code"], "network_forbidden")

            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "mods", "install", "example", "--instance", "portal-test", "--json"]
            )
            self.assertEqual(code, 1)
            install = json.loads(stdout)
            self.assertEqual(install["operation"], "mods.install")
            self.assertEqual(install["instance_id"], "portal-test")
            self.assertEqual(install["refusal"]["code"], "network_forbidden")

            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "mods", "update", "--instance", "portal-test", "--json"]
            )
            self.assertEqual(code, 1)
            update = json.loads(stdout)
            self.assertEqual(update["operation"], "mods.update")
            self.assertEqual(update["refusal"]["code"], "network_forbidden")

    def test_server_profiles_and_dev_tools_are_explicitly_gated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Server Base", "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "servers", "create", "Main Server", "--instance", "server-base", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            server = json.loads(stdout)
            self.assertEqual(server["server_id"], "main-server")
            self.assertEqual(server["execution"], "not_implemented")

            code, stdout, stderr = invoke(["--workspace", tmp, "servers", "list", "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)[0]["server_id"], "main-server")

            code, stdout, _stderr = invoke(["--workspace", tmp, "servers", "start", "main-server", "--json"])
            self.assertEqual(code, 1)
            start = json.loads(stdout)
            self.assertEqual(start["operation"], "servers.start")
            self.assertEqual(start["refusal"]["schema"], "common.refusal.v1")
            self.assertEqual(start["refusal"]["code"], "execution_not_enabled")

            code, stdout, stderr = invoke(["--workspace", tmp, "dev", "bug-report", "--json"])
            self.assertEqual(code, 0, stderr)
            bug_report = json.loads(stdout)
            self.assertTrue(bug_report["redacts_secrets"])
            self.assertFalse(bug_report["includes_factorio_binaries"])

            code, stdout, _stderr = invoke(["--workspace", tmp, "dev", "dump-data", "--json"])
            self.assertEqual(code, 1)
            dev_refusal = json.loads(stdout)
            self.assertEqual(dev_refusal["operation"], "dev.dump-data")
            self.assertEqual(dev_refusal["refusal"]["schema"], "common.refusal.v1")
            self.assertEqual(dev_refusal["refusal"]["code"], "execution_not_enabled")


if __name__ == "__main__":
    unittest.main()
