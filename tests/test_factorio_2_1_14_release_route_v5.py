# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import factorio_2_1_14_release_route_v5_check as route_check


class Factorio2114ReleaseRouteV5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = route_check.load_policy()
        self.route = route_check.load_route()
        self.request = route_check.valid_execution_request()

    def test_canonical_route_is_closed_and_non_authorizing(self) -> None:
        self.assertEqual([], route_check.validate(self.policy, self.route))
        self.assertTrue(all(value is False for value in self.policy["authority"].values()))
        self.assertTrue(all(value is False for value in self.route["authority"].values()))

    def test_route_binds_the_exact_sealed_alpha_candidate(self) -> None:
        candidate = self.route["candidate"]
        self.assertEqual(route_check.EXPECTED_CANDIDATE, candidate)
        self.assertEqual("fa60aaa17e9044bef7bb7347261056959690f1cd", candidate["source_revision"])
        self.assertEqual("5536891662461d3617ee40e93654cb2f0659905c", candidate["source_tree"])
        self.assertEqual("8e18cf7b35d34aee2e39bc6bae0710db48dceef4196d5ff0373b880bfc866573", candidate["candidate_record_sha256"])
        self.assertEqual("00fcf5dfc9597a7118ad8d81ff4489d5ace6019c272e79bcc12e966547149c86", candidate["package_sha256"])
        self.assertEqual("7d59831268babc1be96192f8ed74f5aa5f5c85d9d1fdf9e392cc943f99eae264", candidate["contract_set_sha256"])

    def test_wrong_source_candidate_package_or_contracts_refuse(self) -> None:
        for field in (
            "source_revision", "source_tree", "candidate_record_sha256",
            "package_sha256", "contract_set_sha256",
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.request)
                changed[field] = "0" * len(str(changed[field]))
                self.assertTrue(
                    any(
                        f"{field} mismatch" in item
                        for item in route_check.validate_execution_request(changed)
                    )
                )

    def test_wrong_provider_archive_executable_or_route_refuses(self) -> None:
        for field in (
            "provider_lock_sha256", "archive_sha256", "executable_sha256",
            "policy_digest", "route_definition_digest", "route_record_sha256",
            "source_closure_digest", "host_freshness_schema_sha256",
            "clean_host_receipt_sha256", "observer_revision",
            "guest_runner_sha256", "bundle_builder_sha256",
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.request)
                changed[field] = "0" * 64
                self.assertTrue(
                    any(
                        f"{field} mismatch" in item
                        for item in route_check.validate_execution_request(changed)
                    )
                )

    def test_stale_sandbox_missing_observer_and_writable_archive_refuse(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["sandbox_fresh"] = False
        changed["observer_present"] = False
        changed["archive_mapping_read_only"] = False
        changed["target_kind"] = "host_live_installation"
        problems = route_check.validate_execution_request(changed)
        self.assertTrue(any("sandbox is stale" in item for item in problems))
        self.assertTrue(any("observer is missing" in item for item in problems))
        self.assertTrue(any("archive is writable" in item for item in problems))
        self.assertTrue(any("live or foreign" in item for item in problems))

    def test_stale_replayed_and_preissued_permits_refuse(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["permit_fresh"] = False
        changed["permit_replayed"] = True
        changed["second_permit_preissued"] = True
        problems = route_check.validate_execution_request(changed)
        self.assertTrue(any("permit is stale" in item for item in problems))
        self.assertTrue(any("replayed or consumed" in item for item in problems))
        self.assertTrue(any("preissued the second permit" in item for item in problems))

    def test_two_launches_require_exact_fresh_operation_attempt_permit_and_host(self) -> None:
        first = route_check.valid_execution_request(launch=1)
        second = route_check.valid_execution_request(launch=2)
        self.assertEqual([], route_check.validate_execution_pair(first, second))
        for field in ("operation_id", "attempt_id", "permit_id", "host_freshness_sha256"):
            changed = copy.deepcopy(second)
            changed[field] = first[field]
            self.assertTrue(
                any(
                    f"reuses {field}" in item or f"{field} mismatch" in item
                    for item in route_check.validate_execution_pair(first, changed)
                )
            )

    def test_second_permit_requires_first_terminal_receipt_and_revalidation(self) -> None:
        changed = route_check.valid_execution_request(launch=2)
        changed["launch_1_terminal_receipt_present"] = False
        changed["safety_revalidated"] = False
        problems = route_check.validate_execution_request(changed)
        self.assertTrue(any("first terminal receipt" in item for item in problems))
        self.assertTrue(any("sandbox is stale" in item for item in problems))

    def test_dynamic_wsb_and_freshness_hashes_must_be_lowercase_sha256(self) -> None:
        for field in ("sandbox_configuration_sha256", "host_freshness_sha256"):
            changed = copy.deepcopy(self.request)
            changed[field] = "not-a-digest"
            self.assertTrue(
                any(
                    f"{field} is invalid" in item
                    for item in route_check.validate_execution_request(changed)
                )
            )

    def test_any_source_authority_opening_is_rejected(self) -> None:
        changed = copy.deepcopy(self.route)
        changed["authority"]["factorio_execution_authorized"] = True
        problems = route_check.validate(self.policy, changed)
        self.assertTrue(any("opens authority" in item for item in problems))
        self.assertTrue(any("schema rejection" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
