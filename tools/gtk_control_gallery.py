# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise shared production GTK controls in an isolated desktop session."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import control_gallery_fixtures, development_layout
from tools.ci import gtk_gallery_atspi_probe

SCALES = (100, 125, 150, 200)
THEMES = ("Adwaita", "HighContrast")


def presentation(case: dict) -> dict:
    """Adapt the shared backend-shaped fixture to the production GTK view record."""
    state = case["state"]
    deck = case["snapshots"].get("launch_deck", {})
    selected = deck.get("selected_context", {})
    actions = deck.get("available_semantic_actions", [])
    primary = next((action for action in actions if action["role"] == "primary"), None)
    blockers = deck.get("specific_blockers", [])
    operations = deck.get("active_operations", [])
    transactions = deck.get("recovery", {}).get("transactions", [])
    name = selected.get("display_name", "No instance selected")
    operation = operations[0]["operation_id"] if operations else "none"
    status = "Ready"
    if blockers:
        status = blockers[0]["code"] + ": " + blockers[0]["detail"]
    elif transactions:
        status = "Recovery required: " + transactions[0]["transaction_id"]
        operation = transactions[0]["operation_id"]
    elif operations:
        status = "Running: " + operation
    elif not selected:
        status = case["error"] if state == "error" else "No instance selected"
    available = bool(primary and primary["availability"] == "available")
    return {
        "schema": "facman.gtk_gallery_case.v1", "state": state, "variant": case["variant"],
        "instance_name": name,
        "instance_summary": name if selected else "No backend instances.",
        "installation_summary": ("gallery-install — read-only — 2.0.0" if selected else "No backend installations."),
        "status": status,
        "readiness": deck.get("readiness", {}).get("overall_state", "Unavailable") if selected else "Unavailable",
        "activity": status if operations or transactions else "No active operation.",
        "last_run": "Authoritative Last Run unavailable", "operation_id": operation,
        "primary_label": primary["label"] if primary else "Play",
        "primary_accessibility": "Play" if available else "Play unavailable",
        "primary_available": available, "primary_visible": bool(primary),
        "secondary_label": "Recover operation" if transactions else "Refresh backend state",
    }


def keyfile(record: dict) -> str:
    def value(item):
        if isinstance(item, bool):
            return "true" if item else "false"
        return str(item).replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return "[case]\n" + "".join(f"{key}={value(item)}\n" for key, item in record.items())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_inputs() -> dict[str, str]:
    paths = list((ROOT / "apps/gui/linux/gtk").glob("*.c"))
    paths += list((ROOT / "apps/gui/linux/gtk").glob("*.h"))
    paths += [ROOT / path for path in (
        "apps/gui/linux/gtk/meson.build", "apps/gui/linux/gtk/generated_project_version.txt",
        "tools/gtk_control_gallery.py", "tools/control_gallery_fixtures.py",
        "tools/ci/gtk_gallery_atspi_probe.py", "tools/development_layout.py",
        "tests/golden/commands/presentation.query.success.json",
    )]
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(paths)}


def font_inputs() -> dict[str, dict]:
    raw = subprocess.check_output(["fc-list", "--format=%{file}\n"], timeout=15)
    if len(raw) > 65536:
        raise ValueError("Font inventory exceeds its byte budget")
    paths = sorted(set(raw.decode("utf-8").splitlines()))
    if not paths or len(paths) > 1024:
        raise ValueError("Finite nonempty font inventory required")
    result, total = {}, 0
    for name in paths:
        path = Path(name)
        if not path.is_absolute():
            raise ValueError("Font inventory requires absolute file paths")
        digest, size = hashlib.sha256(), 0
        with path.open("rb") as stream:
            while block := stream.read(65536):
                size += len(block)
                total += len(block)
                if size > 64 * 1024 * 1024 or total > 1024 * 1024 * 1024:
                    raise ValueError("Font input byte budget exceeded")
                digest.update(block)
        result[name] = {"bytes": size, "sha256": digest.hexdigest()}
    return result


