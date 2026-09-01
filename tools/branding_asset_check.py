# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "content/factorio/ui/branding/provenance/branding-asset-manifest.v1.json"
SOURCE_DIGEST = "5001177903f03342630db1adced28a0ebc7dd03f16ffe791f1921cfdbeed6ed8"
SOURCE_CANDIDATES = {
    "FacMan.png": (SOURCE_DIGEST, "selected_provisional_master"),
    "FacMan.ico": (
        "772e23951eef431bb7de936ae17ff6d2d7aafbd9bd5d3de05778d1186b35dfa1",
        "supplied_derivative_reference",
    ),
    "FacMan.favicons.zip": (
        "da3de5d5aebf079df744296d26dc6ec99838ffdfae69d0e335f9c6ed67a00ff8",
        "supplied_derivative_reference",
    ),
}
LINUX_SIZES = (16, 24, 32, 48, 64, 96, 128, 192, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 72, 96, 128, 256)
ICNS_TYPES = {
    b"icp4": 16,
    b"icp5": 32,
    b"icp6": 64,
    b"ic07": 128,
    b"ic08": 256,
    b"ic09": 512,
    b"ic10": 1024,
}


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_manifest() -> dict[str, Any]:
    raw = MANIFEST.read_bytes()
    if len(raw) > 64 * 1024:
        raise ValueError("branding manifest exceeds 64 KiB")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    if not isinstance(data, dict):
        raise ValueError("branding manifest must be an object")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_path(relative: str) -> Path:
    if not relative or "\\" in relative:
        raise ValueError(f"asset path must use a non-empty portable path: {relative!r}")
    candidate = ROOT.joinpath(*relative.split("/"))
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(ROOT.resolve()) or candidate.is_symlink():
        raise ValueError(f"asset path escapes custody or is a link: {relative}")
    if not resolved.is_file():
        raise ValueError(f"asset is not a regular file: {relative}")
    if resolved.stat().st_size > 8 * 1024 * 1024:
        raise ValueError(f"asset exceeds the 8 MiB budget: {relative}")
    return resolved


def png_dimensions(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG signature is absent")
    position = 8
    dimensions: tuple[int, int] | None = None
    saw_end = False
    while position < len(data):
        if position + 12 > len(data):
            raise ValueError("PNG chunk header is truncated")
        length = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4 : position + 8]
        end = position + 12 + length
        if length > 8 * 1024 * 1024 or end > len(data):
            raise ValueError("PNG chunk is unbounded or truncated")
        payload = data[position + 8 : position + 8 + length]
        expected_crc = struct.unpack_from(">I", data, position + 8 + length)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
            raise ValueError(f"PNG {kind!r} chunk CRC differs")
        if position == 8:
            if kind != b"IHDR" or length != 13:
                raise ValueError("PNG does not begin with a canonical IHDR")
            width, height = struct.unpack_from(">II", payload)
            dimensions = (width, height)
            if payload[8] != 8 or payload[9] != 6:
                raise ValueError("PNG must be 8-bit RGBA")
        if kind == b"IEND":
            if length != 0 or end != len(data):
                raise ValueError("PNG IEND is malformed or has trailing bytes")
            saw_end = True
        position = end
    if dimensions is None or not saw_end:
        raise ValueError("PNG has no complete IHDR/IEND envelope")
    return dimensions


def ico_sizes(data: bytes) -> tuple[int, ...]:
    if len(data) < 6 or struct.unpack_from("<HH", data) != (0, 1):
        raise ValueError("ICO header is invalid")
    count = struct.unpack_from("<H", data, 4)[0]
    if count != len(ICO_SIZES) or len(data) < 6 + count * 16:
        raise ValueError("ICO directory count differs from the reviewed set")
    observed: list[int] = []
    directory_end = 6 + count * 16
    for index in range(count):
        offset = 6 + index * 16
        width_byte, height_byte, colors, reserved, planes, bits, size, payload_offset = struct.unpack_from(
            "<BBBBHHII", data, offset
        )
        width = width_byte or 256
        height = height_byte or 256
        if width != height or colors != 0 or reserved != 0 or planes != 1 or bits != 32:
            raise ValueError(f"ICO directory entry {index} is not canonical 32-bit square RGBA")
        if payload_offset < directory_end or payload_offset + size > len(data):
            raise ValueError(f"ICO directory entry {index} is out of bounds")
        if png_dimensions(data[payload_offset : payload_offset + size]) != (width, height):
            raise ValueError(f"ICO directory entry {index} disagrees with its PNG payload")
        observed.append(width)
    if len(set(observed)) != len(observed):
        raise ValueError("ICO contains duplicate pixel sizes")
    return tuple(observed)


