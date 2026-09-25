# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import hashlib
import json
import shutil
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

    def package_script(self, root: Path, version: str, content: bytes) -> Path:
        product = root / f"FacMan-{version}"
        product.mkdir()
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
        archive = root / f"{version}.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(product, arcname=product.name)
        script = root / f"FacManSetup-{version}.run"
        previous = root / "FacManSetup-0.1.0-alpha.5.run"
        test_predecessor = (linux_self_setup.sha256(previous)
                            if version == "0.1.0-alpha.6" and previous.is_file()
                            else None)
        script.write_bytes(
            linux_self_setup.header(version, linux_self_setup.sha256(archive),
                                    test_predecessor_sha256=test_predecessor)
            + archive.read_bytes()
        )
        script.chmod(0o755)
        return script

    def invoke(self, script: Path, home: Path, *args: str,
               path_prefix: Path | None = None,
               extra_environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["HOME"] = str(home)
        if path_prefix is not None:
            environment["PATH"] = str(path_prefix) + os.pathsep + environment["PATH"]
        if extra_environment is not None:
            environment.update(extra_environment)
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

    def test_first_install_refuses_existing_native_entries_without_state(self) -> None:
        for entry in ("terminal", "desktop"):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home = root / "home"
                home.mkdir()
                install = root / "install"
                current = install / "current"
                if entry == "terminal":
                    user_bin = home / ".local/bin"
                    user_bin.mkdir(parents=True)
                    (user_bin / "facman").symlink_to(current / "facman")
                else:
                    desktop_root = home / ".local/share/applications"
                    desktop_root.mkdir(parents=True)
                    (desktop_root / "facman.desktop").write_text(
                        "[Desktop Entry]\nType=Application\nName=FacMan\n"
                        "Comment=Manage Factorio installations and isolated instances\n"
                        f"Exec={current}/FacMan\nTerminal=false\n"
                        "Categories=Game;Utility;\n", encoding="utf-8",
                    )
                script = self.setup_script(root)
                result = self.invoke(
                    script, home, "install", "--root", str(install), "--yes",
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("refusing foreign FacMan", result.stderr)
                self.assertFalse((install / "state").exists())

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
            maintenance = install / "maintenance"
            maintenance.mkdir()
            (maintenance / "FacManSetup.run").write_bytes(script.read_bytes())
            (install / "state/installed-setup.sha256").write_text(
                linux_self_setup.sha256(script) + "\n", encoding="utf-8",
            )
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

    def test_resolved_root_and_linked_ancestor_are_refused_before_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            script = self.setup_script(root)
            resolved_home = root / "other" / ".." / "home"
            result = self.invoke(
                script, home, "install", "--root", str(resolved_home), "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("unsafe resolved install root", result.stderr)
            self.assertFalse((home / "generations").exists())

            foreign = root / "foreign"
            foreign.mkdir()
            (root / "linked").symlink_to(foreign, target_is_directory=True)
            result = self.invoke(
                script, home, "install", "--root", str(root / "linked/install"), "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("linked ancestor", result.stderr)
            self.assertFalse((foreign / "install").exists())

            result = self.invoke(
                script, home, "install", "--root", str(root / "install with spaces"), "--yes",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("unsupported characters", result.stderr)
            self.assertFalse((root / "install with spaces").exists())

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
            desktop = home / ".local/share/applications/facman.desktop"
            self.assertEqual(desktop.stat().st_mode & 0o777, 0o644)
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

    def test_source_distinct_update_recovers_then_rolls_back_and_reapplies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            first = self.package_script(root, "0.1.0-alpha.5", b"first executable\n")
            second = self.package_script(root, "0.1.0-alpha.6", b"second executable\n")
            workspace = home / "workspace"
            workspace.mkdir()
            sentinel = workspace / "world.zip"
            sentinel.write_bytes(b"preserved world bytes")
            installed = self.invoke(first, home, "install", "--yes")
            self.assertEqual(installed.returncode, 0, installed.stderr)

            interrupted = self.invoke(
                second, home, "install", "--yes",
                extra_environment={"FACMAN_TEST_LINUX_SETUP_INTERRUPT_AFTER_CURRENT": "1"},
            )
            self.assertNotEqual(interrupted.returncode, 0, interrupted.stdout)
            installed_setup = home / ".local/opt/facman/maintenance/FacManSetup.run"
            self.assertEqual(self.invoke(installed_setup, home, "--version").stdout.strip(),
                             "0.1.0-alpha.6")
            recovered = self.invoke(installed_setup, home, "recover", "--yes")
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertEqual(self.invoke(first, home, "verify").returncode, 0)
            self.assertEqual(self.invoke(installed_setup, home, "--version").stdout.strip(),
                             "0.1.0-alpha.5")
            self.assertEqual(sentinel.read_bytes(), b"preserved world bytes")

            updated = self.invoke(second, home, "install", "--yes")
            self.assertEqual(updated.returncode, 0, updated.stderr)
            self.assertEqual(self.invoke(second, home, "verify").returncode, 0)
            rolled_back = self.invoke(second, home, "rollback", "--yes")
            self.assertEqual(rolled_back.returncode, 0, rolled_back.stderr)
            self.assertEqual(self.invoke(first, home, "verify").returncode, 0)
            reapplied = self.invoke(second, home, "install", "--yes")
            self.assertEqual(reapplied.returncode, 0, reapplied.stderr)
            self.assertEqual(self.invoke(second, home, "verify").returncode, 0)
            removed = self.invoke(second, home, "uninstall", "--yes")
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertFalse((home / ".local/opt/facman").exists())
            history = home / ".local/state/facman-setup/history"
            self.assertTrue(any(history.rglob("old-target")))
            self.assertEqual(sentinel.read_bytes(), b"preserved world bytes")

    def test_update_refuses_without_previous_setup_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            first = self.package_script(root, "0.1.0-alpha.5", b"first executable\n")
            second = self.package_script(root, "0.1.0-alpha.6", b"second executable\n")
            self.assertEqual(self.invoke(first, home, "install", "--yes").returncode, 0)
            install = home / ".local/opt/facman"
            (install / "maintenance/FacManSetup.run").unlink()
            refused = self.invoke(second, home, "install", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertIn("Setup authority", refused.stderr)
            self.assertNotEqual(self.invoke(first, home, "verify").returncode, 0)
            self.assertFalse((install / "generations/0.1.0-alpha.6").exists())

    def test_update_refuses_changed_previous_setup_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            first = self.package_script(root, "0.1.0-alpha.5", b"first executable\n")
            second = self.package_script(root, "0.1.0-alpha.6", b"second executable\n")
            self.assertEqual(self.invoke(first, home, "install", "--yes").returncode, 0)
            install = home / ".local/opt/facman"
            setup_copy = install / "maintenance/FacManSetup.run"
            setup_copy.write_bytes(b"foreign setup source\n")
            refused = self.invoke(second, home, "install", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertEqual(setup_copy.read_bytes(), b"foreign setup source\n")
            self.assertNotEqual(self.invoke(first, home, "verify").returncode, 0)
            self.assertFalse((install / "generations/0.1.0-alpha.6").exists())

    def test_update_refuses_modified_previous_setup_header(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            first = self.package_script(root, "0.1.0-alpha.5", b"first executable\n")
            second = self.package_script(root, "0.1.0-alpha.6", b"second executable\n")
            self.assertEqual(self.invoke(first, home, "install", "--yes").returncode, 0)
            install = home / ".local/opt/facman"
            setup_copy = install / "maintenance/FacManSetup.run"
            original = setup_copy.read_bytes()
            changed = original.replace(b"operation='install'\n",
                                       b"echo injected-header-command >/dev/null\noperation='install'\n", 1)
            self.assertNotEqual(changed, original)
            setup_copy.write_bytes(changed)
            refused = self.invoke(second, home, "install", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertEqual(setup_copy.read_bytes(), changed)
            self.assertNotEqual(self.invoke(first, home, "verify").returncode, 0)
            self.assertFalse((install / "generations/0.1.0-alpha.6").exists())

    def test_verify_reports_missing_setup_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            package = self.package_script(root, "0.1.0-alpha.6", b"executable\n")
            self.assertEqual(self.invoke(package, home, "install", "--yes").returncode, 0)
            authority = home / ".local/opt/facman/state/installed-setup.sha256"
            authority.unlink()
            refused = self.invoke(package, home, "verify")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertIn("installed Setup authority", refused.stderr)
            repaired = self.invoke(package, home, "repair", "--yes")
            self.assertEqual(repaired.returncode, 0, repaired.stderr)
            self.assertEqual(self.invoke(package, home, "verify").returncode, 0)

    def test_recovery_and_rollback_refuse_linked_previous_generation(self) -> None:
        for operation in ("recover", "rollback"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home = root / "home"
                home.mkdir()
                first = self.package_script(root, "0.1.0-alpha.5", b"first executable\n")
                second = self.package_script(root, "0.1.0-alpha.6", b"second executable\n")
                self.assertEqual(self.invoke(first, home, "install", "--yes").returncode, 0)
                environment = ({"FACMAN_TEST_LINUX_SETUP_INTERRUPT_AFTER_CURRENT": "1"}
                               if operation == "recover" else None)
                updated = self.invoke(second, home, "install", "--yes",
                                      extra_environment=environment)
                self.assertEqual(updated.returncode, 75 if environment else 0,
                                 updated.stderr)
                install = home / ".local/opt/facman"
                old = install / "generations/0.1.0-alpha.5"
                foreign = root / "foreign-old-generation"
                old.rename(foreign)
                old.symlink_to(foreign, target_is_directory=True)
                current = install / "current"
                original_pointer = current.readlink()
                refused = self.invoke(second, home, operation, "--yes")
                self.assertNotEqual(refused.returncode, 0, refused.stdout)
                self.assertEqual(current.readlink(), original_pointer)
                self.assertTrue(old.is_symlink())
                self.assertEqual((foreign / "facman").read_bytes(), b"first executable\n")

    def test_rollback_refuses_foreign_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            first = self.package_script(root, "0.1.0-alpha.5", b"first executable\n")
            second = self.package_script(root, "0.1.0-alpha.6", b"second executable\n")
            self.assertEqual(self.invoke(first, home, "install", "--yes").returncode, 0)
            self.assertEqual(self.invoke(second, home, "install", "--yes").returncode, 0)
            install = home / ".local/opt/facman"
            foreign = install / "generations/0.1.0-alpha.6/foreign-empty"
            foreign.mkdir()
            current = install / "current"
            refused = self.invoke(second, home, "rollback", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertTrue(foreign.is_dir())
            self.assertEqual(current.readlink(), install / "generations/0.1.0-alpha.6")

    def test_uninstall_refuses_generation_outside_receipt_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            first = self.package_script(root, "0.1.0-alpha.5", b"first executable\n")
            second = self.package_script(root, "0.1.0-alpha.6", b"second executable\n")
            self.assertEqual(self.invoke(first, home, "install", "--yes").returncode, 0)
            self.assertEqual(self.invoke(second, home, "install", "--yes").returncode, 0)
            install = home / ".local/opt/facman"
            foreign = install / "generations/foreign"
            shutil.copytree(install / "generations/0.1.0-alpha.5", foreign)
            refused = self.invoke(second, home, "uninstall", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertEqual((foreign / "facman").read_bytes(), b"first executable\n")
            self.assertTrue((install / "current").is_symlink())

    def test_recovery_refuses_foreign_pointer_and_journal_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            first = self.package_script(root, "0.1.0-alpha.5", b"first executable\n")
            second = self.package_script(root, "0.1.0-alpha.6", b"second executable\n")
            self.assertEqual(self.invoke(first, home, "install", "--yes").returncode, 0)
            interrupted = self.invoke(
                second, home, "install", "--yes",
                extra_environment={"FACMAN_TEST_LINUX_SETUP_INTERRUPT_AFTER_CURRENT": "1"},
            )
            self.assertEqual(interrupted.returncode, 75, interrupted.stderr)
            install = home / ".local/opt/facman"
            current = install / "current"
            foreign = root / "foreign"
            foreign.mkdir()
            sentinel = foreign / "keep.txt"
            sentinel.write_bytes(b"foreign bytes")
            current.unlink()
            current.symlink_to(foreign, target_is_directory=True)
            refused = self.invoke(second, home, "recover", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertEqual(current.resolve(), foreign)
            self.assertEqual(sentinel.read_bytes(), b"foreign bytes")

            current.unlink()
            current.symlink_to(install / "generations/0.1.0-alpha.6")
            journal = install / "state/update-pending.v1"
            (journal / "foreign").write_bytes(b"foreign record")
            refused = self.invoke(second, home, "recover", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertTrue((journal / "foreign").exists())
            self.assertEqual(current.readlink(), install / "generations/0.1.0-alpha.6")

    def test_update_refuses_orphan_staging_and_preserves_lock_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            first = self.package_script(root, "0.1.0-alpha.5", b"first executable\n")
            second = self.package_script(root, "0.1.0-alpha.6", b"second executable\n")
            self.assertEqual(self.invoke(first, home, "install", "--yes").returncode, 0)
            install = home / ".local/opt/facman"
            orphan = install / "generations/.install-foreign"
            orphan.mkdir()
            sentinel = orphan / "keep.txt"
            sentinel.write_bytes(b"foreign bytes")
            refused = self.invoke(second, home, "install", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertEqual(sentinel.read_bytes(), b"foreign bytes")
            self.assertEqual(self.invoke(first, home, "verify").returncode, 0)

            sentinel.unlink()
            orphan.rmdir()
            lock_root = home / ".local/state/facman-setup"
            lock_file = next(lock_root.glob("*.lock"))
            lock_file.unlink()
            foreign = root / "foreign-lock"
            foreign.write_bytes(b"foreign lock bytes")
            os.link(foreign, lock_file)
            self.assertEqual(self.invoke(second, home, "install", "--yes").returncode, 0)
            self.assertEqual(foreign.read_bytes(), b"foreign lock bytes")


if __name__ == "__main__":
    unittest.main()
