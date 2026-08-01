# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import plistlib
import tomllib
import unittest
from pathlib import Path

from tools import classic_preview_shell_check, generate_classic_preview_rpc

ROOT = Path(__file__).resolve().parents[1]


class ClassicPreviewShellTests(unittest.TestCase):
    def test_native_shell_contract(self) -> None:
        self.assertEqual(classic_preview_shell_check.validate(), [])

    def test_generated_gtk_rpc_encoder_is_current(self) -> None:
        for path, expected in generate_classic_preview_rpc.render().items():
            self.assertEqual(path.read_text(encoding="utf-8"), expected)
        source = (
            ROOT / "apps/gui/linux/gtk/generated_rpc_request.c"
        ).read_text(encoding="utf-8")
        self.assertIn("facman_preview_json_escape", source)
        self.assertIn("g_get_monotonic_time", source)
        self.assertNotIn("g_strescape", source)

    def test_gtk_async_result_outlives_window_and_timeout_kills_helper(self) -> None:
        main = (ROOT / "apps/gui/linux/gtk/main.c").read_text(encoding="utf-8")
        client = (ROOT / "apps/gui/linux/gtk/command_client.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("g_object_ref(shell->rpc_result)", main)
        self.assertIn("g_object_unref(buffer)", main)
        self.assertIn("g_subprocess_force_exit(call->process)", client)

    def test_gtk_application_flags_cover_old_and_current_glib(self) -> None:
        main = (ROOT / "apps/gui/linux/gtk/main.c").read_text(encoding="utf-8")
        self.assertIn("GLIB_CHECK_VERSION(2, 74, 0)", main)
        self.assertIn("G_APPLICATION_DEFAULT_FLAGS", main)
        self.assertIn("G_APPLICATION_FLAGS_NONE", main)
        self.assertIn("FACMAN_APPLICATION_FLAGS", main)

    def test_appkit_is_an_x64_10_13_bundle_prototype(self) -> None:
        root = ROOT / "apps/gui/macos/appkit"
        with (root / "Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
        self.assertEqual(info["CFBundleExecutable"], "FacMan")
        self.assertEqual(info["LSMinimumSystemVersion"], "10.13")
        self.assertEqual(info["LSArchitecturePriority"], ["x86_64"])
        cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("MACOSX_BUNDLE", cmake)
        self.assertIn("install(TARGETS FacMan BUNDLE", cmake)

    def test_gtk_package_entrypoint_matches_release_profile(self) -> None:
        with (ROOT / "release/profiles/linux_x11_gtk_x64/profile.toml").open("rb") as handle:
            profile = tomllib.load(handle)
        self.assertEqual(profile["entrypoints"]["gui"], "usr/bin/facman-gui-gtk")
        meson = (ROOT / "apps/gui/linux/gtk/meson.build").read_text(encoding="utf-8")
        desktop = (ROOT / "apps/gui/linux/gtk/io.github.julesc013.facman.preview.desktop").read_text(
            encoding="utf-8"
        )
        self.assertIn("executable('facman-gui-gtk'", meson)
        self.assertIn("facman-live-presentation-payload-scope", meson)
        self.assertIn("Exec=facman-gui-gtk", desktop)

    def test_preview_profiles_do_not_claim_runtime_qualification(self) -> None:
        for profile_id in ("macos_legacy_appkit_x64", "linux_x11_gtk_x64"):
            with (ROOT / f"release/profiles/{profile_id}/profile.toml").open("rb") as handle:
                profile = tomllib.load(handle)
            self.assertEqual(profile["support_tier"], "package_preview")
            self.assertTrue(
                "no_runtime_qualification" in profile["runtime_claim"]
                or "no_bundle_runtime_proof" in profile["runtime_claim"]
            )


if __name__ == "__main__":
    unittest.main()
