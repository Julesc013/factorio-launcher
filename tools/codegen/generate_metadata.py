# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INDEX = ROOT / "contracts/command/factorio/index.v1.toml"
VERSION = ROOT / "release/index/version.v1.toml"
FRONTEND = ROOT / "contracts/command/frontend/frontend.required_commands.v1.toml"

OUTPUTS = {
    "catalog_json": ROOT / "contracts/generated-index/command_catalog.v2.json",
    "command_header": ROOT / "runtime/core/generated/command_catalog.h",
    "version_header": ROOT / "runtime/core/generated/version.h",
    "help_include": ROOT / "apps/cli/generated/command_help.inc",
    "bash": ROOT / "apps/cli/completions/facman.bash",
    "zsh": ROOT / "apps/cli/completions/_facman",
    "fish": ROOT / "apps/cli/completions/facman.fish",
    "powershell": ROOT / "apps/cli/completions/FacMan.ps1",
    "docs": ROOT / "docs/reference/generated-command-catalog.md",
    "application_ids": ROOT / "runtime/factorio/application/generated/command_ids.inc",
    "application_lookup": ROOT / "runtime/factorio/application/generated/command_lookup.inc",
    "application_names": ROOT / "runtime/factorio/application/generated/command_names.inc",
    "application_writes": ROOT / "runtime/factorio/application/generated/command_writes.inc",
    "grammar_json": ROOT / "contracts/generated-index/command_cli_grammar.v2.json",
    "frontend_json": ROOT / "contracts/generated-index/frontend_command_catalog.v1.json",
}

REQUEST_FIELDS: dict[str, list[tuple[str, str, bool]]] = {
    "onboarding.plan": [("preferred_install", "identifier", False), ("instance_display_name", "string", False), ("template_id", "identifier", False), ("workspace", "path", False)],
    "launch_plan.explain": [("instance_id", "identifier", True)],
    "modsets.explain": [("instance_id", "identifier", True)],
    "doctor.run": [("roots", "string_array", False)],
    "install_refs.scan": [("roots", "string_array", False)],
    "install_refs.import": [("path", "path", True), ("install_id", "identifier", True)],
    "install_refs.inspect": [("install_id", "identifier", True)],
    "instance.create": [("display_name", "string", True), ("instance_id", "identifier", True), ("install_id", "identifier", True), ("template_id", "identifier", False)],
    "launch_plan.build": [("instance_id", "identifier", True)],
    "launch_plan.preflight": [("instance_id", "identifier", True)],
    "run.preview": [("instance_id", "identifier", True)],
    "run.execute": [("instance_id", "identifier", False)],
    "mods.import": [("source_path", "path", True), ("instance_id", "identifier", True)],
    "modsets.lock": [("instance_id", "identifier", True)],
    "modsets.verify": [("instance_id", "identifier", True)],
    "modsets.export": [("instance_id", "identifier", True), ("output_path", "path", True)],
    "saves.list": [("instance_id", "identifier", True)],
    "saves.backup": [("instance_id", "identifier", True), ("save", "string", True), ("output_path", "path", False)],
    "saves.clone": [("source_instance_id", "identifier", True), ("target_instance_id", "identifier", True), ("save", "string", True)],
    "instance.export": [("instance_id", "identifier", True), ("output_path", "path", True)],
    "instance.import": [("source_path", "path", True), ("instance_id", "identifier", False)],
    "diagnostics.export": [("instance_id", "identifier", True), ("output_path", "path", True)],
    "workspace.recovery.plan": [("transaction_id", "identifier", True)],
    "workspace.recovery.apply": [("transaction_id", "identifier", True)],
    "package.verify": [("path", "path", False)],
    "installs.install_version": [("version", "string", True), ("archive", "path", False)],
    "installs.verify": [("id", "identifier", True)],
    "installs.repair": [("id", "identifier", True)],
    "installs.uninstall": [("id", "identifier", True)],
    "mods.search": [("query", "string", False)],
    "mods.install": [("query", "string", False), ("instance_id", "identifier", False)],
    "mods.update": [("instance_id", "identifier", False)],
    "servers.create": [("name", "string", True), ("id", "identifier", False), ("instance_id", "identifier", True)],
    "servers.start": [("id", "identifier", True)],
    "servers.stop": [("id", "identifier", True)],
    "servers.rcon": [("id", "identifier", True)],
    "diagnostics.redact": [("path", "path", True)],
    "setup.operation": [
        ("operation", "string", True), ("name", "string", False), ("id", "identifier", False),
        ("instance_id", "identifier", False), ("path", "path", False), ("query", "string", False),
        ("version", "string", False), ("archive", "path", False),
    ],
    "utility.operation": [
        ("operation", "string", True), ("name", "string", False), ("id", "identifier", False),
        ("instance_id", "identifier", False), ("path", "path", False), ("query", "string", False),
        ("version", "string", False), ("archive", "path", False),
    ],
}

