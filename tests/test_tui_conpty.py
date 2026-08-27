# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tui_executable() -> Path | None:
    configured = os.environ.get("FACMAN_CLI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/native-smoke/Debug/facman.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


if os.name == "nt":
    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]


    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]


    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreatePipe.argtypes = [
        ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
        ctypes.c_void_p, wintypes.DWORD,
    ]
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.CreatePseudoConsole.argtypes = [
        COORD, wintypes.HANDLE, wintypes.HANDLE, wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    kernel32.CreatePseudoConsole.restype = ctypes.c_long
    kernel32.ResizePseudoConsole.argtypes = [wintypes.HANDLE, COORD]
    kernel32.ResizePseudoConsole.restype = ctypes.c_long
    kernel32.ClosePseudoConsole.argtypes = [wintypes.HANDLE]
    kernel32.InitializeProcThreadAttributeList.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
    ]
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION),
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.PeekNamedPipe.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    kernel32.PeekNamedPipe.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class ConPtyProcess:
    PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
    EXTENDED_STARTUPINFO_PRESENT = 0x00080000
    STARTF_USESTDHANDLES = 0x00000100
    WAIT_OBJECT_0 = 0

    def __init__(self, arguments: list[str], cwd: Path) -> None:
        self._handles: list[int] = []
        self._attribute_buffer: ctypes.Array[ctypes.c_char] | None = None
        self._attribute_list: ctypes.c_void_p | None = None
        self._pseudo_console = wintypes.HANDLE()
        input_read = wintypes.HANDLE()
        self.input_write = wintypes.HANDLE()
        self.output_read = wintypes.HANDLE()
        output_write = wintypes.HANDLE()
        if not kernel32.CreatePipe(ctypes.byref(input_read), ctypes.byref(self.input_write), None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.CreatePipe(ctypes.byref(self.output_read), ctypes.byref(output_write), None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        self._handles.extend([self.input_write.value, self.output_read.value])
        # Leave ample space for the full-screen path before this test
        # deliberately shrinks the terminal below the 40x12 fallback floor.
        result = kernel32.CreatePseudoConsole(
            COORD(120, 40), input_read, output_write, 0, ctypes.byref(self._pseudo_console)
        )
        if result != 0:
            kernel32.CloseHandle(input_read)
            kernel32.CloseHandle(output_write)
            raise OSError(f"CreatePseudoConsole failed with HRESULT 0x{result & 0xFFFFFFFF:08x}")

        size = ctypes.c_size_t()
        kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        self._attribute_buffer = ctypes.create_string_buffer(size.value)
        self._attribute_list = ctypes.cast(self._attribute_buffer, ctypes.c_void_p)
        if not kernel32.InitializeProcThreadAttributeList(
            self._attribute_list, 1, 0, ctypes.byref(size)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.UpdateProcThreadAttribute(
            self._attribute_list,
            0,
            self.PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
            ctypes.c_void_p(self._pseudo_console.value),
            ctypes.sizeof(self._pseudo_console),
            None,
            None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        startup = STARTUPINFOEXW()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        # Explicit null standard handles prevent the hosting test runner's
        # console handles from being retained by CRT startup. ConPTY supplies
        # the attached console endpoints during process creation.
        startup.StartupInfo.dwFlags = self.STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput = None
        startup.StartupInfo.hStdOutput = None
        startup.StartupInfo.hStdError = None
        startup.lpAttributeList = self._attribute_list
        process = PROCESS_INFORMATION()
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))
        if not kernel32.CreateProcessW(
            None,
            command,
            None,
            None,
            False,
            self.EXTENDED_STARTUPINFO_PRESENT,
            None,
            str(cwd),
            ctypes.cast(ctypes.byref(startup), ctypes.POINTER(STARTUPINFOW)),
            ctypes.byref(process),
        ):
            kernel32.CloseHandle(input_read)
            kernel32.CloseHandle(output_write)
            raise ctypes.WinError(ctypes.get_last_error())
        # The pseudoconsole host must retain these ends until after the client
        # has been created and attached. The parent communicates only through
        # the opposite pipe ends retained on this object.
        kernel32.CloseHandle(input_read)
        kernel32.CloseHandle(output_write)
        self.process = process.hProcess
        self._handles.append(self.process)
        kernel32.CloseHandle(process.hThread)

    def write(self, value: bytes) -> None:
        written = wintypes.DWORD()
        buffer = ctypes.create_string_buffer(value)
        if not kernel32.WriteFile(
            self.input_write, buffer, len(value), ctypes.byref(written), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if written.value != len(value):
            raise OSError("short ConPTY input write")

    def read_available(self) -> bytes:
        available = wintypes.DWORD()
        if not kernel32.PeekNamedPipe(
            self.output_read, None, 0, None, ctypes.byref(available), None
        ):
            return b""
        if available.value == 0:
            return b""
        buffer = ctypes.create_string_buffer(min(available.value, 65536))
        read = wintypes.DWORD()
        if not kernel32.ReadFile(
            self.output_read, buffer, len(buffer), ctypes.byref(read), None
        ):
            return b""
        return buffer.raw[: read.value]

    def read_until(self, marker: bytes, timeout: float = 10.0) -> bytes:
        output = bytearray()
        deadline = time.monotonic() + timeout
        while marker not in output and time.monotonic() < deadline:
            output.extend(self.read_available())
            if marker in output:
                break
            time.sleep(0.02)
        return bytes(output)

    def resize(self, columns: int, rows: int) -> None:
        result = kernel32.ResizePseudoConsole(self._pseudo_console, COORD(columns, rows))
        if result != 0:
            raise OSError(f"ResizePseudoConsole failed with HRESULT 0x{result & 0xFFFFFFFF:08x}")

    def wait(self, timeout: float = 10.0) -> int:
        if kernel32.WaitForSingleObject(self.process, int(timeout * 1000)) != self.WAIT_OBJECT_0:
            raise TimeoutError("ConPTY child did not exit")
        result = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(self.process, ctypes.byref(result)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(result.value)

    def close(self) -> None:
        if self._attribute_list is not None:
            kernel32.DeleteProcThreadAttributeList(self._attribute_list)
            self._attribute_list = None
        if self._pseudo_console.value:
            kernel32.ClosePseudoConsole(self._pseudo_console)
            self._pseudo_console = wintypes.HANDLE()
        for handle in self._handles:
            if handle:
                kernel32.CloseHandle(handle)
        self._handles.clear()


@unittest.skipUnless(os.name == "nt", "not_applicable: ConPTY is Windows-only")
@unittest.skipUnless(tui_executable(), "optional: functional same-binary TUI build is not available")
class TuiConPtyTests(unittest.TestCase):
    def test_navigation_cancel_resize_fallback_and_restoration(self) -> None:
        executable = tui_executable()
        assert executable is not None
        with tempfile.TemporaryDirectory(prefix="facman-conpty-") as temporary:
            workspace = Path(temporary) / "workspace"
            inherited_overrides = {
                name: os.environ.pop(name)
                for name in ("TERM", "NO_COLOR", "FACMAN_UI", "FACMAN_SAFE_MODE")
                if name in os.environ
            }
            try:
                process = ConPtyProcess(
                    [str(executable), "tui", "--ordinary", "--workspace", str(workspace)],
                    ROOT,
                )
            finally:
                os.environ.update(inherited_overrides)
            try:
                output = bytearray(process.read_until(b"Focus: Page: Home"))
                # ConHost consumes alternate-buffer commands and emits a
                # normalized screen update. Current ConHost may retain the raw
                # home command or project it as an absolute first-column move;
                # either proves the full-screen adapter was selected while the
                # linear prompt remains absent.
                self.assertRegex(bytes(output), rb"\x1b\[(?:H|[0-9]+;1H)")
                self.assertNotIn(b"Command (1-8", output)
                process.write(b"2")
                output.extend(process.read_until(b"Focus: Page: Instances"))
                process.write(b"\x03")
                output.extend(process.read_until(b"without manufacturing an operation outcome"))
                process.resize(30, 10)
                process.write(b"\x12")
                output.extend(process.read_until(b"dimensions_below_f"))
                output.extend(process.read_until(b"Command (1-8"))
                process.write(b"q\r\n")
                self.assertEqual(process.wait(), 0)
                output.extend(process.read_available())
                self.assertIn(b"Switched to portable l", output)
                self.assertIn(b"dimensions_below_f", output)
                self.assertIn(b"Command (1-8", output)
                self.assertFalse(workspace.exists())
            finally:
                process.close()


if __name__ == "__main__":
    unittest.main()
