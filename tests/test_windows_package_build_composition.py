# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.package import components, pipeline
from tools.package import staging


ROOT = Path(__file__).resolve().parents[1]
REVISIONS = {
    "factorio_launcher": "1" * 40,
    "universal_launcher": "2" * 40,
    "universal_setup": "3" * 40,
}


def build_identity(*, linkage: str = "static", facman: str | None = None) -> str:
    return ";".join(
        (
            f"facman={facman or REVISIONS['factorio_launcher']}",
            f"universal_launcher={REVISIONS['universal_launcher']}",
            f"universal_setup={REVISIONS['universal_setup']}",
            "provider_mode=source",
            f"provider_source_linkage={linkage}",
            "provider_lock_kind=tracked",
            "provider_conformance_only=false",
            "provider_sdk_consumption_candidate=false",
            "provider_candidate_differs_from_tracked=false",
            "provider_consumption_classification=tracked_source",
            "provider_release_identity_coherent=true",
            "source_dirty=false",
        )
    )


def write_build_root(
    root: Path,
    *,
    cache_linkage: str,
    identity_linkage: str | None = None,
    facman: str | None = None,
) -> None:
    root.mkdir(parents=True)
    (root / "CMakeCache.txt").write_text(
        "FACMAN_PROVIDER_MODE:STRING=source\n"
        f"FACMAN_PROVIDER_SOURCE_LINKAGE:STRING={cache_linkage}\n",
        encoding="utf-8",
    )
    (root / pipeline.CMAKE_BUILD_IDENTITY_FILENAME).write_text(
        build_identity(linkage=identity_linkage or cache_linkage, facman=facman) + "\n",
        encoding="utf-8",
    )


def profile_and_bundle(profile_id: str) -> tuple[dict[str, object], dict[str, object]]:
    _path, profile = pipeline.load_profile(profile_id)
    bundle_path = ROOT / str(profile["package_manifest"])
    return profile, pipeline.load_toml(bundle_path)


def install_contracts(install_root: Path) -> None:
    shutil.copytree(
        ROOT / "contracts" / "schema",
        install_root / "share" / "facman" / "contracts" / "schema",
    )


class WindowsPackageBuildCompositionTests(unittest.TestCase):
    def validate(self, profile_id: str, build_root: Path) -> None:
        profile, bundle = profile_and_bundle(profile_id)
        with (
            mock.patch.object(pipeline, "pinned_source_revisions", return_value=REVISIONS),
            mock.patch.object(pipeline, "git_dirty", return_value=False),
        ):
            pipeline.validate_build_composition(
                profile_id, profile, bundle, build_root
            )

    def test_profiles_bind_static_and_shared_build_roots_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            static = root / "static"
            shared = root / "shared"
            write_build_root(static, cache_linkage="static")
            write_build_root(shared, cache_linkage="shared")
            pipeline.validate_distinct_build_roots(static, shared)
            self.validate("windows_portable_cli_x64", static)
            self.validate("windows_portable_tui_x64", static)
            self.validate("windows_legacy_winforms_x64", shared)

    def test_winforms_package_from_static_root_is_refused_early(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "static"
            write_build_root(root, cache_linkage="static")
            with self.assertRaisesRegex(
                ValueError, "invalid package/build-root composition"
            ):
                self.validate("windows_legacy_winforms_x64", root)

    def test_static_and_shared_root_alias_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "must be distinct"):
                pipeline.validate_distinct_build_roots(root, root / ".")

    def test_mixed_static_shared_build_identity_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "shared"
            write_build_root(
                root, cache_linkage="shared", identity_linkage="static"
            )
            with self.assertRaisesRegex(ValueError, "mixed static/shared"):
                self.validate("windows_legacy_winforms_x64", root)

    def test_stale_and_wrong_provider_build_identities_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "shared"
            write_build_root(root, cache_linkage="shared", facman="9" * 40)
            with self.assertRaisesRegex(ValueError, "differs from package custody"):
                self.validate("windows_legacy_winforms_x64", root)

            identity_path = root / pipeline.CMAKE_BUILD_IDENTITY_FILENAME
            identity_path.write_text(
                build_identity(linkage="shared").replace(
                    REVISIONS["universal_launcher"], "8" * 40
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "differs from package custody"):
                self.validate("windows_legacy_winforms_x64", root)

    def test_static_install_refuses_shared_runtime_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            install = Path(temporary) / "install"
            install_contracts(install)
            leaked = install / "bin" / "flb_factorio.dll"
            leaked.parent.mkdir(parents=True)
            leaked.write_bytes(b"not-a-runtime")
            with self.assertRaisesRegex(ValueError, "unselected shared runtime"):
                pipeline.validate_install_composition(
                    "windows_portable_cli_x64", install
                )

    def test_shared_install_requires_each_runtime_and_exact_schema_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            install = Path(temporary) / "install"
            install_contracts(install)
            binary = install / "bin"
            binary.mkdir(parents=True)
            for name in ("ulk.dll", "usk.dll"):
                (binary / name).write_bytes(b"runtime")
            with self.assertRaisesRegex(ValueError, "flb_factorio_shared"):
                pipeline.validate_install_composition(
                    "windows_legacy_winforms_x64", install
                )
            (binary / "flb_factorio.dll").write_bytes(b"runtime")
            pipeline.validate_install_composition(
                "windows_legacy_winforms_x64", install
            )

            schema = install / "share" / "facman" / "contracts" / "schema"
            first = next(path for path in schema.rglob("*") if path.is_file())
            first.unlink()
            with self.assertRaisesRegex(ValueError, "schema inventory differs"):
                pipeline.validate_install_composition(
                    "windows_legacy_winforms_x64", install
                )

    def test_missing_schema_is_independently_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            install = Path(temporary) / "install"
            binary = install / "bin"
            binary.mkdir(parents=True)
            for name in ("ulk.dll", "usk.dll", "flb_factorio.dll"):
                (binary / name).write_bytes(b"runtime")
            with self.assertRaisesRegex(ValueError, "missing contracts/schema"):
                pipeline.validate_install_composition(
                    "windows_legacy_winforms_x64", install
                )

    def test_provider_runtime_resolution_has_no_source_tree_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            install = root / "install"
            source_tree = root / "provider-source"
            source_tree.mkdir()
            (source_tree / "ulk.dll").write_bytes(b"runtime")
            with self.assertRaisesRegex(ValueError, "install tree is missing"):
                components.resolve(install, "ulk_shared")

    def test_static_package_staging_selects_components_without_development(self) -> None:
        selected = pipeline.WINDOWS_PACKAGE_INSTALL_COMPONENTS[
            "windows_portable_cli_x64"
        ]
        self.assertIn("Runtime", selected)
        self.assertIn("Contracts", selected)
        self.assertNotIn("Development", selected)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "build"
            build.mkdir()
            (build / "Release").mkdir()
            (build / "Release" / "facman.exe").write_bytes(b"binary")
            with mock.patch.object(staging.subprocess, "run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = ""
                staging.install_tree(build, root / "install", components=selected)
            installed_components = [
                call.args[0][call.args[0].index("--component") + 1]
                for call in run.call_args_list
            ]
            self.assertEqual(installed_components, list(selected))


if __name__ == "__main__":
    unittest.main()
