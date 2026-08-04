# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import io
import json
import os
import shutil
import stat
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

import jsonschema

from tools.release_compiler.compiler import load_inputs, resolve
from tools.release_compiler.outputs import write_resolution
from tools.release_compiler.packages import inspect_package, verify_package
from tools.release_compiler.staging import (
    STAGE_MANIFEST_PATH,
    load_stage_manifest,
    stage,
    verify_stage,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = ROOT / "release" / "index"
TARGET = "windows_portable_cli_x64"
ARTIFACT = "windows_portable_cli_zip"


class ReleaseStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.resolution = cls.root / "resolution"
        cls.binary = cls.root / "facman.exe"
        cls.binary.write_bytes((b"facman-release-stage-fixture\n" * 64) + bytes(range(256)))
        outputs = resolve(load_inputs(INPUT_ROOT, ROOT), TARGET)
        write_resolution(cls.resolution, outputs)
        cls.stage = cls.root / "stage"
        stage(cls.resolution, ARTIFACT, ROOT, {"facman_cli": cls.binary}, cls.stage)
        cls.manifest = load_stage_manifest(cls.stage)
        cls.modes = {str(item["path"]): int(item["mode"]) for item in cls.manifest["entries"]}
        cls.modes[STAGE_MANIFEST_PATH] = 0o644

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def archive_zip(
        self,
        path: Path,
        *,
        skip: set[str] | None = None,
        replacements: dict[str, bytes] | None = None,
        extras: dict[str, bytes] | None = None,
    ) -> None:
        skipped = skip or set()
        changed = replacements or {}
        added = extras or {}
        with zipfile.ZipFile(path, "w") as archive:
            for source in sorted(self.stage.rglob("*")):
                if not source.is_file():
                    continue
                relative = source.relative_to(self.stage).as_posix()
                if relative in skipped:
                    continue
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = self.modes[relative] << 16
                archive.writestr(info, changed.get(relative, source.read_bytes()))
            for relative, content in sorted(added.items()):
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, content)

    def archive_tar(self, path: Path) -> None:
        with tarfile.open(path, "w:gz") as archive:
            for source in sorted(self.stage.rglob("*")):
                if not source.is_file():
                    continue
                relative = source.relative_to(self.stage).as_posix()
                content = source.read_bytes()
                info = tarfile.TarInfo(relative)
                info.size = len(content)
                info.mode = self.modes[relative]
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                archive.addfile(info, io.BytesIO(content))

    def test_stage_has_file_level_ownership_and_verifies(self) -> None:
        result = verify_stage(self.resolution, ARTIFACT, self.stage)
        self.assertTrue(result["verified"])
        self.assertGreater(result["entry_count"], 300)
        owners = {str(item["owner"]) for item in self.manifest["entries"]}
        self.assertTrue({"facman_cli", "portable_zip"}.issubset(owners))
        self.assertEqual(
            self.manifest["resolution_digest"],
            result["resolution_digest"],
        )

    def test_stage_and_inspection_conform_to_json_schemas(self) -> None:
        stage_schema = json.loads(
            (ROOT / "contracts/schema/release/stage_manifest.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        inspection_schema = json.loads(
            (ROOT / "contracts/schema/release/package_inspection.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator(stage_schema).validate(self.manifest)
        jsonschema.Draft202012Validator(inspection_schema).validate(inspect_package(self.stage))

    def test_directory_zip_and_tar_are_equivalent_projections(self) -> None:
        directory = verify_package(self.resolution, ARTIFACT, self.stage)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            zip_path = root / "facman.zip"
            tar_path = root / "facman.tar.gz"
            self.archive_zip(zip_path)
            self.archive_tar(tar_path)
            zipped = verify_package(self.resolution, ARTIFACT, zip_path)
            tarred = verify_package(self.resolution, ARTIFACT, tar_path)
        self.assertTrue(directory["verified"])
        self.assertTrue(zipped["verified"])
        self.assertTrue(tarred["verified"])
        self.assertEqual(directory["stage_digest"], zipped["stage_digest"])
        self.assertEqual(directory["stage_digest"], tarred["stage_digest"])

    def test_stage_refuses_missing_and_unused_build_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "missing explicit build source"):
                stage(self.resolution, ARTIFACT, ROOT, {}, root / "missing")
            unused = root / "unused.bin"
            unused.write_bytes(b"unused")
            with self.assertRaisesRegex(ValueError, "unused build source"):
                stage(
                    self.resolution,
                    ARTIFACT,
                    ROOT,
                    {"facman_cli": self.binary, "other": unused},
                    root / "unused",
                )

    def test_stage_refuses_nonempty_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "stage"
            destination.mkdir()
            (destination / "foreign.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "absent or empty"):
                stage(
                    self.resolution,
                    ARTIFACT,
                    ROOT,
                    {"facman_cli": self.binary},
                    destination,
                )

    def test_stage_refuses_symlink_build_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            link = root / "facman-link.exe"
            try:
                os.symlink(self.binary, link)
            except OSError as exc:
                self.skipTest(f"unsupported: symlink creation is unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "symbolic link or reparse point"):
                stage(
                    self.resolution,
                    ARTIFACT,
                    ROOT,
                    {"facman_cli": link},
                    root / "stage",
                )

    def test_verify_stage_refuses_tamper_and_undeclared_addition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "tampered"
            shutil.copytree(self.stage, tampered)
            (tampered / "bin/facman.exe").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "does not match manifest"):
                verify_stage(self.resolution, ARTIFACT, tampered)
            added = Path(temporary) / "added"
            shutil.copytree(self.stage, added)
            (added / "undeclared.txt").write_text("undeclared", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "extra=.*undeclared"):
                verify_stage(self.resolution, ARTIFACT, added)

    def test_package_refuses_extra_missing_and_changed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extra = root / "extra.zip"
            missing = root / "missing.zip"
            changed = root / "changed.zip"
            self.archive_zip(extra, extras={"undeclared.txt": b"undeclared"})
            self.archive_zip(missing, skip={"licenses/LICENSE"})
            self.archive_zip(changed, replacements={"licenses/LICENSE": b"changed"})
            with self.assertRaisesRegex(ValueError, "extra=.*undeclared"):
                verify_package(self.resolution, ARTIFACT, extra)
            with self.assertRaisesRegex(ValueError, "missing=.*licenses/LICENSE"):
                verify_package(self.resolution, ARTIFACT, missing)
            with self.assertRaisesRegex(ValueError, "differs from canonical stage"):
                verify_package(self.resolution, ARTIFACT, changed)

    def test_package_refuses_changed_embedded_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "changed-resolution.zip"
            relative = "manifest/resolution/runtime-release-metadata.v1.json"
            self.archive_zip(path, replacements={relative: b"{}\n"})
            with self.assertRaisesRegex(ValueError, "differs from canonical stage"):
                verify_package(self.resolution, ARTIFACT, path)

    def test_archive_inspection_refuses_traversal_and_case_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            traversal = root / "traversal.zip"
            collision = root / "collision.zip"
            with zipfile.ZipFile(traversal, "w") as archive:
                archive.writestr("../escape.txt", b"escape")
            with zipfile.ZipFile(collision, "w") as archive:
                archive.writestr("Path/File.txt", b"one")
                archive.writestr("path/file.txt", b"two")
            with self.assertRaisesRegex(ValueError, "must not escape"):
                inspect_package(traversal)
            with self.assertRaisesRegex(ValueError, "collide under case folding"):
                inspect_package(collision)

    def test_tar_inspection_refuses_symbolic_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "link.tar"
            with tarfile.open(path, "w") as archive:
                info = tarfile.TarInfo("linked")
                info.type = tarfile.SYMTYPE
                info.linkname = "target"
                archive.addfile(info)
            with self.assertRaisesRegex(ValueError, "non-regular entry"):
                inspect_package(path)


if __name__ == "__main__":
    unittest.main()
