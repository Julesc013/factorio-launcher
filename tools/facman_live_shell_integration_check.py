# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Check the bounded live-presentation seam shared by all three C1 shells."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/presentation"
COMPLETED_LAUNCH = FIXTURES / "live/completed-launch.transport_response.v2.json"
COMMAND_SEQUENCE = (
    "workspace.status",
    "installs.scan",
    "instance.list",
    "instances.inspect",
    "instances.readiness",
    "workspace.recovery.inspect",
)


def require(text: str, needles: tuple[str, ...], label: str) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{label}: missing {', '.join(missing)}")


def main() -> int:
    winforms = (ROOT / "apps/gui/windows/winforms/C1LivePresentationStore.cs").read_text(encoding="utf-8")
    winforms_shell = (ROOT / "apps/gui/windows/winforms/C1ShellForm.cs").read_text(encoding="utf-8")
    appkit = (ROOT / "apps/gui/macos/appkit/FacManLivePresentation.m").read_text(encoding="utf-8")
    appkit_shell = (ROOT / "apps/gui/macos/appkit/MainWindowController.m").read_text(encoding="utf-8")
    gtk = (ROOT / "apps/gui/linux/gtk/main.c").read_text(encoding="utf-8")
    for label, text in (("WinForms", winforms), ("AppKit", appkit), ("GTK", gtk)):
        require(text, COMMAND_SEQUENCE, label)
        require(
            text,
            (
                "run.execute",
                "execution_available",
                "stale_readiness",
                "workspace.recovery.apply",
                "non_authoritative_view_copy",
                "completed_factorio_launch_session_v1",
            ),
            label,
        )

    require(winforms_shell, ("FACMAN_PRESENTATION_MODE", '"evidence"', "LIVE BACKEND MODE"), "WinForms shell")
    require(appkit_shell, ("FACMAN_PRESENTATION_MODE", '@\"evidence\"', "LIVE BACKEND MODE"), "AppKit shell")
    require(gtk, ("FACMAN_PRESENTATION_MODE", '"evidence"', "LIVE BACKEND MODE"), "GTK shell")
    require(
        gtk,
        (
            'facman_payload_text(result, "schema")',
            'facman_payload_boolean(result, "complete")',
        ),
        "GTK completed launch projection",
    )

    completed_launch = json.loads(COMPLETED_LAUNCH.read_text(encoding="utf-8"))
    if completed_launch["schema"] != "facman.transport_response.v2":
        raise SystemExit("GTK regression fixture does not preserve the transport envelope schema")
    if completed_launch["payload"].get("schema") != "factorio.launch_session.v1":
        raise SystemExit("GTK regression fixture does not contain a completed launch payload")
    if completed_launch["payload"].get("complete") is not True:
        raise SystemExit("GTK regression fixture launch session is not complete")

    # Fixture bytes stay governed by their existing manifest/checker. Live mode
    # is an additive projection and cannot rewrite a deterministic fixture.
    manifest = json.loads((FIXTURES / "manifest.v0.json").read_text(encoding="utf-8"))
    for item in manifest["states"]:
        document = json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
        if document["authority_scope"] not in {"fixture_only", "unavailable"}:
            raise SystemExit(f"fixture authority changed: {item['path']}")
        if "source_mode" in document:
            raise SystemExit(f"fixture was rewritten with live source metadata: {item['path']}")

    with (ROOT / "contracts/command/factorio/run.execute.v1.toml").open("rb") as handle:
        route = tomllib.load(handle)
    if route["availability"] != "unavailable_until_isolation_proof":
        raise SystemExit("run.execute authority/availability changed in live shell integration")

    print("facman-live-shell-integration-check: ok (3 shells, existing RPC, backend-gated Play)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
