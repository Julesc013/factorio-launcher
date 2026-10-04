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

    def test_same_version_repair_recovers_each_generation_swap_boundary(self) -> None:
        boundaries = (
            "FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_JOURNAL",
            "FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_OLD_MOVE",
            "FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_NEW_MOVE",
            "FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_BACKUP_REMOVAL",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home = root / "home"
                home.mkdir()
                payload = b"exact repaired executable bytes\n"
                setup = self.package_script(root, "0.1.0-alpha.6", payload)
                workspace = home / "workspace"
                workspace.mkdir()
                sentinel = workspace / "world.zip"
                sentinel.write_bytes(b"preserved workspace bytes")
                installed = self.invoke(setup, home, "install", "--yes")
                self.assertEqual(installed.returncode, 0, installed.stderr)
                install = home / ".local/opt/facman"
                generation = install / "generations/0.1.0-alpha.6"
                (generation / "facman").unlink()
                installed_setup = install / "maintenance/FacManSetup.run"
                interrupted = self.invoke(
                    installed_setup, home, "repair", "--yes",
                    extra_environment={boundary: "1"},
                )
                self.assertEqual(interrupted.returncode, 75, interrupted.stderr)
                repair_record = install / "state/repair-pending.v1"
                self.assertTrue(repair_record.is_dir())
                record_identity = (repair_record.stat().st_dev, repair_record.stat().st_ino)
                self.assertNotEqual(self.invoke(installed_setup, home, "verify").returncode, 0)
                self.assertNotEqual(self.invoke(installed_setup, home, "uninstall", "--yes").returncode, 0)
                recovered = self.invoke(installed_setup, home, "recover", "--yes")
                self.assertEqual(recovered.returncode, 0, recovered.stderr)
                verified = self.invoke(installed_setup, home, "verify")
                self.assertEqual(verified.returncode, 0, verified.stderr)
                self.assertEqual((generation / "facman").read_bytes(), payload)
                self.assertFalse((install / "state/repair-pending.v1").exists())
                self.assertFalse(any((install / "generations").glob(".install-*")))
                self.assertFalse(any((install / "generations").glob(".repair-previous-*")))
                for name in ("facman", "FacMan"):
                    self.assertEqual((home / ".local/bin" / name).readlink(), install / "current" / name)
                self.assertEqual(sentinel.read_bytes(), b"preserved workspace bytes")
                history = home / ".local/state/facman-setup/history"
                archived = list(history.rglob("completed-repair-0.1.0-alpha.6-*"))
                self.assertEqual(len(archived), 1)
                self.assertTrue((archived[0] / "new-target").is_file())
                self.assertEqual((archived[0].stat().st_dev, archived[0].stat().st_ino),
                                 record_identity)
                removed = self.invoke(installed_setup, home, "uninstall", "--yes")
                self.assertEqual(removed.returncode, 0, removed.stderr)

    def test_repair_refuses_foreign_generation_file_before_journaling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            setup = self.package_script(root, "0.1.0-alpha.6", b"owned executable\n")
            self.assertEqual(self.invoke(setup, home, "install", "--yes").returncode, 0)
            install = home / ".local/opt/facman"
            foreign = install / "generations/0.1.0-alpha.6/foreign.txt"
            foreign.write_bytes(b"preserve foreign bytes")
            refused = self.invoke(setup, home, "repair", "--yes")
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(foreign.read_bytes(), b"preserve foreign bytes")
            self.assertFalse((install / "state/repair-pending.v1").exists())

    def test_repair_refuses_special_generation_entry_before_journaling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            setup = self.package_script(root, "0.1.0-alpha.6", b"owned executable\n")
            self.assertEqual(self.invoke(setup, home, "install", "--yes").returncode, 0)
            install = home / ".local/opt/facman"
            special = install / "generations/0.1.0-alpha.6/foreign.pipe"
            os.mkfifo(special)
            refused = self.invoke(setup, home, "repair", "--yes")
            self.assertNotEqual(refused.returncode, 0)
            self.assertTrue(special.exists())
            self.assertFalse((install / "state/repair-pending.v1").exists())
            self.assertFalse(any((install / "generations").glob(".repair-previous-*")))

    def test_repair_recovery_handles_partial_backup_retirement_and_foreign_refusal(self) -> None:
        for foreign_backup in (False, True):
            with self.subTest(foreign_backup=foreign_backup), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home = root / "home"
                home.mkdir()
                payload = b"repaired package bytes\n"
                setup = self.package_script(root, "0.1.0-alpha.6", payload)
                self.assertEqual(self.invoke(setup, home, "install", "--yes").returncode, 0)
                install = home / ".local/opt/facman"
                generation = install / "generations/0.1.0-alpha.6"
                (generation / "facman").write_bytes(b"damaged bytes\n")
                installed_setup = install / "maintenance/FacManSetup.run"
                interrupted = self.invoke(
                    installed_setup, home, "repair", "--yes",
                    extra_environment={
                        "FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_NEW_MOVE": "1",
                    },
                )
                self.assertEqual(interrupted.returncode, 75, interrupted.stderr)
                backup = next((install / "generations").glob(".repair-previous-*"))
                if foreign_backup:
                    foreign = backup / "foreign.txt"
                    foreign.write_bytes(b"foreign bytes")
                    refused = self.invoke(installed_setup, home, "recover", "--yes")
                    self.assertNotEqual(refused.returncode, 0)
                    self.assertEqual(foreign.read_bytes(), b"foreign bytes")
                    foreign.unlink()
                else:
                    (backup / "share/facman/manifest/MANIFEST.sha256").unlink()
                recovered = self.invoke(installed_setup, home, "recover", "--yes")
                self.assertEqual(recovered.returncode, 0, recovered.stderr)
                self.assertEqual((generation / "facman").read_bytes(), payload)
                self.assertEqual(self.invoke(installed_setup, home, "verify").returncode, 0)

    def test_repair_recovery_preserves_foreign_stage_and_retries_owned_prefix(self) -> None:
        locations = (
            ("receipt", "state", ".repair-receipt-"),
            ("setup", "maintenance", ".repair-setup-"),
            ("authority", "state", ".repair-authority-"),
            ("desktop", None, ".repair-desktop-"),
        )
        for label, directory, prefix in locations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home = root / "home"
                home.mkdir()
                payload = b"repair stage package bytes\n"
                setup = self.package_script(root, "0.1.0-alpha.6", payload)
                self.assertEqual(self.invoke(setup, home, "install", "--yes").returncode, 0)
                install = home / ".local/opt/facman"
                generation = install / "generations/0.1.0-alpha.6"
                (generation / "facman").unlink()
                installed_setup = install / "maintenance/FacManSetup.run"
                interrupted = self.invoke(
                    installed_setup, home, "repair", "--yes",
                    extra_environment={
                        "FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_JOURNAL": "1",
                    },
                )
                self.assertEqual(interrupted.returncode, 75, interrupted.stderr)
                journal = install / "state/repair-pending.v1"
                stage_name = Path((journal / "staging-target").read_text().strip()).name
                suffix = stage_name.removeprefix(".install-0.1.0-alpha.6-")
                parent = (install / directory) if directory else home / ".local/share/applications"
                foreign = parent / f"{prefix}{suffix}"
                foreign.write_bytes(b"foreign stage bytes")
                refused = self.invoke(installed_setup, home, "recover", "--yes")
                self.assertNotEqual(refused.returncode, 0)
                self.assertEqual(foreign.read_bytes(), b"foreign stage bytes")
                self.assertFalse((install / "generations" / f".repair-previous-0.1.0-alpha.6-{suffix}").exists())
                foreign.unlink()
                if label == "receipt":
                    foreign.write_bytes((install / "state/installed-state.v1.json").read_bytes()[:8])
                recovered = self.invoke(installed_setup, home, "recover", "--yes")
                self.assertEqual(recovered.returncode, 0, recovered.stderr)
                self.assertFalse(foreign.exists())
                self.assertEqual((generation / "facman").read_bytes(), payload)

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
            self.assertFalse((home / ".local/bin/facman").is_symlink())
            self.assertFalse((home / ".local/bin/FacMan").is_symlink())
            self.assertFalse((home / ".local/opt/facman").exists())
            history = home / ".local/state/facman-setup/history"
            self.assertTrue(any(history.rglob("old-target")))
            self.assertEqual(sentinel.read_bytes(), b"preserved world bytes")

    def prepared_rollback_fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        home = root / "home"
        home.mkdir()
        first = self.package_script(root, "0.1.0-alpha.5", b"previous executable\n")
        second = self.package_script(root, "0.1.0-alpha.6", b"candidate executable\n")
        for script in (first, second):
            result = self.invoke(script, home, "install", "--yes")
            self.assertEqual(result.returncode, 0, result.stderr)
        workspace = home / "workspace"
        workspace.mkdir()
        (workspace / "world.zip").write_bytes(b"preserved rollback world bytes")
        install = home / ".local/opt/facman"
        return home, first, second, install

    def rollback_move_fault(self, root: Path, home: Path, install: Path,
                            boundary: str, timing: str) -> tuple[Path, dict[str, str]]:
        prefix = root / "fault-bin"
        prefix.mkdir()
        history = next((home / ".local/state/facman-setup/history").iterdir())
        destinations = {
            "pending": str(install / "state/update-pending.v1"),
            "binding": str(install / "state/update-pending.v1/new-generation-manifest-sha256"),
            "current": str(install / "current"),
            "receipt": str(install / "state/installed-state.v1.json"),
            "authority": str(install / "state/installed-setup.sha256"),
            "generation": str(install / "state/update-pending.v1/retired-generation"),
            "handoff": str(history / "entry-handoff.v1"),
            "setup": str(install / "maintenance/FacManSetup.run"),
            "history": str(history / "restored-*"),
        }
        wrapper = prefix / "mv"
        wrapper.write_text(
            "#!/bin/sh\nfor destination do :; done\n"
            'case "$destination" in\n'
            '  "$FACMAN_ROLLBACK_FAULT_PATH") fault=true ;;\n'
            '  *) fault=false ;;\nesac\n'
            'if [ "$FACMAN_ROLLBACK_FAULT_KIND" = history ]; then\n'
            '  case "$destination" in "$FACMAN_ROLLBACK_FAULT_HISTORY"/restored-*) fault=true ;; esac\n'
            'fi\n'
            'if [ "$fault" = true ] && [ "$FACMAN_ROLLBACK_FAULT_TIMING" = before ]; then\n'
            '  kill -KILL "$PPID"; exit 0\nfi\n'
            '/usr/bin/mv "$@" || exit $?\n'
            'if [ "$fault" = true ] && [ "$FACMAN_ROLLBACK_FAULT_TIMING" = after ]; then\n'
            '  kill -KILL "$PPID"\nfi\n', encoding="utf-8",
        )
        wrapper.chmod(0o755)
        return prefix, {
            "FACMAN_ROLLBACK_FAULT_PATH": destinations[boundary],
            "FACMAN_ROLLBACK_FAULT_KIND": boundary,
            "FACMAN_ROLLBACK_FAULT_HISTORY": str(history),
            "FACMAN_ROLLBACK_FAULT_TIMING": timing,
        }

    def assert_rollback_restored(self, home: Path, first: Path, install: Path) -> None:
        verified = self.invoke(install / "maintenance/FacManSetup.run", home, "verify")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(linux_self_setup.sha256(install / "maintenance/FacManSetup.run"),
                         linux_self_setup.sha256(first))
        self.assertEqual((install / "current").readlink(),
                         install / "generations/0.1.0-alpha.5")
        self.assertFalse((install / "generations/0.1.0-alpha.6").exists())
        for name in ("facman", "FacMan"):
            self.assertEqual((home / ".local/bin" / name).readlink(),
                             install / "current" / name)
        self.assertEqual((home / "workspace/world.zip").read_bytes(),
                         b"preserved rollback world bytes")
        retired = list((home / ".local/state/facman-setup/history").rglob("retired-generation"))
        self.assertTrue(retired)
        for generation in retired:
            self.assertEqual((generation / "facman").read_bytes(), b"candidate executable\n")
            self.assertEqual((generation / "FacMan").read_bytes(), b"candidate executable\n")

    def test_rollback_recovers_process_loss_at_each_effect_boundary(self) -> None:
        for boundary in ("pending", "current", "receipt", "authority", "generation",
                         "handoff", "setup", "history"):
            for timing in ("before", "after"):
                with self.subTest(boundary=boundary, timing=timing), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    home, first, second, install = self.prepared_rollback_fixture(root)
                    prefix, environment = self.rollback_move_fault(root, home, install, boundary, timing)
                    installed_setup = install / "maintenance/FacManSetup.run"
                    interrupted = self.invoke(installed_setup, home, "rollback", "--yes",
                                              path_prefix=prefix, extra_environment=environment)
                    self.assertEqual(interrupted.returncode, -9, interrupted.stderr)
                    if (boundary, timing) == ("pending", "before"):
                        retried = self.invoke(installed_setup, home, "rollback", "--yes")
                        self.assertEqual(retried.returncode, 0, retried.stderr)
                    elif linux_self_setup.sha256(installed_setup) == linux_self_setup.sha256(second):
                        recovered = self.invoke(installed_setup, home, "recover", "--yes")
                        self.assertEqual(recovered.returncode, 0, recovered.stderr)
                    self.assert_rollback_restored(home, first, install)

    def test_rollback_handoff_handles_repeated_cycles_and_prior_removal(self) -> None:
        for remove_previous in (False, True):
            with self.subTest(remove_previous=remove_previous), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home, first, second, install = self.prepared_rollback_fixture(root)
                prefix, environment = self.rollback_move_fault(root, home, install, "setup", "after")
                for cycle in range(3):
                    installed_setup = install / "maintenance/FacManSetup.run"
                    interrupted = self.invoke(installed_setup, home, "rollback", "--yes",
                                              path_prefix=prefix, extra_environment=environment)
                    self.assertEqual(interrupted.returncode, -9, interrupted.stderr)
                    self.assert_rollback_restored(home, first, install)
                    if remove_previous:
                        removed = self.invoke(installed_setup, home, "uninstall", "--yes")
                        self.assertEqual(removed.returncode, 0, removed.stderr)
                        self.assertFalse(install.exists())
                    reapplied = self.invoke(second, home, "install", "--yes")
                    self.assertEqual(reapplied.returncode, 0, reapplied.stderr)
                    verified = self.invoke(second, home, "verify")
                    self.assertEqual(verified.returncode, 0, verified.stderr)
                    if remove_previous and cycle < 2:
                        removed = self.invoke(second, home, "uninstall", "--yes")
                        self.assertEqual(removed.returncode, 0, removed.stderr)
                        self.assertFalse(install.exists())
                        for script in (first, second):
                            prepared = self.invoke(script, home, "install", "--yes")
                            self.assertEqual(prepared.returncode, 0, prepared.stderr)
                self.assertEqual(len(list((home / ".local/state/facman-setup/history").rglob("retired-generation"))), 3)
                self.assertEqual((home / "workspace/world.zip").read_bytes(), b"preserved rollback world bytes")

    def test_rollback_preserves_foreign_handoff_and_restoration_staging(self) -> None:
        for entry in ("handoff", "pointer", "receipt", "authority", "setup"):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home, first, second, install = self.prepared_rollback_fixture(root)
                history = next((home / ".local/state/facman-setup/history").iterdir())
                paths = {
                    "handoff": history / "entry-handoff.v1/foreign.txt",
                    "pointer": install / ".restoration-current",
                    "receipt": install / "state/.restoration-receipt",
                    "authority": install / "state/.restoration-authority",
                    "setup": install / "maintenance/.restoration-setup",
                }
                foreign = paths[entry]
                foreign.parent.mkdir(parents=True, exist_ok=True)
                foreign.write_bytes(b"preserve foreign content")
                rollback = install / "state/rollback.v1"
                receipt = (install / "state/installed-state.v1.json").read_bytes()
                refused = self.invoke(second, home, "rollback", "--yes")
                self.assertNotEqual(refused.returncode, 0, refused.stdout)
                self.assertEqual(foreign.read_bytes(), b"preserve foreign content")
                self.assertTrue(rollback.is_dir())
                self.assertFalse((install / "state/update-pending.v1").exists())
                self.assertEqual((install / "state/installed-state.v1.json").read_bytes(), receipt)
                self.assertEqual(linux_self_setup.sha256(install / "maintenance/FacManSetup.run"),
                                 linux_self_setup.sha256(second))

    def test_rollback_recovery_refuses_changed_retired_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home, first, second, install = self.prepared_rollback_fixture(root)
            prefix, environment = self.rollback_move_fault(root, home, install, "generation", "after")
            installed_setup = install / "maintenance/FacManSetup.run"
            interrupted = self.invoke(installed_setup, home, "rollback", "--yes",
                                      path_prefix=prefix, extra_environment=environment)
            self.assertEqual(interrupted.returncode, -9, interrupted.stderr)
            changed = install / "state/update-pending.v1/retired-generation/facman"
            changed.write_bytes(b"preserve changed retired content")
            refused = self.invoke(installed_setup, home, "recover", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertEqual(changed.read_bytes(), b"preserve changed retired content")
            self.assertTrue((install / "state/update-pending.v1").is_dir())
            self.assertEqual(linux_self_setup.sha256(installed_setup), linux_self_setup.sha256(second))

    @unittest.skipUnless(os.environ.get("FACMAN_TEST_PRIVATE_MOUNT_NAMESPACE") == "1",
                         "not_applicable: requires the owned private mount proof supervisor")
    def test_rollback_refuses_separately_mounted_history_before_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home, first, second, install = self.prepared_rollback_fixture(root)
            history = next((home / ".local/state/facman-setup/history").iterdir())
            subprocess.run(["mount", "-t", "tmpfs", "-o", "size=8m,nodev,nosuid", "tmpfs", str(history)],
                           check=True, timeout=10)
            try:
                self.assertNotEqual(history.stat().st_dev, (install / "state/rollback.v1").stat().st_dev)
                refused = self.invoke(second, home, "rollback", "--yes")
                self.assertNotEqual(refused.returncode, 0, refused.stdout)
                self.assertIn("one filesystem", refused.stderr)
                self.assertTrue((install / "state/rollback.v1").is_dir())
                self.assertFalse((install / "state/update-pending.v1").exists())
                verified = self.invoke(second, home, "verify")
                self.assertEqual(verified.returncode, 0, verified.stderr)
            finally:
                subprocess.run(["umount", str(history)], check=True, timeout=10)

    def test_rollback_restores_older_journal_with_interrupted_manifest_publication(self) -> None:
        for stage_bytes in (None, 0, 5, 64, 65):
            with self.subTest(stage_bytes=stage_bytes), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home, first, second, install = self.prepared_rollback_fixture(root)
                record = install / "state/rollback.v1"
                digest = (record / "new-generation-manifest-sha256").read_bytes()
                (record / "new-generation-manifest-sha256").unlink()
                if stage_bytes is not None:
                    (record / ".restoration-manifest-binding").write_bytes(digest[:stage_bytes])
                result = self.invoke(second, home, "rollback", "--yes")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_rollback_restored(home, first, install)

        for timing in ("before", "after"):
            with self.subTest(publication_loss=timing), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home, first, second, install = self.prepared_rollback_fixture(root)
                (install / "state/rollback.v1/new-generation-manifest-sha256").unlink()
                prefix, environment = self.rollback_move_fault(root, home, install, "binding", timing)
                installed_setup = install / "maintenance/FacManSetup.run"
                interrupted = self.invoke(installed_setup, home, "rollback", "--yes",
                                          path_prefix=prefix, extra_environment=environment)
                self.assertEqual(interrupted.returncode, -9, interrupted.stderr)
                self.assertEqual((install / "current").readlink(), install / "generations/0.1.0-alpha.6")
                recovered = self.invoke(installed_setup, home, "recover", "--yes")
                self.assertEqual(recovered.returncode, 0, recovered.stderr)
                self.assert_rollback_restored(home, first, install)

    def test_rollback_refuses_foreign_manifest_publication_stage_before_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home, first, second, install = self.prepared_rollback_fixture(root)
            record = install / "state/rollback.v1"
            (record / "new-generation-manifest-sha256").unlink()
            stage = record / ".restoration-manifest-binding"
            stage.write_bytes(b"preserve foreign staging bytes")
            refused = self.invoke(second, home, "rollback", "--yes")
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertEqual(stage.read_bytes(), b"preserve foreign staging bytes")
            self.assertTrue(record.is_dir())
            self.assertFalse((install / "state/update-pending.v1").exists())
            self.assertEqual((install / "current").readlink(), install / "generations/0.1.0-alpha.6")
            self.assertEqual(linux_self_setup.sha256(install / "maintenance/FacManSetup.run"),
                             linux_self_setup.sha256(second))

    def test_fixed_rollback_handoff_requires_complete_retired_custody(self) -> None:
        for phase in ("before_entry_swap", "after_entry_swap", "after_removal"):
            for missing in ("retired-generation", "new-generation-manifest-sha256"):
                with self.subTest(phase=phase, missing=missing), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    home, first, second, install = self.prepared_rollback_fixture(root)
                    boundary = "handoff" if phase == "before_entry_swap" else "setup"
                    prefix, environment = self.rollback_move_fault(root, home, install, boundary, "after")
                    installed_setup = install / "maintenance/FacManSetup.run"
                    interrupted = self.invoke(installed_setup, home, "rollback", "--yes",
                                              path_prefix=prefix, extra_environment=environment)
                    self.assertEqual(interrupted.returncode, -9, interrupted.stderr)
                    if phase == "after_removal":
                        removed = self.invoke(installed_setup, home, "uninstall", "--yes")
                        self.assertEqual(removed.returncode, 0, removed.stderr)
                        self.assertFalse(install.exists())
                    history = next((home / ".local/state/facman-setup/history").iterdir())
                    handoff = history / "entry-handoff.v1"
                    moved = root / missing
                    (handoff / missing).rename(moved)
                    retained = {str(path.relative_to(handoff)): path.read_bytes()
                                for path in handoff.rglob("*") if path.is_file()}
                    receipt = ((install / "state/installed-state.v1.json").read_bytes()
                               if install.exists() else None)
                    setup_sha = linux_self_setup.sha256(installed_setup) if install.exists() else None
                    args = ("recover", "--yes") if phase == "before_entry_swap" else ("install", "--yes")
                    refused = self.invoke(second, home, *args)
                    self.assertNotEqual(refused.returncode, 0, refused.stdout)
                    self.assertTrue(moved.exists())
                    self.assertEqual({str(path.relative_to(handoff)): path.read_bytes()
                                      for path in handoff.rglob("*") if path.is_file()}, retained)
                    self.assertEqual((home / "workspace/world.zip").read_bytes(), b"preserved rollback world bytes")
                    if phase == "after_removal":
                        self.assertFalse(install.exists())
                    else:
                        self.assertEqual((install / "current").readlink(), install / "generations/0.1.0-alpha.5")
                        self.assertEqual((install / "state/installed-state.v1.json").read_bytes(), receipt)
                        self.assertEqual(linux_self_setup.sha256(installed_setup), setup_sha)

    @unittest.skipUnless(os.environ.get("FACMAN_TEST_PRIVATE_MOUNT_NAMESPACE") == "1",
                         "not_applicable: requires the owned private mount proof supervisor")
    def test_rollback_refuses_same_device_bind_mounts_before_admission(self) -> None:
        for entry in ("generation", "state", "journal", "history"):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home, first, second, install = self.prepared_rollback_fixture(root)
                history = next((home / ".local/state/facman-setup/history").iterdir())
                mounted = {
                    "generation": install / "generations/0.1.0-alpha.6",
                    "state": install / "state",
                    "journal": install / "state/rollback.v1",
                    "history": history,
                }[entry]
                receipt = (install / "state/installed-state.v1.json").read_bytes()
                authority = (install / "state/installed-setup.sha256").read_bytes()
                rollback = install / "state/rollback.v1"
                journal = {path.name: path.read_bytes() for path in rollback.iterdir()}
                subprocess.run(["mount", "--bind", str(mounted), str(mounted)], check=True, timeout=10)
                try:
                    self.assertEqual(mounted.stat().st_dev, install.stat().st_dev)
                    refused = self.invoke(second, home, "rollback", "--yes")
                    self.assertNotEqual(refused.returncode, 0, refused.stdout)
                    self.assertIn("separately mounted", refused.stderr)
                    self.assertEqual((install / "current").readlink(), install / "generations/0.1.0-alpha.6")
                    self.assertEqual((install / "state/installed-state.v1.json").read_bytes(), receipt)
                    self.assertEqual((install / "state/installed-setup.sha256").read_bytes(), authority)
                    self.assertEqual(linux_self_setup.sha256(install / "maintenance/FacManSetup.run"),
                                     linux_self_setup.sha256(second))
                    self.assertEqual({path.name: path.read_bytes() for path in rollback.iterdir()}, journal)
                    self.assertFalse((install / "state/update-pending.v1").exists())
                    self.assertFalse((history / "entry-handoff.v1").exists())
                    self.assertEqual((home / "workspace/world.zip").read_bytes(), b"preserved rollback world bytes")
                finally:
                    subprocess.run(["umount", str(mounted)], check=True, timeout=10)

    def test_first_install_cutover_recovers_to_absence_and_can_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            setup = self.package_script(root, "0.1.0-alpha.6", b"first install\n")
            workspace = home / "workspace"
            workspace.mkdir()
            sentinel = workspace / "world.zip"
            sentinel.write_bytes(b"preserved world bytes")
            interrupted = self.invoke(
                setup, home, "install", "--yes",
                extra_environment={"FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_AFTER_CURRENT": "1"},
            )
            self.assertEqual(interrupted.returncode, 75, interrupted.stderr)
            install = home / ".local/opt/facman"
            installed_setup = install / "maintenance/FacManSetup.run"
            self.assertTrue(installed_setup.is_file())
            self.assertTrue((install / "current").is_symlink())
            self.assertFalse((install / "state/installed-state.v1.json").exists())
            self.assertNotEqual(self.invoke(setup, home, "verify").returncode, 0)
            self.assertNotEqual(self.invoke(setup, home, "install", "--yes").returncode, 0)
            interrupted_recovery = self.invoke(
                installed_setup, home, "recover", "--yes",
                extra_environment={
                    "FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_RECOVERY_AFTER_CURRENT": "1",
                },
            )
            self.assertEqual(interrupted_recovery.returncode, 75,
                             interrupted_recovery.stderr)
            self.assertFalse((install / "current").is_symlink())
            self.assertTrue((install / "state/first-install-pending.v1").is_dir())
            recovered = self.invoke(installed_setup, home, "recover", "--yes")
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertFalse((install / "current").exists())
            self.assertFalse((install / "generations/0.1.0-alpha.6").exists())
            self.assertFalse((home / ".local/bin/facman").is_symlink())
            self.assertFalse((home / ".local/share/applications/facman.desktop").exists())
            self.assertEqual(sentinel.read_bytes(), b"preserved world bytes")
            history = home / ".local/state/facman-setup/history"
            self.assertTrue(any(history.rglob("restored-first-install-0.1.0-alpha.6-*/new-target")))
            self.assertEqual(self.invoke(setup, home, "install", "--yes").returncode, 0)
            self.assertEqual(self.invoke(setup, home, "verify").returncode, 0)
            self.assertEqual(self.invoke(setup, home, "uninstall", "--yes").returncode, 0)
            self.assertFalse((home / ".local/bin/facman").is_symlink())
            self.assertFalse((home / ".local/bin/FacMan").is_symlink())

    def test_first_install_recovery_refuses_foreign_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            setup = self.package_script(root, "0.1.0-alpha.6", b"first install\n")
            interrupted = self.invoke(
                setup, home, "install", "--yes",
                extra_environment={"FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_AFTER_CURRENT": "1"},
            )
            self.assertEqual(interrupted.returncode, 75, interrupted.stderr)
            install = home / ".local/opt/facman"
            foreign = root / "foreign"
            foreign.write_text("leave this alone", encoding="utf-8")
            link = home / ".local/bin/facman"
            link.symlink_to(foreign)
            refused = self.invoke(setup, home, "recover", "--yes")
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(link.readlink(), foreign)
            self.assertEqual(foreign.read_text(encoding="utf-8"), "leave this alone")
            self.assertTrue((install / "current").is_symlink())
            link.unlink()
            tamper = install / "generations/0.1.0-alpha.6/foreign.txt"
            tamper.write_text("foreign", encoding="utf-8")
            refused = self.invoke(setup, home, "recover", "--yes")
            self.assertNotEqual(refused.returncode, 0)
            self.assertTrue(tamper.exists())
            tamper.unlink()
            recovered = self.invoke(setup, home, "recover", "--yes")
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertFalse((home / ".local/opt/facman").exists())

    def test_first_install_journal_precedes_final_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            setup = self.package_script(root, "0.1.0-alpha.6", b"first install\n")
            interrupted = self.invoke(
                setup, home, "install", "--yes",
                extra_environment={"FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_AFTER_JOURNAL": "1"},
            )
            self.assertEqual(interrupted.returncode, 75, interrupted.stderr)
            install = home / ".local/opt/facman"
            self.assertFalse((install / "current").is_symlink())
            self.assertFalse((install / "generations/0.1.0-alpha.6").exists())
            self.assertEqual(len(list((install / "generations").glob(".install-0.1.0-alpha.6-*"))), 1)
            self.assertTrue((install / "state/first-install-pending.v1").is_dir())
            recovered = self.invoke(setup, home, "recover", "--yes")
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertFalse(install.exists())
            self.assertEqual(self.invoke(setup, home, "install", "--yes").returncode, 0)
            self.assertEqual(self.invoke(setup, home, "uninstall", "--yes").returncode, 0)

    def test_first_install_recovery_restarts_after_generation_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            setup = self.package_script(root, "0.1.0-alpha.6", b"first install\n")
            interrupted = self.invoke(
                setup, home, "install", "--yes",
                extra_environment={"FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_AFTER_RECEIPT": "1"},
            )
            self.assertEqual(interrupted.returncode, 75, interrupted.stderr)
            install = home / ".local/opt/facman"
            installed_setup = install / "maintenance/FacManSetup.run"
            receipt = install / "state/installed-state.v1.json"
            self.assertTrue(receipt.is_file())
            interrupted_recovery = self.invoke(
                installed_setup, home, "recover", "--yes",
                extra_environment={
                    "FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_RECOVERY_AFTER_GENERATION": "1",
                },
            )
            self.assertEqual(interrupted_recovery.returncode, 75,
                             interrupted_recovery.stderr)
            self.assertFalse((install / "current").is_symlink())
            self.assertFalse((install / "generations/0.1.0-alpha.6").exists())
            self.assertTrue(receipt.is_file())
            recovered = self.invoke(installed_setup, home, "recover", "--yes")
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertFalse(install.exists())

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
