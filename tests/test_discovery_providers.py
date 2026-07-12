# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "runtime" / "factorio" / "discovery"


class DiscoveryProviderContractTests(unittest.TestCase):
    def test_provider_modules_are_bounded_and_read_only(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(DISCOVERY.glob("provider_*.cpp"))
        )
        for forbidden in ("sudo", "apt ", "dnf ", "pacman ", "brew ", "system(", "popen("):
            self.assertNotIn(forbidden, combined)
        service = (DISCOVERY / "flb_factorio_discovery.cpp").read_text(encoding="utf-8")
        for anchor in (
            "kMaximumProviderRoots",
            "kMaximumCandidates",
            "kMaximumDirectoryEntries",
            "kMaximumElapsed",
            "symlink_status",
        ):
            self.assertIn(anchor, service)

    def test_linux_provider_covers_bounded_native_layouts(self) -> None:
        text = (DISCOVERY / "provider_linux.cpp").read_text(encoding="utf-8")
        for anchor in (".local", ".steam", "com.valvesoftware.Steam", "/opt/factorio", "libraryfolders.vdf"):
            self.assertIn(anchor, text)

    def test_macos_provider_covers_app_and_steam_layouts(self) -> None:
        text = (DISCOVERY / "provider_macos.cpp").read_text(encoding="utf-8")
        for anchor in ("Applications", "Factorio.app", "Application Support", "libraryfolders.vdf"):
            self.assertIn(anchor, text)

    def test_candidate_contract_exposes_provenance_and_evidence(self) -> None:
        header = (DISCOVERY / "flb_factorio_discovery.h").read_text(encoding="utf-8")
        implementation = (DISCOVERY / "flb_factorio_discovery.cpp").read_text(encoding="utf-8")
        self.assertIn("std::string provider_id", header)
        self.assertIn("std::vector<std::string> evidence", header)
        self.assertIn('output.add_string("provider_id"', implementation)
        self.assertIn('output.add_array("evidence"', implementation)


if __name__ == "__main__":
    unittest.main()
