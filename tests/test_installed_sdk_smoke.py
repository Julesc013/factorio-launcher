# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.windows_junction import create_junction

from tools import installed_sdk_smoke


class InstalledSdkSmokeTests(unittest.TestCase):
    def test_sanitized_parent_links_consumer_to_sanitizer_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "CMakeCache.txt"
            cache.write_text(
                "FACMAN_ENABLE_SANITIZERS:BOOL=ON\n",
                encoding="utf-8",
            )

            self.assertEqual(
                ["-DFACMAN_CONSUMER_SANITIZERS=ON"],
                installed_sdk_smoke.consumer_parent_configuration(cache),
            )

    def test_regular_parent_does_not_instrument_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "CMakeCache.txt"
            cache.write_text(
                "FACMAN_ENABLE_SANITIZERS:BOOL=OFF\n",
                encoding="utf-8",
            )

            self.assertEqual([], installed_sdk_smoke.consumer_parent_configuration(cache))



class RetainedSdkFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sdk-retention-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name).resolve()
        self.build = self.parent / "build"
        self.source = self.parent / "consumer-source"
        self.build.mkdir()
        self.source.mkdir()
        (self.build / "CMakeCache.txt").write_text("CMAKE_GENERATOR:INTERNAL=Ninja\n", encoding="utf-8")
        self.foreign = self.parent / "foreign.txt"
        self.foreign.write_bytes(b"preserve sibling\r\n")
        self.commands: list[list[str]] = []

    def invoke(self, work_root: Path | None, *, fail_at: int = 0, bad_metadata: bool = False, required_ulk: str = "1.9") -> int:
        """Synthetic command outcomes; never execute CMake or an SDK consumer."""
        arguments = ["installed_sdk_smoke", "--cmake", "synthetic-cmake",
                     "--build-dir", str(self.build), "--source-dir", str(self.source)]
        if work_root is not None:
            arguments += ["--work-root", str(work_root)]

        def fake(command, **options):
            self.commands.append(command)
            number = len(self.commands)
            stdout, stderr = f"command-{number}\r\n".encode() + b"\0", b"diagnostic\r\n"
            if hasattr(options["stdout"], "write"):
                options["stdout"].write(stdout)
                options["stderr"].write(stderr)
            if "--install" in command:
                initial = Path(command[command.index("--prefix") + 1])
                self.observed_root = initial.parent
                files = {
                    "lib/cmake/FacMan/FacManConfig.cmake": 'set(FacMan_FLB_ABI_VERSION "1.3")\n'
                        + f'set(FacMan_REQUIRED_ULK_ABI_VERSION "{required_ulk}")\n',
                    "lib/cmake/FacMan/FacManTargets.cmake": "# relocatable imported targets\n",
                    "lib/pkgconfig/facman-flb.pc": "prefix=${pcfiledir}/../..\n",
                    "share/facman/abi/compatibility.v1.json": json.dumps({
                        "flb_abi": {"major": 1, "minor": 3, "encoded": 65539},
                        "required_ulk_abi": {"major": 1, "minor": 9, "encoded": 65545}}),
                }
                if bad_metadata:
                    files["lib/pkgconfig/facman-flb.pc"] = "prefix=/unreviewed/absolute/path\n"
                for relative, contents in files.items():
                    path = initial / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(contents, encoding="utf-8")
            elif "--build" in command:
                consumer_build = Path(command[command.index("--build") + 1])
                consumer_build.mkdir(parents=True, exist_ok=True)
                for name in ("facman_sdk_consumer", "facman_sdk_legacy_consumer"):
                    (consumer_build / (name + (".exe" if os.name == "nt" else ""))).write_bytes(b"synthetic consumer")
            elif command[0] != "synthetic-cmake":
                self.assertEqual(Path(command[0]).read_bytes(), b"synthetic consumer")
                self.assertIn(str(self.observed_root / "relocated-sdk/lib"), options["env"]["LD_LIBRARY_PATH"])
            return subprocess.CompletedProcess(command, 17 if number == fail_at else 0,
                                               stdout=stdout.decode(), stderr=stderr.decode())

        with mock.patch.object(sys, "argv", arguments), mock.patch.object(
            installed_sdk_smoke.subprocess, "run", side_effect=fake
        ):
            return installed_sdk_smoke.main()

    def test_success_retains_relocated_sdk_both_consumers_and_exact_logs(self) -> None:
        root = self.parent / "SDK retained \u00e9"
        self.assertEqual(self.invoke(root), 0)
        self.assertFalse((root / "initial-sdk").exists())
        self.assertTrue((root / "relocated-sdk/lib/pkgconfig/facman-flb.pc").is_file())
        self.assertEqual(len(self.commands), 5)
        expected = ["01-install", "02-configure", "03-build",
                    "04-facman_sdk_consumer", "05-facman_sdk_legacy_consumer"]
        for number, name in enumerate(expected, 1):
            prefix = root / "commands" / name
            self.assertEqual(prefix.with_suffix(".stdout.raw").read_bytes(),
                             f"command-{number}\r\n".encode() + b"\0")
            self.assertEqual(prefix.with_suffix(".stderr.raw").read_bytes(), b"diagnostic\r\n")
            record = json.loads(prefix.with_suffix(".json").read_bytes())
            self.assertEqual(record["argv"], self.commands[number - 1])
            self.assertEqual(record["exit_code"], 0)
        self.assertIn(f"-DCMAKE_PREFIX_PATH={root / 'relocated-sdk'}", self.commands[1])
        self.assertEqual(self.foreign.read_bytes(), b"preserve sibling\r\n")

    def test_each_command_failure_retains_fixture_and_completed_raw_logs(self) -> None:
        labels = ["01-install", "02-configure", "03-build",
                  "04-facman_sdk_consumer", "05-facman_sdk_legacy_consumer"]
        for failing in range(1, 6):
            with self.subTest(command=failing):
                self.commands = []
                root = self.parent / f"failure-{failing}"
                with self.assertRaisesRegex(RuntimeError, "command failed \\(17\\)"):
                    self.invoke(root, fail_at=failing)
                self.assertTrue(root.is_dir())
                self.assertEqual(len(self.commands), failing)
                self.assertTrue((root / ("initial-sdk" if failing == 1 else "relocated-sdk")).is_dir())
                prefix = root / "commands" / labels[failing - 1]
                self.assertEqual(json.loads(prefix.with_suffix(".json").read_bytes())["exit_code"], 17)
                self.assertEqual(prefix.with_suffix(".stdout.raw").read_bytes(),
                                 f"command-{failing}\r\n".encode() + b"\0")
                self.assertEqual(self.foreign.read_bytes(), b"preserve sibling\r\n")

    def test_bad_relocation_metadata_still_refuses_and_retains_original_evidence(self) -> None:
        root = self.parent / "bad-metadata"
        with self.assertRaisesRegex(RuntimeError, "not relocatable"):
            self.invoke(root, bad_metadata=True)
        self.assertEqual(len(self.commands), 1)
        self.assertEqual((root / "relocated-sdk/lib/pkgconfig/facman-flb.pc").read_text(),
                         "prefix=/unreviewed/absolute/path\n")
        self.assertTrue((root / "commands/01-install.json").is_file())

    def test_stale_ulk_metadata_refuses_before_configure_or_consumer(self) -> None:
        root = self.parent / "stale-abi"
        with self.assertRaisesRegex(RuntimeError, "ABI metadata disagrees"):
            self.invoke(root, required_ulk="1.5")
        self.assertEqual(len(self.commands), 1)
        self.assertTrue((root / "relocated-sdk").is_dir())
        self.assertTrue((root / "commands/01-install.stdout.raw").is_file())

    def test_default_success_and_failure_still_clean_the_temporary_fixture(self) -> None:
        for failing in (0, 2):
            with self.subTest(failing=failing):
                self.commands = []
                if failing:
                    with self.assertRaises(RuntimeError):
                        self.invoke(None, fail_at=failing)
                else:
                    self.assertEqual(self.invoke(None), 0)
                self.assertFalse(self.observed_root.exists())
                self.assertEqual(self.foreign.read_bytes(), b"preserve sibling\r\n")

    def test_invalid_or_existing_root_refuses_before_any_command(self) -> None:
        existing = self.parent / "existing"
        existing.mkdir()
        sentinel = existing / "retain"
        sentinel.write_bytes(b"foreign")
        for root in (existing, self.foreign, Path("relative-sdk"), self.parent / ".." / "escape",
                     self.parent / "missing-parent" / "child"):
            with self.subTest(root=root):
                with self.assertRaises((ValueError, OSError)):
                    self.invoke(root)
                self.assertEqual(self.commands, [])
                self.assertEqual(sentinel.read_bytes(), b"foreign")
                self.assertEqual(self.foreign.read_bytes(), b"preserve sibling\r\n")

    def test_indirect_parent_refuses_before_any_command(self) -> None:
        target = self.parent / "target"
        target.mkdir()
        link = self.parent / "alias"
        if os.name == "nt":
            create_junction(link, target)
        else:
            link.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "link or reparse"):
            self.invoke(link / "retained")
        self.assertEqual(self.commands, [])
        self.assertEqual(list(target.iterdir()), [])