APPLICATION_ID_OVERRIDES = {
    "factorio.product.inspect": "product_inspect",
    "install_refs.list": "install_list",
    "install_refs.scan": "install_scan",
    "install_refs.import": "install_import",
    "install_refs.inspect": "install_inspect",
    "setup.operation": "legacy_setup_operation",
    "utility.operation": "legacy_utility_operation",
    "workspace.recovery.inspect": "recovery_inspect",
    "workspace.recovery.plan": "recovery_plan",
    "workspace.recovery.apply": "recovery_apply",
    "workspace.migration.inspect": "migration_inspect",
    "workspace.migration.plan": "migration_plan",
    "workspace.migration.apply": "migration_apply",
}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def digest_source(digest: Any, path: Path) -> None:
    digest.update(path.relative_to(ROOT).as_posix().encode())
    digest.update(b"\0")
    digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    digest.update(b"\0")


def load_sources() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], str]:
    index = load_toml(INDEX)
    version = load_toml(VERSION)
    if index.get("schema") != "facman.command_catalog_index.v1":
        raise ValueError("command catalog index has the wrong schema")
    if version.get("schema") != "facman.version.v1":
        raise ValueError("version index has the wrong schema")
    files = index.get("files", [])
    if not isinstance(files, list) or len(files) != len(set(files)):
        raise ValueError("command catalog files must be a unique array")
    runtime_ids = index.get("runtime_ids", {})
    registered = set(index.get("registered", []))
    commands: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for path in [Path(__file__).resolve(), INDEX, VERSION, FRONTEND]:
        digest_source(digest, path)
    for name in files:
        path = INDEX.parent / str(name)
        if not path.is_file():
            raise ValueError(f"indexed command contract does not exist: {path.relative_to(ROOT)}")
        data = load_toml(path)
        command_id = str(data.get("command_id", ""))
        if not command_id:
            raise ValueError(f"{path.relative_to(ROOT)} has no command_id")
        runtime_id = str(runtime_ids.get(command_id, command_id))
        item = dict(data)
        item["contract_path"] = path.relative_to(ROOT).as_posix()
        item["runtime_id"] = runtime_id
        item["registered"] = runtime_id in registered
        commands.append(item)
        digest_source(digest, path)
    ids = [str(item["command_id"]) for item in commands]
    runtime = [str(item["runtime_id"]) for item in commands]
    if len(ids) != len(set(ids)) or len(runtime) != len(set(runtime)):
        raise ValueError("command and runtime IDs must be unique")
    if registered - set(runtime):
        raise ValueError(f"registered runtime IDs are missing contracts: {sorted(registered - set(runtime))}")
    commands.sort(key=lambda item: str(item["command_id"]))
    return index, version, commands, digest.hexdigest()


def c_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", value).upper()


def application_identifier(runtime_id: str) -> str:
    return APPLICATION_ID_OVERRIDES.get(runtime_id, re.sub(r"[^A-Za-z0-9]", "_", runtime_id).lower())