def icns_sizes(data: bytes) -> tuple[int, ...]:
    if len(data) < 8 or data[:4] != b"icns" or struct.unpack_from(">I", data, 4)[0] != len(data):
        raise ValueError("ICNS envelope length is invalid")
    observed: list[int] = []
    seen: set[bytes] = set()
    position = 8
    while position < len(data):
        if position + 8 > len(data):
            raise ValueError("ICNS entry header is truncated")
        kind = data[position : position + 4]
        length = struct.unpack_from(">I", data, position + 4)[0]
        if kind not in ICNS_TYPES or kind in seen or length < 8 or position + length > len(data):
            raise ValueError(f"ICNS entry is unknown, duplicate, or out of bounds: {kind!r}")
        size = ICNS_TYPES[kind]
        if png_dimensions(data[position + 8 : position + length]) != (size, size):
            raise ValueError(f"ICNS entry {kind!r} disagrees with its PNG payload")
        observed.append(size)
        seen.add(kind)
        position += length
    if position != len(data) or seen != set(ICNS_TYPES):
        raise ValueError("ICNS entry set differs from the reviewed modern icon set")
    return tuple(observed)


def expected_output_specs() -> dict[str, tuple[str, tuple[int, ...]]]:
    specs = {
        "apps/gui/windows/winforms/branding/FacMan.ico": ("image/vnd.microsoft.icon", ICO_SIZES),
        "apps/gui/macos/appkit/branding/FacMan.icns": ("image/icns", tuple(ICNS_TYPES.values())),
        "content/factorio/ui/branding/review/contact-sheet.png": ("image/png", (1280, 720)),
    }
    for size in LINUX_SIZES:
        path = f"apps/gui/linux/gtk/icons/hicolor/{size}x{size}/apps/io.github.julesc013.facman.png"
        specs[path] = ("image/png", (size,))
    return specs


