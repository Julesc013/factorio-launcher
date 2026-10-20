"""Portable public fixture namespace and allocation boundaries."""
import contextlib
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("portable_public_fixture_lite", ROOT / ".aide/scripts/aide_lite.py")
lite = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lite
spec.loader.exec_module(lite)

class PortablePublicFixtureTests(unittest.TestCase):
    def test_unmanaged_uses_standard_temp_and_retires_owned_fixture(self):
        with patch.dict(os.environ):
            os.environ.pop("AIDE_JOB_ID", None)
            with lite.public_archive_fixture("aide-public-release-test-") as directory:
                fixture = Path(directory)
                self.assertTrue(fixture.is_dir())
                (fixture / "public").write_bytes(b"public fixture\n")
            self.assertFalse(fixture.exists())

    def test_unknown_namespace_refuses_before_allocation(self):
        with patch.object(lite.tempfile, "TemporaryDirectory") as allocate:
            with self.assertRaisesRegex(ValueError, "namespace"):
                with lite.public_archive_fixture("../escape-"):
                    self.fail("invalid namespace cannot allocate")
            allocate.assert_not_called()

    def test_claimed_managed_job_without_host_runtime_fails_before_allocation(self):
        if (ROOT / "core/execution/managed_workspace.py").exists():
            self.skipTest("portable absence boundary is not a source-host test")
        with patch.dict(os.environ, {"AIDE_JOB_ID": "a" * 32}), patch.object(lite.tempfile, "TemporaryDirectory") as allocate:
            with self.assertRaises(ImportError):
                with lite.public_archive_fixture("aide-public-release-test-"):
                    self.fail("claimed job requires genuine host authentication")
            allocate.assert_not_called()

if __name__ == "__main__":
    unittest.main()
