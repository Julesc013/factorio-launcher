from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_distribution_product_status", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_distribution_product_status"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def copy_file(root: Path, rel: str) -> None:
    source = REPO_ROOT / rel
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def copy_inputs(root: Path) -> None:
    for rel in [
        ".aide/queue/index.yaml",
        ".aide/queue/AIDE-ACCEPT-DISTRIBUTION-APPLY-ENGINE-V0-01/status.yaml",
        ".aide/queue/AIDE-ACCEPT-AIDE-SELF-CONSUMER-FIXTURE-V0-01/status.yaml",
        ".aide/queue/AIDE-ACCEPT-DISTRIBUTION-APPLY-ROUTING-TEXT-REPAIR-01/status.yaml",
        ".aide/reports/distribution-apply-engine-v0-acceptance/validation-summary.json",
        ".aide/reports/aide-self-consumer-fixture-v0-acceptance/validation-summary.json",
        ".aide/reports/distribution-apply-routing-text-repair-acceptance/validation-summary.json",
    ]:
        copy_file(root, rel)


class AIDEDistributionProductStatusProjectionTests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy_inputs(root)
        return root

    def run_status(self, root: Path) -> str:
        parser = aide_lite.build_parser(REPO_ROOT)
        parsed = parser.parse_args(["--repo-root", str(root), "distribution-product", "status"])
        output = io.StringIO()
        with redirect_stdout(output):
            result = parsed.handler(parsed)
        text = output.getvalue()
        self.assertEqual(result, 0, text)
        return text

    def test_distribution_product_status_projection_shape_and_boundaries(self) -> None:
        root = self.make_repo()
        text = self.run_status(root)
        self.assertIn("result: PASS_WITH_WARNINGS", text)
        self.assertIn("next_task: AIDE-CHECK-DISTRIBUTION-PRODUCT-STATUS-PROJECTION-01", text)
        self.assertIn("real_target_apply_readiness: false", text)
        self.assertIn("canary_readiness: false", text)
        self.assertIn("public_release_readiness: false", text)
        self.assertIn("provider_model_network_readiness: false", text)

        json_path = root / ".aide/reports/distribution-product-status/current.json"
        md_path = root / ".aide/reports/distribution-product-status/current.md"
        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())

        data = json.loads(json_path.read_text(encoding="utf-8"))
        for key in [
            "projection",
            "current",
            "accepted",
            "readiness",
            "canaries",
            "explicit_non_capabilities",
            "warning_debt",
            "recommended_next_tasks",
        ]:
            self.assertIn(key, data)

        accepted = data["accepted"]
        capability_ids = {item["id"] for item in accepted["capabilities"]}
        boundary_ids = {item["id"] for item in accepted["boundaries"]}
        self.assertIn("distribution_apply_engine_v0", capability_ids)
        self.assertIn("aide_self_consumer_fixture_v0", capability_ids)
        self.assertIn("distribution_apply_routing_text_repair_v0", boundary_ids)
        self.assertEqual(data["current"]["next_task"], "AIDE-CHECK-DISTRIBUTION-PRODUCT-STATUS-PROJECTION-01")
        self.assertFalse(data["readiness"]["real_target_apply"])
        self.assertFalse(data["readiness"]["public_release"])
        self.assertFalse(data["readiness"]["provider_model_network"])
        self.assertFalse(data["canaries"]["screensave"]["readiness"])
        self.assertFalse(data["canaries"]["eureka"]["readiness"])
        self.assertFalse(data["canaries"]["dominium"]["readiness"])

        markdown = md_path.read_text(encoding="utf-8")
        for heading in [
            "# Distribution Product Status",
            "## Current gate",
            "## Accepted capabilities and boundaries",
            "## Fixture-only boundaries",
            "## Explicit non-capabilities",
            "## Readiness matrix",
            "## Canary readiness",
            "## Warning debt",
            "## Latest validation",
            "## Next recommended tasks",
            "## Source refs",
        ]:
            self.assertIn(heading, markdown)


if __name__ == "__main__":
    unittest.main()
