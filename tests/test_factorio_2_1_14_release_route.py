# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import factorio_2_1_14_release_route_check as route_check


class Factorio2114ReleaseRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = route_check.load_policy()
        self.route = route_check.load_route()
        self.record = route_check.load_record()
        self.request = route_check.valid_execution_request()

    def test_canonical_route_is_closed_and_non_authorizing(self) -> None:
        self.assertEqual([], route_check.validate(self.policy, self.route, self.record))
        self.assertTrue(all(value is False for value in self.policy["authority"].values()))
        self.assertTrue(all(value is False for value in self.route["authority"].values()))
        self.assertTrue(all(value is False for value in self.record["authority"].values()))

    def test_wrong_facman_source_refuses_before_dispatch(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["source_revision"] = "0" * 40
        self.assertTrue(any("source_revision mismatch" in item for item in route_check.validate_execution_request(changed)))

    def test_wrong_package_refuses_before_dispatch(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["package_sha256"] = "0" * 64
        self.assertTrue(any("package_sha256 mismatch" in item for item in route_check.validate_execution_request(changed)))

    def test_wrong_provider_refuses_before_dispatch(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["provider_lock_sha256"] = "0" * 64
        self.assertTrue(any("provider_lock_sha256 mismatch" in item for item in route_check.validate_execution_request(changed)))

    def test_wrong_archive_refuses_before_dispatch(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["archive_sha256"] = "0" * 64
        self.assertTrue(any("archive_sha256 mismatch" in item for item in route_check.validate_execution_request(changed)))

    def test_changed_route_refuses_before_dispatch(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["route_definition_digest"] = "0" * 64
        self.assertTrue(any("route_definition_digest mismatch" in item for item in route_check.validate_execution_request(changed)))

    def test_stale_sandbox_and_missing_observer_refuse(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["sandbox_fresh"] = False
        changed["observer_present"] = False
        problems = route_check.validate_execution_request(changed)
        self.assertTrue(any("sandbox is stale" in item for item in problems))
        self.assertTrue(any("observer is missing" in item for item in problems))

    def test_writable_archive_and_foreign_target_refuse(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["archive_mapping_read_only"] = False
        changed["target_kind"] = "host_live_installation"
        problems = route_check.validate_execution_request(changed)
        self.assertTrue(any("archive is writable" in item for item in problems))
        self.assertTrue(any("live or foreign" in item for item in problems))

    def test_stale_and_replayed_permits_refuse(self) -> None:
        changed = copy.deepcopy(self.request)
        changed["permit_fresh"] = False
        changed["permit_replayed"] = True
        problems = route_check.validate_execution_request(changed)
        self.assertTrue(any("permit is stale" in item for item in problems))
        self.assertTrue(any("replayed or consumed" in item for item in problems))

    def test_two_launches_require_fresh_operation_attempt_and_permit(self) -> None:
        first = route_check.valid_execution_request(launch=1)
        second = route_check.valid_execution_request(launch=2)
        self.assertEqual([], route_check.validate_execution_pair(first, second))
        second["operation_id"] = first["operation_id"]
        second["attempt_id"] = first["attempt_id"]
        second["permit_id"] = first["permit_id"]
        problems = route_check.validate_execution_pair(first, second)
        self.assertTrue(any("reuses operation_id" in item for item in problems))
        self.assertTrue(any("reuses attempt_id" in item for item in problems))
        self.assertTrue(any("reuses permit_id" in item for item in problems))

    def test_any_source_authority_opening_is_rejected(self) -> None:
        changed = copy.deepcopy(self.route)
        changed["authority"]["factorio_execution_authorized"] = True
        problems = route_check.validate(self.policy, changed, self.record)
        self.assertTrue(any("opens authority" in item for item in problems))
        self.assertTrue(any("schema rejection" in item for item in problems))

    def test_closed_during_loading_cannot_satisfy_the_menu_criterion(self) -> None:
        self.assertFalse(
            route_check.factorio_menu_observed(
                "Loading mod base 2.1.14 (data.lua)\nClosed during loading.\nGoodbye\n"
            )
        )
        self.assertTrue(
            route_check.factorio_menu_observed(
                "Loading mod base 2.1.14 (data.lua)\nFactorio initialised\nGoodbye\n"
            )
        )


if __name__ == "__main__":
    unittest.main()
