# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Ordinary fullscreen Content forms use real terminal input and owner effects."""
from __future__ import annotations

import contextlib
import json
import os
import select
import struct
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from native_cli import ROOT, facman_executable
from test_local_modset_solver import call, snapshot
import test_presentation_content_maintenance as maintenance
from test_tui_pty import tui_executable


@unittest.skipIf(os.name == "nt", "not_applicable: real POSIX PTY; ConPTY has its existing lane")
@unittest.skipUnless(tui_executable(), "optional: functional same-binary TUI build is not available")
class FullscreenContentFormTests(unittest.TestCase):
    @contextlib.contextmanager
    def terminal(self, workspace: Path, action: str):
        import fcntl
        import pty
        import termios

        owner = maintenance.ContentMaintenanceTests()
        observed = owner.query(workspace, "content", "load_save")
        index = next(i for i, item in enumerate(observed["available_semantic_actions"])
                     if item["action_id"] == action)
        master, slave = pty.openpty()
        original = termios.tcgetattr(slave)
        process = None
        output = bytearray()
        deadline = time.monotonic() + 60

        def drain(timeout: float):
            ready, _, _ = select.select([master], [], [], timeout)
            if ready:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    return
                self.assertLessEqual(len(output) + len(chunk), 8 * 1024 * 1024,
                                     "bounded PTY capture exceeded")
                output.extend(chunk)

        edit_prompt = b"Edit field=value (Enter review; Esc/Ctrl+C cancel): "

        def until(markers: list[bytes], start: int = 0, *, editor: bool = False,
                  footer: bytes | None = None):
            step_deadline = min(deadline, time.monotonic() + 15)
            while time.monotonic() < step_deadline:
                matched = 0
                for frame in bytes(output[start:]).split(b"\x1b[H")[1:]:
                    # The existing renderer emits exactly 60 complete lines.
                    # Status text persists while each character is rendered, so
                    # its presence alone cannot acknowledge Enter or a timeout.
                    lines = frame.replace(b"\r", b"").split(b"\n")
                    if len(lines) <= 60:
                        continue
                    lines = [line.removesuffix(b"\x1b[K") for line in lines[:60]]
                    complete = b"\n".join(lines)
                    if markers[matched] not in complete:
                        continue
                    if matched + 1 < len(markers):
                        matched += 1
                        continue
                    if lines[-1].startswith(edit_prompt) != editor:
                        continue
                    if footer is not None and lines[-1] != footer:
                        continue
                    return complete, lines[-3].removeprefix(b"Status: ")
                drain(0.1)
                if process.poll() is not None:
                    break
            self.fail(f"No complete editor={editor} frame for {markers!r}: "
                      f"{bytes(output[-4096:])!r}")

        def send(keys: bytes, markers: list[bytes], *, editor: bool = False,
                 footer: bytes | None = None):
            start = len(output)
            self.assertLess(time.monotonic(), deadline)
            self.assertEqual(len(keys), os.write(master, keys))
            return until(markers, start, editor=editor, footer=footer)

        class Terminal:
            editing = False
            status = b""

            def send(inner, keys: bytes, marker: bytes):
                if keys.startswith(b":") and len(keys) > 1:
                    # A prior closed/rejected repaint must not acknowledge the
                    # next assignment. First observe this exact empty editor.
                    inner.send(b":", b"Edit field=value")
                    keys = keys[1:]
                editor = inner.editing
                footer = None
                markers = [marker]
                if keys == b":":
                    editor, footer = True, edit_prompt
                elif marker.startswith(b"Paste ignored;"):
                    ready = b"Status: Paste ignored; typed input is ready"
                    markers = [ready]
                    if b"[200~" in keys or inner.status == b"Terminal escape awaiting continuation":
                        markers.insert(0, b"Status: Paste ignored; type the action selector")
                elif marker == b"Paste escape awaiting continuation":
                    markers = [b"Status: Paste ignored; type the action selector",
                               b"Status: Paste escape awaiting continuation"]
                elif marker != b"Terminal escape awaiting continuation" and keys.endswith(
                        (b"\r", b"\n", b"\x03", b"\x1b")):
                    editor = False
                complete, inner.status = send(keys, markers, editor=editor, footer=footer)
                inner.editing = editor
                return complete

            def field(inner, value: bytes):
                # The editor receives real text, including global-shortcut bytes.
                return send(b":" + value + b"\r", b"Action input updated; activate the action to continue")

        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 60, 160, 0, 0))
            environment = os.environ.copy()
            for name in ("NO_COLOR", "FACMAN_UI", "FACMAN_SAFE_MODE"):
                environment.pop(name, None)
            environment.update(TERM="xterm-256color", LANG="C.UTF-8")
            executable = facman_executable()
            process = subprocess.Popen(
                [str(executable), "tui", "--ordinary", "--transport", "process",
                 "--cli-path", str(executable), "--workspace", str(workspace)],
                cwd=ROOT, env=environment, stdin=slave, stdout=slave, stderr=slave,
                close_fds=True)
            until([b"q Quit"])
            self.assertIn(b"\x1b[?1049h", output)
            self.assertIn(b"\x1b[?2004h", output)
            send(b"s", [b"Selected Save"])
            labels = {"modsets.plan": b"Plan instance modset",
                      "modsets.apply": b"Apply instance modset",
                      "modsets.rollback": b"Roll back instance modset"}
            send(b"4" + b"\t" * index, [b"Focus: Action: " + labels[action]])
            yield Terminal()
            os.write(master, b"q")
            while process.poll() is None and time.monotonic() < deadline:
                drain(0.1)
            self.assertEqual(0, process.wait(timeout=5), bytes(output[-4096:]))
            for _ in range(10):
                drain(0.05)
            immediate = termios.tcgetattr(slave)
            queued = struct.unpack("I", fcntl.ioctl(slave, termios.FIONREAD, struct.pack("I", 0)))[0]
            self.assertEqual(0, queued)
            # Darwin may set PENDIN until FIONREAD completes canonical retyping.
            self.assertEqual(original, termios.tcgetattr(slave), (original, immediate))
            self.assertIn(b"\x1b[?25h\x1b[?1049l", output)
            self.assertIn(b"\x1b[?2004l", output)
            self.assertNotIn(b"Switched to portable linear mode", output)
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            os.close(slave)
            os.close(master)

    def test_exact_version_edit_preview_cancel_apply_and_explicit_history_rollback(self):
        owner = maintenance.ContentMaintenanceTests()
        with tempfile.TemporaryDirectory(prefix="content-maintenance-fullscreen-") as value:
            workspace = Path(value)
            instance = owner.prepare(workspace)
            original, protected = owner.managed(workspace), owner.protected(instance)
            frozen = snapshot(workspace)

            def identities():
                return {p.relative_to(workspace).as_posix(): maintenance.joined.file_identity(p)
                        for p in [workspace, *workspace.rglob("*")]}

            frozen_identities = identities()

            def assert_frozen():
                self.assertEqual(frozen, snapshot(workspace))
                self.assertEqual(frozen_identities, identities())

            with self.terminal(workspace, "modsets.plan") as terminal:
                terminal.send(b" ", b"Action input:")
                terminal.send(b":mod_identity=q2s\x1b", b"Cancellation requested")
                assert_frozen()
                # A paste suffix after cancellation must not become Space/Run,
                # page navigation, q, or another editor command.
                terminal.send(b"\x1b[200~:mod_identity=simple@2.0.0\r  \x03q4\x1b[201~",
                              b"Paste ignored;")
                assert_frozen()
                terminal.send(b" ", b"Action input:")
                terminal.send(b":mod_identity=q2s\x03", b"Cancellation requested")
                assert_frozen()
                terminal.send(b" ", b"Action input:")
                # Invalid text cannot become a global q command or dispatch.
                terminal.send(b":q\r", b"Action input requires field=value")
                terminal.send(b":unknown=1\r", b"Unknown action input field: unknown")
                # Unsupported bytes cannot be silently removed from an otherwise
                # valid version selector, producing a different successful input.
                terminal.send(b":mod_identity=simple@2.0.0\xc3\xa9\r",
                              b"Action input rejected: only printable ASCII selectors are supported")
                assert_frozen()
                terminal.send(b":mod_identity=simple@2.0.0\x01\r",
                              b"Action input rejected: only printable ASCII selectors are supported")
                assert_frozen()
                terminal.send(b":mod_identity=simple@2.0.0\x1b\x01\r",
                              b"Action input rejected: only printable ASCII selectors are supported")
                assert_frozen()
                terminal.send(b":mod_identity=simple@2.0.0\x1b\xc3\xa9\r",
                              b"Action input rejected: only printable ASCII selectors are supported")
                assert_frozen()
                terminal.send(b":", b"Edit field=value")
                # A split immediately after the paste-END Escape must recover
                # typed editing instead of leaving paste quarantine stuck.
                terminal.send(b"\x1b[200~\x1bq  \x03ms24\x1b",
                              b"Paste escape awaiting continuation")
                terminal.send(b"[201~", b"Paste ignored; typed input is ready")
                # A payload Escape directly adjacent to the paste-end Escape
                # must resynchronize, close quarantine, and retain typed editing.
                terminal.send(b"\x1b[200~  q\x1b\x1b[201~",
                              b"Paste ignored; typed input is ready")
                # A new Escape also resynchronizes an overlong unfinished CSI.
                terminal.send(b"\x1b[" + b"1" * 40 + b"\x1b[200~  q\x1b[201~",
                              b"Paste ignored; typed input is ready")
                terminal.send(b"mod_identity=simple@2.0.0\r",
                              b"Action input rejected: only printable ASCII selectors are supported")
                assert_frozen()
                # Completing an unknown overlong CSI must reject the entire edit,
                # rather than silently accepting its otherwise valid prefix.
                terminal.send(b":mod_identity=simple@2.0.0\x1b[" + b"1" * 40 + b"~\r",
                              b"Action input rejected: only printable ASCII selectors are supported")
                assert_frozen()
                terminal.send(b":mod_identity=simple@2.0.0\x1b[11",
                              b"Terminal escape awaiting continuation")
                terminal.send(b"\x1b[A\r",
                              b"Action input rejected: only printable ASCII selectors are supported")
                assert_frozen()
                terminal.send(b":", b"Edit field=value")
                terminal.send(b"mod_identity=simple@2.0.9\x7f0\r",
                              b"Action input updated; activate the action to continue")
                terminal.send(b" ", b"simple: 1.0.0 -> 2.0.0")
            assert_frozen()

            with self.terminal(workspace, "modsets.apply") as terminal:
                terminal.send(b" ", b"Confirm Apply instance modset")
                # Standalone Esc must cancel, yet preserve a possible delayed
                # paste prefix so its payload cannot become ordinary actions.
                terminal.send(b"\x1b", b"Cancellation requested")
                terminal.send(b"[200~  qms24\x1b[201~", b"Paste ignored;")
                assert_frozen()
                # Cancellation Escape immediately adjacent to a paste-start
                # Escape cannot swallow the marker and expose its shortcuts.
                terminal.send(b"\x1b\x1b[200~  qms24\x1b[201~", b"Paste ignored;")
                assert_frozen()
                terminal.send(b" ", b"Confirm Apply instance modset")
                terminal.field(b"mod_identity=simple@2.0.0")
                terminal.send(b" ", b"Confirm Apply instance modset")
                assert_frozen()
                terminal.send(b"\x03", b"Cancellation requested")
            assert_frozen()

            # A real external activation change still refuses the old observation.
            activation = instance / "mods/mod-list.json"
            activation_bytes = activation.read_bytes()
            with self.terminal(workspace, "modsets.apply") as terminal:
                terminal.send(b" ", b"Action input:")
                terminal.field(b"mod_identity=simple@2.0.0")
                activation.write_bytes(activation_bytes + b"\n")
                stale = snapshot(workspace)
                stale_identities = identities()
                terminal.send(b" ", b"Confirm Apply instance modset")
                terminal.send(b" ", b"stale_snapshot_revision")
                self.assertEqual(stale, snapshot(workspace))
                self.assertEqual(stale_identities, identities())
            activation.write_bytes(activation_bytes)
            assert_frozen()

            with self.terminal(workspace, "modsets.apply") as terminal:
                terminal.send(b" ", b"Confirm Apply instance modset")
                assert_frozen()
                # Force the parser continuation timeout while Apply is armed.
                # Its later paste payload must never reach Space/Run or q.
                terminal.send(b"\x1b[20", b"Terminal escape awaiting continuation")
                terminal.send(b"0~  qms24\x1b[201~", b"Paste ignored;")
                assert_frozen()
                terminal.field(b"mod_identity=simple@2.0.0")
                # Editing an ALREADY ARMED default must disarm confirmation.
                # Editing clears any confirmation armed for the old/default value.
                terminal.send(b" ", b"Confirm Apply instance modset")
                assert_frozen()
                terminal.send(b" ", b"Apply instance modset completed")
            receipts = [json.loads(p.read_bytes()) for p in
                        (workspace / ".facman/action-receipts-v2").glob("*.v2.json")]
            applied = [json.loads(row["result_json"]) for row in receipts
                       if row["action_id"] == "modsets.apply"]
            self.assertEqual(1, len(applied))
            owner.assert_selection(applied[0]["action_payload"], "2.0.0")
            self.assertEqual(protected, owner.protected(instance))
            self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])
            transaction = applied[0]["action_payload"]["transaction_id"]
            history_root = instance / "mods/.facman-modset-history" / transaction
            history = snapshot(history_root)
            history_identities = {
                p.relative_to(history_root).as_posix(): maintenance.joined.file_identity(p)
                for p in [history_root, *history_root.rglob("*")]}
            frozen_applied = snapshot(workspace)

            with self.terminal(workspace, "modsets.rollback") as terminal:
                terminal.send(b" ", b"Confirm Roll back instance modset")
                # Explicit history selection must work even when its valid default
                # already armed confirmation; opening the editor disarms it.
                terminal.field(b"transaction_id=" + transaction.encode("ascii"))
                terminal.send(b" ", b"Confirm Roll back instance modset")
                self.assertEqual(frozen_applied, snapshot(workspace))
                terminal.send(b" ", b"Roll back instance modset completed")
            self.assertEqual(original, owner.managed(workspace))
            self.assertEqual(protected, owner.protected(instance))
            # Rollback appends its displaced applied state and receipt while
            # retaining every earlier history entry's exact bytes and identity.
            self.assertEqual(history, {name: (history_root / name).read_bytes() for name in history})
            self.assertEqual(history_identities, {
                name: maintenance.joined.file_identity(history_root / name)
                for name in history_identities})
            for key, target in (
                    ("mod-list", "instances/main/mods/mod-list.json"),
                    ("local-lock", "instances/main/mods/modset-lock.v1.json"),
                    ("shared-lock", "modsets/main.modset-lock.v1.json")):
                for suffix in (".applied", ".rollback-displaced"):
                    self.assertEqual(frozen_applied[target], (history_root / (key + suffix)).read_bytes())
            self.assertEqual({"schema": "factorio.modset_rollback.v1",
                              "transaction_id": transaction, "instance_id": "main", "status": "rolled_back"},
                             json.loads((history_root / "rollback.v1.json").read_bytes()))
            rollback_receipts = [json.loads(p.read_bytes()) for p in
                                 (workspace / ".facman/action-receipts-v2").glob("*.v2.json")]
            rolled_back = [json.loads(row["result_json"]) for row in rollback_receipts
                           if row["action_id"] == "modsets.rollback"]
            self.assertEqual(1, len(rolled_back))
            self.assertEqual("completed", rolled_back[0]["outcome"])
            self.assertEqual(transaction, rolled_back[0]["action_payload"]["transaction_id"])
            self.assertEqual("rolled_back", rolled_back[0]["action_payload"]["status"])
            self.assertTrue(rolled_back[0]["action_payload"]["mutation_executed"])
            self.assertTrue(rolled_back[0]["action_payload"]["local_artifacts_only"])
            self.assertFalse(rolled_back[0]["action_payload"]["portal_access"])
            self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])


if __name__ == "__main__":
    unittest.main()
