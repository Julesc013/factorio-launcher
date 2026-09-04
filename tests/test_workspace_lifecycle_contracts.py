# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "contracts" / "schema" / "facman"


class WorkspaceLifecycleContractTests(unittest.TestCase):
    names = (
        "facman_workspace_observation.v1.schema.json",
        "facman_workspace_migration_plan.v2.schema.json",
        "facman_workspace_migration_operation.v1.schema.json",
        "facman_workspace_migration_journal.v2.schema.json",
        "facman_workspace_recovery_projection.v1.schema.json",
        "facman_workspace_creation_journal.v1.schema.json",
        "facman_workspace_migration.v2.schema.json",
    )

    def schema(self, name: str) -> dict[str, object]:
        return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))

    def test_contract_schemas_are_valid_and_closed(self) -> None:
        for name in self.names:
            with self.subTest(schema=name):
                schema = self.schema(name)
                jsonschema.Draft202012Validator.check_schema(schema)
                self.assertFalse(schema["additionalProperties"])

    def test_operation_state_and_recovery_boundaries_are_closed(self) -> None:
        operation = self.schema("facman_workspace_migration_operation.v1.schema.json")
        phases = set(operation["properties"]["current_phase"]["enum"])
        self.assertTrue({
            "confirmation_required", "applying", "verifying", "completed",
            "refused_before_effects", "interrupted_recoverable", "resume_available",
            "rollback_available", "recovery_required", "rolled_back", "outcome_unknown",
        }.issubset(phases))
        boundaries = set(operation["properties"]["recovery_boundary"]["enum"])
        self.assertEqual(boundaries, {
            "no_effects", "staged_only", "partially_committed_recoverable",
            "fully_committed", "rolled_back", "unknown",
        })

    def test_plan_requires_every_effect_binding(self) -> None:
        plan = self.schema("facman_workspace_migration_plan.v2.schema.json")
        required = set(plan["required"])
        self.assertTrue({
            "expected_workspace_revision", "expected_root_identity", "plan_digest",
            "effects", "backup_disposition", "rollback_disposition",
            "confirmation_required", "mutation_executed",
        }.issubset(required))
        effect_required = set(plan["properties"]["effects"]["items"]["required"])
        self.assertTrue({
            "step_id", "source_sha256", "target_sha256",
            "backup_disposition", "rollback_disposition",
        }.issubset(effect_required))

    def test_workspace_migration_goldens_validate_against_the_public_response(self) -> None:
        resources: list[tuple[str, Resource[dict[str, object]]]] = []
        for path in SCHEMA_ROOT.glob("*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            schema_id = schema.get("$id")
            if isinstance(schema_id, str):
                resources.append((schema_id, Resource.from_contents(schema)))
        validator = jsonschema.Draft202012Validator(
            self.schema("facman_workspace_migration.v2.schema.json"),
            registry=Registry().with_resources(resources),
        )
        golden_root = ROOT / "tests" / "golden" / "commands"
        for operation in ("inspect", "plan", "apply"):
            with self.subTest(operation=operation):
                value = json.loads(
                    (golden_root / f"workspace.migration.{operation}.success.json")
                    .read_text(encoding="utf-8")
                )
                validator.validate(value)

    def test_normative_text_contains_fail_closed_admission_law(self) -> None:
        text = " ".join(
            (ROOT / "docs" / "architecture" / "workspace-lifecycle-contract.v2.md")
            .read_text(encoding="utf-8")
            .split()
        )
        for phrase in (
            "exact plan digest", "expected workspace revision", "expected root identity",
            "explicit confirmation", "idempotency key", "Future formats are never downgraded",
            "Frontends never inspect journals",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
