# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Compile the first FacMan presentation contract family deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = (
    (
        "PresentationQuery",
        "contracts/schema/command/presentation.query.request.v1.schema.json",
        "effect_input",
    ),
    (
        "SemanticActionRequest",
        "contracts/schema/command/presentation.action.request.v1.schema.json",
        "effect_input",
    ),
    (
        "PresentationSnapshot",
        "contracts/schema/presentation/presentation_snapshot.v1.schema.json",
        "read_projection",
    ),
    (
        "SemanticActionResult",
        "contracts/schema/presentation/semantic_action_result.v1.schema.json",
        "read_projection",
    ),
)
OUTPUTS = {
    "bundle": ROOT / "contracts/generated-index/presentation_contracts.v1.bundle.json",
    "cpp": ROOT / "runtime/core/generated/presentation_contracts.v1.h",
    "csharp": ROOT / "apps/gui/windows/winforms/GeneratedPresentationContracts.cs",
    "python": ROOT / "tests/generated/presentation_contracts.py",
    "docs": ROOT / "docs/generated/contracts/presentation-foundation.md",
}


def encode(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def normalized_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def source_digest(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry["source_path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(entry["source_sha256"]))
        digest.update(b"\0")
    return digest.hexdigest()


def load_bundle() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for model_name, relative, behavior in CONTRACTS:
        path = ROOT / relative
        data = json.loads(path.read_text(encoding="utf-8"))
        entries.append(
            {
                "behavior": behavior,
                "model_name": model_name,
                "schema": data,
                "schema_id": data["$id"],
                "source_path": relative,
                "source_sha256": hashlib.sha256(normalized_bytes(path)).hexdigest(),
            }
        )
    entries.sort(key=lambda item: item["schema_id"])
    return {
        "schema": "facman.contract_bundle.v1",
        "family": "facman.presentation.foundation.v1",
        "compatibility_status": "advisory_not_public_stability_promise",
        "canonical_source": "json_schema_2020_12",
        "source_digest": source_digest(entries),
        "contracts": entries,
    }


def identifier(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def schema_types(schema: dict[str, Any]) -> tuple[list[str], bool]:
    raw = schema.get("type", "object")
    values = raw if isinstance(raw, list) else [raw]
    return [str(value) for value in values if value != "null"], "null" in values


def cpp_type(schema: dict[str, Any]) -> str:
    types, nullable = schema_types(schema)
    primary = types[0] if types else "object"
    if primary == "string":
        value = "std::string"
    elif primary == "integer":
        value = "std::int64_t"
    elif primary == "boolean":
        value = "bool"
    elif primary == "array":
        item = schema.get("items", {})
        value = f"std::vector<{cpp_type(item)}>" if item.get("type") != "object" else "std::string"
    else:
        value = "std::string"
    return f"std::optional<{value}>" if nullable else value


def csharp_type(schema: dict[str, Any]) -> str:
    types, _nullable = schema_types(schema)
    primary = types[0] if types else "object"
    if primary == "string":
        return "string"
    if primary == "integer":
        return "long"
    if primary == "boolean":
        return "bool"
    if primary == "array":
        item = schema.get("items", {})
        return f"IList<{csharp_type(item)}>" if item.get("type") != "object" else "IDictionary<string, object>"
    return "IDictionary<string, object>"


def python_type(schema: dict[str, Any]) -> str:
    types, nullable = schema_types(schema)
    primary = types[0] if types else "object"
    if primary == "string":
        value = "str"
    elif primary == "integer":
        value = "int"
    elif primary == "boolean":
        value = "bool"
    elif primary == "array":
        value = f"list[{python_type(schema.get('items', {}))}]"
    else:
        value = "dict[str, object]"
    return f"Optional[{value}]" if nullable else value


def ordered_properties(schema: dict[str, Any]) -> list[tuple[str, dict[str, Any], bool]]:
    required = set(schema.get("required", []))
    values = [
        (name, definition, name in required)
        for name, definition in sorted(schema.get("properties", {}).items())
    ]
    return sorted(values, key=lambda item: (not item[2], item[0]))


def render_cpp(bundle: dict[str, Any]) -> str:
    lines = [
        "// SPDX-FileCopyrightText: 2026 Jules C",
        "// SPDX-License-Identifier: MIT",
        "// Generated by tools/codegen/generate_contracts.py; do not edit.",
        "#ifndef FACMAN_GENERATED_PRESENTATION_CONTRACTS_V1_H",
        "#define FACMAN_GENERATED_PRESENTATION_CONTRACTS_V1_H",
        "",
        "#include <cstdint>",
        "#include <optional>",
        "#include <string>",
        "#include <vector>",
        "",
        "namespace facman::contracts::presentation_v1 {",
        f'inline constexpr const char* kSourceDigest = "{bundle["source_digest"]}";',
    ]
    for contract in bundle["contracts"]:
        lines.extend(["", f"struct {contract['model_name']} {{"])
        for name, definition, required in ordered_properties(contract["schema"]):
            value_type = cpp_type(definition)
            if not required:
                value_type = f"std::optional<{value_type}>"
            lines.append(f"    {value_type} {name};")
        lines.append("};")
    lines.extend(["", "} // namespace facman::contracts::presentation_v1", "", "#endif", ""])
    return "\n".join(lines)


def render_csharp(bundle: dict[str, Any]) -> str:
    lines = [
        "// SPDX-FileCopyrightText: 2026 Jules C",
        "// SPDX-License-Identifier: MIT",
        "// Generated by tools/codegen/generate_contracts.py; do not edit.",
        "using System.Collections.Generic;",
        "",
        "namespace FacMan.WinForms.GeneratedContracts",
        "{",
        "    public static class PresentationContractIdentity",
        "    {",
        f'        public const string SourceDigest = "{bundle["source_digest"]}";',
        "    }",
    ]
    for contract in bundle["contracts"]:
        lines.extend(["", f"    public sealed class {contract['model_name']}", "    {"])
        for name, definition, _required in ordered_properties(contract["schema"]):
            lines.append(
                f"        public {csharp_type(definition)} {identifier(name)} {{ get; set; }}"
            )
        lines.append("    }")
    lines.extend(["}", ""])
    return "\n".join(lines)


def render_python(bundle: dict[str, Any]) -> str:
    lines = [
        "# SPDX-FileCopyrightText: 2026 Jules C",
        "# SPDX-License-Identifier: MIT",
        "# Generated by tools/codegen/generate_contracts.py; do not edit.",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "from typing import Optional",
        "",
        f'SOURCE_DIGEST = "{bundle["source_digest"]}"',
    ]
    for contract in bundle["contracts"]:
        lines.extend(["", "@dataclass", f"class {contract['model_name']}:"])
        properties = ordered_properties(contract["schema"])
        if not properties:
            lines.append("    pass")
            continue
        for name, definition, required in properties:
            value_type = python_type(definition)
            if required:
                lines.append(f"    {name}: {value_type}")
            else:
                lines.append(f"    {name}: Optional[{value_type}] = None")
    lines.append("")
    return "\n".join(lines)


def render_docs(bundle: dict[str, Any]) -> str:
    rows = [
        "# Generated presentation contract index",
        "",
        "Generated by `tools/codegen/generate_contracts.py` from existing JSON Schema 2020-12 sources.",
        "The compatibility report is advisory; this foundation makes no public SDK stability claim.",
        "",
        f"Source digest: `{bundle['source_digest']}`",
        "",
        "| Model | Behavior | Canonical schema |",
        "| --- | --- | --- |",
    ]
    rows.extend(
        f"| `{item['model_name']}` | `{item['behavior']}` | `{item['source_path']}` |"
        for item in bundle["contracts"]
    )
    rows.extend(
        [
            "",
            "Effect-bearing inputs are closed to unknown fields. Read projections may carry only explicitly namespaced `x-*` extensions where their canonical schema allows them.",
            "",
        ]
    )
    return "\n".join(rows)


def render() -> dict[Path, str]:
    bundle = load_bundle()
    return {
        OUTPUTS["bundle"]: encode(bundle),
        OUTPUTS["cpp"]: render_cpp(bundle),
        OUTPUTS["csharp"]: render_csharp(bundle),
        OUTPUTS["python"]: render_python(bundle),
        OUTPUTS["docs"]: render_docs(bundle),
    }


def generate(write: bool) -> list[str]:
    problems: list[str] = []
    for path, expected in render().items():
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
        elif not path.is_file():
            problems.append(f"missing generated output: {path.relative_to(ROOT).as_posix()}")
        elif path.read_text(encoding="utf-8") != expected:
            problems.append(f"stale generated output: {path.relative_to(ROOT).as_posix()}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    problems = generate(write=not args.check)
    if problems:
        for problem in problems:
            print(f"contract-compiler: {problem}", file=sys.stderr)
        return 1
    print("contract-compiler: deterministic outputs are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
