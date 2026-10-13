# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Mandatory Darwin consumer proof using produced portable TUI package bytes."""
from __future__ import annotations

import hashlib
import base64
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest
import zlib
from unittest.mock import patch

import native_cli
import test_tui_product
from tools import owned_output, package_build, package_hash_manifest
from tools.package.runtime_identity import require_backend_identity
from tools.package_runtime_smoke import machine_payload
from tools.integration_source_observation import load_integration_source_observation, read_build_identity

MAX_CUSTODY_RAW_BYTES = 4 * 1024 * 1024
MAX_CUSTODY_JSON_BYTES = 6 * 1024 * 1024
MAX_CUSTODY_ENCODED_BYTES = 512 * 1024


def custody_record(receipt: dict, files: dict[str, bytes]) -> dict:
    """Export exact evidence files through a bounded, independently checked log record."""
    if sum(len(value) for value in files.values()) > MAX_CUSTODY_RAW_BYTES:
        raise ValueError("delivered TUI custody raw evidence exceeds 4 MiB; refusing truncation")
    metadata = {name: {"size_bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
                for name, value in files.items()}
    content = {"schema": "facman.macos_delivered_tui_custody_content.v1",
               "mode": receipt["mode"], "test_id": receipt["test_id"],
               "result": receipt["result"], "receipt": receipt,
               "files": {name: dict(metadata[name], bytes_base64=base64.b64encode(value).decode("ascii"))
                         for name, value in files.items()}}
    raw = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(raw) > MAX_CUSTODY_JSON_BYTES:
        raise ValueError("delivered TUI custody canonical JSON exceeds 6 MiB; refusing truncation")
    compressed = zlib.compress(raw, level=9)
    encoded = base64.b64encode(compressed).decode("ascii")
    if len(encoded) > MAX_CUSTODY_ENCODED_BYTES:
        raise ValueError("delivered TUI custody encoded payload exceeds 512 KiB; refusing truncation")
    return {"schema": "facman.macos_delivered_tui_custody.v1",
            "encoding": "zlib_base64", "mode": receipt["mode"], "test_id": receipt["test_id"],
            "result": receipt["result"], "files": metadata,
            "canonical_json_size_bytes": len(raw), "canonical_json_sha256": hashlib.sha256(raw).hexdigest(),
            "compressed_size_bytes": len(compressed), "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
            "encoded_size_bytes": len(encoded), "payload_base64": encoded}


def consumer_environment(environment: dict[str, str]) -> dict[str, str]:
    # Selection of the executable belongs to the test driver, never its consumer.
    result = {name: value for name, value in environment.items()
              if not name.startswith(("FACMAN_", "FLAUNCH_", "ULK_", "USK_", "DYLD_"))}
    result.update(PATH="", TERM="xterm-256color", LANG="C.UTF-8")
    result.pop("NO_COLOR", None)
    return result


@unittest.skipUnless(sys.platform == "darwin", "not_applicable: delivered macOS TUI requires Darwin")
class MacosDeliveredTuiTests(unittest.TestCase):
    # Reuse precisely one scenario, without inheriting the source-build campaign.
    exercise_scenario = test_tui_product.TuiProductTests.exercise_ordinary_selected_save_missing_configuration_then_context

    @classmethod
    def setUpClass(cls) -> None:
        configured = os.environ.get("FACMAN_NATIVE_BUILD_ROOT")
        if not configured:
            raise AssertionError("Darwin delivered TUI requires explicit FACMAN_NATIVE_BUILD_ROOT")
        build_root = Path(configured).resolve(strict=True)
        candidate = os.environ.get("FACMAN_TUI_EXE") or os.environ.get("FACMAN_CLI_EXE")
        if not candidate or Path(candidate).resolve(strict=True) != build_root / "facman":
            raise AssertionError("Darwin delivered TUI requires the current explicit build-root candidate")
        cls._temporary = tempfile.TemporaryDirectory(prefix="delivered-tui-", dir=build_root)
        cls.addClassCleanup(cls._temporary.cleanup)
        cls.root = Path(cls._temporary.name).resolve()
        cls.output = cls.root / "packages"
        cls.package = package_build.build_profile(
            "macos_portable_tui_x64", cls.output, build_root, dist_root=None)
        owned_output.assert_owned_output_root(cls.output, "built-packages")
        cls._consumer_tmp = tempfile.TemporaryDirectory(prefix="facman-delivered-consumer-")
        cls.addClassCleanup(cls._consumer_tmp.cleanup)
        cls.consumer = Path(cls._consumer_tmp.name).resolve()
        if cls.consumer.is_relative_to(native_cli.ROOT.resolve()):
            raise AssertionError("consumer temporary root must be outside the checkout")
        relocated = cls.root / "relocated FacMan Ω"
        cls.package.rename(relocated)
        cls.package = relocated
        cls.executable = cls.package / "bin/facman"
        if not cls.executable.is_file():
            raise AssertionError("produced portable TUI package has no bin/facman")
        if package_hash_manifest.verify_manifest(cls.package):
            raise AssertionError("produced package hash manifest does not verify")
        cls.modes = {path: stat.S_IMODE(path.stat().st_mode)
                     for path in (cls.package, *cls.package.rglob("*"))}
        cls.addClassCleanup(cls.restore_modes)
        for path, mode in cls.modes.items():
            path.chmod(mode & ~0o222)
        cls.evidence_root = build_root / "delivered-tui-evidence"
        owned_output.ensure_owned_output_root(cls.evidence_root, "delivered-tui-evidence")
        cls.environment = consumer_environment(dict(os.environ))
        product = subprocess.run(
            [str(cls.executable), "product", "inspect", "--json"],
            cwd=cls.consumer, env=cls.environment, capture_output=True, text=True, timeout=30)
        if product.returncode != 0:
            raise AssertionError(product.stderr + product.stdout)
        cls.backend = require_backend_identity(cls.package, cls.executable, machine_payload(product.stdout))
        build_info = json.loads((cls.package / "manifest/build_info.v1.json").read_bytes())
        runner_temp = os.environ.get("RUNNER_TEMP")
        if not runner_temp:
            raise AssertionError("Darwin delivered TUI requires the existing runner source observation")
        observation_path = Path(runner_temp) / "facman-source-truth/integration-source-observation.v1.json"
        observation = load_integration_source_observation(
            observation_path,
            workspace_lock_path=native_cli.ROOT / "release/index/workspace_lock.v1.toml",
            expected_profile="macos_portable_cli_x64")
        identity, compiled, identity_digest = read_build_identity(build_root / "facman-build-identity.v1.txt")
        if identity != build_info["build_identity"] or identity_digest != observation["compiled_build_identity"]["sha256"]:
            raise AssertionError("existing CLI observation does not bind the produced TUI build")
        if observation["source"]["commit"] != cls.backend["compiled_source_revision"]:
            raise AssertionError("existing CLI observation does not bind the produced TUI source")
        for provider in observation["providers"]:
            if compiled[provider["id"]] != provider["commit"]:
                raise AssertionError("existing CLI observation does not bind the produced TUI providers")
        cls.binding = {
            "schema": "facman.macos_delivered_tui_result.v1",
            "profile_id": "macos_portable_tui_x64", "backend_identity": cls.backend,
            "build_identity": build_info["build_identity"],
            "build_info_sha256": hashlib.sha256((cls.package / "manifest/build_info.v1.json").read_bytes()).hexdigest(),
            "manifest_sha256": hashlib.sha256((cls.package / "manifest/package.v1.toml").read_bytes()).hexdigest(),
            "closure_sha256": hashlib.sha256((cls.package / "manifest/hashes.sha256").read_bytes()).hexdigest(),
            "build_identity_sha256": hashlib.sha256((build_root / "facman-build-identity.v1.txt").read_bytes()).hexdigest(),
            "native_candidate_sha256": hashlib.sha256(Path(candidate).read_bytes()).hexdigest(),
            "corroborating_cli_observation_sha256": hashlib.sha256(observation_path.read_bytes()).hexdigest(),
            "corroborating_observation_scope": "same_source_providers_build; macos_portable_cli_x64; no_TUI_composition_claim",
            "consumer_cwd_outside_source": not cls.consumer.is_relative_to(native_cli.ROOT.resolve()),
            "consumer_overrides_removed": True, "pathless": True, "package_readonly": True,
            "authenticity": "not_proven_unsigned",
        }
        import test_local_modset_solver
        cls.fixture_install = cls.consumer / "fixture-install"
        shutil.copytree(test_local_modset_solver.FIXTURE_INSTALL, cls.fixture_install)

    @classmethod
    def tearDownClass(cls) -> None:
        problems = package_hash_manifest.verify_manifest(cls.package)
        if problems:
            raise AssertionError("package changed after delivered runs: " + "; ".join(problems))

    @classmethod
    def restore_modes(cls) -> None:
        for path, mode in cls.modes.items():
            if path.exists():
                path.chmod(mode)

    def run_cli(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.assertEqual(str(self.executable), args[0])
        kwargs.update(cwd=self.consumer,
                      env=consumer_environment(dict(kwargs.get("env") or os.environ)), timeout=30)
        return subprocess.run(args, **kwargs)

    def invoke(self, args: list[str], *, stdin: str | None = None,
               environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        assert stdin is not None
        if self.mode == "linear":
            completed = subprocess.run(
                [str(self.executable), "tui", *args], input=stdin, cwd=self.consumer,
                env=self.environment, capture_output=True, text=True, timeout=30)
            self.assertNotIn("\x1b[?1049h", completed.stdout)
        else:
            completed = self.invoke_pty([value for value in args if value != "--plain"], stdin)
        if self.mode == "linear":
            self.outputs.append(completed.stdout)
        return completed

    def invoke_pty(self, args: list[str], stdin: str) -> subprocess.CompletedProcess[str]:
        import fcntl
        import pty
        import re
        import struct
        import termios
        import time
        from test_tui_pty import drain_pty

        master, slave = pty.openpty()
        process = None
        output = bytearray()
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 60, 160, 0, 0))
            original = termios.tcgetattr(slave)
            process = subprocess.Popen(
                [str(self.executable), "tui", *args], cwd=self.consumer, env=self.environment,
                stdin=slave, stdout=slave, stderr=slave, close_fds=True)
            def read_frame() -> bytearray:
                frame = bytearray()
                deadline = time.monotonic() + 10
                while len(re.findall(rb"\x1b\[K\r?\n", frame)) < 60:
                    if time.monotonic() >= deadline:
                        self.fail("Full-screen frame did not complete: " + repr(bytes(frame[-4096:])))
                    drain_pty(master, frame, timeout=0.2)
                    if process.poll() is not None:
                        self.fail("TUI exited before its frame: " + repr(bytes(frame[-4096:])))
                return frame

            output.extend(read_frame())
            self.assertIn(b"FacMan - Factorio Manager", output)
            self.assertIn(b"\x1b[?1049h", output)
            # Each typed key has a fresh rendered frame as its acknowledgement.
            for command in stdin.splitlines():
                key = {"tab": b"\t", "space": b" "}.get(command, command.encode())
                self.assertEqual(1, len(key), command)
                os.write(master, key)
                if command == "q":
                    break
                fresh = read_frame()
                self.assertIn(b"\x1b[H", fresh)
                output.extend(fresh)
            deadline = time.monotonic() + 30
            while process.poll() is None and time.monotonic() < deadline:
                drain_pty(master, output, timeout=0.2)
            code = process.wait(timeout=5)
            drain_pty(master, output)
            self.assertEqual(original, termios.tcgetattr(slave), "terminal flags must be restored")
            self.assertIn(b"\x1b[?25h\x1b[?1049l", output)
            self.assertNotIn(b"Switched to portable linear mode", output)
            return subprocess.CompletedProcess(process.args, code, output.decode("utf-8"), "")
        finally:
            self.outputs.append(output.decode("utf-8", errors="replace"))
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            os.close(slave)
            os.close(master)

    def exercise_delivered(self, mode: str) -> None:
        import test_local_modset_solver
        import test_readiness_builtin_content

        self.mode = mode
        self.outputs: list[str] = []
        self.scenario_evidence: list[dict] = []
        # All existing fixture setup and fresh queries select only produced bytes.
        # Keep their child subprocess environments and cwd consumer-isolated too.
        driver = types.SimpleNamespace(run=self.run_cli, PIPE=subprocess.PIPE)
        passed = False
        try:
            with patch.dict(os.environ, {"FACMAN_CLI_EXE": str(self.executable)}), \
                    patch.object(native_cli, "subprocess", driver), \
                    patch.object(test_local_modset_solver, "FIXTURE_INSTALL", self.fixture_install), \
                    patch.object(test_readiness_builtin_content, "FIXTURE_INSTALL", self.fixture_install):
                self.exercise_scenario(evidence=self.scenario_evidence)
            self.assertEqual(2, len(self.scenario_evidence))
            self.assertEqual([], package_hash_manifest.verify_manifest(self.package))
            for path in self.modes:
                self.assertEqual(0, stat.S_IMODE(path.stat().st_mode) & 0o222)
            passed = True
        finally:
            log = self.evidence_root / f"{mode}.terminal.log"
            log.write_text("\n".join(self.outputs), encoding="utf-8")
            effects = self.evidence_root / f"{mode}.effects.json"
            effects.write_text(json.dumps(self.scenario_evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            receipt = dict(self.binding, mode=mode, result="pass" if passed else "fail",
                           test_id=self.id(), terminal_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                           effects_sha256=hashlib.sha256(effects.read_bytes()).hexdigest())
            try:
                custody = custody_record(receipt, {log.name: log.read_bytes(), effects.name: effects.read_bytes()})
                receipt.update(custody_canonical_json_sha256=custody["canonical_json_sha256"],
                               custody_compressed_sha256=custody["compressed_sha256"])
                print("delivered-tui-custody: " + json.dumps(custody, sort_keys=True, separators=(",", ":")), flush=True)
            except ValueError as error:
                receipt.update(result="fail", custody_export_error=str(error))
                raise
            finally:
                (self.evidence_root / f"{mode}.v1.json").write_text(
                    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                print("delivered-tui-evidence: " + json.dumps(receipt, sort_keys=True), flush=True)

    def test_delivered_linear_selected_save_make_ready(self) -> None:
        self.exercise_delivered("linear")

    def test_delivered_fullscreen_selected_save_make_ready_restores_terminal(self) -> None:
        self.exercise_delivered("fullscreen")
