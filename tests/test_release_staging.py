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
from contextlib import redirect_stdout
from pathlib import Path

import jsonschema

from tools import facman_release
from tools.release_compiler.assurance import (
    assure_candidate,
    verify_candidate_assurance,
)
from tools.release_compiler.canonical import digest_value, pretty_json
from tools.release_compiler.compiler import load_inputs, resolve
from tools.release_compiler.outputs import write_resolution
from tools.release_compiler.packages import archive_stage, inspect_package, verify_package
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
        cls.archive_filename = next(
            str(item["filename"])
            for item in outputs["package_plan"]["artifacts"]
            if item["id"] == ARTIFACT
        )
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
        modes: dict[str, int] | None = None,
    ) -> None:
        skipped = skip or set()
        changed = replacements or {}
        added = extras or {}
        changed_modes = modes or {}
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
                info.external_attr = changed_modes.get(relative, self.modes[relative]) << 16
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

    def test_archive_stage_is_resolution_named_deterministic_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = archive_stage(
                self.resolution,
                ARTIFACT,
                self.stage,
                root / "first",
            )
            second = archive_stage(
                self.resolution,
                ARTIFACT,
                self.stage,
                root / "second",
            )
            self.assertEqual(first.name, self.archive_filename)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            verification = verify_package(self.resolution, ARTIFACT, first)
            self.assertEqual(verification["stage_digest"], self.manifest["stage_digest"])
            self.assertEqual(
                verification["resolution_root_digest"],
                self.manifest["resolution_root_digest"],
            )
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), sorted(archive.namelist()))
                self.assertTrue(
                    all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist())
                )
                archived_manifest = json.loads(archive.read(STAGE_MANIFEST_PATH))
            self.assertFalse(archived_manifest["setup_mutation_authorized"])
            self.assertEqual(archived_manifest["staging_domain"], "release_build_output")

    def test_archive_command_builds_the_exact_resolved_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dist"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = facman_release.main(
                    [
                        "archive",
                        "--resolution",
                        str(self.resolution),
                        "--artifact",
                        ARTIFACT,
                        "--stage",
                        str(self.stage),
                        "--output",
                        str(output),
                    ]
                )
            archive = output / self.archive_filename
            self.assertEqual(result, 0)
            self.assertTrue(archive.is_file())
            self.assertIn(f"facman-release: archived {ARTIFACT}", stdout.getvalue())
            self.assertTrue(verify_package(self.resolution, ARTIFACT, archive)["verified"])

    def test_archive_refuses_tampered_stage_and_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tampered = root / "tampered-stage"
            shutil.copytree(self.stage, tampered)
            (tampered / "bin/facman.exe").write_bytes(b"tampered")
            refused_output = root / "refused"
            with self.assertRaisesRegex(ValueError, "does not match manifest"):
                archive_stage(
                    self.resolution,
                    ARTIFACT,
                    tampered,
                    refused_output,
                )
            self.assertFalse(refused_output.exists())

            existing_root = root / "existing"
            existing_root.mkdir()
            existing = existing_root / self.archive_filename
            existing.write_bytes(b"foreign-output")
            with self.assertRaisesRegex(ValueError, "already exists"):
                archive_stage(
                    self.resolution,
                    ARTIFACT,
                    self.stage,
                    existing_root,
                )
            self.assertEqual(existing.read_bytes(), b"foreign-output")
            self.assertEqual(
                list(existing_root.iterdir()),
                [existing],
                "archive refusal must remove its temporary output",
            )
            with self.assertRaisesRegex(ValueError, "outside the verified stage"):
                archive_stage(
                    self.resolution,
                    ARTIFACT,
                    self.stage,
                    self.stage / "dist",
                )
            self.assertFalse((self.stage / "dist").exists())

    def test_archive_stage_writes_deterministic_tar_gz_for_resolved_tar_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resolution = root / "resolution"
            outputs = resolve(load_inputs(INPUT_ROOT, ROOT), "linux_portable_cli_x64")
            write_resolution(resolution, outputs)
            artifact_id = "linux_portable_cli_tar_gz"
            filename = next(
                str(item["filename"])
                for item in outputs["package_plan"]["artifacts"]
                if item["id"] == artifact_id
            )
            staged = root / "stage"
            stage(resolution, artifact_id, ROOT, {"facman_cli": self.binary}, staged)
            first = archive_stage(resolution, artifact_id, staged, root / "first")
            second = archive_stage(resolution, artifact_id, staged, root / "second")
            self.assertEqual(first.name, filename)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(inspect_package(first)["format"], "tar")
            self.assertTrue(verify_package(resolution, artifact_id, first)["verified"])

    def test_candidate_assurance_refuses_a_non_winforms_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = archive_stage(self.resolution, ARTIFACT, self.stage, root / "dist")
            with self.assertRaisesRegex(ValueError, "only the WinForms Technical Preview ZIP"):
                assure_candidate(
                    self.resolution,
                    ARTIFACT,
                    self.stage,
                    archive,
                    root / "assurance",
                )
            self.assertFalse((root / "assurance").exists())

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
            wrong_mode = root / "wrong-mode.zip"
            self.archive_zip(extra, extras={"undeclared.txt": b"undeclared"})
            self.archive_zip(missing, skip={"licenses/LICENSE"})
            self.archive_zip(changed, replacements={"licenses/LICENSE": b"changed"})
            self.archive_zip(wrong_mode, modes={"licenses/LICENSE": 0o777})
            with self.assertRaisesRegex(ValueError, "extra=.*undeclared"):
                verify_package(self.resolution, ARTIFACT, extra)
            with self.assertRaisesRegex(ValueError, "missing=.*licenses/LICENSE"):
                verify_package(self.resolution, ARTIFACT, missing)
            with self.assertRaisesRegex(ValueError, "differs from canonical stage"):
                verify_package(self.resolution, ARTIFACT, changed)
            with self.assertRaisesRegex(ValueError, "differs from canonical stage"):
                verify_package(self.resolution, ARTIFACT, wrong_mode)

    def test_package_refuses_changed_embedded_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "changed-resolution.zip"
            relative = "manifest/resolution/runtime-release-metadata.v1.json"
            self.archive_zip(path, replacements={relative: b"{}\n"})
            with self.assertRaisesRegex(ValueError, "differs from canonical stage"):
                verify_package(self.resolution, ARTIFACT, path)

    def test_package_refuses_forged_authority_and_entry_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, mutate, message in (
                (
                    "authority",
                    lambda value: value.update(
                        {
                            "staging_domain": "installed_software",
                            "setup_mutation_authorized": True,
                        }
                    ),
                    "violates its schema",
                ),
                (
                    "metadata",
                    lambda value: value["entries"][0].update(
                        {
                            "owner": "attacker",
                            "ownership_class": "system_scope",
                            "source": "external://substitution",
                            "mode": 0o777,
                        }
                    ),
                    "entry metadata differs",
                ),
            ):
                package = root / name
                shutil.copytree(self.stage, package)
                manifest_path = package / STAGE_MANIFEST_PATH
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(manifest)
                core = dict(manifest)
                core.pop("stage_digest")
                manifest["stage_digest"] = digest_value(core)
                manifest_path.write_text(pretty_json(manifest), encoding="utf-8")
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, message):
                    verify_package(self.resolution, ARTIFACT, package)

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

    def test_archive_inspection_refuses_nonportable_names_and_types(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = {
                "reserved.zip": ["CON.txt"],
                "trailing.zip": ["trailing-dot."],
                "unicode.zip": ["cafe\u0301.txt"],
                "prefix.zip": ["CaseRoot", "caseroot/child.txt"],
            }
            for filename, members in cases.items():
                path = root / filename
                with zipfile.ZipFile(path, "w") as archive:
                    for member in members:
                        archive.writestr(member, b"fixture")
                with self.subTest(filename=filename), self.assertRaises(ValueError):
                    inspect_package(path)

            special_path = root / "special.zip"
            with zipfile.ZipFile(special_path, "w") as archive:
                special = zipfile.ZipInfo("fifo-entry")
                special.create_system = 3
                special.external_attr = (stat.S_IFIFO | 0o644) << 16
                archive.writestr(special, b"")
            with self.assertRaisesRegex(ValueError, "non-regular entry"):
                inspect_package(special_path)

    def test_tar_inspection_refuses_extreme_compression_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ratio.tar.gz"
            content = b"0" * (4 * 1024 * 1024)
            with tarfile.open(path, "w:gz") as archive:
                info = tarfile.TarInfo("zeros.bin")
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
            with self.assertRaisesRegex(ValueError, "compression ratio"):
                inspect_package(path)

    def test_directory_inspection_refuses_hardlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside.bin"
            outside.write_bytes(b"outside")
            package = root / "package"
            package.mkdir()
            linked = package / "linked.bin"
            try:
                os.link(outside, linked)
            except OSError as exc:
                self.skipTest(f"unsupported: hardlink creation is unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "hard-linked"):
                inspect_package(package)

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


class CanonicalCandidateAssuranceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.resolution = cls.root / "resolution"
        cls.stage = cls.root / "stage"
        cls.artifact_id = "windows_winforms_technical_preview_zip"
        outputs = resolve(
            load_inputs(INPUT_ROOT, ROOT),
            "windows_winforms_technical_preview_x64",
        )
        write_resolution(cls.resolution, outputs)
        cls.archive_filename = str(outputs["package_plan"]["artifacts"][0]["filename"])
        cls.cli = cls.root / "facman.exe"
        cls.winforms = cls.root / "FacMan.WinForms.exe"
        cls.cli.write_bytes(b"facman-cli-candidate-fixture\n" * 64)
        cls.winforms.write_bytes(b"facman-winforms-candidate-fixture\n" * 64)
        stage(
            cls.resolution,
            cls.artifact_id,
            ROOT,
            {"facman_cli": cls.cli, "facman_winforms": cls.winforms},
            cls.stage,
        )
        cls.archive = archive_stage(
            cls.resolution,
            cls.artifact_id,
            cls.stage,
            cls.root / "dist",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_assurance_is_deterministic_and_closes_candidate_without_authority(self) -> None:
        first_sbom, first_provenance = assure_candidate(
            self.resolution,
            self.artifact_id,
            self.stage,
            self.archive,
            self.root / "first-assurance",
        )
        second_sbom, second_provenance = assure_candidate(
            self.resolution,
            self.artifact_id,
            self.stage,
            self.archive,
            self.root / "second-assurance",
        )
        self.assertEqual(first_sbom.read_bytes(), second_sbom.read_bytes())
        self.assertEqual(first_provenance.read_bytes(), second_provenance.read_bytes())
        report = json.loads(first_provenance.read_text(encoding="utf-8"))
        self.assertEqual(report["artifact"]["name"], self.archive_filename)
        self.assertEqual(
            report["stage"]["stage_digest"],
            load_stage_manifest(self.stage)["stage_digest"],
        )
        self.assertEqual(len(report["licences"]), 6)
        self.assertTrue(report["runtime_verifier"]["static_closure_verified"])
        self.assertFalse(report["runtime_verifier"]["source_release_eligible"])
        self.assertFalse(report["runtime_verifier"]["native_admission_ready"])
        self.assertEqual(report["runtime_verifier"]["native_execution"], "not_run")
        self.assertTrue(all(value is False for value in report["authority"].values()))
        self.assertFalse(report["signed"])
        self.assertFalse(report["published"])
        self.assertNotIn(str(self.root), first_provenance.read_text(encoding="utf-8"))
        result = verify_candidate_assurance(
            self.resolution,
            self.artifact_id,
            self.stage,
            self.archive,
            first_sbom,
            first_provenance,
        )
        self.assertTrue(result["verified"])

    def test_assurance_command_and_verifier_reject_stale_or_existing_sidecars(self) -> None:
        output = self.root / "command-assurance"
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            result = facman_release.main(
                [
                    "assure-candidate",
                    "--resolution",
                    str(self.resolution),
                    "--artifact",
                    self.artifact_id,
                    "--stage",
                    str(self.stage),
                    "--archive",
                    str(self.archive),
                    "--output",
                    str(output),
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn(f"facman-release: assured {self.artifact_id}", stdout.getvalue())
        sbom = output / f"{self.archive.name}.sbom.spdx.v2.3.json"
        provenance = output / f"{self.archive.name}.provenance.v1.json"
        original_sbom = sbom.read_bytes()
        sbom_report = json.loads(original_sbom)
        sbom_report["packages"][0]["versionInfo"] = "stale-version"
        sbom.write_text(pretty_json(sbom_report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SPDX differs from the exact canonical stage"):
            verify_candidate_assurance(
                self.resolution,
                self.artifact_id,
                self.stage,
                self.archive,
                sbom,
                provenance,
            )
        sbom.write_bytes(original_sbom)
        original = provenance.read_bytes()
        report = json.loads(original)
        report["artifact"]["sha256"] = "0" * 64
        provenance.write_text(pretty_json(report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs from the exact canonical stage"):
            verify_candidate_assurance(
                self.resolution,
                self.artifact_id,
                self.stage,
                self.archive,
                sbom,
                provenance,
            )
        provenance.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "output already exists"):
            assure_candidate(
                self.resolution,
                self.artifact_id,
                self.stage,
                self.archive,
                output,
            )
        self.assertEqual(provenance.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
