# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gate4c_verdict_session",
    ROOT / "tools/gate4c_verdict_session.py",
)
assert SPEC and SPEC.loader
SESSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SESSION)


ROOTS = {
    "schema": SESSION.CLASSIFICATION_SCHEMA,
    "writable_filesystem": [
        {"resource_id": "instance.saves", "path": r"E:\Gate4C\instance\saves"},
        {"resource_id": "operation.temporary", "path": r"E:\Gate4C\temporary\op"},
    ],
    "protected_filesystem": [
        {"resource_id": "installation.selected", "path": r"D:\Games\Factorio\2.0"},
    ],
}


def dump(*events: str) -> str:
    header = """BeginHeader
P-Start,TimeStamp,Process Name ( PID),ParentPID,SessionID,UniqueKey,DirectoryTableBase,Flags,UserSid,Command Line,Package Full Name,Package Relative Application Id
P-End,TimeStamp,Process Name ( PID),ParentPID,SessionID,UniqueKey,Status,DirectoryTableBase,Flags,UserSid,Command Line,Package Full Name,Package Relative Application Id
FileIoWrite,TimeStamp,Process Name ( PID),ThreadID,LoggingProcessName ( PID),LoggingThreadID,CPU,IrpPtr,FileObject,ByteOffset,Size,Flags,ExtraFlags,Priority,FileName,ParsedFlags
FileIoCreate,TimeStamp,Process Name ( PID),ThreadID,LoggingProcessName ( PID),LoggingThreadID,CPU,IrpPtr,FileObject,Options,Attributes,ShareAccess,FileName,ParsedOptions,ParsedAttributes,ParsedShareAccess
FileIoOpEnd,TimeStamp,Process Name ( PID),ThreadID,LoggingProcessName ( PID),LoggingThreadID,CPU,IrpPtr,FileObject,ElapsedTime,Status,ExtraInfo,Type,FileName
FileIoSetInfo,TimeStamp,Process Name ( PID),ThreadID,LoggingProcessName ( PID),LoggingThreadID,CPU,IrpPtr,FileObject,ExtraInfo,InfoClass,FileName
FileIoClose,TimeStamp,Process Name ( PID),ThreadID,LoggingProcessName ( PID),LoggingThreadID,CPU,IrpPtr,FileObject,FileName
FileNameCreate,TimeStamp,FileObject,FileName,NT FileName
FileNameDelete,TimeStamp,FileObject,FileName,NT FileName
FileNameRundown,TimeStamp,FileObject,FileName,NT FileName
RegKcbCreate,TimeStamp,KCB,Key Name
RegKcbDelete,TimeStamp,KCB,Key Name
RegKcbEndRundown,TimeStamp,KCB,Key Name
RegOpenKey,TimeStamp,KCB,Process Name ( PID),ThreadID,Status,ElapsedTime,Key Name
RegQueryKey,TimeStamp,KCB,Process Name ( PID),ThreadID,Status,ElapsedTime,InfoClass
RegSetValue,TimeStamp,KCB,Process Name ( PID),ThreadID,Status,ElapsedTime,Key Name
RegSetInformation,TimeStamp,KCB,Process Name ( PID),ThreadID,Status,ElapsedTime
VolumeMapping,TimeStamp,NtPath,DosPath
EndHeader
"""
    return header + "\n".join(events) + "\n"


