# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import clang_tidy_changed


class ClangTidyChangedTests(unittest.TestCase):
    def test_compilation_database_resolves_relative_and_absolute_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = root / "relative.cpp"
            absolute = root / "absolute.cpp"
            database = root / "compile_commands.json"
            database.write_text(
                json.dumps(
                    [
                        {"directory": str(root), "file": relative.name, "command": "c++"},
                        {"directory": str(root / "unused"), "file": str(absolute), "command": "c++"},
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                {relative.resolve(), absolute.resolve()},
                clang_tidy_changed.compilation_database_sources(database),
            )

    def test_selection_skips_only_known_platform_exclusive_sources(self) -> None:
        posix = clang_tidy_changed.ROOT / "runtime/platform/fl_process_supervisor_posix.cpp"
        windows = clang_tidy_changed.ROOT / "runtime/platform/fl_process_supervisor_windows.cpp"
        ordinary = clang_tidy_changed.ROOT / "runtime/core/json/fl_json.cpp"

        selected, platform_exclusive, missing = clang_tidy_changed.select_compiled_sources(
            [posix, windows, ordinary],
            {posix.resolve()},
            {"runtime/platform/fl_process_supervisor_windows.cpp"},
        )

        self.assertEqual([posix], selected)
        self.assertEqual([windows], platform_exclusive)
        self.assertEqual([ordinary], missing)

    def test_host_omissions_do_not_hide_missing_native_platform_sources(self) -> None:
        self.assertNotIn(
            "runtime/platform/fl_process_supervisor_posix.cpp",
            clang_tidy_changed.platform_omissions("linux"),
        )
        self.assertNotIn(
            "runtime/platform/fl_process_supervisor_windows.cpp",
            clang_tidy_changed.platform_omissions("win32"),
        )
        self.assertNotIn(
            "runtime/platform/fl_random_macos.cpp",
            clang_tidy_changed.platform_omissions("darwin"),
        )

    def test_invalid_compilation_database_shape_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "compile_commands.json"
            database.write_text(json.dumps({"file": "not-an-array.cpp"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must contain an array"):
                clang_tidy_changed.compilation_database_sources(database)


if __name__ == "__main__":
    unittest.main()
