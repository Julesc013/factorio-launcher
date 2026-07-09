from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
MOD_FIXTURES = ROOT / "tests" / "fixtures" / "factorio_mods"
GOLDENS = ROOT / "tests" / "golden" / "modsets"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def run_json(args: list[str]) -> tuple[int, dict, str]:
    code, stdout, stderr = invoke(args)
    if stdout.strip():
        return code, json.loads(stdout), stderr
    return code, {}, stderr


def setup_instance(workspace: Path) -> None:
    code, _stdout, stderr = invoke(
        [
            "--workspace",
            str(workspace),
            "installs",
            "import",
            str(FIXTURE_INSTALL),
            "--id",
            "fixture",
        ]
    )
    assert code == 0, stderr
    code, _stdout, stderr = invoke(
        [
            "--workspace",
            str(workspace),
            "instances",
            "create",
            "Modzip",
            "--install",
            "fixture",
            "--id",
            "modzip",
        ]
    )
    assert code == 0, stderr


def load_golden(name: str) -> dict:
    return json.loads((GOLDENS / name).read_text(encoding="utf-8"))


def fixture_zip(folder: str, file_name: str) -> Path:
    return MOD_FIXTURES / folder / file_name


def write_mod_zip(path: Path, info: dict, prefix: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    folder = prefix or path.stem
    zip_info = zipfile.ZipInfo(f"{folder}/info.json", (2026, 7, 9, 0, 0, 0))
    zip_info.compress_type = zipfile.ZIP_STORED
    zip_info.external_attr = 0o644 << 16
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(zip_info, json.dumps(info, indent=2, sort_keys=True) + "\n")


class ModZipDepthTests(unittest.TestCase):
    def test_valid_fixture_locks_match_goldens_and_preserve_sources(self) -> None:
        cases = {
            "valid_simple.modset_lock.v1.json": fixture_zip("valid_simple", "simple_mod_1.0.0.zip"),
            "valid_required_deps.modset_lock.v1.json": fixture_zip(
                "valid_required_deps",
                "required_deps_1.0.0.zip",
            ),
            "valid_optional_deps.modset_lock.v1.json": fixture_zip(
                "valid_optional_deps",
                "optional_deps_1.0.0.zip",
            ),
            "valid_incompatibilities.modset_lock.v1.json": fixture_zip(
                "valid_incompatibilities",
                "incompatible_mod_1.0.0.zip",
            ),
        }
        for golden_name, mod_zip in cases.items():
            with self.subTest(golden=golden_name):
                with tempfile.TemporaryDirectory() as tmp:
                    workspace = Path(tmp)
                    setup_instance(workspace)
                    before = sha256(mod_zip)

                    code, imported, stderr = run_json(
                        [
                            "--workspace",
                            tmp,
                            "mods",
                            "import",
                            str(mod_zip),
                            "--instance",
                            "modzip",
                            "--json",
                        ]
                    )
                    self.assertEqual(code, 0, stderr)
                    self.assertEqual(imported["validation_status"], "ok")
                    self.assertEqual(len(imported["sha1"]), 40)
                    self.assertEqual(len(imported["sha256"]), 64)

                    code, lock, stderr = run_json(
                        ["--workspace", tmp, "modsets", "lock", "modzip", "--json"]
                    )
                    self.assertEqual(code, 0, stderr)
                    self.assertEqual(lock, load_golden(golden_name))
                    self.assertEqual(sha256(mod_zip), before)
                    self.assertTrue(
                        (workspace / "modsets" / "modzip.modset-lock.v1.json").is_file()
                    )

    def test_invalid_fixture_imports_match_goldens_without_partial_install(self) -> None:
        cases = {
            "missing_info.refusal.v1.json": fixture_zip("missing_info_json", "missing_info_1.0.0.zip"),
            "malformed_info.refusal.v1.json": fixture_zip(
                "malformed_info_json",
                "malformed_info_1.0.0.zip",
            ),
            "invalid_filename.refusal.v1.json": fixture_zip("invalid_filename", "badname.zip"),
            "factorio_version_mismatch.refusal.v1.json": fixture_zip(
                "factorio_version_mismatch",
                "old_factorio_only_1.0.0.zip",
            ),
        }
        for golden_name, mod_zip in cases.items():
            with self.subTest(golden=golden_name):
                with tempfile.TemporaryDirectory() as tmp:
                    workspace = Path(tmp)
                    setup_instance(workspace)
                    before = sha256(mod_zip)
                    rel_path = mod_zip.relative_to(ROOT).as_posix()

                    code, refusal, _stderr = run_json(
                        [
                            "--workspace",
                            tmp,
                            "mods",
                            "import",
                            rel_path,
                            "--instance",
                            "modzip",
                            "--json",
                        ]
                    )

                    self.assertEqual(code, 1)
                    self.assertEqual(refusal, load_golden(golden_name))
                    self.assertEqual(sha256(mod_zip), before)
                    self.assertFalse(
                        (workspace / "instances" / "modzip" / "mods" / mod_zip.name).exists()
                    )

    def test_name_version_and_dependency_refusals_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            source = Path(tmp) / "sources"
            setup_instance(workspace)

            name_mismatch = source / "name_mismatch_1.0.0.zip"
            write_mod_zip(
                name_mismatch,
                {
                    "name": "actual_name",
                    "version": "1.0.0",
                    "title": "Actual Name",
                    "factorio_version": "2.0",
                },
            )
            version_mismatch = source / "version_mismatch_1.0.0.zip"
            write_mod_zip(
                version_mismatch,
                {
                    "name": "version_mismatch",
                    "version": "2.0.0",
                    "title": "Version Mismatch",
                    "factorio_version": "2.0",
                },
            )
            unsupported_dep = source / "unsupported_dep_1.0.0.zip"
            write_mod_zip(
                unsupported_dep,
                {
                    "name": "unsupported_dep",
                    "version": "1.0.0",
                    "title": "Unsupported Dependency",
                    "factorio_version": "2.0",
                    "dependencies": ["@ bad syntax"],
                },
            )

            expected = {
                name_mismatch: "mod_zip_name_mismatch",
                version_mismatch: "mod_zip_version_mismatch",
                unsupported_dep: "mod_dependency_unsupported_syntax",
            }
            for mod_zip, code_name in expected.items():
                code, refusal, _stderr = run_json(
                    [
                        "--workspace",
                        str(workspace),
                        "mods",
                        "import",
                        str(mod_zip),
                        "--instance",
                        "modzip",
                        "--json",
                    ]
                )
                self.assertEqual(code, 1)
                self.assertEqual(refusal["refusal"]["code"], code_name)
                self.assertFalse(
                    (workspace / "instances" / "modzip" / "mods" / mod_zip.name).exists()
                )

            unsatisfied = source / "unsatisfied_dep_1.0.0.zip"
            write_mod_zip(
                unsatisfied,
                {
                    "name": "unsatisfied_dep",
                    "version": "1.0.0",
                    "title": "Unsatisfied Dependency",
                    "factorio_version": "2.0",
                    "dependencies": ["missing_mod >= 1.0.0"],
                },
            )
            code, imported, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "mods",
                    "import",
                    str(unsatisfied),
                    "--instance",
                    "modzip",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(imported["dependencies"][0]["name"], "missing_mod")

            code, refusal, _stderr = run_json(
                ["--workspace", str(workspace), "modsets", "lock", "modzip", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(refusal["refusal"]["code"], "mod_dependency_unsatisfied")

    def test_duplicate_versions_and_incompatibilities_match_goldens(self) -> None:
        cases = [
            (
                "duplicate_versions.refusal.v1.json",
                [
                    fixture_zip("duplicate_mod_versions", "duplicate_mod_1.0.0.zip"),
                    fixture_zip("duplicate_mod_versions", "duplicate_mod_1.1.0.zip"),
                ],
            ),
            (
                "incompatibility_detected.refusal.v1.json",
                [
                    fixture_zip("valid_incompatibilities", "incompatible_mod_1.0.0.zip"),
                    fixture_zip("conflict_pair", "conflict_mod_1.0.0.zip"),
                ],
            ),
        ]
        for golden_name, mod_zips in cases:
            with self.subTest(golden=golden_name):
                with tempfile.TemporaryDirectory() as tmp:
                    setup_instance(Path(tmp))
                    for mod_zip in mod_zips:
                        code, imported, stderr = run_json(
                            [
                                "--workspace",
                                tmp,
                                "mods",
                                "import",
                                str(mod_zip),
                                "--instance",
                                "modzip",
                                "--json",
                            ]
                        )
                        self.assertEqual(code, 0, stderr)
                        self.assertEqual(imported["validation_status"], "ok")

                    code, refusal, _stderr = run_json(
                        ["--workspace", tmp, "modsets", "lock", "modzip", "--json"]
                    )
                    self.assertEqual(code, 1)
                    self.assertEqual(refusal, load_golden(golden_name))

    def test_verify_checks_sha1_and_sha256_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            setup_instance(workspace)
            mod_zip = fixture_zip("valid_simple", "simple_mod_1.0.0.zip")
            code, _imported, stderr = run_json(
                [
                    "--workspace",
                    tmp,
                    "mods",
                    "import",
                    str(mod_zip),
                    "--instance",
                    "modzip",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            code, _lock, stderr = run_json(["--workspace", tmp, "modsets", "lock", "modzip", "--json"])
            self.assertEqual(code, 0, stderr)

            copied = workspace / "instances" / "modzip" / "mods" / mod_zip.name
            copied.write_bytes(b"tampered")
            code, verify, _stderr = run_json(["--workspace", tmp, "modsets", "verify", "modzip", "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(verify["refusal"]["code"], "mod_hash_mismatch")
            self.assertTrue(any("sha1 mismatch" in problem for problem in verify["problems"]))
            self.assertTrue(any("sha256 mismatch" in problem for problem in verify["problems"]))

    def test_exported_modset_is_portable_and_source_tree_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            setup_instance(workspace)
            fixture_root = MOD_FIXTURES / "valid_simple"
            before = tree_snapshot(fixture_root)
            mod_zip = fixture_zip("valid_simple", "simple_mod_1.0.0.zip")

            code, _imported, stderr = run_json(
                [
                    "--workspace",
                    tmp,
                    "mods",
                    "import",
                    str(mod_zip),
                    "--instance",
                    "modzip",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            code, _lock, stderr = run_json(["--workspace", tmp, "modsets", "lock", "modzip", "--json"])
            self.assertEqual(code, 0, stderr)

            secret = workspace / "instances" / "modzip" / "config" / "secrets.txt"
            secret.write_text("token=super-secret-token\n", encoding="utf-8")
            pack = workspace / "exports" / "modset.zip"
            code, exported, stderr = run_json(
                [
                    "--workspace",
                    tmp,
                    "modsets",
                    "export",
                    "modzip",
                    str(pack),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(exported["files"], 2)
            self.assertEqual(tree_snapshot(fixture_root), before)

            pack_bytes = pack.read_bytes()
            self.assertNotIn(str(workspace).encode("utf-8"), pack_bytes)
            self.assertNotIn(b"super-secret-token", pack_bytes)
            with zipfile.ZipFile(pack) as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    ["mods/simple_mod_1.0.0.zip", "modset-lock.v1.json"],
                )


if __name__ == "__main__":
    unittest.main()