class SdkCommandLogTests(unittest.TestCase):
    def test_real_small_python_failure_preserves_binary_streams_and_exit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sdk-logs-") as temporary:
            log = Path(temporary) / "01-command"
            command = [sys.executable, "-I", "-B", "-c",
                       "import os,sys;os.write(1,b'out\\x00\\r\\n');os.write(2,b'err\\xff\\n');sys.exit(17)"]
            with self.assertRaisesRegex(RuntimeError, "command failed \\(17\\)"):
                installed_sdk_smoke.run(command, log=log)
            self.assertEqual(log.with_suffix(".stdout.raw").read_bytes(), b"out\0\r\n")
            self.assertEqual(log.with_suffix(".stderr.raw").read_bytes(), b"err\xff\n")
            record = json.loads(log.with_suffix(".json").read_bytes())
            self.assertEqual(record["exit_code"], 17)
            self.assertEqual(record["argv"], command)

    def test_spawn_failure_retains_empty_streams_and_error_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sdk-spawn-") as temporary:
            log = Path(temporary) / "01-command"
            with mock.patch.object(installed_sdk_smoke.subprocess, "run", side_effect=OSError("injected spawn")):
                with self.assertRaisesRegex(OSError, "injected spawn"):
                    installed_sdk_smoke.run(["unstarted"], log=log)
            self.assertEqual(log.with_suffix(".stdout.raw").read_bytes(), b"")
            self.assertEqual(log.with_suffix(".stderr.raw").read_bytes(), b"")
            record = json.loads(log.with_suffix(".json").read_bytes())
            self.assertIsNone(record["exit_code"])
            self.assertIn("injected spawn", record["error"])


    def test_existing_log_files_are_preserved_and_prevent_dispatch(self) -> None:
        for suffix in (".stdout.raw", ".stderr.raw", ".json"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory(prefix="sdk-collision-") as temporary:
                log = Path(temporary) / "01-command"
                existing = log.with_suffix(suffix)
                existing.write_bytes(b"original evidence\0\r\n")
                with mock.patch.object(installed_sdk_smoke.subprocess, "run") as child:
                    with self.assertRaises(FileExistsError):
                        installed_sdk_smoke.run(["unstarted"], log=log)
                child.assert_not_called()
                self.assertEqual(existing.read_bytes(), b"original evidence\0\r\n")

    def test_receipt_write_failure_does_not_replace_primary_spawn_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sdk-log-failure-") as temporary:
            log = Path(temporary) / "01-command"
            primary = OSError("primary spawn failure")
            with mock.patch.object(installed_sdk_smoke.subprocess, "run", side_effect=primary), mock.patch.object(
                installed_sdk_smoke.json, "dump", side_effect=OSError("receipt storage failure")
            ):
                with self.assertRaises(OSError) as observed:
                    installed_sdk_smoke.run(["unstarted"], log=log)
            self.assertIs(observed.exception, primary)
            self.assertIn("receipt storage failure", "\n".join(primary.__notes__))
            self.assertTrue(log.with_suffix(".stdout.raw").is_file())
            self.assertTrue(log.with_suffix(".stderr.raw").is_file())
            with log.with_suffix(".json").open("ab") as closed_receipt:
                closed_receipt.write(b"closed and retained")

    def test_receipt_write_failure_on_success_still_refuses(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sdk-log-refusal-") as temporary:
            log = Path(temporary) / "01-command"
            with mock.patch.object(
                installed_sdk_smoke.subprocess, "run", return_value=subprocess.CompletedProcess(["synthetic"], 0)
            ), mock.patch.object(installed_sdk_smoke.json, "dump", side_effect=OSError("receipt storage failure")):
                with self.assertRaisesRegex(OSError, "receipt storage failure"):
                    installed_sdk_smoke.run(["synthetic"], log=log)


class InstalledSdkAbiMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sdk-abi-metadata-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.config = self.root / "FacManConfig.cmake"
        self.compatibility = self.root / "compatibility.v1.json"
        self.contract = {
            "flb_abi": {"major": 1, "minor": 3, "encoded": 65539},
            "required_ulk_abi": {"major": 1, "minor": 9, "encoded": 65545},
        }
        self.compatibility.write_text(json.dumps(self.contract), encoding="utf-8")
        self.valid_config = 'set(FacMan_FLB_ABI_VERSION "1.3")\nset(FacMan_REQUIRED_ULK_ABI_VERSION "1.9")\n'
        self.config.write_text(self.valid_config, encoding="utf-8")

    def test_inconsistent_missing_and_duplicate_advertisements_refuse(self) -> None:
        for name, config in (
            ("stale-ulk", self.valid_config.replace('"1.9"', '"1.5"')),
            ("stale-flb", self.valid_config.replace('"1.3"', '"1.2"')),
            ("missing", 'set(FacMan_FLB_ABI_VERSION "1.3")\n'),
            ("duplicate", self.valid_config + 'set(FacMan_REQUIRED_ULK_ABI_VERSION "1.9")\n'),
        ):
            with self.subTest(name=name):
                self.config.write_text(config, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "ABI metadata disagrees"):
                    installed_sdk_smoke.validate_abi_metadata(self.config, self.compatibility)

    def test_inconsistent_encoding_boolean_and_out_of_range_contract_refuse(self) -> None:
        changes = (("encoded", 65541), ("major", True), ("minor", -1), ("minor", 65536))
        for key, value in changes:
            with self.subTest(key=key, value=value):
                contract = json.loads(json.dumps(self.contract))
                contract["required_ulk_abi"][key] = value
                self.compatibility.write_text(json.dumps(contract), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "contract encoding is inconsistent"):
                    installed_sdk_smoke.validate_abi_metadata(self.config, self.compatibility)

    @unittest.skipUnless(shutil.which("cmake"), "unsupported: CMake metadata interpreter is unavailable")
    def test_actual_config_and_manifest_commands_match_contract_and_consumer(self) -> None:
        source = installed_sdk_smoke.ROOT
        contract = json.loads((source / "contracts/abi/flb/compatibility.v1.json").read_bytes())
        self.compatibility.write_text(json.dumps(contract), encoding="utf-8")
        providers = (source / "cmake/FacManProviders.cmake").read_text(encoding="utf-8")
        version = re.findall(r'set\(_FACMAN_ULK_EXPECTED_ABI_VERSION "([0-9]+\.[0-9]+)"\)', providers)
        self.assertEqual(len(version), 1)
        expected = contract["required_ulk_abi"]
        self.assertEqual(version[0], f'{expected["major"]}.{expected["minor"]}')
        consumer = (source / "tests/installed_consumer/main.c").read_text(encoding="utf-8")
        requested = re.findall(r'flb_required_ulk_abi_v1\(\) != (0x[0-9A-Fa-f]+)u', consumer)
        self.assertEqual([int(item, 16) for item in requested], [expected["encoded"]])
        install = (source / "cmake/FacManInstall.cmake").read_text(encoding="utf-8")
        begin = install.index("file(WRITE ${FACMAN_INSTALL_MANIFEST}")
        end = install.index("\ninstall(FILES ${FACMAN_INSTALL_MANIFEST}", begin)
        script = self.root / "generate.cmake"
        script.write_text(
            'cmake_minimum_required(VERSION 3.20)\ninclude(CMakePackageConfigHelpers)\n'
            'set(PROJECT_VERSION "0.1.0")\n'
            f'set(_FACMAN_ULK_EXPECTED_ABI_VERSION "{version[0]}")\n'
            f'configure_package_config_file("{(source / "cmake/FacManConfig.cmake.in").as_posix()}" '
            f'"{self.config.as_posix()}" INSTALL_DESTINATION "lib/cmake/FacMan")\n'
            f'set(FACMAN_INSTALL_MANIFEST "{(self.root / "artifact.json").as_posix()}")\n'
            + install[begin:end] + "\n", encoding="utf-8"
        )
        # Only CMake metadata commands run: no project languages, install, build or consumer.
        result = subprocess.run([shutil.which("cmake"), "-P", str(script)], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        installed_sdk_smoke.validate_abi_metadata(self.config, self.compatibility)
        manifest = json.loads((self.root / "artifact.json").read_bytes())["sdk"]
        self.assertEqual(manifest["required_ulk_abi"], version[0])
        self.assertEqual(manifest["flb_abi"], f'{contract["flb_abi"]["major"]}.{contract["flb_abi"]["minor"]}')



if __name__ == "__main__":
    unittest.main()
