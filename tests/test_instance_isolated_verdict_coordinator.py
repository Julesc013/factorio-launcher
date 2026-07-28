# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from tools import gate4c_verdict_preflight as PREFLIGHT
from tools import instance_isolated_verdict_coordinator as COORDINATOR
from tools import play_staged_candidate as STAGED
from tools.play_verdict_route import (
    INSTANCE_ISOLATED_REVALIDATION as ROUTE,
    QUALIFICATION_SCHEMA,
    RouteBindingError,
    digest_value,
    load_qualification_binding,
)


def qualification_value() -> dict[str, object]:
    core: dict[str, object] = {
        "schema": QUALIFICATION_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "route_id": ROUTE.route_id,
        "work_unit": ROUTE.work_unit,
        "source_binding": {
            "factorio_launcher": {
                "revision": "1" * 40,
                "required_ref": "origin/dev",
            },
            "universal_launcher": {
                "revision": "2" * 40,
                "required_ref": "origin/main",
            },
            "universal_setup": {
                "revision": "3" * 40,
                "required_ref": "origin/main",
            },
        },
        "artifacts": {
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
                    (
                        "evidence_probe",
                        "Debug/facman_evidence_probe.exe",
                    ),
                    ("cmake_cache", "CMakeCache.txt"),
                )
            )
        },
        "factorio": {
            "version": "2.0.77",
            "sha256": "a" * 64,
            "signer": "Wube Software Ltd",
        },
        "instance": {
            "instance_id": ROUTE.instance_id,
            "spec_digest": "b" * 64,
            "binding_digest": "c" * 64,
            "readiness_digest": "d" * 64,
        },
    }
    return {**core, "qualification_digest": digest_value(core)}


def instance_projection_value(
    qualification: dict[str, object],
    workspace: Path,
    *,
    binding_digest: str = "e" * 64,
    readiness_digest: str = "f" * 64,
) -> dict[str, object]:
    instance = qualification["instance"]
    assert isinstance(instance, dict)
    return {
        "inspection": {
            "instance_id": ROUTE.instance_id,
            "factorio_version": "2.0.77",
            "modset_status": "present",
            "save_count": 0,
        },
        "description": {
            "instance_spec": {
                "spec_digest": instance["spec_digest"],
            },
            "instance_binding": {
                "binding_digest": binding_digest,
            },
        },
        "readiness": {
            "readiness_digest": readiness_digest,
            "launch_intent": "menu",
            "blockers": [{"code": "real_play_gate_not_passed"}],
            "execution_started": False,
            "permit_issued": False,
        },
        "launch_preflight": {
            "status": "pass",
            "started": False,
            "executable": "D:/Games/Factorio/factorio.exe",
            "args": [
                "--config",
                str(workspace / "config.ini"),
                "--mod-directory",
                str(workspace / "mods"),
            ],
        },
    }


def staged_projection_value(
    qualification: dict[str, object],
    workspace: Path,
    *,
    binding_digest: str = "e" * 64,
    readiness_digest: str = "f" * 64,
) -> dict[str, object]:
    qualification_binding = COORDINATOR.parse_qualification_binding(
        qualification, ROUTE
    )
    return STAGED.build_staged_candidate(
        instance_projection_value(
            qualification,
            workspace,
            binding_digest=binding_digest,
            readiness_digest=readiness_digest,
        ),
        workspace=workspace,
        qualification=qualification_binding,
        route=ROUTE,
    )


def principal_value(
    *,
    sid_digest: str = "9" * 64,
    session_id: int = 7,
    integrity: str = "medium",
) -> dict[str, object]:
    core: dict[str, object] = {
        "schema": PREFLIGHT.WINDOWS_PRINCIPAL_SCHEMA,
        "provider_id": "windows.local-token.v1",
        "principal_sid_digest": sid_digest,
        "windows_session_id": session_id,
        "integrity": integrity,
        "valid": True,
    }
    return {**core, "principal_digest": digest_value(core)}


