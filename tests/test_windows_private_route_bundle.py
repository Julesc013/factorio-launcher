# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import windows_private_route_bundle as bundle


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class WindowsPrivateRouteBundleTests(unittest.TestCase):
    def inputs(self, root: Path) -> tuple[argparse.Namespace, dict[str, bytes]]:
        data = {
            "candidate": b"candidate",
            "archive": b"private Factorio bytes",
            "harness": b"harness",
            "route": b"route",
        }
        paths = {}
        for name, contents in data.items():
            path = root / name
            path.write_bytes(contents)
            paths[name] = path
        args = argparse.Namespace(
            candidate_zip=str(paths["candidate"]),
            candidate_sha256=digest(data["candidate"]),
            private_archive=str(paths["archive"]),
            private_archive_sha256=digest(data["archive"]),
            harness=str(paths["harness"]),
            harness_sha256=digest(data["harness"]),
            route_record=str(paths["route"]),
            route_record_sha256=digest(data["route"]),
            factorio_executable_sha256="a" * 64,
            route_id="route.test.v1",
            harness_acknowledgement="FACMAN-RELEASE-ROUTE-D3-D4-ONE-USE",
            output=str(root / "bundle"),
            allow_copy=False,
            launch=False,
        )
        return args, data

    def test_bundle_uses_narrow_mappings_and_no_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args, data = self.inputs(root)
            wsb_path = bundle.prepare_bundle(args)
            wsb = wsb_path.read_text(encoding="utf-8")
            manifest = json.loads(
                (root / "bundle" / "input" / "harness" / "manifest.v1.json").read_text(
                    encoding="utf-8"
                )
            )
            receipt = json.loads(
                (root / "bundle" / "bundle-receipt.v1.json").read_text(encoding="utf-8")
            )
            self.assertIn("<Networking>Disable</Networking>", wsb)
            self.assertEqual(wsb.count("<MappedFolder>"), 4)
            self.assertEqual(wsb.count("<ReadOnly>true</ReadOnly>"), 3)
            self.assertNotIn(str(root), json.dumps(manifest))
            self.assertNotIn("private Factorio bytes", json.dumps(manifest))
            self.assertFalse(receipt["private_archive_uploaded"])
            self.assertEqual(
                manifest["harness_acknowledgement"],
                "FACMAN-RELEASE-ROUTE-D3-D4-ONE-USE",
            )
            self.assertEqual(
                (root / "bundle" / "input" / "private" / "private-input.zip").read_bytes(),
                data["archive"],
            )
            guest = (root / "bundle" / "input" / "harness" / "run.ps1").read_text(
                encoding="utf-8"
            )
            self.assertIn("function Invoke-Required", guest)
            self.assertIn("$script:result.commands += $receipt", guest)
            self.assertIn("$roamingRoot", guest)
            self.assertIn("$localRoot", guest)
            self.assertIn("$tempRoot, $taskEvidenceRoot, $roamingRoot, $localRoot", guest)
            self.assertIn("Join-Path $taskEvidenceRoot \"engineering-$journey.v1.json\"", guest)
            self.assertIn("Copy-Item -LiteralPath $ResultFile -Destination", guest)
            self.assertIn("'--close-after-seconds', '90'", guest)
            self.assertIn("'--timeout-seconds', '180'", guest)
            self.assertLess(
                guest.index("Copy-Item -LiteralPath $ResultFile -Destination"),
                guest.index("if ($code -ne 0)"),
            )

    def test_digest_mismatch_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args, _data = self.inputs(root)
            args.private_archive_sha256 = "b" * 64
            with self.assertRaises(bundle.BundleError):
                bundle.prepare_bundle(args)
            self.assertFalse((root / "bundle").exists())

    def test_nonempty_output_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args, _data = self.inputs(root)
            output = Path(args.output)
            output.mkdir()
            (output / "foreign.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaises(bundle.BundleError):
                bundle.prepare_bundle(args)
            self.assertEqual((output / "foreign.txt").read_text(encoding="utf-8"), "foreign")

    def test_existing_empty_output_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args, _data = self.inputs(root)
            output = Path(args.output)
            output.mkdir()
            with self.assertRaises(bundle.BundleError):
                bundle.prepare_bundle(args)
            self.assertTrue(output.is_dir())

    def test_staging_failure_removes_only_new_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args, _data = self.inputs(root)
            with mock.patch.object(bundle.os, "link", side_effect=OSError("cross-volume")):
                with self.assertRaises(bundle.BundleError):
                    bundle.prepare_bundle(args)
            self.assertFalse(Path(args.output).exists())


if __name__ == "__main__":
    unittest.main()