def runtime_aliases(runtime_id: str) -> list[str]:
    aliases: list[str] = []
    if "_" in runtime_id:
        aliases.append(runtime_id.replace("_", "-"))
    return aliases


def request_schema_path(runtime_id: str) -> str:
    return f"contracts/schema/command/{runtime_id}.request.v1.schema.json"


def request_schema(runtime_id: str) -> str:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, kind, is_required in REQUEST_FIELDS.get(runtime_id, []):
        if kind == "string_array":
            properties[name] = {"type": "array", "items": {"type": "string"}, "maxItems": 256}
        else:
            properties[name] = {"type": "string"}
            if kind == "identifier":
                properties[name]["pattern"] = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
            if is_required:
                properties[name]["minLength"] = 1
        if is_required:
            required.append(name)
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://facman.invalid/schema/command/{runtime_id}.request.v1.schema.json",
        "title": f"{runtime_id} request",
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def cli_grammar(item: dict[str, Any]) -> dict[str, Any]:
    usage = str(item.get("cli", ""))
    runtime_id = str(item["runtime_id"])
    if not usage.startswith("facman "):
        return {"path": [], "positionals": [], "options": [], "usage": usage, "internal": True}
    tokens = shlex.split(usage)[1:]
    path: list[str] = []
    positionals: list[dict[str, Any]] = []
    options: list[dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("<") and token.endswith(">"):
            positionals.append({"name": token[1:-1], "required": True})
        elif token.startswith("--"):
            value = None
            if index + 1 < len(tokens) and tokens[index + 1].startswith("<"):
                value = tokens[index + 1][1:-1]
                index += 1
            options.append({"name": token, "value": value, "repeatable": False})
        elif not positionals and not options:
            path.append(token)
        index += 1
    return {"path": path, "positionals": positionals, "options": options, "usage": usage, "internal": False}


def refusal_code(item: dict[str, Any]) -> str:
    path = ROOT / str(item.get("golden_refusal", ""))
    if not path.is_file():
        return ""
    try:
        refusal = json.loads(path.read_text(encoding="utf-8")).get("refusal", {})
        return str(refusal.get("code", "")) if isinstance(refusal, dict) else ""
    except (OSError, json.JSONDecodeError):
        return ""


def descriptor_metadata(index: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    runtime_id = str(item["runtime_id"])
    effects = [str(value) for value in item.get("effects", [])]
    writes = "workspace_write" in effects
    executes = "process_execute" in effects
    deprecated = runtime_id in {"setup.operation", "utility.operation"}
    grammar = cli_grammar(item)
    return {
        "schema": "facman.command.v2",
        "owner": str(index["owner"]),
        "binding": str(index["binding"]),
        "visibility": "internal_compatibility" if deprecated or grammar["internal"] else "public",
        "deprecation": "deprecated_compatibility" if deprecated else "active",
        "availability_refusal_code": refusal_code(item) if runtime_availability(item) != "available" else "",
        "required_capabilities": effects,
        "risk_tier": "process_execution" if executes else "persistent_local_write" if writes else "read_only",
        "renderer": application_identifier(runtime_id),
        "frontend_category": runtime_id.split(".", 1)[0],
        "localization_keys": [f"command.{runtime_id}.title", f"command.{runtime_id}.description"],
        "request_fields": [
            {"name": name, "type": kind, "required": required}
            for name, kind, required in REQUEST_FIELDS.get(runtime_id, [])
        ],
        "cli_grammar": grammar,
    }


def c_string(value: str) -> str:
    return json.dumps(value)


def dry_run_behavior(item: dict[str, Any]) -> str:
    runtime_id = str(item["runtime_id"])
    effects = set(str(value) for value in item.get("effects", []))
    if runtime_id == "launch_plan.build":
        return "preview_only"
    if runtime_id == "launch_plan.preflight":
        return "read_only_no_process"
    if runtime_id == "run.preview":
        return "preview_only_no_process"
    if "workspace_write" in effects:
        return "explicit_persistent_write"
    return "read_only"


def runtime_availability(item: dict[str, Any]) -> str:
    availability = str(item.get("availability", "implemented"))
    return "available" if availability == "implemented" else availability


def render(index: dict[str, Any], version: dict[str, Any], commands: list[dict[str, Any]], digest: str) -> dict[str, str]:
    catalog_commands = []
    for item in commands:
        value = dict(item)
        value.update(descriptor_metadata(index, item))
        value["native_id"] = application_identifier(str(item["runtime_id"]))
        value["aliases"] = runtime_aliases(str(item["runtime_id"]))
        value["writes_state"] = "workspace_write" in {str(effect) for effect in item.get("effects", [])}
        value["request_schema"] = request_schema_path(str(item["runtime_id"]))
        catalog_commands.append(value)
    catalog = {
        "schema": "facman.generated_command_catalog.v2",
        "source_digest": digest,
        "owner": index["owner"],
        "binding": index["binding"],
        "version": version["canonical_version"],
        "commands": catalog_commands,
    }
    header = [
        f"/* Generated by tools/codegen/generate_metadata.py; source-sha256: {digest}. */",
        "#ifndef FACMAN_GENERATED_COMMAND_CATALOG_H",
        "#define FACMAN_GENERATED_COMMAND_CATALOG_H",
        "",
        "typedef enum facman_generated_command_id {",
    ]
    for item in commands:
        header.append(f"    FACMAN_COMMAND_{c_identifier(str(item['command_id']))},")
    header.extend([
        "    FACMAN_COMMAND_COUNT",
        "} facman_generated_command_id;",
        "",
        "typedef struct facman_generated_command_descriptor {",
        "    const char* command_name;",
        "    const char* native_id;",
        "    const char* aliases_json;",
        "    const char* effects_json;",
        "    const char* request_schema;",
        "    const char* response_schema;",
        "    const char* result_schema;",
        "    const char* refusal_schema;",
        "    const char* diagnostic_schema;",
        "    const char* request_fields_json;",
        "    const char* cli_grammar_json;",
        "    const char* visibility;",
        "    const char* deprecation;",
        "    const char* availability_refusal_code;",
        "    const char* risk_tier;",
        "    const char* renderer;",
        "    const char* frontend_category;",
        "    const char* localization_keys_json;",
        "    const char* dry_run_behavior;",
        "    const char* availability;",
        "    const char* owner;",
        "    const char* binding;",
        "    int writes_state;",
        "} facman_generated_command_descriptor;",
        "",
        "static const facman_generated_command_descriptor facman_generated_registered_commands[] = {",
    ])
    for item in commands:
        if not item["registered"]:
            continue
        effects = json.dumps(item.get("effects", []), separators=(",", ":"))
        metadata = descriptor_metadata(index, item)
        values = [
            str(item["runtime_id"]),
            application_identifier(str(item["runtime_id"])),
            json.dumps(runtime_aliases(str(item["runtime_id"])), separators=(",", ":")),
            effects,
            request_schema_path(str(item["runtime_id"])),
            str(item["response_schema"]),
            str(item["result_schema"]),
            str(item["refusal_schema"]),
            str(item["diagnostic_schema"]),
            json.dumps(metadata["request_fields"], separators=(",", ":")),
            json.dumps(metadata["cli_grammar"], separators=(",", ":")),
            str(metadata["visibility"]),
            str(metadata["deprecation"]),
            str(metadata["availability_refusal_code"]),
            str(metadata["risk_tier"]),
            str(metadata["renderer"]),
            str(metadata["frontend_category"]),
            json.dumps(metadata["localization_keys"], separators=(",", ":")),
            dry_run_behavior(item),
            runtime_availability(item),
            str(index["owner"]),
            str(index["binding"]),
        ]
        header.append("    {")
        header.extend(f"        {c_string(value)}," for value in values)
        header.append(f"        {1 if 'workspace_write' in set(item.get('effects', [])) else 0},")
        header.append("    },")
    header.extend([
        "};",
        "#define FACMAN_GENERATED_REGISTERED_COMMAND_COUNT \\",
        "    (sizeof(facman_generated_registered_commands) / sizeof(facman_generated_registered_commands[0]))",
        "",
        "#endif",
        "",
    ])
    version_header = [
        f"/* Generated by tools/codegen/generate_metadata.py; source-sha256: {digest}. */",
        "#ifndef FACMAN_GENERATED_VERSION_H",
        "#define FACMAN_GENERATED_VERSION_H",
        f"#define FACMAN_VERSION_SEMVER {c_string(str(version['semver']))}",
        f"#define FACMAN_VERSION_CANONICAL {c_string(str(version['canonical_version']))}",
        f"#define FACMAN_VERSION_FILENAME {c_string(str(version['filename_version']))}",
        f"#define FACMAN_VERSION_COMPONENT {c_string(str(version['component_version']))}",
        "#endif",
        "",
    ]
    help_lines = [
        f"// Generated by tools/codegen/generate_metadata.py; source-sha256: {digest}.",
        "static const char* const kGeneratedCommandHelp[] = {",
    ]
    for item in commands:
        cli = str(item.get("cli", ""))
        if cli.startswith("facman "):
            help_lines.append(f"    {c_string(cli[len('facman '):])},")
    help_lines.extend(["};", ""])
    grammars = [descriptor_metadata(index, item) | {
        "command_id": str(item["command_id"]),
        "runtime_id": str(item["runtime_id"]),
        "aliases": runtime_aliases(str(item["runtime_id"])),
    } for item in commands]
    public_grammars = [value for value in grammars if not value["cli_grammar"]["internal"]]
    top_level = sorted({value["cli_grammar"]["path"][0] for value in public_grammars if value["cli_grammar"]["path"]})
    words = " ".join(top_level)
    full_paths = sorted({" ".join(value["cli_grammar"]["path"]) for value in public_grammars if value["cli_grammar"]["path"]})
    bash_words = " ".join(sorted(set(top_level + [part for path in full_paths for part in path.split()])))
    completions = {
        "bash": f"# generated source-sha256: {digest}\n# full paths: {' | '.join(full_paths)}\ncomplete -W \"{bash_words}\" facman\n",
        "zsh": f"#compdef facman\n# generated source-sha256: {digest}\n# full paths: {' | '.join(full_paths)}\n_arguments '1:command:({words})' '*:subcommand:({bash_words})'\n",
        "fish": "# generated source-sha256: " + digest + "\n" + "\n".join(f"# path: {path}" for path in full_paths) + "\n" + "\n".join(f"complete -c facman -f -a {word}" for word in sorted(set(bash_words.split()))) + "\n",
        "powershell": (
            f"# generated source-sha256: {digest}\n# full paths: {' | '.join(full_paths)}\n"
            "Register-ArgumentCompleter -Native -CommandName facman -ScriptBlock { "
            f"param($wordToComplete) '{bash_words}'.Split(' ') | "
            "Where-Object { $_ -like \"$wordToComplete*\" } }\n"
        ),
    }
    docs = [
        "# Generated Command Catalog",
        "",
        f"Source digest: `{digest}`.",
        "",
        "Do not edit this table directly. Edit the indexed command contracts and regenerate.",
        "",
        "| Contract ID | Runtime ID | Native ID | Writes | Aliases | Availability | Effects | CLI |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in commands:
        availability = str(item.get("availability", "available"))
        effects = ", ".join(str(value) for value in item.get("effects", []))
        native_id = application_identifier(str(item["runtime_id"]))
        aliases = ", ".join(runtime_aliases(str(item["runtime_id"]))) or "-"
        writes = "yes" if "workspace_write" in set(item.get("effects", [])) else "no"
        docs.append(
            f"| `{item['command_id']}` | `{item['runtime_id']}` | `{native_id}` | {writes} | "
            f"{aliases} | {availability} | {effects} | `{item.get('cli', '')}` |"
        )
    docs.append("")
    application_ids = [f"// Generated by tools/codegen/generate_metadata.py; source-sha256: {digest}."]
    seen_ids: set[str] = set()
    for item in commands:
        identifier = application_identifier(str(item["runtime_id"]))
        if identifier not in seen_ids:
            application_ids.append(f"    {identifier},")
            seen_ids.add(identifier)
    application_ids.append("")

    application_lookup = [f"// Generated by tools/codegen/generate_metadata.py; source-sha256: {digest}."]
    for item in commands:
        runtime_id = str(item["runtime_id"])
        identifier = application_identifier(runtime_id)
        values = [runtime_id, *runtime_aliases(runtime_id)]
        condition = " || ".join(f"value == {c_string(alias)}" for alias in values)
        application_lookup.append(f"    if ({condition}) return CommandId::{identifier};")
    application_lookup.append("")

    preferred_names: dict[str, str] = {}
    for item in commands:
        runtime_id = str(item["runtime_id"])
        identifier = application_identifier(runtime_id)
        if identifier not in preferred_names or runtime_id == "product.inspect":
            preferred_names[identifier] = runtime_id
    application_names = [f"// Generated by tools/codegen/generate_metadata.py; source-sha256: {digest}."]
    for identifier, runtime_id in preferred_names.items():
        application_names.append(f"    case CommandId::{identifier}: return {c_string(runtime_id)};")
    application_names.append("")

    write_ids = {
        application_identifier(str(item["runtime_id"]))
        for item in commands
        if "workspace_write" in {str(effect) for effect in item.get("effects", [])}
    }
    application_writes = [f"// Generated by tools/codegen/generate_metadata.py; source-sha256: {digest}."]
    for identifier in sorted(write_ids):
        application_writes.append(f"    case CommandId::{identifier}: return true;")
    application_writes.append("")
    rendered = {
        "catalog_json": json.dumps(catalog, indent=2, sort_keys=True) + "\n",
        "command_header": "\n".join(header),
        "version_header": "\n".join(version_header),
        "help_include": "\n".join(help_lines),
        **completions,
        "docs": "\n".join(docs),
        "application_ids": "\n".join(application_ids),
        "application_lookup": "\n".join(application_lookup),
        "application_names": "\n".join(application_names),
        "application_writes": "\n".join(application_writes),
        "grammar_json": json.dumps({"schema": "facman.command_cli_grammar.v2", "source_digest": digest, "commands": grammars}, indent=2, sort_keys=True) + "\n",
        "frontend_json": json.dumps({"schema": "facman.frontend_command_catalog.v1", "source_digest": digest, "commands": [value for value in catalog_commands if value["registered"]]}, indent=2, sort_keys=True) + "\n",
    }
    for item in commands:
        rendered[f"request_schema:{item['runtime_id']}"] = request_schema(str(item["runtime_id"]))
    return rendered


def generate(write: bool) -> list[str]:
    index, version, commands, digest = load_sources()
    rendered = render(index, version, commands, digest)
    outputs = dict(OUTPUTS)
    for item in commands:
        outputs[f"request_schema:{item['runtime_id']}"] = ROOT / request_schema_path(str(item["runtime_id"]))
    problems: list[str] = []
    for name, path in outputs.items():
        expected = rendered[name]
        actual = path.read_text(encoding="utf-8") if path.is_file() else ""
        if actual != expected:
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(expected, encoding="utf-8")
            else:
                problems.append(f"generated output is stale or missing: {path.relative_to(ROOT).as_posix()}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate canonical FacMan command and version metadata.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    problems = generate(write=args.write)
    if problems:
        for problem in problems:
            print(f"generate-metadata: {problem}", file=sys.stderr)
        return 1
    print("generate-metadata: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
