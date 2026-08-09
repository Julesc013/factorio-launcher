# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from tools import winforms_backend_identity_check
from tools.package import pipeline as package_pipeline


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/schema/factorio/facman_backend_identity.v1.schema.json"
PRODUCT_SCHEMA = ROOT / "contracts/schema/factorio/factorio_product.v1.schema.json"


def compiled_build_identity(
    revision: str,
    universal_launcher: str,
    universal_setup: str,
    *,
    provider_source_linkage: str = "static",
    source_dirty: bool,
    release_coherent: bool,
) -> str:
    return ";".join(
        (
            f"facman={revision}",
            f"universal_launcher={universal_launcher}",
            f"universal_setup={universal_setup}",
            "provider_mode=source",
            f"provider_source_linkage={provider_source_linkage}",
            "provider_lock_kind=tracked",
            "provider_conformance_only=false",
            "provider_sdk_consumption_candidate=false",
            "provider_candidate_differs_from_tracked=false",
            "provider_consumption_classification=tracked_source",
            "provider_release_identity_coherent=" + str(release_coherent).lower(),
            "source_dirty=" + str(source_dirty).lower(),
        )
    )


def source_checkout_identity() -> dict[str, object]:
    revision = "1" * 40
    digest = "2" * 64
    universal_launcher = "3" * 40
    universal_setup = "4" * 40
    return {
        "schema": "facman.backend_identity.v1",
        "product_id": "factorio",
        "binding_id": "flb.factorio",
        "backend_role": "facman_cli",
        "build": {
            "source_revision": revision,
            "source_dirty": True,
            "build_identity": compiled_build_identity(
                revision,
                universal_launcher,
                universal_setup,
                source_dirty=True,
                release_coherent=False,
            ),
            "universal_launcher_revision": universal_launcher,
            "universal_setup_revision": universal_setup,
        },
        "transport": {
            "protocol_version": 2,
            "request_schema": "facman.transport_request.v2",
            "response_schema": "facman.transport_response.v2",
        },
        "command_catalog_sha256": digest,
        "contract_set_sha256": "5" * 64,
        "package": {
            "mode": "source_checkout",
            "integrity": "not_packaged",
            "verified": False,
            "profile_id": None,
            "manifest_sha256": None,
            "closure_sha256": None,
            "contract_set_sha256": None,
            "contract_set_matches_build": False,
            "backend_relative_path": None,
            "backend_sha256": None,
            "source_revision": None,
            "source_dirty": None,
            "universal_launcher_revision": None,
            "universal_setup_revision": None,
            "build_matches_package": False,
            "files_verified": 0,
            "authenticity": "not_applicable",
            "detail": "running executable is not in a built package",
        },
        "run_execute": {
            "command": "run.execute",
            "availability": "unavailable_until_isolation_proof",
            "refusal_code": "isolation_not_proven",
            "enabled": False,
        },
    }


