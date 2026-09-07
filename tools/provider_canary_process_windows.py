# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Windows-only owned job containment for the local canary harness."""
from __future__ import annotations

import ctypes as C
import os
import subprocess
import time
from ctypes import wintypes as W
from pathlib import Path


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64), ("flags", W.DWORD),
                ("minimum", C.c_size_t), ("maximum", C.c_size_t), ("active_limit", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", C.c_uint64 * 6),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]


class SecurityAttributes(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p), ("inherit", W.BOOL)]


class Accounting(C.Structure):
    _fields_ = [("times", C.c_int64 * 4), ("faults", W.DWORD), ("total", W.DWORD),
                ("active", W.DWORD), ("terminated", W.DWORD)]


class Startup(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR),
                ("title", W.LPWSTR), ("x", W.DWORD), ("y", W.DWORD), ("width", W.DWORD),
                ("height", W.DWORD), ("chars_x", W.DWORD), ("chars_y", W.DWORD),
                ("fill", W.DWORD), ("flags", W.DWORD), ("show", W.WORD),
                ("reserved_count", W.WORD), ("reserved_data", C.c_void_p),
                ("stdin", W.HANDLE), ("stdout", W.HANDLE), ("stderr", W.HANDLE)]


class StartupEx(C.Structure):
    _fields_ = [("startup", Startup), ("attributes", C.c_void_p)]


class ProcessInfo(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE),
                ("pid", W.DWORD), ("tid", W.DWORD)]


