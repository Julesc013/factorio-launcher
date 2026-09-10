# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import control_gallery_fixtures, gtk_control_gallery
from tools.ci import gtk_gallery_atspi_probe

ROOT = Path(__file__).resolve().parents[1]


class Node:
    def __init__(self, name="", role="label", *, pid=72, showing=True, sensitive=True, children=()):
        self.name, self.role, self.pid = name, role, pid
        self.showing, self.sensitive, self.children = showing, sensitive, list(children)

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, index):
        return self.children[index]

    def get_name(self):
        return self.name

    def get_role(self):
        return self.role

    def get_process_id(self):
        return self.pid

    def get_state_set(self):
        return self

    def contains(self, state):
        return self.showing if state == "showing" else self.sensitive


class FakeAtspi:
    class StateType:
        SHOWING = "showing"
        SENSITIVE = "sensitive"

    @staticmethod
    def role_get_name(role):
        return role


def window(record, *, pid=72, title="Gallery"):
    labels = [record["instance_name"], record["status"], "Readiness: " + record["readiness"],
              "Operation: " + record["operation_id"]]
    children = [Node(name, pid=pid) for name in labels]
    children += [Node("Persistent Launch Deck for selected instance " + record["instance_name"], "panel", pid=pid),
                 Node(record["secondary_label"], "push button", pid=pid)]
    if record["primary_visible"]:
        children.append(Node(record["primary_accessibility"], "push button", pid=pid,
                             sensitive=record["primary_available"]))
    return Node(title, "frame", pid=pid, children=children)


