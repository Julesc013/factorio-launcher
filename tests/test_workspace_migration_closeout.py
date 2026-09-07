# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Historical completion requires actual immutable source/package custody."""
import json
import tempfile
import unittest
from pathlib import Path

from tools import workspace_migration_closeout_check as gate
from tools import release_programme_check as programme
from tools import foundation_beta_readiness_check as readiness


class WorkspaceCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / gate.RECEIPT
        self.path.parent.mkdir(parents=True)
        self.original = (gate.ROOT / gate.RECEIPT).read_bytes()
        self.path.write_bytes(self.original)
        self.archive = self.path.parent / "package-integration-custody.zip"
        self.archive.write_bytes((gate.ROOT / Path(gate.RECEIPT).parent / self.archive.name).read_bytes())
        self.workunit = {"id": gate.TASK, "status": "complete", "evidence": [gate.RECEIPT]}

    def test_reviewed_completion_accepts_lf_or_crlf_metadata(self):
        self.assertEqual(gate.validate(self.workunit, self.root), [])
        self.path.write_bytes(json.dumps(json.loads(self.original), indent=4).replace("\n", "\r\n").encode())
        self.assertEqual(gate.validate(self.workunit, self.root), [])

    def test_active_status_cannot_carry_completion_and_other_leaves_cannot_reuse_it(self):
        self.assertEqual(gate.validate({"id": gate.TASK, "status": "active"}, self.root), [])
        for change in ({"status": "active"}, {"status": "planned"}, {"id": "another-task"},
                       {"evidence": []}, {"evidence": ["../foreign.json"]}):
            with self.subTest(change=change):
                self.assertTrue(gate.validate(dict(self.workunit, **change), self.root))

    def test_source_merge_checks_artifacts_and_authority_cannot_drift(self):
        for key,value in {
            "source": "0" * 40, "source_tree": "0" * 40,
            "mergeCommit": {"oid": "0" * 40}, "state": "OPEN", "checks": 0,
            "portable_installed_cases": 65, "artifact_count": 5, "package_run": 1,
            "beta1_ready": True, "human_acceptance": True, "factorio_execution": True,
            "live_user_workspace": True, "publication": True,
        }.items():
            with self.subTest(key=key):
                doc=json.loads(self.original)
                doc[key]=value
                self.path.write_bytes(json.dumps(doc).encode())
                self.assertTrue(gate.validate(self.workunit, self.root))
        self.path.write_bytes(self.original)
        self.assertEqual(gate.validate(self.workunit, self.root), [])

    def test_corrupt_missing_duplicate_and_oversized_custody_refuse(self):
        for raw in (b'{"schema":1,"schema":2}', b' ', b' ' * (64 * 1024 + 1)):
            self.path.write_bytes(raw)
            self.assertTrue(gate.validate(self.workunit, self.root))
        self.path.write_bytes(self.original)
        self.archive.write_bytes(b'changed archive')
        self.assertTrue(gate.validate(self.workunit, self.root))
        self.archive.unlink()
        self.assertTrue(gate.validate(self.workunit, self.root))

    def test_both_release_gates_require_completion_evidence(self):
        plan=programme.load_plan()
        leaf=next(row for row in plan['workunit'] if row['id']==gate.TASK)
        leaf['evidence']=[]
        self.assertTrue(any('workspace completion' in problem for problem in programme._validate_plan_milestones(plan)))
        errors=readiness.validate(readiness._load(readiness.READINESS), readiness._load(readiness.VERSION),
            readiness._load(readiness.RELEASE_INDEX), readiness._load(readiness.ARTIFACT_MATRIX), plan=plan)
        self.assertTrue(any('workspace completion' in problem for problem in errors), errors)
