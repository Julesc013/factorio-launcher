# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Query the live GTK preview through the external AT-SPI accessibility API."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402


DECK_NAME = "Persistent Launch Deck for selected instance C1 Vanilla"
PRIMARY_NAME = "Play unavailable because readiness is stale"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--window-name", required=True)
    args = parser.parse_args()
    facts = inspect_desktop(args.window_name)
    if facts is None:
        return 1
    Path(args.output).write_text(
        "schema=facman.gtk_external_atspi_probe.v1\n"
        "status=pass\n"
        "window_name=pass\n"
        "launch_deck_name=pass\n"
        f"launch_deck_role={facts['deck_role']}\n"
        "primary_name=pass\n"
        f"primary_role={facts['primary_role']}\n",
        encoding="utf-8",
    )
    return 0


def inspect_desktop(window_name: str) -> dict[str, str] | None:
    desktop = Atspi.get_desktop(0)
    pending = deque([desktop])
    visited = 0
    window_seen = False
    deck_role = ""
    primary_role = ""
    while pending and visited < 10000:
        accessible = pending.popleft()
        visited += 1
        try:
            name = accessible.get_name() or ""
            role_name = Atspi.role_get_name(accessible.get_role()) or ""
            if name == window_name:
                window_seen = True
            elif name == DECK_NAME:
                deck_role = role_name
            elif name == PRIMARY_NAME:
                primary_role = role_name
            for index in range(accessible.get_child_count()):
                child = accessible.get_child_at_index(index)
                if child is not None:
                    pending.append(child)
        except Exception:
            continue
    if not window_seen or not deck_role or primary_role != "push button":
        return None
    return {"deck_role": deck_role, "primary_role": primary_role}


if __name__ == "__main__":
    raise SystemExit(main())