class Gate4CVerdictSessionTests(unittest.TestCase):
    def capture_fixture(self, root: Path) -> tuple[Path, Path, dict[str, object]]:
        task_root = root / SESSION.PREFLIGHT.WORK_UNIT
        operation_root = (
            task_root / "workspace" / "temporary" / "gate4c-broker-test"
        )
        observation_root = operation_root / "process" / "observation"
        observation_root.mkdir(parents=True)
        token_path = observation_root / "capture-token.json"
        core: dict[str, object] = {
            "schema": SESSION.CAPTURE_SCHEMA,
            "operation_root": str(operation_root),
            "active": True,
        }
        token = dict(core)
        token["capture_session_digest"] = SESSION.digest_value(core)
        token_path.write_text(json.dumps(token), encoding="utf-8")
        return task_root, operation_root, token

    def capture_patches(
        self, task_root: Path, operation_root: Path
    ) -> list[mock._patch]:
        windows_os = mock.Mock(wraps=SESSION.os)
        windows_os.name = "nt"
        return [
            mock.patch.object(SESSION, "os", windows_os),
            mock.patch.object(SESSION.PREFLIGHT, "is_elevated", return_value=True),
            mock.patch.object(
                SESSION, "exact_task_root", return_value=task_root
            ),
            mock.patch.object(
                SESSION, "exact_operation_root", return_value=operation_root
            ),
            mock.patch.object(
                SESSION.PREFLIGHT,
                "audit_no_follow",
                return_value={"safe": True},
            ),
            mock.patch.object(
                SESSION.PREFLIGHT,
                "observer_tool_paths",
                return_value={"wpr": Path(r"C:\Tools\wpr.exe")},
            ),
            mock.patch.object(
                SESSION.PREFLIGHT,
                "observer_toolchain_coherent",
                return_value=True,
            ),
        ]

    def test_broker_status_revalidates_bound_active_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_root, operation_root, token = self.capture_fixture(
                Path(temporary)
            )
            token_path = (
                operation_root / "process" / "observation" / "capture-token.json"
            )
            status_result = subprocess.CompletedProcess(
                ["wpr", "-status"], 0, "WPR is recording", ""
            )
            with contextlib.ExitStack() as stack:
                for patch in self.capture_patches(task_root, operation_root):
                    stack.enter_context(patch)
                stack.enter_context(
                    mock.patch.object(
                        SESSION.SELFTEST, "command", return_value=status_result
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        SESSION.SELFTEST,
                        "wpr_is_not_recording",
                        return_value=False,
                    )
                )
                result = SESSION.status_capture(
                    argparse.Namespace(
                        task_root=task_root,
                        operation_root=operation_root,
                        capture_token=token_path,
                        capture_session_digest=token["capture_session_digest"],
                    )
                )
            self.assertTrue(result["active"])
            self.assertEqual(
                result["capture_session_digest"],
                token["capture_session_digest"],
            )

    def test_broker_abort_cancels_and_records_exact_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_root, operation_root, token = self.capture_fixture(
                Path(temporary)
            )
            token_path = (
                operation_root / "process" / "observation" / "capture-token.json"
            )
            results = [
                subprocess.CompletedProcess(
                    ["wpr", "-status"], 0, "WPR is recording", ""
                ),
                subprocess.CompletedProcess(["wpr", "-cancel"], 0, "", ""),
                subprocess.CompletedProcess(
                    ["wpr", "-status"], 0, "WPR is not recording", ""
                ),
            ]
            with contextlib.ExitStack() as stack:
                for patch in self.capture_patches(task_root, operation_root):
                    stack.enter_context(patch)
                stack.enter_context(
                    mock.patch.object(
                        SESSION.SELFTEST, "command", side_effect=results
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        SESSION.SELFTEST,
                        "wpr_is_not_recording",
                        side_effect=(False, True),
                    )
                )
                result = SESSION.abort_capture(
                    argparse.Namespace(
                        task_root=task_root,
                        operation_root=operation_root,
                        capture_token=token_path,
                        capture_session_digest=token["capture_session_digest"],
                        reason="launch_refused",
                    )
                )
            self.assertTrue(result["recording_stopped"])
            self.assertTrue(
                (
                    operation_root
                    / "observer-artifacts"
                    / "observer-abort.json"
                ).is_file()
            )

    def test_observation_digest_matches_reviewed_cpp_field_order(self) -> None:
        observation = {
            "schema": SESSION.OBSERVATION_SCHEMA,
            "provider_id": "factorio.play.process-tree-observer",
            "provider_revision": SESSION.BOUND_PROVIDER_REVISION,
            "plan_digest": "1" * 64,
            "capture_session_digest": "2" * 64,
            "raw_artifact_digest": "3" * 64,
            "active_before_process": True,
            "capture_complete": True,
            "gaps": {
                "lost_events": False,
                "buffer_overflow": False,
                "unknown_process_identity": False,
                "unresolved_target": False,
                "delayed_events": False,
                "attribution_gap": False,
                "provider_failure": False,
            },
            "effects": [
                {
                    "sequence": 0,
                    "domain": "process",
                    "process_identity_digest": "4" * 64,
                    "target_identity_digest": "5" * 64,
                    "logical_resource_id": "process.primary",
                    "classification": "writable",
                }
            ],
        }
        self.assertEqual(
            SESSION.observation_output_digest(observation),
            "2e992514c6a4efd0d20e23e8d258a5b236694e6096c2296852b9b63a180beca3",
        )

    def test_path_classification_is_exact_and_case_insensitive(self) -> None:
        self.assertEqual(
            SESSION.classify_filesystem_target(
                r"E:\Gate4C\instance\saves\gate4c-test.zip", ROOTS
            ),
            ("instance.saves", "writable"),
        )
        self.assertEqual(
            SESSION.classify_filesystem_target(
                r"d:\games\factorio\2.0\data\base\info.json", ROOTS
            ),
            ("installation.selected", "protected"),
        )
        self.assertEqual(
            SESSION.classify_filesystem_target(
                r"E:\Gate4C\instance-sibling\saves\wrong.zip", ROOTS
            ),
            ("effects.external_filesystem", "forbidden"),
        )

    def test_process_tree_effects_bind_primary_child_and_writable_file(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe --config x",,',
            'P-Start,2,"helper.exe (101)",100,1,0,0,0,S-1,"helper.exe",,',
            r'FileIoWrite,3,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0,0,4,0,0,0,E:\Gate4C\instance\saves\gate4c.zip,0',
            r'FileIoWrite,4,"helper.exe (101)",8,"helper.exe (101)",8,0,0,0,0,4,0,0,0,E:\Gate4C\temporary\op\child.log,0',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertEqual(
            gaps,
            {
                "unknown_process_identity": False,
                "unresolved_target": False,
                "attribution_gap": False,
            },
        )
        self.assertEqual(effects[0]["logical_resource_id"], "process.primary")
        self.assertEqual(effects[1]["logical_resource_id"], "instance.saves")
        self.assertEqual(effects[1]["classification"], "writable")
        self.assertEqual(effects[2]["logical_resource_id"], "operation.temporary")

    def test_protected_and_external_file_writes_are_not_weakened(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoSetInfo,3,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0,0,5,D:\Games\Factorio\2.0\data\base\info.json',
            r'FileIoWrite,4,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0,0,4,0,0,0,C:\Windows\Temp\escape.tmp,0',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(effects[1]["logical_resource_id"], "installation.selected")
        self.assertEqual(effects[1]["classification"], "protected")
        self.assertEqual(
            effects[2]["logical_resource_id"], "effects.external_filesystem"
        )
        self.assertEqual(effects[2]["classification"], "forbidden")

    def test_registry_mutation_uses_kcb_and_is_always_forbidden(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r"RegKcbCreate,2,0xffff,\REGISTRY\USER\S-1\Software\Wube Software\Factorio",
            'RegSetValue,3,0xffff,"factorio.exe (100)",7,0,1,Setting',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(effects[1]["domain"], "registry")
        self.assertEqual(effects[1]["logical_resource_id"], "effects.external_registry")
        self.assertEqual(effects[1]["classification"], "forbidden")

    def test_failed_registry_mutation_is_not_a_persistent_effect(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r"RegKcbCreate,2,0xffff,\REGISTRY\USER\S-1\Software\Wube Software\Factorio",
            'RegSetValue,3,0xffff,"factorio.exe (100)",7,0xC0000022,1,Setting',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(len(effects), 1)

    def test_unknown_file_name_resolves_from_temporal_file_object(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoCreate,2,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0x1,0xabc,0x03000060,0,0,E:\Gate4C\instance\saves\gate4c.zip,,,',
            r'FileIoOpEnd,3,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0x1,0xabc,1,0x00000000,3,FileIoCreate,E:\Gate4C\instance\saves\gate4c.zip',
            r'FileIoWrite,4,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0xabc,0,4,0,0,0,"Unknown (0x123)",0',
            r'FileIoClose,5,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0xabc,"Unknown (0x123)"',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(
            [effect["logical_resource_id"] for effect in effects[1:]],
            ["instance.saves", "instance.saves"],
        )
        self.assertTrue(
            all(effect["classification"] == "writable" for effect in effects[1:])
        )

    def test_preexisting_file_object_resolves_from_future_rundown(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoWrite,2,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0xabc,0,4,0,0,0,"Unknown (0x123)",0',
            r"FileNameRundown,3,0xabc,\Device\HarddiskVolume9\Gate4C\instance\saves\gate4c.zip,\Device\HarddiskVolume9\Gate4C\instance\saves\gate4c.zip",
            r"VolumeMapping,0,\Device\HarddiskVolume9,E:",
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(effects[1]["logical_resource_id"], "instance.saves")

    def test_file_object_reuse_boundary_refuses_stale_rundown(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoWrite,2,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0xabc,0,4,0,0,0,"Unknown (0x123)",0',
            r'FileIoClose,3,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0xabc,"Unknown (0x123)"',
            r"FileNameRundown,4,0xabc,E:\Gate4C\instance\saves\other.zip,E:\Gate4C\instance\saves\other.zip",
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertTrue(gaps["unresolved_target"])
        self.assertEqual(effects[1]["classification"], "unresolved")

    def test_registry_kcb_reuse_is_resolved_at_event_time(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r"RegKcbCreate,2,0xffff,\REGISTRY\USER\S-1\Software\First",
            'RegSetValue,3,0xffff,"factorio.exe (100)",7,0,1,Setting',
            r"RegKcbDelete,4,0xffff,\REGISTRY\USER\S-1\Software\First",
            r"RegKcbCreate,5,0xffff,\REGISTRY\USER\S-1\Software\Second",
            'RegSetValue,6,0xffff,"factorio.exe (100)",7,0,1,Setting',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertNotEqual(
            effects[1]["target_identity_digest"],
            effects[2]["target_identity_digest"],
        )

    def test_registry_rundown_resolves_preexisting_kcb(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            'RegSetValue,2,0xffff,"factorio.exe (100)",7,0,1,Setting',
            r"RegKcbEndRundown,3,0xffff,\REGISTRY\MACHINE\Software\Preexisting",
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(effects[1]["classification"], "forbidden")

    def test_immediate_same_thread_open_handoff_resolves_result_kcb(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r"RegKcbCreate,2,0xbase,\REGISTRY\MACHINE",
            r'RegOpenKey,3,0xbase,"factorio.exe (100)",7,0x00000000,1,SYSTEM\CurrentControlSet\Control\Cryptography\ECCParameters',
            r'RegSetInformation,4,0xresult,"factorio.exe (100)",7,0x00000000,1',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(effects[1]["classification"], "forbidden")

    def test_open_handoff_requires_success_same_thread_and_immediacy(self) -> None:
        cases = {
            "wrong_thread": (
                r'RegOpenKey,3,0xbase,"factorio.exe (100)",7,0x00000000,1,Software\Exact',
                r'RegSetInformation,4,0xresult,"factorio.exe (100)",8,0x00000000,1',
            ),
            "failed_open": (
                r'RegOpenKey,3,0xbase,"factorio.exe (100)",7,0xC0000022,1,Software\Exact',
                r'RegSetInformation,4,0xresult,"factorio.exe (100)",7,0x00000000,1',
            ),
            "intervening_operation": (
                r'RegOpenKey,3,0xbase,"factorio.exe (100)",7,0x00000000,1,Software\Exact',
                r'RegQueryKey,4,0xbase,"factorio.exe (100)",7,0x00000000,1,0',
                r'RegSetInformation,5,0xresult,"factorio.exe (100)",7,0x00000000,1',
            ),
        }
        for name, events in cases.items():
            with self.subTest(name=name):
                text = dump(
                    'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
                    r"RegKcbCreate,2,0xbase,\REGISTRY\MACHINE",
                    *events,
                )
                effects, gaps = SESSION.observation_effects(
                    text,
                    primary_pid=100,
                    primary_stable_identity="windows:100:12345",
                    executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
                    roots=ROOTS,
                )
                self.assertTrue(gaps["unresolved_target"])
                self.assertEqual(effects[1]["classification"], "unresolved")

    def test_unknown_file_object_remains_inconclusive(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoWrite,2,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0xabc,0,4,0,0,0,"Unknown (0x123)",0',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertTrue(gaps["unresolved_target"])
        self.assertEqual(effects[1]["classification"], "unresolved")

    def test_wrong_pid_mutations_are_ignored_but_primary_start_is_required(self) -> None:
        text = dump(
            r'FileIoWrite,3,"other.exe (999)",7,"other.exe (999)",7,0,0,0,0,4,0,0,0,C:\escape.tmp,0'
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertEqual(len(effects), 1)
        self.assertTrue(gaps["unknown_process_identity"])
        self.assertTrue(gaps["attribution_gap"])

    def test_primary_pid_requires_the_exact_factorio_image(self) -> None:
        text = dump(
            'P-Start,1,"not-factorio.exe (100)",50,1,0,0,0,S-1,"not-factorio.exe",,',
            r'FileIoWrite,3,"not-factorio.exe (100)",7,"not-factorio.exe (100)",7,0,0,0,0,4,0,0,0,E:\Gate4C\instance\saves\wrong.zip,0',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertEqual(len(effects), 1)
        self.assertTrue(gaps["unknown_process_identity"])
        self.assertTrue(gaps["attribution_gap"])

    def test_nt_volume_paths_are_resolved_before_classification(self) -> None:
        text = dump(
            r"VolumeMapping,0,\Device\HarddiskVolume9,E:",
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoWrite,3,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0,0,0,4,0,0,0,\Device\HarddiskVolume9\Gate4C\instance\saves\save.zip,0',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(effects[1]["logical_resource_id"], "instance.saves")
        self.assertEqual(effects[1]["classification"], "writable")

    def test_named_provider_process_is_attributed_but_unrelated_process_is_not(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoWrite,2,"python.exe (200)",7,"python.exe (200)",7,0,0,0,0,4,0,0,0,E:\Gate4C\temporary\op\provider.json,0',
            r'FileIoWrite,3,"other.exe (999)",7,"other.exe (999)",7,0,0,0,0,4,0,0,0,C:\escape.tmp,0',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
            provider_process_ids=[200],
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(len(effects), 2)
        self.assertEqual(effects[1]["logical_resource_id"], "operation.temporary")

    def test_file_create_disposition_distinguishes_open_from_mutation(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoCreate,2,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0x1,0,0x01000060,0,0,C:\read-only.txt,,,',
            r'FileIoCreate,3,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0x2,0,0x05000060,0,0,E:\Gate4C\instance\saves\empty-directory,,,',
            r'FileIoOpEnd,4,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0x2,0,1,0x00000000,2,FileIoCreate,E:\Gate4C\instance\saves\empty-directory',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(len(effects), 2)
        self.assertEqual(effects[1]["logical_resource_id"], "instance.saves")

    def test_failed_file_create_is_not_a_persistent_effect(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoCreate,2,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0x3,0,0x05000060,0,0,C:\Windows\Temp\refused,,,',
            r'FileIoOpEnd,3,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0x3,0,1,0xC0000022,0,FileIoCreate,C:\Windows\Temp\refused',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(len(effects), 1)

    def test_file_create_requires_matching_completion_event_class(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            r'FileIoCreate,2,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0x3,0,0x05000060,0,0,C:\Windows\Temp\unknown,,,',
            r'FileIoOpEnd,3,"factorio.exe (100)",7,"factorio.exe (100)",7,0,0x3,0,1,0x00000000,2,FileIoCleanup,C:\Windows\Temp\unknown',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertTrue(gaps["attribution_gap"])
        self.assertEqual(len(effects), 1)

    def test_reused_child_pid_after_process_end_is_not_attributed(self) -> None:
        text = dump(
            'P-Start,1,"factorio.exe (100)",50,1,0,0,0,S-1,"factorio.exe",,',
            'P-Start,2,"helper.exe (101)",100,1,0,0,0,S-1,"helper.exe",,',
            'P-End,3,"helper.exe (101)",100,1,0,0,0,0,S-1,"helper.exe",,',
            'P-Start,4,"unrelated.exe (101)",999,1,0,0,0,S-1,"unrelated.exe",,',
            r'FileIoWrite,5,"unrelated.exe (101)",8,"unrelated.exe (101)",8,0,0,0,0,4,0,0,0,C:\escape.tmp,0',
        )
        effects, gaps = SESSION.observation_effects(
            text,
            primary_pid=100,
            primary_stable_identity="windows:100:12345",
            executable=r"D:\Games\Factorio\2.0\bin\x64\factorio.exe",
            roots=ROOTS,
        )
        self.assertFalse(any(gaps.values()))
        self.assertEqual(len(effects), 1)
