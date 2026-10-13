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
import time
import types
import unittest
import zlib
from contextlib import ExitStack
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
MAX_PACK_CALLS = 512
MAX_PACK_SECONDS = 600

# Import modules, never their TestCase classes: discovery must not run another
# source campaign or stage another package in this required Darwin lane.
PACK_SCENARIOS = (
    "test_exported_pack_reconstructs_offline_exact_bytes_and_rebound_local_lock",
    "test_process_loss_before_staging_reconstructs_from_the_original_durable_source_binding",
    "test_process_loss_adopts_original_lock_and_recovers_partial_raw_and_generated_states",
    "test_recovery_before_staging_can_itself_be_interrupted_after_a_complete_entry",
    "test_partial_recovery_refuses_changed_source_context_inventory_and_markers_without_effects",
    "test_incomplete_extraction_is_retained_and_recovery_does_not_delete_it",
    "test_process_loss_recovers_through_ordinary_recovery_action",
)
# The unchanged source methods have respectively 3, 1, 2, 1, 18, 1 and 3
# finite fixture cases. Each synchronous child is bounded to 30 seconds, each
# source pause to 20 seconds, and each owned kill/drain to 10 seconds. Custody
# rejects oversize exact streams and inventories rather than truncating them.

PACK_FAULTS = {
    PACK_SCENARIOS[0]: {},
    PACK_SCENARIOS[1]: {"PAUSE": {"precreate"}},
    PACK_SCENARIOS[2]: {"PAUSE": {"extracted-entry", "generated-entry"}},
    PACK_SCENARIOS[3]: {"PAUSE": {"precreate"}, "EXTRACT_FAULT": {"after_entry"}},
    PACK_SCENARIOS[4]: {"EXTRACT_FAULT": {"after_entry"}},
    PACK_SCENARIOS[5]: {"EXTRACT_FAULT": {"after_entry"}},
    PACK_SCENARIOS[6]: {"PAUSE": {"verified", "published", "committed"}},
}


