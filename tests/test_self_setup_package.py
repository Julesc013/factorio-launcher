# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "self_setup_package", ROOT / "tools/self_setup_package.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SelfSetupPackageTests(unittest.TestCase):
    def test_retirement_records_have_closed_schemas(self) -> None:
        schema_root = ROOT / "contracts/schema/facman"
        generation_id = "a" * 64
        common_step = {
            "generation_id": generation_id,
            "install_root": "C:/Programs/FacMan/generations/a",
            "install_id": "facman.self.generation." + generation_id,
            "active": True,
        }
        records = (
            (
                "facman_self_retirement_intent.v1.schema.json",
                {
                    "schema": "facman.self_retirement_intent.v1",
                    "head_name": "activation.maint.update.one.v1.json",
                    "head_sha256": "b" * 64,
                    "chain_digest": "c" * 64,
                    "steps": [common_step],
                },
            ),
            (
                "facman_self_retirement_step.v1.schema.json",
                {
                    "schema": "facman.self_retirement_step.v1",
                    "phase": "entered",
                    "sequence": "0",
                    **common_step,
                },
            ),
            (
                "facman_self_retirement_completed.v1.schema.json",
                {
                    "schema": "facman.self_retirement_completed.v1",
                    "head_name": "activation.maint.update.one.v1.json",
                    "head_sha256": "b" * 64,
                    "chain_digest": "c" * 64,
                    "completed_steps": "1",
                },
            ),
        )
        for name, record in records:
            schema = json.loads((schema_root / name).read_text(encoding="utf-8"))
            validator = jsonschema.Draft202012Validator(schema)
            validator.validate(record)
            with self.assertRaises(jsonschema.ValidationError):
                validator.validate({**record, "foreign": True})

    def test_windows_ci_requires_exactly_one_portable_and_payload(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("Select-Object -Single", workflow)
        self.assertIn("$portableMatches.Count -ne 1", workflow)
        self.assertIn("$payloadMatches.Count -ne 1", workflow)

    def portable(self, path: Path, extra: str | None = None) -> None:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            entries = [("bin/facman.exe", b"cli"),
                       ("FacMan.exe", b"gui"),
                       ("contracts/example.json", b"{}\n")]
            if extra is not None:
                entries.append((extra, b"bad"))
            # Rebuilding the same fixture must preserve the source archive's
            # bytes, including ZIP timestamps, because its hash binds payload.
            for name, content in entries:
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                archive.writestr(info, content)

    def build(self, root: Path, output_name: str) -> tuple[dict[str, object], Path]:
        portable = root / "FacMan-0.1.0-alpha.2-windows-x64-portable.zip"
        setup = root / "FacManSetup.exe"
        output = root / output_name
        record = MODULE.build(
            portable,
            setup,
            output,
            version="0.1.0-alpha.2",
            facman_revision="a" * 40,
            usk_revision="b" * 40,
            dirty=False,
        )
        return record, output

    def test_single_file_setup_binds_the_same_payload_and_native_overlay_identity(self) -> None:
        from tools import self_contained_setup, self_maintenance_candidate

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            portable = root / "FacMan-0.1.0-alpha.2-windows-x64-portable.zip"
            self.portable(portable)
            bootstrap = root / "FacManSetup.exe"
            original_bootstrap = b"MZ synthetic Setup overlay consumer fixture"
            bootstrap.write_bytes(original_bootstrap)
            split, split_root = self.build(root, "split")
            single = self_contained_setup.build(
                portable, bootstrap, root / "single", version="0.1.0-alpha.2",
                facman_revision="a" * 40, usk_revision="b" * 40, dirty=False,
            )
            executable = root / "single" / single["setup"]["filename"]
            self.assertEqual(
                self_maintenance_candidate.setup_overlay_sha256(executable),
                split["payload"]["sha256"],
            )
            identity = self_maintenance_candidate.identity_from_overlay(executable, portable)
            self.assertEqual(identity["version"], split["version"])
            self.assertEqual(identity["source_revision"], split["facman_source_revision"])
            self.assertEqual(identity["provider_revision"], split["universal_setup_revision"])
            self.assertEqual(single["embedded_payload"]["tree_digest"], split["payload"]["tree_digest"])
            self.assertEqual(single["embedded_payload"]["file_count"], split["payload"]["file_count"])
            self.assertEqual(single["setup"]["sha256"], MODULE.sha256_file(executable))
            self.assertEqual(single["setup"]["size_bytes"], executable.stat().st_size)
            with zipfile.ZipFile(executable) as archive:
                self.assertEqual(archive.read("facman/maintenance/FacManSetup.exe"), original_bootstrap)
                self.assertIn("facman/generations/0.1.0-alpha.2/FacMan.exe", archive.namelist())
            self.assertEqual(bootstrap.read_bytes(), original_bootstrap)
            self.assertEqual(
                MODULE.sha256_file(split_root / split["payload"]["filename"]),
                split["payload"]["sha256"],
            )

    def test_build_is_deterministic_and_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.portable(root / "FacMan-0.1.0-alpha.2-windows-x64-portable.zip")
            (root / "FacManSetup.exe").write_bytes(b"MZ synthetic setup")
            first, first_root = self.build(root, "first")
            second, second_root = self.build(root, "second")
            first_payload = first_root / first["payload"]["filename"]
            second_payload = second_root / second["payload"]["filename"]
            self.assertEqual(first_payload.read_bytes(), second_payload.read_bytes())
            self.assertEqual(first["payload"]["sha256"], second["payload"]["sha256"])
            with zipfile.ZipFile(first_payload) as archive:
                names = set(archive.namelist())
                self.assertIn(
                    "facman/generations/0.1.0-alpha.2/FacMan.exe", names
                )
                self.assertNotIn(
                    "facman/generations/0.1.0-alpha.2/bin/FacMan.WinForms.exe",
                    names,
                )
                self.assertIn("facman/maintenance/FacManSetup.exe", names)
                activation = json.loads(
                    archive.read("facman/state/current-generation.v1.json")
                )
                maintenance = json.loads(
                    archive.read("facman/state/self-maintenance-package.v1.json")
                )
            self.assertEqual(activation["version"], "0.1.0-alpha.2")
            self.assertFalse(activation["automatic_update"])
            self.assertTrue(activation["workspace_preserved"])
            self.assertEqual(maintenance["product_id"], "facman")
            self.assertEqual(
                maintenance["setup_protocol"], "facman.self_maintenance.v1"
            )
            self.assertEqual(
                maintenance["generation_relative_path"],
                "generations/0.1.0-alpha.2",
            )
            self.assertFalse(maintenance["automatic_update"])

            phase_schema = json.loads(
                (ROOT / "contracts/schema/facman/"
                 "facman_self_maintenance_phase.v1.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            validator = jsonschema.Draft202012Validator(phase_schema)
            provider_phase = {
                "schema": "facman.self_maintenance_phase.v1",
                "product_id": "facman",
                "operation": "update",
                "operation_id": "maintenance.update.schema-test",
                "phase": "20-provider-receipt",
                "source_generation_id": "a" * 64,
                "target_generation_id": "b" * 64,
                "package_sha256": "c" * 64,
                "provider_operation": "install_local",
                "state_root": "C:/State/FacMan/setup",
                "acceptance_root": "C:/State",
                "receipt_sha256": "d" * 64,
            }
            validator.validate(provider_phase)
            rollback_intent = {
                **provider_phase,
                "operation": "rollback",
                "phase": "00-intent",
                "package_sha256": "",
                "provider_operation": "none",
                "receipt_sha256": "",
            }
            validator.validate(rollback_intent)
            invalid_records = (
                {**provider_phase, "provider_operation": "none"},
                {**provider_phase, "receipt_sha256": ""},
                {**rollback_intent, "phase": "20-provider-receipt",
                 "receipt_sha256": "d" * 64},
                {**rollback_intent, "package_sha256": "c" * 64},
                {**rollback_intent, "receipt_sha256": "d" * 64},
            )
            for invalid in invalid_records:
                with self.assertRaises(jsonschema.ValidationError):
                    validator.validate(invalid)

            package_schema = json.loads(
                (ROOT / "contracts/schema/facman/"
                 "facman_self_maintenance_package.v1.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            package_validator = jsonschema.Draft202012Validator(package_schema)
            package_validator.validate(maintenance)
            generation_schema = json.loads(
                (ROOT / "contracts/schema/facman/"
                 "facman_self_generation.v1.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            generation_validator = jsonschema.Draft202012Validator(
                generation_schema
            )
            generation = {
                "schema": "facman.self_generation.v1",
                "product_id": "facman",
                "generation_id": "a" * 64,
                "product_version": "1.2.3-alpha.1+build.01",
                "package_sha256": "b" * 64,
                "facman_source_revision": "c" * 40,
                "universal_setup_revision": "d" * 40,
                "install_id": "facman.self.generation." + "a" * 64,
                "install_root": "C:/FacMan",
                "logical_root": "C:/FacMan",
                "state_root": "C:/State/FacMan/setup",
                "acceptance_root": "C:/State",
                "gui": "C:/FacMan/generations/1.2.3-alpha.1+build.01/FacMan.exe",
                "maintenance_launcher": "C:/FacMan/maintenance/FacManSetup.exe",
            }
            generation_validator.validate(generation)
            generation_validator.validate(
                {**generation, "install_id": "facman.self"}
            )
            activation_schema = json.loads(
                (ROOT / "contracts/schema/facman/"
                 "facman_self_activation.v1.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            activation_validator = jsonschema.Draft202012Validator(
                activation_schema
            )
            migration = {
                "schema": "facman.self_activation.v1",
                "product_id": "facman",
                "operation": "migration",
                "operation_id": "migration.schema-test",
                "generation_id": "a" * 64,
                "previous": {"name": "", "sha256": ""},
            }
            activation_validator.validate(migration)
            with self.assertRaises(jsonschema.ValidationError):
                activation_validator.validate(
                    {**migration, "operation": "update"}
                )
            with self.assertRaises(jsonschema.ValidationError):
                activation_validator.validate({
                    **migration,
                    "source_generation_id": "a" * 64,
                    "target_generation_id": "b" * 64,
                })
            for invalid_version in (
                "01.2.3",
                "1.2.3-alpha.01",
                "1.2.3+build..broken",
                "1.2.3/../../escape",
            ):
                with self.assertRaises(jsonschema.ValidationError):
                    generation_validator.validate(
                        {**generation, "product_version": invalid_version}
                    )
                with self.assertRaises(jsonschema.ValidationError):
                    package_validator.validate(
                        {
                            **maintenance,
                            "product_version": invalid_version,
                            "generation_relative_path":
                                "generations/" + invalid_version,
                        }
                    )

    def test_canonical_gui_input_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            portable = root / "FacMan-0.1.0-alpha.3-windows-x64-portable.zip"
            setup = root / "FacManSetup.exe"
            with zipfile.ZipFile(portable, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("bin/facman.exe", b"cli")
                archive.writestr("FacMan.exe", b"gui")
            setup.write_bytes(b"MZ synthetic setup")
            record = MODULE.build(
                portable,
                setup,
                root / "out",
                version="0.1.0-alpha.3",
                facman_revision="a" * 40,
                usk_revision="b" * 40,
                dirty=False,
            )
            with zipfile.ZipFile(root / "out" / record["payload"]["filename"]) as archive:
                names = set(archive.namelist())
            self.assertIn("facman/generations/0.1.0-alpha.3/FacMan.exe", names)

    def test_legacy_gui_layout_is_refused_before_writing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            portable = root / "legacy.zip"
            setup = root / "FacManSetup.exe"
            setup.write_bytes(b"MZ synthetic setup")
            for label, legacy, canonical in (
                ("legacy", True, False),
                ("mixed", True, True),
                ("missing", False, False),
            ):
                with self.subTest(layout=label):
                    with zipfile.ZipFile(portable, "w") as archive:
                        archive.writestr("bin/facman.exe", b"cli")
                        if legacy:
                            archive.writestr("bin/FacMan.WinForms.exe", b"gui")
                        if canonical:
                            archive.writestr("FacMan.exe", b"other gui")
                    output = root / (label + "-output")
                    with self.assertRaisesRegex(ValueError, "must not be relocated"):
                        MODULE.build(
                            portable, setup, output, version="0.1.0-alpha.3",
                            facman_revision="a" * 40, usk_revision="b" * 40,
                            dirty=False,
                        )
                    self.assertFalse(output.exists())

    def test_generation_preserves_portable_bytes_and_manifest_closure(self) -> None:
        from tools.package_hash_manifest import verify_manifest

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            portable = root / "product.zip"
            setup = root / "FacManSetup.exe"
            setup.write_bytes(b"MZ synthetic setup")
            original = {
                "FacMan.exe": b"managed GUI fixture",
                "bin/facman.exe": b"native CLI fixture",
                "facman.resources": b"synthetic resource closure fixture",
                "manifest/package.v1.toml": (
                    'schema = "facman.built_package.v1"\n'
                    'profile_id = "windows_product_x64"\n'
                    'entrypoint = "FacMan.exe"\n'
                ).encode(),
                "manifest/build_info.v1.json": b'{"source_commit":"unchanged"}\n',
            }
            components = []
            for name, target, destination in (
                ("winforms_gui", "apps/gui/windows/winforms", "FacMan.exe"),
                ("terminal_host", "facman_cli", "bin/facman.exe"),
                ("runtime_resources", "facman.resources", "facman.resources"),
            ):
                components.append({
                    "name": name, "source_target": target,
                    "destination": destination, "kind": "frontend",
                    "runtime_role": "runtime_required",
                    "sha256": hashlib.sha256(original[destination]).hexdigest(),
                    "size": len(original[destination]),
                })
            original["manifest/components.v1.json"] = json.dumps({
                "schema": "facman.package_components.v1", "components": components,
            }, sort_keys=True).encode()
            original["manifest/hashes.sha256"] = "".join(
                f"{hashlib.sha256(data).hexdigest()}  {name}\n"
                for name, data in sorted(original.items())
            ).encode()
            with zipfile.ZipFile(portable, "w") as archive:
                for name, data in original.items():
                    archive.writestr(name, data)
            portable_bytes = portable.read_bytes()
            record = MODULE.build(
                portable, setup, root / "output", version="0.1.0-alpha.3",
                facman_revision="a" * 40, usk_revision="b" * 40, dirty=False,
            )
            prefix = "facman/generations/0.1.0-alpha.3/"
            generation = root / "generation"
            with zipfile.ZipFile(root / "output" / record["payload"]["filename"]) as archive:
                members = {name[len(prefix):]: archive.read(name)
                           for name in archive.namelist() if name.startswith(prefix)}
            self.assertEqual(members, original)
            self.assertEqual(portable.read_bytes(), portable_bytes)
            self.assertEqual(record["portable_input"]["sha256"],
                             hashlib.sha256(portable_bytes).hexdigest())
            for name, data in members.items():
                destination = generation / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            self.assertEqual(verify_manifest(generation), [])
            # Independent refusal oracle: this is the historical conversion
            # defect, while the canonical portable manifests remain unchanged.
            (generation / "bin/FacMan.WinForms.exe").write_bytes(
                (generation / "FacMan.exe").read_bytes()
            )
            (generation / "FacMan.exe").unlink()
            self.assertTrue(verify_manifest(generation))

    def test_traversal_and_case_collision_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            setup = root / "FacManSetup.exe"
            setup.write_bytes(b"MZ")
            for extra in ("../escape", "BIN/FACMAN.EXE"):
                portable = root / "portable.zip"
                self.portable(portable, extra)
                with self.assertRaises(ValueError):
                    MODULE.build(
                        portable,
                        setup,
                        root / ("out-" + extra.replace("/", "-")),
                        version="0.1.0-alpha.2",
                        facman_revision="a" * 40,
                        usk_revision="b" * 40,
                        dirty=False,
                    )


if __name__ == "__main__":
    unittest.main()
