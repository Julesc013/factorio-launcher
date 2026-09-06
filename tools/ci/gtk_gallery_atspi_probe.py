# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Inspect one gallery window owned by the exact process under test."""

from __future__ import annotations

from collections import deque


def descendants(root, *, stop_at=None):
    pending = deque([root])
    for _ in range(10000):
        if not pending:
            return
        node = pending.popleft()
        if node is not root and stop_at is not None and stop_at(node):
            continue
        yield node
        for index in range(node.get_child_count()):
            child = node.get_child_at_index(index)
            if child is not None:
                pending.append(child)
    raise ValueError("Accessibility tree exceeds bounded traversal")


def inspect_window(desktop, pid: int, window_name: str, expected: dict, atspi) -> dict:
    # Never combine labels from other applications or sibling windows.
    windows = [node for node in descendants(desktop)
               if node.get_name() == window_name and node.get_process_id() == pid
               and atspi.role_get_name(node.get_role()) == "frame"]
    if len(windows) != 1:
        raise ValueError("Expected one exact window and PID")
    nodes = list(descendants(windows[0], stop_at=lambda node:
                            atspi.role_get_name(node.get_role()) in {"frame", "dialog", "window"}))

    def matching(name: str, role: str):
        return [node for node in nodes if node.get_name() == name
                and atspi.role_get_name(node.get_role()) == role
                and node.get_process_id() == pid
                and node.get_state_set().contains(atspi.StateType.SHOWING)]

    deck_name = "Persistent Launch Deck for selected instance " + expected["instance_name"]
    deck = matching(deck_name, "panel")
    if len(deck) != 1:
        raise ValueError("Own window lacks its exact native Launch Deck")
    for name in (expected["instance_name"], expected["status"],
                 "Readiness: " + expected["readiness"], "Operation: " + expected["operation_id"]):
        if not matching(name, "label"):
            raise ValueError("Own window lacks expected label: " + name)
    primary = matching(expected["primary_accessibility"], "push button")
    if expected["primary_visible"]:
        if len(primary) != 1:
            raise ValueError("Own window lacks the exact primary action")
        sensitive = primary[0].get_state_set().contains(atspi.StateType.SENSITIVE)
        if sensitive != expected["primary_available"]:
            raise ValueError("Primary native availability differs from fixture")
    elif primary:
        raise ValueError("Empty/error window exposes a fabricated primary action")
    if not matching(expected["secondary_label"], "push button"):
        raise ValueError("Own window lacks the exact secondary action")
    if expected["instance_name"] == "No instance selected":
        if any("Gallery Factory" in (node.get_name() or "") or "C1 Vanilla" in (node.get_name() or "")
               for node in nodes):
            raise ValueError("Empty/error accessibility tree retains sample identity")
    return {"result": "pass", "pid": pid, "window": window_name,
            "node_count": len(nodes), "deck_role": "panel", "primary_visible": bool(primary),
            "primary_available": expected["primary_available"]}


def inspect(pid: int, window_name: str, expected: dict) -> dict:
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    return inspect_window(Atspi.get_desktop(0), pid, window_name, expected, Atspi)
