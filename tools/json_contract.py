from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
SUPPORTED_SCHEMA_KEYWORDS = {
    "$id",
    "$schema",
    "additionalProperties",
    "const",
    "default",
    "description",
    "enum",
    "examples",
    "items",
    "maximum",
    "maxItems",
    "maxLength",
    "minimum",
    "minItems",
    "minLength",
    "pattern",
    "properties",
    "required",
    "title",
    "type",
}


def load_schema(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"schema is not an object: {path}")
    return data


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    problems: list[str] = []
    expected_type = schema.get("type")
    type_problems = _type_declaration_problems(expected_type, f"{path}.type")
    if type_problems:
        return type_problems
    if expected_type is not None and not _matches_type(instance, expected_type):
        return [f"{path}: expected type {expected_type!r}, got {_type_name(instance)}"]

    if "const" in schema and instance != schema["const"]:
        problems.append(f"{path}: expected constant {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        problems.append(f"{path}: value {instance!r} is not in {schema['enum']!r}")
    if isinstance(instance, str) and isinstance(schema.get("minLength"), int):
        if len(instance) < schema["minLength"]:
            problems.append(f"{path}: string is shorter than {schema['minLength']}")
    if isinstance(instance, str) and isinstance(schema.get("maxLength"), int):
        if len(instance) > schema["maxLength"]:
            problems.append(f"{path}: string is longer than {schema['maxLength']}")
    if isinstance(instance, str) and isinstance(schema.get("pattern"), str):
        try:
            if re.search(schema["pattern"], instance) is None:
                problems.append(f"{path}: string does not match pattern {schema['pattern']!r}")
        except re.error as exc:
            problems.append(f"{path}: schema pattern is invalid: {exc}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if isinstance(schema.get("minimum"), (int, float)) and instance < schema["minimum"]:
            problems.append(f"{path}: value is less than {schema['minimum']}")
        if isinstance(schema.get("maximum"), (int, float)) and instance > schema["maximum"]:
            problems.append(f"{path}: value is greater than {schema['maximum']}")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in instance:
                    problems.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, value in instance.items():
                property_schema = properties.get(key)
                if isinstance(property_schema, dict):
                    problems.extend(validate(value, property_schema, f"{path}.{key}"))
                elif schema.get("additionalProperties") is False:
                    problems.append(f"{path}: additional property {key!r} is not allowed")
                elif isinstance(schema.get("additionalProperties"), dict):
                    problems.extend(validate(value, schema["additionalProperties"], f"{path}.{key}"))

    if isinstance(instance, list):
        if isinstance(schema.get("minItems"), int) and len(instance) < schema["minItems"]:
            problems.append(f"{path}: array has fewer than {schema['minItems']} items")
        if isinstance(schema.get("maxItems"), int) and len(instance) > schema["maxItems"]:
            problems.append(f"{path}: array has more than {schema['maxItems']} items")
        if isinstance(schema.get("items"), dict):
            for index, value in enumerate(instance):
                problems.extend(validate(value, schema["items"], f"{path}[{index}]"))
    return problems


def supported_schema_problems(schema: dict[str, Any], path: str = "$") -> list[str]:
    """Reject schemas whose constraints the bounded validator cannot enforce."""
    problems: list[str] = []
    for keyword in schema:
        if keyword not in SUPPORTED_SCHEMA_KEYWORDS:
            problems.append(f"{path}: unsupported schema keyword {keyword!r}")
    problems.extend(_type_declaration_problems(schema.get("type"), f"{path}.type"))

    properties = schema.get("properties")
    if properties is not None and not isinstance(properties, dict):
        problems.append(f"{path}.properties: expected object")
    elif isinstance(properties, dict):
        for key, child in properties.items():
            if not isinstance(child, dict):
                problems.append(f"{path}.properties.{key}: expected schema object")
            else:
                problems.extend(supported_schema_problems(child, f"{path}.properties.{key}"))

    items = schema.get("items")
    if items is not None:
        if not isinstance(items, dict):
            problems.append(f"{path}.items: only one schema object is supported")
        else:
            problems.extend(supported_schema_problems(items, f"{path}.items"))

    additional = schema.get("additionalProperties")
    if additional is not None and not isinstance(additional, (bool, dict)):
        problems.append(f"{path}.additionalProperties: expected boolean or schema object")
    elif isinstance(additional, dict):
        problems.extend(supported_schema_problems(additional, f"{path}.additionalProperties"))

    required = schema.get("required")
    if required is not None and (
        not isinstance(required, list) or not all(isinstance(item, str) for item in required)
    ):
        problems.append(f"{path}.required: expected an array of property names")

    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        problems.append(f"{path}.enum: expected array")

    pattern = schema.get("pattern")
    if isinstance(pattern, str):
        try:
            re.compile(pattern)
        except re.error as exc:
            problems.append(f"{path}.pattern: invalid regular expression: {exc}")
    return problems


def _type_declaration_problems(expected: Any, path: str) -> list[str]:
    if expected is None:
        return []
    values = expected if isinstance(expected, list) else [expected]
    if not values or not all(isinstance(value, str) for value in values):
        return [f"{path}: expected a type name or non-empty array of type names"]
    unknown = sorted(set(values) - SUPPORTED_TYPES)
    return [f"{path}: unsupported type {value!r}" for value in unknown]


def _matches_type(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches_type(value, candidate) for candidate in expected)
    return {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "integer": lambda: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda: isinstance(value, bool),
        "null": lambda: value is None,
    }[str(expected)]()


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__
