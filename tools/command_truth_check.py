# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import architecture_fitness


def universal_launcher_root() -> Path | None:
    candidates = []
    configured = os.environ.get("FLAUNCH_UNIVERSAL_LAUNCHER_ROOT")
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            ROOT.parent / "universal-launcher",
            ROOT.parents[1] / "Universal" / "universal-launcher",
        ]
    )
    return next((path for path in candidates if (path / "runtime/launcher/kernel/ulk_api.c").is_file()), None)


def detect_registry_capacity() -> set[str]:
    launcher = universal_launcher_root()
    if launcher is None:
        return {"universal-launcher:source-unavailable"}
    source = (launcher / "runtime/launcher/kernel/ulk_api.c").read_text(encoding="utf-8")
    return {"universal-launcher:fixed-command-capacity"} if "ULK_MAX_REGISTERED_COMMANDS" in source else set()


def detect_availability_parity() -> set[str]:
    violations: set[str] = set()
    binding = (ROOT / "runtime/factorio/binding/flb_api.c").read_text(encoding="utf-8")
    header = (ROOT / "runtime/core/generated/command_catalog.h").read_text(encoding="utf-8")
    if 'static const char availability[] = "available"' in binding:
        violations.add("runtime/factorio/binding/flb_api.c:hardcoded-availability")
    if "const char* availability;" not in header:
        violations.add("runtime/core/generated/command_catalog.h:availability-omitted")

    with (ROOT / "contracts/generated-index/command_catalog.v2.json").open(encoding="utf-8") as handle:
        generated = json.load(handle)
    for item in generated.get("commands", []):
        availability = str(item.get("availability", "implemented"))
        if item.get("runtime_id") == "run.execute" and availability != "unavailable_until_isolation_proof":
            violations.add("run.execute:availability-mismatch")
    return violations


def detect_generic_operations() -> set[str]:
    with (ROOT / "contracts/command/factorio/index.v1.toml").open("rb") as handle:
        index = tomllib.load(handle)
    registered = set(index.get("registered", []))
    return registered & {"setup.operation", "utility.operation"}


def detect_setup_provider_boundary() -> set[str]:
    violations: set[str] = set()
    handlers = ROOT / "runtime/factorio/application/handlers"
    for path in sorted(handlers.glob("*.cpp")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "usk/usk_api.h" in text or "usk_command_execute_v1" in text:
            violations.add(architecture_fitness.relative(path))
    return violations


def detect_command_catalog_v2() -> set[str]:
    violations: set[str] = set()
    catalog_path = ROOT / "contracts/generated-index/command_catalog.v2.json"
    if not catalog_path.is_file():
        return {"contracts/generated-index/command_catalog.v2.json:missing"}
    generated = json.loads(catalog_path.read_text(encoding="utf-8"))
    if generated.get("schema") != "facman.generated_command_catalog.v2":
        violations.add("contracts/generated-index/command_catalog.v2.json:schema")
    for item in generated.get("commands", []):
        runtime_id = str(item.get("runtime_id", "missing"))
        if not isinstance(item.get("native_id"), str) or not item.get("native_id"):
            violations.add(f"{runtime_id}:native-id-missing")
        if not isinstance(item.get("aliases"), list):
            violations.add(f"{runtime_id}:aliases-missing")
        if not isinstance(item.get("writes_state"), bool):
            violations.add(f"{runtime_id}:writes-state-missing")
    application_types = (ROOT / "runtime/factorio/application/application_types.h").read_text(encoding="utf-8")
    dispatch = (ROOT / "runtime/factorio/application/command_dispatch.cpp").read_text(encoding="utf-8")
    if '#include "generated/command_ids.inc"' not in application_types:
        violations.add("runtime/factorio/application/application_types.h:manual-command-ids")
    for name in ("command_lookup.inc", "command_names.inc", "command_writes.inc"):
        if f'#include "generated/{name}"' not in dispatch:
            violations.add(f"runtime/factorio/application/command_dispatch.cpp:missing-{name}")
    if 'value == "product.inspect"' in dispatch:
        violations.add("runtime/factorio/application/command_dispatch.cpp:manual-command-lookup")
    if "command == CommandId::install_import" in dispatch:
        violations.add("runtime/factorio/application/command_dispatch.cpp:manual-write-policy")
    return violations


def main() -> int:
    statuses = [
        architecture_fitness.run("registry_capacity", detect_registry_capacity),
        architecture_fitness.run("availability_parity", detect_availability_parity),
        architecture_fitness.run("generic_operation", detect_generic_operations),
        architecture_fitness.run("setup_provider_boundary", detect_setup_provider_boundary),
        architecture_fitness.run("command_catalog_v2", detect_command_catalog_v2),
    ]
    return 1 if any(status != 0 for status in statuses) else 0


if __name__ == "__main__":
    raise SystemExit(main())
