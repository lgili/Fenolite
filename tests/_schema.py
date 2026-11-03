# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A small JSON Schema (2020-12) validator covering the keywords Fenolite's generator emits.

Supported: $ref (local #/$defs/...), anyOf, type (string or list), enum, const, pattern, minimum,
properties, required, additionalProperties (bool or schema), items (schema or false), prefixItems.
Returns a list of "<json-pointer>: <problem>" strings; empty means valid.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"

_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "null": (type(None),),
}


def load(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def closed(schema: dict[str, Any]) -> dict[str, Any]:
    """Close declared structures while retaining explicitly typed, data-keyed map boundaries."""
    result = copy.deepcopy(schema)

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if (
                node.get("type") == "object"
                and "properties" in node
                and not node.get("x-fenolite-map", False)
            ):
                node["additionalProperties"] = False
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(result)
    return result


def _is_type(value: Any, name: str) -> bool:
    if isinstance(value, bool) and name in ("integer", "number"):
        return False
    return isinstance(value, _TYPES[name])


def _resolve(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"only local refs are supported: {ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(instance: Any, schema: dict[str, Any], root: dict[str, Any] | None = None,
             pointer: str = "") -> list[str]:  # fmt: skip
    root = schema if root is None else root
    where = pointer or "/"
    if "$ref" in schema:
        return validate(instance, _resolve(schema["$ref"], root), root, pointer)
    if "anyOf" in schema:
        if not any(not validate(instance, option, root, pointer) for option in schema["anyOf"]):
            return [f"{where}: matches no anyOf alternative"]
        return []
    errors: list[str] = []
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(instance, n) for n in names):
            return [f"{where}: expected {'/'.join(names)}, got {type(instance).__name__}"]
    if "enum" in schema and not any(
        instance == choice and isinstance(instance, bool) == isinstance(choice, bool)
        for choice in schema["enum"]
    ):
        errors.append(f"{where}: {instance!r} not in {schema['enum']!r}")
    if "const" in schema and (
        instance != schema["const"] or isinstance(instance, bool) != isinstance(schema["const"], bool)
    ):
        errors.append(f"{where}: expected constant {schema['const']!r}")
    if isinstance(instance, str) and "pattern" in schema and not re.search(schema["pattern"], instance):
        errors.append(f"{where}: {instance!r} does not match {schema['pattern']!r}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool) and "minimum" in schema:
        if instance < schema["minimum"]:
            errors.append(f"{where}: {instance} < minimum {schema['minimum']}")
    if isinstance(instance, dict):
        props: dict[str, Any] = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{where}: missing required property {key!r}")
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            child = f"{pointer}/{key}"
            if key in props:
                errors.extend(validate(value, props[key], root, child))
            elif additional is False:
                errors.append(f"{where}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                errors.extend(validate(value, additional, root, child))
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{where}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{where}: more than {schema['maxItems']} items")
        prefix: list[Any] = schema.get("prefixItems", [])
        for index, value in enumerate(instance):
            child = f"{pointer}/{index}"
            if index < len(prefix):
                errors.extend(validate(value, prefix[index], root, child))
            elif schema.get("items") is False:
                errors.append(f"{where}: unexpected item at index {index}")
            elif isinstance(schema.get("items"), dict):
                errors.extend(validate(value, schema["items"], root, child))
    return errors