def fixture_font_coverage(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("Font coverage requires observed cells")
    missing = []
    for row in rows:
        for field, minimum in (("font_label_observations", 1), ("font_unknown_glyphs", 0), ("identity_unknown_glyphs", 0)):
            if type(row.get(field)) is not int or row[field] < minimum:
                raise ValueError("Font coverage requires complete native glyph observations")
        if row["font_unknown_glyphs"] or row["identity_unknown_glyphs"]:
            missing.append({key: row[key] for key in
                            ("state", "variant", "scale_percent", "theme", "font_unknown_glyphs", "identity_unknown_glyphs")})
    return {"result": "pass" if not missing else "missing_glyphs", "cells": len(rows),
            "scope": "Mapped production GtkLabel layouts across all five visited pages, plus the instance identity layout",
            "label_observations": sum(row["font_label_observations"] for row in rows), "missing_cells": missing}


def owned_root(path: Path) -> Path:
    path = path.resolve()
    marker = development_layout.read_marker(path)
    source = str(marker.get("source_root", ""))
    if ":\\" in source:
        # A WSL mount can use an existing Windows-owned root without rewriting its identity.
        source = subprocess.check_output(["wslpath", "-u", source], text=True).strip()
    if Path(source).resolve() != ROOT or path == ROOT or path.is_relative_to(ROOT) or ROOT.is_relative_to(path):
        raise ValueError("Gallery output requires this repository's external owned task root")
    if marker.get("task_id") != development_layout.current_task_id(ROOT):
        raise ValueError("Gallery output task identity differs from the current branch")
    return path


def command(args: list[str], log: Path, *, timeout: int = 120) -> None:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(args) + "\n" + result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}); see {log}")


