# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Public observation-context and closed durable receipt regression oracles."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke_machine
from test_profiles_templates import create_instance


class PresentationIntentTests(unittest.TestCase):
    def test_observation_revision_replacement_replay_and_closed_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman presentation intent ") as raw:
            workspace = Path(raw)
            create_instance(workspace)

            def call(*args: str, success: bool = True) -> dict:
                code, stdout, stderr = invoke_machine(["--workspace", str(workspace), *args, "--json"])
                self.assertEqual(stderr, "", stdout)
                self.assertEqual(code == 0, success, stdout)
                return json.loads(stdout)

            def query(intent: str, selected: bool = True, scope: str = "launch_deck") -> dict:
                selection = ["--instance", "main"] if selected else []
                return call("presentation", "query", scope, *selection, "--intent", intent)["payload"]

            menu = query("menu")
            save = query("load_save")
            self.assertNotEqual(menu["revision"], save["revision"])
            self.assertNotEqual(query("menu", False)["revision"], query("load_save", False)["revision"])
            before = {p.relative_to(workspace): p.read_bytes() for p in workspace.rglob("*") if p.is_file()}
            refresh_args = ["presentation", "action", "readiness.refresh", "--scope", "launch_deck",
                            "--instance", "main", "--intent", "load_save", "--request-id", "refresh-save",
                            "--expected-revision", menu["revision"]]
            stale = call(*refresh_args, success=False)
            self.assertEqual("stale_snapshot_revision", stale["error"]["code"])
            self.assertEqual("load_save", stale["payload"]["replacement_snapshot"]["selected_context"]["launch_intent"])
            refresh_args[-1] = save["revision"]
            refreshed = call(*refresh_args)["payload"]
            self.assertEqual(save, refreshed["replacement_snapshot"])
            self.assertEqual(before, {p.relative_to(workspace): p.read_bytes() for p in workspace.rglob("*") if p.is_file()})

            def create_profile(intent: str, identity: str) -> tuple[list[str], dict, Path]:
                snapshot = query(intent, scope="content")
                args = ["presentation", "action", "profile.create", "--scope", "content",
                        "--instance", "main", "--intent", intent,
                        "--expected-revision", snapshot["revision"], "--request-id", identity,
                        "--idempotency-key", identity, "--operation-id", identity, "--attempt-id", identity,
                        "--confirmation", "explicit", "--profile", identity]
                result = call(*args)
                receipt = workspace / ".facman" / "action-receipts-v2" / (hashlib.sha256(identity.encode()).hexdigest() + ".v2.json")
                return args, result, receipt

            menu_args, menu_result, menu_receipt = create_profile("menu", "menu-profile")
            menu_raw = menu_receipt.read_bytes()
            recorded = json.loads(menu_raw)
            canonical = json.loads(recorded["request_json"])
            # Frozen legacy 20-key vocabulary, independent of the new request serializer.
            legacy_keys = (
                "action_id scope expected_snapshot_revision request_id selected_instance_id "
                "durable_operation_id attempt_id confirmation installation_id installation_path "
                "new_instance_id display_name template_id profile_id mod_identity save output_path "
                "source_data_root transaction_id roots"
            )
            self.assertEqual(set(canonical), set(legacy_keys.split()))
            self.assertEqual(recorded["request_fingerprint"], hashlib.sha256(recorded["request_json"].encode()).hexdigest())
            omitted = menu_args.copy(); i = omitted.index("--intent"); del omitted[i:i+2]
            self.assertEqual(menu_result["payload"], call(*omitted)["payload"])
            self.assertEqual(menu_result["payload"], call(*menu_args)["payload"])
            self.assertEqual(menu_raw, menu_receipt.read_bytes())

            save_args, save_result, save_receipt = create_profile("load_save", "save-profile")
            self.assertEqual("load_save", save_result["payload"]["replacement_snapshot"]["selected_context"]["launch_intent"])
            self.assertEqual(save_result["payload"], call(*save_args)["payload"])
            conflict = save_args.copy(); conflict[conflict.index("--intent") + 1] = "menu"
            self.assertEqual("idempotency_key_conflict", call(*conflict, success=False)["error"]["code"])
            old_bytes = save_receipt.read_bytes()
            receipt = json.loads(old_bytes)
            request = json.loads(receipt["request_json"])
            self.assertEqual("load_save", request["launch_intent"])
            for extra in ({"launch_intent": "menu"}, {"launch_intent": 1}, {"unknown_intent": "load_save"}):
                altered = dict(request); altered.update(extra)
                receipt["request_json"] = json.dumps(altered, sort_keys=True, separators=(",", ":"))
                receipt["request_fingerprint"] = hashlib.sha256(receipt["request_json"].encode()).hexdigest()
                save_receipt.write_text(json.dumps(receipt), encoding="utf-8")
                refused = call(*save_args, success=False)
                self.assertEqual("idempotency_receipt_invalid", refused["error"]["code"])
                self.assertEqual("recovery_required", refused["operation"]["outcome"])
            save_receipt.write_bytes(old_bytes)


if __name__ == "__main__":
    unittest.main()
