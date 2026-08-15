# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReproducibleBuildConfigurationTests(unittest.TestCase):
    def test_msvc_policy_applies_reproducible_compile_and_link_options(self) -> None:
        policy = (ROOT / "cmake/FacManPolicies.cmake").read_text(encoding="utf-8")

        self.assertIn("/experimental:deterministic", policy)
        self.assertIn('"/pathmap:${_facman_native_source_dir}=/_/src"', policy)
        self.assertIn('"/pathmap:${_facman_native_binary_dir}=/_/build"', policy)
        self.assertIn(
            '"/pathmap:${_facman_native_ulk_source_dir}=/_/providers/universal-launcher"',
            policy,
        )
        self.assertIn(
            '"/pathmap:${_facman_native_usk_source_dir}=/_/providers/universal-setup"',
            policy,
        )
        self.assertIn(
            "add_compile_options(${_facman_msvc_reproducible_compile_options})",
            policy,
        )
        self.assertIn("add_link_options(/Brepro /INCREMENTAL:NO)", policy)
        self.assertLess(
            policy.index(
                "add_compile_options(${_facman_msvc_reproducible_compile_options})"
            ),
            policy.index("function(facman_apply_policies"),
        )

    def test_release_winforms_build_is_deterministic_and_path_mapped(self) -> None:
        project = (
            ROOT / "apps/gui/windows/winforms/FacMan.WinForms.csproj"
        ).read_text(encoding="utf-8")

        self.assertIn("<Deterministic>true</Deterministic>", project)
        self.assertIn(
            "<PathMap>$(MSBuildProjectDirectory)=/_/src/apps/gui/windows/winforms</PathMap>",
            project,
        )


if __name__ == "__main__":
    unittest.main()
