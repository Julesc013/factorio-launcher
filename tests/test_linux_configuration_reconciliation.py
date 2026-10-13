# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Linux ordinary existing-INI owner proofs, independent of Windows metadata tests."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import struct
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


def access_acl(named_uid: int = 65533) -> bytes:
    # Linux POSIX ACL xattr v2: owner rw, named user r, group r, mask r, other r.
    entries = [(1, 6, 0xffffffff), (2, 4, named_uid), (4, 4, 0xffffffff),
               (16, 4, 0xffffffff), (32, 4, 0xffffffff)]
    return struct.pack('<I', 2) + b''.join(struct.pack('<HHI', *entry) for entry in entries)


def metadata(path: Path) -> tuple:
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            tuple((name, os.getxattr(path, name)) for name in sorted(os.listxattr(path))))


@unittest.skipUnless(sys.platform == 'linux', 'unsupported: Linux existing-INI owner qualification')
class LinuxExistingConfigurationTests(unittest.TestCase):
    # Share fixture construction and transport assertions, never Windows test bodies.
    prepare = common.ExistingConfigurationTests.prepare
    query = common.ExistingConfigurationTests.query
    args = common.ExistingConfigurationTests.args
    journal = common.ExistingConfigurationTests.journal
    recover = common.ExistingConfigurationTests.recover
    preserved = common.ExistingConfigurationTests.preserved

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
        cases = [(scope, intent, raw, crlf, length) for scope in ('instances', 'launch_deck')
                 for intent, raw, crlf, length in [('menu', False, False, 5), ('menu', True, True, 'equal'),
                                                 ('load_save', True, False, 1500)]]
        for scope, intent, raw, crlf, length in cases:
            with self.subTest(scope=scope, intent=intent, raw=raw, length=length), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder); instance, original, expected = self.prepare(workspace, intent, raw, crlf, length)
                target = instance / 'config/config.ini'; target.chmod(0o640)
                os.setxattr(target, 'user.facman-first', b'\0\xff\x80\r\n')
                os.setxattr(target, 'user.facman-second', b'exact unrelated bytes')
                os.setxattr(target, 'system.posix_acl_access', access_acl())
                self.assertEqual(access_acl(), os.getxattr(target, 'system.posix_acl_access'))
                held_metadata = metadata(target); before = self.preserved(instance)
                held = snapshot(workspace); old = self.query(workspace, scope, intent)
                self.assertEqual(held, snapshot(workspace))
                plan = old['dependency_identities']['configuration_preparation']['plan']
                factorio_validator('factorio_configuration_preparation_plan.v1.schema.json').validate(plan)
                self.assertEqual(expected.decode(), plan['config_text'])
                self.assertEqual(original.decode(), plan['original_config_text'])
                self.assertEqual(str(target.stat().st_ino), plan['original_object'])
                self.assertEqual(hashlib.sha256(original).hexdigest(), plan['original_config_sha256'])
                self.assertIn('linux', plan['original_metadata_identity'])
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

    def test_missing_routing_keys_and_ambiguous_syntax(self):
        for original in (b'; custom\n[graphics]\nmax-texture-size=4096\n',
                         b'[path]\nread-data=wrong\n[graphics]\nmax-texture-size=4096\n',
                         b'[path]\r\nwrite-data=wrong\r\n[graphics]\r\nmax-texture-size=4096\r\n'):
            with self.subTest(original=original), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder); instance, _, _ = self.prepare(workspace)
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
                workspace = Path(folder); instance, _, _ = self.prepare(workspace)
                (instance / 'config/config.ini').write_bytes(original)
                old = self.query(workspace); self.assertIsNone(old['dependency_identities']['configuration_preparation']['plan'])
                held = snapshot(workspace); code, out, err = invoke_machine(self.args(workspace, old['revision']))
                self.assertIn(code, (1, 3), out); self.assertEqual('', err, out); self.assertEqual(held, snapshot(workspace))

    def test_all_durable_boundaries_and_repeated_recovery_interruption(self):
        cases = [(phase, 5) for phase in PHASES] + [(phase, length)
            for phase in ('rewrite_after_prefix', 'rewrite_after_write', 'rewrite_after_truncate') for length in ('equal', 1500)]
        for phase, length in cases:
            with self.subTest(phase=phase, length=length), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder); instance, original, expected = self.prepare(workspace, wrong_length=length)
                target = instance / 'config/config.ini'; held_metadata = metadata(target); before = self.preserved(instance)
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
                    workspace = Path(folder); instance, original, expected = self.prepare(workspace, wrong_length=length)
                    target = instance / 'config/config.ini'; before = self.preserved(instance); held_metadata = metadata(target)
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
                        os.kill(process.pid, signal.SIGKILL); process.communicate(timeout=10)
                        self.assertEqual(-signal.SIGKILL, process.returncode)
                    finally:
                        if process.poll() is None: process.kill(); process.communicate(timeout=10)
                    (instance / ('.facman-test-configuration-' + phase)).unlink()
                    # A second real process loss while recovering the same durable owner.
                    if phase == 'rewrite_after_prefix':
                        process = self.start_paused(self.recover_args(workspace, record), instance, phase)
                        try:
                            os.kill(process.pid, signal.SIGKILL); process.communicate(timeout=10)
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
                    'extra_link', 'readonly', 'set_id', 'mode', 'xattr', 'acl', 'oversized_metadata', 'flock')
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder); instance, _, expected = self.prepare(workspace)
                target = instance / 'config/config.ini'
                os.setxattr(target, 'user.facman', b'original')
                os.setxattr(target, 'system.posix_acl_access', access_acl())
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
                elif variant == 'xattr': os.setxattr(target, 'user.facman', b'changed')
                elif variant == 'acl': os.setxattr(target, 'system.posix_acl_access', access_acl(65532))
                elif variant == 'oversized_metadata': os.setxattr(target, 'user.large', b'x' * 40000)
                else: handle = target.open('r+b'); fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    held = snapshot(instance); journal = path.read_bytes()
                    current_metadata = metadata(target) if target.exists() else None
                    code, out = self.recover(workspace, record); self.assertEqual(3, code, out)
                    self.assertEqual(held, snapshot(instance)); self.assertEqual(journal, path.read_bytes())
                    if current_metadata is not None: self.assertEqual(current_metadata, metadata(target))
                finally:
                    if handle is not None: handle.close()
                    if variant in ('readonly', 'set_id'): target.chmod(0o644)

    def test_invalid_journal_authority_ids_and_foreign_root_remain_readonly(self):
        variants = ('unadmitted_partial', 'unadmitted_marker', 'duplicate_marker', 'verified_without_admission',
                    'strategy', 'command', 'foreign_root', 'malformed_context', 'object_numeric', 'device_numeric',
                    'object_overflow', 'device_noncanonical', 'object_empty', 'object_signed', 'device_fractional')
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder); instance, original, expected = self.prepare(workspace)
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
                    workspace = Path(folder); instance, original, expected = self.prepare(workspace)
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
                workspace = Path(folder); instance, original, _ = self.prepare(workspace, intent='load_save')
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
            workspace = Path(folder); instance, original, _ = self.prepare(workspace)
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
            workspace = Path(folder); instance, original, _ = self.prepare(workspace)
            path, record = self.interrupted(workspace, 'rewrite_after_admission')
            target = instance / 'config/config.ini'; credentials = {}
            if os.geteuid() == 0:
                for owned in [workspace, *workspace.rglob('*')]: os.chown(owned, 65534, 65534)
                credentials = dict(user=65534, group=65534, extra_groups=[])
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

    def test_checkpoint_parent_permission_denial_preserves_actual_durable_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder); instance, _, expected = self.prepare(workspace)
            args = self.args(workspace, self.query(workspace)['revision'])
            credentials = {}
            if os.geteuid() == 0:
                # Transfer only this test-owned fixture to the bounded unprivileged worker.
                for owned in [workspace, *workspace.rglob('*')]: os.chown(owned, 65534, 65534)
                credentials = dict(user=65534, group=65534, extra_groups=[])
            process = self.start_paused(args, instance, 'rewrite_after_write', **credentials)
            parent = workspace / 'transactions'; mode = parent.stat().st_mode & 0o777
            try:
                path, record = self.journal(workspace); journal = path.read_bytes()
                self.assertIn('configuration_rewrite_mutation_authorized', record['completed_steps'])
                self.assertNotIn('configuration_rewrite_effect_verified', record['completed_steps'])
                parent.chmod(0o555)
                # Prove the worker cannot create a sibling used for atomic replacement.
                probe = subprocess.run([sys.executable, '-c',
                    'import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(b"probe")', str(parent / 'denied-probe')],
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
