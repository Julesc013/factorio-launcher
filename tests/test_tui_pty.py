# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import select
import signal
import struct
import subprocess
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tui_executable() -> Path | None:
    configured = os.environ.get("FACMAN_CLI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/native-smoke/facman",
        ROOT / "build/macos-native/facman",
    ]
    return next((path for path in candidates if path.is_file()), None)


def drain_pty(master: int, output: bytearray, timeout: float = 1.0) -> None:
    """Capture terminal restoration bytes that may follow process exit."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], 0.1)
        if not ready:
            break
        try:
            chunk = os.read(master, 65536)
        except OSError:
            break
        if not chunk:
            break
        output.extend(chunk)


@unittest.skipIf(os.name == "nt", "not_applicable: PTY is POSIX-only; ConPTY has a separate Windows lane")
@unittest.skipUnless(tui_executable(), "optional: functional same-binary TUI build is not available")
class TuiPtyTests(unittest.TestCase):
    def test_full_screen_capability_help_resize_and_clean_exit(self) -> None:
        import fcntl
        import pty
        import termios

        executable = tui_executable()
        assert executable is not None
        master, slave = pty.openpty()
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
            environment = os.environ.copy()
            environment.update({"TERM": "xterm-256color", "LANG": "C.UTF-8"})
            process = subprocess.Popen(
                [str(executable), "tui"],
                cwd=ROOT,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=environment,
                close_fds=True,
            )
            os.close(slave)
            slave = -1
            output = bytearray()
            deadline = time.monotonic() + 10
            while b"FacMan - Factorio Manager" not in output and time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    output.extend(os.read(master, 65536))
            self.assertIn(b"\x1b[?1049h", output)
            self.assertIn(b"FacMan - Factorio Manager", output)

            os.write(master, b"\x1bOP")  # F1
            os.write(master, b"\x03")  # Ctrl+C is a typed cancel event, not process death
            time.sleep(0.2)
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 10, 30, 0, 0))
            os.write(master, b"\x12")  # refresh observes the sub-minimum dimensions
            time.sleep(0.2)
            os.write(master, b"q\n")  # full-screen guard has restored canonical input
            exit_deadline = time.monotonic() + 10
            while process.poll() is None and time.monotonic() < exit_deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    try:
                        output.extend(os.read(master, 65536))
                    except OSError:
                        break
            return_code = process.wait(timeout=2)
            drain_pty(master, output)
            self.assertEqual(return_code, 0)
            self.assertIn(b"Help: use numbered pages", output)
            self.assertIn(b"without manufacturing an operation outcome", output)
            self.assertIn(b"Switched to portable linear mode", output)
            self.assertIn(b"\x1b[?1049l", output)
        finally:
            if slave >= 0:
                os.close(slave)
            os.close(master)

    def test_suspend_resume_and_signal_exit_restore_terminal(self) -> None:
        import fcntl
        import pty
        import termios

        executable = tui_executable()
        assert executable is not None
        master, slave = pty.openpty()
        process: subprocess.Popen[bytes] | None = None
        stopped = False
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
            environment = os.environ.copy()
            environment.update({"TERM": "xterm-256color", "LANG": "C.UTF-8"})
            process = subprocess.Popen(
                [str(executable), "tui"],
                cwd=ROOT,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=environment,
                close_fds=True,
            )
            os.close(slave)
            slave = -1
            output = bytearray()
            deadline = time.monotonic() + 10
            while b"FacMan - Factorio Manager" not in output and time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    output.extend(os.read(master, 65536))
            self.assertIn(b"\x1b[?1049h", output)

            os.write(master, b"\x1a")  # typed Ctrl+Z follows the owned suspend boundary
            stop_deadline = time.monotonic() + 5
            while time.monotonic() < stop_deadline:
                pid, status = os.waitpid(process.pid, os.WNOHANG | os.WUNTRACED)
                if pid == process.pid and os.WIFSTOPPED(status):
                    stopped = True
                    break
                time.sleep(0.05)
            self.assertTrue(stopped, "the TUI did not enter a resumable stopped state")
            os.kill(process.pid, signal.SIGCONT)
            stopped = False
            resume_deadline = time.monotonic() + 5
            while b"Terminal session resumed" not in output and time.monotonic() < resume_deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    output.extend(os.read(master, 65536))

            os.kill(process.pid, signal.SIGTERM)
            exit_deadline = time.monotonic() + 10
            while process.poll() is None and time.monotonic() < exit_deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    try:
                        output.extend(os.read(master, 65536))
                    except OSError:
                        break
            return_code = process.wait(timeout=2)
            drain_pty(master, output)
            self.assertEqual(return_code, 128 + signal.SIGTERM)
            self.assertIn(b"Terminal session resumed", output)
            self.assertGreaterEqual(output.count(b"\x1b[?1049h"), 2)
            self.assertGreaterEqual(output.count(b"\x1b[?1049l"), 2)
        finally:
            if process is not None and stopped:
                os.kill(process.pid, signal.SIGCONT)
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=2)
            if slave >= 0:
                os.close(slave)
            os.close(master)


if __name__ == "__main__":
    unittest.main()
