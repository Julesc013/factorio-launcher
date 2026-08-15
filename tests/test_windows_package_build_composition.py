# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import tomllib
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


def build_identity(
    *,
    linkage: str = "static",
    facman: str | None = None,
    ulk_session_consumer_canary: bool = False,
    provider_class: str = "canonical",
    universal_launcher: str | None = None,
    universal_setup: str | None = None,
) -> str:
    canary = provider_class == "repaired_provider_canary"
    return ";".join(
        (
            f"facman={facman or REVISIONS['factorio_launcher']}",
            f"universal_launcher={universal_launcher or REVISIONS['universal_launcher']}",
            f"universal_setup={universal_setup or REVISIONS['universal_setup']}",
            "provider_mode=source",
            f"provider_source_linkage={linkage}",
            "provider_lock_kind=" + ("sdk_candidate" if canary else "tracked"),
            "provider_conformance_only=false",
            "provider_sdk_consumption_candidate=" + str(canary).lower(),
            "provider_candidate_differs_from_tracked=" + str(canary).lower(),
            "provider_consumption_classification="
            + ("sdk_candidate_source" if canary else "tracked_source"),
            "provider_release_identity_coherent=" + str(not canary).lower(),
            "ulk_session_consumer_canary="
            + str(ulk_session_consumer_canary).lower(),
            "msvc_runtime=static",
            "source_dirty=false",
        )
    )


