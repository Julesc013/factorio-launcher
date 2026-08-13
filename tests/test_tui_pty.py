# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import select
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
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 16, 48, 0, 0))
            os.write(master, b"\x12")  # Ctrl+R: causes a refresh and resized render
            time.sleep(0.2)
            os.write(master, b"q")
            while process.poll() is None and time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    try:
                        output.extend(os.read(master, 65536))
                    except OSError:
                        break
            self.assertEqual(process.wait(timeout=2), 0)
            self.assertIn(b"Help: use numbered pages", output)
            self.assertIn(b"\x1b[?1049l", output)
        finally:
            if slave >= 0:
                os.close(slave)
            os.close(master)


if __name__ == "__main__":
    unittest.main()