class GtkControlGalleryTests(unittest.TestCase):
    def test_font_inventory_binds_actual_bytes_and_detects_same_size_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            font = Path(temporary) / "fixture.font"
            font.write_bytes(b"first font bytes")
            listing = (str(font) + "\n" + str(font) + "\n").encode()
            with mock.patch.object(gtk_control_gallery.subprocess, "check_output", return_value=listing):
                first = gtk_control_gallery.font_inputs()
                self.assertEqual(first, {str(font): {"bytes": 16, "sha256": hashlib.sha256(b"first font bytes").hexdigest()}})
                font.write_bytes(b"other font bytes")
                second = gtk_control_gallery.font_inputs()
                self.assertEqual(first[str(font)]["bytes"], second[str(font)]["bytes"])
                self.assertNotEqual(first, second)

    def test_font_inventory_refuses_empty_relative_oversized_or_missing_inputs(self):
        for listing in (b"", b"relative.font\n", b"x" * 65537,
                        ("\n".join(str((Path.cwd() / str(i))) for i in range(1025))).encode()):
            with self.subTest(bytes=len(listing)), mock.patch.object(
                    gtk_control_gallery.subprocess, "check_output", return_value=listing):
                with self.assertRaises(ValueError):
                    gtk_control_gallery.font_inputs()
        with tempfile.TemporaryDirectory() as temporary:
            missing = (str(Path(temporary) / "missing.font") + "\n").encode()
            with mock.patch.object(gtk_control_gallery.subprocess, "check_output", return_value=missing):
                with self.assertRaises(FileNotFoundError):
                    gtk_control_gallery.font_inputs()

    def test_font_coverage_keeps_missing_native_glyphs_unqualified(self):
        row = {"state": "ready", "variant": "overflow", "scale_percent": 125, "theme": "HighContrast",
               "font_label_observations": 12, "font_unknown_glyphs": 0, "identity_unknown_glyphs": 0}
        self.assertEqual(gtk_control_gallery.fixture_font_coverage([row])["result"], "pass")
        for field in ("font_unknown_glyphs", "identity_unknown_glyphs"):
            missing = dict(row, **{field: 2})
            receipt = gtk_control_gallery.fixture_font_coverage([row, missing])
            self.assertEqual(receipt["result"], "missing_glyphs")
            self.assertEqual(receipt["missing_cells"][0][field], 2)
            self.assertEqual(receipt["label_observations"], 24)

    def test_font_coverage_refuses_absent_or_invalid_observations(self):
        row = {"font_label_observations": 1, "font_unknown_glyphs": 0, "identity_unknown_glyphs": 0}
        with self.assertRaises(ValueError):
            gtk_control_gallery.fixture_font_coverage([])
        for field in row:
            for value in (None, True, -1, "0"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    gtk_control_gallery.fixture_font_coverage([dict(row, **{field: value})])
        with self.assertRaises(ValueError):
            gtk_control_gallery.fixture_font_coverage([dict(row, font_label_observations=0)])

    def test_six_states_keep_distinct_backend_facts(self):
        records = {state: gtk_control_gallery.presentation(case)
                   for state, case in control_gallery_fixtures.cases().items()}
        self.assertTrue(records["ready"]["primary_available"])
        self.assertIn("stale_readiness", records["blocked"]["status"])
        self.assertFalse(records["blocked"]["primary_available"])
        self.assertEqual(records["busy"]["operation_id"], "gallery-operation")
        self.assertIn("gallery-transaction", records["recovery"]["status"])
        self.assertEqual(records["recovery"]["secondary_label"], "Recover operation")
        for state in ("empty", "error"):
            self.assertFalse(records[state]["primary_visible"])
            self.assertEqual(records[state]["instance_name"], "No instance selected")
            self.assertEqual(records[state]["installation_summary"], "No backend installations.")
            self.assertEqual(records[state]["readiness"], "Unavailable")
        self.assertNotEqual(records["empty"]["status"], records["error"]["status"])
        self.assertIn("工場 e\u0301 🚂", records["ready-overflow"]["instance_name"])
        self.assertGreater(len(records["ready-overflow"]["instance_name"]), 250)

    def test_adapter_does_not_mutate_or_inherit_positive_records(self):
        case = control_gallery_fixtures.scenario("ready")
        before = copy.deepcopy(case)
        gtk_control_gallery.presentation(case)
        self.assertEqual(case, before)
        case["snapshots"]["launch_deck"]["selected_context"] = {}
        case["snapshots"]["launch_deck"]["available_semantic_actions"] = []
        record = gtk_control_gallery.presentation(case)
        self.assertEqual(record["instance_name"], "No instance selected")
        self.assertFalse(record["primary_visible"])

    def test_keyfile_escapes_control_characters_without_losing_unicode(self):
        encoded = gtk_control_gallery.keyfile({"name": "工場\\name\nline\r\ttab", "enabled": False})
        self.assertEqual(encoded, "[case]\nname=工場\\\\name\\nline\\r\\ttab\nenabled=false\n")

    def probe(self, desktop, record):
        return gtk_gallery_atspi_probe.inspect_window(desktop, 72, "Gallery", record, FakeAtspi)

    def test_external_probe_accepts_each_exact_window_state(self):
        for case in control_gallery_fixtures.cases().values():
            with self.subTest(case=case["state"], variant=case["variant"]):
                record = gtk_control_gallery.presentation(case)
                self.assertEqual(self.probe(Node(children=[window(record)]), record)["result"], "pass")

    def test_external_probe_rejects_foreign_pid_and_sibling_window_label_substitution(self):
        record = gtk_control_gallery.presentation(control_gallery_fixtures.scenario("ready"))
        own = window(record)
        own.children = []
        for foreign in (window(record, pid=73), window(record, title="Other window")):
            with self.subTest(pid=foreign.pid, title=foreign.name), self.assertRaises(ValueError):
                self.probe(Node(children=[own, foreign]), record)

    def test_external_probe_rejects_duplicate_windows_and_wrong_availability(self):
        record = gtk_control_gallery.presentation(control_gallery_fixtures.scenario("blocked"))
        with self.assertRaises(ValueError):
            self.probe(Node(children=[window(record), window(record)]), record)
        own = window(record)
        own.children[-1].sensitive = True
        with self.assertRaises(ValueError):
            self.probe(Node(children=[own]), record)

    def test_external_probe_cannot_borrow_labels_from_nested_window(self):
        record = gtk_control_gallery.presentation(control_gallery_fixtures.scenario("ready"))
        own = window(record)
        own.children = [window(record, title="Nested window")]
        with self.assertRaises(ValueError):
            self.probe(Node(children=[own]), record)

    def test_external_probe_rejects_hidden_labels_and_sample_residue(self):
        for state in ("ready", "empty"):
            record = gtk_control_gallery.presentation(control_gallery_fixtures.scenario(state))
            own = window(record)
            if state == "ready":
                own.children[1].showing = False
            else:
                own.children.append(Node("C1 Vanilla"))
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.probe(Node(children=[own]), record)

    def test_gallery_links_only_shared_widgets_and_recording_host(self):
        root = ROOT / "apps/gui/linux/gtk"
        meson = (root / "meson.build").read_text(encoding="utf-8")
        target = meson.split("executable('facman-control-gallery',", 1)[1].split("\n)", 1)[0]
        self.assertIn("'control_gallery.c', 'shell_view.c'", target)
        for source in (target, (root / "shell_view.c").read_text(encoding="utf-8"),
                       (root / "control_gallery.c").read_text(encoding="utf-8")):
            for forbidden in ("command_client", "g_subprocess_", "facman_gtk_rpc_call", "g_spawn_"):
                self.assertNotIn(forbidden, source)
        controller = (root / "main.c").read_text(encoding="utf-8")
        self.assertIn("facman_gtk_view_new", controller)
        self.assertIn("facman_gtk_view_render", controller)
        self.assertIn('"product.inspect"', (root / "shell_view.c").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
