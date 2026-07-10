from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_schema(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"schema is not an object: {path}")
    return data


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    problems: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(instance, expected_type):
        return [f"{path}: expected type {expected_type!r}, got {_type_name(instance)}"]

    if "const" in schema and instance != schema["const"]:
        problems.append(f"{path}: expected constant {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        problems.append(f"{path}: value {instance!r} is not in {schema['enum']!r}")
    if isinstance(instance, str) and isinstance(schema.get("minLength"), int):
        if len(instance) < schema["minLength"]:
            problems.append(f"{path}: string is shorter than {schema['minLength']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if isinstance(schema.get("minimum"), (int, float)) and instance < schema["minimum"]:
            problems.append(f"{path}: value is less than {schema['minimum']}")

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

    if isinstance(instance, list) and isinstance(schema.get("items"), dict):
        for index, value in enumerate(instance):
            problems.extend(validate(value, schema["items"], f"{path}[{index}]"))
    return problems


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
    }.get(str(expected), lambda: True)()


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
