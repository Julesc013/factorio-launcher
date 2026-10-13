# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Darwin ordinary existing-INI owner proofs with OS-readable metadata oracles."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from native_cli import ROOT, facman_executable, invoke_machine
import test_configuration_reconciliation as common
from test_local_modset_solver import snapshot
from test_presentation_profile_preparation import factorio_validator


PHASES = ('rewrite_after_manifest', 'rewrite_before_admission', 'rewrite_after_admission',
          'rewrite_before_write', 'rewrite_after_prefix', 'rewrite_after_write',
          'rewrite_after_truncate', 'rewrite_after_verification_checkpoint',
          'rewrite_before_finalization', 'rewrite_after_audit', 'rewrite_after_finalization')


# Python documents os.*xattr as Linux-only. The explicit LP64 Darwin bindings
# below follow Apple's headers, including INODE64 symbol selection on Intel:
# https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/sys/stat.h
# https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/sys/fcntl.h
# https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/sys/xattr.h
# https://raw.githubusercontent.com/apple-oss-distributions/Libc/main/include/sys/acl.h
# https://docs.python.org/3/library/os.html#linux-extended-attributes
class Timespec(ctypes.Structure):
    _fields_ = [('seconds', ctypes.c_int64), ('nanoseconds', ctypes.c_int64)]


class DarwinStat64(ctypes.Structure):
    _fields_ = [('device', ctypes.c_int32), ('mode', ctypes.c_uint16), ('links', ctypes.c_uint16),
                ('inode', ctypes.c_uint64), ('uid', ctypes.c_uint32), ('gid', ctypes.c_uint32),
                ('rdev', ctypes.c_int32), ('atime', Timespec), ('mtime', Timespec),
                ('ctime', Timespec), ('birthtime', Timespec), ('size', ctypes.c_int64),
                ('blocks', ctypes.c_int64), ('blksize', ctypes.c_int32), ('flags', ctypes.c_uint32),
                ('generation', ctypes.c_uint32), ('spare', ctypes.c_int32),
                ('qspare', ctypes.c_int64 * 2)]


class DarwinMetadata:
    def __init__(self):
        assert sys.platform == 'darwin'
        assert platform.machine() in ('x86_64', 'arm64'), 'Darwin oracle requires the documented LP64 ABI'
        assert ctypes.sizeof(ctypes.c_void_p) == 8 and ctypes.sizeof(DarwinStat64) == 144
        assert DarwinStat64.birthtime.offset == 80 and DarwinStat64.flags.offset == 116
        self.lib = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
        suffix = '$INODE64' if platform.machine() == 'x86_64' else ''
        self.statx = getattr(self.lib, 'fstatx_np' + suffix)
        self.statx.argtypes = [ctypes.c_int, ctypes.POINTER(DarwinStat64), ctypes.c_void_p]
        self.statx.restype = ctypes.c_int
        signatures = {
            'filesec_init': ([], ctypes.c_void_p),
            'filesec_free': ([ctypes.c_void_p], None),
            'filesec_query_property': ([ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)], ctypes.c_int),
            'filesec_get_property': ([ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p], ctypes.c_int),
            'acl_size': ([ctypes.c_void_p], ctypes.c_ssize_t),
            'acl_copy_ext': ([ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ssize_t], ctypes.c_ssize_t),
            'acl_free': ([ctypes.c_void_p], ctypes.c_int),
            'flistxattr': ([ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int], ctypes.c_ssize_t),
            'fgetxattr': ([ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t,
                           ctypes.c_uint32, ctypes.c_int], ctypes.c_ssize_t),
            'fsetxattr': ([ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t,
                           ctypes.c_uint32, ctypes.c_int], ctypes.c_int),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.lib, name); function.argtypes = args; function.restype = result

    def check(self, result: int, path: Path) -> int:
        if result < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(path))
        return result

    def attributes(self, fd: int, path: Path) -> tuple:
        count = self.check(self.lib.flistxattr(fd, None, 0, 0), path)
        assert count <= 1024 * 1024, 'Oracle xattr list is unexpectedly large'
        raw = ctypes.create_string_buffer(max(1, count))
        assert self.check(self.lib.flistxattr(fd, raw, count, 0), path) == count
        encoded = raw.raw[:count]
        assert not encoded or encoded.endswith(b'\0')
        names = sorted(encoded[:-1].split(b'\0')) if encoded else []
        assert len(set(names)) == len(names) and all(names)
        return tuple((name, self.attribute(fd, path, name)) for name in names)

    def attribute(self, fd: int, path: Path, name: bytes) -> bytes:
        count = self.check(self.lib.fgetxattr(fd, name, None, 0, 0, 0), path)
        assert count <= 1024 * 1024, 'Oracle xattr is unexpectedly large'
        value = ctypes.create_string_buffer(max(1, count))
        assert self.check(self.lib.fgetxattr(fd, name, value, count, 0, 0), path) == count
        return value.raw[:count]

    def metadata(self, fd: int, path: Path) -> tuple:
        security = self.lib.filesec_init()
        if not security: self.check(-1, path)
        acl = ctypes.c_void_p()
        try:
            native = DarwinStat64()
            self.check(self.statx(fd, ctypes.byref(native), security), path)
            # Cross-check the binding against Python before trusting birthtime/ACL.
            info = os.fstat(fd)
            assert (native.device, native.inode, native.mode, native.links, native.uid, native.gid,
                    native.size, native.flags) == (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                                                   info.st_uid, info.st_gid, info.st_size, info.st_flags)
            assert native.mtime.seconds * 10**9 + native.mtime.nanoseconds == info.st_mtime_ns
            present = ctypes.c_int()
            self.check(self.lib.filesec_query_property(security, 5, ctypes.byref(present)), path)  # FILESEC_ACL
            # Successful queries return zero or the raw property-validity bit,
            # not a normalized boolean. Only zero establishes ACL absence.
            # https://raw.githubusercontent.com/apple-oss-distributions/Libc/71bbe350ab79eef58113991d817ccc6165061a64/gen/filesec.c
            external = None  # Verified absence after a successful statx/security read.
            if present.value:
                self.check(self.lib.filesec_get_property(security, 5, ctypes.byref(acl)), path)
                assert acl.value
                count = self.check(self.lib.acl_size(acl), path)
                assert 0 < count <= 65536
                value = ctypes.create_string_buffer(count)
                assert self.check(self.lib.acl_copy_ext(value, acl, count), path) == count
                external = value.raw
            birthtime = (native.birthtime.seconds, native.birthtime.nanoseconds)
            assert 0 <= birthtime[1] < 10**9
            return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                    birthtime, info.st_flags, self.attributes(fd, path), external)
        finally:
            if acl.value: self.lib.acl_free(acl)
            self.lib.filesec_free(security)


