# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import unittest

import jsonschema

from tools import command_contract_check


class CommandContractTests(unittest.TestCase):
    def test_command_contract_check(self) -> None:
        self.assertEqual(command_contract_check.main(), 0)

    def test_uninstall_plan_schema_rejects_runtime_invalid_shapes(self) -> None:
        schema = json.loads(
            (
                command_contract_check.ROOT
                / "contracts/schema/factorio/usk_operation_plan.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        golden = json.loads(
            (
                command_contract_check.ROOT
                / "tests/golden/commands/installs.uninstall.plan.success.json"
            ).read_text(encoding="utf-8")
        )
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(golden)

        state_effect = next(
            effect for effect in golden["effects"] if effect["kind"] == "write_state"
        )
        missing_state = copy.deepcopy(golden)
        missing_state["effects"] = [
            effect for effect in missing_state["effects"] if effect["kind"] != "write_state"
        ]
        duplicate_state = copy.deepcopy(golden)
        duplicate = copy.deepcopy(state_effect)
        duplicate["effect_id"] = "effect.duplicate-state"
        duplicate_state["effects"].append(duplicate)
        malformed_paths = ("..", "/absolute", "C:\\Windows", "bin/./x", "bin//x", "bin/x/")
        invalid_documents = [missing_state, duplicate_state]
        for malformed_path in malformed_paths:
            document = copy.deepcopy(golden)
            document["effects"][0]["relative_path"] = malformed_path
            invalid_documents.append(document)
        relative_root = copy.deepcopy(golden)
        relative_root["roots"][0]["root"] = "relative/install"
        invalid_documents.append(relative_root)

        for document in invalid_documents:
            with self.subTest(document=document):
                self.assertTrue(list(validator.iter_errors(document)))

    def test_uninstall_report_schema_rejects_runtime_invalid_shapes(self) -> None:
        schema = json.loads(
            (
                command_contract_check.ROOT
                / "contracts/schema/factorio/usk_uninstall_report.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        golden = json.loads(
            (
                command_contract_check.ROOT
                / "tests/golden/commands/installs.uninstall.apply.success.json"
            ).read_text(encoding="utf-8")
        )
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(golden)

        invalid_documents = []
        for malformed_path in ("..", "/absolute", "C:\\Windows", "bin/./x", "bin//x", "bin/x/"):
            document = copy.deepcopy(golden)
            document["deleted_owned_files"] = [malformed_path]
            invalid_documents.append(document)
        duplicate_path = copy.deepcopy(golden)
        duplicate_path["deleted_owned_files"] *= 2
        invalid_documents.append(duplicate_path)
        archive_deleted = copy.deepcopy(golden)
        archive_deleted["source_archive_deleted"] = True
        invalid_documents.append(archive_deleted)
        unsupported_status = copy.deepcopy(golden)
        unsupported_status["status"] = "failed"
        invalid_documents.append(unsupported_status)
        empty_retained_status = copy.deepcopy(golden)
        empty_retained_status["status"] = "retained_foreign_content"
        invalid_documents.append(empty_retained_status)
        malformed_timestamp = copy.deepcopy(golden)
        malformed_timestamp["completed_at"] = "2026-09-15T00:00Z"
        invalid_documents.append(malformed_timestamp)

        for document in invalid_documents:
            with self.subTest(document=document):
                self.assertTrue(list(validator.iter_errors(document)))

    def test_managed_install_recovery_schema_rejects_impossible_effect_states(self) -> None:
        schema_root = command_contract_check.ROOT / "contracts/schema/factorio"
        shared = json.loads((
            schema_root / "facman_managed_install_recovery.v1.schema.json"
        ).read_text(encoding="utf-8"))
        repair = json.loads((
            schema_root / "facman_managed_repair_recovery.v1.schema.json"
        ).read_text(encoding="utf-8"))
        uninstall = json.loads((
            schema_root / "facman_managed_uninstall_recovery.v1.schema.json"
        ).read_text(encoding="utf-8"))
        terminal_uninstall = json.loads((
            command_contract_check.ROOT
            / "tests/golden/commands/installs.recovery.inspect.success.json"
        ).read_text(encoding="utf-8"))
        shared_validator = jsonschema.Draft202012Validator(shared)
        repair_validator = jsonschema.Draft202012Validator(repair)
        uninstall_validator = jsonschema.Draft202012Validator(uninstall)
        shared_validator.validate(terminal_uninstall)
        uninstall_validator.validate(terminal_uninstall)

        terminal_repair = copy.deepcopy(terminal_uninstall)
        terminal_repair.update({
            "schema": "facman.managed_repair_recovery.v1",
            "operation": "repair",
            "classification": "provider_repaired",
            "target_exists": True,
        })
        shared_validator.validate(terminal_repair)
        repair_validator.validate(terminal_repair)

        for source, operation_validator in (
            (terminal_uninstall, uninstall_validator),
            (terminal_repair, repair_validator),
        ):
            no_effect = copy.deepcopy(source)
            no_effect.update({
                "classification": "no_provider_effect",
                "action": "close_no_provider_effect",
                "provider_journal_present": False,
                "provider_observed_state": "",
                "provider_journal_digest": "",
                "provider_journal_snapshot_sha256": "",
                "target_exists": True,
            })
            shared_validator.validate(no_effect)
            operation_validator.validate(no_effect)
            for field, invalid_value in (
                ("provider_journal_present", True),
                ("provider_observed_state", "completed"),
                ("target_exists", False),
            ):
                invalid = copy.deepcopy(no_effect)
                invalid[field] = invalid_value
                with self.subTest(schema=source["schema"], field=field):
                    self.assertTrue(list(shared_validator.iter_errors(invalid)))
                    self.assertTrue(list(operation_validator.iter_errors(invalid)))

        terminal_cases = (
            (terminal_repair, "target_exists", False),
            (terminal_repair, "provider_journal_present", False),
            (terminal_uninstall, "target_exists", True),
            (terminal_uninstall, "provider_journal_present", False),
        )
        for source, field, invalid_value in terminal_cases:
            invalid = copy.deepcopy(source)
            invalid[field] = invalid_value
            with self.subTest(classification=source["classification"], field=field):
                self.assertTrue(list(shared_validator.iter_errors(invalid)))

    def test_uninstall_transaction_identity_matches_request_and_journal_contracts(self) -> None:
        request_schema = json.loads((
            command_contract_check.ROOT
            / "contracts/schema/command/installs.uninstall.apply.request.v1.schema.json"
        ).read_text(encoding="utf-8"))
        journal_schema = json.loads((
            command_contract_check.ROOT
            / "contracts/schema/facman/facman_transaction.v2.schema.json"
        ).read_text(encoding="utf-8"))
        request_validator = jsonschema.Draft202012Validator(request_schema)
        journal_validator = jsonschema.Draft202012Validator(journal_schema)
        transaction_id = "tx-m1-unint-recover"
        request = {
            "install_id": "managed-install",
            "plan_id": "uninstall-plan-managed-install",
            "plan_digest": "1" * 64,
            "plan_created_at": "2099-01-01T00:00:00Z",
            "transaction_id": transaction_id,
            "applied_at": "2099-01-01T00:00:01Z",
            "confirmation": "APPLY",
        }
        journal = {
            "schema": "facman.transaction.v2",
            "transaction_id": transaction_id,
            "command_id": "installs.uninstall.apply",
            "workspace_id": "workspace",
            "marker_nonce": "nonce-" + "1" * 32,
            "target": "target",
            "source_identities": [],
            "created_utc": "2099-01-01T00:00:00Z",
            "updated_utc": "2099-01-01T00:00:01Z",
            "state": "recovery_required",
            "completed_steps": [],
            "owned_staging_roots": [],
            "expected_files": [],
            "commit_strategy": "provider_uninstall_then_durable_install_reference_replacement",
            "operation_context": "{}",
            "error": "interrupted",
            "recovery_actions": [],
        }
        request_validator.validate(request)
        journal_validator.validate(journal)
        for invalid in ("tx.M1", "tx_m1", "TX-m1", "tx--m1", "tx-" + "a" * 62):
            with self.subTest(transaction_id=invalid):
                invalid_request = {**request, "transaction_id": invalid}
                invalid_journal = {**journal, "transaction_id": invalid}
                self.assertTrue(list(request_validator.iter_errors(invalid_request)))
                self.assertTrue(list(journal_validator.iter_errors(invalid_journal)))


if __name__ == "__main__":
    unittest.main()
