"""Small fail-closed JSON Schema subset used by the deterministic P0 runner."""
from __future__ import annotations

from typing import Any


def validate(value: Any, schema: dict[str, Any] | None, path: str = "$") -> tuple[str, ...]:
    if schema is None:
        return ()
    errors: list[str] = []
    expected = schema.get("type")
    if expected and not _matches_type(value, str(expected)):
        return (f"{path}: expected {expected}, got {_type_name(value)}",)
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")
    if isinstance(value, dict):
        required = schema.get("required", ())
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: required field is missing")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(validate(value[key], child_schema, f"{path}.{key}"))
        if schema.get("additionalProperties") is False and isinstance(properties, dict):
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key}: additional property is not allowed")
    elif isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            errors.extend(validate(item, schema["items"], f"{path}[{index}]"))
    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            errors.append(f"{path}: string shorter than minLength")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(schema.get("minimum"), (int, float)) and value < schema["minimum"]:
            errors.append(f"{path}: value below minimum")
    return tuple(errors)


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def infer_schema(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        return {"type": "array", "items": infer_schema(value[0]) if value else {}}
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {str(key): infer_schema(item) for key, item in value.items()},
            "required": sorted(str(key) for key in value),
            "additionalProperties": True,
        }
    return {"type": "string"}
