# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools import linux_self_setup


@unittest.skipUnless(sys.platform.startswith("linux"),
                     "not_applicable: Linux setup shell only")
class LinuxSelfSetupOwnershipTests(unittest.TestCase):
    def setup_script(self, root: Path) -> Path:
        script = root / "FacManSetup.run"
        script.write_bytes(linux_self_setup.header("0.1.0-alpha.6", "0" * 64))
        script.chmod(0o755)
        return script

    def invoke(self, script: Path, home: Path, *args: str,
               path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["HOME"] = str(home)
        if path_prefix is not None:
            environment["PATH"] = str(path_prefix) + os.pathsep + environment["PATH"]
        return subprocess.run(
            [str(script), *args], env=environment, capture_output=True,
            text=True, check=False,
        )

    def installed_state(self, install: Path) -> Path:
        generation = install / "generations" / "0.1.0-alpha.6"
        state = install / "state"
        state.mkdir(parents=True)
        (state / "installed-state.v1.json").write_text(
            json.dumps({
                "schema": "facman.installed_state.v1",
                "version": "0.1.0-alpha.6",
                "generation": str(generation),
                "workspace_preserved": True,
            }, separators=(",", ":")) + "\n", encoding="utf-8",
        )
        return generation

    def test_verify_refuses_missing_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            script = self.setup_script(root)
            result = self.invoke(script, home, "verify", "--root", str(root / "install"))
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("verified", result.stdout)

    def test_uninstall_preserves_foreign_current_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            foreign = root / "foreign"
            foreign.mkdir()
            sentinel = foreign / "keep.txt"
            sentinel.write_text("preserve foreign bytes\n", encoding="utf-8")
            install = root / "install"
            install.mkdir()
            self.installed_state(install)
            current = install / "current"
            current.symlink_to(foreign, target_is_directory=True)
            script = self.setup_script(root)
            result = self.invoke(
                script, home, "uninstall", "--root", str(install), "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertTrue(current.is_symlink())
            self.assertEqual(current.resolve(), foreign)
            self.assertEqual(sentinel.read_text(encoding="utf-8"),
                             "preserve foreign bytes\n")

    def test_exact_install_verifies_and_uninstalls_without_touching_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            install = root / "install"
            generation = self.installed_state(install)
            generation.mkdir(parents=True)
            for name in ("FacMan", "facman"):
                executable = generation / name
                executable.write_bytes(b"local package fixture\n")
                executable.chmod(0o755)
            manifest = generation / "share/facman/manifest/MANIFEST.sha256"
            manifest.parent.mkdir(parents=True)
            digest = hashlib.sha256(b"local package fixture\n").hexdigest()
            manifest.write_text(
                f"{digest}  FacMan\n{digest}  facman\n", encoding="utf-8",
            )
            (install / "current").symlink_to(generation, target_is_directory=True)
            workspace = root / "workspace"
            workspace.mkdir()
            sentinel = workspace / "world.zip"
            sentinel.write_bytes(b"preserve this workspace")
            script = self.setup_script(root)
            verified = self.invoke(script, home, "verify", "--root", str(install))
            self.assertEqual(verified.returncode, 0, verified.stderr)
            removed = self.invoke(
                script, home, "uninstall", "--root", str(install), "--yes",
            )
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertFalse(generation.exists())
            self.assertFalse((install / "current").is_symlink())
            self.assertEqual(sentinel.read_bytes(), b"preserve this workspace")

    def test_uninstall_preserves_foreign_terminal_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            user_bin = home / ".local/bin"
            user_bin.mkdir(parents=True)
            install = root / "install"
            generation = self.installed_state(install)
            current = install / "current"
            current.symlink_to(generation, target_is_directory=True)
            foreign = install / "foreign-terminal"
            foreign.write_bytes(b"foreign command\n")
            link = user_bin / "facman"
            link.symlink_to(foreign)
            script = self.setup_script(root)
            result = self.invoke(
                script, home, "uninstall", "--root", str(install), "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertTrue(current.is_symlink())
            self.assertEqual(link.resolve(), foreign)
            self.assertEqual(foreign.read_bytes(), b"foreign command\n")

    def test_uninstall_refuses_linked_state_root_before_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            install = root / "install"
            install.mkdir()
            foreign = root / "foreign-state"
            foreign.mkdir()
            sentinel = foreign / "installed-state.v1.json"
            sentinel.write_bytes(b"foreign state bytes\n")
            (install / "state").symlink_to(foreign, target_is_directory=True)
            current = install / "current"
            current.symlink_to(install / "generations/0.1.0-alpha.6",
                               target_is_directory=True)
            script = self.setup_script(root)
            result = self.invoke(
                script, home, "uninstall", "--root", str(install), "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertTrue(current.is_symlink())
            self.assertTrue((install / "state").is_symlink())
            self.assertEqual(sentinel.read_bytes(), b"foreign state bytes\n")

    def test_uninstall_preserves_foreign_desktop_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            desktop_root = home / ".local/share/applications"
            desktop_root.mkdir(parents=True)
            install = root / "install"
            generation = self.installed_state(install)
            current = install / "current"
            current.symlink_to(generation, target_is_directory=True)
            desktop = desktop_root / "facman.desktop"
            foreign_content = f"[Desktop Entry]\nExec={install}/foreign-command\n"
            desktop.write_text(foreign_content, encoding="utf-8")
            script = self.setup_script(root)
            result = self.invoke(
                script, home, "uninstall", "--root", str(install), "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertTrue(current.is_symlink())
            self.assertEqual(desktop.read_text(encoding="utf-8"), foreign_content)

    def test_uninstall_preserves_changed_setup_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            install = root / "install"
            generation = self.installed_state(install)
            current = install / "current"
            current.symlink_to(generation, target_is_directory=True)
            maintenance = install / "maintenance"
            maintenance.mkdir()
            setup_copy = maintenance / "FacManSetup.run"
            setup_copy.write_bytes(b"foreign setup bytes\n")
            script = self.setup_script(root)
            result = self.invoke(
                script, home, "uninstall", "--root", str(install), "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertTrue(current.is_symlink())
            self.assertEqual(setup_copy.read_bytes(), b"foreign setup bytes\n")

    def test_repair_refuses_foreign_setup_symlink_before_payload_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            install = root / "install"
            generation = self.installed_state(install)
            current = install / "current"
            current.symlink_to(generation, target_is_directory=True)
            maintenance = install / "maintenance"
            maintenance.mkdir()
            foreign = root / "foreign-setup"
            foreign.write_bytes(b"foreign setup bytes\n")
            (maintenance / "FacManSetup.run").symlink_to(foreign)
            script = self.setup_script(root)
            result = self.invoke(
                script, home, "repair", "--root", str(install), "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("refusing a foreign or changed FacMan setup copy", result.stderr)
            self.assertEqual(foreign.read_bytes(), b"foreign setup bytes\n")

    def test_relative_root_is_refused_before_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            script = self.setup_script(root)
            result = self.invoke(
                script, home, "install", "--root", "relative-install", "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertFalse((root / "relative-install").exists())

    def test_embedded_gzip_package_installs_without_zstd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            product = root / "FacMan-0.1.0-alpha.6"
            product.mkdir()
            content = b"#!/bin/sh\nexit 0\n"
            digest = hashlib.sha256(content).hexdigest()
            for name in ("FacMan", "facman"):
                executable = product / name
                executable.write_bytes(content)
                executable.chmod(0o755)
            manifest = product / "share/facman/manifest/MANIFEST.sha256"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                f"{digest}  FacMan\n{digest}  facman\n", encoding="utf-8",
            )
            archive = root / "payload.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                stream.add(product, arcname=product.name)
            script = root / "FacManSetup.run"
            script.write_bytes(
                linux_self_setup.header("0.1.0-alpha.6", linux_self_setup.sha256(archive))
                + archive.read_bytes()
            )
            script.chmod(0o755)
            guard = root / "guard"
            guard.mkdir()
            zstd = guard / "zstd"
            zstd.write_text("#!/bin/sh\nexit 83\n", encoding="utf-8")
            zstd.chmod(0o755)
            installed = self.invoke(script, home, "install", "--yes", path_prefix=guard)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            verified = self.invoke(script, home, "verify", path_prefix=guard)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            installed_root = home / ".local/opt/facman"
            receipt = installed_root / "state/installed-state.v1.json"
            setup_copy = installed_root / "maintenance/FacManSetup.run"
            foreign_receipt = root / "foreign-receipt"
            foreign_setup = root / "foreign-setup"
            os.link(receipt, foreign_receipt)
            os.link(setup_copy, foreign_setup)
            repaired = self.invoke(script, home, "repair", "--yes", path_prefix=guard)
            self.assertEqual(repaired.returncode, 0, repaired.stderr)
            self.assertEqual(foreign_receipt.read_bytes(), receipt.read_bytes())
            self.assertEqual(foreign_setup.read_bytes(), script.read_bytes())
            self.assertNotEqual(receipt.stat().st_ino, foreign_receipt.stat().st_ino)
            self.assertNotEqual(setup_copy.stat().st_ino, foreign_setup.stat().st_ino)
            removed = self.invoke(script, home, "uninstall", "--yes", path_prefix=guard)
            self.assertEqual(removed.returncode, 0, removed.stderr)


if __name__ == "__main__":
    unittest.main()
