# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import unittest
from pathlib import Path

from tools import linux_self_setup


class LinuxSetupPredecessorCatalogTests(unittest.TestCase):
    def catalog(self, root: Path, *rows: tuple[str, str, str]) -> Path:
        path = root / "admission.toml"
        text = 'schema = "facman.linux_setup_predecessors.v1"\n'
        for target, version, digest in rows:
            text += (
                '\n[[predecessor]]\n'
                f'target_version = "{target}"\n'
                f'version = "{version}"\n'
                f'sha256 = "{digest}"\n'
                'qualification = "exact produced package receipt"\n'
            )
        path.write_text(text, encoding="utf-8")
        return path

    def test_current_catalog_preserves_exact_alpha5_admission(self) -> None:
        entries = linux_self_setup.admitted_predecessors("0.1.0-alpha.6")
        self.assertEqual(2, len(entries))
        self.assertEqual({"0.1.0-alpha.5"}, {item[0] for item in entries})
        shell = linux_self_setup.header("0.1.0-alpha.6", "0" * 64).decode()
        for version, digest in entries:
            self.assertIn(f"'{version}:{digest}'", shell)
        self.assertIn("refusing an unadmitted previous Setup package", shell)

    def test_later_package_embeds_only_its_exact_admitted_predecessors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            digest = "a" * 64
            old_digest = "b" * 64
            path = self.catalog(
                Path(temporary),
                ("0.1.0-alpha.6", "0.1.0-alpha.5", old_digest),
                ("0.1.0-alpha.7", "0.1.0-alpha.6", digest),
            )
            self.assertEqual(
                (("0.1.0-alpha.6", digest),),
                linux_self_setup.admitted_predecessors("0.1.0-alpha.7", path),
            )
            shell = linux_self_setup.header(
                "0.1.0-alpha.7", "0" * 64, predecessor_catalog=path,
            ).decode()
            self.assertIn(f"'0.1.0-alpha.6:{digest}'", shell)
            self.assertNotIn(old_digest, shell)
            earlier = linux_self_setup.header(
                "0.1.0-alpha.6", "0" * 64, predecessor_catalog=path,
            ).decode()
            self.assertIn(f"'0.1.0-alpha.5:{old_digest}'", earlier)
            self.assertNotIn(digest, earlier)

    def test_unqualified_and_ambiguous_catalogs_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = (
                (("0.1.0-alpha.7", "0.1.0-alpha.6", "x" * 64),),
                (("0.1.0-alpha.7", "0.1.0-alpha.6", "a" * 64),
                 ("0.1.0-alpha.7", "0.1.0-alpha.5", "a" * 64)),
                (("bad/version", "0.1.0-alpha.6", "a" * 64),),
                (("0.1.0-alpha.7", "bad/version", "a" * 64),),
                (("0.1.0-alpha.7", "0.1.0-alpha.7", "a" * 64),),
            )
            for rows in cases:
                with self.subTest(rows=rows):
                    with self.assertRaises(ValueError):
                        linux_self_setup.admitted_predecessors(
                            "0.1.0-alpha.7", self.catalog(root, *rows),
                        )
            with self.assertRaises(ValueError):
                linux_self_setup.admitted_predecessors(
                    "0.1.0-alpha.7", self.catalog(root),
                )

    @unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("zstd"),
                         "not_applicable: Linux package builder needs zstd")
    def test_builder_binds_exact_catalog_into_package_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            version = linux_self_setup.version_truth()
            product = root / f"FacMan-{version}"
            product.mkdir()
            payload = b"#!/bin/sh\nexit 0\n"
            digest = hashlib.sha256(payload).hexdigest()
            for name in ("FacMan", "facman"):
                executable = product / name
                executable.write_bytes(payload)
                executable.chmod(0o755)
            manifest = product / "share/facman/manifest/MANIFEST.sha256"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                f"{digest}  FacMan\n{digest}  facman\n", encoding="utf-8",
            )
            raw = root / "portable.tar"
            with tarfile.open(raw, "w") as archive:
                archive.add(product, arcname=product.name)
            portable = root / f"FacMan-{version}-linux-x64-portable.tar.zst"
            subprocess.run(["zstd", "-q", "-o", str(portable), str(raw)], check=True)
            evidence = root / "evidence.json"
            record = linux_self_setup.build(portable, root / "out", evidence)
            self.assertEqual("pass", record["status"])
            self.assertEqual(
                linux_self_setup.sha256(linux_self_setup.PREDECESSORS),
                record["predecessor_catalog_sha256"],
            )
            self.assertEqual(
                [{"version": version, "sha256": sha}
                 for version, sha in linux_self_setup.admitted_predecessors(version)],
                record["admitted_predecessors"],
            )
            self.assertEqual(record, json.loads(evidence.read_text(encoding="utf-8")))
            setup = root / "out" / record["setup"]["filename"]
            result = subprocess.run([str(setup), "--version"], check=True,
                                    capture_output=True, text=True)
            self.assertEqual(version, result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
