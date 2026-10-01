# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generate JSON Schema (draft 2020-12) files from Fenolite dataclasses.

    uv run python tools/gen_schemas.py          # (re)write schemas/
    uv run python tools/gen_schemas.py --check  # exit 1 if any schema file would change

Supported annotations: bool, int, float, str, None, Any, Literal, X | None, list[T], tuple[T, ...],
dict[str, T], Enum subclasses and nested dataclasses. Field metadata keys ``pattern``,
``minimum`` and ``description`` are copied into the property schema.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import sys
import types
import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DRAFT = "https://json-schema.org/draft/2020-12/schema"


@dataclass(frozen=True)
class Target:
    schema_id: str
    ref: str  # "module:ClassName"
    out: str  # path relative to ROOT
    all_required: bool  # wire formats: every field always present


def _targets() -> list[Target]:
    from fenolite.model.schema import LAYER_SCHEMAS, LIBRARY_SCHEMA, SCHEMA_DIR

    wire = [
        Target(
            "fenolite.envelope.v0", "fenolite.cli.output:Envelope", "schemas/fenolite.envelope.v0.json", True
        ),
        Target("fenolite.error.v0", "fenolite.cli.errors:ErrorInfo", "schemas/fenolite.error.v0.json", True),
    ]
    model = [Target(sid, ref, f"{SCHEMA_DIR}/{name}", False) for name, (sid, ref) in LAYER_SCHEMAS.items()]
    name, sid, ref = LIBRARY_SCHEMA
    return [*wire, *model, Target(sid, ref, f"{SCHEMA_DIR}/{name}", False)]


TARGETS: list[Target] = _targets()


class SchemaBuilder:
    def __init__(self, *, all_required: bool) -> None:
        self.all_required = all_required
        self.defs: dict[str, dict[str, Any]] = {}

    def root(self, cls: type, schema_id: str) -> dict[str, Any]:
        body = self.object_schema(cls)
        schema: dict[str, Any] = {"$schema": DRAFT, "$id": schema_id, "title": cls.__name__, **body}
        if self.defs:
            schema["$defs"] = {name: self.defs[name] for name in sorted(self.defs)}
        return schema

    def object_schema(self, cls: type) -> dict[str, Any]:
        hints = typing.get_type_hints(cls)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for f in dataclasses.fields(cls):
            prop = self.type_schema(hints[f.name])
            _apply_metadata(prop, dict(f.metadata))
            properties[f.name] = prop
            no_default = f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
            if self.all_required or no_default:
                required.append(f.name)
        schema: dict[str, Any] = {}
        doc = (cls.__doc__ or "").strip().splitlines()
        if doc and not doc[0].startswith(cls.__name__ + "("):
            schema["description"] = doc[0]
        schema.update({"type": "object", "properties": properties, "additionalProperties": False})
        if required:
            schema["required"] = required
        return schema

    def type_schema(self, tp: Any) -> dict[str, Any]:
        origin = typing.get_origin(tp)
        args = typing.get_args(tp)
        if tp is Any:
            return {}
        if tp is type(None):
            return {"type": "null"}
        if tp is bool:
            return {"type": "boolean"}
        if tp is int:
            return {"type": "integer"}
        if tp is float:
            return {"type": "number"}
        if tp is str:
            return {"type": "string"}
        if origin is typing.Literal:
            return {"enum": list(args)}
        if origin in (typing.Union, types.UnionType):
            return {"anyOf": [self.type_schema(a) for a in args]}
        if origin is list:
            return {"type": "array", "items": self.type_schema(args[0])}
        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                return {"type": "array", "items": self.type_schema(args[0])}
            return {"type": "array", "prefixItems": [self.type_schema(a) for a in args], "items": False}
        if origin is dict:
            value = self.type_schema(args[1])
            return {"type": "object"} if value == {} else {"type": "object", "additionalProperties": value}
        if isinstance(tp, type) and issubclass(tp, Enum):
            return {"enum": [member.value for member in tp]}
        if isinstance(tp, type) and dataclasses.is_dataclass(tp):
            name = tp.__name__
            if name not in self.defs:
                self.defs[name] = {}
                self.defs[name] = self.object_schema(tp)
            return {"$ref": f"#/$defs/{name}"}
        raise TypeError(f"unsupported annotation {tp!r}")


def _apply_metadata(prop: dict[str, Any], metadata: dict[str, Any]) -> None:
    extra = {k: metadata[k] for k in ("pattern", "minimum", "description") if k in metadata}
    if not extra:
        return
    if "anyOf" in prop:
        for option in prop["anyOf"]:
            if option.get("type") in ("string", "integer", "number"):
                option.update(extra)
    else:
        prop.update(extra)


def _load(ref: str) -> type:
    module_name, _, attr = ref.partition(":")
    return getattr(importlib.import_module(module_name), attr)


def render(target: Target) -> str:
    builder = SchemaBuilder(all_required=target.all_required)
    schema = builder.root(_load(target.ref), target.schema_id)
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if any schema file would change")
    args = parser.parse_args(argv)
    stale: list[str] = []
    for target in TARGETS:
        text = render(target)
        path = ROOT / target.out
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        if args.check:
            stale.append(target.out)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {target.out}")
    if stale:
        print("stale schemas (run tools/gen_schemas.py):\n  " + "\n  ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
