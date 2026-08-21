# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReproducibleBuildConfigurationTests(unittest.TestCase):
    def test_windows_portable_build_selects_static_msvc_runtime_after_detection(self) -> None:
        root_cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("cmake_policy(SET CMP0091 NEW)", root_cmake)
        self.assertIn("CMAKE_MSVC_RUNTIME_LIBRARY", root_cmake)
        self.assertIn('"MultiThreaded$<$<CONFIG:Debug>:Debug>"', root_cmake)
        self.assertIn('"msvc_runtime=${FACMAN_MSVC_RUNTIME_IDENTITY};"', root_cmake)
        self.assertLess(
            root_cmake.index("cmake_policy(SET CMP0091 NEW)"),
            root_cmake.index("project(facman"),
        )
        self.assertGreater(
            root_cmake.index("set(CMAKE_MSVC_RUNTIME_LIBRARY"),
            root_cmake.index("project(facman"),
        )
        self.assertLess(
            root_cmake.index("set(CMAKE_MSVC_RUNTIME_LIBRARY"),
            root_cmake.index("facman_configure_providers()"),
        )

    def test_msvc_debug_information_is_embedded_before_languages_enable(self) -> None:
        root_cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("cmake_policy(SET CMP0141 NEW)", root_cmake)
        self.assertIn("CMAKE_MSVC_DEBUG_INFORMATION_FORMAT", root_cmake)
        self.assertIn(":Debug,RelWithDebInfo>:Embedded", root_cmake)
        self.assertLess(
            root_cmake.index("cmake_policy(SET CMP0141 NEW)"),
            root_cmake.index("project(facman"),
        )
        self.assertIn('string(REPLACE "/Zi" "/Z7"', root_cmake)

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
            policy.index('"/pathmap:${_facman_native_binary_dir}=/_/build"'),
            policy.index('"/pathmap:${_facman_native_source_dir}=/_/src"'),
        )
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
