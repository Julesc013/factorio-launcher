# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

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
    def test_windows_ci_requires_exactly_one_portable_and_payload(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("Select-Object -Single", workflow)
        self.assertIn("$portableMatches.Count -ne 1", workflow)
        self.assertIn("$payloadMatches.Count -ne 1", workflow)

    def portable(self, path: Path, extra: str | None = None) -> None:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("bin/facman.exe", b"cli")
            archive.writestr("bin/FacMan.WinForms.exe", b"gui")
            archive.writestr("contracts/example.json", b"{}\n")
            if extra is not None:
                archive.writestr(extra, b"bad")

    def build(self, root: Path, output_name: str) -> tuple[dict[str, object], Path]:
        portable = root / "FacMan-0.1.0-alpha.2-windows-x64-portable.zip"
        setup = root / "FacManSetup.exe"
        output = root / output_name
        self.portable(portable)
        setup.write_bytes(b"MZ synthetic setup")
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

    def test_build_is_deterministic_and_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
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
