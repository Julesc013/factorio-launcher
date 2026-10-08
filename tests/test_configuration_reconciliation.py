# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
from __future__ import annotations
import ctypes
import hashlib
import json
import os
import threading
import time
from pathlib import Path
import tempfile
import unittest

from native_cli import invoke_machine
import test_configuration_preparation as missing_configuration
from test_local_modset_solver import snapshot
from test_presentation_profile_preparation import factorio_validator


def readable_security(path: Path) -> bytes:
    api = ctypes.WinDLL('advapi32', use_last_error=True).GetFileSecurityW
    api.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                    ctypes.POINTER(ctypes.c_uint32)]
    api.restype = ctypes.c_int
    required = ctypes.c_uint32()
    assert not api(str(path), 7, None, 0, ctypes.byref(required))
    assert ctypes.get_last_error() == 122 and 0 < required.value <= 65536
    data = ctypes.create_string_buffer(required.value)
    assert api(str(path), 7, data, len(data), ctypes.byref(required))
    return data.raw[:required.value]


def change_synthetic_dacl_inheritance(path: Path) -> bytes:
    # Only this newly created test-owned file. Preserve all ACE contents.
    api = ctypes.WinDLL('advapi32', use_last_error=True)
    descriptor = ctypes.create_string_buffer(readable_security(path))
    api.GetSecurityDescriptorControl.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint32)]
    control, revision = ctypes.c_uint16(), ctypes.c_uint32()
    assert api.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(revision))
    api.SetSecurityDescriptorControl.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16]
    protected = 0x1000 if not control.value & 0x1000 else 0
    assert api.SetSecurityDescriptorControl(descriptor, 0x1000, protected)
    api.SetFileSecurityW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
    assert api.SetFileSecurityW(str(path), 4 | (0x80000000 if protected else 0x20000000), descriptor)
    return readable_security(path)


def genuine_partial(original: bytes, intended: bytes) -> bytes:
    first_difference = next(i for i, (old, new) in enumerate(zip(original, intended)) if old != new)
    boundary = first_difference + 1
    result = intended[:boundary] + original[boundary:]
    assert result != original and result != intended
    return result


