from __future__ import annotations

import hashlib
import os
import platform
import tomllib
from pathlib import Path
from typing import Any

from factorio_launcher.app.config import product_dir
from factorio_launcher.factorio.discovery.detect_version import detect_version
from factorio_launcher.factorio.install.install_ref import make_install_ref

EXECUTABLE_CANDIDATES = [
    "bin/x64/factorio.exe",
    "bin/x64/factorio",
    "Contents/MacOS/factorio",
    "bin/x64/factorio.exe.stub",
    "bin/x64/factorio.stub",
]


def stable_install_id(source: str, root: Path) -> str:
    digest = hashlib.sha1(str(root.resolve()).encode("utf-8")).hexdigest()[:8]
    name = slugify(root.stem or root.name or "factorio")
    return f"{slugify(source)}-{name}-{digest}"


def slugify(value: str) -> str:
    chars: list[str] = []
    last_dash = False
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
            last_dash = False
        elif not last_dash:
            chars.append("-")
            last_dash = True
    return "".join(chars).strip("-") or "item"


def find_executable(root: Path) -> Path | None:
    for candidate in EXECUTABLE_CANDIDATES:
        path = root / candidate
        if path.is_file():
            return path
    return None


def classify_platform(executable: Path | None) -> str:
    system = platform.system().lower() or "unknown"
    if executable and executable.name.endswith(".exe"):
        return "windows-x64"
    if executable and "Contents" in executable.parts:
        return "macos"
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows-x64"
    if system == "linux":
        return "linux-x64"
    return system


def infer_source_and_ownership(root: Path, requested_source: str | None) -> tuple[str, str]:
    if requested_source:
        source = requested_source
    else:
        normalized = str(root).lower()
        if "steamapps" in normalized:
            source = "steam"
        elif "headless" in normalized:
            source = "headless"
        else:
            source = "manual"

    if source == "steam":
        return source, "foreign"
    if source == "portable":
        return source, "portable"
    return source, "imported"


def inspect_install(root: Path, source: str | None = None, install_id: str | None = None) -> dict[str, Any]:
    root = root.expanduser().resolve()
    executable = find_executable(root)
    found_version = detect_version(root)
    source_value, ownership = infer_source_and_ownership(root, source)
    verification_status = "invalid"
    problems: list[str] = []

    if not root.exists():
        problems.append("install root does not exist")
    if executable is None:
        problems.append("Factorio executable was not found")
    else:
        verification_status = "structural"
    if found_version is None:
        problems.append("Factorio version was not found in data/base/info.json")

    capabilities = ["gui", "mods", "saves"]
    if source_value == "headless":
        capabilities = ["headless_server", "mods", "saves"]
    if executable and executable.name.endswith(".stub"):
        capabilities.append("fixture_stub")

    return make_install_ref(
        install_id=install_id or stable_install_id(source_value, root),
        source=source_value,
        ownership=ownership,
        version=found_version,
        channel=None,
        platform_name=classify_platform(executable),
        executable=str(executable) if executable else "",
        app_dir=str(root),
        capabilities=capabilities,
        verification={
            "status": verification_status,
            "managed_by_setup": False,
            "problems": problems,
        },
    )


def discovery_config(platform_name: str) -> dict[str, Any]:
    path = product_dir() / "discovery" / f"{platform_name}.toml"
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def expand_candidate(path_text: str) -> Path:
    expanded = os.path.expandvars(path_text)
    return Path(expanded).expanduser()


def scan_common_installs() -> list[dict[str, Any]]:
    system = platform.system().lower()
    platform_key = "macos" if system == "darwin" else system
    config = discovery_config(platform_key)
    roots = [expand_candidate(item) for item in config.get("candidate_roots", [])]

    env_home = os.environ.get("FACTORIO_HOME")
    if env_home:
        roots.append(Path(env_home).expanduser())

    found: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve() if root.exists() else root
        if resolved in seen or not root.exists():
            continue
        seen.add(resolved)
        install_ref = inspect_install(root)
        if install_ref["verification"]["status"] != "invalid":
            found.append(install_ref)
    return found

