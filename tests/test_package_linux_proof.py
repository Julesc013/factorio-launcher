from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

from tools import package_layout_check

ROOT = Path(__file__).resolve().parents[1]


class LinuxPackageProofContractTests(unittest.TestCase):
    def test_profile_and_bundle_are_cli_only_and_target_specific(self) -> None:
        profile_path = ROOT / "release/profiles/linux_portable_cli_x64/profile.toml"
        with profile_path.open("rb") as handle:
            profile = tomllib.load(handle)
        bundle_path = ROOT / profile["package_manifest"]
        with bundle_path.open("rb") as handle:
            bundle = package_layout_check.expand_bundle_manifest(
                bundle_path,
                tomllib.load(handle),
                [],
            )
        self.assertEqual(profile["target_os"], "linux")
        self.assertEqual(profile["target_arch"], "x64")
        self.assertEqual(profile["runtime_floor"], "glibc_2_39_ci_baseline")
        self.assertEqual(profile["linkage"]["model"], "static_first")
        self.assertTrue(profile["linkage"]["system_dynamic_dependencies_inspected"])
        self.assertEqual(bundle["entrypoint"], "bin/facman")
        self.assertEqual(bundle["package_type"], "tarball")
        destinations = {component["destination"].rstrip("/") for component in bundle["components"]}
        self.assertEqual(destinations, {"bin/facman", "contracts/schema", "content/factorio"})
        self.assertFalse(any("tui" in item or "daemon" in item or "gui" in item for item in destinations))

    def test_proof_schemas_are_strict_and_zero_skip(self) -> None:
        proof_schema = json.loads(
            (
                ROOT
                / "contracts/schema/release/linux_cli_package_proof.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        linkage_schema = json.loads(
            (
                ROOT
                / "contracts/schema/release/linux_linkage_proof.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(proof_schema["properties"]["required_skips"]["const"], 0)
        self.assertEqual(proof_schema["properties"]["signed"]["const"], False)
        self.assertEqual(proof_schema["properties"]["published"]["const"], False)
        self.assertEqual(linkage_schema["properties"]["rpath"]["type"], "null")
        self.assertEqual(linkage_schema["properties"]["runpath"]["type"], "null")
        self.assertFalse(proof_schema["additionalProperties"])
        self.assertFalse(linkage_schema["additionalProperties"])

    def test_ci_invokes_required_proof_and_preserves_unsigned_evidence(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        proof = (ROOT / "tools/linux_package_proof.py").read_text(encoding="utf-8")
        for anchor in [
            "Run required Linux x64 CLI package proof with zero skips",
            "python tools/linux_package_proof.py",
            "actions/upload-artifact@v4",
            "build/linux-package-proof/dist/*.tar.gz",
            "build/linux-package-proof/dist/*.provenance.v1.json",
            "build/linux-package-proof/evidence.v1.json",
        ]:
            self.assertIn(anchor, workflow)
        for anchor in [
            "read_only_package_root",
            "wrong_architecture_refused",
            "linked_payload_refused",
            "archive_extraction_runtime",
            '"required_skips": 0',
            '"signed": False',
            '"published": False',
            "unsigned_provenance_verified",
        ]:
            self.assertIn(anchor, proof)

    def test_application_maps_the_linux_profile_to_setup_authority(self) -> None:
        setup = (
            ROOT / "runtime" / "factorio" / "application" / "handlers" / "setup.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '{"linux_portable_cli_x64", "linux", "x64", "static_first"}',
            setup,
        )
        self.assertIn('setup_execute("package.verify"', setup)


if __name__ == "__main__":
    unittest.main()
