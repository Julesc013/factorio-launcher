# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import factorio_2_1_14_route_d3_d4_request_check as request_check


class FactorioRouteD3D4RequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.request = request_check.load_request()

    def validate(self, request: dict | None = None) -> list[str]:
        return request_check.validate(
            copy.deepcopy(request if request is not None else self.request)
        )

    def test_canonical_request_is_valid_and_non_authorizing(self) -> None:
        self.assertEqual([], self.validate())

    def test_digest_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["scope"] = "different"
        self.assertIn(
            "request digest does not match canonical content",
            self.validate(changed),
        )

    def test_d3_activation_is_rejected(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["requested_d3"]["currently_authorized"] = True
        errors = self.validate(changed)
        self.assertTrue(any("D3 request field currently_authorized" in item for item in errors))
        self.assertTrue(any("request digest" in item for item in errors))

    def test_d4_delegation_or_machine_inference_is_rejected(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["requested_d4"]["delegable"] = True
        changed["requested_d4"]["machine_inference_allowed"] = True
        errors = self.validate(changed)
        self.assertTrue(any("D4 request field delegable" in item for item in errors))
        self.assertTrue(any("D4 request field machine_inference_allowed" in item for item in errors))

    def test_premature_permit_material_is_rejected(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["launch"][0]["permit_id"] = "permit-" + "a" * 32
        errors = self.validate(changed)
        self.assertTrue(any("premature live material" in item for item in errors))

    def test_second_permit_preissue_is_rejected(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["launch"][1]["second_permit_preissued"] = True
        errors = self.validate(changed)
        self.assertTrue(any("launch 2 field second_permit_preissued" in item for item in errors))

    def test_route_binding_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["route"]["definition_digest"] = "a" * 64
        self.assertIn(
            "request route binding differs from immutable route v5",
            self.validate(changed),
        )

    def test_non_success_workflow_receipt_is_rejected(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["control_plane"]["workflow"][0]["conclusion"] = "pending"
        errors = self.validate(changed)
        self.assertIn(
            "control-plane post-merge workflow set is not the exact five-success receipt",
            errors,
        )

    def test_launch_identity_reuse_is_rejected(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["launch"][1]["operation_id"] = changed["launch"][0]["operation_id"]
        errors = self.validate(changed)
        self.assertTrue(any("launch pair reuses operation_id" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