_api = None


def darwin() -> DarwinMetadata:
    global _api
    if _api is None: _api = DarwinMetadata()
    return _api


def metadata(path: Path) -> tuple:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try: return darwin().metadata(fd, path)
    finally: os.close(fd)


def set_xattr(path: Path, name: str, value: bytes) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        assert stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid(), 'Setter is limited to test-owned regular files'
        data = ctypes.create_string_buffer(value)
        darwin().check(darwin().lib.fsetxattr(fd, name.encode(), data, len(value), 0, 0), path)
    finally: os.close(fd)


def get_xattr(path: Path, name: str) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try: return darwin().attribute(fd, path, name.encode())
    finally: os.close(fd)


def set_owned_acl(path: Path, present: bool, permissions: str = 'read') -> None:
    # Apple's chmod interface is restricted to this test-owned synthetic file.
    # https://raw.githubusercontent.com/apple-oss-distributions/file_cmds/main/chmod/chmod.1
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
    subprocess.run(['/bin/chmod', '-N', str(path)], check=True, capture_output=True)
    if present:
        subprocess.run(['/bin/chmod', '+a', 'group:everyone allow ' + permissions, str(path)],
                       check=True, capture_output=True)
    assert (metadata(path)[-1] is not None) == present


@unittest.skipUnless(sys.platform == 'darwin', 'unsupported: macOS existing-INI owner qualification')
class MacOSExistingConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('FACMAN_CLI_EXE'):
            raise AssertionError('Mac owner qualification requires an explicit candidate FACMAN_CLI_EXE')
        facman_executable()  # Missing candidate binaries fail; never become an unknown skip.
        darwin()  # Validate the documented ABI before creating any fixture.

    # Share fixture construction and transport assertions, never Windows test bodies.
    prepare = common.ExistingConfigurationTests.prepare
    query = common.ExistingConfigurationTests.query
    args = common.ExistingConfigurationTests.args
    journal = common.ExistingConfigurationTests.journal
    recover = common.ExistingConfigurationTests.recover
    preserved = common.ExistingConfigurationTests.preserved

    def configure_metadata(self, target: Path, acl_present: bool) -> tuple:
        target.chmod(0o640)
        os.chflags(target, stat.UF_NODUMP)
        set_xattr(target, 'user.facman-first', b'\0\xff\x80\r\n')
        set_xattr(target, 'user.facman-second', b'exact unrelated bytes')
        set_xattr(target, 'user.facman-empty', b'')
        set_owned_acl(target, present=acl_present)
        result = metadata(target)
        self.assertEqual(acl_present, result[-1] is not None)
        self.assertEqual(stat.UF_NODUMP, result[6])
        self.assertEqual(b'\0\xff\x80\r\n', get_xattr(target, 'user.facman-first'))
        return result

    def interrupted(self, workspace: Path, phase: str, intent: str = 'menu', scope: str = 'instances') -> tuple[Path, dict]:
        code, out, err = invoke_machine(self.args(workspace, self.query(workspace, scope, intent)['revision'],
                                                scope=scope, intent=intent),
                                        env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT=phase))
        self.assertEqual((74, ''), (code, err), out)
        return self.journal(workspace)

    def recover_args(self, workspace: Path, record: dict) -> list[str]:
        return ['--workspace', str(workspace), 'workspace', 'recovery', 'apply', record['transaction_id'], '--json']

    def start_paused(self, args: list[str], root: Path, phase: str, **kwargs) -> subprocess.Popen:
        process = subprocess.Popen([str(facman_executable()), *args], cwd=ROOT,
            env=dict(os.environ, FACMAN_TEST_CONFIGURATION_PAUSE=phase), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        marker = root / ('.facman-test-configuration-' + phase)
        deadline = time.monotonic() + 18
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        if not marker.exists():
            process.kill(); out, err = process.communicate(timeout=10)
            self.fail(f'Owner pause {phase} not reached: {process.returncode}: {out}: {err}')
        return process

    def test_ordinary_scopes_intents_lengths_line_endings_and_readable_metadata(self):
        cases = [(scope, intent, raw, crlf, length, acl_present) for scope in ('instances', 'launch_deck')
                 for intent, raw, crlf, length in [('menu', False, False, 5), ('menu', True, True, 'equal'),
                                                 ('load_save', True, False, 1500)] for acl_present in (False, True)]
        for scope, intent, raw, crlf, length, acl_present in cases:
            with self.subTest(scope=scope, intent=intent, raw=raw, length=length, acl=acl_present), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder).resolve(); instance, original, expected = self.prepare(workspace, intent, raw, crlf, length)
                target = instance / 'config/config.ini'
                held_metadata = self.configure_metadata(target, acl_present); before = self.preserved(instance)
                if not raw: self.assertFalse((instance / 'instance-overrides.v1.json').exists())
                held = snapshot(workspace); old = self.query(workspace, scope, intent)
                self.assertEqual(held, snapshot(workspace))
                plan = old['dependency_identities']['configuration_preparation']['plan']
                factorio_validator('factorio_configuration_preparation_plan.v1.schema.json').validate(plan)
                self.assertEqual(expected.decode(), plan['config_text'])
                self.assertEqual(original.decode(), plan['original_config_text'])
                self.assertEqual(str(target.stat().st_ino), plan['original_object'])
                self.assertEqual(hashlib.sha256(original).hexdigest(), plan['original_config_sha256'])
                self.assertIn('darwin-retained-metadata.v1:', plan['original_metadata_identity'])
                args = self.args(workspace, old['revision'], scope=scope, intent=intent)
                code, out, err = invoke_machine(args); self.assertEqual((0, ''), (code, err), out)
                result = json.loads(out)['payload']; effect = result['action_payload']
                factorio_validator('factorio_configuration_preparation_result.v1.schema.json').validate(effect)
                self.assertEqual('completed', result['outcome'])
                self.assertEqual('routing_configuration_reconciled', effect['status'])
                self.assertTrue(effect['original_file_preserved']); self.assertFalse(effect['existing_settings_modified'])
                self.assertFalse(effect['execution_started']); self.assertFalse(effect['permit_issued'])
                self.assertEqual(expected, target.read_bytes()); self.assertEqual(held_metadata, metadata(target))
                self.assertEqual(before, self.preserved(instance))
                ready = result['replacement_snapshot']['readiness']
                self.assertFalse(ready['preparation_available']); self.assertFalse(ready['execution_available'])
                self.assertEqual('unavailable', ready['play_authority_state'])
                _, record = self.journal(workspace); self.assertEqual('complete', record['state'])
                held = snapshot(workspace); code, replay, err = invoke_machine(args)
                self.assertEqual((0, ''), (code, err), replay)
                self.assertEqual(result, json.loads(replay)['payload']); self.assertEqual(held, snapshot(workspace))
                code, recovery = self.recover(workspace, record); self.assertEqual(0, code, recovery)
                self.assertEqual(held, snapshot(workspace)); self.assertEqual(held_metadata, metadata(target))

    def test_confirmation_and_current_revision_required_before_effects(self):
        for scope in ('instances', 'launch_deck'):
            for variant in ('confirmation', 'settings_drift', 'original_drift'):
                with self.subTest(scope=scope, variant=variant), tempfile.TemporaryDirectory() as folder:
                    workspace = Path(folder).resolve(); instance, original, _ = self.prepare(workspace)
                    target = instance / 'config/config.ini'; old = self.query(workspace, scope)
                    if variant == 'settings_drift':
                        changed = instance / 'instance-overrides.v1.json'
                        changed.write_bytes(changed.read_bytes() + b'\n')
                    elif variant == 'original_drift': target.write_bytes(original + b'; current user change\n')
                    before = snapshot(workspace); held_metadata = metadata(target)
                    code, out, err = invoke_machine(self.args(workspace, old['revision'], scope=scope,
                                                            confirmation=variant != 'confirmation'))
                    self.assertIn(code, (1, 3), out); self.assertEqual('', err, out)
                    self.assertEqual(before, snapshot(workspace)); self.assertEqual(held_metadata, metadata(target))
                    self.assertFalse(any(json.loads(p.read_text())['command_id'] == 'readiness.prepare_configuration'
                                         for p in (workspace / 'transactions').glob('*.transaction.v1.json')))

    def test_unsafe_original_is_refused_during_readonly_planning(self):
        for variant in ('readonly', 'set_id', 'unsafe_flags', 'extra_link', 'security_xattr', 'oversized_metadata'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder).resolve(); instance, original, _ = self.prepare(workspace)
                target = instance / 'config/config.ini'
                if variant == 'readonly': target.chmod(0o444)
                elif variant == 'set_id': target.chmod(0o4644)
                elif variant == 'unsafe_flags': os.chflags(target, stat.UF_HIDDEN)
                elif variant == 'extra_link': os.link(target, instance / 'owned-link.ini')
                elif variant == 'security_xattr': set_xattr(target, 'security.facman', b'owned')
                else:
                    set_xattr(target, 'user.large', b'x' * 40000)
                    self.assertEqual(b'x' * 40000, get_xattr(target, 'user.large'))
                try:
                    held = snapshot(workspace); held_metadata = metadata(target)
                    for scope in ('instances', 'launch_deck'):
                        projected = self.query(workspace, scope)
                        self.assertIsNone(projected['dependency_identities']['configuration_preparation']['plan'])
                        action = next(a for a in projected['available_semantic_actions']
                                      if a['action_id'] == 'readiness.prepare_configuration')
                        self.assertEqual('refused', action['availability'])
                        code, out, err = invoke_machine(self.args(workspace, projected['revision'], scope=scope))
                        self.assertIn(code, (1, 3), out); self.assertEqual('', err, out)
                        self.assertEqual(held, snapshot(workspace)); self.assertEqual(original, target.read_bytes())
                        self.assertEqual(held_metadata, metadata(target))
                finally:
                    if variant in ('readonly', 'set_id'): target.chmod(0o644)
                    if variant == 'unsafe_flags': os.chflags(target, 0)

    def test_missing_routing_keys_and_ambiguous_syntax(self):
        for original in (b'; custom\n[graphics]\nmax-texture-size=4096\n',
                         b'[path]\nread-data=wrong\n[graphics]\nmax-texture-size=4096\n',
                         b'[path]\r\nwrite-data=wrong\r\n[graphics]\r\nmax-texture-size=4096\r\n'):
            with self.subTest(original=original), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder).resolve(); instance, _, _ = self.prepare(workspace)
                target = instance / 'config/config.ini'; target.write_bytes(original)
                before = self.preserved(instance); held_metadata = metadata(target)
                old = self.query(workspace); plan = old['dependency_identities']['configuration_preparation']['plan']
                self.assertIsNotNone(plan)
                code, out, err = invoke_machine(self.args(workspace, old['revision']))
                self.assertEqual((0, ''), (code, err), out)
                self.assertEqual(plan['config_text'].encode(), target.read_bytes())
                self.assertIn(b'max-texture-size=4096', target.read_bytes())
                self.assertEqual(held_metadata, metadata(target)); self.assertEqual(before, self.preserved(instance))
        for original in (b'', b'[path]\nread-data=a\nread-data=b\nwrite-data=c\n',
                         b'[Path]\nread-data=a\nwrite-data=b\n', b'[path]\nread-data=a ; ambiguous\n',
                         b'[path]\nread-data=a\n[path]\nwrite-data=b\n', b'\xef\xbb\xbf[path]\n',
                         b'[path]\nread-data=a\0\n', b'[path]\rread-data=a\n'):
            with self.subTest(original=original), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder).resolve(); instance, _, _ = self.prepare(workspace)
                (instance / 'config/config.ini').write_bytes(original)
                old = self.query(workspace); self.assertIsNone(old['dependency_identities']['configuration_preparation']['plan'])
                held = snapshot(workspace); code, out, err = invoke_machine(self.args(workspace, old['revision']))
                self.assertIn(code, (1, 3), out); self.assertEqual('', err, out); self.assertEqual(held, snapshot(workspace))

    def test_all_durable_boundaries_and_repeated_recovery_interruption(self):
        cases = [(phase, 5, acl) for phase in PHASES for acl in (False, True)] + [(phase, length, True)
            for phase in ('rewrite_after_prefix', 'rewrite_after_write', 'rewrite_after_truncate') for length in ('equal', 1500)]
        for phase, length, acl_present in cases:
            with self.subTest(phase=phase, length=length, acl=acl_present), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder).resolve(); instance, original, expected = self.prepare(workspace, wrong_length=length)
                target = instance / 'config/config.ini'
                held_metadata = self.configure_metadata(target, acl_present); before = self.preserved(instance)
                _, record = self.interrupted(workspace, phase)
                context = json.loads(record['operation_context'])
                self.assertEqual(original.decode(), context['original_config_text'])
                self.assertEqual(expected.decode(), context['config_text'])
                if phase in ('rewrite_after_manifest', 'rewrite_before_admission'):
                    self.assertNotIn('configuration_rewrite_mutation_authorized', record['completed_steps'])
                    self.assertEqual(original, target.read_bytes())
                else: self.assertIn('configuration_rewrite_mutation_authorized', record['completed_steps'])
                if phase == 'rewrite_after_prefix':
                    self.assertNotEqual(original, target.read_bytes()); self.assertNotEqual(expected, target.read_bytes())
                    for _ in range(2):
                        code, out, err = invoke_machine(self.recover_args(workspace, record),
                            env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT=phase))
                        self.assertEqual((74, ''), (code, err), out)
                code, out = self.recover(workspace, record); self.assertEqual(0, code, out)
                self.assertEqual(expected, target.read_bytes()); self.assertEqual(held_metadata, metadata(target))
                self.assertEqual(before, self.preserved(instance))
                held = snapshot(workspace); code, out = self.recover(workspace, record)
                self.assertEqual(0, code, out); self.assertEqual(held, snapshot(workspace))

    def test_actual_cli_sigkill_at_prefix_write_and_truncate_then_recovery(self):
        for phase in ('rewrite_after_prefix', 'rewrite_after_write', 'rewrite_after_truncate'):
            for length in (5, 'equal', 1500):
                with self.subTest(phase=phase, length=length), tempfile.TemporaryDirectory() as folder:
                    workspace = Path(folder).resolve(); instance, original, expected = self.prepare(workspace, wrong_length=length)
                    target = instance / 'config/config.ini'; before = self.preserved(instance)
                    held_metadata = self.configure_metadata(target, length != 'equal')
                    args = self.args(workspace, self.query(workspace)['revision'])
                    process = self.start_paused(args, instance, phase)
                    try:
                        _, record = self.journal(workspace)
                        self.assertIn('configuration_rewrite_mutation_authorized', record['completed_steps'])
                        self.assertNotIn('configuration_rewrite_effect_verified', record['completed_steps'])
                        if phase == 'rewrite_after_prefix':
                            self.assertNotEqual(original, target.read_bytes()); self.assertNotEqual(expected, target.read_bytes())
                        elif phase == 'rewrite_after_truncate': self.assertEqual(expected, target.read_bytes())
                        else: self.assertEqual(expected + original[len(expected):], target.read_bytes())
                        process.kill(); process.communicate(timeout=10)
                        self.assertEqual(-signal.SIGKILL, process.returncode)
                    finally:
                        if process.poll() is None: process.kill(); process.communicate(timeout=10)
                    (instance / ('.facman-test-configuration-' + phase)).unlink()
                    # A second real process loss while recovering the same durable owner.
                    if phase == 'rewrite_after_prefix':
                        process = self.start_paused(self.recover_args(workspace, record), instance, phase)
                        try:
                            process.kill(); process.communicate(timeout=10)
                            self.assertEqual(-signal.SIGKILL, process.returncode)
                        finally:
                            if process.poll() is None: process.kill(); process.communicate(timeout=10)
                    code, out = self.recover(workspace, record); self.assertEqual(0, code, out)
                    self.assertEqual(expected, target.read_bytes()); self.assertEqual(held_metadata, metadata(target))
                    self.assertEqual(before, self.preserved(instance))
                    held = snapshot(workspace); code, out = self.recover(workspace, record)
                    self.assertEqual(0, code, out); self.assertEqual(held, snapshot(workspace))

    def test_unsafe_objects_metadata_drift_and_flock_preserve_owned_inputs(self):
        import fcntl

        variants = ('foreign', 'missing', 'target_symlink', 'substituted', 'parent_symlink', 'parent_substituted',
                    'extra_link', 'readonly', 'set_id', 'mode', 'flags', 'unsafe_flags', 'xattr', 'acl', 'acl_absence', 'security_xattr', 'oversized_metadata', 'flock')
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(
                    prefix='macos-existing-ini-metadata-') as folder:
                workspace = Path(folder).resolve(); instance, _, expected = self.prepare(workspace)
                self.assertEqual(os.geteuid(), workspace.stat().st_uid)
                target = instance / 'config/config.ini'
                set_xattr(target, 'user.facman', b'original')
                set_owned_acl(target, present=True)
                path, record = self.interrupted(workspace, 'rewrite_after_admission'); handle = None
                if variant == 'foreign': target.write_bytes(b'foreign user bytes\n')
                elif variant == 'missing': target.unlink()
                elif variant in ('target_symlink', 'substituted'):
                    held_original = target.with_name('original.ini'); target.rename(held_original)
                    if variant == 'target_symlink': target.symlink_to(held_original)
                    else: target.write_bytes(expected)
                elif variant in ('parent_symlink', 'parent_substituted'):
                    parent = target.parent; held_parent = parent.with_name('original-config'); parent.rename(held_parent)
                    if variant == 'parent_symlink': parent.symlink_to(held_parent, target_is_directory=True)
                    else: parent.mkdir(); target.write_bytes(expected)
                elif variant == 'extra_link': os.link(target, instance / 'original-link.ini')
                elif variant == 'readonly': target.chmod(0o444)
                elif variant == 'set_id': target.chmod(0o4644)
                elif variant == 'mode': target.chmod(0o600)
                elif variant == 'flags': os.chflags(target, stat.UF_NODUMP)
                elif variant == 'unsafe_flags': os.chflags(target, stat.UF_HIDDEN)
                elif variant == 'acl_absence': set_owned_acl(target, present=False)
                elif variant == 'security_xattr': set_xattr(target, 'security.facman', b'test-owned')
                elif variant == 'xattr': set_xattr(target, 'user.facman', b'changed')
                elif variant == 'acl': set_owned_acl(target, present=True, permissions='readattr')
                elif variant == 'oversized_metadata':
                    set_xattr(target, 'user.large', b'x' * 40000)
                    self.assertEqual(b'x' * 40000, get_xattr(target, 'user.large'))
                else: handle = target.open('r+b'); fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    held = snapshot(instance); journal = path.read_bytes()
                    current_metadata = metadata(target) if target.exists() and not target.is_symlink() else None
                    code, out = self.recover(workspace, record); self.assertEqual(3, code, out)
                    self.assertEqual(held, snapshot(instance)); self.assertEqual(journal, path.read_bytes())
                    if current_metadata is not None: self.assertEqual(current_metadata, metadata(target))
                finally:
                    if handle is not None: handle.close()
                    if variant in ('readonly', 'set_id'): target.chmod(0o644)
                    if variant in ('flags', 'unsafe_flags'): os.chflags(target, 0)
            self.assertFalse(workspace.exists(), 'TemporaryDirectory must retire its owned fixture')

    def test_invalid_journal_authority_ids_and_foreign_root_remain_readonly(self):
        variants = ('unadmitted_partial', 'unadmitted_marker', 'duplicate_marker', 'verified_without_admission',
                    'strategy', 'command', 'foreign_root', 'malformed_context', 'object_numeric', 'device_numeric',
                    'object_overflow', 'device_noncanonical', 'object_empty', 'object_signed', 'device_fractional')
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder).resolve(); instance, original, expected = self.prepare(workspace)
                path, record = self.interrupted(workspace, 'rewrite_after_manifest')
                target = instance / 'config/config.ini'; context = json.loads(record['operation_context'])
                if variant == 'unadmitted_partial': target.write_bytes(common.genuine_partial(original, expected))
                elif variant == 'unadmitted_marker': record['completed_steps'].append('configuration_rewrite_mutation_authorized')
                elif variant == 'duplicate_marker':
                    record['completed_steps'].extend(['configuration_rewrite_mutation_authorized'] * 2)
                    record['state'] = 'recovery_required'
                elif variant == 'verified_without_admission': record['completed_steps'].append('configuration_rewrite_effect_verified')
                elif variant == 'strategy': record['commit_strategy'] = 'durable_sidecar_create_no_save_mutation'
                elif variant == 'command': record['command_id'] = 'readiness.prepare_selected_save'
                elif variant == 'foreign_root':
                    foreign = workspace / 'foreign'; (foreign / 'config').mkdir(parents=True)
                    (foreign / 'config/config.ini').write_bytes(b'foreign bytes\n')
                    context['instance_root'] = str(foreign); record['target'] = str(foreign / 'config/config.ini')
                    record['source_identities'] = [str(foreign / 'instance.v1.json')]
                elif variant == 'object_numeric': context['original_object'] = int(context['original_object'])
                elif variant == 'device_numeric': context['original_device'] = int(context['original_device'])
                elif variant == 'object_overflow': context['original_object'] = '18446744073709551616'
                elif variant == 'device_noncanonical': context['original_device'] = '01'
                elif variant == 'object_empty': context['original_object'] = ''
                elif variant == 'object_signed': context['original_object'] = '-1'
                elif variant == 'device_fractional': context['original_device'] = '1.0'
                record['operation_context'] = '{' if variant == 'malformed_context' else json.dumps(context)
                path.write_text(json.dumps(record) + '\n'); journal = path.read_bytes(); held = snapshot(instance)
                foreign_held = snapshot(workspace / 'foreign') if variant == 'foreign_root' else None
                code, out = self.recover(workspace, record); self.assertIn(code, (1, 3), out)
                self.assertEqual(held, snapshot(instance)); self.assertEqual(journal, path.read_bytes())
                if foreign_held is not None: self.assertEqual(foreign_held, snapshot(workspace / 'foreign'))

    def test_verified_audited_complete_states_never_rewrite_torn_or_foreign_objects(self):
        for phase in ('rewrite_after_verification_checkpoint', 'rewrite_after_audit', 'rewrite_after_finalization'):
            for variant in ('partial', 'foreign', 'missing', 'substituted'):
                with self.subTest(phase=phase, variant=variant), tempfile.TemporaryDirectory() as folder:
                    workspace = Path(folder).resolve(); instance, original, expected = self.prepare(workspace)
                    path, record = self.interrupted(workspace, phase)
                    self.assertIn('configuration_rewrite_effect_verified', record['completed_steps'])
                    target = instance / 'config/config.ini'
                    if variant == 'missing': target.unlink()
                    elif variant == 'partial': target.write_bytes(common.genuine_partial(original, expected))
                    elif variant == 'foreign': target.write_bytes(b'foreign bytes\n')
                    else: target.rename(target.with_name('original.ini')); target.write_bytes(expected)
                    held = snapshot(instance); journal = path.read_bytes()
                    code, out = self.recover(workspace, record); self.assertEqual(3, code, out)
                    self.assertEqual(held, snapshot(instance)); self.assertEqual(journal, path.read_bytes())

    def test_current_install_profile_content_settings_and_save_context_drift(self):
        from test_local_modset_solver import call

        for variant in ('installation', 'profile', 'content', 'settings', 'save'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder).resolve(); instance, original, _ = self.prepare(workspace, intent='load_save')
                # gui is built in; use a real current profile file before binding the journal.
                call(workspace, 'profiles', 'create', 'owned-current', '--selection-mode', 'load-save',
                     '--selection', 'selected.zip', '--arg', '--low-vram')
                call(workspace, 'profiles', 'apply', 'main', 'owned-current')
                inputs = {'installation': workspace / 'fixture-install/data/base/info.json',
                          'profile': workspace / 'profiles/owned-current/profile.v1.json',
                          'content': instance / 'mods/simple_1.0.0.zip',
                          'settings': instance / 'instance-overrides.v1.json',
                          'save': instance / 'saves/selected.zip'}
                for name, source in inputs.items():
                    self.assertTrue(source.is_file(), f'{name} fixture input is missing: {source}')
                    self.assertTrue(source.read_bytes(), f'{name} fixture input is empty: {source}')
                self.assertEqual('owned-current', json.loads((instance / 'instance.v1.json').read_text())['profile'])
                self.assertEqual('owned-current', json.loads(inputs['settings'].read_text())['profile_id'])
                self.assertEqual(original, (instance / 'config/config.ini').read_bytes())
                path, record = self.interrupted(workspace, 'rewrite_after_admission', intent='load_save')
                changed = inputs[variant]
                changed.write_bytes(changed.read_bytes() + b'\n')
                held = snapshot(instance); journal = path.read_bytes(); other = changed.read_bytes()
                code, out = self.recover(workspace, record); self.assertEqual(3, code, out)
                self.assertEqual(original, (instance / 'config/config.ini').read_bytes())
                self.assertEqual(held, snapshot(instance)); self.assertEqual(other, changed.read_bytes())
                self.assertEqual(journal, path.read_bytes())

    def test_live_post_admission_drift_refuses_before_first_write(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder).resolve(); instance, original, _ = self.prepare(workspace)
            process = self.start_paused(self.args(workspace, self.query(workspace)['revision']),
                                        instance, 'rewrite_after_admission')
            try:
                changed = instance / 'instance-overrides.v1.json'
                changed.write_bytes(changed.read_bytes() + b'\n'); held = changed.read_bytes()
                path, _ = self.journal(workspace); journal = path.read_bytes()
                (instance / '.facman-test-configuration-release').write_bytes(b'release')
                out, err = process.communicate(timeout=30)
                self.assertEqual((3, ''), (process.returncode, err), out)
                self.assertEqual(original, (instance / 'config/config.ini').read_bytes())
                self.assertEqual(held, changed.read_bytes()); self.assertEqual(journal, path.read_bytes())
            finally:
                if process.poll() is None: process.kill(); process.communicate(timeout=10)

    def test_unreadable_original_under_unprivileged_owner_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder).resolve(); instance, original, _ = self.prepare(workspace)
            path, record = self.interrupted(workspace, 'rewrite_after_admission')
            target = instance / 'config/config.ini'; credentials = {}
            if os.geteuid() == 0:
                import pwd
                worker = pwd.getpwnam('nobody')
                self.assertNotEqual(0, worker.pw_uid)
                for owned in [workspace, *workspace.rglob('*')]: os.chown(owned, worker.pw_uid, worker.pw_gid)
                credentials = dict(user=worker.pw_uid, group=worker.pw_gid, extra_groups=[])
            target.chmod(0o200); journal = path.read_bytes()
            try:
                # Demonstrate the owned process cannot read this original inode.
                probe = subprocess.run([sys.executable, '-c',
                    'import pathlib,sys; pathlib.Path(sys.argv[1]).read_bytes()', str(target)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, **credentials)
                self.assertNotEqual(0, probe.returncode); self.assertIn(b'PermissionError', probe.stderr)
                process = subprocess.run([str(facman_executable()), *self.recover_args(workspace, record)],
                    cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **credentials)
                self.assertEqual((3, ''), (process.returncode, process.stderr), process.stdout)
                self.assertEqual(journal, path.read_bytes()); self.assertEqual(0o200, target.stat().st_mode & 0o777)
            finally:
                target.chmod(0o644)
            self.assertEqual(original, target.read_bytes())

    def test_unreadable_acl_and_xattrs_under_unprivileged_owner_are_preserved(self):
        for permission in ('readsecurity', 'readextattr'):
            with self.subTest(permission=permission), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder).resolve(); instance, original, _ = self.prepare(workspace)
                target = instance / 'config/config.ini'
                set_xattr(target, 'user.facman', b'owned-readable-metadata')
                set_owned_acl(target, present=False)
                path, record = self.interrupted(workspace, 'rewrite_after_admission')
                credentials = {}
                if os.geteuid() == 0:
                    import pwd
                    worker = pwd.getpwnam('nobody'); self.assertNotEqual(0, worker.pw_uid)
                    for owned in [workspace, *workspace.rglob('*')]: os.chown(owned, worker.pw_uid, worker.pw_gid)
                    credentials = dict(user=worker.pw_uid, group=worker.pw_gid, extra_groups=[])
                # This test owns the file and grants no writes; remove this test ACL during fixture retirement.
                subprocess.run(['/bin/chmod', '+a', 'group:everyone deny ' + permission, str(target)],
                               check=True, capture_output=True)
                try:
                    held = snapshot(instance); journal = path.read_bytes(); mode = target.stat().st_mode
                    probe_code = ('import os,pathlib,sys; assert os.geteuid() != 0; '
                                  'sys.path[:0] = [sys.argv[1], sys.argv[2]]; '
                                  'import test_macos_configuration_reconciliation as m; '
                                  'p=pathlib.Path(sys.argv[3]); '
                                  + ('m.metadata(p)' if permission == 'readsecurity' else 'm.get_xattr(p, "user.facman")'))
                    probe = subprocess.run([sys.executable, '-c', probe_code, str(ROOT / 'tests'), str(ROOT), str(target)],
                                           cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **credentials)
                    self.assertNotEqual(0, probe.returncode); self.assertIn(b'PermissionError', probe.stderr)
                    process = subprocess.run([str(facman_executable()), *self.recover_args(workspace, record)],
                        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **credentials)
                    self.assertEqual((3, ''), (process.returncode, process.stderr), process.stdout)
                    self.assertEqual(held, snapshot(instance)); self.assertEqual(journal, path.read_bytes())
                    self.assertEqual(original, target.read_bytes()); self.assertEqual(mode, target.stat().st_mode)
                finally:
                    subprocess.run(['/bin/chmod', '-N', str(target)], check=True, capture_output=True)
                self.assertIsNone(metadata(target)[-1]); self.assertEqual(b'owned-readable-metadata', get_xattr(target, 'user.facman'))

    def test_checkpoint_parent_permission_denial_preserves_actual_durable_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder).resolve(); instance, _, expected = self.prepare(workspace)
            args = self.args(workspace, self.query(workspace)['revision'])
            credentials = {}
            if os.geteuid() == 0:
                import pwd
                worker = pwd.getpwnam('nobody')
                self.assertNotEqual(0, worker.pw_uid)
                # Transfer only this test-owned fixture to the bounded unprivileged worker.
                for owned in [workspace, *workspace.rglob('*')]: os.chown(owned, worker.pw_uid, worker.pw_gid)
                credentials = dict(user=worker.pw_uid, group=worker.pw_gid, extra_groups=[])
            process = self.start_paused(args, instance, 'rewrite_after_write', **credentials)
            parent = workspace / 'transactions'; mode = parent.stat().st_mode & 0o777
            try:
                path, record = self.journal(workspace); journal = path.read_bytes()
                self.assertIn('configuration_rewrite_mutation_authorized', record['completed_steps'])
                self.assertNotIn('configuration_rewrite_effect_verified', record['completed_steps'])
                parent.chmod(0o555)
                # Prove the worker cannot create a sibling used for atomic replacement.
                probe = subprocess.run([sys.executable, '-c',
                    'import os,pathlib,sys; assert os.geteuid() != 0; pathlib.Path(sys.argv[1]).write_bytes(b"probe")', str(parent / 'denied-probe')],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, **credentials)
                self.assertNotEqual(0, probe.returncode); self.assertIn(b'PermissionError', probe.stderr)
                self.assertFalse((parent / 'denied-probe').exists())
                (instance / '.facman-test-configuration-release').write_bytes(b'release')
                out, err = process.communicate(timeout=30)
                self.assertEqual((3, ''), (process.returncode, err), out)
                self.assertEqual(journal, path.read_bytes()); self.assertEqual(expected, (instance / 'config/config.ini').read_bytes())
                parent.chmod(mode)
                recovered = subprocess.run([str(facman_executable()), *self.recover_args(workspace, record)],
                    cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **credentials)
                self.assertEqual((0, ''), (recovered.returncode, recovered.stderr), recovered.stdout)
                self.assertEqual('complete', json.loads(path.read_text())['state'])
                self.assertEqual(expected, (instance / 'config/config.ini').read_bytes())
            finally:
                parent.chmod(mode)
                if process.poll() is None: process.kill(); process.communicate(timeout=10)


if __name__ == '__main__': unittest.main()
