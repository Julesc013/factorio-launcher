# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import windows_classic_profile_check


class WindowsClassicProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inputs = list(windows_classic_profile_check.load_inputs())

    def _validate(self, inputs: list[object] | None = None) -> list[str]:
        return windows_classic_profile_check.validate(*(inputs or self.inputs))

    def test_preparation_is_complete_and_non_authorizing(self) -> None:
        self.assertEqual(self._validate(), [])

    def test_target_profile_identity_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.inputs)
        compatibility = next(
            item
            for item in changed[0]["managed_host_profile"]
            if item["id"] == "win_x86_compat"
        )
        compatibility["framework_target"] = "net48"
        compatibility["architecture"] = "x86_64"
        problems = self._validate(changed)
        self.assertTrue(any("win_x86_compat framework" in item for item in problems))

    def test_planning_cannot_create_a_support_claim(self) -> None:
        changed = copy.deepcopy(self.inputs)
        changed[0]["managed_host_profile"][1]["support_status"] = "supported"
        changed[2]["host_qualification"][0]["support_status"] = "preview"
        changed[2]["host_qualification"][0]["evidence"] = ["compile.log"]
        changed[2]["host_qualification"][0]["release_authorized"] = True
        problems = self._validate(changed)
        self.assertTrue(any("cannot acquire support or release authority" in item for item in problems))
        self.assertTrue(any("cannot acquire support or evidence" in item for item in problems))
        self.assertTrue(any("cannot acquire release authority" in item for item in problems))

    def test_frontend_cannot_become_a_package_or_install_identity(self) -> None:
        changed = copy.deepcopy(self.inputs)
        changed[1]["frontend_is_distribution_identity"] = True
        changed[1]["install_modes"] = ["per_user"]
        problems = self._validate(changed)
        self.assertTrue(any("frontend cannot become" in item for item in problems))
        self.assertTrue(any("frontend-specific install modes" in item for item in problems))

    def test_setup_projection_remains_deferred_and_non_mutating(self) -> None:
        changed = copy.deepcopy(self.inputs)
        setup = next(
            item
            for item in changed[1]["package_projection"]
            if item["package_type"] == "setup_executable"
        )
        setup["status"] = "ready"
        setup["setup_mutation"] = True
        problems = self._validate(changed)
        self.assertTrue(any("cannot acquire Setup mutation authority" in item for item in problems))
        self.assertTrue(any("must remain deferred" in item for item in problems))

    def test_windows_workunits_remain_later_and_release_proven(self) -> None:
        changed = copy.deepcopy(self.inputs)
        plan = changed[3]
        workunit_id = "FACMAN-WINFORMS-SHELL-V2-FIXTURE-01"
        record = next(item for item in plan["later"] if item["id"] == workunit_id)
        plan["later"].remove(record)
        plan["workunit"].append({"id": workunit_id, "status": "planned"})
        problems = self._validate(changed)
        self.assertTrue(any("cannot enter active work" in item for item in problems))
        self.assertTrue(any("omits Windows Classic gates" in item for item in problems))

    def test_windows_workunit_requires_release_proven_c1(self) -> None:
        changed = copy.deepcopy(self.inputs)
        record = next(
            item
            for item in changed[3]["later"]
            if item["id"] == "FACMAN-WINDOWS-X86-COMPAT-SPIKE-01"
        )
        record["trigger"] = "Begin after a successful net48 build."
        problems = self._validate(changed)
        self.assertTrue(any("must remain gated on release-proven C1" in item for item in problems))

    def test_non_authoritative_generation_boundary_is_enforced(self) -> None:
        changed = copy.deepcopy(self.inputs)
        changed[5]["generation"] = changed[5]["generation"].replace(
            "Status: non-authoritative rendering and fixture reference",
            "Status: implementation authority",
        )
        problems = self._validate(changed)
        self.assertTrue(any("generation document is missing anchor" in item for item in problems))

    def test_os_named_source_family_is_rejected(self) -> None:
        changed = copy.deepcopy(self.inputs)
        changed[8].append("apps/gui/windows/winforms/src/Xp")
        problems = self._validate(changed)
        self.assertTrue(any("source family is forbidden" in item for item in problems))

    def test_current_c1_project_cannot_be_silently_retargeted(self) -> None:
        changed = copy.deepcopy(self.inputs)
        changed[6] = changed[6].replace(
            "<TargetFrameworkVersion>v4.8</TargetFrameworkVersion>",
            "<TargetFrameworkVersion>v4.0</TargetFrameworkVersion>",
        )
        problems = self._validate(changed)
        self.assertTrue(any("current C1 project must remain unchanged" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
