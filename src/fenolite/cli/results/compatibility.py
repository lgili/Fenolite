# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Compare declared wire properties after resolving local references; definition names stay internal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SchemaChange:
    kind: str
    path: str


def schema_changes(
    before: dict[str, Any], after: dict[str, Any], *, name: str, input_mode: bool = False
) -> tuple[SchemaChange, ...]:
    found: list[SchemaChange] = []

    def resolve(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
        while "$ref" in node:
            ref = str(node["$ref"])
            if not ref.startswith("#/"):
                raise ValueError(f"external schema reference is not supported: {ref}")
            node = root
            for key in ref[2:].split("/"):
                node = node[key.replace("~1", "/").replace("~0", "~")]
        return node

    def alternatives(node: dict[str, Any], root: dict[str, Any]) -> list[dict[str, Any]]:
        node = resolve(node, root)
        return [resolve(child, root) for child in node.get("anyOf", [node])]

    def kind(node: dict[str, Any]) -> str:
        if "type" in node:
            return str(node["type"])
        values = node.get("enum", [node["const"]] if "const" in node else [])
        if values:
            return "/".join(
                sorted(
                    {
                        "null"
                        if value is None
                        else "boolean"
                        if isinstance(value, bool)
                        else "integer"
                        if isinstance(value, int)
                        else "number"
                        if isinstance(value, float)
                        else "string"
                        for value in values
                    }
                )
            )
        return "any"

    def literals(node: dict[str, Any]) -> set[tuple[str, str]] | None:
        values = node.get("enum", [node["const"]] if "const" in node else None)
        return None if values is None else {(type(value).__name__, repr(value)) for value in values}

    seen: set[tuple[int, int]] = set()

    def compare(a: dict[str, Any], b: dict[str, Any], path: str) -> None:
        a, b = resolve(a, before), resolve(b, after)
        pair = id(a), id(b)
        if pair in seen:
            return
        seen.add(pair)
        left, right = alternatives(a, before), alternatives(b, after)
        if {kind(value) for value in left} != {kind(value) for value in right}:
            found.append(SchemaChange("type-changed", path))
            return
        if "anyOf" in a or "anyOf" in b:
            for old in left:
                candidates = [value for value in right if kind(old) == kind(value)]
                # A new object alternative may coexist with an unchanged old one.
                best = max(
                    candidates,
                    key=lambda value: len(set(old.get("properties", {})) & set(value.get("properties", {}))),
                )
                compare(old, best, path)
            return
        if literals(a) != literals(b):
            found.append(SchemaChange("type-changed", path))
        old_props, new_props = a.get("properties", {}), b.get("properties", {})
        for key in sorted(old_props.keys() - new_props.keys()):
            found.append(SchemaChange("removed", path + "." + key))
        for key in sorted(old_props.keys() & new_props.keys()):
            compare(old_props[key], new_props[key], path + "." + key)
        if input_mode:
            for key in sorted(set(b.get("required", ())) - set(a.get("required", ()))):
                found.append(SchemaChange("required-added", path + "." + key))
        if isinstance(a.get("items"), dict) and isinstance(b.get("items"), dict):
            compare(a["items"], b["items"], path + "[]")
        old_tuple, new_tuple = a.get("prefixItems", []), b.get("prefixItems", [])
        if len(old_tuple) != len(new_tuple):
            found.append(SchemaChange("type-changed", path + "[]"))
        for index, (old, new) in enumerate(zip(old_tuple, new_tuple, strict=False)):
            compare(old, new, f"{path}[{index}]")
        if isinstance(a.get("additionalProperties"), dict) and isinstance(
            b.get("additionalProperties"), dict
        ):
            compare(a["additionalProperties"], b["additionalProperties"], path + ".{key}")
        elif isinstance(a.get("additionalProperties"), dict) != isinstance(
            b.get("additionalProperties"), dict
        ):
            found.append(SchemaChange("type-changed", path + ".{key}"))

    compare(before, after, name)
    return tuple(dict.fromkeys(found))
