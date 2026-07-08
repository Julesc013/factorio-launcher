from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_distribution_apply_routing_text", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_distribution_apply_routing_text"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def copy_file(root: Path, rel: str) -> None:
    source = REPO_ROOT / rel
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def copy_inputs(root: Path) -> None:
    for rel in [
        ".aide/scripts/aide_lite.py",
        "core/distribution/__init__.py",
        "core/distribution/apply_context.py",
        "core/distribution/apply_engine.py",
        "core/distribution/apply_reports.py",
        "core/distribution/operation_executor.py",
        "core/distribution/rollback_verifier.py",
        "core/distribution/temp_workspace.py",
        ".aide/reports/distribution-manifest-v1-accept/acceptance-report.json",
        ".aide/reports/project-lock-v0-accept/acceptance-report.json",
        ".aide/reports/ownership-ledger-v1-acceptance/acceptance-report.json",
        ".aide/reports/install-record-v0-acceptance/acceptance-report.json",
        ".aide/reports/migration-record-v0-acceptance/acceptance-report.json",
        ".aide/reports/update-plan-v1-acceptance/validation-summary.json",
        ".aide/reports/rollback-bundle-v0-acceptance/validation-summary.json",
        ".aide/reports/update-receipt-v0-acceptance/validation-summary.json",
        ".aide/reports/aide-self-consumer-fixture-v0-acceptance/validation-summary.json",
    ]:
        copy_file(root, rel)


class AIDEDistributionApplyRoutingTextRepairTests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy_inputs(root)
        return root

    def run_cli(self, root: Path, command: list[str]) -> str:
        parser = aide_lite.build_parser(REPO_ROOT)
        parsed = parser.parse_args(["--repo-root", str(root), *command])
        output = io.StringIO()
        with redirect_stdout(output):
            result = parsed.handler(parsed)
        text = output.getvalue()
        self.assertEqual(result, 0, text)
        return text

    def assert_routes_after_self_consumer_acceptance(self, text: str) -> None:
        self.assertIn("recommended_next_task: AIDE-BUILD-DISTRIBUTION-PRODUCT-STATUS-PROJECTION-01", text)
        self.assertIn("aide_self_consumer_fixture_accepted: true", text)
        self.assertIn("accepted_fixture_capability: aide_self_consumer_fixture_v0", text)
        self.assertIn("self_consumer_fixture_started: true", text)
        self.assertNotIn("recommended_next_task: AIDE-CHECK-DISTRIBUTION-APPLY-ENGINE-V0-01", text)
        self.assertNotIn("self_consumer_fixture_started: false", text)
        self.assertIn("real_target_apply_implemented: false", text)
        self.assertIn("source_repo_apply_implemented: false", text)
        self.assertIn("target_repository_mutation_implemented: false", text)
        self.assertIn("release_publication_implemented: false", text)
        self.assertIn("canary_readiness: false", text)
        self.assertIn("public_release_readiness: false", text)
        self.assertIn("network_calls_implemented: false", text)
        self.assertIn("provider_model_calls_implemented: false", text)
        self.assertIn("branch_worktree_automation_implemented: false", text)

    def test_status_plan_and_verify_route_to_product_status_after_self_consumer_acceptance(self) -> None:
        root = self.make_repo()
        commands = [
            ["distribution-apply", "status"],
            ["distribution-apply", "plan"],
            ["distribution-apply", "plan", "--scenario", "managed-file-update"],
            ["distribution-apply", "verify"],
        ]
        for command in commands:
            with self.subTest(command=command):
                text = self.run_cli(root, command)
                self.assert_routes_after_self_consumer_acceptance(text)


if __name__ == "__main__":
    unittest.main()
