# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ULK_MAIN = "09f0639ab6529fba2f2aa22e9bf68e5eebed0553"


class UlkSessionProviderAdoptionTests(unittest.TestCase):
    def test_provider_is_exact_canonical_main_and_canary_is_retired(self) -> None:
        cmake = (ROOT / "cmake" / "FacManProviders.cmake").read_text(
            encoding="utf-8"
        )
        self.assertIn("UniversalLauncher 1.8.0 EXACT", cmake)
        self.assertIn("session/session_record.v1.schema.json", cmake)
        self.assertIn("session/session_list.v1.schema.json", cmake)
        self.assertIn("accepted_exact_main_session_provider", cmake)
        self.assertIn("was retired after canonical ULK session adoption", cmake)
        self.assertNotIn("_FACMAN_ULK_SESSION_CANARY_REVISION", cmake)
        self.assertNotIn("engineering_canary", cmake)

        workflow = (
            ROOT / ".github" / "workflows" / "provider-sdk-consumption.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(f"ref: {ULK_MAIN}", workflow)
        self.assertNotIn("ulk_session_consumer_canary.py", workflow)

        with (ROOT / "release/index/providers.lock.v2.toml").open("rb") as handle:
            providers = tomllib.load(handle)
        ulk = next(
            row
            for row in providers["provider"]
            if row["id"] == "universal_launcher"
        )
        self.assertEqual(ulk["source_revision"], ULK_MAIN)
        self.assertEqual(ulk["package_version"], "1.8.0")
        self.assertEqual(ulk["abi_version"], "1.9")
        self.assertIn("ulk.session_record.v1", ulk["contracts"])
        self.assertTrue(all(
            row["source_revision"] == ULK_MAIN and row["package_version"] == "1.8.0"
            for row in providers["sdk_package"]
            if row["provider_id"] == "universal_launcher"
        ))

        package_gate = (
            ROOT / "apps/gui/windows/winforms/PackagedBackendIdentity.cs"
        ).read_text(encoding="utf-8")
        self.assertIn(ULK_MAIN, package_gate)

    def test_default_provider_uses_public_abi_and_bounded_two_call_read(self) -> None:
        source = (
            ROOT / "runtime" / "factorio" / "application" / "last_run_provider.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn('#include "ulk/ulk_session.h"', source)
        self.assertEqual(source.count("ulk_session_journal_last_run_v1("), 2)
        self.assertIn("kMaximumLastRunJsonBytes", source)
        self.assertIn("latest_session_nonterminal", source)
        self.assertIn("record_corrupt_or_incompatible", source)
        self.assertIn("outcome_unknown", source)
        self.assertIn("recovery_required", source)
        self.assertIn("make_ulk_session_last_run_provider(workspace)", source)
        self.assertIn("ulk.session.journal.v1.authoritative", source)
        self.assertNotIn("LOCALAPPDATA", source)

    def test_live_frontends_cannot_reintroduce_last_run_cache_authority(self) -> None:
        paths = (
            ROOT / "apps/gui/windows/winforms/C1LivePresentationStore.cs",
            ROOT / "apps/gui/macos/appkit/FacManLivePresentation.m",
            ROOT / "apps/gui/linux/gtk/main.c",
        )
        retired = (
            "non_authoritative_view_copy",
            "completed_factorio_launch_session_v1",
            "frontend_last_run_cache",
            "presentation-cache.v0",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for marker in retired:
                self.assertNotIn(marker, text, path.as_posix())

        winforms = paths[0].read_text(encoding="utf-8")
        self.assertIn('PayloadAsync("presentation.query"', winforms)
        self.assertIn('Record(backendPresentation, "last_run")', winforms)
        self.assertIn("backendLastRun ?? UnavailableLastRun()", winforms)
        self.assertIn("backendLastRun = null;", winforms)
        self.assertIn("Authoritative Last Run unavailable", paths[1].read_text(encoding="utf-8"))
        self.assertIn("Authoritative Last Run unavailable", paths[2].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
