# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gate4c_observer_self_test", ROOT / "tools/gate4c_observer_self_test.py"
)
assert SPEC and SPEC.loader
OBSERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OBSERVER)


class Gate4CObserverSelfTestTests(unittest.TestCase):
    def observer_validation_fixture(
        self, root: Path, *, generated_at: str = "2026-07-22T13:00:00Z"
    ) -> tuple[Path, dict[str, object], dict[str, object], dict[str, object]]:
        artifacts: dict[str, object] = {}
        for name in ("trace", "dump", "stats"):
            path = root / f"{name}.artifact"
            path.write_bytes(name.encode("utf-8"))
            artifacts[name] = {"path": str(path), "sha256": OBSERVER.PREFLIGHT.sha256_file(path)}
        tooling: dict[str, object] = {
            "facman_tool_commit": "tooling-commit",
            "worktree_clean": True,
            "tool_files": {},
            "valid": True,
        }
        tools: dict[str, object] = {
            name: {"valid": True, "sha256": f"{name}-sha"}
            for name in ("wpr", "xperf", "wpaexporter")
        }
        session: dict[str, object] = {
            "provider": "windows.machine-local-session.v1",
            "machine_binding_id": "machine",
            "boot_identity": "boot",
            "valid": True,
        }
        record: dict[str, object] = {
            "schema": OBSERVER.PREFLIGHT.OBSERVER_SELF_TEST_SCHEMA,
            "canonicalization_version": "facman.sorted-json.v1",
            "generated_at": generated_at,
            "work_unit": OBSERVER.PREFLIGHT.WORK_UNIT,
            "candidate_revision": OBSERVER.PREFLIGHT.CANDIDATE_REVISION,
            "status": "pass",
            "elevated": True,
            "machine_binding_id": "machine",
            "boot_identity": "boot",
            "tooling": tooling,
            "observer_tools": tools,
            "provider": OBSERVER.PREFLIGHT.observer_provider_identity(ROOT),
            "attribution_complete": True,
            "lost_events": 0,
            "artifacts": artifacts,
        }
        record["self_test_digest"] = OBSERVER.PREFLIGHT.digest_value(record)
        path = root / "observer-self-test.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return path, tooling, tools, session

    def validate_observer_fixture(
        self,
        path: Path,
        tooling: dict[str, object],
        tools: dict[str, object],
        session: dict[str, object],
        *,
        now: datetime,
    ) -> dict[str, object]:
        toolkit = path.parent / "observer-tools"
        toolkit.mkdir(exist_ok=True)
        for name in ("wpr.exe", "xperf.exe", "wpaexporter.exe"):
            (toolkit / name).write_bytes(name.encode("utf-8"))

        def tool_identity(value: str | Path | None) -> dict[str, object]:
            stem = Path(str(value).replace("\\", "/")).stem.casefold()
            return dict(tools[stem])

        status = subprocess.CompletedProcess(
            ["wpr", "-status"], 0, "WPR is not recording", ""
        )
        with (
            mock.patch.object(
                OBSERVER.PREFLIGHT,
                "WINDOWS_PERFORMANCE_TOOLKIT_ROOT",
                toolkit,
            ),
            mock.patch.object(OBSERVER.PREFLIGHT, "run", return_value=status),
            mock.patch.object(
                OBSERVER.PREFLIGHT, "repository_tool_identity", return_value=tooling
            ),
            mock.patch.object(
                OBSERVER.PREFLIGHT,
                "executable_tool_identity",
                side_effect=tool_identity,
            ),
            mock.patch.object(OBSERVER.PREFLIGHT, "is_elevated", return_value=True),
        ):
            return OBSERVER.PREFLIGHT.observer_prerequisites(
                path,
                repo_root=ROOT,
                session=session,
                now=now,
            )

    def test_observer_tool_selection_prefers_one_complete_toolkit_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("wpr.exe", "xperf.exe", "wpaexporter.exe"):
                (root / name).write_bytes(name.encode("utf-8"))
            with (
                mock.patch.object(
                    OBSERVER.PREFLIGHT,
                    "WINDOWS_PERFORMANCE_TOOLKIT_ROOT",
                    root,
                ),
                mock.patch.object(
                    OBSERVER.PREFLIGHT.shutil,
                    "which",
                    return_value=r"C:\Windows\System32\wpr.exe",
                ),
            ):
                paths = OBSERVER.PREFLIGHT.observer_tool_paths()
            self.assertEqual(str(root / "wpr.exe"), paths["wpr"])
            self.assertEqual(str(root / "xperf.exe"), paths["xperf"])
            self.assertEqual(str(root / "wpaexporter.exe"), paths["wpaexporter"])
            self.assertTrue(
                OBSERVER.PREFLIGHT.observer_toolchain_coherent(paths)
            )

    def test_observer_tool_selection_refuses_incomplete_toolkit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "wpr.exe").write_bytes(b"wpr")
            with (
                mock.patch.object(
                    OBSERVER.PREFLIGHT,
                    "WINDOWS_PERFORMANCE_TOOLKIT_ROOT",
                    root,
                ),
                mock.patch.object(
                    OBSERVER.PREFLIGHT.shutil,
                    "which",
                    return_value=r"C:\Windows\System32\wpr.exe",
                ),
            ):
                paths = OBSERVER.PREFLIGHT.observer_tool_paths()
            self.assertEqual(
                {"wpr": None, "xperf": None, "wpaexporter": None},
                paths,
            )
            self.assertFalse(
                OBSERVER.PREFLIGHT.observer_toolchain_coherent(paths)
            )

    def test_observer_tool_selection_refuses_mixed_roots(self) -> None:
        paths = {
            "wpr": r"C:\Windows\System32\wpr.exe",
            "xperf": (
                r"C:\Program Files (x86)\Windows Kits\10"
                r"\Windows Performance Toolkit\xperf.exe"
            ),
            "wpaexporter": (
                r"C:\Program Files (x86)\Windows Kits\10"
                r"\Windows Performance Toolkit\wpaexporter.exe"
            ),
        }
        self.assertFalse(
            OBSERVER.PREFLIGHT.observer_toolchain_coherent(paths)
        )

    def test_wpr_status_requires_successful_not_recording_result(self) -> None:
        self.assertTrue(
            OBSERVER.wpr_is_not_recording(
                subprocess.CompletedProcess(
                    ["wpr", "-status"],
                    0,
                    "WPR is not recording",
                    "",
                )
            )
        )
        for result in (
            subprocess.CompletedProcess(
                ["wpr", "-status"],
                1,
                "WPR is not recording",
                "",
            ),
            subprocess.CompletedProcess(
                ["wpr", "-status"],
                0,
                "WPR recording is active",
                "",
            ),
        ):
            with self.subTest(result=result):
                self.assertFalse(OBSERVER.wpr_is_not_recording(result))

    def test_lost_event_parser_is_closed_on_unknown_format(self) -> None:
        self.assertIsNone(OBSERVER.parse_lost_events("trace complete without a count"))
        self.assertEqual(OBSERVER.parse_lost_events("Events Lost: 0"), 0)
        self.assertEqual(OBSERVER.parse_lost_events("Events Lost: 0\nEvents Lost: 7"), 7)
        self.assertEqual(
            OBSERVER.parse_lost_events("This trace has dropped 77091 events."),
            77091,
        )

    def test_observer_profile_is_narrow_closed_and_capacity_bound(self) -> None:
        profile = OBSERVER.PREFLIGHT.observer_profile_identity(ROOT)
        self.assertTrue(profile["valid"])
        self.assertEqual(
            profile["sha256"],
            "57d5301961d0c9877d769f9d4a175aae7fa4d558769f89fb32481f2046b2fd40",
        )
        self.assertEqual(profile["buffer_size_kb"], 1024)
        self.assertEqual(profile["buffer_count"], 256)
        self.assertEqual(
            profile["system_keywords"],
            ["ProcessThread", "FileIO", "FileIOInit", "Registry"],
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = Path(OBSERVER.PREFLIGHT.OBSERVER_PROFILE_RELATIVE_PATH)
            changed = root / relative
            changed.parent.mkdir(parents=True)
            source = ROOT / relative
            changed.write_bytes(
                source.read_bytes().replace(
                    b'<Keyword Value="Registry"/>',
                    b'<Keyword Value="DiskIO"/>',
                )
            )
            refused = OBSERVER.PREFLIGHT.observer_profile_identity(root)
            self.assertFalse(refused["valid"])
            self.assertEqual(refused["reason"], "profile_contract_mismatch")

    def test_wpr_start_uses_only_the_bound_custom_profile(self) -> None:
        profile = ROOT / OBSERVER.PREFLIGHT.OBSERVER_PROFILE_RELATIVE_PATH
        args = OBSERVER.wpr_start_arguments(
            "wpr.exe",
            profile,
            Path(r"E:\Gate4C\observer"),
        )
        self.assertEqual(args.count("-start"), 1)
        self.assertIn(
            (
                f"{profile}!{OBSERVER.PREFLIGHT.OBSERVER_PROFILE_NAME}."
                f"{OBSERVER.PREFLIGHT.OBSERVER_PROFILE_DETAIL_LEVEL}"
            ),
            args,
        )
        for broad_profile in ("GeneralProfile", "FileIO", "Registry"):
            self.assertNotIn(broad_profile, args)

    def test_probe_attribution_requires_all_domains_and_pid(self) -> None:
        parent_process_id = 4242
        child_process_id = 5151
        dump = "\n".join(
            [
                r"FileIo/Write,pid=4242,C:\Gate4C\probe.txt",
                r"Registry/SetValue,pid=4242,FacManGate4CRegistryProbe-test",
                r"Process/Start,pid=5151,parentpid=4242,FacManGate4CProcessProbe-test",
            ]
        )
        result = OBSERVER.classify_dump(
            dump,
            parent_process_id=parent_process_id,
            child_process_id=child_process_id,
            file_marker=r"C:\Gate4C\probe.txt",
            registry_marker="FacManGate4CRegistryProbe-test",
            process_marker="FacManGate4CProcessProbe-test",
        )
        self.assertTrue(result["attribution_complete"])

        incomplete = OBSERVER.classify_dump(
            dump.replace("FacManGate4CRegistryProbe-test", "missing"),
            parent_process_id=parent_process_id,
            child_process_id=child_process_id,
            file_marker=r"C:\Gate4C\probe.txt",
            registry_marker="FacManGate4CRegistryProbe-test",
            process_marker="FacManGate4CProcessProbe-test",
        )
        self.assertFalse(incomplete["attribution_complete"])

    def test_each_domain_refuses_wrong_pid(self) -> None:
        base = "\n".join(
            [
                r"FileIo/Write,pid=4242,C:\Gate4C\probe.txt",
                r"Registry/SetValue,pid=4242,FacManGate4CRegistryProbe-test",
                r"Process/Start,pid=5151,parentpid=4242,FacManGate4CProcessProbe-test",
            ]
        )
        mutations = (
            base.replace("FileIo/Write,pid=4242", "FileIo/Write,pid=9999"),
            base.replace(
                "FileIo/Write,pid=4242",
                "FileIo/Write,pid=9999,unrelated=4242",
            ),
            base.replace("Registry/SetValue,pid=4242", "Registry/SetValue,pid=9999"),
            base.replace("Process/Start,pid=5151", "Process/Start,pid=9999"),
            base.replace("parentpid=4242", "parentpid=9999"),
        )
        for dump in mutations:
            with self.subTest(dump=dump):
                result = OBSERVER.classify_dump(
                    dump,
                    parent_process_id=4242,
                    child_process_id=5151,
                    file_marker=r"C:\Gate4C\probe.txt",
                    registry_marker="FacManGate4CRegistryProbe-test",
                    process_marker="FacManGate4CProcessProbe-test",
                )
                self.assertFalse(result["attribution_complete"])

    def test_each_domain_requires_the_expected_event_class(self) -> None:
        base = "\n".join(
            [
                r"FileIo/Write,pid=4242,C:\Gate4C\probe.txt",
                r"Registry/SetValue,pid=4242,FacManGate4CRegistryProbe-test",
                r"Process/Start,pid=5151,parentpid=4242,FacManGate4CProcessProbe-test",
            ]
        )
        mutations = (
            base.replace("FileIo/Write", "Network/Write"),
            base.replace("Registry/SetValue", "Image/Load"),
            base.replace("Process/Start", "Thread/Start"),
        )
        for dump in mutations:
            with self.subTest(dump=dump):
                result = OBSERVER.classify_dump(
                    dump,
                    parent_process_id=4242,
                    child_process_id=5151,
                    file_marker=r"C:\Gate4C\probe.txt",
                    registry_marker="FacManGate4CRegistryProbe-test",
                    process_marker="FacManGate4CProcessProbe-test",
                )
                self.assertFalse(result["attribution_complete"])

    def test_self_test_is_bound_to_current_tools_machine_boot_and_time(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, tooling, tools, session = self.observer_validation_fixture(root)
            now = datetime(2026, 7, 22, 13, 5, tzinfo=timezone.utc)
            result = self.validate_observer_fixture(
                path, tooling, tools, session, now=now
            )
            self.assertTrue(result["self_test_passed"])
            self.assertTrue(result["self_test_validation"]["artifacts"])
            self.assertTrue(result["self_test_validation"]["self_test_digest"])

            changed_session = {**session, "boot_identity": "new-boot"}
            restarted = self.validate_observer_fixture(
                path, tooling, tools, changed_session, now=now
            )
            self.assertFalse(restarted["self_test_passed"])
            self.assertFalse(restarted["self_test_validation"]["boot_identity"])

            changed_tools = {**tools, "xperf": {"valid": True, "sha256": "changed"}}
            updated = self.validate_observer_fixture(
                path, tooling, changed_tools, session, now=now
            )
            self.assertFalse(updated["self_test_passed"])
            self.assertFalse(updated["self_test_validation"]["observer_tools"])

            stale = self.validate_observer_fixture(
                path,
                tooling,
                tools,
                session,
                now=datetime(2026, 7, 22, 13, 16, tzinfo=timezone.utc),
            )
            self.assertFalse(stale["self_test_passed"])
            self.assertEqual(
                "timestamp_expired", stale["self_test_validation"]["time"]["reason"]
            )

    def test_self_test_refuses_changed_trace_hash_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, tooling, tools, session = self.observer_validation_fixture(root)
            record = json.loads(path.read_text(encoding="utf-8"))
            Path(record["artifacts"]["trace"]["path"]).write_bytes(b"changed")
            result = self.validate_observer_fixture(
                path,
                tooling,
                tools,
                session,
                now=datetime(2026, 7, 22, 13, 5, tzinfo=timezone.utc),
            )
            self.assertFalse(result["self_test_passed"])
            self.assertFalse(result["self_test_validation"]["artifacts"])

            record["lost_events"] = 1
            path.write_text(json.dumps(record), encoding="utf-8")
            result = self.validate_observer_fixture(
                path,
                tooling,
                tools,
                session,
                now=datetime(2026, 7, 22, 13, 5, tzinfo=timezone.utc),
            )
            self.assertFalse(result["self_test_validation"]["self_test_digest"])

    def test_self_test_refuses_each_bound_context_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, tooling, tools, session = self.observer_validation_fixture(root)
            original = json.loads(path.read_text(encoding="utf-8"))
            mutations = {
                "work_unit": lambda value: value.__setitem__("work_unit", "other"),
                "provider": lambda value: value["provider"].__setitem__(
                    "revision", "other"
                ),
                "candidate_revision": lambda value: value.__setitem__(
                    "candidate_revision", "other"
                ),
                "elevated": lambda value: value.__setitem__("elevated", False),
                "machine_binding": lambda value: value.__setitem__(
                    "machine_binding_id", "other"
                ),
                "tooling": lambda value: value["tooling"].__setitem__(
                    "facman_tool_commit", "other"
                ),
                "observer_tools": lambda value: value["observer_tools"]["wpr"].__setitem__(
                    "sha256", "other"
                ),
            }
            for expected_key, mutate in mutations.items():
                with self.subTest(binding=expected_key):
                    value = json.loads(json.dumps(original))
                    value.pop("self_test_digest", None)
                    mutate(value)
                    value["self_test_digest"] = OBSERVER.PREFLIGHT.digest_value(value)
                    path.write_text(json.dumps(value), encoding="utf-8")
                    result = self.validate_observer_fixture(
                        path,
                        tooling,
                        tools,
                        session,
                        now=datetime(2026, 7, 22, 13, 5, tzinfo=timezone.utc),
                    )
                    self.assertFalse(result["self_test_passed"])
                    self.assertFalse(result["self_test_validation"][expected_key])


if __name__ == "__main__":
    unittest.main()
