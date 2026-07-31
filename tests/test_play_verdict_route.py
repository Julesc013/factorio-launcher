# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools.play_verdict_route import (
    HERMETIC_VERDICT03,
    INSTANCE_ISOLATED_REVALIDATION,
    QUALIFICATION_SCHEMA_V4,
    RouteBindingError,
    digest_value,
    parse_qualification_binding,
    route_for_work_unit,
)


def qualification_value() -> dict[str, object]:
    route = INSTANCE_ISOLATED_REVALIDATION
    core: dict[str, object] = {
        "schema": QUALIFICATION_SCHEMA_V4,
        "canonicalization_version": "facman.sorted-json.v1",
        "route_id": route.route_id,
        "work_unit": route.work_unit,
        "source_binding": {
            "factorio_launcher": {
                "revision": "a" * 40,
                "required_ref": "origin/dev",
            },
            "universal_launcher": {
                "revision": "b" * 40,
                "required_ref": "origin/main",
            },
            "universal_setup": {
                "revision": "c" * 40,
                "required_ref": "origin/main",
            },
        },
        "artifacts": {
            name: {
                "relative_path": relative,
                "size": index,
                "sha256": f"{index:x}" * 64,
            }
            for index, (name, relative) in enumerate(
                (
                    ("facman", "Debug/facman.exe"),
                    ("candidate_smoke", "Debug/candidate-smoke.exe"),
                    ("verdict_harness", "Debug/verdict-harness.exe"),
                    ("evidence_probe", "Debug/evidence-probe.exe"),
                    ("cmake_cache", "CMakeCache.txt"),
                ),
                start=1,
            )
        },
        "factorio": {
            "version": "2.0.77",
            "sha256": "d" * 64,
            "signer": "Wube Software Ltd",
        },
        "instance": {
            "instance_id": route.instance_id,
            "spec_digest": "e" * 64,
            "binding_digest": "f" * 64,
            "readiness_digest": "0" * 64,
        },
    }
    return {**core, "qualification_digest": digest_value(core)}


class PlayVerdictRouteTests(unittest.TestCase):
    def test_successor_route_is_exact_and_historical_attempts_are_rejected(self) -> None:
        self.assertEqual(
            INSTANCE_ISOLATED_REVALIDATION.work_unit,
            "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04",
        )
        self.assertEqual(
            route_for_work_unit(INSTANCE_ISOLATED_REVALIDATION.work_unit),
            INSTANCE_ISOLATED_REVALIDATION,
        )
        self.assertEqual(
            route_for_work_unit(HERMETIC_VERDICT03.work_unit),
            HERMETIC_VERDICT03,
        )
        for historical in (
            "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-02",
            "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03",
            "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-99",
        ):
            with self.subTest(historical=historical), self.assertRaises(
                RouteBindingError
            ):
                route_for_work_unit(historical)

    def test_v4_qualification_projects_the_successor_session_identity(self) -> None:
        binding = parse_qualification_binding(
            qualification_value(),
            INSTANCE_ISOLATED_REVALIDATION,
        )
        self.assertEqual(binding.work_unit, INSTANCE_ISOLATED_REVALIDATION.work_unit)
        self.assertEqual(binding.factorio_launcher.revision, "a" * 40)

    def test_legacy_schema_cannot_be_reused_for_successor_route(self) -> None:
        value = qualification_value()
        value["schema"] = "facman.play_candidate_qualification_binding.v3"
        core = dict(value)
        core.pop("qualification_digest")
        value["qualification_digest"] = digest_value(core)
        with self.assertRaises(RouteBindingError):
            parse_qualification_binding(value, INSTANCE_ISOLATED_REVALIDATION)


if __name__ == "__main__":
    unittest.main()
