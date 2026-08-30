# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import tomllib
import unittest

from tools import factorio_version_family_check as family_check


CAPABILITIES = {
    "config_option": True,
    "mod_directory_option": True,
    "load_game_option": True,
    "start_server_option": True,
}


def installation(label: str, version: str) -> dict[str, object]:
    return {
        "label": label,
        "status": "probed",
        "reported_version": version,
        "install_tree_unchanged": True,
        "version_probe": {"status": "completed"},
        "help_probe": {"status": "completed"},
        "capabilities": dict(CAPABILITIES),
    }


def complete_corpus() -> dict[str, object]:
    return {
        "schema": "factorio.version_capability_corpus.v1",
        "status": "complete",
        "installations": [
            installation("factorio-1.0.0", "1.0.0"),
            installation("factorio-1.1.110", "1.1.110"),
            installation("factorio-2.0.77", "2.0.77"),
            installation("factorio-2.1.14", "2.1.14"),
        ],
    }


class FactorioVersionFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = family_check.load_policy()

    def test_canonical_policy_is_valid(self) -> None:
        self.assertEqual(family_check.validate_policy(self.policy), [])
        self.assertEqual(family_check.validate_bound_evidence(self.policy), [])
        with (family_check.ROOT / "release/index/release_index.v1.toml").open("rb") as handle:
            release_index = tomllib.load(handle)
        self.assertEqual(
            release_index["factorio_version_families"],
            "release/index/factorio_version_families.v1.toml",
        )

    def test_classifies_every_required_family(self) -> None:
        expected = {
            "1.0": ("F100", False),
            "1.0.0": ("F100", True),
            "1.1.110": ("F110", True),
            "2.0.77": ("F200", True),
            "2.1.14": ("F210", True),
        }
        for version, (family_id, exact_patch) in expected.items():
            with self.subTest(version=version):
                result = family_check.classify_version(version, self.policy)
                self.assertEqual(result.status, "eligible")
                self.assertEqual(result.family_id, family_id)
                self.assertEqual(result.exact_patch, exact_patch)

    def test_rejects_malformed_and_classifies_outside_versions(self) -> None:
        for version in ("2.1.01", "2.1.14-beta", "v2.1.14", "unknown", 210):
            with self.subTest(version=version):
                self.assertEqual(
                    family_check.classify_version(version, self.policy).status,
                    "invalid",
                )
        result = family_check.classify_version("0.18.40", self.policy)
        self.assertEqual(result.status, "outside")
        self.assertIsNone(result.family_id)

    def test_complete_four_family_corpus_qualifies_without_claiming_support(self) -> None:
        matrix = family_check.build_matrix(
            complete_corpus(), self.policy, generated_utc="2026-08-27T00:00:00Z"
        )
        self.assertEqual(matrix["overall_status"], "qualified")
        self.assertEqual(matrix["support_claim"], "unclaimed")
        self.assertEqual([item["id"] for item in matrix["families"]], ["F100", "F110", "F200", "F210"])
        self.assertTrue(all(item["status"] == "qualified" for item in matrix["families"]))
        self.assertFalse(any(matrix["authority"].values()))
        self.assertEqual(family_check.validate_matrix_schema(matrix), [])

    def test_missing_family_keeps_matrix_incomplete(self) -> None:
        corpus = complete_corpus()
        corpus["installations"] = corpus["installations"][:-1]
        matrix = family_check.build_matrix(corpus, self.policy)
        self.assertEqual(matrix["overall_status"], "incomplete")
        self.assertEqual(matrix["families"][-1]["status"], "incomplete")
        self.assertIn("F210 lacks 1 accepted exact-patch observation(s)", matrix["limitations"])

    def test_changed_tree_and_capability_gap_are_not_accepted(self) -> None:
        corpus = complete_corpus()
        corpus["installations"][0]["install_tree_unchanged"] = False
        corpus["installations"][1]["capabilities"]["load_game_option"] = False
        matrix = family_check.build_matrix(corpus, self.policy)
        observations = matrix["observations"]
        self.assertFalse(observations[0]["accepted"])
        self.assertIn("install_tree_changed", observations[0]["reasons"])
        self.assertFalse(observations[1]["accepted"])
        self.assertIn("required_capability_missing", observations[1]["reasons"])
        self.assertEqual(matrix["overall_status"], "incomplete")

    def test_two_component_version_cannot_satisfy_exact_patch_requirement(self) -> None:
        corpus = complete_corpus()
        corpus["installations"][2]["reported_version"] = "2.0"
        matrix = family_check.build_matrix(corpus, self.policy)
        observation = matrix["observations"][2]
        self.assertEqual(observation["family_id"], "F200")
        self.assertFalse(observation["accepted"])
        self.assertIn("exact_patch_required", observation["reasons"])

    def test_corpus_digest_is_canonical_and_deterministic(self) -> None:
        corpus = complete_corpus()
        reordered = copy.deepcopy(corpus)
        reordered = {key: reordered[key] for key in reversed(list(reordered))}
        first = family_check.build_matrix(corpus, self.policy)
        second = family_check.build_matrix(reordered, self.policy)
        self.assertEqual(first["source_corpus_sha256"], second["source_corpus_sha256"])


if __name__ == "__main__":
    unittest.main()
