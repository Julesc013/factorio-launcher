from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.native_cli import invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


class ManagedPathSafetyTests(unittest.TestCase):
    def import_install(self, workspace: Path, install_id: str = "fixture") -> None:
        code, _stdout, stderr = invoke(
            [
                "--workspace",
                str(workspace),
                "installs",
                "import",
                str(FIXTURE_INSTALL),
                "--id",
                install_id,
                "--json",
            ]
        )
        self.assertEqual(code, 0, stderr)

    def create_instance(self, workspace: Path, instance_id: str = "safe-instance") -> None:
        code, _stdout, stderr = invoke(
            [
                "--workspace",
                str(workspace),
                "instances",
                "create",
                "Safe Instance",
                "--id",
                instance_id,
                "--install",
                "fixture",
                "--json",
            ]
        )
        self.assertEqual(code, 0, stderr)

    def test_install_id_cannot_escape_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            escaped = workspace / "outside-install.json"
            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    str(workspace),
                    "installs",
                    "import",
                    str(FIXTURE_INSTALL),
                    "--id",
                    "../../outside-install",
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "invalid_identifier")
            self.assertFalse(escaped.exists())

    def test_instance_id_cannot_escape_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            self.import_install(workspace)
            escaped = root / "outside-instance"
            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    str(workspace),
                    "instances",
                    "create",
                    "Escape",
                    "--id",
                    "../../outside-instance",
                    "--install",
                    "fixture",
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "invalid_identifier")
            self.assertFalse(escaped.exists())

    def test_reserved_and_absolute_identifiers_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            for install_id in ["CON", "C:escape", "/absolute", "trailing.", "snowman-\N{SNOWMAN}"]:
                with self.subTest(install_id=install_id):
                    code, stdout, _stderr = invoke(
                        [
                            "--workspace",
                            str(workspace),
                            "installs",
                            "import",
                            str(FIXTURE_INSTALL),
                            "--id",
                            install_id,
                            "--json",
                        ]
                    )
                    self.assertEqual(code, 1)
                    self.assertEqual(json.loads(stdout)["refusal"]["code"], "invalid_identifier")

    def test_install_import_is_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            self.import_install(workspace)
            manifest = workspace / "installs" / "refs" / "fixture.json"
            before = manifest.read_bytes()
            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    str(workspace),
                    "installs",
                    "import",
                    str(FIXTURE_INSTALL),
                    "--id",
                    "fixture",
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "persistent_target_exists")
            self.assertEqual(manifest.read_bytes(), before)

    def test_instance_create_is_no_clobber_and_leaves_no_staging_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            self.import_install(workspace)
            self.create_instance(workspace)
            instance = workspace / "instances" / "safe-instance"
            sentinel = instance / "operator-data.txt"
            sentinel.write_text("preserve\n", encoding="utf-8")
            before = (instance / "instance.v1.json").read_bytes()

            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    str(workspace),
                    "instances",
                    "create",
                    "Replacement",
                    "--id",
                    "safe-instance",
                    "--install",
                    "fixture",
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "persistent_target_exists")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
            self.assertEqual((instance / "instance.v1.json").read_bytes(), before)
            self.assertFalse((workspace / "instances" / "safe-instance.facman-staging").exists())

    def test_manifest_cannot_redirect_instance_local_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            external = root / "external-instance"
            self.import_install(workspace)
            self.create_instance(workspace)
            manifest = workspace / "instances" / "safe-instance" / "instance.v1.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["local_data_root"] = str(external)
            manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

            code, stdout, stderr = invoke(
                ["--workspace", str(workspace), "launch-plan", "safe-instance", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            plan = json.loads(stdout)
            self.assertNotIn(str(external), plan["args"])
            self.assertIn(
                str(workspace / "instances" / "safe-instance" / "config" / "config.ini"),
                plan["args"],
            )

    def test_instance_import_id_cannot_escape_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            self.import_install(workspace)
            self.create_instance(workspace)
            pack = root / "instance.zip"
            code, _stdout, stderr = invoke(
                ["--workspace", str(workspace), "export", "instance", "safe-instance", str(pack), "--json"]
            )
            self.assertEqual(code, 0, stderr)
            escaped = root / "escaped-import"
            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    str(workspace),
                    "import",
                    "instance",
                    str(pack),
                    "--id",
                    "../../escaped-import",
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "invalid_identifier")
            self.assertFalse(escaped.exists())

    def test_server_id_cannot_escape_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            self.import_install(workspace)
            self.create_instance(workspace)
            escaped = workspace / "escaped-server.server.v1.json"
            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    str(workspace),
                    "servers",
                    "create",
                    "Escape Server",
                    "--id",
                    "../escaped-server",
                    "--instance",
                    "safe-instance",
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "invalid_identifier")
            self.assertFalse(escaped.exists())

    def test_save_lookup_cannot_escape_instance_save_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            self.import_install(workspace)
            self.create_instance(workspace)
            outside_save = workspace / "instances" / "safe-instance" / "outside.zip"
            shutil.copy2(
                ROOT / "tests" / "fixtures" / "factorio_saves" / "valid_simple_save" / "starter.zip",
                outside_save,
            )
            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    str(workspace),
                    "saves",
                    "backup",
                    "../outside",
                    "--instance",
                    "safe-instance",
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "save_not_found")
            self.assertFalse((workspace / "instances" / "safe-instance" / "backups" / "outside.backup.zip").exists())

    def test_instance_lookup_refuses_link_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            external = root / "external"
            external.mkdir()
            (workspace / "instances").mkdir(parents=True)
            link = workspace / "instances" / "linked-instance"
            if os.name == "nt":
                completed = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(external)],
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            else:
                os.symlink(external, link, target_is_directory=True)
            code, _stdout, _stderr = invoke(
                ["--workspace", str(workspace), "launch-plan", "linked-instance", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertFalse((external / "instance.v1.json").exists())


if __name__ == "__main__":
    unittest.main()
