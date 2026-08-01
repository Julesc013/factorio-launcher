# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import classic_preview_package_proof

ROOT = Path(__file__).resolve().parents[1]


class ClassicPreviewPackageProofTests(unittest.TestCase):
    def test_probe_parser_and_claim_boundary(self) -> None:
        lines = [
            "schema=facman.classic_preview_runtime_probe.v1",
            "platform=gtk",
            *[f"{key}={value}" for key, value in classic_preview_package_proof.REQUIRED_PROBE.items()],
            "diagnostic without equals",
        ]
        probe = classic_preview_package_proof.parse_probe("\n".join(lines))
        classic_preview_package_proof.require_probe(probe)
        self.assertEqual(probe["authority"], "fixture_only")
        self.assertEqual(probe["live_play"], "false")

    def test_deterministic_tar_and_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "stage"
            source.mkdir()
            executable = source / "usr/bin/facman-gui-gtk"
            executable.parent.mkdir(parents=True)
            executable.write_text("fixture\n", encoding="utf-8")
            executable.chmod(0o755)
            first = root / "first.tar.gz"
            second = root / "second.tar.gz"
            classic_preview_package_proof.deterministic_tar(source, first)
            classic_preview_package_proof.deterministic_tar(source, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            checksum = classic_preview_package_proof.write_artifact_checksum(first)
            self.assertTrue(classic_preview_package_proof.verify_artifact_checksum(first, checksum))

    def test_evidence_schema_is_closed_and_preview_only(self) -> None:
        schema = json.loads(
            (ROOT / "contracts/schema/release/classic_preview_package_proof.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(schema["additionalProperties"])
        claims = schema["properties"]["claims"]["properties"]
        self.assertEqual(schema["properties"]["status"]["const"], "provisional")
        self.assertEqual(claims["support"]["const"], "unavailable")
        self.assertEqual(claims["live_play"]["const"], False)
        self.assertEqual(claims["package"]["const"], "frontend_prototype_only")
        self.assertEqual(schema["properties"]["source_dirty"]["const"], False)

    def test_complete_evidence_record_satisfies_strict_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "preview.tar.gz"
            artifact.write_bytes(b"deterministic preview")
            checksum = classic_preview_package_proof.write_artifact_checksum(artifact)
            manifest = root / "preview-files.sha256"
            manifest.write_text("0" * 64 + "  FacMan.app\n", encoding="utf-8")
            probe = {
                "schema": "facman.classic_preview_runtime_probe.v1",
                "platform": "appkit",
                **classic_preview_package_proof.REQUIRED_PROBE,
            }
            report = classic_preview_package_proof.evidence_report(
                platform_id="appkit",
                profile_id=classic_preview_package_proof.APPKIT_PROFILE,
                target_os="macos",
                revision="a" * 40,
                artifact=artifact,
                checksum_file=checksum,
                binary={
                    "identity": "Mach-O 64-bit executable x86_64",
                    "architectures": ["x86_64"],
                    "deployment_floor": "macos_10_13",
                    "dependencies": ["/System/Library/Frameworks/Cocoa.framework/Cocoa"],
                    "rpath": None,
                    "runpath": None,
                },
                probe=probe,
                relocated_probe=probe,
                manifest=manifest,
                file_count=1,
                signing={"status": "not_requested", "reason": "No credentials."},
                notarization={"status": "not_requested", "reason": "No credentials."},
                toolchain_identity="Xcode mutable hosted runner",
                platform_accessibility={
                    "at_spi_bridge": "not_applicable",
                    "orca": "not_applicable",
                    "external_at_spi": "not_applicable",
                    "high_contrast": "not_applicable",
                    "timeout_process_tree": "not_applicable",
                },
            )
            self.assertEqual(classic_preview_package_proof.validate_evidence(report), [])
            self.assertEqual(report["status"], "provisional")
            self.assertEqual(report["claims"]["package"], "frontend_prototype_only")
            self.assertEqual(report["signing"]["status"], "not_requested")
            self.assertFalse(report["package"]["profile_contract_satisfied"])

    def test_unsigned_gtk_is_provisional_and_cannot_be_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "preview.tar.gz"
            artifact.write_bytes(b"deterministic preview")
            checksum = classic_preview_package_proof.write_artifact_checksum(artifact)
            manifest = root / "preview-files.sha256"
            manifest.write_text("0" * 64 + "  usr/bin/facman-gui-gtk\n", encoding="utf-8")
            probe = {
                "schema": "facman.classic_preview_runtime_probe.v1",
                "platform": "gtk",
                **classic_preview_package_proof.REQUIRED_PROBE,
            }

            def report() -> dict[str, object]:
                return classic_preview_package_proof.evidence_report(
                    platform_id="gtk",
                    profile_id=classic_preview_package_proof.GTK_PROFILE,
                    target_os="linux",
                    revision="b" * 40,
                    artifact=artifact,
                    checksum_file=checksum,
                    binary={
                        "identity": "ELF 64-bit x86-64",
                        "architectures": ["x86_64"],
                        "deployment_floor": "ubuntu_24_04_gtk3_x11_runner",
                        "dependencies": ["libgtk-3.so.0"],
                        "rpath": None,
                        "runpath": None,
                    },
                    probe=probe,
                    relocated_probe=probe,
                    manifest=manifest,
                    file_count=1,
                    signing={"status": "not_requested", "reason": "Signing workflow deferred."},
                    notarization={"status": "not_requested", "reason": "Not applicable."},
                    toolchain_identity="cc hosted image",
                    platform_accessibility={
                        "at_spi_bridge": "pass",
                        "orca": "pass",
                        "external_at_spi": "pass",
                        "high_contrast": "pass",
                        "timeout_process_tree": "pass",
                    },
                )

            unsigned = report()
            self.assertEqual(classic_preview_package_proof.validate_evidence(unsigned), [])
            self.assertEqual(unsigned["status"], "provisional")
            self.assertEqual(unsigned["claims"]["package"], "frontend_prototype_only")
            self.assertEqual(unsigned["claims"]["support"], "unavailable")
            unsigned["status"] = "pass"
            unsigned["claims"]["package"] = "preview_pass"
            unsigned["signing"]["status"] = "pass"
            self.assertNotEqual(classic_preview_package_proof.validate_evidence(unsigned), [])

    def test_native_sources_expose_runtime_probes_and_bounded_tree_cleanup(self) -> None:
        appkit_delegate = (ROOT / "apps/gui/macos/appkit/AppDelegate.m").read_text(encoding="utf-8")
        appkit_window = (ROOT / "apps/gui/macos/appkit/MainWindowController.m").read_text(encoding="utf-8")
        gtk_main = (ROOT / "apps/gui/linux/gtk/main.c").read_text(encoding="utf-8")
        gtk_client = (ROOT / "apps/gui/linux/gtk/command_client.c").read_text(encoding="utf-8")
        for source in (appkit_delegate, gtk_main):
            self.assertIn("--facman-preview-self-test", source)
        self.assertIn("runPreviewSelfTestWithCompletion", appkit_window)
        for anchor in (
            "menu_keyboard=", "focus_restoration=", "appearance_recovery=",
            "fixture_journey=", "bounded_rpc=", "live_play=false",
        ):
            self.assertIn(anchor, appkit_window + gtk_main)
        self.assertIn("setpgid(0, 0)", gtk_client)
        self.assertIn("kill((pid_t)-pid, SIGTERM)", gtk_client)
        self.assertIn("FACMAN_PREVIEW_RPC_TIMEOUT_SECONDS", gtk_client)
        self.assertIn('"org.a11y.Bus"', gtk_main)
        at_spi = (ROOT / "tools/ci/gtk_atspi_probe.py").read_text(encoding="utf-8")
        session = (ROOT / "tools/ci/gtk_preview_accessibility_session.sh").read_text(encoding="utf-8")
        self.assertIn("Atspi.get_desktop(0)", at_spi)
        self.assertIn("primary_role != \"push button\"", at_spi)
        self.assertIn('rm -f -- "${FACMAN_PREVIEW_ORCA_MARKER}"', session)

    def test_ci_runs_both_hosted_preview_proofs(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        for anchor in (
            "runs-on: macos-15-intel",
            "classic_preview_package_proof.py appkit",
            "macos-appkit-x64-preview-${{ github.sha }}",
            "classic_preview_package_proof.py gtk",
            "linux-gtk3-x64-preview-${{ github.sha }}",
            "at-spi2-core",
            "orca python3-gi xvfb",
            "gir1.2-atspi-2.0",
            "python3-gi",
        ):
            self.assertIn(anchor, workflow)

    def test_workunit_is_active_until_hosted_evidence_exists(self) -> None:
        plan = (ROOT / "release/index/plan.v1.toml").read_text(encoding="utf-8")
        unit = plan.split('id = "C1-PREVIEW-RUNTIME-PACKAGES-01"', 1)[1].split("[[", 1)[0]
        self.assertIn('status = "active"', unit)
        self.assertIn('base_revision = "8f99e968e336b10eef3665a01f21f9c94a0a24e6"', unit)
        self.assertIn("All current evidence remains provisional", unit)
        self.assertIn("cannot claim full profile closure", unit)

        for profile_id in (classic_preview_package_proof.APPKIT_PROFILE, classic_preview_package_proof.GTK_PROFILE):
            profile = (ROOT / f"release/profiles/{profile_id}/profile.toml").read_text(encoding="utf-8")
            self.assertIn('artifact_scope = "frontend_only_prototype"', profile)
            self.assertIn("profile_contract_satisfied = false", profile)
            self.assertIn("clean_machine_product_package = false", profile)

    def test_credentials_are_absent_from_pull_request_proof(self) -> None:
        proof = (ROOT / "tools/classic_preview_package_proof.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("GPG_PRIVATE_KEY", proof + workflow)
        self.assertNotIn("GPG_SIGNING_KEY", proof + workflow)
        self.assertNotIn("APPLE_SIGNING_IDENTITY", proof + workflow)
        self.assertIn("pull-request CI receives no credentials", proof)

    def test_dirty_source_is_rejected_before_proof(self) -> None:
        with mock.patch.object(classic_preview_package_proof, "output", return_value=" M source.c"):
            with self.assertRaisesRegex(ValueError, "exact clean worktree"):
                classic_preview_package_proof.require_clean_source()
        with mock.patch.object(classic_preview_package_proof, "output", return_value=""):
            classic_preview_package_proof.require_clean_source()


if __name__ == "__main__":
    unittest.main()
