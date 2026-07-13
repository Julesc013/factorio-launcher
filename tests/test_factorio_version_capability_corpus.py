# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import factorio_version_capability_corpus as corpus


class FactorioVersionCapabilityCorpusTests(unittest.TestCase):
    def test_reported_version_accepts_old_and_new_banner_shapes(self) -> None:
        self.assertEqual(corpus.reported_version("Version: 0.6.4 (build 7245)"), "0.6.4")
        self.assertEqual(corpus.reported_version("Factorio 2.0.77"), "2.0.77")
        self.assertEqual(corpus.reported_version("no version banner"), "unknown")

    def test_help_capabilities_are_explicit_booleans(self) -> None:
        capabilities = corpus.help_capabilities(
            "--config PATH --mod-directory PATH --start-server SAVE --benchmark SAVE"
        )
        self.assertTrue(capabilities["config_option"])
        self.assertTrue(capabilities["mod_directory_option"])
        self.assertTrue(capabilities["start_server_option"])
        self.assertTrue(capabilities["benchmark_option"])
        self.assertFalse(capabilities["dump_data_option"])

    def test_metadata_version_is_a_bounded_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info = root / "data" / "base" / "info.json"
            info.parent.mkdir(parents=True)
            info.write_text('{"name":"base","version":"0.12.35"}\n', encoding="utf-8")
            self.assertEqual(corpus.metadata_version(root), "0.12.35")

    def test_tree_fingerprint_detects_metadata_changes_without_content_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "data" / "base" / "info.json"
            path.parent.mkdir(parents=True)
            path.write_text("{}\n", encoding="utf-8")
            before, count = corpus.tree_fingerprint(root)
            path.write_text('{"version":"2.0.77"}\n', encoding="utf-8")
            after, after_count = corpus.tree_fingerprint(root)
            self.assertEqual(count, after_count)
            self.assertNotEqual(before, after)

    def test_discover_executable_prefers_bounded_known_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "bin" / "x64" / "factorio.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"fixture")
            self.assertEqual(corpus.discover_executable(root), executable)


if __name__ == "__main__":
    unittest.main()
