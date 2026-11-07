# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Write model field/extension inventories with decisions pending by default (c0218).

Reader locations are a conservative static index: attribute/getattr/mapping reads by spelling,
plus generic dataclass readers. They are review leads, not a runtime coverage claim.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import importlib
import inspect
import json
import pkgutil
import sys
import types
import typing
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from datetime import date
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "openspec/changes/archive/2026-11-04-c0218-model-schema-1-0/review.json"


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return {"enum": type(value).__qualname__, "value": value.value}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            "type": type(value).__module__ + "." + type(value).__qualname__,
            "fields": {field.name: _plain(getattr(value, field.name)) for field in dataclasses.fields(value)},
        }
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, object], value)
        return {str(key): _plain(item) for key, item in sorted(mapping.items())}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in cast(tuple[object, ...] | list[object], value)]
    if isinstance(value, (set, frozenset)):
        collection = cast(set[object] | frozenset[object], value)
        values = [_plain(item) for item in collection]
        return {
            "kind": type(collection).__name__,
            "values": sorted(values, key=lambda item: json.dumps(item, sort_keys=True)),
        }
    if callable(value) and hasattr(value, "__qualname__"):
        return {"callable": value.__module__ + "." + value.__qualname__}
    if hasattr(value, "__dict__"):
        return {"type": type(value).__module__ + "." + type(value).__qualname__, "state": _plain(vars(value))}
    raise TypeError(f"review default of {type(value).__name__} needs an explicit representation")


def _default(field: dataclasses.Field[Any]) -> dict[str, Any]:
    if field.default is not dataclasses.MISSING:
        return {"kind": "value", "value": _plain(field.default)}
    if field.default_factory is not dataclasses.MISSING:
        return {"kind": "factory", "value": _plain(field.default_factory())}
    return {"kind": "required"}


def model_classes() -> tuple[type, ...]:
    import fenolite.model

    classes: dict[str, type] = {}
    for entry in pkgutil.walk_packages(fenolite.model.__path__, fenolite.model.__name__ + "."):
        module = importlib.import_module(entry.name)
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__.startswith("fenolite.model.") and dataclasses.is_dataclass(cls):
                classes[cls.__module__ + "." + cls.__qualname__] = cls
    return tuple(classes[name] for name in sorted(classes))


def _resolved(hint: object) -> None:
    if isinstance(hint, typing.ForwardRef):
        raise NameError(f"unresolved model annotation {hint.__forward_arg__!r}")
    for argument in typing.get_args(hint):
        _resolved(argument)


def model_hints(cls: type, classes: tuple[type, ...]) -> dict[str, Any]:
    """Resolve actual annotations, preserving each base's owning module and class scope.

    A unique real model class may fill a TYPE_CHECKING-only binding. Ambiguous or absent names
    remain absent and get_type_hints fails; no field is dropped or substituted with Any.
    """
    by_name: dict[str, set[type]] = defaultdict(set)
    for actual in classes:
        by_name[actual.__name__].add(actual)
    unique = {name: next(iter(found)) for name, found in by_name.items() if len(found) == 1}
    resolved: dict[str, Any] = {}
    for base in reversed(cls.__mro__):
        annotations = vars(base).get("__annotations__", {})
        if not annotations:
            continue
        namespace = {**unique, **vars(sys.modules[base.__module__])}
        own = types.SimpleNamespace(__annotations__=annotations)
        hints = typing.get_type_hints(own, globalns=namespace, localns=dict(vars(base)))
        for hint in hints.values():
            _resolved(hint)
        resolved.update(hints)
    return resolved