class BackendIdentityContractTests(unittest.TestCase):
    def test_winforms_production_identity_gate_is_package_bound(self) -> None:
        self.assertEqual(winforms_backend_identity_check.validate_source(), [])

    def test_source_checkout_shape_satisfies_strict_schema(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(source_checkout_identity())

    def test_unknown_missing_and_stale_protocol_members_are_rejected(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)

        unknown = source_checkout_identity()
        unknown["unexpected"] = True
        self.assertTrue(list(validator.iter_errors(unknown)))

        missing = source_checkout_identity()
        del missing["package"]["closure_sha256"]  # type: ignore[index]
        self.assertTrue(list(validator.iter_errors(missing)))

        stale_protocol = copy.deepcopy(source_checkout_identity())
        stale_protocol["transport"]["protocol_version"] = 1  # type: ignore[index]
        self.assertTrue(list(validator.iter_errors(stale_protocol)))

    def test_product_contract_requires_the_backend_identity_reference(self) -> None:
        schema = json.loads(PRODUCT_SCHEMA.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("backend_identity", schema["required"])
        self.assertEqual(
            schema["properties"]["backend_identity"]["$ref"],
            "facman_backend_identity.v1.schema.json",
        )

    def test_workspace_status_uses_the_verifier_success_convention(self) -> None:
        source = (
            ROOT / "runtime/factorio/application/handlers/intelligence.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("fl_runtime_is_packaged() != 0", source)
        self.assertIn("fl_runtime_verify_package", source)
        self.assertIn("files_verified) != 0", source)

    def test_frontend_binds_the_exact_compiled_build_identity(self) -> None:
        source = (
            ROOT / "apps/gui/windows/winforms/PackagedBackendIdentity.cs"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'build, "build_identity", expectation.BuildIdentity, "backend build identity"',
            source,
        )
        self.assertIn(
            'buildInfo, "build_identity", "build info"',
            source,
        )
        self.assertIn("BuildIdentity = buildIdentity;", source)
        self.assertNotIn('return "facman=" + SourceRevision', source)
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("facman-build-identity.v1.txt", cmake)
        self.assertIn('"${FACMAN_BUILD_IDENTITY}\\n"', cmake)

    def test_package_build_identity_carries_every_exact_provider_state(self) -> None:
        revisions = {
            "factorio_launcher": "1" * 40,
            "universal_launcher": "2" * 40,
            "universal_setup": "3" * 40,
        }
        for coherent in (False, True):
            with self.subTest(release_coherent=coherent):
                expected = compiled_build_identity(
                    revisions["factorio_launcher"],
                    revisions["universal_launcher"],
                    revisions["universal_setup"],
                    source_dirty=False,
                    release_coherent=coherent,
                )
                with tempfile.TemporaryDirectory() as temporary:
                    build = Path(temporary)
                    (build / package_pipeline.CMAKE_BUILD_IDENTITY_FILENAME).write_text(
                        expected + "\n", encoding="utf-8", newline="\n"
                    )
                    self.assertEqual(
                        package_pipeline.cmake_build_identity(build, revisions, False),
                        expected,
                    )

    def test_package_build_identity_normalizes_lf_and_crlf_terminators(self) -> None:
        revisions = {
            "factorio_launcher": "1" * 40,
            "universal_launcher": "2" * 40,
            "universal_setup": "3" * 40,
        }
        expected = compiled_build_identity(
            revisions["factorio_launcher"],
            revisions["universal_launcher"],
            revisions["universal_setup"],
            source_dirty=False,
            release_coherent=False,
        )
        with tempfile.TemporaryDirectory() as temporary:
            build = Path(temporary)
            path = build / package_pipeline.CMAKE_BUILD_IDENTITY_FILENAME
            for name, terminator in (("lf", b"\n"), ("crlf", b"\r\n")):
                with self.subTest(name=name):
                    path.write_bytes(expected.encode("utf-8") + terminator)
                    self.assertEqual(
                        package_pipeline.cmake_build_identity(build, revisions, False),
                        expected,
                    )

    def test_package_build_identity_refuses_noncanonical_line_boundaries(self) -> None:
        revisions = {
            "factorio_launcher": "1" * 40,
            "universal_launcher": "2" * 40,
            "universal_setup": "3" * 40,
        }
        valid = compiled_build_identity(
            revisions["factorio_launcher"],
            revisions["universal_launcher"],
            revisions["universal_setup"],
            source_dirty=False,
            release_coherent=False,
        ).encode("utf-8")
        invalid = {
            "unterminated": valid,
            "bare_cr": valid + b"\r",
            "embedded_bare_cr": valid.replace(b";", b"\r;", 1) + b"\n",
            "multiple_lf_lines": valid + b"\n\n",
            "multiple_crlf_lines": valid + b"\r\n\r\n",
            "trailing_after_lf": valid + b"\ntrailing\n",
            "trailing_after_crlf": valid + b"\r\ntrailing\r\n",
        }
        with tempfile.TemporaryDirectory() as temporary:
            build = Path(temporary)
            path = build / package_pipeline.CMAKE_BUILD_IDENTITY_FILENAME
            for name, content in invalid.items():
                with self.subTest(name=name):
                    path.write_bytes(content)
                    with self.assertRaisesRegex(
                        ValueError,
                        "one bounded LF- or CRLF-terminated line",
                    ):
                        package_pipeline.cmake_build_identity(build, revisions, False)

    def test_package_build_identity_refuses_provider_tamper_and_missing_fields(
        self,
    ) -> None:
        revisions = {
            "factorio_launcher": "1" * 40,
            "universal_launcher": "2" * 40,
            "universal_setup": "3" * 40,
        }
        valid = compiled_build_identity(
            revisions["factorio_launcher"],
            revisions["universal_launcher"],
            revisions["universal_setup"],
            source_dirty=False,
            release_coherent=False,
        )
        mutations = {
            "installed_mode": valid.replace(
                "provider_mode=source", "provider_mode=installed_static"
            ),
            "invalid_source_linkage": valid.replace(
                "provider_source_linkage=static",
                "provider_source_linkage=automatic",
            ),
            "candidate_lock": valid.replace(
                "provider_lock_kind=tracked", "provider_lock_kind=conformance"
            ),
            "conformance": valid.replace(
                "provider_conformance_only=false",
                "provider_conformance_only=true",
            ),
            "sdk_candidate": valid.replace(
                "provider_sdk_consumption_candidate=false",
                "provider_sdk_consumption_candidate=true",
            ),
            "candidate_difference": valid.replace(
                "provider_candidate_differs_from_tracked=false",
                "provider_candidate_differs_from_tracked=true",
            ),
            "classification": valid.replace(
                "provider_consumption_classification=tracked_source",
                "provider_consumption_classification=conformance_rehearsal_source",
            ),
            "non_boolean_coherence": valid.replace(
                "provider_release_identity_coherent=false",
                "provider_release_identity_coherent=unknown",
            ),
            "missing_provider_mode": valid.replace("provider_mode=source;", ""),
        }
        with tempfile.TemporaryDirectory() as temporary:
            build = Path(temporary)
            path = build / package_pipeline.CMAKE_BUILD_IDENTITY_FILENAME
            for name, identity in mutations.items():
                with self.subTest(name=name):
                    path.write_text(identity + "\n", encoding="utf-8", newline="\n")
                    with self.assertRaises(ValueError):
                        package_pipeline.cmake_build_identity(build, revisions, False)


if __name__ == "__main__":
    unittest.main()
