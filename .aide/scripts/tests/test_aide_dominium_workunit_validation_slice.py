from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.interop.dominium import workunit_validation
from core.protocol import event_record, evidence_packet, workunit


MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_dominium_workunit_validation", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_dominium_workunit_validation"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def copy_slice_files(root: Path) -> None:
    rels = {
        ".aide/scripts/aide_lite.py",
        "core/__init__.py",
        "core/interop/__init__.py",
        "core/interop/dominium/__init__.py",
        "core/interop/dominium/workunit_validation.py",
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/reference_id.py",
        "core/protocol/workunit.py",
        "core/protocol/evidence_packet.py",
        "core/protocol/event_record.py",
        ".aide/protocol/aide-workunit.schema.json",
        ".aide/protocol/aide-context-pack-v2.schema.json",
        ".aide/protocol/aide-evidence-packet.schema.json",
        ".aide/protocol/aide-event-record.schema.json",
        ".aide/queue/AIDE-ACCEPT-DOMINIUM-READONLY-SEAM-V0-01/status.yaml",
        ".aide/reports/dominium-readonly-seam-v0-accept/acceptance-report.json",
    }
    rels.update(rel.as_posix() for rel in workunit_validation.source_paths())
    for rel in sorted(rels):
        source = REPO_ROOT / rel
        if source.exists():
            destination = root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


class AIDEDominiumWorkUnitValidationSliceTests(unittest.TestCase):
    def test_cli_run_executes_exactly_one_registered_readonly_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_slice_files(root)
            exit_code = aide_lite.main(["--repo-root", str(root), "dominium-workunit-validation", "run"])
            self.assertEqual(exit_code, 0)
            report = json.loads((root / workunit_validation.SLICE_REPORT_JSON).read_text(encoding="utf-8"))
            result = json.loads((root / workunit_validation.INVOCATION_RESULT_JSON).read_text(encoding="utf-8"))
            self.assertEqual(report["capability_id"], workunit_validation.CAPABILITY_ID)
            self.assertEqual(report["capability_invocation_count"], 1)
            self.assertEqual(result["result"], "PASS")
            self.assertEqual(result["invocation_count"], 1)
            self.assertTrue(result["dominium_validation_run_invoked"])
            self.assertEqual(report["before_state_digest"], report["after_state_digest"])
            for field in workunit_validation.FALSE_BOUNDARY_FIELDS:
                self.assertIs(result[field], False, field)

    def test_validate_reads_existing_reports_without_second_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_slice_files(root)
            self.assertEqual(aide_lite.main(["--repo-root", str(root), "dominium-workunit-validation", "run"]), 0)
            before = (root / workunit_validation.INVOCATION_RESULT_JSON).read_text(encoding="utf-8")
            self.assertEqual(aide_lite.main(["--repo-root", str(root), "dominium-workunit-validation", "validate"]), 0)
            after = (root / workunit_validation.INVOCATION_RESULT_JSON).read_text(encoding="utf-8")
            validation = json.loads((root / workunit_validation.VALIDATION_JSON).read_text(encoding="utf-8"))
            self.assertEqual(before, after)
            self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS")
            self.assertTrue(validation["exactly_one_invocation"])
            self.assertTrue(validation["no_mutation"])

    def test_unsupported_capability_gets_typed_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_slice_files(root)
            workunit_validation.write_fixture_workspace(root)
            refusal = workunit_validation.invoke_capability(root, "dominium.future.unsupported")
            self.assertEqual(refusal["result"], "REFUSED")
            self.assertEqual(refusal["reason_code"], "AIDE_DOMINIUM_WORKUNIT_VALIDATION_UNSUPPORTED_CAPABILITY")
            self.assertEqual(refusal["invocation_count"], 0)
            self.assertFalse(refusal["underlying_executor_called"])

    def test_generated_protocol_objects_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_slice_files(root)
            self.assertEqual(aide_lite.main(["--repo-root", str(root), "dominium-workunit-validation", "run"]), 0)
            workunit_record = json.loads((root / workunit_validation.WORKUNIT_JSON).read_text(encoding="utf-8"))
            evidence = json.loads((root / workunit_validation.EVIDENCE_PACKET_JSON).read_text(encoding="utf-8"))
            event = json.loads((root / workunit_validation.EVENT_RECORD_JSON).read_text(encoding="utf-8"))
            self.assertEqual(workunit.validate_workunit(workunit_record), [])
            self.assertEqual(evidence_packet.validate_evidence_packet(evidence), [])
            self.assertEqual(event_record.validate_event_record(event), [])

    def test_projection_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_slice_files(root)
            self.assertEqual(aide_lite.main(["--repo-root", str(root), "dominium-workunit-validation", "run"]), 0)
            first = (root / workunit_validation.PROJECTION_JSON).read_text(encoding="utf-8")
            self.assertEqual(aide_lite.main(["--repo-root", str(root), "dominium-workunit-validation", "run"]), 0)
            second = (root / workunit_validation.PROJECTION_JSON).read_text(encoding="utf-8")
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
