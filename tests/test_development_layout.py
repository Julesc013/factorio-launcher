# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import development_layout, workspace_hygiene


class DevelopmentLayoutTests(unittest.TestCase):
    def test_task_root_is_external_and_branch_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            external = Path(temporary) / "development"
            with mock.patch.dict("os.environ", {"FACMAN_DEV_ROOT": str(external)}, clear=False):
                first = development_layout.task_root(source, "task/alpha")
                second = development_layout.task_root(source, "task/beta")
            self.assertNotEqual(first, second)
            self.assertFalse(first.is_relative_to(source))
            self.assertTrue(first.is_relative_to(external.resolve()))

    def test_explicit_task_root_overrides_portable_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            configured = Path(temporary) / "explicit-task"
            source.mkdir()
            with mock.patch.dict(
                "os.environ", {"FACMAN_TASK_ROOT": str(configured)}, clear=False
            ):
                self.assertEqual(
                    development_layout.default_task_root(source),
                    configured.resolve(),
                )

    def test_marker_refuses_existing_unowned_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            target = Path(temporary) / "target"
            source.mkdir()
            target.mkdir()
            (target / "unknown.txt").write_text("preserve", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unowned development task root"):
                development_layout.ensure_task_root(target, source, "TASK-01")

    def test_marker_binds_repository_and_task(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            target = Path(temporary) / "target"
            source.mkdir()
            development_layout.ensure_task_root(target, source, "TASK-01")
            marker = json.loads(
                (target / development_layout.MARKER_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(marker["schema"], development_layout.MARKER_SCHEMA)
            self.assertEqual(marker["task_id"], "TASK-01")
            with self.assertRaisesRegex(ValueError, "marker mismatch"):
                development_layout.ensure_task_root(target, source, "TASK-02")

    def test_cleanup_marker_must_remain_at_its_canonical_task_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            external = Path(temporary) / "development"
            source.mkdir()
            with mock.patch.dict(
                "os.environ", {"FACMAN_DEV_ROOT": str(external)}, clear=False
            ):
                original = development_layout.task_root(source, "TASK-01")
                moved = development_layout.task_root(source, "TASK-02")
                development_layout.ensure_task_root(original, source, "TASK-01")
                original.rename(moved)
                with self.assertRaisesRegex(ValueError, "path mismatch"):
                    development_layout.read_marker(moved, source)

    def test_legacy_cleanup_refuses_source_and_unrecognized_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            allowed = Path(temporary)
            unknown = allowed / "important-project"
            unknown.mkdir()
            with self.assertRaisesRegex(ValueError, "not recognized as disposable"):
                workspace_hygiene.validate_legacy_path(unknown, [allowed], False)
            with self.assertRaisesRegex(ValueError, "protected"):
                workspace_hygiene.validate_legacy_path(
                    workspace_hygiene.ROOT,
                    [workspace_hygiene.ROOT.parent],
                    False,
                )

    def test_legacy_cleanup_requires_acknowledgement_before_apply(self) -> None:
        args = mock.Mock(
            apply=True,
            acknowledge_unowned=False,
            allowed_root=[],
            path=[],
            allow_filesystem_root=False,
        )
        with self.assertRaisesRegex(ValueError, "acknowledge-unowned"):
            workspace_hygiene.command_legacy_clean(args)

    def test_legacy_discovery_is_direct_recognized_and_excludable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            allowed = Path(temporary)
            disposable = allowed / "facman-old-build"
            excluded = allowed / "FacManPrivateRoute"
            unrelated = allowed / "important-project"
            disposable.mkdir()
            excluded.mkdir()
            unrelated.mkdir()
            args = mock.Mock(
                apply=False,
                acknowledge_unowned=False,
                allowed_root=[str(allowed)],
                path=[],
                discover_direct_children=True,
                exclude_name=[excluded.name],
                allow_filesystem_root=False,
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(workspace_hygiene.command_legacy_clean(args), 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(
                [record["path"] for record in payload["targets"]],
                [str(disposable.resolve())],
            )

    def test_legacy_prune_preserves_named_direct_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            allowed = Path(temporary)
            root = allowed / "facman-old-root"
            preserved = root / "FacManRoute"
            disposable = root / "old-build"
            preserved.mkdir(parents=True)
            disposable.mkdir()
            (preserved / "input.zip").write_text("keep", encoding="utf-8")
            (disposable / "output.zip").write_text("remove", encoding="utf-8")
            args = mock.Mock(
                apply=True,
                acknowledge_unowned=True,
                allowed_root=[str(allowed)],
                path=str(root),
                preserve_child_name=[preserved.name],
                allow_filesystem_root=False,
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(workspace_hygiene.command_legacy_prune(args), 0)
            self.assertTrue(preserved.is_dir())
            self.assertFalse(disposable.exists())

    def test_legacy_prune_refuses_a_missing_preservation_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            allowed = Path(temporary)
            root = allowed / "facman-old-root"
            disposable = root / "old-build"
            disposable.mkdir(parents=True)
            args = mock.Mock(
                apply=True,
                acknowledge_unowned=True,
                allowed_root=[str(allowed)],
                path=str(root),
                preserve_child_name=["FacManRoute"],
                allow_filesystem_root=False,
            )
            with self.assertRaisesRegex(ValueError, "does not exist"):
                workspace_hygiene.command_legacy_prune(args)
            self.assertTrue(disposable.is_dir())


if __name__ == "__main__":
    unittest.main()
