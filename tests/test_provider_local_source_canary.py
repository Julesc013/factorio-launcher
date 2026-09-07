# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import provider_local_source_custody as custody

ROOT = Path(__file__).resolve().parents[1]


class LocalSourceCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="local-custody-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / "source"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("switch", "-q", "-c", "task/fixture")
        (self.repo / "payload.txt").write_text("fixture\n", encoding="utf-8")
        self.git("add", "payload.txt")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-q", "-m", "fixture")
        self.git("remote", "add", "origin", custody.REMOTE)
        self.commit = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD^{tree}")
        self.ref = "refs/heads/task/fixture"
        self.receipt = self.base / "review.json"
        self.review = {
            "schema": "facman.provider-checkpoint-root-review.v1", "result": "pass",
            "clean": True, "commit": self.commit, "tree": self.tree,
            "authority": {"consumer_qualification": False, "provider_adoption": False,
                          "publication": False},
        }
        self.path = self.base / "custody.json"
        self.data = {
            "schema": "facman.provider_local_source_custody.v1",
            "scope": "source_static_sdk_candidate_only",
            "source": {"commit": self.commit, "tree": self.tree, "ref": self.ref,
                       "repository": "Julesc013/universal-setup", "remote": custody.REMOTE},
            "review": {"receipt": str(self.receipt), "sha256": ""},
            "authority": {"provider_adoption": False, "publication": False,
                          "stable_identity": False, "release_eligible": False},
        }
        self.seal_review()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo,
                                       stderr=subprocess.STDOUT).decode().strip()

    def seal(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        self.digest = custody.sha256(self.path)

    def seal_review(self):
        self.receipt.write_text(json.dumps(self.review), encoding="utf-8")
        self.data["review"]["sha256"] = custody.sha256(self.receipt)
        self.seal()

    def validate(self, **overrides):
        args = dict(custody=self.path, expected_sha256=self.digest, root=self.repo,
                    commit=self.commit, tree=self.tree, remote=custody.REMOTE,
                    source_ref=self.ref)
        args.update(overrides)
        return custody.validate(**args)

    def test_exact_clean_local_checkpoint_needs_no_remote_branch(self):
        self.assertEqual(self.validate(), self.data)
        self.assertEqual(self.git("for-each-ref", "refs/remotes"), "")

    def test_changed_source_and_untracked_files_refuse(self):
        for name in ("payload.txt", "unknown.txt"):
            with self.subTest(name=name):
                path = self.repo / name
                before = path.read_bytes() if path.exists() else None
                path.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "dirty|physical provider bytes"):
                    self.validate()
                if before is None:
                    path.unlink()
                else:
                    path.write_bytes(before)

    def test_hidden_tracked_changes_refuse_python_and_actual_cmake(self):
        original = (self.repo / "payload.txt").read_bytes()
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag):
                self.git("update-index", "--" + flag, "payload.txt")
                try:
                    # Refuse the concealed source state even before its bytes change.
                    with self.assertRaisesRegex(ValueError, "flagged or sparse"):
                        self.validate()
                    (self.repo / "payload.txt").write_bytes(b"changed\n")
                    self.assertEqual(self.git("status", "--porcelain"), "")
                    self.assertEqual(self.git("rev-parse", "HEAD"), self.commit)
                    self.assertEqual(self.git("rev-parse", "HEAD^{tree}"), self.tree)
                    with self.assertRaisesRegex(ValueError, "flagged or sparse"):
                        self.validate()
                    result = self.cmake()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("flagged or sparse", result.stderr)
                finally:
                    (self.repo / "payload.txt").write_bytes(original)
                    self.git("update-index", "--no-" + flag, "payload.txt")
        self.assertEqual(self.validate(), self.data)

    def test_sparse_checkout_refuses_before_concealed_source_use(self):
        self.git("sparse-checkout", "init", "--no-cone")
        self.git("sparse-checkout", "set", "--no-cone", "!/payload.txt")
        self.assertFalse((self.repo / "payload.txt").exists())
        self.assertEqual(self.git("status", "--porcelain"), "")
        with self.assertRaisesRegex(ValueError, "flagged or sparse"):
            self.validate()
        result = self.cmake()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("flagged or sparse", result.stderr)

    def test_physical_bytes_are_compared_without_status_cache_authority(self):
        source = self.repo / "payload.txt"
        source.write_bytes(b"fixture\r\n")
        observed = custody.provider_source_bytes.observe(self.repo)
        self.assertEqual(observed["files"][0]["normalization"], "utf8_crlf_to_lf_v1")
        self.assertEqual(observed["files"][0]["raw_sha256"], custody.sha256(source))
        source.write_bytes(b"changed\n")
        with self.assertRaisesRegex(ValueError, "physical provider bytes"):
            custody.provider_source_bytes.observe(self.repo)

    def test_custom_filter_and_encoding_refuse_without_executing_filter(self):
        marker = self.base / "unexpected-filter-effect"
        helper = self.base / "filter.py"
        helper.write_text("from pathlib import Path\nPath(" + repr(str(marker)) +
                          ").write_text('unexpected')\n", encoding="utf-8")
        self.git("config", "filter.canary.clean", f'"{sys.executable}" "{helper}"')
        for attr in ("filter=canary", "working-tree-encoding=UTF-16"):
            with self.subTest(attr=attr):
                (self.repo / ".git/info/attributes").write_text(
                    "payload.txt " + attr + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "custom filter or encoding"):
                    self.validate()
                result = self.cmake()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("custom filter or encoding", result.stderr)
                self.assertFalse(marker.exists())

    def test_gitlink_and_symlink_entries_are_not_regular_source(self):
        for mode in ("120000", "160000"):
            with self.subTest(mode=mode):
                oid = self.commit if mode == "160000" else self.git("rev-parse", "HEAD:payload.txt")
                self.git("update-index", "--add", "--cacheinfo", mode + "," + oid + ",link")
                self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                         "commit", "-q", "-m", "unsupported fixture entry")
                with self.assertRaisesRegex(ValueError, "unsupported path or nonregular"):
                    custody.provider_source_bytes.observe(self.repo)

    def test_selected_identity_mismatch_refuses(self):
        for key, value in {"commit": "0" * 40, "tree": "1" * 40,
                           "source_ref": "refs/heads/task/other", "remote": "other"}.items():
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "selected provider lock"):
                self.validate(**{key: value})

    def test_same_tree_new_commit_does_not_inherit_review(self):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--allow-empty", "-q", "-m", "later")
        with self.assertRaisesRegex(ValueError, "HEAD/tree/ref"):
            self.validate()

    def test_detached_or_other_local_ref_refuses(self):
        self.git("switch", "-q", "-c", "task/other")
        with self.assertRaisesRegex(ValueError, "task ref"):
            self.validate()

    def test_changed_receipt_or_custody_refuses(self):
        self.receipt.write_bytes(self.receipt.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "receipt bytes"):
            self.validate()
        self.seal_review()
        self.path.write_bytes(self.path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "custody bytes"):
            self.validate()

    def test_numeric_false_and_authorizing_review_refuse(self):
        for value in (0, True):
            with self.subTest(value=value):
                self.review["authority"]["publication"] = value
                self.seal_review()
                with self.assertRaisesRegex(ValueError, "non-authorizing"):
                    self.validate()

    def test_wrong_review_tree_or_outcome_refuses(self):
        self.review["tree"] = "0" * 40
        self.seal_review()
        with self.assertRaisesRegex(ValueError, "non-authorizing"):
            self.validate()

    def test_bounded_duplicate_and_unknown_records_refuse(self):
        self.path.write_bytes(b" " * (custody.LIMIT + 1))
        with self.assertRaises(ValueError):
            self.validate(expected_sha256=custody.sha256(self.path))
        self.seal()
        raw = self.path.read_text().replace('{', '{"schema":"duplicate",', 1)
        self.path.write_text(raw)
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            self.validate(expected_sha256=custody.sha256(self.path))
        self.data["unexpected"] = True
        self.seal()
        with self.assertRaises(custody.jsonschema.ValidationError):
            self.validate()

    def cmake(self, *, local=True, mode="source", linkage="static", candidate=True):
        script = self.base / "probe.cmake"
        rows = ["cmake_minimum_required(VERSION 3.20)",
                f'include("{(ROOT / "cmake/FacManProviders.cmake").as_posix()}")',
                f'set(Python3_EXECUTABLE "{Path(sys.executable).as_posix()}")',
                f'set(FACMAN_PROVIDER_MODE {mode})',
                f'set(FACMAN_PROVIDER_SOURCE_LINKAGE {linkage})',
                f'set(FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE {"ON" if candidate else "OFF"})',
                'set(FACMAN_PROVIDER_CONFORMANCE_ONLY OFF)',
                'set(FACMAN_PROVIDER_LOCK_KIND sdk_candidate)']
        if local:
            rows += [f'set(FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE "{self.path.as_posix()}")',
                     f'set(FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_SHA256 "{self.digest}")']
        rows += [f'_facman_git_identity(commit tree "{self.repo.as_posix()}" "fixture" '
                 f'"{self.commit}" "{self.tree}" "{custody.REMOTE}" "{self.ref}")']
        script.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return subprocess.run(["cmake", "-P", str(script)], cwd=ROOT,
                              capture_output=True, text=True, check=False)

    def test_actual_cmake_accepts_only_explicit_local_source_mode(self):
        positive = self.cmake()
        self.assertEqual(positive.returncode, 0, positive.stdout + positive.stderr)
        ordinary = self.cmake(local=False)
        self.assertNotEqual(ordinary.returncode, 0)
        self.assertIn("selected origin ref", ordinary.stderr)
        for args in ({"mode": "installed_static"}, {"linkage": "shared"}, {"candidate": False}):
            with self.subTest(args=args):
                result = self.cmake(**args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("source-static SDK-candidate", result.stderr)


if __name__ == "__main__":
    unittest.main()
