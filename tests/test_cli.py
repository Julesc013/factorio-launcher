from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import facman_executable, invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


def relative_files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


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
        self.assertIn("launch_plan.build", {command["command"] for command in graph["commands"]})

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

            code, stdout, stderr = invoke(["--workspace", tmp, "launch", "plan", "space-age-main", "--json"])
            self.assertEqual(code, 0, stderr)
            alias_plan = json.loads(stdout)
            self.assertEqual(alias_plan["instance_id"], "space-age-main")

            code, stdout, stderr = invoke(["--workspace", tmp, "run", "space-age-main"])
            self.assertEqual(code, 0, stderr)
            self.assertIn("Dry-run only", stdout)

    def test_run_execute_invokes_isolated_plan(self) -> None:
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
            result = json.loads(stdout)

            self.assertEqual(code, 2)
            self.assertEqual(result["preflight"]["status"], "ok")
            self.assertTrue(result["started"])
            self.assertEqual(result["exit_code"], 2)
            history = Path(tmp) / "instances" / "exec-fixture" / "logs" / "launch_history.log"
            self.assertIn("--mod-directory", history.read_text(encoding="utf-8"))
            audit = Path(tmp) / "audit" / "launch_events.log"
            self.assertIn("event=run.execute", audit.read_text(encoding="utf-8"))

    def test_run_execute_refuses_failed_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Locked World", "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            lock = Path(tmp) / "instances" / "locked-world" / "locks" / "save.write.lock"
            lock.write_text("held by another writer\n", encoding="utf-8")

            code, stdout, _stderr = invoke(["--workspace", tmp, "run", "locked-world", "--execute", "--json"])
            refusal = json.loads(stdout)

            self.assertEqual(code, 1)
            self.assertEqual(refusal["schema"], "factorio.launch_refusal.v1")
            self.assertEqual(refusal["refusal"]["code"], "preflight_failed")
            self.assertFalse(refusal["started"])
            self.assertTrue(any("lock blocks launch" in problem for problem in refusal["preflight"]["problems"]))
            self.assertFalse((Path(tmp) / "audit" / "launch_events.log").exists())

    def test_local_mod_import_lock_verify_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mod_zip = Path(tmp) / "filename_only_0.0.1.zip"
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
            self.assertEqual(imported["dependencies"], ["base >= 2.0"])
            self.assertEqual(imported["optional_dependencies"], ["space-age >= 2.0"])
            self.assertEqual(imported["incompatibilities"], ["conflict-mod"])
            self.assertEqual(len(imported["sha1"]), 40)

            code, stdout, stderr = invoke(["--workspace", tmp, "modsets", "lock", "modded", "--json"])
            self.assertEqual(code, 0, stderr)
            lock = json.loads(stdout)
            self.assertEqual(lock["factorio_version"], "2.0.77")
            self.assertEqual(lock["mods"][0]["file_name"], "filename_only_0.0.1.zip")
            self.assertEqual(lock["mods"][0]["name"], "metadata-example")
            self.assertEqual(lock["mods"][0]["optional_dependencies"], ["space-age >= 2.0"])
            self.assertTrue((Path(tmp) / "modsets" / "modded.modset-lock.v1.json").is_file())

            code, stdout, stderr = invoke(["--workspace", tmp, "modsets", "verify", "modded", "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["status"], "ok")

            copied_mod = Path(tmp) / "instances" / "modded" / "mods" / "filename_only_0.0.1.zip"
            copied_mod.write_bytes(b"tampered")
            code, stdout, _stderr = invoke(["--workspace", tmp, "modsets", "verify", "modded", "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["status"], "error")

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
            self.assertEqual(code, 0, stderr)
            verify = json.loads(stdout)
            self.assertEqual(verify["setup_command"], "verify.report")
            self.assertEqual(verify["setup_response"]["payload"]["schema"], "usk.verify_report.v1")

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

            source_save = Path(tmp) / "instances" / "source-world" / "saves" / "starter.zip"
            source_save.write_bytes(b"fake save zip")
            source_config = Path(tmp) / "instances" / "source-world" / "config" / "config.ini"
            source_config.write_text(
                "[path]\ntoken=super-secret-token\nrcon_password=hunter2\n",
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
            self.assertEqual(Path(json.loads(stdout)["path"]), backup)
            self.assertEqual(backup.read_bytes(), b"fake save zip")

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
            self.assertEqual(
                (Path(tmp) / "instances" / "target-world" / "saves" / "starter.zip").read_bytes(),
                b"fake save zip",
            )

            pack = Path(tmp) / "instance.zip"
            code, stdout, stderr = invoke(["--workspace", tmp, "export", "instance", "source-world", str(pack), "--json"])
            self.assertEqual(code, 0, stderr)
            exported = json.loads(stdout)
            self.assertEqual(exported["schema"], "factorio.instance_export.v1")
            self.assertIn("local_data_root", exported["redactions"])
            self.assertIn("config.ini secrets", exported["redactions"])
            pack_bytes = pack.read_bytes()
            self.assertTrue(pack_bytes.startswith(b"PK\x03\x04"))
            self.assertIn(b"$FACMAN_INSTANCE_ROOT", pack_bytes)
            self.assertNotIn(str(Path(tmp)).encode("utf-8"), pack_bytes)
            self.assertIn(b"[REDACTED]", pack_bytes)
            self.assertNotIn(b"super-secret-token", pack_bytes)
            self.assertNotIn(b"hunter2", pack_bytes)

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "import", "instance", str(pack), "--id", "restored-world", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            imported = json.loads(stdout)
            self.assertEqual(imported["schema"], "factorio.instance_import.v1")
            self.assertEqual(imported["instance_id"], "restored-world")
            restored_root = Path(tmp) / "instances" / "restored-world"
            self.assertEqual((restored_root / "saves" / "starter.zip").read_bytes(), b"fake save zip")
            self.assertIn("$FACMAN_INSTANCE_ROOT", (restored_root / "config" / "config-path.cfg").read_text())
            restored_manifest = json.loads((restored_root / "instance.v1.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(restored_manifest["local_data_root"]), restored_root)

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
