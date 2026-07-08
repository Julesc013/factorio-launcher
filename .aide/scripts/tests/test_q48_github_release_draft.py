from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_q48", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_q48"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


class Q48GitHubReleaseDraftTests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for rel in [*aide_lite.Q47_POLICY_FILES, *aide_lite.Q47_SCHEMA_FILES, *aide_lite.Q48_POLICY_FILES, *aide_lite.Q48_SCHEMA_FILES, aide_lite.RELEASE_README_PATH]:
            source = REPO_ROOT / rel
            self.write(root, rel, source.read_text(encoding="utf-8"))
        self.write(root, ".gitignore", ".aide.local/\n.aide.local/**\n.env\nsecrets/\n")
        self.write(root, aide_lite.CHANGELOG_PREVIEW_MD_PATH, "# AIDE Changelog Preview\n\n- Added: fixture changelog entry.\n")
        self.write(root, aide_lite.RELEASE_NOTES_PREVIEW_MD_PATH, "# AIDE Release Notes Preview\n\n- Fixture release note.\n")
        self.write_pack(root)
        aide_lite.build_release_bundle_outputs(root)
        return root

    def write(self, root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def write_pack(self, root: Path) -> None:
        pack_root = aide_lite.export_pack_root(root, aide_lite.EXPORT_PACK_ID)
        self.write(root, f"{aide_lite.EXPORT_PACK_PATH}/README.md", "# Pack\n")
        self.write(root, f"{aide_lite.EXPORT_PACK_PATH}/install.md", "# Install\n")
        self.write(root, f"{aide_lite.EXPORT_PACK_PATH}/import-policy.yaml", "schema_version: fixture.import.v0\n")
        self.write(root, f"{aide_lite.EXPORT_PACK_PATH}/export-report.md", "# Export Report\n")
        self.write(root, f"{aide_lite.EXPORT_PACK_FILES_ROOT}/.aide/scripts/aide_lite.py", "# portable script\n")
        self.write(root, f"{aide_lite.EXPORT_PACK_FILES_ROOT}/docs/reference/aide-lite.md", "# AIDE Lite\n")
        self.write(
            root,
            f"{aide_lite.EXPORT_PACK_PATH}/manifest.yaml",
            "\n".join([
                "schema_version: q25.aide-lite-pack-manifest.v1",
                "pack_id: aide-lite-pack-v0",
                "source_commit: fixture-commit",
                "source_dirty_state: true",
                "files:",
                "  - files/.aide/scripts/aide_lite.py",
                "  - files/docs/reference/aide-lite.md",
            ]) + "\n",
        )
        checksums = aide_lite.build_pack_checksums(pack_root)
        self.write(root, f"{aide_lite.EXPORT_PACK_PATH}/checksums.json", aide_lite.stable_json_text(checksums))

    def run_cmd(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MODULE_PATH), "--repo-root", str(root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_policy_and_schema_validation(self) -> None:
        root = self.make_repo()
        checks = aide_lite.validate_github_release_draft_files(root, require_outputs=False)
        self.assertEqual(aide_lite.result_from_checks(checks), "PASS")

    def test_fixture_bundle_produces_draft_markdown_and_json(self) -> None:
        root = self.make_repo()
        draft = aide_lite.build_github_release_draft_outputs(root)
        self.assertTrue((root / aide_lite.GITHUB_RELEASE_DRAFT_MD_PATH).exists())
        self.assertTrue((root / aide_lite.GITHUB_RELEASE_DRAFT_JSON_PATH).exists())
        self.assertTrue(draft["no_publish"])
        self.assertIn("not published", draft["release_body_markdown"].lower())
        self.assertIn("aide-lite-pack-v0-draft-", draft["suggested_tag"])

    def test_assets_include_hashes_and_upload_plan_is_no_upload(self) -> None:
        root = self.make_repo()
        aide_lite.build_github_release_draft_outputs(root)
        assets = json.loads((root / aide_lite.GITHUB_RELEASE_ASSETS_JSON_PATH).read_text(encoding="utf-8"))
        self.assertGreaterEqual(assets["asset_count"], 8)
        for asset in assets["assets"]:
            if asset["validation_status"] == "present":
                self.assertTrue(asset["sha256"])
                self.assertGreater(asset["size_bytes"], 0)
        plan = json.loads((root / aide_lite.GITHUB_RELEASE_UPLOAD_PLAN_JSON_PATH).read_text(encoding="utf-8"))
        self.assertTrue(plan["no_upload"])
        self.assertIn("upload_release_asset", plan["blocked_actions"])

    def test_missing_required_asset_creates_blocker(self) -> None:
        root = self.make_repo()
        (root / aide_lite.RELEASE_ZIP_PATH).unlink()
        aide_lite.build_github_release_draft_outputs(root)
        validation = json.loads((root / aide_lite.GITHUB_RELEASE_DRAFT_VALIDATION_JSON_PATH).read_text(encoding="utf-8"))
        self.assertEqual(validation["result"], "FAIL")
        self.assertTrue(any("missing required release asset" in blocker or "required asset missing" in blocker for blocker in validation["blockers"]))

    def test_publication_boundary_is_false_and_advisory_only(self) -> None:
        root = self.make_repo()
        aide_lite.build_github_release_draft_outputs(root)
        boundary = aide_lite.github_release_boundary_data()
        for key in ["tag_created", "github_release_created", "upload_performed", "network_api_call", "branch_mutation", "active_ci_installed"]:
            self.assertFalse(boundary[key])
        result = self.run_cmd(root, "release", "publication-boundary")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no_publish: true", result.stdout)

    def test_draft_validate_rejects_implied_published_state(self) -> None:
        root = self.make_repo()
        aide_lite.build_github_release_draft_outputs(root)
        draft_path = root / aide_lite.GITHUB_RELEASE_DRAFT_JSON_PATH
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        draft["no_publish"] = False
        draft_path.write_text(json.dumps(draft), encoding="utf-8")
        checks = aide_lite.validate_github_release_draft_files(root, require_outputs=True)
        self.assertEqual(aide_lite.result_from_checks(checks), "FAIL")

    def test_draft_validate_rejects_checksum_mismatch(self) -> None:
        root = self.make_repo()
        aide_lite.build_github_release_draft_outputs(root)
        self.write(root, aide_lite.RELEASE_INSTALL_NOTES_PATH, "# tampered\n")
        checks = aide_lite.validate_github_release_draft_files(root, require_outputs=True)
        self.assertEqual(aide_lite.result_from_checks(checks), "FAIL")
        self.assertTrue(any("checksum mismatch" in check.message for check in checks))

    def test_commands_generate_local_only_outputs(self) -> None:
        root = self.make_repo()
        for args in [
            ("release", "draft"),
            ("release", "draft-validate"),
            ("release", "draft-status"),
            ("release", "upload-plan"),
            ("release", "checklist"),
            ("release", "publication-boundary"),
        ]:
            result = self.run_cmd(root, *args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("no_publish: true", result.stdout)
        self.assertTrue((root / aide_lite.GITHUB_RELEASE_DRAFT_MD_PATH).exists())
        self.assertTrue((root / aide_lite.GITHUB_RELEASE_DRAFT_VALIDATION_JSON_PATH).exists())


if __name__ == "__main__":
    unittest.main()