def write_build_root(
    root: Path,
    *,
    cache_linkage: str,
    identity_linkage: str | None = None,
    facman: str | None = None,
    provider_class: str = "canonical",
    universal_launcher: str | None = None,
    universal_setup: str | None = None,
) -> None:
    root.mkdir(parents=True)
    (root / "CMakeCache.txt").write_text(
        "FACMAN_PROVIDER_MODE:STRING=source\n"
        f"FACMAN_PROVIDER_SOURCE_LINKAGE:STRING={cache_linkage}\n",
        encoding="utf-8",
    )
    (root / pipeline.CMAKE_BUILD_IDENTITY_FILENAME).write_text(
        build_identity(
            linkage=identity_linkage or cache_linkage,
            facman=facman,
            provider_class=provider_class,
            universal_launcher=universal_launcher,
            universal_setup=universal_setup,
        ) + "\n",
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
    def validate(
        self,
        profile_id: str,
        build_root: Path,
        *,
        source_revisions: dict[str, str] | None = None,
        provider_class: str = "canonical",
    ) -> None:
        profile, bundle = profile_and_bundle(profile_id)
        with (
            mock.patch.object(pipeline, "pinned_source_revisions", return_value=REVISIONS),
            mock.patch.object(pipeline, "git_dirty", return_value=False),
        ):
            pipeline.validate_build_composition(
                profile_id,
                profile,
                bundle,
                build_root,
                source_revisions=source_revisions,
                provider_class=provider_class,
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

    def test_ulk_session_consumer_canary_build_identity_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "static"
            write_build_root(root, cache_linkage="static")
            identity_path = root / pipeline.CMAKE_BUILD_IDENTITY_FILENAME
            identity_path.write_text(
                build_identity(ulk_session_consumer_canary=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "ulk_session_consumer_canary"):
                self.validate("windows_portable_cli_x64", root)

    def test_repaired_provider_canary_requires_exact_candidate_identity(self) -> None:
        candidate_ulk = "7" * 40
        candidate_revisions = {**REVISIONS, "universal_launcher": candidate_ulk}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "shared"
            write_build_root(
                root,
                cache_linkage="shared",
                provider_class="repaired_provider_canary",
                universal_launcher=candidate_ulk,
            )
            self.validate(
                "windows_legacy_winforms_x64",
                root,
                source_revisions=candidate_revisions,
                provider_class="repaired_provider_canary",
            )
            with self.assertRaisesRegex(ValueError, "differs from package custody"):
                self.validate("windows_legacy_winforms_x64", root)

            with self.assertRaisesRegex(ValueError, "differs from package custody"):
                self.validate(
                    "windows_legacy_winforms_x64",
                    root,
                    source_revisions={**candidate_revisions, "universal_launcher": "8" * 40},
                    provider_class="repaired_provider_canary",
                )

    def test_canary_revision_must_be_exact_and_noncanonical(self) -> None:
        with self.assertRaisesRegex(ValueError, "exact 40-character"):
            pipeline.repaired_provider_canary_revisions(REVISIONS, "short")
        with self.assertRaisesRegex(ValueError, "differ from the tracked"):
            pipeline.repaired_provider_canary_revisions(
                REVISIONS, REVISIONS["universal_launcher"]
            )
        candidate = pipeline.repaired_provider_canary_revisions(REVISIONS, "7" * 40)
        self.assertEqual(candidate["universal_launcher"], "7" * 40)
        self.assertEqual(
            REVISIONS["universal_launcher"],
            "2" * 40,
            "candidate projection must not mutate tracked revisions",
        )

    def test_canary_source_trees_come_from_exact_candidate_lock(self) -> None:
        candidate = {
            **REVISIONS,
            "universal_launcher": "7" * 40,
        }
        trees = {
            "universal_launcher": "8" * 40,
            "universal_setup": "9" * 40,
        }
        required_refs = {
            "universal_launcher": "refs/heads/task/ulk-repair",
            "universal_setup": "refs/heads/main",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "build"
            lock = root / "candidate.lock.v1.toml"
            write_build_root(
                build,
                cache_linkage="shared",
                provider_class="repaired_provider_canary",
                universal_launcher=candidate["universal_launcher"],
            )
            with (build / "CMakeCache.txt").open("a", encoding="utf-8") as stream:
                stream.write(f"FACMAN_PROVIDER_LOCK_FILE:FILEPATH={lock.as_posix()}\n")
            lock.write_text(
                'schema = "facman.provider_sdk_consumption_lock.v1"\n'
                + "\n".join(
                    (
                        "[[component]]",
                        'id = "universal_launcher"',
                        f'pin = "{candidate["universal_launcher"]}"',
                        f'tree = "{trees["universal_launcher"]}"',
                        f'required_ref = "{required_refs["universal_launcher"]}"',
                        "",
                        "[[component]]",
                        'id = "universal_setup"',
                        f'pin = "{candidate["universal_setup"]}"',
                        f'tree = "{trees["universal_setup"]}"',
                        f'required_ref = "{required_refs["universal_setup"]}"',
                        "",
                    )
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                pipeline.repaired_provider_canary_source_bindings(build, candidate),
                (trees, required_refs),
            )

    def test_canary_metadata_records_override_without_mutating_tracked_lock(self) -> None:
        candidate_ulk = "7" * 40
        candidate_ulk_tree = "8" * 40
        tracked = pipeline.pinned_source_revisions()
        candidate = {**tracked, "universal_launcher": candidate_ulk}
        candidate_trees = {
            "universal_launcher": candidate_ulk_tree,
            "universal_setup": "9" * 40,
        }
        candidate_refs = {
            "universal_launcher": "refs/heads/task/ulk-repair",
            "universal_setup": "refs/heads/main",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            packaged_lock = package / "release/index/workspace_lock.v1.toml"
            packaged_lock.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "release/index/workspace_lock.v1.toml", packaged_lock)
            build = root / "build"
            write_build_root(
                build,
                cache_linkage="shared",
                provider_class="repaired_provider_canary",
                universal_launcher=candidate_ulk,
                universal_setup=tracked["universal_setup"],
                facman=tracked["factorio_launcher"],
            )
            pipeline.write_packaged_canary_workspace_lock(
                package,
                candidate,
                candidate_trees,
                candidate_refs,
            )
            with packaged_lock.open("rb") as handle:
                package_components = {
                    row["id"]: row
                    for row in tomllib.load(handle)["component"]
                }
            self.assertEqual(
                package_components["universal_launcher"]["pin"], candidate_ulk
            )
            self.assertEqual(
                package_components["universal_launcher"]["tree"], candidate_ulk_tree
            )
            self.assertEqual(
                package_components["universal_setup"]["pin"],
                tracked["universal_setup"],
            )
            self.assertEqual(
                package_components["universal_setup"]["tree"],
                candidate_trees["universal_setup"],
            )
            self.assertEqual(
                package_components["universal_launcher"]["required_ref"],
                candidate_refs["universal_launcher"],
            )
            with mock.patch.object(pipeline, "git_dirty", return_value=False):
                pipeline.write_repaired_provider_canary_metadata(
                    package,
                    candidate,
                    candidate_trees,
                    candidate_refs,
                    tracked,
                    build,
                )
            record = json.loads(
                (package / "manifest" / pipeline.REPAIRED_PROVIDER_CANARY_RECORD)
                .read_text(encoding="utf-8")
            )
            self.assertEqual(record["classification"], "noncanonical_engineering_candidate")
            self.assertEqual(record["source_revisions"]["universal_launcher"], candidate_ulk)
            self.assertEqual(record["source_trees"], candidate_trees)
            self.assertEqual(record["required_refs"], candidate_refs)
            self.assertEqual(
                record["build_identity_sha256"],
                hashlib.sha256(
                    (build / pipeline.CMAKE_BUILD_IDENTITY_FILENAME).read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                record["canonical_provider_revisions"]["universal_launcher"],
                tracked["universal_launcher"],
            )
            self.assertFalse(any(record["authority"].values()))

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
