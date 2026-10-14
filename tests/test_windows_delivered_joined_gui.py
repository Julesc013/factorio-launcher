# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Real WinForms controls and production package transport; no gallery seam."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
import hashlib
import base64
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import traceback
import unittest
import zlib
from unittest.mock import patch

import native_cli
import test_configuration_reconciliation as existing
import test_make_ready_joined as joined
import test_readiness_builtin_content as builtin
import test_local_modset_solver as modsets


class ControlGone(AssertionError):
    """A read-only enumeration raced normal modal-window disposal."""


class ControlReadFailed(AssertionError):
    """A bounded owned EDIT read failed; frames can retain partial diagnostics."""


class OwnedProcessJob:
    """Retain a kernel-owned descendant set and prove zero live descendants."""

    def __init__(self, process, backend):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, args, result in (
            ("CreateJobObjectW", [ctypes.c_void_p, wt.LPCWSTR], wt.HANDLE),
            ("AssignProcessToJobObject", [wt.HANDLE, wt.HANDLE], wt.BOOL),
            ("IsProcessInJob", [wt.HANDLE, wt.HANDLE, ctypes.POINTER(wt.BOOL)], wt.BOOL),
            ("GetProcessId", [wt.HANDLE], wt.DWORD),
            ("GetProcessTimes", [wt.HANDLE, ctypes.POINTER(wt.FILETIME),
                ctypes.POINTER(wt.FILETIME), ctypes.POINTER(wt.FILETIME),
                ctypes.POINTER(wt.FILETIME)], wt.BOOL),
            ("CreateToolhelp32Snapshot", [wt.DWORD, wt.DWORD], wt.HANDLE),
            ("OpenThread", [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE),
            ("GetProcessIdOfThread", [wt.HANDLE], wt.DWORD),
            ("ResumeThread", [wt.HANDLE], wt.DWORD),
            ("SetInformationJobObject", [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD], wt.BOOL),
            ("QueryInformationJobObject", [wt.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wt.DWORD, ctypes.POINTER(wt.DWORD)], wt.BOOL),
            ("OpenProcess", [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE),
            ("QueryFullProcessImageNameW", [wt.HANDLE, wt.DWORD, wt.LPWSTR,
                                            ctypes.POINTER(wt.DWORD)], wt.BOOL),
            ("WaitForSingleObject", [wt.HANDLE, wt.DWORD], wt.DWORD),
            ("GetExitCodeProcess", [wt.HANDLE, ctypes.POINTER(wt.DWORD)], wt.BOOL),
            ("TerminateJobObject", [wt.HANDLE, wt.UINT], wt.BOOL),
            ("CloseHandle", [wt.HANDLE], wt.BOOL),
        ):
            method = getattr(self.api, name)
            method.argtypes, method.restype = args, result
        self.job, self.primary_thread = None, None
        class Limits(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", wt.DWORD), ("min_working", ctypes.c_size_t),
                ("max_working", ctypes.c_size_t), ("active_limit", wt.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wt.DWORD), ("scheduling", wt.DWORD)]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Limits), ("io", ctypes.c_uint64 * 6),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]
        self.pid, self.backend = process.pid, backend.resolve()
        self.handles, self.records, self.closed = {}, [], False
        try:
            limits = Extended()
            limits.basic.flags = 0x2000  # Exact owned cleanup on every exception.
            self.job = self.api.CreateJobObjectW(None, None)
            if not self.job or not self.api.SetInformationJobObject(self.job, 9,
                    ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if self.api.GetProcessId(int(process._handle)) != self.pid:
                raise AssertionError("Retained suspended GUI process identity differs")
            if not self.api.AssignProcessToJobObject(self.job, int(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            membership = wt.BOOL()
            if not self.api.IsProcessInJob(int(process._handle), self.job,
                    ctypes.byref(membership)) or not membership.value:
                raise AssertionError("Suspended GUI has no exact owned-job membership")
            # Popen closes CreateProcess's original primary-thread handle. Before
            # execution there is exactly one thread; retain its supported Win32
            # handle and verify its owning PID before releasing that suspension.
            class ThreadEntry(ctypes.Structure):
                _fields_ = [("size", wt.DWORD), ("usage", wt.DWORD),
                    ("thread_id", wt.DWORD), ("owner_pid", wt.DWORD),
                    ("base_priority", wt.LONG), ("delta_priority", wt.LONG),
                    ("flags", wt.DWORD)]
            self.api.Thread32First.argtypes = [wt.HANDLE, ctypes.POINTER(ThreadEntry)]
            self.api.Thread32Next.argtypes = [wt.HANDLE, ctypes.POINTER(ThreadEntry)]
            snapshot = self.api.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
            if snapshot == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                entry, threads = ThreadEntry(), []
                entry.size = ctypes.sizeof(entry)
                available = self.api.Thread32First(snapshot, ctypes.byref(entry))
                while available:
                    if entry.owner_pid == self.pid:
                        threads.append(entry.thread_id)
                    entry.size = ctypes.sizeof(entry)
                    available = self.api.Thread32Next(snapshot, ctypes.byref(entry))
                if len(threads) != 1:
                    raise AssertionError("Suspended initial GUI thread is not unique")
            finally:
                self.api.CloseHandle(snapshot)
            self.primary_thread = self.api.OpenThread(0x2 | 0x800, False, threads[0])
            if not self.primary_thread or self.api.GetProcessIdOfThread(self.primary_thread) != self.pid:
                raise AssertionError("Retained primary thread belongs to another process")
            previous = self.api.ResumeThread(self.primary_thread)
            if previous != 1:
                raise AssertionError("Initial primary-thread suspension count differs from one")
            self.launch = dict(created_suspended=True, pid=self.pid, primary_thread_id=threads[0],
                exact_job_membership_before_resume=True, resume_previous_suspend_count=previous)
        except Exception:
            if self.primary_thread:
                self.api.CloseHandle(self.primary_thread)
            if self.job:
                self.api.CloseHandle(self.job)
            self.closed = True
            raise

    def observe(self):
        if self.closed:
            return []
        # Two DWORD counts followed by ULONG_PTR process IDs. Exact own job only.
        buffer = ctypes.create_string_buffer(4096)
        if not self.api.QueryInformationJobObject(self.job, 3, buffer, len(buffer), None):
            raise ctypes.WinError(ctypes.get_last_error())
        assigned, listed = (ctypes.c_uint32 * 2).from_buffer(buffer)
        if assigned > 128 or listed > assigned:
            raise AssertionError("Owned descendant inventory exceeds its exact bound")
        self.last_counts = dict(assigned=assigned, listed=listed)
        pids = list((ctypes.c_size_t * listed).from_buffer(buffer, 8))
        for pid in pids:
            if pid == self.pid:
                continue
            handle = self.api.OpenProcess(0x1000 | 0x100000, False, pid)
            if not handle:  # The job still proves lifetime for an already exited child.
                continue
            membership = wt.BOOL()
            if not self.api.IsProcessInJob(handle, self.job, ctypes.byref(membership)) or not membership.value:
                # PID list can race exit/reuse; never adopt a foreign opened handle.
                self.api.CloseHandle(handle)
                continue
            creation, exit_time, kernel, user = (wt.FILETIME() for _ in range(4))
            if self.api.GetProcessId(handle) != pid or not self.api.GetProcessTimes(handle,
                    ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel), ctypes.byref(user)):
                self.api.CloseHandle(handle)
                continue
            identity = str(pid) + ":" + str((creation.dwHighDateTime << 32) | creation.dwLowDateTime)
            if identity in self.handles:
                self.api.CloseHandle(handle)
                continue
            image = ctypes.create_unicode_buffer(32768)
            length = wt.DWORD(len(image))
            if not self.api.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(length)):
                self.api.CloseHandle(handle)
                continue
            observed = Path(image.value).resolve()
            console_host = Path(os.environ["SystemRoot"]) / "System32/conhost.exe"
            if observed not in (self.backend, console_host.resolve()):
                self.api.CloseHandle(handle)
                raise AssertionError("Owned GUI dispatched a foreign backend image: " + image.value)
            self.handles[identity] = handle
            self.records.append(dict(pid=pid, gui_pid=self.pid, image=image.value,
                process_identity=identity, exact_job_membership=True,
                role="packaged_backend" if observed == self.backend else "windows_console_host",
                image_sha256=hashlib.sha256(observed.read_bytes()).hexdigest()))
        return pids

    def finish(self):
        if self.closed:
            return
        try:
            live = self.observe()
            # Concurrent production query children may exit while the kernel copies
            # the ID list. Require both counts to reach zero after GUI termination.
            deadline = time.monotonic() + 5
            while (live or self.last_counts["assigned"]) and time.monotonic() < deadline:
                time.sleep(.025)
                live = self.observe()
            if live or self.last_counts["assigned"]:
                self.api.TerminateJobObject(self.job, 1)
                raise AssertionError("Owned GUI job retained live descendants; safety termination is not PASS")
            if not any(r["role"] == "packaged_backend" for r in self.records):
                raise AssertionError("No actual production backend process identity was observed")
            for record in self.records:
                handle = self.handles[record["process_identity"]]
                if self.api.WaitForSingleObject(handle, 0) != 0:
                    raise AssertionError("Observed owned backend did not exit")
                code = wt.DWORD()
                if not self.api.GetExitCodeProcess(handle, ctypes.byref(code)):
                    raise ctypes.WinError(ctypes.get_last_error())
                record["exit_code"] = code.value
                if code.value not in (0, 1):
                    raise AssertionError("Owned backend terminated abnormally")
        finally:
            for handle in self.handles.values():
                self.api.CloseHandle(handle)
            if self.primary_thread:
                self.api.CloseHandle(self.primary_thread)
            self.api.CloseHandle(self.job)
            self.closed = True


class OwnedControls:
    """Address only HWNDs belonging to the exact launched product process."""

    def __init__(self, executable: Path, consumer: Path, workspace: Path, environment: dict,
                 deadline: float):
        self.deadline = deadline
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.callback = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        for name, args in {
            "EnumWindows": [self.callback, wt.LPARAM],
            "EnumChildWindows": [wt.HWND, self.callback, wt.LPARAM],
            "GetWindowThreadProcessId": [wt.HWND, ctypes.POINTER(wt.DWORD)],
            "GetWindowTextW": [wt.HWND, wt.LPWSTR, ctypes.c_int],
            "GetClassNameW": [wt.HWND, wt.LPWSTR, ctypes.c_int],
            "GetParent": [wt.HWND], "GetDlgCtrlID": [wt.HWND],
            "IsWindowEnabled": [wt.HWND], "IsWindowVisible": [wt.HWND],
            "GetAncestor": [wt.HWND, wt.UINT],
            "GetForegroundWindow": [],
            "GetWindowRect": [wt.HWND, ctypes.POINTER(wt.RECT)],
            "PostMessageW": [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM],
            "SetWindowPos": [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, wt.UINT],
            "SendMessageTimeoutW": [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM,
                                    wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_size_t)],
        }.items():
            getattr(self.api, name).argtypes = args
        self.api.GetParent.restype = wt.HWND
        self.api.GetAncestor.restype = wt.HWND
        self.api.GetForegroundWindow.restype = wt.HWND
        self.api.SendMessageTimeoutW.restype = ctypes.c_size_t
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        environment = dict(environment, FACMAN_WORKSPACE=str(workspace))
        self.process = subprocess.Popen([str(executable)], cwd=consumer, env=environment,
            startupinfo=startup, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=0x4)  # Documented CREATE_SUSPENDED; assign the job before execution.
        try:
            self.job = OwnedProcessJob(self.process, executable.parent / "facman.exe")
        except Exception:
            self.process.kill()
            self.process.communicate(timeout=10)
            raise
        self.events = []
        self.terminal = None

    def require_owned(self, hwnd):
        pid = wt.DWORD()
        self.api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if self.process.poll() is not None:
            raise AssertionError("Owned GUI process exited unexpectedly")
        if pid.value != self.process.pid:
            raise ControlGone("Control no longer belongs to the live owned GUI")

    def text(self, hwnd, class_name=False):
        self.require_owned(hwnd)
        value = ctypes.create_unicode_buffer(16384)
        if not class_name and "COMBOBOX" in self.text(hwnd, True).upper():
            index = self.send(hwnd, 0x147)  # CB_GETCURSEL
            if index == ctypes.c_size_t(-1).value:
                return ""
            length = self.send(hwnd, 0x149, index)  # CB_GETLBTEXTLEN
            if length >= len(value):
                raise AssertionError("Owned combo text exceeds the evidence bound")
            self.send(hwnd, 0x148, index, ctypes.addressof(value))  # CB_GETLBTEXT
            return value.value
        if not class_name and "EDIT" in self.text(hwnd, True).upper():
            # GetWindowText reads another process's cached caption, which can
            # retain the constructor text after the actual edit contents change.
            try:
                length = self.send(hwnd, 0xD, len(value), ctypes.addressof(value))  # WM_GETTEXT
            except ControlGone:
                raise
            except AssertionError as error:
                self.require_owned(hwnd)  # Disposal must remain ControlGone.
                raise ControlReadFailed("Bounded owned EDIT text read failed") from error
            self.require_owned(hwnd)  # Never accept text after HWND disposal/reuse.
            if length >= len(value) - 1:
                raise ControlReadFailed("Owned edit text exceeds the evidence bound")
            return value.value
        method = self.api.GetClassNameW if class_name else self.api.GetWindowTextW
        method(hwnd, value, len(value))
        return value.value

    def enumerate(self, parent=None, observe=True):
        if observe:
            self.job.observe()
        result = []
        @self.callback
        def collect(hwnd, unused):
            pid = wt.DWORD()
            self.api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.process.pid:
                result.append(int(hwnd))
            return True
        if parent is None:
            self.api.EnumWindows(collect, 0)
            current = []
            for hwnd in result:
                try:
                    self.require_owned(hwnd)
                except ControlGone:
                    continue
                # No activation, global keyboard input or user-window movement.
                self.api.SetWindowPos(hwnd, None, -20000, -20000, 0, 0, 0x15)
                current.append(hwnd)
            result = current
        else:
            self.require_owned(parent)
            self.api.EnumChildWindows(parent, collect, 0)
        return result

    def frame(self, hwnd, stage):
        controls = []
        result = dict(stage=stage, pid=self.process.pid, hwnd=hwnd, controls=controls)
        try:
            result["title"] = self.text(hwnd)
            children = self.enumerate(hwnd)
        except ControlGone:
            result["control_gone"] = True
            self.events.append(result)
            return result
        for child in children:
            try:
                controls.append(dict(hwnd=child, text=self.text(child),
                    class_name=self.text(child, True), **self.control_state(child)))
            except ControlGone:
                controls.append(dict(hwnd=child, control_gone=True))
            except ControlReadFailed as error:
                controls.append(dict(hwnd=child, read_error=str(error)))
        self.events.append(result)
        return result

    def control_state(self, hwnd):
        self.require_owned(hwnd)
        return dict(parent_hwnd=self.api.GetParent(hwnd),
            root_hwnd=self.api.GetAncestor(hwnd, 2),
            control_id=self.api.GetDlgCtrlID(hwnd),
            enabled=bool(self.api.IsWindowEnabled(hwnd)),
            visible=bool(self.api.IsWindowVisible(hwnd)),
            observed_at=time.monotonic())

    def ancestors(self, hwnd):
        root = self.api.GetAncestor(hwnd, 2)
        self.require_owned(root)
        current, result = hwnd, []
        for unused in range(16):
            result.append(dict(hwnd=current, **self.control_state(current)))
            if current == root:
                return result
            current = self.api.GetParent(current)
            if not current:
                break
        raise AssertionError("Owned control ancestors did not terminate at its exact root")

    def show_main_offscreen(self, main):
        self.require_owned(main)
        class_name = self.text(main, True)
        if (self.text(main) != "FacMan" or not class_name.startswith("WindowsForms10.Window.")
                or self.api.GetAncestor(main, 2) != main):
            raise AssertionError("Passive show target is not the exact owned FacMan main form")
        rectangle = wt.RECT()
        if not self.api.GetWindowRect(main, ctypes.byref(rectangle)):
            raise ctypes.WinError(ctypes.get_last_error())
        if rectangle.right >= -10000 or rectangle.bottom >= -10000:
            raise AssertionError("Owned main form must be offscreen before it is shown")
        foreground = self.api.GetForegroundWindow()
        # Preserve size/Z order and prohibit activation. Only the verified main
        # form is shown; other enumerated helper windows keep their show state.
        if not self.api.SetWindowPos(main, None, -20000, -20000, 0, 0, 0x55):
            raise ctypes.WinError(ctypes.get_last_error())
        after = self.api.GetForegroundWindow()
        self.events.append(dict(stage="owned main shown offscreen", pid=self.process.pid,
            hwnd=main, class_name=class_name, flags=0x55,
            offscreen_rectangle=dict(left=rectangle.left, top=rectangle.top,
                right=rectangle.right, bottom=rectangle.bottom),
            foreground_before=foreground, foreground_after=after,
            foreground_unchanged=foreground == after, **self.control_state(main)))

    def wait(self, predicate, description, seconds=35):
        deadline = min(time.monotonic() + seconds, self.deadline)
        while time.monotonic() < deadline and self.process.poll() is None:
            try:
                value = predicate()
            except ControlGone:
                value = None
            if value:
                return value
            time.sleep(.025)
        for hwnd in self.enumerate(observe=False):
            try:
                self.frame(hwnd, "timeout: " + description)
            except ControlGone:
                self.events.append(dict(stage="timeout: " + description,
                    pid=self.process.pid, hwnd=hwnd, control_gone=True))
        for event in reversed(self.events):
            if event["stage"] == "BM_CLICK":
                try:
                    state = self.control_state(event["hwnd"])
                except ControlGone:
                    state = dict(control_gone=True)
                self.events.append(dict(stage="timeout: last click target",
                    pid=self.process.pid, hwnd=event["hwnd"], **state))
                break
        raise AssertionError("Owned GUI did not reach " + description)

    def window(self, title, control_text=None):
        def find():
            for hwnd in self.enumerate():
                if self.text(hwnd) == title and (control_text is None or any(
                    control_text in self.text(c) for c in self.enumerate(hwnd))):
                    return hwnd
        return self.wait(find, title + " / " + str(control_text))

    def control(self, window, label):
        return self.wait(lambda: next((h for h in self.enumerate(window)
            if self.text(h).replace("&", "") == label and all(
                state["visible"] and state["enabled"] for state in self.ancestors(h))), None), label)

    def click(self, hwnd):
        self.require_owned(hwnd)
        if "BUTTON" not in self.text(hwnd, True).upper():
            raise AssertionError("BM_CLICK target is not a native button")
        ancestors = self.ancestors(hwnd)
        if not all(state["visible"] and state["enabled"] for state in ancestors):
            raise AssertionError("BM_CLICK requires visible and enabled owned control ancestors")
        event = dict(stage="BM_CLICK", pid=self.process.pid, hwnd=hwnd,
                     text=self.text(hwnd), ancestors=ancestors, **self.control_state(hwnd))
        self.events.append(event)
        if not self.api.PostMessageW(hwnd, 0xF5, 0, 0):
            event["post_succeeded"] = False
            raise ctypes.WinError(ctypes.get_last_error())
        event.update(post_succeeded=True, posted_at=time.monotonic())

    def send(self, hwnd, message, wparam=0, lparam=0):
        self.require_owned(hwnd)
        result = ctypes.c_size_t()
        if not self.api.SendMessageTimeoutW(hwnd, message, wparam, lparam,
                                           2, 2000, ctypes.byref(result)):
            raise AssertionError("Bounded owned-control message failed")
        return result.value

    def select(self, hwnd, index, value):
        self.require_owned(hwnd)
        self.send(hwnd, 0x14E, index)  # CB_SETCURSEL
        if self.text(hwnd) != value:
            raise AssertionError("Actual typed selection differs from reviewed value")
        parent = self.api.GetParent(hwnd)
        self.require_owned(parent)
        identifier = self.api.GetDlgCtrlID(hwnd)
        # The ordinary event can start package hashing before its first await.
        # Queue the owned notification; observe its resulting revision below.
        if not self.api.PostMessageW(parent, 0x111, (1 << 16) | (identifier & 0xFFFF), hwnd):
            raise ctypes.WinError(ctypes.get_last_error())
        self.events.append(dict(stage="CBN_SELCHANGE", pid=self.process.pid,
                                hwnd=hwnd, value=value))

    def inputs(self, main):
        self.click(self.control(main, "Make Ready with current settings"))
        dialog = self.window("Make Ready with current settings", "Continue")
        combos = [h for h in self.enumerate(dialog) if "COMBOBOX" in self.text(h, True).upper()]
        actual = [self.text(h) for h in combos]
        if actual != ["main", "fixture", "gui", "selected.zip"]:
            raise AssertionError("Actual form lost exact selected-save inputs: " + repr(actual))
        for hwnd, value in zip(combos, actual):
            self.select(hwnd, 0, value)
        self.frame(dialog, "typed semantic inputs")
        return dialog

    def revision(self, main):
        return next((self.text(h) for h in self.enumerate(main)
                     if self.text(h).startswith("Readiness:")), "")

    def selected_observation(self, main):
        self.show_main_offscreen(main)
        original = self.wait(lambda: self.revision(main) if "revision 0" not in
            self.revision(main) else None, "actual backend revision")
        observation = next(h for h in self.enumerate(main) if
            "COMBOBOX" in self.text(h, True).upper() and self.text(h) == "Menu")
        self.select(observation, 1, "Selected Save")
        self.wait(lambda: self.api.IsWindowEnabled(observation) and
            self.revision(main) != original and "revision 0" not in self.revision(main),
            "actual selected-save backend replacement revision")
        self.frame(main, "selected-save observation completed")

    def finish(self):
        if self.terminal is not None:
            return
        # Cleanup must still work if descendant identity observation caused the
        # original failure. Never let that failure retain the owned GUI/job.
        for hwnd in self.enumerate(observe=False):
            try:
                if self.text(hwnd) == "FacMan":
                    self.require_owned(hwnd)
                    self.api.PostMessageW(hwnd, 0x10, 0, 0)
            except ControlGone:
                continue
        safety = False
        try:
            out, err = self.process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            safety = True
            self.process.kill()
            out, err = self.process.communicate(timeout=10)
        self.terminal = dict(pid=self.process.pid, exit_code=self.process.returncode,
            stdout=out.decode("utf-8", errors="strict"),
            stderr=err.decode("utf-8", errors="strict"), safety_termination=safety)
        self.job.finish()
        self.terminal.update(owned_job_active_processes=0, backend_processes=self.job.records,
                             launch=self.job.launch)
        if safety or self.process.returncode != 0 or out or err:
            raise AssertionError("GUI must drain and exit normally: " + repr(self.terminal))