class PackConsumerDriver:
    """Bound every source-scenario child and retain bytes before fixture cleanup."""

    def __init__(self, owner, scenario: str) -> None:
        self.owner, self.scenario = owner, scenario
        self.calls: list[dict] = []
        self.files: dict[str, bytes] = {}
        self.children: list = []
        self.child_records: dict[int, dict] = {}
        self.started = time.monotonic()
        self.stream_bytes = 0

    def snapshot(self, workspace: Path) -> dict:
        self.owner.assertTrue(workspace.is_relative_to(self.owner.consumer))
        inventory = {}
        for path in sorted(workspace.rglob("*")):
            if path.is_symlink():
                inventory[path.relative_to(workspace).as_posix()] = {"symlink": os.readlink(path)}
            elif path.is_file():
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                self.files.setdefault("objects/" + digest, data)
                if sum(map(len, self.files.values())) > MAX_CUSTODY_RAW_BYTES:
                    raise AssertionError("pack custody exceeds bound; refusing truncation")
                inventory[path.relative_to(workspace).as_posix()] = {
                    "sha256": digest, "size_bytes": len(data), "inode": path.stat().st_ino}
        return inventory

    def prepare(self, args: list[str], kwargs: dict) -> tuple[dict, Path]:
        self.owner.assertLess(len(self.calls), MAX_PACK_CALLS)
        self.owner.assertLess(time.monotonic() - self.started, MAX_PACK_SECONDS)
        self.owner.assertEqual(str(self.owner.executable), args[0])
        workspace = Path(args[args.index("--workspace") + 1]).resolve()
        supplied = dict(kwargs.get("env") or os.environ)
        # The adapter clears inherited hooks before the scenario is invoked.
        # Only its explicitly authored, scenario-specific hook values survive.
        hooks = {name: value for name, value in supplied.items()
                 if name.startswith("FACMAN_TEST_")}
        allowed = {"FACMAN_TEST_MODPACK_IMPORT_" + key: values
                   for key, values in PACK_FAULTS[self.scenario].items()}
        for name, value in hooks.items():
            self.owner.assertIn(name, allowed)
            self.owner.assertIn(value, allowed[name])
        environment = consumer_environment(supplied)
        environment.update(hooks)
        kwargs.update(cwd=self.owner.consumer, env=environment)
        record = {"argv": list(args), "executable": str(self.owner.executable),
                  "cwd": str(self.owner.consumer), "workspace": str(workspace),
                  "environment_inputs": {key: environment[key] for key in
                      ("PATH", "TERM", "LANG", *sorted(hooks))},
                  "source_backend_provider_overrides": [], "before": self.snapshot(workspace)}
        self.calls.append(record)
        return record, workspace

    def finish(self, record: dict, workspace: Path, code: int, stdout, stderr) -> None:
        # Repeated communicate() returns cached streams, not another call.
        if "exit_code" not in record:
            self.stream_bytes += sum(len(value.encode("utf-8") if isinstance(value, str) else value)
                                     for value in (stdout, stderr) if value is not None)
        record.update(exit_code=code, stdout=stdout, stderr=stderr, after=self.snapshot(workspace))
        self.owner.assertLessEqual(self.stream_bytes, MAX_CUSTODY_RAW_BYTES)
        self.owner.assertLessEqual(time.monotonic() - self.started, MAX_PACK_SECONDS)

    def run(self, args: list[str], **kwargs):
        record, workspace = self.prepare(args, kwargs)
        kwargs["timeout"] = 30
        completed = subprocess.run(args, **kwargs)
        self.finish(record, workspace, completed.returncode, completed.stdout, completed.stderr)
        return completed

    def popen(self, args: list[str], **kwargs):
        record, workspace = self.prepare(args, kwargs)
        child = subprocess.Popen(args, **kwargs)
        self.children.append(child)
        self.child_records[id(child)] = record
        record["child_pid"] = child.pid
        driver = self

        class OwnedChild:
            def __getattr__(self, name):
                return getattr(child, name)

            def kill(self):
                record["termination"] = "test_owned_kill"
                return child.kill()

            def communicate(self, *arguments, **options):
                options["timeout"] = min(options.get("timeout", 10), 30)
                stdout, stderr = child.communicate(*arguments, **options)
                driver.finish(record, workspace, child.returncode, stdout, stderr)
                return stdout, stderr

        return OwnedChild()

    def drain(self) -> list[dict]:
        cleanup = []
        for child in self.children:
            if child.poll() is None:
                child.kill()
                stdout, stderr = child.communicate(timeout=10)
                record = self.child_records[id(child)]
                # Safety cleanup cannot substitute for the scenario's captured
                # completion or its before-cleanup fixture inventory.
                cleanup.append({"child_pid": child.pid, "argv": record["argv"],
                                "termination": "safety_cleanup_kill", "exit_code": child.returncode,
                                "stdout": stdout, "stderr": stderr})
            else:
                child.communicate(timeout=10)
        return cleanup


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


def terminal_attributes(attributes: list) -> list:
    """Keep every field, including control-character bytes, JSON-safe for custody."""
    return [*attributes[:6], [value[0] if isinstance(value, bytes) else value for value in attributes[6]]]


def queued_input(descriptor: int) -> int:
    import array
    import fcntl
    import termios

    count = array.array("i", [0])
    fcntl.ioctl(descriptor, termios.FIONREAD, count, True)
    return count[0]


