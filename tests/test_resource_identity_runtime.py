# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Failure custody and noninteractive loader behavior for the actual CLI fixture."""
from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from tests.integration import resource_identity_runtime as proof


class ResourceIdentityRuntimeTests(unittest.TestCase):
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