class FakeEvidenceIo:
    def __init__(self, probe: Path):
        self.probe = Path(probe)

    def read_json(self, path: Path):
        return {
            "payload": {
                "document": json.loads(Path(path).read_text(encoding="utf-8"))
            }
        }

    def inspect_file(self, path: Path):
        path = Path(path)
        if path.name == "facman_evidence_probe.exe":
            digest, size = "4" * 64, 4
        else:
            content = path.read_bytes()
            digest = PREFLIGHT.hashlib.sha256(content).hexdigest()
            size = len(content)
        return {
            "payload": {
                "file": {
                    "content_sha256": digest,
                    "bytes_read": size,
                }
            }
        }

    def hash_file(self, path: Path):
        return self.inspect_file(path)

    def write_new_json(self, path: Path, value: dict):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return {}

    def copy_file(
        self,
        source: Path,
        destination: Path,
        *,
        maximum_bytes: int,
    ):
        del maximum_bytes
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(Path(source).read_bytes())
        return {}


class InstanceIsolatedVerdictCoordinatorTests(unittest.TestCase):
    def test_workspace_stage_requires_exact_current_active_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "factorio" / "bin" / "x64" / "factorio.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"authenticated-factorio")
            identity = {
                "version": "2.0.77",
                "sha256": PREFLIGHT.sha256_file(executable),
                "signer": PREFLIGHT.EXPECTED_SIGNER,
            }
            workspace = root / "workspace"

            COORDINATOR._stage_workspace(
                workspace,
                ROUTE.instance_id,
                executable,
                identity,
            )

            record = json.loads(
                (
                    workspace
                    / "installs"
                    / "refs"
                    / "instance-isolated-factorio-2-0-77.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(record["lifecycle_status"], "active")
            self.assertEqual(record["verification"]["status"], "pass")
            self.assertEqual(
                record["verification"]["executable_sha256"],
                identity["sha256"],
            )
            self.assertEqual(len(record["last_verification_identity"]), 64)
            self.assertEqual(len(record["state_revision"]), 64)

            refused_workspace = root / "refused-workspace"
            with self.assertRaises(COORDINATOR.CoordinatorError):
                COORDINATOR._stage_workspace(
                    refused_workspace,
                    ROUTE.instance_id,
                    executable,
                    {**identity, "sha256": "0" * 64},
                )
            self.assertFalse(refused_workspace.exists())

    def test_instance_preflight_cannot_bypass_qualification(self) -> None:
        with self.assertRaises(PREFLIGHT.PreflightError):
            PREFLIGHT.build_preflight(
                Namespace(),
                route=ROUTE,
                qualification=None,
            )
        with self.assertRaisesRegex(
            PREFLIGHT.PreflightError, "staged candidate binding"
        ):
            PREFLIGHT.build_preflight(
                Namespace(),
                route=ROUTE,
                qualification=COORDINATOR.parse_qualification_binding(
                    qualification_value(), ROUTE
                ),
            )

    def test_relocated_instance_is_rebound_before_preflight(self) -> None:
        qualification = qualification_value()
        binding = COORDINATOR.parse_qualification_binding(
            qualification, ROUTE
        )
        workspace = Path("D:/evidence/revalidation/workspace")
        projections = instance_projection_value(
            qualification, workspace
        )

        def observe(**kwargs: object) -> dict[str, object]:
            with patch.object(
                PREFLIGHT,
                "run_json",
                side_effect=[
                    projections["inspection"],
                    projections["description"],
                    projections["readiness"],
                    projections["launch_preflight"],
                ],
            ):
                return PREFLIGHT.instance_evidence(
                    Path("facman.exe"),
                    workspace,
                    ROUTE.instance_id,
                    binding,
                    **kwargs,
                )

        self.assertFalse(observe()["valid"])
        unbound = observe(allow_unbound_runtime_digests=True)
        self.assertTrue(unbound["valid"])
        staged = staged_projection_value(qualification, workspace)
        rebound = observe(staged_instance=staged["instance"])
        self.assertTrue(rebound["valid"])
        changed = dict(staged["instance"])
        changed["binding_digest"] = "0" * 64
        self.assertFalse(observe(staged_instance=changed)["valid"])

    def test_operator_attestations_are_explicit_exact_and_never_defaulted(
        self,
    ) -> None:
        exact = [
            f"{name}=true"
            for name in sorted(PREFLIGHT.INSTANCE_OPERATOR_CLAIMS)
        ]
        parsed = COORDINATOR._named_booleans(
            exact,
            expected=PREFLIGHT.INSTANCE_OPERATOR_CLAIMS,
            context="operator attestation",
        )
        self.assertTrue(all(parsed.values()))
        with self.assertRaises(COORDINATOR.CoordinatorError):
            COORDINATOR._named_booleans(
                exact[:-1],
                expected=PREFLIGHT.INSTANCE_OPERATOR_CLAIMS,
                context="operator attestation",
            )
        with self.assertRaises(COORDINATOR.CoordinatorError):
            COORDINATOR._named_booleans(
                exact + [exact[0]],
                expected=PREFLIGHT.INSTANCE_OPERATOR_CLAIMS,
                context="operator attestation",
            )

    def test_operation_ids_are_validated_before_staging(self) -> None:
        first = ROUTE.operation_prefix + "3f913de2-d6d6-4ed0-89d8-f5a3330216d7"
        second = ROUTE.operation_prefix + "d8320010-37e3-49b2-8c13-60165b04207c"
        COORDINATOR._validate_operation_ids(first, second)
        for invalid_first, invalid_second in (
            ("3f913de2-d6d6-4ed0-89d8-f5a3330216d7", second),
            (first, first),
            (first.upper(), second),
        ):
            with self.subTest(
                first=invalid_first, second=invalid_second
            ), self.assertRaises(COORDINATOR.CoordinatorError):
                COORDINATOR._validate_operation_ids(
                    invalid_first, invalid_second
                )

    def test_qualification_binding_is_closed_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "qualification.json"
            value = qualification_value()
            path.write_text(json.dumps(value), encoding="utf-8")
            binding = load_qualification_binding(path, ROUTE)
            self.assertEqual(binding.work_unit, ROUTE.work_unit)
            self.assertEqual(
                set(binding.artifact_mapping()),
                {
                    "facman",
                    "candidate_smoke",
                    "verdict_harness",
                    "evidence_probe",
                    "cmake_cache",
                },
            )

            value["factorio"]["version"] = "2.0.78"  # type: ignore[index]
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(RouteBindingError):
                load_qualification_binding(path, ROUTE)

    def test_configuration_binds_observed_principal_and_has_no_python_approval(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_root = root / ROUTE.work_unit
            operator = task_root / "operator"
            workspace = task_root / "workspace"
            repository = root / "facman"
            launcher = root / "launcher"
            setup = root / "setup"
            qualified_build = (
                task_root / "artifacts" / "qualified-build"
            )
            for directory in (
                operator,
                workspace,
                repository,
                launcher,
                setup,
                qualified_build,
            ):
                directory.mkdir(parents=True)
            files = {
                "qualification_binding": task_root
                / "qualification-binding.json",
                "staged_candidate_binding": qualified_build
                / "staged-candidate-binding.v1.json",
                "artifact_manifest": task_root / "manifest.json",
                "facman_artifact": task_root / "facman.exe",
                "evidence_probe": qualified_build
                / "facman_evidence_probe.exe",
                "factorio_executable": task_root / "factorio.exe",
                "source_artifact": task_root / "source.zip",
                "source_member_executable": task_root / "source-factorio.exe",
            }
            qualification = qualification_value()
            files["qualification_binding"].write_text(
                json.dumps(qualification), encoding="utf-8"
            )
            staged_candidate = staged_projection_value(
                qualification, workspace
            )
            files["staged_candidate_binding"].write_text(
                json.dumps(staged_candidate), encoding="utf-8"
            )
            for key, path in files.items():
                if key not in {
                    "qualification_binding",
                    "staged_candidate_binding",
                }:
                    path.write_bytes(key.encode("utf-8"))
            first = ROUTE.operation_prefix + "launch1"
            second = ROUTE.operation_prefix + "launch2"
            config = {
                "schema": COORDINATOR.CONFIG_SCHEMA,
                "task_root": str(task_root),
                "repository_root": str(repository),
                "launcher_repository": str(launcher),
                "setup_repository": str(setup),
                "qualification_binding": str(
                    files["qualification_binding"]
                ),
                "qualification_digest": qualification[
                    "qualification_digest"
                ],
                "staged_candidate_binding": str(
                    files["staged_candidate_binding"]
                ),
                "staged_candidate_digest": staged_candidate[
                    "staged_candidate_digest"
                ],
                "artifact_manifest": str(files["artifact_manifest"]),
                "facman_artifact": str(files["facman_artifact"]),
                "evidence_probe": str(files["evidence_probe"]),
                "workspace": str(workspace),
                "instance_id": ROUTE.instance_id,
                "factorio_executable": str(files["factorio_executable"]),
                "source_artifact": str(files["source_artifact"]),
                "source_member_executable": str(
                    files["source_member_executable"]
                ),
                "reviewer_principal": principal_value(),
                "first_operation_id": first,
                "second_operation_id": second,
            }
            config_path = operator / "instance-isolated-config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with patch.object(
                PREFLIGHT,
                "windows_principal_identity",
                return_value=principal_value(),
            ), patch.object(
                COORDINATOR, "EvidenceIo", FakeEvidenceIo
            ):
                loaded, binding, staged = COORDINATOR.validate_config(
                    config_path
                )
            self.assertEqual(loaded["instance_id"], ROUTE.instance_id)
            self.assertEqual(
                binding.qualification_digest,
                qualification["qualification_digest"],
            )
            self.assertEqual(
                staged["staged_candidate_digest"],
                staged_candidate["staged_candidate_digest"],
            )

            changed_staged = json.loads(
                files["staged_candidate_binding"].read_text(
                    encoding="utf-8"
                )
            )
            changed_staged["instance"]["binding_digest"] = "0" * 64
            files["staged_candidate_binding"].write_text(
                json.dumps(changed_staged), encoding="utf-8"
            )
            with (
                patch.object(
                    PREFLIGHT,
                    "windows_principal_identity",
                    return_value=principal_value(),
                ),
                patch.object(
                    COORDINATOR, "EvidenceIo", FakeEvidenceIo
                ),
                self.assertRaises(COORDINATOR.CoordinatorError),
            ):
                COORDINATOR.validate_config(config_path)
            files["staged_candidate_binding"].write_text(
                json.dumps(staged_candidate), encoding="utf-8"
            )

            config["evidence_probe"] = str(task_root / "attacker.exe")
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with (
                patch.object(
                    PREFLIGHT,
                    "windows_principal_identity",
                    return_value=principal_value(),
                ),
                patch.object(
                    COORDINATOR, "EvidenceIo", FakeEvidenceIo
                ),
                self.assertRaises(COORDINATOR.CoordinatorError),
            ):
                COORDINATOR.validate_config(config_path)
            config["evidence_probe"] = str(files["evidence_probe"])
            config_path.write_text(json.dumps(config), encoding="utf-8")

            with (
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                COORDINATOR.parser().parse_args(["approve-plan"])

            changed = principal_value(session_id=8)
            with patch.object(
                PREFLIGHT,
                "windows_principal_identity",
                return_value=changed,
            ), patch.object(
                COORDINATOR, "EvidenceIo", FakeEvidenceIo
            ):
                with self.assertRaises(COORDINATOR.CoordinatorError):
                    COORDINATOR.validate_config(config_path)

    def test_explicit_human_checks_derive_each_disposition_and_bind_output(
        self,
    ) -> None:
        for expected_disposition, exceptional in (
            ("Pass", {}),
            ("Fail", {"normal_menu_observed": "false"}),
            ("Inconclusive", {"normal_menu_observed": "unknown"}),
        ):
            with self.subTest(expected_disposition), tempfile.TemporaryDirectory() as temporary:
                task_root = Path(temporary) / ROUTE.work_unit
                task_root.mkdir()
                operation = ROUTE.operation_prefix + "launch1"
                config = {
                    "task_root": str(task_root),
                    "evidence_probe": str(task_root / "probe.exe"),
                    "first_operation_id": operation,
                    "second_operation_id": ROUTE.operation_prefix + "launch2",
                    "reviewer_principal": principal_value(),
                }
                session = {
                    "operation_id": operation,
                    "session_digest": "1" * 64,
                    "task_root": str(task_root),
                }
                packet = {"packet_digest": "2" * 64}
                checks = {
                    name: exceptional.get(name, "true")
                    for name in COORDINATOR.EVIDENCE.FIRST_LAUNCH_CHECKS
                }
                notes = {
                    name: (
                        "direct observation"
                        if checks[name] != "true"
                        else ""
                    )
                    for name in checks
                }
                output = (
                    task_root
                    / "evidence"
                    / "human"
                    / f"{operation}-launch-1.json"
                )
                displayed: list[str] = []

                def confirm(_: str) -> str:
                    return displayed[-1].splitlines()[-1]

                with (
                    patch.object(
                        COORDINATOR,
                        "validate_config",
                        return_value=(config, object(), object()),
                    ),
                    patch.object(
                        COORDINATOR.EVIDENCE,
                        "validate_session_record",
                        return_value=session,
                    ),
                    patch.object(
                        COORDINATOR.EVIDENCE,
                        "validate_native_packet",
                        return_value=packet,
                    ),
                    patch.object(
                        COORDINATOR, "EvidenceIo", FakeEvidenceIo
                    ),
                ):
                    result = COORDINATOR.human(
                        Namespace(
                            config=Path("config.json"),
                            launch=1,
                            session=Path("session.json"),
                            packet=Path("packet.json"),
                            check=[
                                f"{name}={value}"
                                for name, value in sorted(checks.items())
                            ],
                            check_note=[
                                f"{name}={value}"
                                for name, value in sorted(notes.items())
                            ],
                            notes="synthetic protocol proof",
                            out=output,
                        ),
                        input_fn=confirm,
                        output_fn=displayed.append,
                    )
                record = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(result["disposition"], expected_disposition)
                self.assertEqual(
                    record["disposition"], expected_disposition
                )
                self.assertEqual(record["launch_sequence"], 1)
                self.assertNotIn("grants_authority", record)

    def test_human_observation_rejects_swapped_launch_and_wrong_output(
        self,
    ) -> None:
        operation = ROUTE.operation_prefix + "launch2"
        config = {
            "task_root": str(Path("root") / ROUTE.work_unit),
            "first_operation_id": ROUTE.operation_prefix + "launch1",
            "second_operation_id": operation,
            "reviewer_principal": principal_value(),
        }
        session = {
            "operation_id": operation,
            "session_digest": "1" * 64,
        }
        arguments = Namespace(
            config=Path("config.json"),
            launch=1,
            session=Path("session.json"),
            packet=Path("packet.json"),
            check=[
                f"{name}=true"
                for name in sorted(
                    COORDINATOR.EVIDENCE.FIRST_LAUNCH_CHECKS
                )
            ],
            check_note=[
                f"{name}=observed"
                for name in sorted(
                    COORDINATOR.EVIDENCE.FIRST_LAUNCH_CHECKS
                )
            ],
            notes="",
            out=Path("wrong.json"),
        )
        with (
            patch.object(
                COORDINATOR,
                "validate_config",
                return_value=(config, object(), object()),
            ),
            patch.object(
                COORDINATOR.EVIDENCE,
                "validate_session_record",
                return_value=session,
            ),
            patch.object(
                COORDINATOR.EVIDENCE,
                "validate_native_packet",
                return_value={"packet_digest": "2" * 64},
            ),
            self.assertRaises(COORDINATOR.CoordinatorError),
        ):
            COORDINATOR.human(arguments, input_fn=lambda _: "")

    def test_synthetic_two_launch_protocol_derives_pass_fail_and_inconclusive(
        self,
    ) -> None:
        for expected_verdict, exceptional in (
            ("Pass", {}),
            ("Fail", {"normal_menu_observed": False}),
            ("Inconclusive", {"normal_menu_observed": None}),
        ):
            with self.subTest(expected_verdict), tempfile.TemporaryDirectory() as temporary:
                task_root = Path(temporary) / ROUTE.work_unit
                task_root.mkdir()
                principal = principal_value()
                probe = (
                    task_root
                    / "artifacts"
                    / "qualified-build"
                    / "facman_evidence_probe.exe"
                )
                probe.parent.mkdir(parents=True)
                probe.write_bytes(b"fake")
                operation_ids = [
                    ROUTE.operation_prefix + "synthetic-launch1",
                    ROUTE.operation_prefix + "synthetic-launch2",
                ]
                sessions: list[dict[str, object]] = []
                session_paths: list[Path] = []
                packet_paths: list[Path] = []
                packet_values: dict[Path, dict[str, object]] = {}
                human_paths: list[Path] = []
                for index, operation in enumerate(operation_ids):
                    session_core: dict[str, object] = {
                        "schema": (
                            COORDINATOR.EVIDENCE.INSTANCE_SESSION_SCHEMA
                        ),
                        "work_unit": ROUTE.work_unit,
                        "instance_id": ROUTE.instance_id,
                        "operation_id": operation,
                        "machine_binding_id": "machine",
                        "facman_source_revision_digest": "a" * 64,
                        "facman_build_identity_digest": "b" * 64,
                        "task_root": str(task_root),
                        "principal": {
                            "provider_id": principal["provider_id"],
                            "principal_id": principal["principal_digest"],
                            "application_session_id": (
                                str(index + 1) * 64
                            ),
                        },
                        "evidence_probe": str(probe),
                        "evidence_probe_sha256": "4" * 64,
                        "resource_set_digest": "7" * 64,
                        "startup_environment_snapshot_digest": "8" * 64,
                    }
                    session = {
                        **session_core,
                        "session_digest": digest_value(session_core),
                    }
                    session_path = (
                        task_root
                        / "evidence"
                        / "sessions"
                        / f"{operation}-session.json"
                    )
                    session_path.parent.mkdir(parents=True, exist_ok=True)
                    session_path.write_text(
                        json.dumps(session), encoding="utf-8"
                    )
                    packet_path = (
                        task_root
                        / "workspace"
                        / "operations"
                        / operation
                        / "synthetic-packet.json"
                    )
                    packet_path.parent.mkdir(parents=True, exist_ok=True)
                    packet_path.write_text("{}", encoding="utf-8")
                    packet = {
                        "packet_digest": str(index + 3) * 64,
                        "permit_id": f"synthetic-permit-{index + 1}",
                        "permit_claims_digest": str(index + 5) * 64,
                        "technical_disposition": (
                            "eligible_for_human_verdict"
                        ),
                        "synthetic_process_observer": True,
                    }
                    checks_expected = (
                        COORDINATOR.EVIDENCE.FIRST_LAUNCH_CHECKS
                        if index == 0
                        else COORDINATOR.EVIDENCE.SECOND_LAUNCH_CHECKS
                    )
                    checks = {
                        name: (
                            exceptional.get(name, True)
                            if index == 0
                            else True
                        )
                        for name in checks_expected
                    }
                    disposition = (
                        "Fail"
                        if any(value is False for value in checks.values())
                        else (
                            "Inconclusive"
                            if any(
                                value is None for value in checks.values()
                            )
                            else "Pass"
                        )
                    )
                    human_core: dict[str, object] = {
                        "schema": ROUTE.human_observation_schema,
                        "canonicalization_version": (
                            "facman.sorted-json.v1"
                        ),
                        "work_unit": ROUTE.work_unit,
                        "operation_id": operation,
                        "launch_sequence": index + 1,
                        "session_digest": session["session_digest"],
                        "packet_digest": packet["packet_digest"],
                        "reviewer_principal": principal,
                        "observed_at": "2026-07-27T00:00:00Z",
                        "disposition": disposition,
                        "checks": checks,
                        "check_notes": {
                            name: (
                                "synthetic adverse observation"
                                if value is not True
                                else "synthetic direct observation"
                            )
                            for name, value in checks.items()
                        },
                        "notes": "Synthetic; no Factorio was executed.",
                    }
                    human = {
                        **human_core,
                        "attestation_digest": digest_value(human_core),
                    }
                    human_path = (
                        task_root
                        / "evidence"
                        / "human"
                        / f"{operation}-launch-{index + 1}.json"
                    )
                    human_path.parent.mkdir(parents=True, exist_ok=True)
                    human_path.write_text(
                        json.dumps(human), encoding="utf-8"
                    )
                    sessions.append(session)
                    session_paths.append(session_path)
                    packet_paths.append(packet_path)
                    packet_values[packet_path] = packet
                    human_paths.append(human_path)

                def packet_for(
                    _session: dict[str, object],
                    path: Path,
                    _route: object,
                ) -> dict[str, object]:
                    return packet_values[path]

                verdict_path = (
                    task_root / "evidence" / "verdict" / "synthetic.json"
                )
                with patch.object(
                    COORDINATOR.EVIDENCE,
                    "validate_native_packet",
                    side_effect=packet_for,
                ), patch.object(
                    COORDINATOR.EVIDENCE,
                    "EvidenceIo",
                    FakeEvidenceIo,
                ):
                    result = COORDINATOR.finalize_auto(
                        Namespace(
                            first_session=session_paths[0],
                            first_packet=packet_paths[0],
                            first_human=human_paths[0],
                            second_session=session_paths[1],
                            second_packet=packet_paths[1],
                            second_human=human_paths[1],
                            out=verdict_path,
                        )
                    )
                self.assertEqual(result["verdict"], expected_verdict)
                self.assertFalse(result["grants_authority"])
                self.assertFalse(result["product_route_available"])

    def test_stage_reuses_only_an_exact_prequalified_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_root = root / ROUTE.work_unit
            workspace = task_root / "workspace"
            source_member = (
                task_root
                / "source"
                / "portable-package-inspection"
                / "factorio.exe"
            )
            workspace.mkdir(parents=True)
            source_member.parent.mkdir(parents=True)
            source_member.write_bytes(b"factorio")
            candidate_build = root / "build"
            candidate_build.mkdir()
            facman = candidate_build / "facman.exe"
            facman.write_bytes(b"facman")
            factorio = root / "factorio.exe"
            factorio.write_bytes(b"factorio")
            source_artifact = root / "factorio.zip"
            source_artifact.write_bytes(b"source")
            repositories = [root / name for name in ("repo", "launcher", "setup")]
            for repository in repositories:
                repository.mkdir()
            qualification_path = root / "qualification.json"
            qualification = qualification_value()
            qualification_path.write_text(
                json.dumps(qualification), encoding="utf-8"
            )

            def copy_artifacts(
                _source: Path,
                destination: Path,
                _qualification: object,
                _evidence_io: object,
            ):
                destination.mkdir(parents=True)
                paths = {}
                records = []
                for logical_name, name in (
                    ("facman", "facman.exe"),
                    (
                        "candidate_smoke",
                        "facman_hermetic_play_candidate_smoke.exe",
                    ),
                    (
                        "verdict_harness",
                        "facman_gate4c_verdict_harness.exe",
                    ),
                    (
                        "evidence_probe",
                        "facman_evidence_probe.exe",
                    ),
                    ("cmake_cache", "CMakeCache.txt"),
                ):
                    path = destination / name
                    path.write_bytes(logical_name.encode("utf-8"))
                    paths[logical_name] = path
                    records.append(
                        {
                            "name": name,
                            "bytes": path.stat().st_size,
                            "sha256": PREFLIGHT.sha256_file(path),
                            "logical_name": logical_name,
                        }
                    )
                return records, paths

            with (
                patch.object(
                    PREFLIGHT,
                    "windows_principal_identity",
                    return_value=principal_value(),
                ),
                patch.object(
                    COORDINATOR,
                    "_qualified_source_paths",
                    return_value={"facman": facman},
                ),
                patch.object(COORDINATOR, "_exact_repository_inputs"),
                patch.object(
                    COORDINATOR,
                    "_validate_staged_candidate",
                    return_value=instance_projection_value(
                        qualification, workspace
                    ),
                ) as validate,
                patch.object(
                    COORDINATOR,
                    "_copy_qualified_artifacts",
                    side_effect=copy_artifacts,
                ),
                patch.object(
                    COORDINATOR, "EvidenceIo", FakeEvidenceIo
                ),
                patch.object(
                    COORDINATOR,
                    "_extract_authenticated_executable",
                ) as extract,
                patch.object(COORDINATOR, "_stage_workspace") as create_workspace,
            ):
                result = COORDINATOR.stage(
                    Namespace(
                        task_root=task_root,
                        candidate_build=candidate_build,
                        configuration="Debug",
                        qualification_binding=qualification_path,
                        repository_root=repositories[0],
                        launcher_repository=repositories[1],
                        setup_repository=repositories[2],
                        factorio_executable=factorio,
                        source_artifact=source_artifact,
                        first_operation_id=ROUTE.operation_prefix + "launch1",
                        second_operation_id=ROUTE.operation_prefix + "launch2",
                    )
                )

            validate.assert_called_once()
            extract.assert_not_called()
            create_workspace.assert_not_called()
            self.assertEqual(result["workspace"], str(workspace))
            self.assertTrue(Path(result["config"]).is_file())
            staged_path = Path(result["staged_candidate_binding"])
            self.assertTrue(staged_path.is_file())
            staged = json.loads(staged_path.read_text(encoding="utf-8"))
            self.assertEqual(
                staged["instance"]["binding_digest"], "e" * 64
            )
            self.assertEqual(
                result["staged_candidate_digest"],
                staged["staged_candidate_digest"],
            )


if __name__ == "__main__":
    unittest.main()