def kernel():
    if os.name != "nt":
        raise ValueError("owned canary job containment is qualified on Windows only")
    api = C.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreatePipe": ([C.POINTER(W.HANDLE), C.POINTER(W.HANDLE), C.c_void_p, W.DWORD], W.BOOL),
        "PeekNamedPipe": ([W.HANDLE, C.c_void_p, W.DWORD, C.c_void_p,
                           C.POINTER(W.DWORD), C.c_void_p], W.BOOL),
        "ReadFile": ([W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p], W.BOOL),
        "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
        "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
        "TerminateProcess": ([W.HANDLE, W.UINT], W.BOOL),
        "CloseHandle": ([W.HANDLE], W.BOOL),
        "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
        "ResumeThread": ([W.HANDLE], W.DWORD),
        "GetExitCodeProcess": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
        "GetProcessTimes": ([W.HANDLE, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p], W.BOOL),
        "InitializeProcThreadAttributeList": ([C.c_void_p, W.DWORD, W.DWORD,
                                               C.POINTER(C.c_size_t)], W.BOOL),
        "UpdateProcThreadAttribute": ([C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p,
                                        C.c_size_t, C.c_void_p, C.c_void_p], W.BOOL),
        "DeleteProcThreadAttributeList": ([C.c_void_p], None),
        "CreateProcessW": ([W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL,
                            W.DWORD, C.c_void_p, W.LPCWSTR, C.c_void_p,
                            C.POINTER(ProcessInfo)], W.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = args, result
    return api


def require(value, operation: str) -> None:
    if not value:
        raise OSError(C.get_last_error(), operation + " failed")


class Capture:
    """One bounded nonblocking pipe reader; child never receives the raw log handle."""

    def __init__(self, api, output, limit):
        self.api, self.output, self.limit = api, output, limit
        self.read, self.write = W.HANDLE(), W.HANDLE()
        self.count, self.exceeded, self.eof = 0, False, False
        security = SecurityAttributes(C.sizeof(SecurityAttributes), None, True)
        require(api.CreatePipe(C.byref(self.read), C.byref(self.write), C.byref(security), 0),
                "CreatePipe")
        try:
            os.set_handle_inheritable(self.read.value, False)
        except BaseException:
            self.close()
            raise

    def close_writer(self):
        if self.write.value:
            self.api.CloseHandle(self.write)
            self.write = W.HANDLE()

    def drain(self):
        if self.eof or self.exceeded:
            return
        available = W.DWORD()
        if not self.api.PeekNamedPipe(self.read, None, 0, None, C.byref(available), None):
            if C.get_last_error() == 109:  # ERROR_BROKEN_PIPE, all inherited writers closed
                self.eof = True
                return
            require(False, "PeekNamedPipe")
        if not available.value:
            return
        amount = min(available.value, 65536, self.limit - self.count)
        if amount:
            buffer, received = C.create_string_buffer(amount), W.DWORD()
            require(self.api.ReadFile(self.read, buffer, amount, C.byref(received), None), "ReadFile")
            self.output.write(buffer.raw[:received.value])
            self.count += received.value
        if available.value > amount and self.count == self.limit:
            self.exceeded = True

    def close(self):
        self.close_writer()
        if self.read.value:
            self.api.CloseHandle(self.read)
            self.read = W.HANDLE()


def stop_and_drain(api, job, process, assigned, captures, result, cleanup_seconds):
    """Finite cleanup; a termination request alone does not prove job completion."""
    end = time.monotonic() + cleanup_seconds
    if job:
        result["job_terminated"] = bool(api.TerminateJobObject(job, 124))
    if process.process and not assigned:
        require(api.TerminateProcess(process.process, 125), "TerminateProcess")
    while True:
        for capture in captures:
            capture.drain()
        state = api.WaitForSingleObject(process.process, 0) if process.process else 0
        if state == 0xFFFFFFFF:
            require(False, "WaitForSingleObject cleanup")
        result["primary_stopped"] = state == 0
        accounting = Accounting()
        if job:
            require(api.QueryInformationJobObject(job, 1, C.byref(accounting),
                                                  C.sizeof(accounting), None),
                    "QueryInformationJobObject")
        result["job_empty_observed"] = accounting.active == 0
        if result["primary_stopped"] and result["job_empty_observed"] and all(
                item.eof or item.exceeded for item in captures):
            break
        if time.monotonic() >= end:
            result["termination"] = "cleanup_incomplete"
            break
        time.sleep(0.005)
    if any(item.exceeded for item in captures) and result["termination"] != "cleanup_incomplete":
        result["termination"] = "output_limit"
    if process.process:
        code = W.DWORD()
        require(api.GetExitCodeProcess(process.process, C.byref(code)), "GetExitCodeProcess")
        result["exit_code"] = code.value


def run(command: list[str], cwd: Path, environment: dict[str, str], streams: tuple,
        *, seconds: float, cleanup_seconds: float, output_limit: int) -> dict:
    import msvcrt
    deadline = time.monotonic() + seconds
    api = kernel()
    process = ProcessInfo()
    job, attributes = None, None
    initialized, assigned = False, False
    captures = []
    result = {"dispatched": False, "resumed": False, "termination": "start_failed",
              "exit_code": None, "process_identity": None, "job_terminated": False,
              "primary_stopped": False, "job_empty_observed": False, "error": None}
    stdin = msvcrt.get_osfhandle(streams[0].fileno())
    try:
        job = api.CreateJobObjectW(None, None)
        require(job, "CreateJobObjectW")
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        require(api.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)),
                "SetInformationJobObject")
        for output in streams[1:]:
            captures.append(Capture(api, output, output_limit))
        handles = [stdin, *(item.write.value for item in captures)]
        size = C.c_size_t()
        api.InitializeProcThreadAttributeList(None, 1, 0, C.byref(size))
        if not 0 < size.value <= 65536:
            raise OSError("invalid process attribute allocation size")
        storage = C.create_string_buffer(size.value)
        attributes = C.cast(storage, C.c_void_p)
        require(api.InitializeProcThreadAttributeList(attributes, 1, 0, C.byref(size)),
                "InitializeProcThreadAttributeList")
        initialized = True
        inherited = (W.HANDLE * 3)(*handles)
        os.set_handle_inheritable(stdin, True)
        require(api.UpdateProcThreadAttribute(attributes, 0, 0x20002, inherited,
                                              C.sizeof(inherited), None, None),
                "UpdateProcThreadAttribute")
        startup = StartupEx()
        startup.startup.cb = C.sizeof(startup)
        startup.startup.flags = 0x101  # STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW
        startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
        startup.attributes = attributes
        arguments = C.create_unicode_buffer(subprocess.list2cmdline(command))
        env = C.create_unicode_buffer("\0".join(key + "=" + value for key, value in
                                    sorted(environment.items(), key=lambda item: item[0].upper())) + "\0\0")
        flags = 0x08000000 | 0x00000004 | 0x00080000 | 0x00000400
        require(api.CreateProcessW(command[0], arguments, None, None, True, flags, env,
                                   str(cwd), C.byref(startup), C.byref(process)), "CreateProcessW")
        result["dispatched"] = True
        for capture in captures:
            capture.close_writer()
        ticks = [C.c_uint64() for _ in range(4)]
        require(api.GetProcessTimes(process.process, *(C.byref(value) for value in ticks)),
                "GetProcessTimes")
        result["process_identity"] = {"pid": process.pid, "creation_ticks": ticks[0].value}
        require(api.AssignProcessToJobObject(job, process.process), "AssignProcessToJobObject")
        assigned = True
        result["termination"] = "timed_out"
        if time.monotonic() < deadline:
            if api.ResumeThread(process.thread) == 0xFFFFFFFF:
                require(False, "ResumeThread")
            result["resumed"] = True
            while True:
                for capture in captures:
                    capture.drain()
                if any(item.exceeded for item in captures):
                    result["termination"] = "output_limit"
                    break
                state = api.WaitForSingleObject(process.process, 10)
                if state == 0xFFFFFFFF:
                    require(False, "WaitForSingleObject")
                if state == 0:
                    result["termination"] = "completed"
                    break
                if time.monotonic() >= deadline:
                    break
    except Exception as error:
        result["termination"] = "execution_error" if result["resumed"] else "start_failed"
        result["error"] = str(error)[:4096]
    finally:
        try:
            for capture in captures:
                capture.close_writer()
            stop_and_drain(api, job, process, assigned, captures, result, cleanup_seconds)
        except Exception as error:
            result["termination"] = "cleanup_incomplete"
            result["cleanup_error"] = str(error)[:4096]
        finally:
            # Closing this retained job is the final kill-on-close fallback, never a PID search.
            if job:
                api.CloseHandle(job)
            for handle in (process.process, process.thread):
                if handle:
                    api.CloseHandle(handle)
            for capture in captures:
                capture.close()
            if initialized:
                api.DeleteProcThreadAttributeList(attributes)
            os.set_handle_inheritable(stdin, False)
    return result