def readers() -> tuple[dict[str, list[str]], list[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    reflective: set[str] = set()
    for path in sorted((ROOT / "src/fenolite").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                found[node.attr].add(relative)
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    found[node.slice.value].add(relative)
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            if name in {"fields", "asdict", "astuple"}:
                reflective.add(relative)
            index = 1 if name == "getattr" else 0 if name in {"get", "pop", "setdefault"} else -1
            if index >= 0 and len(node.args) > index:
                argument = node.args[index]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    found[argument.value].add(relative)
    return {key: sorted(values) for key, values in sorted(found.items())}, sorted(reflective)


def extensions(index: dict[str, list[str]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted((ROOT / "src/fenolite/backends").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants: dict[str, Any] = {}
        for node in tree.body:
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, ast.AnnAssign)
                else []
            )
            if value is not None:
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in {"BACKEND", "EXT_KEYS"}:
                        constants[target.id] = ast.literal_eval(value)
        for key in constants.get("EXT_KEYS", ()):
            result.append(
                {
                    "backend": constants.get(
                        "BACKEND", path.relative_to(ROOT / "src/fenolite/backends").parts[0]
                    ),
                    "key": key,
                    "declared_in": path.relative_to(ROOT).as_posix(),
                    "readers": index.get(key, []),
                    "decision": "pending",
                }
            )
    return result


def inventory() -> dict[str, Any]:
    index, reflective = readers()
    entries: list[dict[str, Any]] = []
    used_names: set[str] = set()
    classes = model_classes()
    for cls in classes:
        hints = model_hints(cls, classes)
        fields: list[dict[str, Any]] = []
        for field in dataclasses.fields(cls):
            used_names.add(field.name)
            fields.append(
                {
                    "name": field.name,
                    "type": str(hints[field.name]).replace("typing.", ""),
                    "default": _default(field),
                    "readers": field.name,
                    "decision": "pending",
                }
            )
        entries.append(
            {"class": cls.__module__ + "." + cls.__qualname__, "fields": fields, "decision": "pending"}
        )
    return {
        "schema": "fenolite.model-review.v0",
        "decision_date": None,
        "reviewer": None,
        "decision": "Pending explicit maintainer KEEP/RENAME/DROP review.",
        "reader_method": (
            "Conservative static attribute/key spellings plus generic reflective readers. "
            "Not runtime or type-resolved coverage."
        ),
        "generic_readers": reflective,
        "readers": {name: index.get(name, []) for name in sorted(used_names)},
        "classes": entries,
        "extension_keys": extensions(index),
        "opaque_extensions": (
            "Keep all unknown backend fragments and backend namespaces verbatim; "
            "they have no closed key vocabulary."
        ),
    }


def record_keep_all(data: dict[str, Any], *, reviewer: str, decision_date: str) -> dict[str, Any]:
    """Record an explicitly supplied review without changing type/default metadata."""
    if not reviewer.strip() or date.fromisoformat(decision_date).isoformat() != decision_date:
        raise ValueError("an explicit reviewer and canonical actual decision date are required")
    result = deepcopy(data)
    for entry in result["classes"]:
        entry["decision"] = "keep"
        for field in entry["fields"]:
            field["decision"] = "keep"
    for entry in result["extension_keys"]:
        entry["decision"] = "keep"
    result["decision"] = "KEEP current fields and extension keys; explicit maintainer decision."
    result["decision_date"] = decision_date
    result["reviewer"] = reviewer
    return result


def reviewed(data: dict[str, Any]) -> dict[str, Any]:
    """The part of an inventory a review decides on: classes, fields, types, defaults, extension keys and
    decisions. The reader locations are review leads that move with every source edit, so a stale reader
    index alone does not make the inventory stale (change c0404)."""
    result = {key: value for key, value in data.items() if key not in {"generic_readers", "readers"}}
    result["extension_keys"] = [
        {key: value for key, value in entry.items() if key != "readers"} for entry in data["extension_keys"]
    ]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "Review model fields and extensions.").splitlines()[0]
    )
    parser.add_argument("--out", type=Path, default=DEFAULT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--keep-all", action="store_true", help="record an actual authorized KEEP decision")
    parser.add_argument("--reviewer", help="the actual maintainer who made the decision")
    parser.add_argument("--decision-date", help="the actual decision date, YYYY-MM-DD")
    args = parser.parse_args(argv)
    if args.keep_all and (not args.reviewer or not args.decision_date):
        parser.error("--keep-all requires --reviewer and --decision-date; no approval is assumed")
    if not args.keep_all and (args.reviewer or args.decision_date):
        parser.error("review metadata requires an actual --keep-all decision")
    data = inventory()
    if args.keep_all:
        try:
            data = record_keep_all(data, reviewer=args.reviewer, decision_date=args.decision_date)
        except ValueError as error:
            parser.error(str(error))
    rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        stored = json.loads(args.out.read_text(encoding="utf-8")) if args.out.is_file() else None
        if stored is None or reviewed(stored) != reviewed(data):
            print("model review inventory is stale: run tools/model_review.py", file=sys.stderr)
            return 1
        if args.out.read_text(encoding="utf-8") != rendered:
            print("model review: reader locations moved (review leads only); the reviewed shape is current")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    fields = sum(len(entry["fields"]) for entry in data["classes"])
    print(
        f"model review: {len(data['classes'])} dataclasses, {fields} fields, "
        f"{len(data['extension_keys'])} fixed extension keys; "
        f"{'KEEP explicitly recorded' if args.keep_all else 'all decisions PENDING'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
