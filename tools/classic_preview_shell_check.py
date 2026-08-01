# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import plistlib
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import facman_presentation_check, generate_classic_preview_rpc

APPKIT = ROOT / "apps/gui/macos/appkit"
GTK = ROOT / "apps/gui/linux/gtk"
FIXTURES = ROOT / "tests/fixtures/presentation"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _require(text: str, anchors: tuple[str, ...], label: str, problems: list[str]) -> None:
    for anchor in anchors:
        if anchor not in text:
            problems.append(f"{label}: missing {anchor!r}")


def validate() -> list[str]:
    problems: list[str] = []
    if facman_presentation_check.main() != 0:
        problems.append("presentation fixture corpus is invalid")

    fixtures = {
        state: json.loads((FIXTURES / f"{state}.facman.presentation.v0.json").read_text(encoding="utf-8"))
        for state in ("positive", "refused", "running", "exited", "interrupted")
    }
    for path, expected in generate_classic_preview_rpc.render().items():
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            problems.append(f"stale generated GTK RPC encoder: {path.relative_to(ROOT)}")
    appkit_model = _text(APPKIT / "FacManPreviewFixture.m")
    gtk_model = _text(GTK / "preview_model.c")
    for state, fixture in fixtures.items():
        values = [
            state,
            fixture["launch_deck"]["status_text"],
            fixture["pages"]["activity"]["summary"],
        ]
        refusal = fixture.get("refusal")
        if refusal is not None:
            values.append(refusal["code"])
        operation_id = fixture["launch_deck"].get("operation_id")
        if operation_id:
            values.append(operation_id)
        recovery_id = fixture["launch_deck"].get("recovery_id")
        if recovery_id:
            values.append(recovery_id)
        for value in values:
            if value not in appkit_model:
                problems.append(f"AppKit fixture model does not project {state}:{value}")
            if value not in gtk_model:
                problems.append(f"GTK fixture model does not project {state}:{value}")

    appkit_view = _text(APPKIT / "MainWindowController.m")
    appkit_delegate = _text(APPKIT / "AppDelegate.m")
    appkit_transport = _text(APPKIT / "CliProcessClient.mm")
    _require(appkit_view, (
        '@"Instances"', '@"Installations"', '@"Activity"', '@"Settings / About"', '@"Advanced"',
        "Launch Deck", "stale_readiness", "Last Run", "operation.fixture-play-002",
        "setAccessibilityLabel", "setAccessibilityHelp", "NSAccessibilityPostNotification",
        "System Native", "FacMan OEM+ Launch Deck",
    ), "AppKit shell", problems)
    _require(appkit_delegate, (
        '@"Navigate"', '@"1"', '@"2"', '@"3"', '@"4"', '@"5"',
        "Restore System Native Appearance",
    ), "AppKit menus", problems)
    _require(appkit_transport, (
        '@[ @"rpc", @"--stdio" ]', "FacManCliTimeoutSeconds", "FacManMaximumStdoutBytes",
        "FacManMaximumStderrBytes", "outcomeUnknownWithCommandId", "recoveryRequired",
    ), "AppKit bounded RPC", problems)

    cmake = _text(APPKIT / "CMakeLists.txt")
    _require(cmake, (
        "MACOSX_BUNDLE", 'CMAKE_OSX_ARCHITECTURES "x86_64"',
        'CMAKE_OSX_DEPLOYMENT_TARGET "10.13"', "Info.plist", "install(TARGETS FacMan BUNDLE",
    ), "AppKit bundle", problems)
    with (APPKIT / "Info.plist").open("rb") as handle:
        plist = plistlib.load(handle)
    if plist.get("CFBundleExecutable") != "FacMan":
        problems.append("AppKit bundle executable must be FacMan")
    if plist.get("LSMinimumSystemVersion") != "10.13":
        problems.append("AppKit bundle deployment floor must be macOS 10.13")
    if plist.get("LSArchitecturePriority") != ["x86_64"]:
        problems.append("AppKit bundle architecture priority must be x86_64 only")

    gtk_main = _text(GTK / "main.c")
    gtk_transport = _text(GTK / "command_client.c")
    gtk_encoder = _text(GTK / "generated_rpc_request.c")
    _require(gtk_main, (
        '"instances"', '"installations"', '"activity"', '"settings"', '"advanced"',
        "Launch Deck", "stale_readiness", "Last Run", "operation.fixture-play-002",
        "gtk_menu_bar_new", "GDK_KEY_1", "GDK_KEY_5", "atk_object_set_name",
        "atk_object_set_description", "System Native", "OEM+ Launch Deck",
        "g_object_ref(shell->rpc_result)", "g_object_unref(buffer)",
        "GLIB_CHECK_VERSION(2, 74, 0)", "G_APPLICATION_DEFAULT_FLAGS",
        "G_APPLICATION_FLAGS_NONE", "FACMAN_APPLICATION_FLAGS",
    ), "GTK shell", problems)
    _require(gtk_transport, (
        '"rpc", "--stdio"', "FACMAN_RPC_TIMEOUT_SECONDS", "FACMAN_RPC_STDOUT_LIMIT",
        "FACMAN_RPC_STDERR_LIMIT", "outcome_unknown", "g_subprocess_communicate_utf8_async",
        "g_subprocess_force_exit",
    ), "GTK bounded RPC", problems)
    _require(gtk_encoder, (
        "facman_preview_json_escape", 'g_string_append(escaped, "\\\\\\\"")',
        '"\\\\u%04x"', "g_get_monotonic_time", "g_random_int",
    ), "GTK generated RPC encoder", problems)
    if "g_strescape" in gtk_encoder:
        problems.append("GTK RPC encoder uses C-string escaping instead of JSON escaping")
    meson = _text(GTK / "meson.build")
    _require(meson, (
        "dependency('gtk+-3.0', version: '>=3.22'", "executable('facman-gui-gtk'",
        "install: true", "io.github.julesc013.facman.preview.desktop",
        "facman-live-presentation-payload-scope", "live_presentation_test.c",
    ), "GTK package prototype", problems)
    desktop = _text(GTK / "io.github.julesc013.facman.preview.desktop")
    if "Exec=facman-gui-gtk" not in desktop or "Terminal=false" not in desktop:
        problems.append("GTK desktop entry does not launch the native package entrypoint")

    for profile_id in ("macos_legacy_appkit_x64", "linux_x11_gtk_x64"):
        with (ROOT / f"release/profiles/{profile_id}/profile.toml").open("rb") as handle:
            profile = tomllib.load(handle)
        if profile.get("support_tier") != "package_preview":
            problems.append(f"{profile_id}: support tier must remain package_preview")
        runtime_claim = profile.get("runtime_claim", "")
        if "no_runtime_qualification" not in runtime_claim and "no_bundle_runtime_proof" not in runtime_claim:
            problems.append(f"{profile_id}: runtime claim must remain explicitly unqualified")
        if profile.get("publication") is not False and profile_id.startswith("macos"):
            problems.append(f"{profile_id}: publication must remain false")

    bounded_sources = "\n".join((appkit_view, appkit_transport, gtk_main, gtk_transport, gtk_encoder))
    for forbidden in ("libulk", "ulk_static", "gtk_socket", "NSConnection", "Universal Launcher ABI"):
        if forbidden in bounded_sources:
            problems.append(f"classic preview shell introduced forbidden boundary {forbidden!r}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"classic-preview-shell-check: {problem}", file=sys.stderr)
        return 1
    print("classic-preview-shell-check: ok (AppKit and GTK runtime qualification remains external)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
