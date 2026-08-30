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
    (
        "PresentationActionReceipt",
        "contracts/schema/presentation/presentation_action_receipt.v2.schema.json",
        "correlation_receipt",
    ),
    (
        "FrontendRequestContext",
        "contracts/schema/frontend/frontend_request_context.v1.schema.json",
        "effect_input",
    ),
    (
        "FrontendOperationInspectRequest",
        "contracts/schema/frontend/frontend_operation_inspect_request.v1.schema.json",
        "effect_input",
    ),
    (
        "FrontendOperationProjection",
        "contracts/schema/frontend/frontend_operation_projection.v1.schema.json",
        "read_projection",
    ),
    (
        "FrontendCancellationRequest",
        "contracts/schema/frontend/frontend_cancellation_request.v1.schema.json",
        "effect_input",
    ),
    (
        "FrontendCapabilitySnapshot",
        "contracts/schema/frontend/frontend_capability_snapshot.v1.schema.json",
        "read_projection",
    ),
    (
        "FrontendExecutionCorrelation",
        "contracts/schema/frontend/frontend_execution_correlation.v1.schema.json",
        "correlation_receipt",
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
    raw = schema.get("type")
    if raw is None and "const" in schema:
        raw = json_type(schema["const"])
    if raw is None and schema.get("enum"):
        raw = list(dict.fromkeys(json_type(value) for value in schema["enum"]))
    if raw is None:
        raw = "object"
    values = raw if isinstance(raw, list) else [raw]
    return [str(value) for value in values if value != "null"], "null" in values


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


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
        value = f"std::vector<{cpp_type(item)}>"
    else:
        value = "facman::core::json::Value"
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
        return f"IList<{csharp_type(item)}>"
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


def snake(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def cpp_string_checks(variable: str, schema: dict[str, Any]) -> list[str]:
    checks: list[str] = []
    if isinstance(schema.get("const"), str):
        checks.append(f'{variable} != {json.dumps(schema["const"])}')
    enum_values = [value for value in schema.get("enum", []) if isinstance(value, str)]
    if enum_values:
        checks.append(
            "(" + " && ".join(f'{variable} != {json.dumps(value)}' for value in enum_values) + ")"
        )
    if "minLength" in schema:
        checks.append(f"{variable}.size() < {int(schema['minLength'])}U")
    if "maxLength" in schema:
        checks.append(f"{variable}.size() > {int(schema['maxLength'])}U")
    pattern = schema.get("pattern")
    if pattern == "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$":
        checks.append(f"!detail::portable_identifier({variable})")
    elif pattern == "^[0-9a-f]{64}$":
        checks.append(f"!detail::sha256({variable})")
    return checks


def cpp_decode_scalar(
    lines: list[str],
    model_name: str,
    field_name: str,
    schema: dict[str, Any],
    field_var: str,
    indent: str,
) -> None:
    types, _nullable = schema_types(schema)
    primary = types[0] if types else "object"
    failure = (
        f'return facman::core::Result<{model_name}>::failure('
        f'detail::invalid("{field_name} has an invalid type or value"));'
    )
    local = f"decoded_{field_name}"
    if primary == "string":
        lines.append(f"{indent}if (!{field_var}->is_string()) {failure}")
        lines.append(f"{indent}auto {local}_result = {field_var}->string_value();")
        lines.append(f"{indent}if (!{local}_result) {failure}")
        lines.append(f"{indent}std::string {local} = {local}_result.take_value();")
        checks = cpp_string_checks(local, schema)
        if checks:
            lines.append(f"{indent}if ({' || '.join(checks)}) {failure}")
        lines.append(f"{indent}value.{field_name} = std::move({local});")
    elif primary == "integer":
        lines.append(f"{indent}auto {local}_result = {field_var}->signed_integer_value();")
        lines.append(f"{indent}if (!{local}_result) {failure}")
        lines.append(f"{indent}const std::int64_t {local} = {local}_result.value();")
        checks = []
        if isinstance(schema.get("const"), int):
            checks.append(f"{local} != {int(schema['const'])}")
        if "minimum" in schema:
            checks.append(f"{local} < {int(schema['minimum'])}")
        if "maximum" in schema:
            checks.append(f"{local} > {int(schema['maximum'])}")
        if checks:
            lines.append(f"{indent}if ({' || '.join(checks)}) {failure}")
        lines.append(f"{indent}value.{field_name} = {local};")
    elif primary == "boolean":
        lines.append(f"{indent}auto {local}_result = {field_var}->bool_value();")
        lines.append(f"{indent}if (!{local}_result) {failure}")
        if isinstance(schema.get("const"), bool):
            expected = "true" if schema["const"] else "false"
            lines.append(f"{indent}if ({local}_result.value() != {expected}) {failure}")
        lines.append(f"{indent}value.{field_name} = {local}_result.value();")
    elif primary == "array":
        item_schema = schema.get("items", {})
        item_types, _ = schema_types(item_schema)
        item_primary = item_types[0] if item_types else "object"
        lines.append(f"{indent}if (!{field_var}->is_array()) {failure}")
        if "minItems" in schema:
            lines.append(f"{indent}if ({field_var}->size() < {int(schema['minItems'])}U) {failure}")
        if "maxItems" in schema:
            lines.append(f"{indent}if ({field_var}->size() > {int(schema['maxItems'])}U) {failure}")
        lines.append(f"{indent}{cpp_type(schema)} {local};")
        lines.append(f"{indent}for (std::size_t index = 0; index < {field_var}->size(); ++index) {{")
        lines.append(f"{indent}    const auto* item = {field_var}->at(index);")
        if item_primary == "string":
            lines.append(f"{indent}    if (item == nullptr || !item->is_string()) {failure}")
            lines.append(f"{indent}    auto item_value = item->string_value();")
            lines.append(f"{indent}    if (!item_value) {failure}")
            lines.append(f"{indent}    std::string decoded_item = item_value.take_value();")
            item_checks = cpp_string_checks("decoded_item", item_schema)
            if item_checks:
                lines.append(f"{indent}    if ({' || '.join(item_checks)}) {failure}")
            if schema.get("uniqueItems"):
                lines.append(
                    f"{indent}    if (std::find({local}.begin(), {local}.end(), decoded_item) != {local}.end()) {failure}"
                )
            lines.append(f"{indent}    {local}.push_back(std::move(decoded_item));")
        elif item_primary == "integer":
            lines.append(f"{indent}    if (item == nullptr) {failure}")
            lines.append(f"{indent}    auto item_value = item->signed_integer_value();")
            lines.append(f"{indent}    if (!item_value) {failure}")
            if isinstance(item_schema.get("const"), int):
                lines.append(
                    f"{indent}    if (item_value.value() != {int(item_schema['const'])}) {failure}"
                )
            lines.append(f"{indent}    {local}.push_back(item_value.value());")
        elif item_primary == "boolean":
            lines.append(f"{indent}    if (item == nullptr) {failure}")
            lines.append(f"{indent}    auto item_value = item->bool_value();")
            lines.append(f"{indent}    if (!item_value) {failure}")
            lines.append(f"{indent}    {local}.push_back(item_value.value());")
        else:
            lines.append(f"{indent}    if (item == nullptr || !item->is_object()) {failure}")
            lines.append(f"{indent}    {local}.push_back(*item);")
        lines.append(f"{indent}}}")
        lines.append(f"{indent}value.{field_name} = std::move({local});")
    else:
        lines.append(f"{indent}if (!{field_var}->is_object()) {failure}")
        lines.append(f"{indent}value.{field_name} = *{field_var};")


def cpp_encode_value(
    lines: list[str],
    field_name: str,
    schema: dict[str, Any],
    expression: str,
    indent: str,
) -> None:
    types, _nullable = schema_types(schema)
    primary = types[0] if types else "object"
    if primary == "string":
        lines.append(f'{indent}output.add_string("{field_name}", {expression});')
    elif primary == "integer":
        lines.append(f'{indent}(void)output.add_signed_integer("{field_name}", {expression});')
    elif primary == "boolean":
        lines.append(f'{indent}output.add_bool("{field_name}", {expression});')
    elif primary == "object":
        lines.append(f'{indent}output.add_value("{field_name}", {expression});')
    else:
        item_types, _ = schema_types(schema.get("items", {}))
        item_primary = item_types[0] if item_types else "object"
        array_name = f"array_{field_name}"
        lines.append(f"{indent}facman::core::json::ArrayBuilder {array_name};")
        lines.append(f"{indent}for (const auto& item : {expression}) {{")
        if item_primary == "string":
            lines.append(f"{indent}    {array_name}.add_string(item);")
        elif item_primary == "integer":
            lines.append(f"{indent}    (void){array_name}.add_signed_integer(item);")
        elif item_primary == "boolean":
            lines.append(f"{indent}    {array_name}.add_bool(item);")
        else:
            lines.append(f"{indent}    {array_name}.add_value(item);")
        lines.append(f"{indent}}}")
        lines.append(f'{indent}output.add_array("{field_name}", {array_name});')


def render_cpp_helpers(bundle: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "namespace detail {",
        "inline facman::core::Error invalid(std::string message)",
        "{",
        "    return {\"generated_contract_invalid\", std::move(message), \"$\",",
        "        facman::core::OutcomeKind::invalid_argument};",
        "}",
        "inline bool portable_identifier(const std::string& value) noexcept",
        "{",
        "    if (value.empty() || value.size() > 128U) return false;",
        "    const auto alpha_numeric = [](unsigned char byte) {",
        "        return (byte >= 'A' && byte <= 'Z') || (byte >= 'a' && byte <= 'z') ||",
        "            (byte >= '0' && byte <= '9');",
        "    };",
        "    if (!alpha_numeric(static_cast<unsigned char>(value.front()))) return false;",
        "    for (const unsigned char byte : value) {",
        "        if (!alpha_numeric(byte) && byte != '.' && byte != '_' && byte != '-') return false;",
        "    }",
        "    return true;",
        "}",
        "inline bool sha256(const std::string& value) noexcept",
        "{",
        "    return value.size() == 64U && std::all_of(value.begin(), value.end(), [](char byte) {",
        "        return (byte >= '0' && byte <= '9') || (byte >= 'a' && byte <= 'f');",
        "    });",
        "}",
        "inline bool keys_allowed(const facman::core::json::Value& value,",
        "    std::initializer_list<const char*> names, bool extensions)",
        "{",
        "    for (const std::string& key : value.object_keys()) {",
        "        bool known = false;",
        "        for (const char* name : names) if (key == name) { known = true; break; }",
        "        if (!known && !(extensions && key.rfind(\"x-\", 0U) == 0U)) return false;",
        "    }",
        "    return true;",
        "}",
        "} // namespace detail",
    ]
    for contract in bundle["contracts"]:
        model = contract["model_name"]
        properties = ordered_properties(contract["schema"])
        lines.extend(["", f"inline std::string encode_json(const {model}& value)", "{"])
        lines.append("    facman::core::json::ObjectBuilder output;")
        for field_name, definition, required in properties:
            _types, nullable = schema_types(definition)
            optional = not required or nullable
            if optional:
                if required and nullable:
                    lines.append(f"    if (value.{field_name}) {{")
                    cpp_encode_value(lines, field_name, definition, f"*value.{field_name}", "        ")
                    lines.append("    } else {")
                    lines.append(f'        output.add_null("{field_name}");')
                    lines.append("    }")
                else:
                    lines.append(f"    if (value.{field_name}) {{")
                    cpp_encode_value(lines, field_name, definition, f"*value.{field_name}", "        ")
                    lines.append("    }")
            else:
                cpp_encode_value(lines, field_name, definition, f"value.{field_name}", "    ")
        lines.extend(["    return output.serialize();", "}"])

        decoder = f"decode_{snake(model)}"
        known = ", ".join(json.dumps(name) for name, _, _ in properties)
        allow_extensions = "true" if contract["behavior"] == "read_projection" else "false"
        lines.extend([
            "",
            f"inline facman::core::Result<{model}> {decoder}(const std::string& raw)",
            "{",
            "    auto document = facman::core::json::parse(raw);",
            "    if (!document || !document.value().is_object())",
            f"        return facman::core::Result<{model}>::failure(detail::invalid(\"contract is not an object\"));",
            f"    if (!detail::keys_allowed(document.value(), {{{known}}}, {allow_extensions}))",
            f"        return facman::core::Result<{model}>::failure(detail::invalid(\"contract contains an unknown field\"));",
            f"    {model} value;",
        ])
        for field_name, definition, required in properties:
            _types, nullable = schema_types(definition)
            field_var = f"field_{field_name}"
            lines.append(f'    const auto* {field_var} = document.value().find("{field_name}");')
            if required:
                lines.append(f"    if ({field_var} == nullptr)")
                lines.append(
                    f"        return facman::core::Result<{model}>::failure(detail::invalid(\"{field_name} is required\"));"
                )
            condition = f"{field_var} != nullptr"
            if nullable:
                lines.append(f"    if ({condition} && !{field_var}->is_null()) {{")
            else:
                lines.append(f"    if ({condition}) {{")
            cpp_decode_scalar(lines, model, field_name, definition, field_var, "        ")
            lines.append("    }")
        if contract["behavior"] == "read_projection":
            lines.append("    value.raw_canonical_json = document.value().serialize();")
        lines.extend([
            f"    return facman::core::Result<{model}>::success(std::move(value));",
            "}",
        ])
    return lines


def render_cpp(bundle: dict[str, Any]) -> str:
    lines = [
        "// SPDX-FileCopyrightText: 2026 Jules C",
        "// SPDX-License-Identifier: MIT",
        "// Generated by tools/codegen/generate_contracts.py; do not edit.",
        "#ifndef FACMAN_GENERATED_PRESENTATION_CONTRACTS_V1_H",
        "#define FACMAN_GENERATED_PRESENTATION_CONTRACTS_V1_H",
        "",
        '#include "fl_json.h"',
        "",
        "#include <algorithm>",
        "#include <cstdint>",
        "#include <initializer_list>",
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
            if not required and not value_type.startswith("std::optional<"):
                value_type = f"std::optional<{value_type}>"
            lines.append(f"    {value_type} {name};")
        if contract["behavior"] == "read_projection":
            lines.append("    std::string raw_canonical_json;")
        lines.append("};")
    lines.extend(render_cpp_helpers(bundle))
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
        if contract["behavior"] == "read_projection":
            lines.append("        public string RawCanonicalJson { get; set; }")
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
                optional_type = value_type if value_type.startswith("Optional[") else f"Optional[{value_type}]"
                lines.append(f"    {name}: {optional_type} = None")
        if contract["behavior"] == "read_projection":
            lines.append("    raw_canonical_json: str = \"\"")
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
