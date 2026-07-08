from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from core.knowledge import okf_bundle


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_okf", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_okf"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def okf_source_files() -> list[str]:
    files = {
        ".aide/scripts/aide_lite.py",
        ".aide/queue/index.yaml",
        ".aide/context/latest-task-packet.md",
        "core/knowledge/__init__.py",
        "core/knowledge/okf_bundle.py",
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/reference_id.py",
        "core/protocol/event_record.py",
    }
    files.update(okf_bundle._source_artifacts())
    for item in okf_bundle.PROTOCOLS:
        files.add(item["schema_path"])
        files.add(item["helper_path"])
        files.add(item["evidence"])
        files.add(item["report"])
    return sorted(files)


def copy_okf_files(root: Path) -> None:
    for rel in okf_source_files():
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


class AIDEOKFKnowledgeBundleTests(unittest.TestCase):
    def test_frontmatter_round_trip_preserves_aide_fields(self) -> None:
        fields = {
            "type": "AIDE Protocol Object",
            "title": "EventRecord",
            "aide_uri": "aide://schema/event-record",
            "source_refs": [".aide/protocol/aide-event-record.schema.json"],
            "explicit_non_capabilities": ["runtime_knowledge_service"],
        }
        text = okf_bundle.write_frontmatter(fields) + "body\n"
        parsed, body = okf_bundle.parse_frontmatter(text)
        self.assertEqual(body, "body\n")
        self.assertEqual(parsed["type"], "AIDE Protocol Object")
        self.assertEqual(parsed["aide_uri"], "aide://schema/event-record")
        self.assertIn("explicit_non_capabilities", parsed)
        self.assertNotIn("not_capabilities", parsed)
        self.assertTrue(okf_bundle.validate_frontmatter(parsed).valid)

    def test_project_writes_required_pages_and_reserved_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_okf_files(root)
            source_paths = [root / rel for rel in okf_bundle._source_artifacts() if (root / rel).exists()]
            before = {path: path.read_bytes() for path in source_paths}
            report = okf_bundle.project_okf_bundle(root)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertFalse(report["source_artifacts_mutated"])
            self.assertEqual(report["concepts_count"], 24)
            self.assertTrue((root / ".aide/knowledge/okf/index.md").exists())
            self.assertTrue((root / ".aide/knowledge/okf/log.md").exists())
            for rel in okf_bundle.REQUIRED_CONCEPT_PATHS:
                self.assertTrue((root / ".aide/knowledge/okf" / rel).exists(), rel)
            self.assertFalse((root / ".aide/knowledge/okf/index.md").read_text(encoding="utf-8").startswith("---"))
            self.assertFalse((root / ".aide/knowledge/okf/log.md").read_text(encoding="utf-8").startswith("---"))
            self.assertEqual(before, {path: path.read_bytes() for path in source_paths})

    def test_validate_and_lint_reports_are_warning_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_okf_files(root)
            okf_bundle.project_okf_bundle(root)
            validation = okf_bundle.validate_okf_bundle(root)
            lint = okf_bundle.lint_okf_bundle(root)
            self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS")
            self.assertEqual(lint["lint_status"], "PASS_WITH_WARNINGS")
            self.assertTrue(validation["required_pages_exist"])
            self.assertTrue(validation["all_concepts_have_frontmatter"])
            self.assertTrue(validation["all_concepts_have_non_empty_type"])
            self.assertTrue(validation["aide_refs_parse"])
            self.assertTrue(validation["event_refs_parse"])
            self.assertTrue(validation["authority_boundary_preserved"])
            self.assertTrue(validation["overclaiming_check_passed"])
            self.assertEqual(lint["broken_links"], [])
            self.assertEqual(lint["orphan_pages"], [])
            self.assertEqual(lint["missing_source_refs"], [])
            self.assertEqual(lint["missing_evidence_refs"], [])
            self.assertEqual(lint["overclaiming_findings"], [])
            self.assertEqual(lint["authority_boundary_findings"], [])
            self.assertTrue(lint["stale_context_findings"])

    def test_concept_pages_have_type_and_expected_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_okf_files(root)
            okf_bundle.project_okf_bundle(root)
            for path in sorted((root / ".aide/knowledge/okf").rglob("*.md")):
                if path.name in {"index.md", "log.md"}:
                    continue
                fields, body = okf_bundle.parse_frontmatter(path.read_text(encoding="utf-8"))
                self.assertIsInstance(fields.get("type"), str)
                self.assertTrue(fields["type"])
                self.assertIn("explicit_non_capabilities", fields)
                self.assertIn("OKF knowledge explains", body)
                text = path.read_text(encoding="utf-8").lower()
                for forbidden in [
                    "okf pages are execution authority",
                    "reconciler implemented",
                    "patchtransaction implemented",
                    "adaptermanifest implemented",
                    "contextpack v2 implemented",
                    "service implemented",
                    "commander implemented",
                    "provider/model calls implemented",
                    "release ready",
                    "production ready",
                ]:
                    self.assertNotIn(forbidden, text)

    def test_event_record_page_is_projection_only_and_accepted_with_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_okf_files(root)
            okf_bundle.project_okf_bundle(root)
            page = root / ".aide/knowledge/okf/protocol/event-record.md"
            fields, body = okf_bundle.parse_frontmatter(page.read_text(encoding="utf-8"))
            self.assertEqual(fields["aide_status"], "accepted_with_warnings")
            self.assertEqual(fields["aide_capability_label"], "minimal_event_record_schema")
            self.assertIn("projection-only", body)
            self.assertIn("does not append events", body)

    def test_okf_cli_status_project_validate_and_lint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_okf_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            commands = [
                ["--repo-root", str(root), "okf", "status"],
                ["--repo-root", str(root), "okf", "project", "--source", "current-repo"],
                ["--repo-root", str(root), "okf", "validate"],
                ["--repo-root", str(root), "okf", "lint"],
            ]
            for command in commands:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("projection_only: true", output.getvalue())
                self.assertIn("okf_execution_authority: false", output.getvalue())
                self.assertIn("runtime_knowledge_service_implemented: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())

    def test_okf_cli_rejects_runtime_or_network_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["serve", "crawl", "enrich", "llm-update", "search-index", "vector-index", "visualize", "sync-remote"]:
            with self.subTest(subcommand=subcommand):
                stderr = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(stderr), self.assertRaises(SystemExit):
                    parser.parse_args(["okf", subcommand])

    def test_reports_parse_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_okf_files(root)
            okf_bundle.project_okf_bundle(root)
            for rel in [
                ".aide/reports/okf/projection-report.json",
                ".aide/reports/okf/validation.json",
                ".aide/reports/okf/lint.json",
                ".aide/reports/okf/concept-index.json",
                ".aide/reports/okf/link-index.json",
            ]:
                data = json.loads((root / rel).read_text(encoding="utf-8"))
                self.assertEqual(data["task_id"], "AIDE-BUILD-OKF-KNOWLEDGE-BUNDLE-01")


if __name__ == "__main__":
    unittest.main()