@unittest.skipUnless(os.name == "nt", "unsupported: native WinForms requires Windows")
class WindowsDeliveredJoinedGuiTests(unittest.TestCase):
    query = joined.JoinedMakeReadyTests.query
    preserved_inputs = joined.JoinedMakeReadyTests.preserved_inputs
    journals = joined.JoinedMakeReadyTests.journals
    assert_effects = joined.JoinedMakeReadyTests.assert_effects

    def test_actual_joined_controls_dispatch_production_packaged_backend(self):
        started = time.monotonic()
        candidate = os.environ.get("FACMAN_DELIVERED_GUI_PACKAGE")
        consumer = os.environ.get("FACMAN_DELIVERED_GUI_CONSUMER")
        qualification = "original portable file closure reconstructed from produced self-setup payload"
        if not candidate and not consumer:
            build = Path(os.environ.get("FACMAN_WINFORMS_SHARED_BUILD_ROOT",
                native_cli.ROOT / "build/winforms-shared")).resolve()
            if not (build / "CMakeCache.txt").is_file():
                self.skipTest("required_blocked: matching Windows shared native build/candidate absent")
            # Existing required Windows Python CI already built the native Release
            # product and WinForms. Assemble once with the ordinary package factory;
            # clean source and exact build/provider checks remain mandatory.
            from tools import package_build
            campaign = Path(tempfile.mkdtemp(prefix="fmg-"))
            package = package_build.build_profile(profile_id="windows_legacy_winforms_x64",
                out_root=campaign / "p", build_root=build, dist_root=None, allow_dirty=False)
            candidate = str(package)
            consumer = str(campaign / "c")
            Path(consumer).mkdir()
            qualification = "factory-produced Windows legacy WinForms portable file closure"
        self.assertTrue(candidate and consumer, "Candidate and owned consumer are both required")
        package, consumer = Path(candidate).resolve(), Path(consumer).resolve()
        self.assertFalse(consumer.is_relative_to(native_cli.ROOT))
        self.assertTrue(consumer.is_dir())
        gui, backend = package / "bin/FacMan.WinForms.exe", package / "bin/facman.exe"
        self.assertTrue(gui.is_file() and backend.is_file())
        hashes = dict(line.split("  ", 1)[::-1] for line in
                      (package / "manifest/hashes.sha256").read_text().splitlines())
        manifest_digest = hashlib.sha256((package / "manifest/hashes.sha256").read_bytes()).hexdigest()
        actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
        self.assertEqual(set(hashes) | {"manifest/hashes.sha256"}, actual)
        for name, digest in hashes.items():
            self.assertEqual(digest, hashlib.sha256((package / name).read_bytes()).hexdigest(), name)
        build_info = json.loads((package / "manifest/build_info.v1.json").read_bytes())
        self.assertEqual("windows_legacy_winforms_x64", build_info["profile_id"])
        self.assertFalse(build_info["source_dirty"])
        # Only this admitted package's existing files. Bytes and closure are checked
        # again after the actual product sessions; no manifest is rewritten.
        for name in actual:
            os.chmod(package / name, stat.S_IREAD)
        environment = {k: v for k, v in os.environ.items() if not k.startswith("FACMAN_")}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PATH"] = ""
        custody = consumer / "evidence"
        custody.mkdir(exist_ok=True)
        files = {}
        stream_bytes = 0
        def inventory(path):
            self.assertLess(time.monotonic() - started, 300)
            result = {}
            for p in sorted(path.rglob("*")):
                if p.is_file():
                    data = p.read_bytes()
                    digest = hashlib.sha256(data).hexdigest()
                    files.setdefault(digest, data)
                    self.assertLess(sum(map(len, files.values())), 8 * 1024 * 1024)
                    result[p.relative_to(path).as_posix()] = dict(sha256=digest,
                        size_bytes=len(data), file_identity=joined.file_identity(p))
            return result
        calls, sessions, snapshots = [], [], []
        real_run = subprocess.run
        def delivered_run(args, **kwargs):
            nonlocal stream_bytes
            self.assertLess(time.monotonic() - started, 300)
            self.assertLess(len(calls), 64)
            self.assertEqual(str(backend), args[0])
            kwargs.update(cwd=consumer, env=environment, timeout=30)
            response = real_run(args, **kwargs)
            stream_bytes += sum(len(s.encode("utf-8")) for s in
                                (response.stdout, response.stderr) if s is not None)
            self.assertLess(stream_bytes, 4 * 1024 * 1024)
            calls.append(dict(argv=list(args), cwd=str(consumer), exit_code=response.returncode,
                              stdout=response.stdout, stderr=response.stderr))
            return response
        fixture = consumer / "fixture-install-source"
        self.assertFalse(fixture.exists())
        import shutil
        shutil.copytree(modsets.FIXTURE_INSTALL, fixture)
        result = dict(schema="facman.windows_delivered_joined_gui.v1", package=str(package),
            gui_sha256=hashes["bin/FacMan.WinForms.exe"], backend_sha256=hashes["bin/facman.exe"],
            qualification=qualification, build_info=build_info,
            environment=dict(PATH="", source_backend_provider_overrides=[],
                workspace=str(consumer / "workspace")), package_file_count=len(actual),
            calls=calls, sessions=sessions, snapshots=snapshots, result="FAIL")
        active = None
        try:
            with patch.dict(os.environ, FACMAN_CLI_EXE=str(backend)), \
                 patch.object(native_cli, "ROOT", consumer), \
                 patch.object(subprocess, "run", delivered_run), \
                 patch.object(builtin, "FIXTURE_INSTALL", fixture):
                workspace = consumer / "workspace"
                self.assertFalse(workspace.exists())
                instance, original, expected = existing.ExistingConfigurationTests.prepare(
                    self, workspace, "load_save", raw=True, crlf=True)
                config = instance / "config/config.ini"
                identity = joined.file_identity(config)
                preserved = self.preserved_inputs(instance)
                snapshots.append(dict(stage="prepared fixture", inventory=inventory(workspace)))
                active = OwnedControls(gui, consumer, workspace, environment, started + 300)
                sessions.append(dict(events=active.events))
                main = active.window("FacMan")
                active.selected_observation(main)
                frozen = inventory(workspace)
                dialog = active.inputs(main)
                active.click(active.control(dialog, "Cancel"))
                active.wait(lambda: dialog not in active.enumerate(), "input cancellation")
                self.assertEqual(frozen, inventory(workspace))
                dialog = active.inputs(main)
                active.click(active.control(dialog, "Continue"))
                confirm = active.window("Make Ready with current settings", "Apply Make Ready")
                active.frame(confirm, "explicit confirmation cancelled")
                active.click(active.control(confirm, "Cancel"))
                active.wait(lambda: confirm not in active.enumerate(), "confirmation cancellation")
                self.assertEqual(frozen, inventory(workspace))
                snapshots.append(dict(stage="both cancellation routes unchanged", inventory=frozen))
                dialog = active.inputs(main)
                active.click(active.control(dialog, "Continue"))
                confirm = active.window("Make Ready with current settings", "Apply Make Ready")
                metadata = workspace / "fixture-install/data/base/info.json"
                metadata_original = metadata.read_bytes()
                metadata.write_bytes(metadata_original + b"\n")
                stale = inventory(workspace)
                active.frame(confirm, "stale confirmation")
                active.click(active.control(confirm, "OK"))
                refusal = active.window("Make Ready with current settings refused", "stale_snapshot_revision")
                active.frame(refusal, "actual backend stale refusal")
                self.assertEqual(stale, inventory(workspace))
                active.click(active.control(refusal, "OK"))
                active.finish()
                sessions[-1]["terminal"] = active.terminal
                metadata.write_bytes(metadata_original)
                snapshots.append(dict(stage="stale refused before effects", inventory=stale))
                active = OwnedControls(gui, consumer, workspace, environment, started + 300)
                sessions.append(dict(events=active.events))
                main = active.window("FacMan")
                active.selected_observation(main)
                before = self.query(workspace, "instances", "load_save")
                before_files = inventory(workspace)
                dialog = active.inputs(main)
                active.click(active.control(dialog, "Continue"))
                confirm = active.window("Make Ready with current settings", "Apply Make Ready")
                active.frame(confirm, "explicit confirmation accepted")
                active.click(active.control(confirm, "OK"))
                final = active.window("Make Ready with current settings", "Review the remaining readiness checks")
                active.frame(final, "actual completed joined result")
                receipts = [json.loads(p.read_bytes()) for p in
                            (workspace / ".facman/action-receipts-v2").glob("*.v2.json")]
                matching = [r for r in receipts if r["action_id"] == "readiness.prepare_joined"]
                self.assertEqual(1, len(matching))
                outcome = json.loads(matching[0]["result_json"])
                self.assertEqual("completed", outcome["outcome"])
                self.assert_effects(workspace, outcome,
                    ["readiness.prepare_configuration", "readiness.prepare_selected_save"])
                request = json.loads(matching[0]["request_json"])
                self.assertEqual(before["revision"], request["expected_snapshot_revision"])
                self.assertEqual("load_save", request["launch_intent"])
                self.assertEqual("selected.zip", request["save"])
                self.assertEqual("explicit", request["confirmation"])
                self.assertEqual(expected, config.read_bytes())
                self.assertEqual(identity, joined.file_identity(config))
                self.assertEqual(preserved, self.preserved_inputs(instance))
                current = self.query(workspace, "instances", "load_save")
                self.assertEqual("satisfied", current["readiness"]["selected_save"]["state"])
                self.assertFalse(current["readiness"]["execution_available"])
                after_files = inventory(workspace)
                effects = {"instances/main/config/config.ini",
                           "instances/main/metadata/save-refs/selected.zip.save-ref.v1.json"}
                for name, observed in before_files.items():
                    if name not in effects:
                        self.assertEqual(observed, after_files[name], "Preserved original input: " + name)
                new = set(after_files) - set(before_files)
                allowed = effects | {".facman/action-receipts-v2/workspace-admission.v1.json"}
                allowed.update("transactions/" + c["transaction_id"] + ".transaction.v1.json"
                    for c in outcome["action_payload"]["completed_components"])
                allowed.add(".facman/action-receipts-v2/" + matching[0]["key_digest"] + ".v2.json")
                self.assertEqual(new, new & allowed)
                snapshots.append(dict(stage="joined completion independently verified", inventory=after_files))
                result.update(receipt=matching[0], outcome=outcome, observation=current)
                active.click(active.control(final, "OK"))
                active.finish()
                sessions[-1]["terminal"] = active.terminal
                self.assertEqual(actual, {p.relative_to(package).as_posix() for p in
                                          package.rglob("*") if p.is_file()})
                for name, digest in hashes.items():
                    self.assertEqual(digest, hashlib.sha256((package / name).read_bytes()).hexdigest(), name)
                self.assertEqual(manifest_digest,
                    hashlib.sha256((package / "manifest/hashes.sha256").read_bytes()).hexdigest())
                result["package_closure_unchanged"] = True
                result["result"] = "PASS"
        except Exception:
            result.update(result="FAIL", exception=traceback.format_exc())
            raise
        finally:
            try:
                if active is not None:
                    try:
                        active.finish()
                    except Exception:
                        result.update(result="FAIL", cleanup_exception=traceback.format_exc())
                        raise
                    finally:
                        sessions[-1]["terminal"] = active.terminal
                        sessions[-1]["observed_backend_processes"] = active.job.records
                        sessions[-1]["launch"] = active.job.launch
            finally:
                objects = custody / "objects"
                objects.mkdir(exist_ok=True)
                for digest, data in files.items():
                    (objects / digest).write_bytes(data)
                result["elapsed_seconds"] = time.monotonic() - started
                record = json.dumps(result, indent=2).encode("utf-8")
                self.assertLess(len(record), 4 * 1024 * 1024)
                self.assertFalse((custody / "result.json").exists(), "Evidence cannot overwrite an earlier run")
                (custody / "result.json").write_bytes(record)
                if result["result"] in ("PASS", "FAIL"):
                    raw = {"result.json": record, **{"objects/" + k: v for k, v in files.items()}}
                    manifest = {name: dict(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                        bytes_base64=base64.b64encode(data).decode("ascii")) for name, data in raw.items()}
                    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    self.assertLess(len(canonical), 12 * 1024 * 1024)
                    compressed = zlib.compress(canonical, 9)
                    encoded = base64.b64encode(compressed).decode("ascii")
                    self.assertLess(len(encoded), 512 * 1024)
                    print("delivered-windows-gui-custody " + json.dumps(dict(
                        schema="facman.windows_delivered_gui_custody.v1", file_count=len(raw),
                        canonical_sha256=hashlib.sha256(canonical).hexdigest(),
                        compressed_sha256=hashlib.sha256(compressed).hexdigest(),
                        payload_base64=encoded), sort_keys=True))
                    print("delivered-windows-gui-result " + json.dumps(dict(result=result["result"],
                        qualification=qualification, source=build_info["source_commit"],
                        gui_sha256=result["gui_sha256"], backend_sha256=result["backend_sha256"],
                        result_sha256=hashlib.sha256(record).hexdigest(),
                        custody_sha256=hashlib.sha256(canonical).hexdigest()), sort_keys=True))
        # The completed GUI oracle keeps its original custody and budget. Exercise
        # the three portable-environment journeys against this same factory output
        # with separate call, ownership, time and whole-scenario custody bounds.
        import delivered_environment_reconstruction as reconstruction
        for scenario in reconstruction.SCENARIOS:
            reconstruction.exercise(self, scenario, package=package, consumer=consumer,
                fixture=fixture, evidence_root=custody,
                binding=dict(schema="facman.windows_delivered_environment_result.v1",
                    qualification=qualification, build_info=build_info,
                    backend_sha256=hashes["bin/facman.exe"],
                    closure_sha256=manifest_digest, package_readonly=True))