@unittest.skipUnless(os.name == 'nt', 'unsupported: existing INI repair is Windows NTFS only')
class ExistingConfigurationTests(unittest.TestCase):
    # Reuse fixture methods without inheriting and rediscovering thirteen tests.
    query = missing_configuration.ConfigurationPreparationTests.query
    args = missing_configuration.ConfigurationPreparationTests.args
    journal = missing_configuration.ConfigurationPreparationTests.journal
    recover = missing_configuration.ConfigurationPreparationTests.recover
    preserved = missing_configuration.ConfigurationPreparationTests.preserved

    def prepare(self, workspace: Path, intent: str = 'menu', raw: bool = True,
                crlf: bool = False, wrong_length: int | str = 5) -> tuple[Path, bytes, bytes]:
        instance, current = missing_configuration.ConfigurationPreparationTests.prepare(self, workspace, intent, raw)
        routing = dict(line.split(b'=', 1) for line in current.splitlines() if b'=' in line)
        read_count, write_count = (len(routing[b'read-data']), len(routing[b'write-data'])) if wrong_length == 'equal' else (wrong_length, wrong_length)
        read, write = b'R' * read_count, b'W' * write_count
        original = (b'; retain this comment\n[path]\nread-data = ' + read + b'  \n; ' + b'gap ' * 1500 + b'\nwrite-data= ' + write +
                    b'\t\n\n[graphics]\nmax-texture-size=4096\n[other]\ncheck-updates=true\n; ' + b'padding ' * 1000 + b'\n')
        expected = original.replace(read, routing[b'read-data']).replace(write, routing[b'write-data'])
        if crlf: original, expected = original.replace(b'\n', b'\r\n'), expected.replace(b'\n', b'\r\n')
        (instance / 'config/config.ini').write_bytes(original)
        return instance, original, expected

    def test_ordinary_configuration_repair_preserves_custom_bytes_file_and_metadata(self) -> None:
        for scope, intent, crlf, raw in [('instances', 'menu', False, False),
                                       ('instances', 'menu', False, True), ('launch_deck', 'menu', True, True),
                                       ('instances', 'load_save', True, True)]:
            with self.subTest(scope=scope, intent=intent, raw=raw), tempfile.TemporaryDirectory(prefix='existing-config-') as value:
                workspace = Path(value); instance, original, expected = self.prepare(workspace, intent, raw=raw, crlf=crlf)
                if not raw: self.assertFalse((instance / 'instance-overrides.v1.json').exists())
                target = instance / 'config/config.ini'; before = self.preserved(instance)
                stat = target.stat(); security = readable_security(target)
                ads = [Path(str(target) + ':' + name) for name in ['facman-first', 'facman-second']]
                for i, stream in enumerate(ads): stream.write_bytes(bytes([0, 255, i, 128, 13, 10]))
                frozen = snapshot(workspace); old = self.query(workspace, scope, intent)
                self.assertEqual(frozen, snapshot(workspace))
                plan = old['dependency_identities']['configuration_preparation']['plan']
                factorio_validator('factorio_configuration_preparation_plan.v1.schema.json').validate(plan)
                self.assertEqual('existing_routing_configuration', plan['component'])
                self.assertEqual(original.decode(), plan['original_config_text'])
                self.assertEqual(hashlib.sha256(original).hexdigest(), plan['original_config_sha256'])
                self.assertIsInstance(plan['original_device'], str)
                self.assertEqual(str(stat.st_ino), plan['original_object'])
                self.assertEqual(expected.decode(), plan['config_text'])
                args = self.args(workspace, old['revision'], identity='existing', scope=scope, intent=intent)
                code, out, err = invoke_machine(args); self.assertEqual((0, ''), (code, err), out)
                result = json.loads(out)['payload']; self.assertEqual('completed', result['outcome'])
                effect = result['action_payload']
                factorio_validator('factorio_configuration_preparation_result.v1.schema.json').validate(effect)
                self.assertEqual('routing_configuration_reconciled', effect['status'])
                self.assertTrue(effect['original_file_preserved']); self.assertFalse(effect['existing_settings_modified'])
                self.assertEqual(expected, target.read_bytes()); self.assertEqual(before, self.preserved(instance))
                self.assertEqual(stat.st_ino, target.stat().st_ino)
                self.assertEqual(stat.st_birthtime_ns, target.stat().st_birthtime_ns)
                self.assertEqual(security, readable_security(target))
                for i, stream in enumerate(ads): self.assertEqual(bytes([0, 255, i, 128, 13, 10]), stream.read_bytes())
                ready = result['replacement_snapshot']['readiness']
                self.assertNotIn('instance_effective_config_invalid', [b['code'] for b in ready['blockers']])
                self.assertFalse(ready['preparation_available']); self.assertFalse(ready['execution_available'])
                frozen = snapshot(workspace); repeat, text, error = invoke_machine(args)
                self.assertEqual((0, ''), (repeat, error), text)
                self.assertEqual(result, json.loads(text)['payload']); self.assertEqual(frozen, snapshot(workspace))

    def test_large_file_id_is_lossless_and_malformed_journal_ids_preserve_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix='existing-config-large-id-') as value:
            workspace = Path(value); instance, original, expected = self.prepare(workspace, raw=False)
            target = instance / 'config/config.ini'
            # Reuse only this synthetic file until its real NTFS sequence number
            # exceeds the JSON exact-integer limit that caused the failure.
            for _ in range(512):
                if target.stat().st_ino > 9007199254740991: break
                target.unlink(); target.write_bytes(original)
            identity = target.stat().st_ino
            self.assertGreater(identity, 9007199254740991, 'NTFS did not produce the required large file ID')
            old = self.query(workspace)
            component = old['dependency_identities']['configuration_preparation']
            self.assertIsNotNone(component['plan'], component['refusal'])
            plan = component['plan']
            factorio_validator('factorio_configuration_preparation_plan.v1.schema.json').validate(plan)
            self.assertEqual(str(identity), plan['original_object'])
            self.assertIsInstance(plan['original_device'], str)
            code, text, error = invoke_machine(self.args(workspace, old['revision']),
                env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT='rewrite_after_manifest'))
            self.assertEqual((74, ''), (code, error), text)
            path, record = self.journal(workspace); actual_journal = path.read_bytes()
            context = json.loads(record['operation_context'])
            self.assertEqual(str(identity), context['original_object'])
            self.assertEqual(plan['original_device'], context['original_device'])
            for field in ['original_object', 'original_device']:
                for invalid in [identity, '', '01', '-1', '+1', ' 1', '1.0', '18446744073709551616']:
                    with self.subTest(field=field, invalid=invalid):
                        changed = dict(context); changed[field] = invalid
                        tampered = dict(record); tampered['operation_context'] = json.dumps(changed)
                        path.write_text(json.dumps(tampered) + '\n')
                        frozen_journal = path.read_bytes(); frozen_instance = snapshot(instance)
                        code, output = self.recover(workspace, tampered)
                        self.assertEqual(3, code, output)
                        self.assertEqual(frozen_journal, path.read_bytes())
                        self.assertEqual(frozen_instance, snapshot(instance))
            path.write_bytes(actual_journal)
            code, output = self.recover(workspace, record); self.assertEqual(0, code, output)
            self.assertEqual(expected, target.read_bytes()); self.assertEqual(identity, target.stat().st_ino)

    def test_durable_journal_recovers_before_during_and_after_same_object_write(self) -> None:
        phases = ['rewrite_after_manifest', 'rewrite_before_admission', 'rewrite_after_admission',
                      'rewrite_before_write', 'rewrite_after_prefix', 'rewrite_after_write',
                      'rewrite_after_truncate', 'rewrite_after_verification_checkpoint',
                      'rewrite_before_finalization', 'rewrite_after_audit', 'rewrite_after_finalization']
        for phase, length in [(phase, 5) for phase in phases] + [(phase, length) for phase in
            ['rewrite_after_prefix', 'rewrite_after_write', 'rewrite_after_truncate'] for length in [1500, 'equal']]:
            with self.subTest(phase=phase, length=length), tempfile.TemporaryDirectory(prefix='existing-config-loss-') as value:
                workspace = Path(value); instance, original, expected = self.prepare(workspace, wrong_length=length)
                target = instance / 'config/config.ini'; identity = target.stat().st_ino
                preserved = self.preserved(instance)
                old = self.query(workspace)
                code, out, err = invoke_machine(self.args(workspace, old['revision']),
                    env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT=phase))
                self.assertEqual((74, ''), (code, err), out)
                _, record = self.journal(workspace)
                self.assertEqual('existing_config_retained_stream_rewrite_v1', record['commit_strategy'])
                context = json.loads(record['operation_context'])
                self.assertEqual(original.decode(), context['original_config_text'])
                self.assertEqual(expected.decode(), context['config_text'])
                if phase in ['rewrite_after_manifest', 'rewrite_before_admission']:
                    self.assertNotIn('configuration_rewrite_mutation_authorized', record['completed_steps'])
                    self.assertEqual(original, target.read_bytes())
                else: self.assertIn('configuration_rewrite_mutation_authorized', record['completed_steps'])
                if phase == 'rewrite_after_prefix':
                    self.assertNotEqual(original, target.read_bytes()); self.assertNotEqual(expected, target.read_bytes())
                    again, _, _ = invoke_machine(['--workspace', str(workspace), 'workspace', 'recovery', 'apply',
                        record['transaction_id'], '--json'], env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT=phase))
                    self.assertEqual(74, again)
                code, recovery = self.recover(workspace, record); self.assertEqual(0, code, recovery)
                self.assertEqual(expected, target.read_bytes()); self.assertEqual(identity, target.stat().st_ino)
                self.assertEqual(preserved, self.preserved(instance))
                frozen = snapshot(workspace); code, recovery = self.recover(workspace, record)
                self.assertEqual(0, code, recovery); self.assertEqual(frozen, snapshot(workspace))

    def test_terminal_recovery_preserves_missing_partial_foreign_and_substituted_objects(self) -> None:
        for variant in ['missing', 'partial', 'foreign', 'substituted']:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix='existing-config-terminal-') as value:
                workspace = Path(value); instance, original, expected = self.prepare(workspace)
                old = self.query(workspace); code, out, _ = invoke_machine(self.args(workspace, old['revision']))
                self.assertEqual(0, code, out); _, record = self.journal(workspace)
                target = instance / 'config/config.ini'
                if variant == 'missing': target.unlink()
                elif variant == 'partial': target.write_bytes(genuine_partial(original, expected))
                elif variant == 'foreign': target.write_bytes(b'foreign operator contents\n')
                else:
                    target.rename(target.with_name('preserved-original.ini')); target.write_bytes(expected)
                held = snapshot(instance); code, output = self.recover(workspace, record)
                self.assertEqual(3, code, output); self.assertEqual(held, snapshot(instance))

    def test_unadmitted_partial_foreign_metadata_and_strategy_are_preserved(self) -> None:
        for variant in ['unadmitted', 'unadmitted_marker', 'foreign', 'readonly', 'strategy', 'extra_link', 'dacl']:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix='existing-config-refusal-') as value:
                workspace = Path(value); instance, original, expected = self.prepare(workspace)
                phase = 'rewrite_after_manifest' if variant in ['unadmitted', 'unadmitted_marker'] else 'rewrite_after_admission'
                code, _, _ = invoke_machine(self.args(workspace, self.query(workspace)['revision']),
                    env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT=phase))
                self.assertEqual(74, code); path, record = self.journal(workspace)
                target = instance / 'config/config.ini'
                if variant == 'unadmitted': target.write_bytes(genuine_partial(original, expected))
                elif variant == 'foreign': target.write_bytes(b'foreign contents must survive\n')
                elif variant == 'readonly': target.chmod(0o444)
                elif variant == 'extra_link': os.link(target, instance / 'preserved-extra-link.ini')
                elif variant == 'dacl': changed_security = change_synthetic_dacl_inheritance(target)
                elif variant == 'unadmitted_marker':
                    record['completed_steps'].append('configuration_rewrite_mutation_authorized')
                    path.write_text(json.dumps(record) + '\n'); frozen_journal = path.read_bytes()
                else:
                    record['commit_strategy'] = 'durable_sidecar_create_no_save_mutation'
                    path.write_text(json.dumps(record) + '\n'); frozen_journal = path.read_bytes()
                try:
                    held = snapshot(instance); code, output = self.recover(workspace, record)
                    self.assertEqual(1 if variant == 'strategy' else 3, code, output)
                    self.assertEqual(held, snapshot(instance))
                    if variant in ['unadmitted_marker', 'strategy']: self.assertEqual(frozen_journal, path.read_bytes())
                    if variant == 'strategy':
                        self.assertEqual('recovery_journal_invalid', output['error']['code'])
                        self.assertEqual('refused_before_effects', output['operation']['outcome'])
                        self.assertFalse(output['operation']['effects_may_have_occurred'])
                    if variant == 'dacl': self.assertEqual(changed_security, readable_security(target))
                finally:
                    if variant == 'readonly': target.chmod(0o666)

    def test_ambiguous_syntax_empty_and_legacy_configuration_have_no_effect(self) -> None:
        for value in [b'', b'[path]\nread-data=a\nread-data=b\nwrite-data=c\n',
                      b'[Path]\nread-data=a\nwrite-data=b\n', b'[path]\nread-data=a ; ambiguous\nwrite-data=b\n',
                      b'[path]\nread-data=a\n[path]\nwrite-data=b\n', b'\xef\xbb\xbf[path]\n', b'legacy']:
            with self.subTest(value=value), tempfile.TemporaryDirectory(prefix='existing-config-ambiguous-') as folder:
                workspace = Path(folder); instance, _, _ = self.prepare(workspace)
                if value == b'legacy': (instance / 'config-path.cfg').write_bytes(b'config-path=foreign\n')
                else: (instance / 'config/config.ini').write_bytes(value)
                old = self.query(workspace)
                self.assertIsNone(old['dependency_identities']['configuration_preparation']['plan'])
                held = snapshot(workspace); code, output, error = invoke_machine(self.args(workspace, old['revision']))
                self.assertIn(code, (1, 3), output); self.assertEqual('', error, output)
                self.assertEqual(held, snapshot(workspace))

    def test_verified_and_audited_recovery_cannot_write_a_partial_or_missing_stream(self) -> None:
        for phase in ['rewrite_after_verification_checkpoint', 'rewrite_after_audit']:
            for missing in [False, True]:
                with self.subTest(phase=phase, missing=missing), tempfile.TemporaryDirectory(prefix='existing-config-verified-') as folder:
                    workspace = Path(folder); instance, original, expected = self.prepare(workspace)
                    code, _, _ = invoke_machine(self.args(workspace, self.query(workspace)['revision']),
                        env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT=phase))
                    self.assertEqual(74, code); journal_path, record = self.journal(workspace)
                    frozen_journal = journal_path.read_bytes()
                    self.assertIn('configuration_rewrite_effect_verified', record['completed_steps'])
                    self.assertEqual('audited' if phase == 'rewrite_after_audit' else 'recovery_required', record['state'])
                    target = instance / 'config/config.ini'
                    if missing: target.unlink()
                    else: target.write_bytes(genuine_partial(original, expected))
                    held = snapshot(instance); code, output = self.recover(workspace, record)
                    self.assertEqual(3, code, output); self.assertEqual(held, snapshot(instance))
                    self.assertEqual(frozen_journal, journal_path.read_bytes())

    def test_foreign_journal_root_is_rejected_before_configuration_lock_or_file_access(self) -> None:
        with tempfile.TemporaryDirectory(prefix='existing-config-foreign-root-') as folder:
            workspace = Path(folder); instance, _, _ = self.prepare(workspace)
            code, _, _ = invoke_machine(self.args(workspace, self.query(workspace)['revision']),
                env=dict(os.environ, FACMAN_TEST_CONFIGURATION_EXIT='rewrite_after_manifest'))
            self.assertEqual(74, code); path, record = self.journal(workspace)
            foreign = workspace / 'foreign-user-instance'; (foreign / 'config').mkdir(parents=True)
            (foreign / 'locks').mkdir(); (foreign / 'config/config.ini').write_bytes(b'foreign user bytes\n')
            context = json.loads(record['operation_context']); context['instance_root'] = str(foreign)
            record['target'] = str(foreign / 'config/config.ini')
            record['source_identities'] = [str(foreign / 'instance.v1.json')]
            record['operation_context'] = json.dumps(context); path.write_text(json.dumps(record) + '\n')
            frozen_journal = path.read_bytes(); frozen_instance = snapshot(instance)
            held = snapshot(foreign); code, output = self.recover(workspace, record)
            self.assertEqual(3, code, output); self.assertEqual(held, snapshot(foreign))
            self.assertEqual(frozen_instance, snapshot(instance))
            self.assertEqual(frozen_journal, path.read_bytes())
            self.assertEqual('configuration_reconciliation_recovery_required', output['error']['code'])
            self.assertIn('Journal root is not the current registered', output['error']['message'])

    def test_post_admission_context_drift_refuses_before_first_byte_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix='existing-config-drift-') as folder:
            workspace = Path(folder); instance, original, _ = self.prepare(workspace)
            marker = instance / '.facman-test-configuration-rewrite_after_admission'
            release = instance / '.facman-test-configuration-release'
            result = []
            worker = threading.Thread(target=lambda: result.append(invoke_machine(
                self.args(workspace, self.query(workspace)['revision']),
                env=dict(os.environ, FACMAN_TEST_CONFIGURATION_PAUSE='rewrite_after_admission'))))
            worker.start()
            try:
                deadline = time.monotonic() + 20
                while not marker.exists() and worker.is_alive() and time.monotonic() < deadline: time.sleep(.01)
                self.assertTrue(marker.exists(), 'post-admission seam was not reached')
                overrides = instance / 'instance-overrides.v1.json'
                changed = overrides.read_bytes() + b'\n'; overrides.write_bytes(changed)
                release.write_bytes(b'release'); worker.join(30); self.assertFalse(worker.is_alive())
                code, text, error = result[0]; self.assertEqual((3, ''), (code, error), text)
                self.assertEqual(original, (instance / 'config/config.ini').read_bytes())
                self.assertEqual(changed, overrides.read_bytes())
            finally:
                release.write_bytes(b'release'); worker.join(30)

    def test_failed_verified_checkpoint_preserves_last_actual_journal_and_stream(self) -> None:
        with tempfile.TemporaryDirectory(prefix='existing-config-journal-failure-') as folder:
            workspace = Path(folder); instance, _, expected = self.prepare(workspace)
            marker = instance / '.facman-test-configuration-rewrite_after_write'
            release = instance / '.facman-test-configuration-release'
            args = self.args(workspace, self.query(workspace)['revision'])
            result = []
            worker = threading.Thread(target=lambda: result.append(invoke_machine(args,
                env=dict(os.environ, FACMAN_TEST_CONFIGURATION_PAUSE='rewrite_after_write'))))
            worker.start(); path = None
            try:
                deadline = time.monotonic() + 20
                while not marker.exists() and worker.is_alive() and time.monotonic() < deadline: time.sleep(.01)
                self.assertTrue(marker.exists(), 'held completed-write seam was not reached')
                path, record = self.journal(workspace)
                self.assertIn('configuration_rewrite_mutation_authorized', record['completed_steps'])
                self.assertNotIn('configuration_rewrite_effect_verified', record['completed_steps'])
                actual_journal = path.read_bytes(); path.chmod(0o444)
                release.write_bytes(b'release'); worker.join(30); self.assertFalse(worker.is_alive())
                code, text, error = result[0]; self.assertEqual((3, ''), (code, error), text)
                self.assertEqual(actual_journal, path.read_bytes())
                self.assertEqual(expected, (instance / 'config/config.ini').read_bytes())
                self.assertTrue(path.stat().st_file_attributes & 1)
                path.chmod(0o666)
                code, recovery = self.recover(workspace, record); self.assertEqual(0, code, recovery)
                self.assertEqual(expected, (instance / 'config/config.ini').read_bytes())
            finally:
                release.write_bytes(b'release'); worker.join(30)
                if path is not None and path.exists(): path.chmod(0o666)


if __name__ == '__main__': unittest.main()
