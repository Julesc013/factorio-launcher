# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import windows_stable_build_root as stable


class WindowsStableBuildRootTests(unittest.TestCase):
    def test_drive_is_bounded_and_normalized(self) -> None:
        self.assertEqual("Q", stable.normalize_drive("q:"))
        for value in ("", "C", "AA", "1", "Q:\\"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                stable.normalize_drive(value)

    def test_working_directory_refuses_escape_and_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source").mkdir()
            self.assertEqual(
                Path("source"),
                stable.require_relative_working_directory(root, "source"),
            )
            self.assertEqual(
                Path("."), stable.require_relative_working_directory(root, ".")
            )
            for value in ("", "../outside", str(root), "source/../../outside"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    stable.require_relative_working_directory(root, value)

    def test_mapping_refuses_an_existing_drive_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            stable, "exclusive_drive", return_value=contextlib.nullcontext()
        ), mock.patch.object(
            stable, "logical_drive_present", return_value=True
        ), mock.patch.object(stable, "run_subst") as subst:
            with self.assertRaisesRegex(stable.StableBuildRootError, "already present"):
                with stable.stable_build_root(Path(temporary), "Q"):
                    self.fail("mapping must not be yielded")
            subst.assert_not_called()

    def test_mapping_is_verified_and_removed_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            stable, "exclusive_drive", return_value=contextlib.nullcontext()
        ), mock.patch.object(
            stable, "logical_drive_present", side_effect=(False, True, False)
        ), mock.patch.object(stable, "run_subst") as subst, mock.patch.object(
            stable.os.path, "samefile", return_value=True
        ):
            root = Path(temporary)
            with stable.stable_build_root(root, "Q") as logical:
                self.assertEqual("Q:\\", logical)
            self.assertEqual(
                [mock.call("Q", root), mock.call("Q", None)], subst.call_args_list
            )

    def test_mapping_is_removed_when_target_verification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            stable, "exclusive_drive", return_value=contextlib.nullcontext()
        ), mock.patch.object(
            stable, "logical_drive_present", side_effect=(False, True, False)
        ), mock.patch.object(stable, "run_subst") as subst, mock.patch.object(
            stable.os.path, "samefile", return_value=False
        ):
            root = Path(temporary)
            with self.assertRaisesRegex(stable.StableBuildRootError, "does not resolve"):
                with stable.stable_build_root(root, "Q"):
                    self.fail("unverified mapping must not be yielded")
            self.assertEqual(mock.call("Q", None), subst.call_args_list[-1])

    def test_execute_rewrites_only_the_explicit_root_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            stable,
            "stable_build_root",
            return_value=contextlib.nullcontext("Q:\\"),
        ), mock.patch.object(stable.subprocess, "run") as run:
            root = Path(temporary)
            (root / "source").mkdir()
            run.return_value.returncode = 0
            result = stable.execute(
                root,
                "Q",
                "source",
                ["cmake", "-S", stable.TOKEN + "\\source", "literal"],
            )
            self.assertEqual(0, result)
            run.assert_called_once_with(
                ["cmake", "-S", "Q:\\source", "literal"],
                cwd="Q:\\source",
                check=False,
            )


if __name__ == "__main__":
    unittest.main()
