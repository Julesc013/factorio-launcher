# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from argparse import Namespace
from unittest import mock

from tools.play_verdict_route import (
    INSTANCE_ISOLATED_REVALIDATION as INSTANCE_ROUTE,
)
from tools.play_evidence_resource_spec import baseline_specs

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gate4c_verdict_evidence",
    ROOT / "tools/gate4c_verdict_evidence.py",
)
assert SPEC and SPEC.loader
EVIDENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVIDENCE)
SESSION_SPEC = importlib.util.spec_from_file_location(
    "gate4c_verdict_session",
    ROOT / "tools/gate4c_verdict_session.py",
)
assert SESSION_SPEC and SESSION_SPEC.loader
SESSION = importlib.util.module_from_spec(SESSION_SPEC)
SESSION_SPEC.loader.exec_module(SESSION)


class Gate4CVerdictEvidenceTests(unittest.TestCase):
    def observer_probe_patches(self) -> list[mock._patch]:
        tools = {
            "wpr": r"C:\ObserverTools\wpr.exe",
            "xperf": r"C:\ObserverTools\xperf.exe",
            "wpaexporter": r"C:\ObserverTools\wpaexporter.exe",
        }
        windows_os = mock.Mock(wraps=SESSION.os)
        windows_os.name = "nt"
        return [
            mock.patch.object(SESSION, "os", windows_os),
            mock.patch.object(SESSION.PREFLIGHT, "is_elevated", return_value=True),
            mock.patch.object(
                SESSION.PREFLIGHT,
                "observer_tool_paths",
                return_value=tools,
            ),
            mock.patch.object(
                SESSION.PREFLIGHT,
                "observer_toolchain_coherent",
                return_value=True,
            ),
            mock.patch.object(
                SESSION.PREFLIGHT,
                "observer_profile_identity",
                return_value={"valid": True, "identity": "profile"},
            ),
            mock.patch.object(
                SESSION.PREFLIGHT,
                "repository_tool_identity",
                return_value={"valid": True, "revision": "fixture"},
            ),
            mock.patch.object(
                SESSION.PREFLIGHT,
                "host_session_identity",
                return_value={"valid": True, "machine_binding_id": "fixture"},
            ),
            mock.patch.object(
                SESSION.PREFLIGHT,
                "executable_tool_identity",
                return_value={"valid": True, "identity": "tool"},
            ),
        ]

    def test_observer_provider_identity_propagates_profile_validity(self) -> None:
        with mock.patch.object(
            SESSION.PREFLIGHT,
            "observer_profile_identity",
            return_value={"valid": True},
        ):
            valid = SESSION.PREFLIGHT.observer_provider_identity(ROOT)
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["reason"], "valid")
        self.assertEqual(
            valid["revision"],
            SESSION.PREFLIGHT.OBSERVER_PROVIDER_REVISION,
        )

        with mock.patch.object(
            SESSION.PREFLIGHT,
            "observer_profile_identity",
            return_value={"valid": False},
        ):
            invalid = SESSION.PREFLIGHT.observer_provider_identity(ROOT)
        self.assertFalse(invalid["valid"])
        self.assertEqual(invalid["reason"], "observer_profile_invalid")

    def test_observer_probe_patches_do_not_mutate_process_platform(self) -> None:
        process_platform = os.name
        with contextlib.ExitStack() as stack:
            for patch in self.observer_probe_patches():
                stack.enter_context(patch)
            self.assertEqual(os.name, process_platform)

    def test_observer_start_probe_preserves_exact_pass_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_root = (
                Path(temporary) / SESSION.OBSERVER_START_REPAIR_WORK_UNIT
            )
            task_root.mkdir()
            probe_id = "gate4c-observer-start-probe-pass"
            output = (
                task_root
                / "evidence"
                / "observer-start-probes"
                / f"{probe_id}.json"
            )

            def command(
                arguments: list[str],
                *,
                timeout: int = 180,
            ) -> subprocess.CompletedProcess[str]:
                del timeout
                if "-stop" in arguments:
                    Path(arguments[2]).write_bytes(b"trace")
                    return subprocess.CompletedProcess(
                        arguments, 0, "stopped", ""
                    )
                if arguments[-1] == "-status":
                    status_calls = getattr(command, "status_calls", 0)
                    command.status_calls = status_calls + 1
                    text = (
                        "WPR is not recording"
                        if status_calls in {0, 2}
                        else "WPR is recording"
                    )
                    return subprocess.CompletedProcess(arguments, 0, text, "")
                return subprocess.CompletedProcess(arguments, 0, "started", "")

            patches = self.observer_probe_patches()
            with contextlib.ExitStack() as stack:
                for patch in patches:
                    stack.enter_context(patch)
                stack.enter_context(
                    mock.patch.object(
                        SESSION.SELFTEST,
                        "command",
                        side_effect=command,
                    )
                )
                result = SESSION.observer_start_probe(
                    argparse.Namespace(
                        task_root=task_root,
                        probe_id=probe_id,
                        out=output,
                    )
                )
            self.assertEqual(result["status"], "pass")
            self.assertFalse(result["recording_active_after_probe"])
            self.assertEqual(len(result["commands"]), 5)
            self.assertTrue(output.is_file())
            self.assertEqual(
                result["trace"]["sha256"],
                SESSION.PREFLIGHT.sha256_file(Path(result["trace"]["path"])),
            )

    def test_observer_start_probe_persists_start_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_root = (
                Path(temporary) / SESSION.OBSERVER_START_REPAIR_WORK_UNIT
            )
            task_root.mkdir()
            probe_id = "gate4c-observer-start-probe-failure"
            output = (
                task_root
                / "evidence"
                / "observer-start-probes"
                / f"{probe_id}.json"
            )
            calls = 0

            def command(
                arguments: list[str],
                *,
                timeout: int = 180,
            ) -> subprocess.CompletedProcess[str]:
                nonlocal calls
                del timeout
                calls += 1
                if calls == 1:
                    return subprocess.CompletedProcess(
                        arguments, 0, "WPR is not recording", ""
                    )
                return subprocess.CompletedProcess(
                    arguments, 9, "", "exact WPR start failure"
                )

            patches = self.observer_probe_patches()
            with contextlib.ExitStack() as stack:
                for patch in patches:
                    stack.enter_context(patch)
                stack.enter_context(
                    mock.patch.object(
                        SESSION.SELFTEST,
                        "command",
                        side_effect=command,
                    )
                )
                result = SESSION.observer_start_probe(
                    argparse.Namespace(
                        task_root=task_root,
                        probe_id=probe_id,
                        out=output,
                    )
                )
            self.assertEqual(result["status"], "inconclusive")
            self.assertIn("wpr_start_failed", result["errors"])
            self.assertEqual(
                result["commands"][1]["stderr"],
                "exact WPR start failure",
            )
            self.assertTrue(output.is_file())

    def test_stable_manifest_detects_file_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "protected"
            root.mkdir()
            target = root / "one.txt"
            target.write_text("one", encoding="utf-8")
            before = EVIDENCE.capture_filesystem_resource(
                "installation.selected", [root]
            )
            target.write_text("replacement", encoding="utf-8")
            after = EVIDENCE.capture_filesystem_resource(
                "installation.selected", [root]
            )
            self.assertTrue(before["complete"])
            self.assertTrue(after["complete"])
            self.assertNotEqual(
                before["resource_digest"], after["resource_digest"]
            )

    def test_absent_member_is_complete_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "absent"
            first = EVIDENCE.capture_filesystem_resource(
                "installation.siblings", [missing]
            )
            second = EVIDENCE.capture_filesystem_resource(
                "installation.siblings", [missing]
            )
            self.assertTrue(first["complete"])
            self.assertEqual(first["resource_digest"], second["resource_digest"])
            self.assertEqual(
                first["members"][0]["manifest_digest"],
                second["members"][0]["manifest_digest"],
            )

    def test_conceptual_resources_complete_exact_protected_scope(self) -> None:
        conceptual = {
            "effects.external_filesystem": "event-only:filesystem",
            "effects.external_registry": "event-only:registry",
            "host.external_unobserved": "disclosed:outside-process-tree-claim",
        }
        resources = EVIDENCE.capture_resources(
            {"filesystem": {}, "registry": {}, "conceptual": conceptual}
        )
        self.assertEqual(
            {item["resource_id"] for item in resources}, set(conceptual)
        )
        self.assertTrue(all(item["complete"] for item in resources))

    def test_resource_set_digest_is_order_independent(self) -> None:
        resources = [
            {
                "resource_id": "b",
                "resource_digest": EVIDENCE.sha256_text("b"),
                "complete": True,
            },
            {
                "resource_id": "a",
                "resource_digest": EVIDENCE.sha256_text("a"),
                "complete": True,
            },
        ]
        self.assertEqual(
            EVIDENCE.resource_set_digest(resources),
            EVIDENCE.resource_set_digest(list(reversed(resources))),
        )

    def test_baseline_consumes_preflight_paths_without_environment_rediscovery(
        self,
    ) -> None:
        specification = {
            "protected_resources": [
                {
                    "resource_id": "factorio.appdata",
                    "kind": "filesystem",
                    "source": "startup_environment_snapshot",
                    "members": [
                        {
                            "path": r"C:\Observed\AppData\Factorio",
                            "root_identity": {"present": False},
                        }
                    ],
                },
                {
                    "resource_id": "registry.factorio_uninstall",
                    "kind": "registry",
                    "source": "preflight_registry_discovery",
                    "members": [
                        {"hive": "HKCU", "subkey": r"Software\Uninstall"}
                    ],
                },
            ],
            "writable_resources": [
                {
                    "resource_id": "instance.closure",
                    "kind": "filesystem",
                    "source": "frozen_route_writable_mapping",
                    "members": [
                        {
                            "path": r"D:\Task\workspace\instances\selected",
                            "root_identity": {"present": True},
                        }
                    ],
                }
            ],
        }
        with mock.patch.dict(
            os.environ,
            {
                "APPDATA": r"Z:\Substituted\AppData",
                "LOCALAPPDATA": r"Z:\Substituted\Local",
            },
            clear=False,
        ):
            protected, writable = baseline_specs(specification)
        self.assertEqual(
            protected["filesystem"]["factorio.appdata"],
            [r"C:\Observed\AppData\Factorio"],
        )
        self.assertEqual(
            writable["instance.closure"],
            [r"D:\Task\workspace\instances\selected"],
        )

    def test_new_output_is_exact_task_owned_and_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_root = Path(temporary) / EVIDENCE.WORK_UNIT
            task_root.mkdir()
            sessions = task_root / "evidence" / "sessions"
            output = sessions / "one.json"
            self.assertEqual(
                EVIDENCE.prepare_new_output(
                    output,
                    root=task_root,
                    expected_parent=sessions,
                ),
                output,
            )
            output.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.prepare_new_output(
                    output,
                    root=task_root,
                    expected_parent=sessions,
                )
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.prepare_new_output(
                    Path(temporary) / "outside.json",
                    root=task_root,
                    expected_parent=sessions,
                )

    def test_human_pass_requires_every_exact_first_launch_invariant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "human.json"
            core = {
                "schema": EVIDENCE.HUMAN_OBSERVATION_SCHEMA,
                "canonicalization_version": "facman.sorted-json.v1",
                "work_unit": EVIDENCE.WORK_UNIT,
                "operation_id": "gate4c-first",
                "session_digest": "1" * 64,
                "packet_digest": "2" * 64,
                "reviewer_id": "windows:Jules",
                "observed_at": "2026-07-24T00:00:00Z",
                "disposition": "Pass",
                "checks": {
                    key: True for key in EVIDENCE.FIRST_LAUNCH_CHECKS
                },
                "notes": "Observed directly.",
            }
            core["attestation_digest"] = EVIDENCE.digest_value(core)
            EVIDENCE.atomic_json(path, core)
            validated = EVIDENCE.validate_human_observation(
                path,
                operation_id="gate4c-first",
                session_digest="1" * 64,
                packet_digest="2" * 64,
                expected_checks=EVIDENCE.FIRST_LAUNCH_CHECKS,
            )
            self.assertEqual(validated["disposition"], "Pass")
            core["checks"]["normal_menu_observed"] = False
            unsigned = dict(core)
            unsigned.pop("attestation_digest")
            core["attestation_digest"] = EVIDENCE.digest_value(unsigned)
            EVIDENCE.atomic_json(path, core)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.validate_human_observation(
                    path,
                    operation_id="gate4c-first",
                    session_digest="1" * 64,
                    packet_digest="2" * 64,
                    expected_checks=EVIDENCE.FIRST_LAUNCH_CHECKS,
                )

    def test_instance_human_observation_is_operation_sequence_and_principal_bound(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_root = Path(temporary) / INSTANCE_ROUTE.work_unit
            operation = INSTANCE_ROUTE.operation_prefix + "launch1"
            path = (
                task_root
                / "evidence"
                / "human"
                / f"{operation}-launch-1.json"
            )
            principal_core = {
                "schema": EVIDENCE.PREFLIGHT.WINDOWS_PRINCIPAL_SCHEMA,
                "provider_id": "windows.local-token.v1",
                "principal_sid_digest": "9" * 64,
                "windows_session_id": 7,
                "integrity": "medium",
                "valid": True,
            }
            principal = {
                **principal_core,
                "principal_digest": EVIDENCE.digest_value(principal_core),
            }
            core = {
                "schema": INSTANCE_ROUTE.human_observation_schema,
                "canonicalization_version": "facman.sorted-json.v1",
                "work_unit": INSTANCE_ROUTE.work_unit,
                "operation_id": operation,
                "launch_sequence": 1,
                "session_digest": "1" * 64,
                "packet_digest": "2" * 64,
                "reviewer_principal": principal,
                "observed_at": "2026-07-27T00:00:00Z",
                "disposition": "Pass",
                "checks": {
                    key: True for key in EVIDENCE.FIRST_LAUNCH_CHECKS
                },
                "check_notes": {
                    key: "observed" for key in EVIDENCE.FIRST_LAUNCH_CHECKS
                },
                "notes": "Synthetic protocol proof.",
            }
            value = {
                **core,
                "attestation_digest": EVIDENCE.digest_value(core),
            }
            EVIDENCE.atomic_json(path, value)
            validated = EVIDENCE.validate_human_observation(
                path,
                operation_id=operation,
                session_digest="1" * 64,
                packet_digest="2" * 64,
                expected_checks=EVIDENCE.FIRST_LAUNCH_CHECKS,
                route=INSTANCE_ROUTE,
                launch_sequence=1,
                task_root=task_root,
            )
            self.assertEqual(validated["disposition"], "Pass")

            value["checks"]["normal_menu_observed"] = False
            value["check_notes"]["normal_menu_observed"] = ""
            unsigned = dict(value)
            unsigned.pop("attestation_digest")
            value["attestation_digest"] = EVIDENCE.digest_value(unsigned)
            EVIDENCE.atomic_json(path, value)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.validate_human_observation(
                    path,
                    operation_id=operation,
                    session_digest="1" * 64,
                    packet_digest="2" * 64,
                    expected_checks=EVIDENCE.FIRST_LAUNCH_CHECKS,
                    route=INSTANCE_ROUTE,
                    launch_sequence=1,
                    task_root=task_root,
                )

            value["check_notes"]["normal_menu_observed"] = "menu absent"
            value["disposition"] = "Fail"
            value["reviewer_principal"] = {
                **principal,
                "windows_session_id": 8,
            }
            unsigned = dict(value)
            unsigned.pop("attestation_digest")
            value["attestation_digest"] = EVIDENCE.digest_value(unsigned)
            EVIDENCE.atomic_json(path, value)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.validate_human_observation(
                    path,
                    operation_id=operation,
                    session_digest="1" * 64,
                    packet_digest="2" * 64,
                    expected_checks=EVIDENCE.FIRST_LAUNCH_CHECKS,
                    route=INSTANCE_ROUTE,
                    launch_sequence=1,
                    task_root=task_root,
                )

    def test_instance_finalizer_rejects_same_operation_and_changed_principal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_root = Path(temporary) / INSTANCE_ROUTE.work_unit
            task_root.mkdir()
            principal_core = {
                "schema": EVIDENCE.PREFLIGHT.WINDOWS_PRINCIPAL_SCHEMA,
                "provider_id": "windows.local-token.v1",
                "principal_sid_digest": "9" * 64,
                "windows_session_id": 7,
                "integrity": "medium",
                "valid": True,
            }
            principal = {
                **principal_core,
                "principal_digest": EVIDENCE.digest_value(principal_core),
            }
            session = {
                "instance_id": INSTANCE_ROUTE.instance_id,
                "operation_id": INSTANCE_ROUTE.operation_prefix + "same",
                "machine_binding_id": "machine",
                "facman_source_revision_digest": "1" * 64,
                "facman_build_identity_digest": "2" * 64,
                "task_root": str(task_root),
                "session_digest": "a" * 64,
                "principal": {
                    "provider_id": principal["provider_id"],
                    "principal_id": principal["principal_digest"],
                },
            }
            arguments = Namespace(
                first_session=Path("first-session.json"),
                first_packet=Path("first-packet.json"),
                first_human=Path("first-human.json"),
                second_session=Path("second-session.json"),
                second_packet=Path("second-packet.json"),
                second_human=Path("second-human.json"),
                verdict="Pass",
                out=task_root / "evidence" / "verdict" / "verdict.json",
            )
            with (
                mock.patch.object(
                    EVIDENCE,
                    "validate_session_record",
                    side_effect=[session, dict(session)],
                ),
                self.assertRaises(EVIDENCE.EvidenceError),
            ):
                EVIDENCE.finalize_verdict(
                    arguments, route=INSTANCE_ROUTE
                )

            second_session = {
                **session,
                "operation_id": INSTANCE_ROUTE.operation_prefix + "second",
                "session_digest": "b" * 64,
            }
            second_principal_core = {
                **principal_core,
                "principal_sid_digest": "8" * 64,
            }
            second_principal = {
                **second_principal_core,
                "principal_digest": EVIDENCE.digest_value(
                    second_principal_core
                ),
            }
            second_session["principal"] = {
                "provider_id": second_principal["provider_id"],
                "principal_id": second_principal["principal_digest"],
            }
            packets = [
                {
                    "packet_digest": "3" * 64,
                    "permit_id": "permit-one",
                    "permit_claims_digest": "4" * 64,
                    "technical_disposition": (
                        "eligible_for_human_verdict"
                    ),
                },
                {
                    "packet_digest": "5" * 64,
                    "permit_id": "permit-two",
                    "permit_claims_digest": "6" * 64,
                    "technical_disposition": (
                        "eligible_for_human_verdict"
                    ),
                },
            ]
            humans = [
                {
                    "reviewer_principal": principal,
                    "disposition": "Pass",
                    "attestation_digest": "7" * 64,
                },
                {
                    "reviewer_principal": second_principal,
                    "disposition": "Pass",
                    "attestation_digest": "8" * 64,
                },
            ]
            with (
                mock.patch.object(
                    EVIDENCE,
                    "validate_session_record",
                    side_effect=[session, second_session],
                ),
                mock.patch.object(
                    EVIDENCE,
                    "validate_native_packet",
                    side_effect=packets,
                ),
                mock.patch.object(
                    EVIDENCE,
                    "validate_human_observation",
                    side_effect=humans,
                ),
                self.assertRaises(EVIDENCE.EvidenceError),
            ):
                EVIDENCE.finalize_verdict(
                    arguments, route=INSTANCE_ROUTE
                )


if __name__ == "__main__":
    unittest.main()
