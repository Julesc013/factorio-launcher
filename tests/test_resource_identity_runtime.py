# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Failure custody and noninteractive loader behavior for the actual CLI fixture."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.integration import resource_identity_runtime as proof


class ResourceIdentityRuntimeTests(unittest.TestCase):
    def resource_recreation_boundary(self, label, *, restrictive_umask=False,
                                     fixture_timeout=None):
        """Run the actual helper flow with inert CLI responses and real private files."""
        observed = []
        observed_timeouts = []
        original = b'original resource payload'
        write_bytes = Path.write_bytes
        with tempfile.TemporaryDirectory(prefix='facman-resource-mode-') as tmp:
            root = Path(tmp)
            cli, fixture = root / 'cli', root / 'fixture'
            cli.write_bytes(b'not executed')
            fixture.write_bytes(b'not executed')
            expected_mode = None

            def capture(name, command, records, **kwargs):
                nonlocal expected_mode
                observed_timeouts.append((name, kwargs['timeout']))
                if name == 'prepare_fixture':
                    seed = Path(command[3])
                    (seed / 'share/facman/manifest').mkdir(parents=True)
                    (seed / 'facman').write_bytes(b'not executed')
                    resource = seed / 'share/facman/facman.resources'
                    resource.write_bytes(original)
                    resource.chmod(0o644)
                    expected_mode = stat.S_IMODE(resource.stat().st_mode)
                    (seed / 'share/facman/manifest/product-stage.v1.json').write_bytes(b'{}')
                product = Path(kwargs.get('executable') or command[0]).parent
                resource = product / 'share/facman/facman.resources'
                if name == label:
                    observed.append((resource.read_bytes(), stat.S_IMODE(resource.stat().st_mode)))
                    raise RuntimeError('injected stop after observing resource boundary')
                payload = dict(pack_sha256=proof.sha(original), package_profile='linux_product_x64',
                               package_manifest_sha256=proof.sha(b'{}'),
                               entries=['content/factorio/test.txt'], expanded_bytes=len(original))
                record = dict(exit_code=1 if name in ('portable_missing', 'portable_truncated') else 0,
                              stdout=json.dumps(dict(payload=payload, error='resource_fixture')), stderr='')
                records.append(record)
                return record

            def restrictive_write(path, data):
                result = write_bytes(path, data)
                if ('portable relocated' in str(path) and path.name == 'facman.resources' and
                        data == (original[:-1] if label.endswith('_truncated') else original)):
                    # Windows cannot model Unix 0600 vs 0644; removing write access
                    # gives a real filesystem mode distinction at both call sites.
                    path.chmod(stat.S_IREAD)
                return result

            previous_umask = os.umask(0o077) if restrictive_umask else None
            arguments = ['proof', '--cli', str(cli), '--fixture', str(fixture),
                         '--work-root', str(root / 'runs')]
            if fixture_timeout is not None:
                arguments.extend(['--fixture-timeout-seconds', str(fixture_timeout)])
            try:
                with mock.patch.object(proof.sys, 'platform', 'linux'), \
                     mock.patch.object(proof.sys, 'argv', arguments), \
                     mock.patch.object(proof, 'capture', side_effect=capture), \
                     mock.patch.object(proof, 'run_child', side_effect=AssertionError('no native dispatch')), \
                     mock.patch.object(Path, 'write_bytes', write_bytes if restrictive_umask else restrictive_write), \
                     mock.patch('sys.stdout', new_callable=io.StringIO), \
                     mock.patch('sys.stderr', new_callable=io.StringIO):
                    self.assertEqual(proof.main(), 1)  # Deliberate stop; never claim a full CLI proof.
                expected_bytes = original[:-1] if label.endswith('_truncated') else original
                self.assertEqual(observed, [(expected_bytes, expected_mode)])
            finally:
                if previous_umask is not None:
                    os.umask(previous_umask)
                for path in root.rglob('facman.resources'):
                    path.chmod(0o644)
        return observed_timeouts

    def test_restoration_preserves_mode_at_both_cli_boundaries(self):
        for label in ('portable_truncated', 'portable_export'):
            with self.subTest(label=label):
                self.resource_recreation_boundary(label)

    @unittest.skipUnless(os.name == 'posix', 'not_applicable: Unix umask and permission bits; required on POSIX')
    def test_restoration_preserves_original_mode_under_umask_077(self):
        for label in ('portable_truncated', 'portable_export'):
            with self.subTest(label=label):
                self.resource_recreation_boundary(label, restrictive_umask=True)

    def test_sanitized_fixture_timeout_is_bounded_and_does_not_extend_other_commands(self):
        observed = self.resource_recreation_boundary(
            'portable_truncated', fixture_timeout=60)

        self.assertEqual(observed[0], ('prepare_fixture', 60.0))
        self.assertTrue(all(timeout == 30.0 for _, timeout in observed[1:]))
        for value in ('0', '61', 'nan', 'not-a-number'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                proof.child_timeout_seconds(value)

    def test_second_relocated_layout_only_repeats_process_image_verification(self):
        labels = []
        original = b'original resource payload'
        with tempfile.TemporaryDirectory(prefix='facman-resource-layouts-') as tmp:
            root = Path(tmp)
            cli, fixture = root / 'cli', root / 'fixture'
            cli.write_bytes(b'cli')
            fixture.write_bytes(b'fixture')

            def capture(label, command, records, **kwargs):
                labels.append(label)
                if label == 'prepare_fixture':
                    seed = Path(command[3])
                    (seed / 'share/facman/manifest').mkdir(parents=True)
                    (seed / 'facman').write_bytes(b'cli')
                    (seed / 'share/facman/facman.resources').write_bytes(original)
                    (seed / 'share/facman/manifest/product-stage.v1.json').write_bytes(b'{}')
                if label == 'installed-stage_relocated':
                    raise RuntimeError('stop after second independent relocation check')
                payload = dict(pack_sha256=proof.sha(original), package_profile='linux_product_x64',
                               package_manifest_sha256=proof.sha(b'{}'),
                               entries=['content/factorio/test.txt'], expanded_bytes=len(original))
                if label == 'portable_export':
                    destination = Path(command[3])
                    (destination / 'content/factorio').mkdir(parents=True)
                    (destination / 'content/factorio/test.txt').write_bytes(original)
                    output = dict(operation=dict(effects_may_have_occurred=True, outcome='completed',
                                                 recovery=dict(required=False)))
                elif label == 'portable_export_existing':
                    output = dict(operation=dict(effects_may_have_occurred=False, outcome='refused_before_effects',
                                                 recovery=dict(required=False)))
                elif label == 'portable_inspect_export':
                    output = dict(command='resources.export.inspect',
                                  operation=dict(effects_may_have_occurred=False, outcome='refused_before_effects',
                                                 recovery=dict(required=False)),
                                  payload=dict(scope='destination_type_and_identity_only', state='present'))
                else:
                    output = dict(payload=payload, error='resource_fixture')
                record = dict(exit_code=1 if label in (
                    'portable_missing', 'portable_truncated', 'portable_export_existing') else 0,
                              stdout=json.dumps(output), stderr='')
                records.append(record)
                return record

            arguments = ['proof', '--cli', str(cli), '--fixture', str(fixture),
                         '--work-root', str(root / 'runs')]
            with mock.patch.object(proof.sys, 'platform', 'linux'), \
                 mock.patch.object(proof.sys, 'argv', arguments), \
                 mock.patch.object(proof, 'capture', side_effect=capture), \
                 mock.patch('sys.stdout', new_callable=io.StringIO), \
                 mock.patch('sys.stderr', new_callable=io.StringIO):
                self.assertEqual(proof.main(), 1)
        self.assertIn('portable_inspect_export', labels)
        self.assertEqual(labels[-1], 'installed-stage_relocated')
        self.assertFalse(any(label.startswith('installed-stage_') and label != 'installed-stage_relocated'
                             for label in labels))

    def test_loader_exit_is_recorded_without_converting_it_to_timeout(self):
        records = []
        completed = subprocess.CompletedProcess(['fixture'], 0xc0000135, b'', b'')
        with mock.patch.object(proof, 'run_child', return_value=completed):
            result = proof.capture('missing-runtime', ['fixture'], records, timeout=8)
        self.assertEqual(result['exit_code'], 0xc0000135)
        self.assertFalse(result['timed_out'])
        self.assertEqual(records, [result])
        self.assertEqual(result['stdout_sha256'], proof.sha(b''))

    def test_timeout_retains_command_partial_output_and_failure(self):
        records = []
        error = subprocess.TimeoutExpired(['fixture'], 8, output=b'partial\xff', stderr=b'diagnostic')
        with mock.patch.object(proof, 'run_child', side_effect=error):
            with self.assertRaises(subprocess.TimeoutExpired):
                proof.capture('hung-child', ['fixture'], records, executable='actual', timeout=8)
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]['exit_code'])
        self.assertTrue(records[0]['timed_out'])
        self.assertEqual(records[0]['executable'], 'actual')
        self.assertEqual(records[0]['stdout_sha256'], proof.sha(b'partial\xff'))
        self.assertEqual(records[0]['stderr'], 'diagnostic')

    def test_windows_child_inherits_suppression_and_parent_mode_is_restored(self):
        for raises in (False, True):
            with self.subTest(raises=raises):
                kernel = mock.Mock()
                kernel.GetErrorMode.return_value = 0x4
                def child(*args, **kwargs):
                    self.assertEqual(kernel.SetErrorMode.call_args, mock.call(0x8007))
                    if raises:
                        raise OSError('creation refused')
                    return subprocess.CompletedProcess(args[0], 0, b'pass', b'')
                with mock.patch.object(proof.sys, 'platform', 'win32'), \
                     mock.patch.object(proof.ctypes, 'WinDLL', create=True, return_value=kernel), \
                     mock.patch.object(proof.subprocess, 'run', side_effect=child):
                    if raises:
                        with self.assertRaisesRegex(OSError, 'creation refused'):
                            proof.run_child(['fixture'])
                    else:
                        self.assertEqual(proof.run_child(['fixture']).returncode, 0)
                self.assertEqual(kernel.SetErrorMode.call_args_list, [mock.call(0x8007), mock.call(0x4)])

    def test_non_windows_runner_does_not_load_windows_api(self):
        completed = subprocess.CompletedProcess(['fixture'], 23, b'out', b'err')
        with mock.patch.object(proof.sys, 'platform', 'linux'), \
             mock.patch.object(proof.ctypes, 'WinDLL', create=True) as windows_api, \
             mock.patch.object(proof.subprocess, 'run', return_value=completed):
            self.assertIs(proof.run_child(['fixture'], timeout=8), completed)
            windows_api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
