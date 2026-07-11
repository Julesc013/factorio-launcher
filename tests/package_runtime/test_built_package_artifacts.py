from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import tomllib
import unittest
import zipfile
from pathlib import Path

from tools import package_build, package_runtime_smoke, provenance_build
from tools import package_hash_manifest

ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "build" / "native-smoke"
SECRET_CORPUS = ROOT / "tests" / "fixtures" / "redaction" / "secrets_corpus.v1.json"


class BuiltPackageArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not BUILD_ROOT.exists():
            raise unittest.SkipTest("native smoke build has not been created")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out_root = Path(cls._tmp.name) / "packages"
        cls.portable_cli = build_or_skip(cls, "portable_cli_x64")
        cls.portable_tui = build_or_skip(cls, "portable_tui_x64")

    @classmethod
    def tearDownClass(cls) -> None:
        tmp = getattr(cls, "_tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def test_portable_cli_runtime_smoke_runs_from_package_root(self) -> None:
        report = package_runtime_smoke.smoke_package(self.portable_cli)
        self.assertEqual(report["schema"], "facman.package_runtime_smoke.v1")
        self.assertEqual(report["product_id"], "factorio")
        self.assertTrue(report["contracts_found"])
        self.assertTrue(report["content_found"])
        self.assertFalse(report["python_runtime"])

    def test_portable_cli_contains_required_package_layout(self) -> None:
        required = [
            "bin/facman",
            "contracts/schema",
            "content/factorio",
            "docs",
            "licenses/LICENSE",
            "licenses/THIRD_PARTY_NOTICES.md",
            "release",
            "manifest/package.v1.toml",
            "manifest/build_info.v1.json",
            "manifest/components.v1.json",
            "manifest/hashes.sha256",
        ]
        for relative in required:
            self.assertTrue((self.portable_cli / relative).exists(), relative)

    def test_portable_tui_contains_tui_entrypoint_and_smokes_cli(self) -> None:
        self.assertTrue((self.portable_tui / "bin" / "facman-tui").exists())
        report = package_runtime_smoke.smoke_package(self.portable_tui)
        self.assertEqual(report["product_id"], "factorio")

    def test_hash_manifest_covers_all_package_files_except_itself(self) -> None:
        hashed = hash_manifest_destinations(self.portable_cli)
        expected = {
            path.relative_to(self.portable_cli).as_posix()
            for path in self.portable_cli.rglob("*")
            if path.is_file()
            and path.relative_to(self.portable_cli).as_posix() != "manifest/hashes.sha256"
            and not path.name.endswith(".sig")
        }
        self.assertEqual(hashed, expected)
        self.assertIn("manifest/components.v1.json", hashed)

    def test_component_manifest_records_profile_components(self) -> None:
        data = json.loads((self.portable_cli / "manifest" / "components.v1.json").read_text(encoding="utf-8"))
        destinations = {component["destination"] for component in data["components"]}
        self.assertIn("bin/facman", destinations)
        self.assertIn("lib/ulk", destinations)
        self.assertIn("lib/usk", destinations)
        self.assertIn("lib/flb_factorio", destinations)
        self.assertTrue(any(destination.startswith("contracts/schema/") for destination in destinations))
        self.assertTrue(any(destination.startswith("content/factorio/") for destination in destinations))

    def test_package_excludes_python_runtime_files(self) -> None:
        for root in [self.portable_cli, self.portable_tui]:
            leaked = [
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
                if path.name in {"python", "python3", "python.exe", "__pycache__"}
                or path.suffix in {".py", ".pyc", ".pyo"}
            ]
            self.assertEqual(leaked, [])

    def test_package_excludes_forbidden_factorio_payloads_and_secret_markers(self) -> None:
        forbidden_names = ["factorio.exe", "Factorio.app", "steamapps", "mod_portal_credentials"]
        for root in [self.portable_cli, self.portable_tui]:
            relative_paths = [path.relative_to(root).as_posix() for path in root.rglob("*")]
            for marker in forbidden_names:
                self.assertFalse(
                    any(marker.lower() in relative.lower() for relative in relative_paths),
                    marker,
                )
            package_text = read_text_payload(root)
            for secret in secret_values():
                self.assertNotIn(secret, package_text)

    def test_text_manifests_do_not_leak_source_tree_absolute_paths(self) -> None:
        forbidden = str(ROOT.resolve())
        for root in [self.portable_cli, self.portable_tui]:
            for path in text_payloads(root):
                self.assertNotIn(forbidden, path.read_text(encoding="utf-8"))


class BuiltPackageOutputOwnershipTests(unittest.TestCase):
    def test_builder_refuses_unowned_output_root_before_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "unowned"
            root.mkdir()
            valuable = root / "operator-data.txt"
            valuable.write_text("preserve\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unowned output root"):
                package_build.build_profile(
                    profile_id="portable_cli_x64",
                    out_root=root,
                    build_root=Path(tmp) / "missing-build",
                    dist_root=None,
                )
            self.assertEqual(valuable.read_text(encoding="utf-8"), "preserve\n")


@unittest.skipUnless(os.name == "nt", "target-specific Windows package proof")
class WindowsPortableCliPackageProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        facman = BUILD_ROOT / "Debug" / "facman.exe"
        if not facman.is_file():
            raise AssertionError(f"required Windows package proof binary is missing: {facman}")
        cls._tmp = tempfile.TemporaryDirectory(prefix="facman-windows-package-proof-")
        cls.temp_root = Path(cls._tmp.name)
        cls.out_root = cls.temp_root / "FacMan Ω package output"
        cls.dist_root = cls.temp_root / "FacMan Ω archives"
        cls.package_root = package_build.build_profile(
            profile_id="windows_portable_cli_x64",
            out_root=cls.out_root,
            build_root=BUILD_ROOT,
            dist_root=cls.dist_root,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        temp_root = getattr(cls, "temp_root", None)
        if temp_root is not None:
            for path in temp_root.rglob("*"):
                if path.is_file():
                    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        tmp = getattr(cls, "_tmp", None)
        if tmp is not None:
            for attempt in range(10):
                try:
                    tmp.cleanup()
                    break
                except PermissionError:
                    if attempt == 9:
                        raise
                    time.sleep(0.05)

    def test_static_first_layout_contains_only_the_functional_cli(self) -> None:
        self.assertTrue((self.package_root / "bin" / "facman.exe").is_file())
        self.assertFalse((self.package_root / "lib").exists())
        self.assertFalse((self.package_root / "bin" / "facman-tui.exe").exists())
        self.assertFalse((self.package_root / "bin" / "facmand.exe").exists())
        self.assertEqual(package_hash_manifest.verify_manifest(self.package_root), [])

    def test_runtime_smoke_is_relocated_unicode_pathless_and_arbitrary_cwd(self) -> None:
        report = package_runtime_smoke.smoke_package(self.package_root)
        self.assertEqual(report["integrity"], "sha256_consistent")
        self.assertEqual(report["authenticity"], "not_proven_unsigned")
        self.assertGreater(report["files_verified"], 0)
        self.assertTrue(report["pathless_runtime"])
        self.assertTrue(report["arbitrary_cwd"])

    def test_spdx_and_external_provenance_bind_artifact_and_manifests(self) -> None:
        artifact = next(self.dist_root.glob("*.zip"))
        provenance = artifact.with_name(artifact.name + ".provenance.v1.json")
        self.assertEqual(
            provenance_build.verify_artifact_provenance(
                provenance,
                artifact,
                self.package_root,
            ),
            [],
        )
        sbom = json.loads(
            (self.package_root / "manifest/sbom.spdx.v2.3.json").read_text(encoding="utf-8")
        )
        self.assertEqual(sbom["spdxVersion"], "SPDX-2.3")
        self.assertEqual(
            {package["name"] for package in sbom["packages"]},
            {"FacMan", "Universal Launcher", "Universal Setup", "Miniz"},
        )
        self.assertFalse(json.loads(provenance.read_text())["signed"])
        self.assertEqual(
            json.loads(provenance.read_text())["authenticity"],
            "publisher_authenticity_not_proven",
        )

        drifted_artifact_root = self.temp_root / "provenance artifact drift"
        drifted_artifact_root.mkdir()
        drifted_artifact = drifted_artifact_root / artifact.name
        shutil.copy2(artifact, drifted_artifact)
        drifted_artifact.write_bytes(drifted_artifact.read_bytes() + b"drift")
        self.assertIn(
            "artifact digest disagrees with provenance",
            provenance_build.verify_artifact_provenance(
                provenance,
                drifted_artifact,
                self.package_root,
            ),
        )

        for relative, expected in [
            ("manifest/components.v1.json", "manifest digest disagrees"),
            ("manifest/hashes.sha256", "manifest digest disagrees"),
            ("release/index/workspace_lock.v1.toml", "manifest digest disagrees"),
        ]:
            copied = self.temp_root / ("provenance " + relative.replace("/", "_"))
            shutil.copytree(self.package_root, copied)
            changed = copied / relative
            changed.write_bytes(changed.read_bytes() + b"\ndrift\n")
            self.assertTrue(
                any(
                    expected in problem
                    for problem in provenance_build.verify_artifact_provenance(
                        provenance,
                        artifact,
                        copied,
                    )
                )
            )

        for field in ("source_revisions", "ci"):
            changed_provenance = self.temp_root / f"changed-{field}.json"
            data = json.loads(provenance.read_text(encoding="utf-8"))
            if field == "source_revisions":
                data[field]["factorio_launcher"] = "0" * 40
            else:
                data[field]["provider"] = "github_actions"
            changed_provenance.write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(
                provenance_build.verify_artifact_provenance(
                    changed_provenance,
                    artifact,
                    self.package_root,
                )
            )

    def test_renamed_extracted_directory_smokes(self) -> None:
        renamed = self.temp_root / "Renamed FacMan Ω"
        shutil.copytree(self.package_root, renamed)
        report = package_runtime_smoke.smoke_package(renamed)
        self.assertEqual(report["integrity"], "sha256_consistent")

    def test_read_only_package_files_smoke(self) -> None:
        copied = self.temp_root / "read only package"
        shutil.copytree(self.package_root, copied)
        files = [path for path in copied.rglob("*") if path.is_file()]
        try:
            for path in files:
                os.chmod(path, stat.S_IREAD)
            report = package_runtime_smoke.smoke_package(copied)
            self.assertEqual(report["integrity"], "sha256_consistent")
        finally:
            for path in files:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)

    def test_external_workspace_is_not_created_by_read_only_smoke(self) -> None:
        workspace = self.temp_root / "separate workspace path"
        report = package_runtime_smoke.smoke_package(self.package_root, workspace)
        self.assertFalse(workspace.exists())
        self.assertFalse(report["doctor_workspace_write"])

    def test_missing_contracts_and_content_are_refused(self) -> None:
        for relative in ["contracts", "content"]:
            copied = self.temp_root / f"missing {relative}"
            shutil.copytree(self.package_root, copied)
            shutil.rmtree(copied / relative)
            completed = run_package_verify(copied)
            self.assertNotEqual(completed.returncode, 0)
            report = json.loads(completed.stdout)
            self.assertEqual(report["status"], "error")
            self.assertTrue(
                "missing required package path" in report["detail"]
                or "missing or unsafe hashed file" in report["detail"],
                report["detail"],
            )

    def test_hash_verifiers_detect_payload_drift_and_unhashed_files(self) -> None:
        drifted = self.temp_root / "drifted package"
        shutil.copytree(self.package_root, drifted)
        payload = drifted / "docs" / "README.md"
        payload.write_bytes(payload.read_bytes() + b"\nchanged\n")
        self.assertTrue(any("SHA-256 mismatch" in problem for problem in package_hash_manifest.verify_manifest(drifted)))
        self.assertNotEqual(run_package_verify(drifted).returncode, 0)

        extra = self.temp_root / "extra file package"
        shutil.copytree(self.package_root, extra)
        (extra / "unexpected.bin").write_bytes(b"unexpected")
        self.assertTrue(any("unhashed package file" in problem for problem in package_hash_manifest.verify_manifest(extra)))
        self.assertNotEqual(run_package_verify(extra).returncode, 0)

    def test_target_identity_is_runtime_enforced_even_after_rehash(self) -> None:
        wrong = self.temp_root / "wrong target package"
        shutil.copytree(self.package_root, wrong)
        manifest = wrong / "manifest" / "package.v1.toml"
        text = manifest.read_text(encoding="utf-8").replace('target_os = "windows"', 'target_os = "linux"')
        manifest.write_text(text, encoding="utf-8")
        package_hash_manifest.write_hash_manifest(wrong)
        self.assertEqual(package_hash_manifest.verify_manifest(wrong), [])
        completed = run_package_verify(wrong)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("target, linkage, or entrypoint identity", completed.stdout)

    def test_manifest_records_target_linkage_and_all_source_revisions(self) -> None:
        with (self.package_root / "manifest" / "package.v1.toml").open("rb") as handle:
            manifest = tomllib.load(handle)
        build_info = json.loads((self.package_root / "manifest" / "build_info.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["profile_id"], "windows_portable_cli_x64")
        self.assertEqual(manifest["target_os"], "windows")
        self.assertEqual(manifest["target_arch"], "x64")
        self.assertEqual(manifest["linkage_model"], "static_first")
        self.assertEqual(manifest["workspace_lock"], "release/index/workspace_lock.v1.toml")
        revisions = build_info["source_revisions"]
        self.assertEqual(set(revisions), {"factorio_launcher", "universal_launcher", "universal_setup"})
        self.assertTrue(all(value != "unknown" and len(value) == 40 for value in revisions.values()))
        self.assertEqual(manifest["source_revision"], build_info["source_commit"])
        self.assertEqual(manifest["source_revision"], revisions["factorio_launcher"])

        with (self.package_root / "release" / "index" / "workspace_lock.v1.toml").open("rb") as handle:
            workspace_lock = tomllib.load(handle)
        pins = {component["id"]: component["pin"] for component in workspace_lock["component"]}
        self.assertEqual(manifest["proof_baseline_revision"], pins["factorio_binding"])
        self.assertEqual(manifest["universal_launcher_revision"], pins["universal_launcher"])
        self.assertEqual(manifest["universal_setup_revision"], pins["universal_setup"])

    def test_component_roles_are_explicit_and_runtime_enforced(self) -> None:
        path = self.package_root / "manifest" / "components.v1.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        roles = {component["runtime_role"] for component in data["components"]}
        self.assertEqual(roles, {"runtime_required", "compatibility_reference"})
        by_destination = {component["destination"]: component for component in data["components"]}
        self.assertEqual(by_destination["bin/facman.exe"]["runtime_role"], "runtime_required")
        self.assertTrue(
            all(
                component["runtime_role"] == "compatibility_reference"
                for destination, component in by_destination.items()
                if destination.startswith("contracts/schema/") or destination.startswith("content/factorio/")
            )
        )

        invalid = self.temp_root / "invalid component role"
        shutil.copytree(self.package_root, invalid)
        invalid_path = invalid / "manifest" / "components.v1.json"
        invalid_data = json.loads(invalid_path.read_text(encoding="utf-8"))
        invalid_data["components"][0]["runtime_role"] = "untrusted_magic"
        invalid_path.write_text(json.dumps(invalid_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        package_hash_manifest.write_hash_manifest(invalid)
        self.assertTrue(package_hash_manifest.verify_manifest(invalid))
        completed = run_package_verify(invalid)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("runtime_role is invalid", completed.stdout)

    def test_unknown_profile_and_manifest_fields_are_refused_after_rehash(self) -> None:
        unknown = self.temp_root / "unknown profile"
        shutil.copytree(self.package_root, unknown)
        manifest = unknown / "manifest" / "package.v1.toml"
        text = manifest.read_text(encoding="utf-8").replace(
            'profile_id = "windows_portable_cli_x64"',
            'profile_id = "future_unreviewed_profile"',
        )
        manifest.write_text(text, encoding="utf-8")
        package_hash_manifest.write_hash_manifest(unknown)
        completed = run_package_verify(unknown)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unknown built package profile", completed.stdout)

        extra = self.temp_root / "extra manifest field"
        shutil.copytree(self.package_root, extra)
        manifest = extra / "manifest" / "package.v1.toml"
        manifest.write_text(manifest.read_text(encoding="utf-8") + 'unreviewed = "true"\n', encoding="utf-8")
        package_hash_manifest.write_hash_manifest(extra)
        completed = run_package_verify(extra)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unsupported package manifest field", completed.stdout)

    def test_workspace_lock_revision_mismatch_is_refused_after_rehash(self) -> None:
        mismatched = self.temp_root / "mismatched workspace lock"
        shutil.copytree(self.package_root, mismatched)
        manifest = mismatched / "manifest" / "package.v1.toml"
        text = manifest.read_text(encoding="utf-8")
        current = tomllib.loads(text)["universal_launcher_revision"]
        text = text.replace(current, "0" * 40, 1)
        manifest.write_text(text, encoding="utf-8")
        package_hash_manifest.write_hash_manifest(mismatched)
        completed = run_package_verify(mismatched)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("source revisions disagree with workspace lock", completed.stdout)

    def test_archive_name_uses_version_once_and_extracted_archive_smokes(self) -> None:
        build_info = json.loads((self.package_root / "manifest" / "build_info.v1.json").read_text(encoding="utf-8"))
        version = build_info["filename_version"]
        archives = list(self.dist_root.glob("*.zip"))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].name.count(version), 1)
        self.assertEqual(archives[0].name, f"{version}-windows-cli-x64-portable.zip")
        self.assertNotIn("facman-facman-", archives[0].name.lower())
        extracted = self.temp_root / "extracted archive Ω"
        with zipfile.ZipFile(archives[0]) as archive:
            archive.extractall(extracted)
        report = package_runtime_smoke.smoke_package(extracted)
        self.assertEqual(report["integrity"], "sha256_consistent")


@unittest.skipIf(os.name != "nt", "WinForms package layout proof is Windows-only")
class BuiltWindowsPackageArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not BUILD_ROOT.exists():
            raise unittest.SkipTest("native smoke build has not been created")
        if not (ROOT / "apps" / "gui" / "windows" / "winforms" / "bin" / "Debug" / "FacMan.WinForms.exe").is_file():
            raise unittest.SkipTest("WinForms shell has not been built")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out_root = Path(cls._tmp.name) / "packages"
        cls.package_root = build_or_skip(cls, "windows_legacy_winforms_x64")

    @classmethod
    def tearDownClass(cls) -> None:
        tmp = getattr(cls, "_tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def test_windows_package_contains_legacy_frontends_and_dlls(self) -> None:
        required = [
            "bin/FacMan.WinForms.exe",
            "bin/facman.exe",
            "bin/facman-tui.exe",
            "bin/facmand.exe",
            "bin/ulk.dll",
            "bin/usk.dll",
            "bin/flb_factorio.dll",
            "contracts/schema",
            "content/factorio",
        ]
        for relative in required:
            self.assertTrue((self.package_root / relative).exists(), relative)

    def test_windows_package_cli_smokes_from_package_root(self) -> None:
        report = package_runtime_smoke.smoke_package(self.package_root)
        self.assertEqual(report["product_id"], "factorio")


def build_or_skip(test_case: unittest.TestCase, profile_id: str) -> Path:
    try:
        return package_build.build_profile(
            profile_id=profile_id,
            out_root=test_case.out_root,
            build_root=BUILD_ROOT,
            dist_root=None,
        )
    except ValueError as exc:
        raise unittest.SkipTest(str(exc)) from exc


def run_package_verify(root: Path) -> subprocess.CompletedProcess[str]:
    executable = root / "bin" / "facman.exe"
    env = os.environ.copy()
    env["PATH"] = ""
    return subprocess.run(
        [str(executable), "package", "verify", "--json"],
        cwd=root.parent,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def hash_manifest_destinations(root: Path) -> set[str]:
    destinations: set[str] = set()
    for line in (root / "manifest" / "hashes.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        _, destination = line.split("  ", 1)
        destinations.add(destination)
    return destinations


def text_payloads(root: Path) -> list[Path]:
    suffixes = {".json", ".md", ".toml", ".txt", ".sha256"}
    return [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes]


def read_text_payload(root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in text_payloads(root))


def secret_values() -> list[str]:
    if not SECRET_CORPUS.is_file():
        return []
    data = json.loads(SECRET_CORPUS.read_text(encoding="utf-8"))
    return [str(value) for value in data.get("values", [])]


if __name__ == "__main__":
    unittest.main()
