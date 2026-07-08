from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


class ExportImportTests(unittest.TestCase):
    def make_source_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "source"
        root.mkdir()
        for rel in [*aide_lite.PORTABLE_SOURCE_FILES, *aide_lite.Q21_REQUIRED_FILES]:
            source = REPO_ROOT / rel
            if source.exists() and source.is_file():
                self.copy_file(source, root / rel)
        for directory in [*aide_lite.PORTABLE_SOURCE_DIRS, ".aide/import"]:
            source_root = REPO_ROOT / directory
            if not source_root.exists():
                continue
            for source in sorted(source_root.rglob("*")):
                if source.is_file():
                    self.copy_file(source, root / source.relative_to(REPO_ROOT))
        aide_lite.write_text(root / "README.md", "# Source Fixture\n")
        aide_lite.write_text(root / "AGENTS.md", "# Source Agents\n")
        aide_lite.write_text(root / ".gitignore", ".aide.local/\n.aide.local/**\n.env\n")
        return root

    def copy_file(self, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    def build_pack(self, source_root: Path) -> Path:
        pack_root, report = aide_lite.build_export_pack(source_root)
        self.assertGreater(len(report["included_files"]), 20)
        self.assertEqual(report["boundary_violations"], [])
        return pack_root

    def set_manifest_scalars(self, pack_root: Path, updates: dict[str, str]) -> None:
        lines = []
        for line in aide_lite.read_text(pack_root / "manifest.yaml").splitlines():
            key = line.split(":", 1)[0] if ":" in line else ""
            if key in updates:
                lines.append(f"{key}: {updates[key]}")
            else:
                lines.append(line)
        aide_lite.write_text(pack_root / "manifest.yaml", "\n".join(lines) + "\n")

    def test_export_policy_has_required_anchors(self) -> None:
        policy = aide_lite.read_text(REPO_ROOT / aide_lite.EXPORT_IMPORT_POLICY_PATH)
        for anchor in [
            "portable_pack_only",
            "no_external_repo_mutation",
            "no_network",
            "no_provider_calls",
            "aide-lite-pack-v0",
            "never_copy_aide_self_hosting_queue: true",
            "never_copy_aide_generated_context: true",
            "never_copy_aide_local_state: true",
            "never_copy_provider_credentials: true",
        ]:
            self.assertIn(anchor, policy)

    def test_export_includes_required_portable_files_and_manifest(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        self.assertTrue((pack_root / "manifest.yaml").exists())
        self.assertTrue((pack_root / "checksums.json").exists())
        for rel in [
            "files/.aide/scripts/aide_lite.py",
            "files/.aide/policies/token-budget.yaml",
            "files/.aide/policies/export-import.yaml",
            "files/.aide/prompts/compact-task.md",
            "files/.aide/profile.template.yaml",
            "files/.aide/memory/project-state.template.md",
            "files/AGENTS.md.template",
            "files/.aide.local.example/secrets/README.md",
        ]:
            self.assertTrue((pack_root / rel).exists(), rel)
        manifest = aide_lite.read_text(pack_root / "manifest.yaml")
        self.assertIn("included_files:", manifest)
        self.assertIn("excluded_classes:", manifest)
        self.assertIn("raw_prompt_storage: false", manifest)

    def test_export_excludes_source_state_and_generated_artifacts(self) -> None:
        source_root = self.make_source_repo()
        for rel in [
            ".aide/profile.yaml",
            ".aide/queue/index.yaml",
            ".aide/context/latest-task-packet.md",
            ".aide/reports/token-ledger.jsonl",
            ".aide/cache/latest-cache-keys.json",
            ".aide/routing/latest-route-decision.json",
            ".aide/gateway/latest-gateway-status.json",
            ".aide/providers/latest-provider-status.json",
            ".aide.local/state.json",
            ".env",
        ]:
            aide_lite.write_text(source_root / rel, "source-only\n")
        pack_root = self.build_pack(source_root)
        for rel in [
            "files/.aide/profile.yaml",
            "files/.aide/queue/index.yaml",
            "files/.aide/context/latest-task-packet.md",
            "files/.aide/reports/token-ledger.jsonl",
            "files/.aide/cache/latest-cache-keys.json",
            "files/.aide/routing/latest-route-decision.json",
            "files/.aide/gateway/latest-gateway-status.json",
            "files/.aide/providers/latest-provider-status.json",
            "files/.aide.local/state.json",
            "files/.env",
        ]:
            self.assertFalse((pack_root / rel).exists(), rel)

    def test_export_checksums_match_and_are_deterministic(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        ok, problems = aide_lite.validate_pack_checksums(pack_root)
        self.assertTrue(ok, problems)
        checksum_data = json.loads(aide_lite.read_text(pack_root / "checksums.json"))
        self.assertEqual(checksum_data["checksum_scope"], "payload-and-static-pack-docs")
        self.assertIn("manifest.yaml", checksum_data["excluded_from_checksums"])
        self.assertNotIn("manifest.yaml", checksum_data["checksums"])
        self.assertNotIn("checksums.json", checksum_data["checksums"])
        self.assertNotIn("export-report.md", checksum_data["checksums"])
        first = aide_lite.read_text(pack_root / "checksums.json")
        self.build_pack(source_root)
        second = aide_lite.read_text(pack_root / "checksums.json")
        self.assertEqual(first, second)

    def test_pack_status_fails_for_payload_mismatch_not_manifest_metadata(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        aide_lite.write_text(pack_root / "manifest.yaml", aide_lite.read_text(pack_root / "manifest.yaml") + "# metadata note\n")
        ok, problems = aide_lite.validate_pack_checksums(pack_root)
        self.assertTrue(ok, problems)
        aide_lite.write_text(pack_root / "files/.aide/scripts/aide_lite.py", "# tampered payload\n")
        ok, problems = aide_lite.validate_pack_checksums(pack_root)
        self.assertFalse(ok)
        self.assertTrue(any("checksum mismatch: files/.aide/scripts/aide_lite.py" in problem for problem in problems))

    def test_pack_status_fails_for_unchecksummed_payload_file(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        aide_lite.write_text(pack_root / "files/.aide/untracked-payload.txt", "untracked\n")
        ok, problems = aide_lite.validate_pack_checksums(pack_root)
        self.assertFalse(ok)
        self.assertIn("unchecksummed pack file: files/.aide/untracked-payload.txt", problems)

    def test_export_manifest_records_provenance_fields(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        manifest = aide_lite.read_text(pack_root / "manifest.yaml")
        self.assertIn("source_commit:", manifest)
        self.assertIn("source_dirty_state:", manifest)
        self.assertIn("checksum_scope:", manifest)
        status, problems = aide_lite.validate_pack_provenance(pack_root, source_root)
        self.assertFalse(problems)
        self.assertIn(status, {"PASS", "DIRTY_SOURCE_RECORDED", "UNKNOWN_GIT_UNAVAILABLE"})

    def test_pack_provenance_fails_stale_clean_manifest(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        self.set_manifest_scalars(
            pack_root,
            {
                "source_commit": "old-commit",
                "source_dirty_state": "false",
            },
        )
        status, problems = aide_lite.validate_pack_provenance(pack_root, source_root, current_commit="new-commit")
        self.assertEqual(status, "FAIL")
        self.assertTrue(any("does not match current HEAD" in problem for problem in problems))

    def test_pack_provenance_allows_explicit_dirty_manifest(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        self.set_manifest_scalars(
            pack_root,
            {
                "source_commit": "old-commit",
                "source_dirty_state": "true",
            },
        )
        status, problems = aide_lite.validate_pack_provenance(pack_root, source_root, current_commit="new-commit")
        self.assertEqual(status, "DIRTY_SOURCE_RECORDED")
        self.assertFalse(problems)

    def test_import_dry_run_reports_without_writing(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        target = source_root.parent / "target-dry-run"
        aide_lite.write_text(target / "README.md", "# Target\n")
        result = aide_lite.apply_import_pack(pack_root, target, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["mode"], "safe")
        self.assertGreater(result["operation_count"], 10)
        self.assertTrue(result["operations"])
        self.assertTrue(result["skipped"])
        self.assertFalse((target / ".aide").exists())

    def test_import_fixture_creates_templates_and_preserves_agents(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        target = source_root.parent / "target"
        aide_lite.write_text(target / "README.md", "# Target\n")
        aide_lite.write_text(target / "AGENTS.md", "# Target Agents\n\nManual guidance.\n")
        result = aide_lite.apply_import_pack(pack_root, target, dry_run=False)
        self.assertFalse(result["conflicts"])
        agents = aide_lite.read_text(target / "AGENTS.md")
        self.assertIn("Manual guidance.", agents)
        self.assertIn("AIDE-PORTABLE:BEGIN", agents)
        for rel in [
            ".aide/profile.template.yaml",
            ".aide/profile.yaml",
            ".aide/memory/project-state.template.md",
            ".aide/memory/project-state.md",
            ".aide/memory/decisions.template.md",
            ".aide/memory/open-risks.template.md",
        ]:
            self.assertTrue((target / rel).exists(), rel)
        self.assertTrue(aide_lite.gitignore_has_local_state_rules(target))
        self.assertFalse((target / ".aide.local").exists())
        self.assertFalse((target / ".aide/queue/index.yaml").exists())
        self.assertFalse((target / aide_lite.LATEST_PACKET_PATH).exists())
        self.assertFalse((target / "core").exists())
        self.assertTrue((target / "docs/reference/commit-discipline.md").exists())
        self.assertFalse((target / "docs/roadmap").exists())

    def test_import_safe_mode_skips_broad_source_roots(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        target = source_root.parent / "target-safe-scope"
        aide_lite.write_text(target / "README.md", "# Target\n")
        result = aide_lite.apply_import_pack(pack_root, target, dry_run=True)
        skipped_sources = {item["source"] for item in result["skipped"]}
        planned_targets = {item["target"] for item in result["operations"]}
        self.assertTrue(any(source.startswith("core/") for source in skipped_sources), skipped_sources)
        self.assertFalse(any(target.startswith("core/") for target in planned_targets), planned_targets)
        self.assertTrue(any(target.startswith("docs/reference/") for target in planned_targets), planned_targets)
        self.assertFalse(any(target.startswith("docs/roadmap/") for target in planned_targets), planned_targets)

    def test_import_full_mode_is_explicit_for_optional_broad_roots(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        target = source_root.parent / "target-full-scope"
        aide_lite.write_text(target / "README.md", "# Target\n")
        result = aide_lite.apply_import_pack(pack_root, target, dry_run=True, mode="full")
        planned_targets = {item["target"] for item in result["operations"]}
        self.assertFalse(result["skipped"])
        self.assertTrue(any(target.startswith("core/") for target in planned_targets), planned_targets)
        self.assertTrue(any(target.startswith("docs/reference/") for target in planned_targets), planned_targets)

    def test_imported_aide_lite_doctor_snapshot_and_pack_run(self) -> None:
        source_root = self.make_source_repo()
        pack_root = self.build_pack(source_root)
        target = source_root.parent / "target-smoke"
        aide_lite.write_text(target / "README.md", "# Target Smoke\n")
        aide_lite.apply_import_pack(pack_root, target, dry_run=False)
        script = target / ".aide/scripts/aide_lite.py"
        commands = [
            ["doctor"],
            ["snapshot"],
            ["index"],
            ["pack", "--task", "Fixture target smoke task"],
        ]
        for command in commands:
            result = subprocess.run(
                [sys.executable, str(script), "--repo-root", str(target), *command],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((target / aide_lite.SNAPSHOT_PATH).exists())
        self.assertTrue((target / aide_lite.LATEST_PACKET_PATH).exists())

    def test_fake_secret_source_file_is_not_exported(self) -> None:
        source_root = self.make_source_repo()
        aide_lite.write_text(source_root / ".aide/prompts/compact-task.md", "api_key = \"abcdefghijklmnop\"\n")
        self.assertFalse(aide_lite.is_exportable_file(source_root, ".aide/prompts/compact-task.md"))
        pack_root = self.build_pack(source_root)
        self.assertFalse((pack_root / "files/.aide/prompts/compact-task.md").exists())


if __name__ == "__main__":
    unittest.main()