def darwin_terminal_control() -> dict:
    """Prove the kernel's retype transition on a separate owned PTY, without flushing."""
    import copy
    import pty
    import termios

    # Missing platform API symbols are failures on the required Darwin lane.
    symbols = {"PENDIN": termios.PENDIN, "FIONREAD": termios.FIONREAD}
    master, slave = pty.openpty()
    tester = unittest.TestCase()
    observations = []
    try:
        original = termios.tcgetattr(slave)
        tester.assertTrue(original[3] & termios.ICANON)
        tester.assertFalse(original[3] & termios.PENDIN)
        raw = copy.deepcopy(original)
        raw[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG | termios.IEXTEN)
        raw[0] &= ~(termios.IXON | termios.ICRNL)
        raw[6][termios.VMIN], raw[6][termios.VTIME] = 1, 0
        os.set_blocking(slave, False)
        for pending in (b"", b"facman-control-preserved\n"):
            termios.tcsetattr(slave, termios.TCSANOW, raw)
            if pending:
                tester.assertEqual(len(pending), os.write(master, pending))
            termios.tcsetattr(slave, termios.TCSANOW, original)
            immediate = termios.tcgetattr(slave)
            expected = copy.deepcopy(original)
            expected[3] |= termios.PENDIN
            tester.assertEqual(expected, immediate, "normal raw-to-canonical must expose kernel retype state")
            count = queued_input(slave)
            final = termios.tcgetattr(slave)
            observations.append({"original": terminal_attributes(original),
                                 "immediate_after_restore": terminal_attributes(immediate),
                                 "fionread_count": count, "after_fionread": terminal_attributes(final),
                                 "pending_input_base64": base64.b64encode(pending).decode("ascii")})
            tester.assertEqual(len(pending), count)
            tester.assertEqual(original, final, "FIONREAD must complete retyping without rewriting settings")
            recovered = os.read(slave, count) if count else b""
            observations[-1]["recovered_input_base64"] = base64.b64encode(recovered).decode("ascii")
            tester.assertEqual(pending, recovered, "the pending input must survive retyping exactly")
            tester.assertEqual(0, queued_input(slave))
            tester.assertEqual(original, termios.tcgetattr(slave))
        return {"schema": "facman.darwin_terminal_control.v1", "result": "pass",
                "symbols": symbols, "observations": observations}
    finally:
        os.close(slave)
        os.close(master)


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
        cls.terminal_control = darwin_terminal_control()
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
            immediate = termios.tcgetattr(slave)
            # Darwin TCSANOW raw→canonical sets PENDIN itself. A queue query
            # completes kernel retyping; it neither rewrites settings nor flushes.
            count = queued_input(slave)
            restored = termios.tcgetattr(slave)
            self.terminal_states.append({"session_index": len(self.terminal_states),
                                         "original": terminal_attributes(original),
                                         "immediate_after_exit": terminal_attributes(immediate),
                                         "fionread_count": count,
                                         "after_fionread": terminal_attributes(restored)})
            self.assertEqual(0, count, "the candidate must consume all typed scenario input")
            self.assertEqual(original, restored, "terminal flags must be restored exactly after kernel retyping")
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
        self.terminal_states: list[dict] = []
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
            self.assertEqual(3 if mode == "fullscreen" else 0, len(self.terminal_states))
            self.assertEqual([], package_hash_manifest.verify_manifest(self.package))
            for path in self.modes:
                self.assertEqual(0, stat.S_IMODE(path.stat().st_mode) & 0o222)
            passed = True
        finally:
            log = self.evidence_root / f"{mode}.terminal.log"
            log.write_text("\n".join(self.outputs), encoding="utf-8")
            effects = self.evidence_root / f"{mode}.effects.json"
            effects.write_text(json.dumps(self.scenario_evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            terminal_state = self.evidence_root / f"{mode}.terminal-state.json"
            terminal_state.write_text(json.dumps(
                {"schema": "facman.macos_delivered_tui_terminal_state.v1", "mode": mode,
                 "control": self.terminal_control, "candidate_sessions": self.terminal_states},
                indent=2, sort_keys=True) + "\n", encoding="utf-8")
            receipt = dict(self.binding, mode=mode, result="pass" if passed else "fail",
                           test_id=self.id(), terminal_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                           terminal_state_sha256=hashlib.sha256(terminal_state.read_bytes()).hexdigest(),
                           terminal_control_result=self.terminal_control["result"],
                           effects_sha256=hashlib.sha256(effects.read_bytes()).hexdigest())
            try:
                custody = custody_record(receipt, {log.name: log.read_bytes(), effects.name: effects.read_bytes(),
                                                  terminal_state.name: terminal_state.read_bytes()})
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

    def exercise_delivered_pack(self, scenario: str) -> None:
        import test_local_modset_solver as solver
        import test_portable_modpack_import as portable
        import test_presentation_pack_import as presentation

        module = presentation if scenario == PACK_SCENARIOS[-1] else portable
        case_type = (presentation.PresentationPackImportTests if module is presentation
                     else portable.PortableModpackImportTests)
        driver = PackConsumerDriver(self, scenario)
        proxy = types.SimpleNamespace(run=driver.run, Popen=driver.popen, PIPE=subprocess.PIPE)
        temporary = types.SimpleNamespace(TemporaryDirectory=lambda **kwargs:
            tempfile.TemporaryDirectory(**dict(kwargs, dir=self.consumer)))
        result = unittest.TestResult()
        passed = False
        try:
            self.assertEqual([], package_hash_manifest.verify_manifest(self.package))
            with ExitStack() as stack:
                stack.enter_context(patch.dict(os.environ, consumer_environment(dict(os.environ)), clear=True))
                stack.enter_context(patch.dict(os.environ, FACMAN_CLI_EXE=str(self.executable)))
                for source in (native_cli, portable, presentation):
                    stack.enter_context(patch.object(source, "subprocess", proxy))
                for source in (solver, portable, presentation):
                    stack.enter_context(patch.object(source, "FIXTURE_INSTALL", self.fixture_install))
                stack.enter_context(patch.object(module, "tempfile", temporary))
                case_type(scenario).run(result)
            self.assertEqual(1, result.testsRun)
            self.assertEqual([], result.skipped, "Darwin source scenarios must execute, never skip")
            self.assertTrue(result.wasSuccessful(), repr(result.errors + result.failures))
            self.assertTrue(driver.calls)
            self.assertTrue(all(all(key in call for key in ("exit_code", "stdout", "stderr", "after"))
                                for call in driver.calls))
            self.assertTrue(all(child.poll() is not None for child in driver.children),
                            "Source scenario must finish every owned child before acceptance")
            self.assertEqual([], package_hash_manifest.verify_manifest(self.package))
            for path in self.modes:
                self.assertEqual(0, stat.S_IMODE(path.stat().st_mode) & 0o222)
            passed = True
        finally:
            live_before_drain = [child.pid for child in driver.children if child.poll() is None]
            cleanup_terminations = driver.drain()
            if live_before_drain:
                passed = False
            mode = "pack-" + scenario.removeprefix("test_")
            effects = {"schema": "facman.macos_delivered_pack_calls.v1", "source_test_id":
                       module.__name__ + "." + case_type.__name__ + "." + scenario,
                       "calls": driver.calls, "tests_run": result.testsRun,
                       "errors": [error for _, error in result.errors],
                       "failures": [failure for _, failure in result.failures],
                       "skips": [reason for _, reason in result.skipped],
                       "live_child_pids_before_safety_drain": live_before_drain,
                       "safety_cleanup_terminations": cleanup_terminations,
                       "call_count": len(driver.calls), "raw_stream_size_bytes": driver.stream_bytes,
                       "scenario_elapsed_seconds": time.monotonic() - driver.started,
                       "limits": {"calls": MAX_PACK_CALLS, "seconds": MAX_PACK_SECONDS,
                                  "raw_stream_bytes": MAX_CUSTODY_RAW_BYTES},
                       "all_owned_children_drained": all(child.poll() is not None for child in driver.children)}
            raw = json.dumps(effects, sort_keys=True, separators=(",", ":")).encode("utf-8")
            files = dict(driver.files, **{"calls.json": raw})
            receipt = dict(self.binding, mode=mode, test_id=self.id(),
                           result="pass" if passed else "fail", source_test_id=effects["source_test_id"],
                           calls_sha256=hashlib.sha256(raw).hexdigest(),
                           source_test_sha256=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
                           fault_controls={key: sorted(values) for key, values in PACK_FAULTS[scenario].items()},
                           evidence_scope="produced_package_offline_source_fixture; no_real_game_or_human_claim")
            try:
                custody = custody_record(receipt, files)
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

    def test_delivered_pack_exact_offline_reconstruction(self) -> None:
        self.exercise_delivered_pack(PACK_SCENARIOS[0])

    def test_delivered_pack_process_loss_before_staging(self) -> None:
        self.exercise_delivered_pack(PACK_SCENARIOS[1])

    def test_delivered_pack_process_loss_partial_raw_and_generated(self) -> None:
        self.exercise_delivered_pack(PACK_SCENARIOS[2])

    def test_delivered_pack_recovery_itself_interrupted(self) -> None:
        self.exercise_delivered_pack(PACK_SCENARIOS[3])

    def test_delivered_pack_changed_and_torn_objects_preserved(self) -> None:
        self.exercise_delivered_pack(PACK_SCENARIOS[4])

    def test_delivered_pack_foreign_partial_objects_preserved(self) -> None:
        self.exercise_delivered_pack(PACK_SCENARIOS[5])

    def test_delivered_pack_ordinary_semantic_recovery(self) -> None:
        self.exercise_delivered_pack(PACK_SCENARIOS[6])
