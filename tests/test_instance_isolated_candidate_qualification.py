# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import instance_isolated_candidate_qualification as QUALIFICATION
from tools.play_verdict_route import (
    INSTANCE_ISOLATED_REVALIDATION as ROUTE,
    load_qualification_binding,
)


def source(repo_id: str, path: Path, revision: str, ref: str):
    return QUALIFICATION.QualifiedSource(
        repo_id=repo_id,
        path=path,
        revision=revision,
        required_ref=ref,
        remote=f"https://github.com/example/{repo_id}.git",
    )


def artifact_values() -> dict[str, dict[str, object]]:
    return {
        name: {
            "relative_path": relative,
            "size": index + 1,
            "sha256": str(index + 1) * 64,
        }
        for index, (name, relative) in enumerate(
            (
                ("facman", "Debug/facman.exe"),
                (
                    "candidate_smoke",
                    "Debug/facman_hermetic_play_candidate_smoke.exe",
                ),
                (
                    "verdict_harness",
                    "Debug/facman_gate4c_verdict_harness.exe",
                ),
                ("cmake_cache", "CMakeCache.txt"),
            )
        )
    }


class InstanceIsolatedCandidateQualificationTests(unittest.TestCase):
    def test_qualification_value_is_closed_hash_bound_and_reloadable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {
                "factorio-launcher": source(
                    "factorio-launcher", root / "facman", "1" * 40, "origin/dev"
                ),
                "universal-launcher": source(
                    "universal-launcher",
                    root / "launcher",
                    "2" * 40,
                    "origin/main",
                ),
                "universal-setup": source(
                    "universal-setup", root / "setup", "3" * 40, "origin/main"
                ),
            }
            value = QUALIFICATION.qualification_value(
                sources,
                artifact_values(),
                {
                    "version": "2.0.77",
                    "sha256": "a" * 64,
                    "signer": "Wube Software Ltd",
                },
                {
                    "instance_id": ROUTE.instance_id,
                    "spec_digest": "b" * 64,
                    "binding_digest": "c" * 64,
                    "readiness_digest": "d" * 64,
                },
            )
            path = root / "qualification.json"
            path.write_text(json.dumps(value), encoding="utf-8")

            loaded = load_qualification_binding(path, ROUTE)

            self.assertEqual(
                loaded.qualification_digest,
                value["qualification_digest"],
            )
            self.assertEqual(
                loaded.factorio_launcher.revision,
                "1" * 40,
            )

    def test_remote_closure_requires_exact_no_local_clean_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clone_root = root / "clones"
            build_root = root / "build"
            paths = {
                "factorio-launcher": clone_root / "factorio-launcher",
                "universal-launcher": clone_root / "universal-launcher",
                "universal-setup": clone_root / "universal-setup",
            }
            for path in [*paths.values(), build_root / "factorio-launcher"]:
                path.mkdir(parents=True)
            revisions = {
                "factorio-launcher": "1" * 40,
                "universal-launcher": "2" * 40,
                "universal-setup": "3" * 40,
            }
            branches = {
                "factorio-launcher": "dev",
                "universal-launcher": "main",
                "universal-setup": "main",
            }
            report = {
                "schema": QUALIFICATION.SOURCE_CLOSURE_SCHEMA,
                "status": "pass",
                "observed_at_utc": "2026-07-26T00:00:00Z",
                "claim": "remote_source_closure_proven",
                "authority_promotion": False,
                "factorio_execution": False,
                "permit_issuance": False,
                "publication": False,
                "clone_policy": {
                    "alternates": False,
                    "detached_exact_checkouts": True,
                    "empty_directories": True,
                    "git_clone_no_local": True,
                    "https_remotes_only": True,
                    "preexisting_objects": False,
                },
                "repositories": [
                    {
                        "id": name,
                        "remote": f"https://github.com/example/{name}.git",
                        "required_ref": f"refs/heads/{branches[name]}",
                        "pin": revisions[name],
                        "head": revisions[name],
                        "tree": "f" * 40,
                        "detached": True,
                        "clean": True,
                        "alternates": False,
                        "local_clone": False,
                        "canonical_ref_contains_pin": True,
                    }
                    for name in sorted(paths)
                ],
                "workspace": {
                    "clone_root": str(clone_root),
                    "build_root": str(build_root),
                    "paths_are_local_observations": True,
                    "source_worktrees_clean_after_validation": True,
                },
                "tooling": {
                    "git": "git version test",
                    "cmake": "cmake version test",
                    "python": "Python test",
                    "host": "Windows-test",
                },
                "validation": {
                    "steps": [
                        {
                            "label": f"step-{index}",
                            "status": "pass",
                            "command": ["test"],
                        }
                        for index in range(18)
                    ],
                    "test_counts": {
                        "factorio-launcher_native": 1,
                        "factorio-launcher_python": 1,
                        "universal-launcher_native": 1,
                        "universal-setup_native": 1,
                    },
                    "strict_repositories": [
                        "factorio-launcher",
                        "universal-launcher",
                        "universal-setup",
                    ],
                    "aide_lite": "pass",
                },
                "package": {
                    "profile_id": "windows_portable_cli_x64",
                    "package_file_count": 1,
                    "artifact": "facman.zip",
                    "artifact_size": 1,
                    "artifact_sha256": "a" * 64,
                    "provenance": "facman.zip.provenance.v1.json",
                    "provenance_sha256": "b" * 64,
                    "source_revisions": {
                        "factorio_launcher": revisions["factorio-launcher"],
                        "universal_launcher": revisions["universal-launcher"],
                        "universal_setup": revisions["universal-setup"],
                    },
                    "required_package_skips": 0,
                    "runtime_smoke": "pass",
                    "archive_runtime_smoke": "pass",
                    "provenance_verification": "pass",
                    "installed_sdk_proof": True,
                    "required_package_tests": 1,
                    "toolchain": {"compiler": "test"},
                    "signed": False,
                    "published": False,
                },
            }
            report_path = root / "closure.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")

            def git_output(path: Path, *args: str) -> str:
                if args == ("remote", "get-url", "origin"):
                    return f"https://github.com/example/{path.name}.git"
                if args == (
                    "rev-parse",
                    "--git-path",
                    "objects/info/alternates",
                ):
                    return str(path / ".git" / "objects" / "info" / "alternates")
                raise AssertionError(args)

            with (
                patch.object(
                    QUALIFICATION.PREFLIGHT,
                    "git_identity",
                    return_value={"valid": True},
                ),
                patch.object(
                    QUALIFICATION,
                    "_run_git",
                    side_effect=git_output,
                ),
                patch.object(QUALIFICATION, "_git_code", return_value=1),
            ):
                observed, loaded = QUALIFICATION.validate_remote_closure(
                    report_path,
                    factorio_repository=paths["factorio-launcher"],
                    launcher_repository=paths["universal-launcher"],
                    setup_repository=paths["universal-setup"],
                    candidate_build=build_root / "factorio-launcher",
                )

            self.assertEqual(set(observed), set(paths))
            self.assertEqual(loaded["status"], "pass")

            report["repositories"][0]["clean"] = False
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaises(QUALIFICATION.QualificationError):
                QUALIFICATION.validate_remote_closure(
                    report_path,
                    factorio_repository=paths["factorio-launcher"],
                    launcher_repository=paths["universal-launcher"],
                    setup_repository=paths["universal-setup"],
                    candidate_build=build_root / "factorio-launcher",
                )

    def test_instance_identity_requires_the_exact_nonexecuting_blocker(self) -> None:
        inspection = {
            "instance_id": ROUTE.instance_id,
            "factorio_version": "2.0.77",
            "modset_status": "present",
            "save_count": 0,
        }
        description = {
            "instance_spec": {"spec_digest": "a" * 64},
            "instance_binding": {"binding_digest": "b" * 64},
        }
        readiness = {
            "readiness_digest": "c" * 64,
            "blockers": [{"code": "real_play_gate_not_passed"}],
            "execution_started": False,
            "permit_issued": False,
        }
        launch = {"status": "pass", "started": False}
        with patch.object(
            QUALIFICATION.PREFLIGHT,
            "run_json",
            side_effect=[inspection, description, readiness, launch],
        ):
            identity, _ = QUALIFICATION.derive_instance_identity(
                Path("facman.exe"),
                Path("workspace"),
            )
        self.assertEqual(identity["readiness_digest"], "c" * 64)

        readiness["blockers"] = []
        with (
            patch.object(
                QUALIFICATION.PREFLIGHT,
                "run_json",
                side_effect=[inspection, description, readiness, launch],
            ),
            self.assertRaises(QUALIFICATION.QualificationError),
        ):
            QUALIFICATION.derive_instance_identity(
                Path("facman.exe"),
                Path("workspace"),
            )

    def test_qualify_writes_nonexecuting_binding_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_root = root / ROUTE.work_unit
            closure_path = root / "closure.json"
            closure_path.write_text("{}", encoding="utf-8")
            facman = root / "facman.exe"
            facman.write_bytes(b"facman")
            sources = {
                "factorio-launcher": source(
                    "factorio-launcher", root / "facman", "1" * 40, "origin/dev"
                ),
                "universal-launcher": source(
                    "universal-launcher",
                    root / "launcher",
                    "2" * 40,
                    "origin/main",
                ),
                "universal-setup": source(
                    "universal-setup", root / "setup", "3" * 40, "origin/main"
                ),
            }

            def extract(_source: Path, destination: Path) -> None:
                destination.parent.mkdir(parents=True)
                destination.write_bytes(b"factorio")

            def stage_workspace(workspace: Path, _instance: str, _exe: Path) -> None:
                workspace.mkdir(parents=True)

            with (
                patch.object(
                    QUALIFICATION,
                    "validate_remote_closure",
                    return_value=(sources, {"observed_at_utc": "2026-07-26T00:00:00Z"}),
                ),
                patch.object(
                    QUALIFICATION,
                    "resolve_artifacts",
                    return_value=(artifact_values(), {"facman": facman}),
                ),
                patch.object(
                    QUALIFICATION,
                    "_extract_source_member",
                    side_effect=extract,
                ),
                patch.object(
                    QUALIFICATION,
                    "factorio_identity",
                    return_value=(
                        {
                            "version": "2.0.77",
                            "sha256": "a" * 64,
                            "signer": "Wube Software Ltd",
                        },
                        {"authentication_evidence_digest": "e" * 64},
                    ),
                ),
                patch.object(
                    QUALIFICATION.COORDINATOR,
                    "_stage_workspace",
                    side_effect=stage_workspace,
                ),
                patch.object(
                    QUALIFICATION,
                    "derive_instance_identity",
                    return_value=(
                        {
                            "instance_id": ROUTE.instance_id,
                            "spec_digest": "b" * 64,
                            "binding_digest": "c" * 64,
                            "readiness_digest": "d" * 64,
                        },
                        {
                            "inspection": {},
                            "description": {},
                            "readiness": {},
                            "launch_preflight": {},
                        },
                    ),
                ),
                patch.object(
                    QUALIFICATION.PREFLIGHT,
                    "sha256_file",
                    return_value="f" * 64,
                ),
            ):
                result = QUALIFICATION.qualify(
                    argparse.Namespace(
                        task_root=task_root,
                        remote_source_closure=closure_path,
                        candidate_build=root / "build",
                        configuration="Debug",
                        repository_root=root / "facman",
                        launcher_repository=root / "launcher",
                        setup_repository=root / "setup",
                        factorio_executable=root / "factorio.exe",
                        source_artifact=root / "factorio.zip",
                    )
                )

            self.assertEqual(result["status"], "pass")
            self.assertFalse(result["factorio_execution"])
            self.assertFalse(result["permit_issuance"])
            binding = load_qualification_binding(
                Path(result["qualification_binding"]),
                ROUTE,
            )
            self.assertEqual(
                binding.qualification_digest,
                result["qualification_digest"],
            )
            report = json.loads(
                Path(result["qualification_report"]).read_text(encoding="utf-8")
            )
            self.assertFalse(report["authority_promotion"])
            self.assertFalse(report["human_verdict"])


if __name__ == "__main__":
    unittest.main()
