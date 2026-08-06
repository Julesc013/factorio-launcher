# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = (ROOT / "cmake" / "FacManProviders.cmake").read_text(encoding="utf-8")
TOP_LEVEL = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
INSTALL = (ROOT / "cmake" / "FacManInstall.cmake").read_text(encoding="utf-8")
WORKFLOWS = {
    name: (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
    for name in ("ci.yml", "codeql.yml", "release.yml")
}
AUTHORITY_KEYS = (
    "credentials",
    "factorio_execution",
    "observer_capture",
    "permit_issuance",
    "product_execution",
    "provider_adoption",
    "publication",
    "route_promotion",
    "setup_mutation",
    "signing",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked_provider_pins() -> tuple[str, str]:
    with (ROOT / "release/index/workspace_lock.v1.toml").open("rb") as handle:
        lock = tomllib.load(handle)
    components = {component["id"]: component["pin"] for component in lock["component"]}
    return components["universal_launcher"], components["universal_setup"]


def run_cmake_script(body: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temporary:
        script = Path(temporary) / "provider-mode-test.cmake"
        script.write_text(
            f'include("{(ROOT / "cmake/FacManProviders.cmake").as_posix()}")\n' + body,
            encoding="utf-8",
        )
        return subprocess.run(
            ["cmake", "-P", str(script)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )


def run_cmake_project(body: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "source"
        build = Path(temporary) / "build"
        source.mkdir()
        (source / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(provider_custody_fixture NONE)\n"
            f'include("{(ROOT / "cmake/FacManProviders.cmake").as_posix()}")\n' + body,
            encoding="utf-8",
        )
        return subprocess.run(
            ["cmake", "-G", "Ninja", "-S", str(source), "-B", str(build)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )


def candidate_lock(
    authority_lines: list[str],
    *,
    pins: tuple[str, str] = ("1" * 40, "2" * 40),
    candidate_differs: bool = True,
) -> str:
    components = []
    for provider_id, source, pin in (
        ("universal_launcher", "universal-launcher", pins[0]),
        ("universal_setup", "universal-setup", pins[1]),
    ):
        components.extend(
            [
                "[[component]]",
                f'id = "{provider_id}"',
                f'source = "{source}"',
                f'pin = "{pin}"',
                f'tree = "{pin}"',
                f'remote = "https://example.invalid/{source}.git"',
                'required_ref = "refs/heads/main"',
                "",
            ]
        )
    return "\n".join(
        [
            'schema = "facman.provider_conformance_lock.v1"',
            'id = "facman_provider_conformance_candidate_v1"',
            "conformance_only = true",
            "sdk_consumption_candidate = false",
            "candidate_not_adopted = true",
            "release_eligible = false",
            "tracked_lock_mutated = false",
            "candidate_differs_from_tracked = "
            f"{'true' if candidate_differs else 'false'}",
            "",
            *components,
            "[authority]",
            *authority_lines,
            "",
        ]
    )


class FacManProviderModeTests(unittest.TestCase):
    def test_mode_is_a_closed_enum_and_enters_build_identity(self) -> None:
        policy = "cmake_policy(SET CMP0057 NEW)"
        mode_check = "FACMAN_PROVIDER_MODE IN_LIST _FACMAN_PROVIDER_MODES"
        self.assertIn(policy, PROVIDERS)
        self.assertLess(PROVIDERS.index(policy), PROVIDERS.index(mode_check))
        self.assertIn(
            "set(_FACMAN_PROVIDER_MODES source installed_static installed_shared)",
            PROVIDERS,
        )
        self.assertIn(mode_check, PROVIDERS)
        self.assertIn('"provider_mode=${FACMAN_PROVIDER_MODE};"', TOP_LEVEL)
        self.assertIn('"provider_lock_kind=${FACMAN_PROVIDER_LOCK_KIND};"', TOP_LEVEL)
        self.assertIn(
            '"provider_conformance_only=${FACMAN_PROVIDER_CONFORMANCE_IDENTITY};"',
            TOP_LEVEL,
        )
        self.assertIn(
            '"provider_candidate_differs_from_tracked=${FACMAN_PROVIDER_CANDIDATE_DIFFERS_FROM_TRACKED};"',
            TOP_LEVEL,
        )
        self.assertIn(
            '"provider_consumption_classification=${FACMAN_PROVIDER_CONSUMPTION_CLASSIFICATION};"',
            TOP_LEVEL,
        )
        self.assertIn(
            '"provider_release_identity_coherent='
            '${FACMAN_PROVIDER_RELEASE_IDENTITY_COHERENCE};"',
            TOP_LEVEL,
        )

    def test_source_mode_has_only_exact_provider_roots(self) -> None:
        self.assertIn("FLAUNCH_UNIVERSAL_LAUNCHER_ROOT", PROVIDERS)
        self.assertIn("FLAUNCH_UNIVERSAL_SETUP_ROOT", PROVIDERS)
        self.assertIn(
            "${cache_var} is required in source mode; no sibling or "
            "workspace-root fallback is permitted",
            PROVIDERS,
        )
        self.assertIn(
            'COMMAND git -c "safe.directory=${repo_root}" rev-parse HEAD', PROVIDERS
        )
        self.assertIn("refs/remotes/origin/${required_branch}", PROVIDERS)
        self.assertNotIn("safe.directory --add", PROVIDERS)
        self.assertIn("does not match selected lock", PROVIDERS)
        for forbidden in (
            "FLAUNCH_WORKSPACE_ROOT",
            "FLAUNCH_UNIVERSAL_ROOT",
            '"${CMAKE_CURRENT_SOURCE_DIR}/../${repo_name}"',
            "facman_find_repo_root",
            "facman_append_env_candidate",
        ):
            self.assertNotIn(forbidden, TOP_LEVEL + PROVIDERS)

    def test_source_provider_installs_are_excluded_only_for_sdk_candidates(
        self,
    ) -> None:
        self.assertIn("set(ULK_BUILD_APPS OFF CACHE BOOL \"\" FORCE)", PROVIDERS)
        self.assertIn("set(ULK_BUILD_TESTS OFF CACHE BOOL \"\" FORCE)", PROVIDERS)
        self.assertIn("set(ULK_BUILD_SHARED ON CACHE BOOL \"\" FORCE)", PROVIDERS)
        self.assertIn("set(USK_BUILD_APPS OFF CACHE BOOL \"\" FORCE)", PROVIDERS)
        self.assertIn("set(USK_BUILD_TESTS OFF CACHE BOOL \"\" FORCE)", PROVIDERS)
        self.assertIn("set(USK_BUILD_FUZZERS OFF CACHE BOOL \"\" FORCE)", PROVIDERS)
        self.assertIn("set(USK_BUILD_SHARED ON CACHE BOOL \"\" FORCE)", PROVIDERS)
        self.assertRegex(
            PROVIDERS,
            r"if\(FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE\)\s+"
            r'add_subdirectory\("\$\{FLAUNCH_UNIVERSAL_LAUNCHER_ROOT\}"\s+'
            r'"\$\{CMAKE_CURRENT_BINARY_DIR\}/universal-launcher" EXCLUDE_FROM_ALL\)\s+'
            r"else\(\)\s+"
            r'add_subdirectory\("\$\{FLAUNCH_UNIVERSAL_LAUNCHER_ROOT\}"\s+'
            r'"\$\{CMAKE_CURRENT_BINARY_DIR\}/universal-launcher"\)',
        )
        self.assertRegex(
            PROVIDERS,
            r"if\(FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE\)\s+"
            r'add_subdirectory\("\$\{FLAUNCH_UNIVERSAL_SETUP_ROOT\}"\s+'
            r'"\$\{CMAKE_CURRENT_BINARY_DIR\}/universal-setup" EXCLUDE_FROM_ALL\)\s+'
            r"else\(\)\s+"
            r'add_subdirectory\("\$\{FLAUNCH_UNIVERSAL_SETUP_ROOT\}"\s+'
            r'"\$\{CMAKE_CURRENT_BINARY_DIR\}/universal-setup"\)',
        )
        self.assertIn(
            "set(FACMAN_UNIVERSAL_LAUNCHER_RUNTIME_TARGET ulk_shared)", PROVIDERS
        )
        self.assertIn(
            "set(FACMAN_UNIVERSAL_SETUP_RUNTIME_TARGET usk_shared)", PROVIDERS
        )

    def test_existing_source_build_workflows_supply_explicit_provider_roots(
        self,
    ) -> None:
        for name, workflow in WORKFLOWS.items():
            with self.subTest(workflow=name):
                self.assertIn(
                    "FLAUNCH_UNIVERSAL_LAUNCHER_ROOT: "
                    "${{ github.workspace }}/../universal-launcher",
                    workflow,
                )
                self.assertIn(
                    "FLAUNCH_UNIVERSAL_SETUP_ROOT: "
                    "${{ github.workspace }}/../universal-setup",
                    workflow,
                )

    def test_candidate_lock_is_explicit_out_of_tree_and_non_authorizing(self) -> None:
        for anchor in (
            "facman.provider_conformance_lock.v1",
            "conformance_only = true",
            "candidate_not_adopted = true",
            "release_eligible = false",
            "tracked_lock_mutated = false",
            "candidate_differs_from_tracked = (true|false)",
            "must contain exactly two provider components",
            "grants authority",
            "must be outside the FacMan source tree",
            "CMAKE_SKIP_INSTALL_RULES ON",
        ):
            self.assertIn(anchor, PROVIDERS)
        self.assertIn("FACMAN_PROVIDER_CONFORMANCE_ONLY", INSTALL)
        self.assertIn("return()", INSTALL)

    def test_candidate_lock_requires_the_exact_false_authority_set(self) -> None:
        exact = [f"{key} = false" for key in AUTHORITY_KEYS]
        variants = {
            "missing": exact[:-1],
            "unknown": [*exact, "unknown_authority = false"],
            "duplicate": [*exact, "signing = false"],
            "malformed": [*exact[:-1], 'signing = "false"'],
            "granted": [*exact[:-1], "signing = true"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            good_lock = temporary_root / "good.toml"
            good_lock.write_text(candidate_lock(exact), encoding="utf-8")
            good = run_cmake_script(
                "set(FACMAN_PROVIDER_CONFORMANCE_ONLY ON)\n"
                f'set(FACMAN_PROVIDER_LOCK_FILE "{good_lock.as_posix()}")\n'
                "_facman_validate_provider_lock(kind selected)\n"
            )
            self.assertEqual(good.returncode, 0, good.stderr)
            for name, authority in variants.items():
                with self.subTest(name=name):
                    lock = temporary_root / f"{name}.toml"
                    lock.write_text(candidate_lock(authority), encoding="utf-8")
                    result = run_cmake_script(
                        "set(FACMAN_PROVIDER_CONFORMANCE_ONLY ON)\n"
                        f'set(FACMAN_PROVIDER_LOCK_FILE "{lock.as_posix()}")\n'
                        "_facman_validate_provider_lock(kind selected)\n"
                    )
                    self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_candidate_lock_requires_exact_once_custody_classification(self) -> None:
        exact = [f"{key} = false" for key in AUTHORITY_KEYS]
        valid = candidate_lock(exact)
        variants = {
            "omitted_tracked_state": valid.replace(
                "tracked_lock_mutated = false\n", ""
            ),
            "wrong_tracked_state": valid.replace(
                "tracked_lock_mutated = false",
                "tracked_lock_mutated = true",
            ),
            "omitted_difference": valid.replace(
                "candidate_differs_from_tracked = true\n", ""
            ),
            "wrong_difference": valid.replace(
                "candidate_differs_from_tracked = true",
                "candidate_differs_from_tracked = false",
            ),
            "duplicate_difference": valid.replace(
                "candidate_differs_from_tracked = true",
                "candidate_differs_from_tracked = true\n"
                "candidate_differs_from_tracked = true",
            ),
            "malformed_difference": valid.replace(
                "candidate_differs_from_tracked = true",
                'candidate_differs_from_tracked = "true"',
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            for name, content in variants.items():
                with self.subTest(name=name):
                    lock = temporary_root / f"{name}.toml"
                    lock.write_text(content, encoding="utf-8")
                    result = run_cmake_script(
                        "set(FACMAN_PROVIDER_CONFORMANCE_ONLY ON)\n"
                        f'set(FACMAN_PROVIDER_LOCK_FILE "{lock.as_posix()}")\n'
                        "_facman_validate_provider_lock(kind selected)\n"
                    )
                    self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_candidate_difference_declaration_matches_both_exact_provider_pins(
        self,
    ) -> None:
        exact_authority = [f"{key} = false" for key in AUTHORITY_KEYS]
        tracked_pins = tracked_provider_pins()
        cases = {
            "equal_declared_false": (
                candidate_lock(
                    exact_authority,
                    pins=tracked_pins,
                    candidate_differs=False,
                ),
                True,
                "false",
            ),
            "equal_declared_true": (
                candidate_lock(
                    exact_authority,
                    pins=tracked_pins,
                    candidate_differs=True,
                ),
                False,
                None,
            ),
            "different_declared_true": (
                candidate_lock(exact_authority, candidate_differs=True),
                True,
                "true",
            ),
            "different_declared_false": (
                candidate_lock(exact_authority, candidate_differs=False),
                False,
                None,
            ),
            "one_provider_differs_declared_true": (
                candidate_lock(
                    exact_authority,
                    pins=(tracked_pins[0], "3" * 40),
                    candidate_differs=True,
                ),
                True,
                "true",
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            for name, (content, should_pass, expected) in cases.items():
                with self.subTest(name=name):
                    lock = temporary_root / f"{name}.toml"
                    lock.write_text(content, encoding="utf-8")
                    assertion = ""
                    if expected is not None:
                        assertion = (
                            "if(NOT FACMAN_PROVIDER_CANDIDATE_DIFFERS_FROM_TRACKED "
                            f'STREQUAL "{expected}")\n'
                            '  message(FATAL_ERROR "computed candidate truth was lost")\n'
                            "endif()\n"
                        )
                    result = run_cmake_script(
                        "set(FACMAN_PROVIDER_CONFORMANCE_ONLY ON)\n"
                        f'set(FACMAN_PROVIDER_LOCK_FILE "{lock.as_posix()}")\n'
                        "_facman_validate_provider_lock(kind selected)\n" + assertion
                    )
                    if should_pass:
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_lock_parsers_reject_duplicate_or_contradictory_recognized_fields(
        self,
    ) -> None:
        exact = [f"{key} = false" for key in AUTHORITY_KEYS]
        valid_candidate = candidate_lock(exact)
        component_variants = {
            "duplicate": valid_candidate.replace(
                f'pin = "{"1" * 40}"',
                f'pin = "{"1" * 40}"\npin = "{"1" * 40}"',
                1,
            ),
            "contradictory": valid_candidate.replace(
                f'pin = "{"1" * 40}"',
                f'pin = "{"1" * 40}"\npin = "{"3" * 40}"',
                1,
            ),
            "malformed": valid_candidate.replace(f'pin = "{"1" * 40}"', "pin = 111", 1),
        }
        release = "\n".join(
            (
                "[[provider]]",
                'id = "universal_launcher"',
                'repository = "Julesc013/universal-launcher"',
                f'source_revision = "{"1" * 40}"',
                'package_version = "source-111111111111"',
                'package_identity_kind = "source_composition_identity"',
                f'package_digest = "{"a" * 64}"',
                'abi_version = "1.8"',
                'contract_set_id = "ulk-contract-set"',
                f'contract_digest = "{"b" * 64}"',
                'consumption_mode = "source"',
                "",
            )
        )
        release_variants = {
            "duplicate": release.replace(
                'consumption_mode = "source"',
                'consumption_mode = "source"\nconsumption_mode = "source"',
            ),
            "contradictory": release.replace(
                'consumption_mode = "source"',
                'consumption_mode = "source"\nconsumption_mode = "installed_static"',
            ),
            "malformed": release.replace(
                'consumption_mode = "source"', "consumption_mode = true"
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            for name, content in component_variants.items():
                with self.subTest(parser="component", name=name):
                    lock = temporary_root / f"component-{name}.toml"
                    lock.write_text(content, encoding="utf-8")
                    result = run_cmake_script(
                        f'_facman_load_lock_component(TEST "{lock.as_posix()}" universal_launcher)\n'
                    )
                    self.assertNotEqual(result.returncode, 0, result.stdout)
            for name, content in release_variants.items():
                with self.subTest(parser="release", name=name):
                    lock = temporary_root / f"release-{name}.toml"
                    lock.write_text(content, encoding="utf-8")
                    result = run_cmake_script(
                        f'_facman_load_release_provider(TEST universal_launcher "{lock.as_posix()}")\n'
                    )
                    self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_sdk_identity_requires_exact_false_authority_members(self) -> None:
        exact = {key: False for key in AUTHORITY_KEYS}
        variants = {
            "missing": {key: value for key, value in exact.items() if key != "signing"},
            "unknown": {**exact, "unknown_authority": False},
            "granted": {**exact, "signing": True},
        }
        good_json = json.dumps({"authority": exact}, separators=(",", ":"))
        good = run_cmake_script(
            f"set(identity [==[{good_json}]==])\n"
            '_facman_validate_authority_json("${identity}" "fixture")\n'
        )
        self.assertEqual(good.returncode, 0, good.stderr)
        for name, authority in variants.items():
            with self.subTest(name=name):
                payload = json.dumps({"authority": authority}, separators=(",", ":"))
                result = run_cmake_script(
                    f"set(identity [==[{payload}]==])\n"
                    '_facman_validate_authority_json("${identity}" "fixture")\n'
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_conformance_install_suppression_is_not_sticky(self) -> None:
        exact = [f"{key} = false" for key in AUTHORITY_KEYS]
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "candidate.toml"
            candidate.write_text(candidate_lock(exact), encoding="utf-8")
            result = run_cmake_script(
                "set(FACMAN_PROVIDER_CONFORMANCE_ONLY ON)\n"
                f'set(FACMAN_PROVIDER_LOCK_FILE "{candidate.as_posix()}")\n'
                "_facman_validate_provider_lock(kind selected)\n"
                "if(NOT CMAKE_SKIP_INSTALL_RULES)\n"
                '  message(FATAL_ERROR "conformance did not suppress install")\n'
                "endif()\n"
                "set(FACMAN_PROVIDER_CONFORMANCE_ONLY OFF)\n"
                f'set(FACMAN_PROVIDER_LOCK_FILE "{(ROOT / "release/index/workspace_lock.v1.toml").as_posix()}")\n'
                "_facman_validate_provider_lock(kind selected)\n"
                "if(CMAKE_SKIP_INSTALL_RULES)\n"
                '  message(FATAL_ERROR "install suppression remained sticky")\n'
                "endif()\n"
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_identity_divergence_is_explicitly_classified(self) -> None:
        tracked_source = run_cmake_script(
            "set(FACMAN_PROVIDER_CONFORMANCE_ONLY OFF)\n"
            'set(FACMAN_PROVIDER_LOCK_KIND "tracked")\n'
            'set(FACMAN_PROVIDER_MODE "source")\n'
            '_facman_classify_release_source_match(coherent "fixture" "111" "222")\n'
            'if(coherent)\n  message(FATAL_ERROR "divergence was hidden")\nendif()\n'
        )
        self.assertEqual(tracked_source.returncode, 0, tracked_source.stderr)
        self.assertIn("release eligibility remains false", tracked_source.stdout)
        conformance = run_cmake_script(
            "set(FACMAN_PROVIDER_CONFORMANCE_ONLY ON)\n"
            'set(FACMAN_PROVIDER_LOCK_KIND "conformance")\n'
            'set(FACMAN_PROVIDER_MODE "installed_static")\n'
            '_facman_classify_release_source_match(coherent "fixture" "111" "222")\n'
            'if(coherent)\n  message(FATAL_ERROR "candidate was adopted")\nendif()\n'
        )
        self.assertEqual(conformance.returncode, 0, conformance.stderr)
        exact = run_cmake_script(
            "set(FACMAN_PROVIDER_CONFORMANCE_ONLY OFF)\n"
            'set(FACMAN_PROVIDER_LOCK_KIND "tracked")\n'
            'set(FACMAN_PROVIDER_MODE "source")\n'
            '_facman_classify_release_source_match(coherent "fixture" "111" "111")\n'
            'if(NOT coherent)\n  message(FATAL_ERROR "exact identity was rejected")\nendif()\n'
        )
        self.assertEqual(exact.returncode, 0, exact.stderr)
        installed_without_conformance = run_cmake_script(
            "set(FACMAN_PROVIDER_CONFORMANCE_ONLY OFF)\n"
            'set(FACMAN_PROVIDER_LOCK_KIND "tracked")\n'
            'set(FACMAN_PROVIDER_MODE "installed_static")\n'
            '_facman_classify_release_source_match(coherent "fixture" "111" "222")\n'
        )
        self.assertNotEqual(
            installed_without_conformance.returncode,
            0,
            installed_without_conformance.stdout,
        )

    def test_installed_consumption_remains_rehearsal_even_at_exact_pins(self) -> None:
        exact_but_unadopted = run_cmake_script(
            "set(FACMAN_PROVIDER_CONFORMANCE_ONLY OFF)\n"
            'set(FACMAN_PROVIDER_LOCK_KIND "tracked")\n'
            'set(FACMAN_PROVIDER_MODE "installed_static")\n'
            "set(FACMAN_PROVIDER_RELEASE_IDENTITY_COHERENT TRUE)\n"
            "_facman_classify_provider_consumption(classification)\n"
        )
        self.assertNotEqual(
            exact_but_unadopted.returncode, 0, exact_but_unadopted.stdout
        )
        rehearsal = run_cmake_script(
            "set(FACMAN_PROVIDER_CONFORMANCE_ONLY ON)\n"
            'set(FACMAN_PROVIDER_LOCK_KIND "conformance")\n'
            'set(FACMAN_PROVIDER_MODE "installed_shared")\n'
            "_facman_classify_provider_consumption(classification)\n"
            'if(NOT classification STREQUAL "conformance_rehearsal_installed_shared")\n'
            '  message(FATAL_ERROR "installed mode was misclassified")\n'
            "endif()\n"
        )
        self.assertEqual(rehearsal.returncode, 0, rehearsal.stderr)

    def test_play_evidence_tools_refuse_silent_installed_mode_omission(self) -> None:
        refused = run_cmake_script(
            "set(FACMAN_BUILD_PLAY_EVIDENCE_TOOLS ON)\n"
            "_facman_validate_play_evidence_provider_availability(FALSE)\n"
        )
        self.assertNotEqual(refused.returncode, 0, refused.stdout)
        available = run_cmake_script(
            "set(FACMAN_BUILD_PLAY_EVIDENCE_TOOLS ON)\n"
            "_facman_validate_play_evidence_provider_availability(TRUE)\n"
        )
        self.assertEqual(available.returncode, 0, available.stderr)

    def test_installed_modes_are_exact_and_have_no_global_fallback(self) -> None:
        self.assertRegex(
            PROVIDERS,
            r"find_package\(UniversalLauncher 1\.8\.0 EXACT CONFIG REQUIRED\s+"
            r'PATHS "\$\{FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT\}" NO_DEFAULT_PATH\)',
        )
        self.assertRegex(
            PROVIDERS,
            r"find_package\(UniversalSetup 1\.0\.0 EXACT CONFIG REQUIRED\s+"
            r'PATHS "\$\{FACMAN_UNIVERSAL_SETUP_SDK_ROOT\}" NO_DEFAULT_PATH\)',
        )
        for required in (
            "FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT",
            "FACMAN_UNIVERSAL_SETUP_SDK_ROOT",
            "FACMAN_UNIVERSAL_LAUNCHER_IDENTITY_FILE",
            "FACMAN_UNIVERSAL_SETUP_IDENTITY_FILE",
        ):
            self.assertIn(required, PROVIDERS)
        self.assertIn(
            "${required_value} is mandatory in installed provider modes", PROVIDERS
        )

    def test_identity_sidecar_closes_supported_sdk_surface(self) -> None:
        for field in (
            "provider_id",
            "repository",
            "canonical_main_ref",
            "source commit",
            "source tree",
            "source remote",
            "consumption mode",
            "consumption linkage",
            "package version",
            "package.metadata_relative_path",
            "package metadata_sha256",
            "abi version",
            "abi manifest_relative_path",
            "abi manifest_sha256",
            "contracts contract_set_id",
            "contracts bundle_sha256",
            "install inventory_sha256",
            "toolchain.${field}",
            "exact known authority set",
            "facman.provider_sdk_inventory.v1",
            "inventory_manifest_relative_path",
            "inventory_manifest_sha256",
        ):
            self.assertIn(field, PROVIDERS)
        for target in (
            "UniversalLauncher::Headers",
            "UniversalLauncher::CoreStatic",
            "UniversalLauncher::CoreShared",
            "UniversalSetup::Headers",
            "UniversalSetup::CoreStatic",
            "UniversalSetup::CoreShared",
        ):
            self.assertIn(target, PROVIDERS)
        for active_toolchain_field in (
            'set(expected_cmake "cmake version ${CMAKE_VERSION}")',
            "${CMAKE_GENERATOR}",
            "generator_platform",
            "generator_toolset",
            "${CMAKE_SYSTEM_NAME}",
            "${CMAKE_SYSTEM_PROCESSOR}",
            "${CMAKE_SIZEOF_VOID_P}",
            "${CMAKE_${language}_COMPILER_ID}",
            "${CMAKE_${language}_COMPILER_VERSION}",
            "c_compiler_target",
            "cxx_compiler_target",
            "sysroot",
            "msvc_runtime_library",
            "${CMAKE_${active_field}}",
            "${CMAKE_BUILD_TYPE}",
            "CMAKE_CONFIGURATION_TYPES",
        ):
            self.assertIn(active_toolchain_field, PROVIDERS)
        self.assertIn(
            "toolchain processor '${toolchain_processor}' does not match active",
            PROVIDERS,
        )
        self.assertLess(
            PROVIDERS.index("_facman_validate_installed_provider(FACMAN_ULK_PRE"),
            PROVIDERS.index("find_package(UniversalLauncher 1.8.0 EXACT"),
        )
        self.assertIn("_facman_validate_imported_target", PROVIDERS)

    def test_imported_target_dependency_closure_is_recursively_root_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk = root / "sdk"
            include = sdk / "include"
            library = sdk / "lib/provider.a"
            outside = root / "outside"
            include.mkdir(parents=True)
            library.parent.mkdir(parents=True)
            library.write_bytes(b"fixture")
            outside.mkdir()

            prefix = (
                "add_library(Fixture::Headers INTERFACE IMPORTED)\n"
                "set_target_properties(Fixture::Headers PROPERTIES\n"
                f'  INTERFACE_INCLUDE_DIRECTORIES "{include.as_posix()}")\n'
                "add_library(Fixture::Core UNKNOWN IMPORTED)\n"
                "set_target_properties(Fixture::Core PROPERTIES\n"
                f'  IMPORTED_LOCATION "{library.as_posix()}"\n'
            )
            good = run_cmake_project(
                prefix
                + '  INTERFACE_LINK_LIBRARIES "$<LINK_ONLY:Fixture::Headers>;m"\n'
                '  INTERFACE_COMPILE_OPTIONS "-Wall"\n'
                '  INTERFACE_LINK_OPTIONS "-pthread")\n'
                f'_facman_validate_imported_target(Fixture::Core "{sdk.as_posix()}" "fixture")\n'
            )
            self.assertEqual(good.returncode, 0, good.stderr)

            variants = {
                "escaped_dependency": (
                    prefix
                    + f'  INTERFACE_LINK_LIBRARIES "{(outside / "escape.a").as_posix()}")\n'
                ),
                "path_compile_option": (
                    prefix + f'  INTERFACE_COMPILE_OPTIONS "-I{outside.as_posix()}")\n'
                ),
                "deferred_source": (
                    prefix
                    + f'  INTERFACE_SOURCES "$<BUILD_INTERFACE:{library.as_posix()}>")\n'
                ),
                "missing_dependency": (
                    prefix + '  INTERFACE_LINK_LIBRARIES "Fixture::Missing")\n'
                ),
            }
            for name, body in variants.items():
                with self.subTest(name=name):
                    result = run_cmake_project(
                        body
                        + f'_facman_validate_imported_target(Fixture::Core "{sdk.as_posix()}" "fixture")\n'
                    )
                    self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_inventory_manifest_rejects_mutated_or_unrecorded_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sdk = Path(temporary) / "sdk"
            metadata = sdk / "lib/cmake/Example/ExampleConfig.cmake"
            payload = sdk / "include/example.h"
            identity_path = sdk / "share/facman/provider-identities/example.json"
            manifest_path = (
                sdk / "share/facman/provider-identities/example.inventory.json"
            )
            for path in (metadata, payload, identity_path, manifest_path):
                path.parent.mkdir(parents=True, exist_ok=True)
            metadata.write_text("# inert package metadata\n", encoding="utf-8")
            payload.write_text("/* exact */\n", encoding="utf-8")
            records = [
                {
                    "path": path.relative_to(sdk).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in sorted(
                    (metadata, payload), key=lambda item: item.as_posix()
                )
            ]
            files_sha = hashlib.sha256(
                json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            manifest = {
                "schema": "facman.provider_sdk_inventory.v1",
                "provider_id": "example",
                "consumption": {"mode": "installed_static", "linkage": "static"},
                "excludes": [
                    identity_path.relative_to(sdk).as_posix(),
                    manifest_path.relative_to(sdk).as_posix(),
                ],
                "files": records,
                "files_sha256": files_sha,
            }
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            identity = {
                "package": {
                    "metadata_relative_path": metadata.relative_to(sdk).as_posix(),
                    "metadata_sha256": sha256_file(metadata),
                },
                "install": {
                    "inventory_manifest_relative_path": manifest_path.relative_to(
                        sdk
                    ).as_posix(),
                    "inventory_manifest_sha256": sha256_file(manifest_path),
                    "inventory_sha256": files_sha,
                    "file_count": len(records),
                },
            }
            identity_path.write_text(json.dumps(identity), encoding="utf-8")

            body = (
                f'file(READ "{identity_path.as_posix()}" identity)\n'
                "_facman_validate_sdk_inventory(manifest metadata\n"
                f'  "{sdk.as_posix()}" "{identity_path.as_posix()}" "${{identity}}"\n'
                '  "fixture" "example" "installed_static" "static" "Example")\n'
            )
            good = run_cmake_script(body)
            self.assertEqual(good.returncode, 0, good.stderr)
            payload.write_text("/* mutated */\n", encoding="utf-8")
            mutated = run_cmake_script(body)
            self.assertNotEqual(mutated.returncode, 0, mutated.stdout)
            payload.write_text("/* exact */\n", encoding="utf-8")
            extra = sdk / "unrecorded.txt"
            extra.write_text("unrecorded\n", encoding="utf-8")
            unrecorded = run_cmake_script(body)
            self.assertNotEqual(unrecorded.returncode, 0, unrecorded.stdout)

    def test_source_provider_custody_rejects_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            repository.mkdir()
            for command in (
                ("git", "init", "--quiet"),
                ("git", "config", "user.email", "provider@example.invalid"),
                ("git", "config", "user.name", "Provider Fixture"),
                ("git", "branch", "-M", "main"),
                (
                    "git",
                    "remote",
                    "add",
                    "origin",
                    "https://example.invalid/provider.git",
                ),
            ):
                subprocess.run(command, cwd=repository, check=True, capture_output=True)
            tracked = repository / "provider.c"
            tracked.write_text("int provider(void) { return 0; }\n", encoding="utf-8")
            subprocess.run(("git", "add", "provider.c"), cwd=repository, check=True)
            subprocess.run(
                ("git", "commit", "--quiet", "-m", "fixture"),
                cwd=repository,
                check=True,
                capture_output=True,
            )
            commit = subprocess.run(
                ("git", "rev-parse", "HEAD"),
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(
                ("git", "update-ref", "refs/remotes/origin/main", commit),
                cwd=repository,
                check=True,
            )
            tree = subprocess.run(
                ("git", "rev-parse", "HEAD^{tree}"),
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            body = (
                "_facman_git_identity(commit tree\n"
                f'  "{repository.as_posix()}" "fixture provider" "{commit}" "{tree}"\n'
                '  "https://example.invalid/provider.git" "refs/heads/main")\n'
            )
            clean = run_cmake_script(body)
            self.assertEqual(clean.returncode, 0, clean.stderr)
            subprocess.run(
                (
                    "git",
                    "remote",
                    "set-url",
                    "origin",
                    "https://example.invalid/substituted.git",
                ),
                cwd=repository,
                check=True,
            )
            wrong_origin = run_cmake_script(body)
            self.assertNotEqual(wrong_origin.returncode, 0, wrong_origin.stdout)
            subprocess.run(
                (
                    "git",
                    "remote",
                    "set-url",
                    "origin",
                    "https://example.invalid/provider.git",
                ),
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ("git", "update-ref", "-d", "refs/remotes/origin/main"),
                cwd=repository,
                check=True,
            )
            missing_ref = run_cmake_script(body)
            self.assertNotEqual(missing_ref.returncode, 0, missing_ref.stdout)
            subprocess.run(
                ("git", "update-ref", "refs/remotes/origin/main", commit),
                cwd=repository,
                check=True,
            )
            (repository / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            dirty = run_cmake_script(body)
            self.assertNotEqual(dirty.returncode, 0, dirty.stdout)

    def test_target_consumers_use_only_normalized_wrappers(self) -> None:
        target_files = (
            ROOT / "runtime" / "client" / "CMakeLists.txt",
            ROOT / "runtime" / "factorio" / "CMakeLists.txt",
            ROOT / "apps" / "daemon" / "CMakeLists.txt",
            ROOT / "tests" / "native" / "CMakeLists.txt",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in target_files)
        self.assertIn("${FACMAN_UNIVERSAL_LAUNCHER_TARGET}", combined)
        self.assertIn("${FACMAN_UNIVERSAL_SETUP_TARGET}", combined)
        self.assertNotRegex(combined, r"(?<![A-Za-z_])ulk_(static|shared)(?![A-Za-z_])")
        # The two private USK targets are retained only inside explicit source-only gates.
        self.assertEqual(combined.count("usk_archive_static"), 1)
        self.assertEqual(combined.count("usk_lifecycle_static"), 1)
        self.assertGreaterEqual(
            combined.count("FACMAN_PROVIDER_PRIVATE_SOURCE_TARGETS_AVAILABLE"), 3
        )
        self.assertIn("source-mode-only", combined)
        self.assertIn(
            "set(FACMAN_UNIVERSAL_LAUNCHER_CORE_TARGET ulk_static)", PROVIDERS
        )
        self.assertIn("set(FACMAN_UNIVERSAL_SETUP_CORE_TARGET usk_static)", PROVIDERS)
        self.assertIn(
            'FacManProvider::LauncherHeaders "${FACMAN_UNIVERSAL_LAUNCHER_HEADERS_TARGET}"',
            PROVIDERS,
        )
        self.assertIn(
            "FACMAN_WITH_SETUP gates product operations, not the two-provider custody",
            PROVIDERS,
        )

    def test_install_closure_copies_headers_and_selected_shared_runtime(self) -> None:
        source_start = INSTALL.index('if(FACMAN_PROVIDER_MODE STREQUAL "source"')
        installed_start = INSTALL.index(
            'elseif(FACMAN_PROVIDER_MODE STREQUAL "installed_shared")'
        )
        source_runtime = INSTALL[source_start:installed_start]
        self.assertIn(
            'AND (FACMAN_PROVIDER_SOURCE_LINKAGE STREQUAL "shared"',
            source_runtime,
        )
        self.assertIn(
            "OR NOT FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE",
            source_runtime,
        )
        self.assertIn(
            "set(facman_source_provider_runtime_targets\n"
            "    ${FACMAN_UNIVERSAL_LAUNCHER_RUNTIME_TARGET})",
            source_runtime,
        )
        self.assertIn("if(FACMAN_WITH_SETUP)", source_runtime)
        self.assertIn(
            "list(APPEND facman_source_provider_runtime_targets\n"
            "      ${FACMAN_UNIVERSAL_SETUP_RUNTIME_TARGET})",
            source_runtime,
        )
        self.assertIn(
            "install(TARGETS ${facman_source_provider_runtime_targets}",
            source_runtime,
        )
        self.assertNotIn(
            "install(TARGETS ${FACMAN_UNIVERSAL_LAUNCHER_RUNTIME_TARGET}",
            source_runtime,
        )
        self.assertIn(
            "install(IMPORTED_RUNTIME_ARTIFACTS ${facman_provider_runtime_targets}",
            INSTALL,
        )
        self.assertIn("${FACMAN_UNIVERSAL_LAUNCHER_INCLUDE_DIR}/ulk", INSTALL)
        self.assertNotIn("EXPORT FacManTargets\n    RUNTIME", INSTALL)
        self.assertIn('FACMAN_PROVIDER_MODE STREQUAL "installed_shared"', INSTALL)

    def test_no_direct_provider_target_use_escaped_the_scoped_files(self) -> None:
        cmake_files = {
            ROOT / "CMakeLists.txt",
            *(
                path
                for path in ROOT.glob("**/CMakeLists.txt")
                if "build" not in path.relative_to(ROOT).parts
            ),
        }
        allowed = {
            ROOT / "tests" / "native" / "CMakeLists.txt",
        }
        raw = re.compile(r"(?<![A-Za-z_])(ulk|usk)_(static|shared)(?![A-Za-z_])")
        for path in cmake_files:
            if path in allowed:
                continue
            self.assertIsNone(raw.search(path.read_text(encoding="utf-8")), str(path))


if __name__ == "__main__":
    unittest.main()