def run_cell(binary: Path, fixture: Path, record: dict, cell: Path, scale: int, theme: str) -> dict:
    cell.mkdir()
    env = {**os.environ, "GTK_THEME": theme, "GTK_MODULES": "atk-bridge", "NO_AT_BRIDGE": "0",
           "GDK_BACKEND": "x11", "GDK_SCALE": "2" if scale == 200 else "1",
           "GDK_DPI_SCALE": "1" if scale == 200 else str(scale / 100)}
    with (cell / "stdout.txt").open("w", encoding="utf-8") as stdout, (cell / "stderr.txt").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen([str(binary), str(fixture), str(cell)], env=env, stdout=stdout, stderr=stderr)
        try:
            deadline = time.monotonic() + 25
            native = configparser.ConfigParser(interpolation=None)
            report = None
            error = "Native receipt not ready"
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Gallery exited {process.returncode} before external probe; see {cell}")
                if (cell / "native.ini").is_file():
                    native.read(cell / "native.ini", encoding="utf-8")
                    pid = native.getint("result", "pid")
                    if pid != process.pid:
                        raise RuntimeError("Native receipt belongs to a different process")
                    try:
                        report = gtk_gallery_atspi_probe.inspect(pid, native["result"]["window"], record)
                        break
                    except Exception as failure:
                        error = str(failure)
                time.sleep(.1)
            if report is None:
                raise RuntimeError(f"AT-SPI did not qualify own window: {error}; see {cell}")
            (cell / "external.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            (cell / "external.release").write_bytes(b"")
            if process.wait(timeout=10) != 0:
                raise RuntimeError(f"Gallery exited {process.returncode}; see {cell}")
            expected_widget_scale = 2 if scale == 200 else 1
            expected_font_dpi = 96 if scale == 200 else 96 * scale / 100
            if native.getint("result", "widget_scale_factor") != expected_widget_scale or abs(native.getfloat("result", "font_dpi") - expected_font_dpi) > .01:
                raise RuntimeError(f"Observed toolkit/font scale differs from requested fixture; see {cell}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
    return {"state": record["state"], "variant": record["variant"], "scale_percent": scale,
            "theme": theme, "assertions": native.getint("result", "assertions"),
            "body_text_contrast": native.getfloat("result", "body_text_contrast"),
            "widget_scale_factor": native.getint("result", "widget_scale_factor"),
            "font_dpi": native.getfloat("result", "font_dpi"),
            "identity_unknown_glyphs": native.getint("result", "identity_unknown_glyphs"),
            "font_label_observations": native.getint("result", "font_label_observations"),
            "font_unknown_glyphs": native.getint("result", "font_unknown_glyphs"),
            "actions": native["result"]["actions"].strip(";").split(";"),
            "external": report, "files": {name: sha(cell / name) for name in
                                           ("window.png", "native.ini", "external.json", "stdout.txt", "stderr.txt")}}


def run_session(binary: Path, attempt: Path, names: list[str], scales: list[int], themes: list[str]) -> None:
    rows = []
    for name, case in control_gallery_fixtures.cases().items():
        if names and name not in names:
            continue
        record = presentation(case)
        fixture = attempt / "fixtures" / f"{name}.ini"
        for scale in scales:
            for theme in themes:
                cell = attempt / f"{name}-{scale}-{theme}"
                rows.append(run_cell(binary, fixture, record, cell, scale, theme))
                print(f"GTK gallery PASS {cell.name}", flush=True)
    (attempt / "cells.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def run(task_root: Path, names: list[str], scales: list[int], themes: list[str], *, require_fixture_fonts: bool = False) -> dict:
    if not sys.platform.startswith("linux"):
        raise ValueError("GTK gallery requires a Linux GTK/AT-SPI host")
    task_root = owned_root(task_root)
    attempt = task_root / "gtk-control-gallery" / "runs" / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    source = source_inputs()
    report = {"schema": "facman.gtk_control_gallery.v1", "result": "fail", "source_files": source,
              "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
              "pending": ["physical monitor DPI and theme transitions", "human keyboard and screen reader evaluation",
                          "packaged release candidate qualification"],
              "fixture_font_coverage_required": require_fixture_fonts,
              "scale_scope": "GDK_SCALE=2 at 200%; GDK_DPI_SCALE font scaling at 125%/150%; isolated Xvfb",
              "theme_scope": "GTK Adwaita and HighContrast theme fixtures; no desktop configuration changed"}
    try:
        report["font_inputs"] = font_inputs()
        build = task_root / "gtk-build"
        if not (build / "build.ninja").exists():
            command(["meson", "setup", str(build), str(ROOT / "apps/gui/linux/gtk"), "--buildtype=debug", "--werror"], attempt / "build.log")
        info = json.loads((build / "meson-info/meson-info.json").read_text(encoding="utf-8"))
        options = json.loads((build / "meson-info/intro-buildoptions.json").read_text(encoding="utf-8"))
        if Path(info["directories"]["source"]).resolve() != ROOT / "apps/gui/linux/gtk" or not any(option["name"] == "werror" and option["value"] is True for option in options):
            raise ValueError("Gallery requires the exact production source and Meson --werror build")
        report["build_configuration"] = {"source": info["directories"]["source"], "werror": True}
        report["host"] = {name: subprocess.check_output(command_line, text=True).strip() for name, command_line in (
            ("kernel", ["uname", "-srmo"]), ("gtk", ["pkg-config", "--modversion", "gtk+-3.0"]),
            ("glib", ["pkg-config", "--modversion", "glib-2.0"]), ("compiler", ["cc", "--version"]),
        )}
        command(["meson", "compile", "-C", str(build)], attempt / "build.log")
        command(["meson", "test", "-C", str(build), "--print-errorlogs"], attempt / "tests.log")
        fixtures = attempt / "fixtures"
        fixtures.mkdir()
        for name, case in control_gallery_fixtures.cases().items():
            (fixtures / f"{name}.json").write_text(json.dumps(case, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            (fixtures / f"{name}.ini").write_text(keyfile(presentation(case)), encoding="utf-8")
        report["fixture_files"] = {path.name: sha(path) for path in sorted(fixtures.iterdir())}
        binary = build / "facman-control-gallery"
        report["binary_sha256"] = sha(binary)
        report["product_sha256"] = sha(build / "FacMan")
        args = ["dbus-run-session", "--", "xvfb-run", "-a", "-s", "-screen 0 2560x1800x24",
                sys.executable, str(Path(__file__).resolve()), "--session", str(attempt), "--binary", str(binary),
                "--scales", *map(str, scales), "--themes", *themes]
        if names:
            args += ["--cases", *names]
        command(args, attempt / "session.log", timeout=1800)
        if source_inputs() != source or sha(binary) != report["binary_sha256"] or sha(build / "FacMan") != report["product_sha256"]:
            raise RuntimeError("Source or executable changed during gallery validation")
        report["rows"] = json.loads((attempt / "cells.json").read_text(encoding="utf-8"))
        report["assertions"] = sum(row["assertions"] for row in report["rows"])
        report["fixture_font_coverage"] = fixture_font_coverage(report["rows"])
        if font_inputs() != report["font_inputs"]:
            raise RuntimeError("Font inventory or bytes changed during gallery validation")
        if report["fixture_font_coverage"]["result"] != "pass":
            report["pending"].append("missing glyphs in the observed fixture font environment")
            if require_fixture_fonts:
                raise RuntimeError("Required fixture font coverage has missing glyphs; see retained cells")
        report["result"] = "pass"
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        receipt = attempt / "validation.json"
        receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"GTK gallery receipt: {receipt}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path)
    parser.add_argument("--cases", nargs="+", choices=tuple(control_gallery_fixtures.cases()), default=[])
    parser.add_argument("--scales", nargs="+", type=int, choices=SCALES, default=list(SCALES))
    parser.add_argument("--themes", nargs="+", choices=THEMES, default=list(THEMES))
    parser.add_argument("--require-fixture-glyph-coverage", action="store_true")
    parser.add_argument("--session", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--binary", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.session:
            task = owned_root(args.session.resolve().parents[2])
            if args.session.resolve().parent != task / "gtk-control-gallery/runs" or args.binary.resolve() != task / "gtk-build/facman-control-gallery":
                raise ValueError("Internal session must use the owned gallery attempt and executable")
            run_session(args.binary, args.session, args.cases, args.scales, args.themes)
        else:
            if args.task_root is None:
                parser.error("--task-root must name an existing owned task root")
            run(args.task_root, args.cases, args.scales, args.themes,
                require_fixture_fonts=args.require_fixture_glyph_coverage)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"GTK gallery: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
