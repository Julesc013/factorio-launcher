# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import jsonschema

from tools import winforms_backend_identity_check


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/schema/factorio/facman_backend_identity.v1.schema.json"
PRODUCT_SCHEMA = ROOT / "contracts/schema/factorio/factorio_product.v1.schema.json"


def source_checkout_identity() -> dict[str, object]:
    revision = "1" * 40
    digest = "2" * 64
    return {
        "schema": "facman.backend_identity.v1",
        "product_id": "factorio",
        "binding_id": "flb.factorio",
        "backend_role": "facman_cli",
        "build": {
            "source_revision": revision,
            "source_dirty": True,
            "build_identity": "facman=test;universal_launcher=test;universal_setup=test;source_dirty=true",
            "universal_launcher_revision": "3" * 40,
            "universal_setup_revision": "4" * 40,
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
        for fragment in (
            '"facman=" + SourceRevision',
            '";universal_launcher=" + UniversalLauncherRevision',
            '";universal_setup=" + UniversalSetupRevision',
            '";source_dirty=" + (SourceDirty ? "true" : "false")',
        ):
            self.assertIn(fragment, source)


if __name__ == "__main__":
    unittest.main()