def check_manifest(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if manifest.get("schema") != "facman.branding_asset_manifest.v1":
        problems.append("manifest schema differs")
    if manifest.get("status") != "provisional_human_review_required":
        problems.append("manifest must remain provisional and human-review-bound")
    source = manifest.get("source")
    if not isinstance(source, dict) or source != {
        "path": "content/factorio/ui/branding/master/facman-provisional.png",
        "sha256": SOURCE_DIGEST,
        "width": 1254,
        "height": 1254,
        "custody": "operator_supplied_local_inbox",
        "official_brand_asset": False,
    }:
        problems.append("source custody differs from the reviewed provisional master")
    else:
        try:
            source_path = checked_path(source["path"])
            if sha256(source_path) != SOURCE_DIGEST or png_dimensions(source_path.read_bytes()) != (1254, 1254):
                problems.append("source bytes or dimensions differ")
        except (OSError, ValueError) as error:
            problems.append(f"source validation failed: {error}")

    candidates = manifest.get("source_candidates")
    observed_candidates = {
        item.get("name"): (item.get("sha256"), item.get("disposition"))
        for item in candidates
        if isinstance(candidates, list) and isinstance(item, dict)
    } if isinstance(candidates, list) else {}
    if observed_candidates != SOURCE_CANDIDATES or len(candidates or []) != 3:
        problems.append("source candidate custody differs")

    if manifest.get("generation") != {
        "tool": "tools/generate_branding_assets.ps1",
        "algorithm": "system_drawing_high_quality_bicubic_v1",
        "deterministic": True,
    }:
        problems.append("generation contract differs")

    expected = expected_output_specs()
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        problems.append("outputs are absent")
        outputs = []
    observed_paths = [item.get("path") for item in outputs if isinstance(item, dict)]
    if len(observed_paths) != len(set(observed_paths)):
        problems.append("outputs contain duplicate paths")
    if set(observed_paths) != set(expected):
        problems.append("output path set differs from platform branding contract")
    for item in outputs:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            problems.append("output entry is malformed")
            continue
        relative = item["path"]
        specification = expected.get(relative)
        if specification is None:
            continue
        media_type, sizes = specification
        if item.get("media_type") != media_type or tuple(item.get("pixel_sizes", ())) != sizes:
            problems.append(f"output metadata differs: {relative}")
        try:
            path = checked_path(relative)
            if sha256(path) != item.get("sha256"):
                problems.append(f"output digest differs: {relative}")
            data = path.read_bytes()
            if media_type == "image/png":
                expected_dimensions = sizes if len(sizes) == 2 else (sizes[0], sizes[0])
                if png_dimensions(data) != expected_dimensions:
                    problems.append(f"PNG dimensions differ: {relative}")
            elif media_type == "image/vnd.microsoft.icon" and ico_sizes(data) != ICO_SIZES:
                problems.append("ICO size set differs")
            elif media_type == "image/icns" and icns_sizes(data) != tuple(ICNS_TYPES.values()):
                problems.append("ICNS size set differs")
        except (OSError, ValueError) as error:
            problems.append(f"output validation failed for {relative}: {error}")

    if set(manifest.get("human_review_required", ())) != {
        "small_size_optical_correction",
        "public_brand_and_trademark_judgment",
        "high_contrast_and_dpi_experience",
    }:
        problems.append("human review boundary differs")
    if set(manifest.get("authority_exclusions", ())) != {
        "official_factorio_or_wube_branding",
        "production_signing",
        "public_release_or_support_activation",
    }:
        problems.append("authority exclusions differ")
    return problems


def check_platform_wiring() -> list[str]:
    problems: list[str] = []
    winforms_project = (ROOT / "apps/gui/windows/winforms/FacMan.WinForms.csproj").read_text(encoding="utf-8")
    winforms_shell = (ROOT / "apps/gui/windows/winforms/C1ShellForm.cs").read_text(encoding="utf-8")
    for marker in (
        "<ApplicationIcon>branding\\FacMan.ico</ApplicationIcon>",
        "System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath)",
        "provisional FacMan gear mark",
    ):
        if marker not in winforms_project + winforms_shell:
            problems.append(f"WinForms branding wiring is absent: {marker}")

    appkit_cmake = (ROOT / "apps/gui/macos/appkit/CMakeLists.txt").read_text(encoding="utf-8")
    appkit_plist = (ROOT / "apps/gui/macos/appkit/Info.plist").read_text(encoding="utf-8")
    for marker in ("FacMan.icns", "MACOSX_PACKAGE_LOCATION \"Resources\"", "CFBundleIconFile"):
        if marker not in appkit_cmake + appkit_plist:
            problems.append(f"AppKit branding wiring is absent: {marker}")

    gtk_meson = (ROOT / "apps/gui/linux/gtk/meson.build").read_text(encoding="utf-8")
    gtk_desktop = (ROOT / "apps/gui/linux/gtk/io.github.julesc013.facman.desktop").read_text(
        encoding="utf-8"
    )
    gtk_main = (ROOT / "apps/gui/linux/gtk/main.c").read_text(encoding="utf-8")
    for marker in (
        "branding_icon_sizes",
        "Icon=io.github.julesc013.facman",
        "io.github.julesc013.facman.png",
        "gtk_window_set_icon_name(GTK_WINDOW(shell->window), FACMAN_GUI_APPLICATION_ID)",
    ):
        if marker not in gtk_meson + gtk_desktop + gtk_main:
            problems.append(f"GTK branding wiring is absent: {marker}")
    package_proof = (ROOT / "tools/classic_preview_package_proof.py").read_text(encoding="utf-8")
    for marker in (
        "AppKit bundle is missing its exact FacMan.icns resource",
        "GTK package is missing the FacMan desktop icon binding",
        "GTK package is missing the {size}px FacMan hicolor icon",
    ):
        if marker not in package_proof:
            problems.append(f"classic preview package proof omits branding custody: {marker}")
    return problems


def main() -> int:
    problems: list[str] = []
    try:
        problems.extend(check_manifest(load_manifest()))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        problems.append(f"manifest validation failed: {error}")
    problems.extend(check_platform_wiring())
    if problems:
        for problem in problems:
            print(f"branding-asset-check: {problem}", file=sys.stderr)
        return 1
    print("branding-asset-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
