from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

from tools import package_layout_check

ROOT = Path(__file__).resolve().parents[1]


class MacosPackageProofContractTests(unittest.TestCase):
    def test_profile_and_bundle_are_cli_only_intel_and_target_specific(self) -> None:
        profile_path = ROOT / "release/profiles/macos_portable_cli_x64/profile.toml"
        with profile_path.open("rb") as handle:
            profile = tomllib.load(handle)
        bundle_path = ROOT / profile["package_manifest"]
        with bundle_path.open("rb") as handle:
            bundle = package_layout_check.expand_bundle_manifest(
                bundle_path, tomllib.load(handle), []
            )
        self.assertEqual(profile["target_os"], "macos")
        self.assertEqual(profile["target_arch"], "x64")
        self.assertEqual(profile["minimum_os"], "macos_13_0")
        self.assertEqual(profile["linkage"]["model"], "static_first")
        self.assertTrue(profile["linkage"]["system_dynamic_dependencies_inspected"])
        self.assertEqual(bundle["entrypoint"], "bin/facman")
        self.assertEqual(bundle["package_type"], "tarball")
        destinations = {component["destination"].rstrip("/") for component in bundle["components"]}
        self.assertEqual(destinations, {"bin/facman", "contracts/schema", "content/factorio"})
        self.assertFalse(any("app" in item.lower() or "gui" in item.lower() for item in destinations))

    def test_proof_schemas_are_strict_unsigned_and_zero_skip(self) -> None:
        built_schema = json.loads(
            (ROOT / "contracts/schema/release/built_package.v1.schema.json").read_text(encoding="utf-8")
        )
        proof_schema = json.loads(
            (ROOT / "contracts/schema/release/macos_cli_package_proof.v1.schema.json").read_text(encoding="utf-8")
        )
        linkage_schema = json.loads(
            (ROOT / "contracts/schema/release/macos_linkage_proof.v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(proof_schema["properties"]["required_skips"]["const"], 0)
        self.assertIn("macos", built_schema["properties"]["target_os"]["enum"])
        self.assertEqual(proof_schema["properties"]["signed"]["const"], False)
        self.assertEqual(proof_schema["properties"]["notarized"]["const"], False)
        self.assertEqual(proof_schema["properties"]["published"]["const"], False)
        self.assertEqual(linkage_schema["properties"]["deployment_target"]["const"], "13.0")
        self.assertEqual(
            linkage_schema["properties"]["file_identity"]["const"],
            "Mach-O 64-bit executable x86_64",
        )
        self.assertEqual(linkage_schema["properties"]["rpath"]["type"], "null")
        self.assertFalse(proof_schema["additionalProperties"])
        self.assertFalse(linkage_schema["additionalProperties"])

        builder = (ROOT / "tools/package_build.py").read_text(encoding="utf-8")
        self.assertIn('raw_file_identity.partition(":")', builder)
        self.assertNotIn('"file_identity": raw_file_identity', builder)

    def test_ci_runs_full_native_and_package_proof_without_promoting_appkit(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        proof = (ROOT / "tools/macos_package_proof.py").read_text(encoding="utf-8")
        for anchor in [
            "macos-native-cli:",
            "runs-on: macos-15-intel",
            "CMAKE_OSX_DEPLOYMENT_TARGET=13.0",
            'export TMPDIR="$RUNNER_TEMP/facman-native-tmp"',
            'echo "TMPDIR=$TMPDIR" >> "$GITHUB_ENV"',
            "Prepare no-link temporary root",
            "ctest --test-dir build/macos-native --output-on-failure",
            "python -m unittest discover -s tests -v",
            "python tools/macos_package_proof.py",
            "build/macos-package-proof/dist/*.tar.gz",
            "build/macos-package-proof/dist/*.provenance.v1.json",
            "build/macos-package-proof/evidence.v1.json",
        ]:
            self.assertIn(anchor, workflow)
        for anchor in [
            "read_only_package_root",
            "wrong_architecture_refused",
            "linked_payload_refused",
            "archive_extraction_runtime",
            '"required_skips": 0',
            '"signed": False',
            '"notarized": False',
            "unsigned_provenance_verified",
        ]:
            self.assertIn(anchor, proof)
        appkit_job = workflow.split("appkit-compile:", 1)[1]
        self.assertNotIn("FacMan.app", appkit_job)
        self.assertNotIn("open ", appkit_job)

    def test_application_maps_macos_profile_to_setup_authority(self) -> None:
        setup = (
            ROOT / "runtime" / "factorio" / "application" / "handlers" / "setup.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '{"macos_portable_cli_x64", "macos", "x64", "static_first"}', setup
        )
        self.assertIn('setup_execute("package.verify"', setup)


if __name__ == "__main__":
    unittest.main()
