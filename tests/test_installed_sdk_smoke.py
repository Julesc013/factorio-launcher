# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import installed_sdk_smoke


class InstalledSdkSmokeTests(unittest.TestCase):
    def test_sanitized_parent_links_consumer_to_sanitizer_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "CMakeCache.txt"
            cache.write_text(
                "FACMAN_ENABLE_SANITIZERS:BOOL=ON\n",
                encoding="utf-8",
            )

            self.assertEqual(
                ["-DFACMAN_CONSUMER_SANITIZERS=ON"],
                installed_sdk_smoke.consumer_parent_configuration(cache),
            )

    def test_regular_parent_does_not_instrument_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "CMakeCache.txt"
            cache.write_text(
                "FACMAN_ENABLE_SANITIZERS:BOOL=OFF\n",
                encoding="utf-8",
            )

            self.assertEqual([], installed_sdk_smoke.consumer_parent_configuration(cache))


if __name__ == "__main__":
    unittest.main()
