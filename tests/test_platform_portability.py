# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "runtime" / "platform"


class PlatformPortabilityTests(unittest.TestCase):
    def test_secure_randomness_has_explicit_target_sources(self) -> None:
        cmake = (PLATFORM / "CMakeLists.txt").read_text(encoding="utf-8")
        shared = (PLATFORM / "fl_system_services.cpp").read_text(encoding="utf-8")
        for name in ["fl_random_windows.cpp", "fl_random_linux.cpp", "fl_random_macos.cpp"]:
            self.assertIn(name, cmake)
            self.assertTrue((PLATFORM / name).is_file())
        self.assertNotIn("sys/random.h", shared)
        self.assertNotIn("getrandom(", shared)
        self.assertIn("message(FATAL_ERROR", cmake)

    def test_durable_io_reports_platform_guarantee_level(self) -> None:
        header = (PLATFORM / "fl_file_io.h").read_text(encoding="utf-8")
        source = (PLATFORM / "fl_file_io.cpp").read_text(encoding="utf-8")
        for value in [
            "file_flushed",
            "file_and_directory_flushed",
            "best_effort_platform_limit",
            "unsupported_filesystem",
        ]:
            self.assertIn(value, header)
        self.assertIn("DurabilityLevel::file_and_directory_flushed", source)
        self.assertIn("DurabilityLevel::best_effort_platform_limit", source)


if __name__ == "__main__":
    unittest.main()
