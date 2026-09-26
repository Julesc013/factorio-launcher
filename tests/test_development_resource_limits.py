"""Check resource refusals before launching compilers or cloning providers."""
from __future__ import annotations
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from tools import dev, native_build, development_layout


class DevelopmentResourceLimitsTests(unittest.TestCase):
    def test_low_disk_refuses_before_provider_preparation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.dict(os.environ, {'FACMAN_MIN_FREE_GIB': '8'}), \
                 mock.patch.object(native_build.shutil, 'disk_usage', return_value=SimpleNamespace(free=2*1024**3)), \
                 mock.patch.object(dev.provider_workspace, 'prepare') as prepare, \
                 mock.patch.object(dev, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'reserve required'):
                    dev.configure_native(root/'build', root)
                prepare.assert_not_called()
                run.assert_not_called()

    def test_invalid_disk_threshold_is_refused(self):
        with mock.patch.dict(os.environ, {'FACMAN_MIN_FREE_GIB': 'nan'}):
            with self.assertRaises(ValueError):
                native_build.require_disk_reserve(Path('.'))

    def test_package_refuses_low_space_before_preparing_providers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = SimpleNamespace(task_root=str(root), profile='windows_product_portable',
                                   build_root=None, out=None, dist=None, allow_in_tree_output=False)
            development_layout.ensure_task_root(root, dev.ROOT, development_layout.current_task_id(dev.ROOT))
            with mock.patch.object(dev, 'prepare_task_root', return_value=root), \
                 mock.patch.dict(os.environ, {'FACMAN_MIN_FREE_GIB': '8'}), \
                 mock.patch.object(native_build.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024**3)), \
                 mock.patch.object(dev.provider_workspace, 'prepare') as prepare:
                with self.assertRaisesRegex(ValueError, 'reserve required'):
                    dev.package_command(args)
                prepare.assert_not_called()

    def test_unowned_external_output_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'owned task root'):
                dev.validate_external_output(Path(temporary)/'build', allow_in_tree=False)

    def test_output_cannot_use_another_tasks_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            development_layout.ensure_task_root(root, dev.ROOT, 'task/another-owner')
            with self.assertRaisesRegex(ValueError, 'another task'):
                dev.validate_external_output(root/'build', allow_in_tree=False)

    def test_visual_studio_limits_workers_and_releases_nodes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'CMakeCache.txt').write_text('CMAKE_GENERATOR:INTERNAL=Visual Studio 18 2026\n')
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(native_build.os, 'name', 'nt'):
                args = native_build.command(root, 'Debug', ['facman_cli'], {})
            self.assertEqual(args[args.index('--parallel')+1], '2')
            self.assertIn('/nr:false', args)
            self.assertIn('--clean-first', args)

    def test_explicit_worker_limit_and_invalid_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.dict(os.environ, {'CMAKE_BUILD_PARALLEL_LEVEL': '1'}):
                args = native_build.command(root, 'Debug', [], {})
                self.assertEqual(args[args.index('--parallel')+1], '1')
            with mock.patch.dict(os.environ, {'CMAKE_BUILD_PARALLEL_LEVEL': '0'}):
                with self.assertRaises(ValueError):
                    native_build.command(root, 'Debug', [], {})
