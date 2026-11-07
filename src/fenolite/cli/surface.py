# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The declared CLI and explicitly exported Python surface, without running command examples."""

from __future__ import annotations

import argparse
import ast
import dataclasses
import importlib
import inspect
import json
import re
import textwrap
import typing
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, cast

from fenolite import __version__
from fenolite.cli import api as cli_api
from fenolite.cli.api import Command
from fenolite.cli.errors import REGISTRY
from fenolite.cli.exitcodes import ExitCode
from fenolite.cli.explain import TABLES, all_codes, table_codes

PUBLIC_MODULES = ("fenolite.dsl", "fenolite.api")
PROTOCOL_METHODS = frozenset(
    {
        "__call__",
        "__getitem__",
        "__setitem__",
        "__iter__",
        "__next__",
        "__len__",
        "__contains__",
        "__enter__",
        "__exit__",
        "__add__",
        "__radd__",
        "__sub__",
        "__rsub__",
        "__mul__",
        "__rmul__",
        "__truediv__",
        "__rtruediv__",
        "__neg__",
        "__pos__",
        "__or__",
        "__and__",
        "__invert__",
        "__matmul__",
        "__bool__",
        "__eq__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
    }
)


@dataclass(frozen=True)
class Surface:
    """JSON data describing a prepared v1 boundary; it does not activate the v1 contract."""

    data: Mapping[str, Any]

    def to_json(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(json.dumps(self.data, ensure_ascii=False)))

    @classmethod
    def from_json(cls, data: str | Mapping[str, Any]) -> Surface:
        raw: Any = json.loads(data) if isinstance(data, str) else dict(data)
        if not isinstance(raw, dict):
            raise ValueError("a surface must be an object")
        typed = cast(dict[str, Any], raw)
        if any(
            not isinstance(typed.get(key), dict)
            for key in ("commands", "exit_codes", "fen_codes", "issue_codes", "library")
        ):
            raise ValueError("a surface requires commands, exit_codes, fen_codes, issue_codes and library")
        return cls(typed)


ChangeKind = Literal[
    "added",
    "removed",
    "narrowed",
    "default-changed",
    "type-changed",
    "required-added",
    "severity-raised",
    "severity-lowered",
]


@dataclass(frozen=True, slots=True)
class SurfaceChange:
    kind: ChangeKind
    path: str
    before: Any
    after: Any
    breaking: bool


def _version(value: object) -> tuple[int, int, int]:
    found = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?", str(value))
    return (0, 0, 0) if found is None else (int(found[1]), int(found[2]), int(found[3] or 0))


def _arity(value: Any) -> tuple[int, int | None, bool]:
    if isinstance(value, int):
        return value, value, value != 0
    return {
        None: (1, 1, False),
        "?": (0, 1, False),
        "*": (0, None, True),
        "+": (1, None, True),
        argparse.REMAINDER: (0, None, True),
        argparse.PARSER: (1, None, True),
    }.get(value, (0, 0, False))


def surface_changes(before: Surface, after: Surface) -> tuple[SurfaceChange, ...]:
    """Compare caller-visible declarations. An experimental label cannot withdraw an old guarantee."""
    left, right = before.to_json(), after.to_json()
    changes: list[SurfaceChange] = []

    def exempt(items: Sequence[Mapping[str, Any]], kind: ChangeKind) -> bool:
        if any(item.get("experimental", False) for item in items):
            return True
        for item in items:
            deprecated = item.get("deprecated")
            since = (
                cast(Mapping[str, Any], deprecated).get("since")
                if isinstance(deprecated, dict)
                else deprecated
            )
            if since and _version(since) <= _version(left.get("version")):
                if kind != "removed" and _version(right.get("version"))[0] >= 1:
                    return True
                if kind == "removed" and _version(right.get("version"))[0] >= 2:
                    return True
        return False

    def add(
        kind: ChangeKind,
        path: str,
        old: Any,
        new: Any,
        *,
        breaking: bool = True,
        items: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        changes.append(SurfaceChange(kind, path, old, new, breaking and not exempt(items, kind)))

    def stability(
        old: Mapping[str, Any], new: Mapping[str, Any], path: str, parents: Sequence[Mapping[str, Any]]
    ) -> None:
        if not old.get("experimental", False) and new.get("experimental", False):
            add("type-changed", path + " experimental", False, True, items=parents)

    def mapping(
        old: Mapping[str, Any],
        new: Mapping[str, Any],
        path: str,
        parents: Sequence[Mapping[str, Any]],
        compare: Callable[[Any, Any, str, Sequence[Mapping[str, Any]]], None],
    ) -> None:
        for name in sorted(old.keys() - new.keys()):
            item: Mapping[str, Any] = (
                cast(Mapping[str, Any], old[name]) if isinstance(old[name], dict) else {}
            )
            add("removed", f"{path}{name}", old[name], None, items=(*parents, item))
        for name in sorted(new.keys() - old.keys()):
            add("added", f"{path}{name}", None, new[name], breaking=False)
        for name in sorted(old.keys() & new.keys()):
            compare(old[name], new[name], f"{path}{name}", parents)

    def parameters(
        old: Sequence[Mapping[str, Any]],
        new: Sequence[Mapping[str, Any]],
        path: str,
        parents: Sequence[Mapping[str, Any]],
    ) -> None:
        a, b = {p["name"]: p for p in old}, {p["name"]: p for p in new}
        positional = {"POSITIONAL_ONLY", "POSITIONAL_OR_KEYWORD"}
        old_positions = {p["name"]: n for n, p in enumerate(p for p in old if p["kind"] in positional)}
        new_positions = {p["name"]: n for n, p in enumerate(p for p in new if p["kind"] in positional)}
        for name in sorted(a.keys() - b.keys()):
            add("removed", f"{path}({name})", a[name], None, items=parents)
        for name in sorted(b.keys() - a.keys()):
            required = b[name].get("required", False)
            add(
                "required-added" if required else "added",
                f"{path}({name})",
                None,
                b[name],
                breaking=required,
                items=parents,
            )
        for name in sorted(a.keys() & b.keys()):
            first, last = a[name], b[name]
            where = f"{path}({name})"
            if first.get("kind") != last.get("kind"):
                add("type-changed", where, first.get("kind"), last.get("kind"), items=parents)
            if name in old_positions and name in new_positions and old_positions[name] != new_positions[name]:
                add("type-changed", where, old_positions[name], new_positions[name], items=parents)
            if not first.get("required", False) and last.get("required", False):
                add("required-added", where, False, True, items=parents)
            elif not first.get("required", False) and first.get("default") != last.get("default"):
                add("default-changed", where, first.get("default"), last.get("default"), items=parents)
            if first.get("annotation") != last.get("annotation"):
                add(
                    "type-changed" if first.get("annotation") is not None else "added",
                    where + " type",
                    first.get("annotation"),
                    last.get("annotation"),
                    breaking=first.get("annotation") is not None,
                    items=parents,
                )

    def field(
        old: Mapping[str, Any], new: Mapping[str, Any], path: str, parents: Sequence[Mapping[str, Any]]
    ) -> None:
        if old.get("annotation") != new.get("annotation"):
            add(
                "type-changed" if old.get("annotation") is not None else "added",
                path,
                old.get("annotation"),
                new.get("annotation"),
                breaking=old.get("annotation") is not None,
                items=parents,
            )
        if old.get("value") != new.get("value"):
            add("default-changed", path, old.get("value"), new.get("value"), items=parents)
        if old.get("writable", False) and not new.get("writable", False):
            add("narrowed", path, True, False, items=parents)

    def callable_(
        old: Mapping[str, Any], new: Mapping[str, Any], path: str, parents: Sequence[Mapping[str, Any]]
    ) -> None:
        parameters(old.get("parameters", ()), new.get("parameters", ()), path, parents)

    def export(
        old: Mapping[str, Any], new: Mapping[str, Any], path: str, parents: Sequence[Mapping[str, Any]]
    ) -> None:
        ancestry = (*parents, old)
        stability(old, new, path, parents)
        if old.get("kind") != new.get("kind"):
            add("type-changed", path, old.get("kind"), new.get("kind"), items=ancestry)
            return
        kind = old.get("kind")
        if kind in {"function", "class"}:
            callable_(old, new, path, ancestry)
        if kind == "class":
            mapping(old.get("fields", {}), new.get("fields", {}), path + ".", ancestry, field)
            mapping(old.get("methods", {}), new.get("methods", {}), path + ".", ancestry, callable_)
            mapping(
                old.get("values", {}),
                new.get("values", {}),
                path + ".",
                ancestry,
                lambda a, b, p, context: add("default-changed", p, a, b, items=context) if a != b else None,
            )
        elif kind == "namespace":
            mapping(old.get("members", {}), new.get("members", {}), path + ".", ancestry, export)
        elif kind == "constant" and old.get("value") != new.get("value"):
            add("default-changed", path, old.get("value"), new.get("value"), items=ancestry)
        elif kind == "alias" and old.get("annotation") != new.get("annotation"):
            add("type-changed", path, old.get("annotation"), new.get("annotation"), items=ancestry)

    def option(
        old: Mapping[str, Any], new: Mapping[str, Any], path: str, parents: Sequence[Mapping[str, Any]]
    ) -> None:
        ancestry = (*parents, old)
        stability(old, new, path, parents)
        for key in ("type", "positional"):
            if old.get(key) != new.get(key):
                add("type-changed", path, old.get(key), new.get(key), items=ancestry)
        if old.get("default") != new.get("default"):
            add("default-changed", path, old.get("default"), new.get("default"), items=ancestry)
        if not old.get("required", False) and new.get("required", False):
            add("required-added", path, False, True, items=ancestry)
        a, b = old.get("choices"), new.get("choices")
        if a != b:
            removed = (
                a is None and b is not None or a is not None and b is not None and any(x not in b for x in a)
            )
            removed_choices = [] if a is None or b is None else [x for x in a if x not in b]
            experimental = old.get("experimental_choices", ())
            only_experimental = bool(removed_choices) and all(x in experimental for x in removed_choices)
            add(
                "narrowed" if removed else "added",
                path,
                a,
                b,
                breaking=bool(removed and not only_experimental),
                items=ancestry,
            )
        for choice in new.get("experimental_choices", ()):
            if choice not in old.get("experimental_choices", ()) and choice in (a or ()):
                add("type-changed", path + " experimental choice", choice, choice, items=parents)
        if old.get("nargs") != new.get("nargs"):
            old_min, old_max, old_list = _arity(old.get("nargs"))
            new_min, new_max, new_list = _arity(new.get("nargs"))
            narrowed = new_min > old_min or new_max is not None and (old_max is None or new_max < old_max)
            add(
                "type-changed" if old_list != new_list else "narrowed" if narrowed else "added",
                path + " nargs",
                old.get("nargs"),
                new.get("nargs"),
                breaking=old_list != new_list or narrowed,
                items=ancestry,
            )

    def command(
        old: Mapping[str, Any], new: Mapping[str, Any], path: str, parents: Sequence[Mapping[str, Any]]
    ) -> None:
        ancestry = (*parents, old)
        stability(old, new, path, parents)
        for key, kind in (("mutates", "type-changed"), ("default_limit", "default-changed")):
            if old.get(key) != new.get(key):
                add(cast(ChangeKind, kind), path + " " + key, old.get(key), new.get(key), items=ancestry)
        a, b = old.get("paged"), new.get("paged")
        if a != b:
            narrowed = a is not None and (b is None or not set(a.split("|")) <= set(b.split("|")))
            add("narrowed" if narrowed else "added", path + " paged", a, b, breaking=narrowed, items=ancestry)
        a_options, b_options = old.get("options", {}), new.get("options", {})
        for name in sorted(a_options.keys() - b_options.keys()):
            add("removed", f"{path} {name}", a_options[name], None, items=(*ancestry, a_options[name]))
        for name in sorted(b_options.keys() - a_options.keys()):
            aliases = b_options[name].get("aliases", ())
            required = b_options[name].get("required", False) and not any(
                alias in a_options for alias in aliases
            )
            add(
                "required-added" if required else "added",
                f"{path} {name}",
                None,
                b_options[name],
                breaking=required,
                items=ancestry,
            )
        for name in sorted(a_options.keys() & b_options.keys()):
            option(a_options[name], b_options[name], f"{path} {name}", ancestry)

    mapping(left["commands"], right["commands"], "", (), command)
    for key in ("exit_codes", "fen_codes"):
        mapping(
            left[key],
            right[key],
            key + " ",
            (),
            lambda a, b, p, context: add("type-changed", p, a, b) if a != b else None,
        )

    def severity(
        old: Mapping[str, Any], new: Mapping[str, Any], path: str, parents: Sequence[Mapping[str, Any]]
    ) -> None:
        stability(old, new, path, parents)
        a, b = set(old["severities"]), set(new["severities"])
        if a == b:
            return
        rank = {"info": 0, "warning": 1, "error": 2}
        raised = any(rank[value] > max((rank[x] for x in a), default=-1) for value in b)
        raised |= any(any(rank[y] > rank[x] for y in b) for x in a - b)
        add(
            "severity-raised" if raised else "severity-lowered",
            path,
            sorted(a),
            sorted(b),
            breaking=raised,
            items=(*parents, old),
        )

    mapping(left["issue_codes"], right["issue_codes"], "issue_codes ", (), severity)
    for module in sorted(left["library"].keys() - right["library"].keys()):
        add("removed", module, left["library"][module], None)
    for module in sorted(right["library"].keys() - left["library"].keys()):
        add("added", module, None, right["library"][module], breaking=False)
    for module in sorted(left["library"].keys() & right["library"].keys()):
        mapping(left["library"][module], right["library"][module], module + ".", (), export)
    return tuple(changes)


def _value(value: Any) -> Any:
    if value is inspect.Parameter.empty:
        return {"required": True}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return _value(value.value)
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _value(item) for key, item in cast(Mapping[object, Any], value).items()}
    if isinstance(value, (tuple, list)):
        return [_value(item) for item in cast(Sequence[Any], value)]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_value(item) for item in cast(set[Any] | frozenset[Any], value)),
            key=lambda item: json.dumps(item, sort_keys=True),
        )
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: _value(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if callable(value):
        return {"callable": getattr(value, "__qualname__", type(value).__name__)}
    # Object addresses and implementation import paths are not a release boundary.
    if re.fullmatch(r"<[^>]+ object at 0x[0-9a-fA-F]+>", repr(value)):
        return {"opaque": True}
    text = re.sub(r" at 0x[0-9a-fA-F]+", "", repr(value))
    text = re.sub(r"(?:[A-Za-z_]\w*\.)+", "", text)
    return {"value": text}


def _annotation(value: Any) -> str | None:
    if value is inspect.Parameter.empty:
        return None
    if isinstance(value, str):
        return value
    if value is type(None):
        return "None"
    origin = typing.get_origin(value)
    if origin is not None:
        name = getattr(origin, "__name__", str(origin).removeprefix("typing."))
        return f"{name}[{', '.join(_annotation(item) or str(item) for item in typing.get_args(value))}]"
    return str(getattr(value, "__name__", str(value).removeprefix("typing.")))


def _signature(value: Any, *, method: bool = False) -> list[dict[str, Any]]:
    try:
        signature = inspect.signature(value)
    except (TypeError, ValueError):
        return []  # a built-in exception without its own constructor
    return [
        {
            "name": parameter.name,
            "kind": parameter.kind.name,
            "required": parameter.default is inspect.Parameter.empty
            and parameter.kind not in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD),
            "default": None if parameter.default is inspect.Parameter.empty else _value(parameter.default),
            "annotation": _annotation(parameter.annotation),
        }
        for parameter in signature.parameters.values()
        if not (method and parameter.name in {"self", "cls"}) and not parameter.name.startswith("_")
    ]


def _assigned_fields(cls: type) -> dict[str, Any]:
    found: dict[str, Any] = {}
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(cls)))
    except (OSError, TypeError, IndentationError, SyntaxError):
        return found

    def descendants(node: ast.AST) -> Iterator[ast.AST]:
        if isinstance(node, ast.ClassDef):
            return
        yield node
        for child in ast.iter_child_nodes(node):
            yield from descendants(child)

    body: list[ast.stmt] = []
    for statement in tree.body:
        if isinstance(statement, ast.ClassDef):
            body = statement.body
            break
    for node in (node for member in body for node in descendants(member)):
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and not target.attr.startswith("_")
            ):
                found[target.attr] = {
                    "annotation": ast.unparse(node.annotation) if isinstance(node, ast.AnnAssign) else None
                }
    return found


def _class(cls: type) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    methods: dict[str, Any] = {}
    for parent in reversed(cls.__mro__):
        if parent.__module__ == "builtins":
            continue
        fields.update(_assigned_fields(parent))
        annotations = inspect.get_annotations(parent, eval_str=False)
        for name, annotation in annotations.items():
            if not name.startswith("_"):
                fields[name] = {"annotation": _annotation(annotation)}
        for name, raw in vars(parent).items():
            if name.startswith("_") and name not in PROTOCOL_METHODS:
                continue
            if isinstance(raw, property):
                fields[name] = {
                    "annotation": None
                    if raw.fget is None
                    else _annotation(inspect.signature(raw.fget).return_annotation),
                    "writable": raw.fset is not None,
                }
            elif isinstance(raw, (classmethod, staticmethod)):
                methods[name] = {"parameters": _signature(cast(Any, raw).__func__, method=True)}
            elif inspect.isfunction(raw):
                methods[name] = {"parameters": _signature(raw, method=True)}
            elif not name.startswith("_") and not inspect.ismethoddescriptor(raw):
                fields.setdefault(name, {"annotation": None, "value": _value(raw)})
    if dataclasses.is_dataclass(cls):
        for field in dataclasses.fields(cls):
            if not field.name.startswith("_"):
                fields[field.name] = {"annotation": _annotation(field.type)}
    enum_values = (
        {name: _value(member.value) for name, member in cls.__members__.items()}
        if issubclass(cls, Enum)
        else {}
    )
    return {
        "kind": "class",
        "parameters": _signature(cls),
        "fields": dict(sorted(fields.items())),
        "methods": dict(sorted(methods.items())),
        **({"values": enum_values} if enum_values else {}),
    }


def _export(value: Any, seen: frozenset[str] = frozenset()) -> dict[str, Any]:
    if typing.get_origin(value) is not None:
        return {"kind": "alias", "annotation": _annotation(value)}
    if inspect.isclass(value):
        return _class(value)
    if inspect.isroutine(value):
        return {"kind": "function", "parameters": _signature(value)}
    if isinstance(value, ModuleType):
        names = getattr(value, "__all__", ())
        if value.__name__ in seen:
            return {"kind": "namespace"}
        return {
            "kind": "namespace",
            "members": {
                name: _export(getattr(value, name), seen | {value.__name__}) for name in sorted(names)
            },
        }
    return {"kind": "constant", "value": _value(value)}


def library_surface() -> dict[str, Any]:
    """Only explicit export namespaces; neither module internals nor implementation paths are frozen."""
    found: dict[str, Any] = {}
    for name in PUBLIC_MODULES:
        module = importlib.import_module(name)
        exports = cast(Sequence[str], module.__all__)
        found[name] = {export: _export(getattr(module, export)) for export in sorted(exports)}
    return found


def _actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [a for a in parser._actions if not isinstance(a, argparse._SubParsersAction)]  # pyright: ignore[reportPrivateUsage]


def _children(parser: argparse.ArgumentParser) -> Mapping[str, argparse.ArgumentParser]:
    for action in parser._actions:  # pyright: ignore[reportPrivateUsage]
        if isinstance(action, argparse._SubParsersAction):  # pyright: ignore[reportPrivateUsage]
            return cast(Mapping[str, argparse.ArgumentParser], cast(Any, action).choices)
    return {}


def _options(parser: argparse.ArgumentParser, *, omit: frozenset[str] = frozenset()) -> dict[str, Any]:
    found: dict[str, Any] = {}
    marked = cast(Mapping[str, Any], getattr(parser, "_fenolite_deprecations", {}))
    for action in _actions(parser):
        keys = list(action.option_strings) or [action.dest]
        value_type = (
            "boolean"
            if action.nargs == 0
            else "integer"
            if action.type is int
            else "number"
            if action.type is float
            else "string"
        )
        for key in keys:
            if key in omit:
                continue
            found[key] = {
                "aliases": keys,
                "type": value_type,
                "default": _value(action.default),
                # Python3.11 marks '*' positionals required internally, but accepts zero values.
                "required": bool(action.required) and (bool(action.option_strings) or action.nargs != "*"),
                "nargs": action.nargs,
                "choices": None
                if action.choices is None
                else sorted(
                    (_value(choice) for choice in action.choices),
                    key=lambda item: json.dumps(item, sort_keys=True),
                ),
                "positional": not action.option_strings,
                "experimental": False,
                "deprecated": _value(marked.get(key)),
            }
    return dict(sorted(found.items()))


def _experimental_codes(features: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    """A stable shared table owner keeps a code stable, even when a writer also uses it."""
    names = {feature.get("name") for feature in features}
    tables: list[tuple[str, Mapping[str, object]]] = []
    roots: set[str] = set()
    for module_name, attribute in TABLES:
        module = importlib.import_module(module_name)
        tables.append((module_name, cast(Mapping[str, object], getattr(module, attribute))))
        for name in ("EXPERIMENTAL", "PCB_EXPERIMENTAL"):
            declaration = getattr(module, name, None)
            if (
                isinstance(declaration, Mapping)
                and cast(Mapping[str, object], declaration).get("name") in names
            ):
                roots.add(module_name)
    owners: dict[str, list[bool]] = {}
    for module_name, table in tables:
        experimental = any(
            module_name == root or module_name.startswith(root + ".") or module_name.startswith(root + "_")
            for root in roots
        )
        for code in table_codes(table):
            owners.setdefault(code, []).append(experimental)
    return frozenset(code for code, flags in owners.items() if flags and all(flags))


def cli_surface(
    commands: Mapping[str, Command], *, experimental: Sequence[Mapping[str, Any]] | None = None
) -> Surface:
    from fenolite import api
    from fenolite.cli.main import build_parser

    if experimental is None:
        reply = api.run("capabilities", "--no-tools")
        if reply.exit_code:
            raise ValueError("capabilities could not describe its experimental selectors")
        experimental = cast(Sequence[Mapping[str, Any]], reply.result.get("experimental", ()))
    parser = build_parser(dict(commands))
    experimental_codes = _experimental_codes(experimental)
    shared = _options(parser)
    children = _children(parser)
    entries: dict[str, Any] = {"*": {"options": shared}}
    for name, command in sorted(commands.items()):
        if command.hidden:
            continue
        options = _options(children[name], omit=frozenset(shared))
        for feature in experimental:
            if feature.get("command") != name:
                continue
            selector = str(feature.get("option", "")).split(maxsplit=1)
            if selector and selector[0] in options:
                if len(selector) == 1:
                    options[selector[0]]["experimental"] = True
                else:
                    choices = options[selector[0]].setdefault("experimental_choices", [])
                    value = next(
                        (
                            choice
                            for choice in options[selector[0]]["choices"] or ()
                            if str(choice) == selector[1]
                        ),
                        selector[1],
                    )
                    if value not in choices:
                        choices.append(value)
        entries[name] = {
            "mutates": command.mutates,
            "paged": command.paged,
            "default_limit": command.default_limit,
            "experimental": False,
            "deprecated": None
            if command.deprecated is None
            else {"since": command.deprecated, "use": command.replacement},
            "options": options,
        }
    return Surface(
        {
            "contract": "v1",
            "active_contract": getattr(cli_api, "CONTRACT_VERSION", "v0"),
            "version": __version__,
            "commands": entries,
            "exit_codes": {code.name: int(code) for code in ExitCode},
            "fen_codes": {code: int(spec.exit_code) for code, spec in sorted(REGISTRY.items())},
            "issue_codes": {
                code: {"severities": list(severities), "experimental": code in experimental_codes}
                for code, severities in all_codes().items()
                if not code.startswith("FEN-")
            },
            "library": library_surface(),
        }
    )


def review(surface: Surface, root: Path, commands: Mapping[str, Command], *, keep_all: bool = False) -> str:
    """Static references assist the keep/rename/drop review; mentions are not execution coverage."""

    def text(folder: Path, suffix: str) -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in sorted(folder.rglob(f"*{suffix}")))

    tests = text(root / "tests", ".py")
    guide = text(root / "src/fenolite/agent/skill", ".md")
    docs = (root / "docs/cli-contract.md").read_text(encoding="utf-8")
    decision = "keep" if keep_all else "pending"
    rows = [
        "# Contract pre-freeze review",
        "",
        "Static mentions only; this is not runtime coverage.",
        "",
        "| Item | Test mention | Example | Guide | Contract docs | Decision |",
        "|---|---|---|---|---|---|",
    ]
    for name, entry in surface.data["commands"].items():
        example = " ".join(commands[name].example_args) if name in commands else ""
        for flag in entry["options"]:
            cells = ["yes" if flag in source else "no" for source in (tests, example, guide, docs)]
            rows.append(f"| `{name} {flag}` | " + " | ".join(cells) + f" | {decision} |")
    rows += ["", "## Hidden commands", ""]
    rows += [
        f"- `{name}`: {decision}; hidden, outside the frozen surface."
        for name, command in sorted(commands.items())
        if command.hidden
    ]
    rows += [
        "",
        "## Issue codes with no literal test mention",
        "",
        "Dynamic families may be tested indirectly; no execution claim follows from this list.",
        "",
    ]
    rows += [f"- `{code}`: {decision}." for code in surface.data["issue_codes"] if code not in tests]
    rows += ["", "## Public Python exports", ""]

    def exports(entries: Mapping[str, Any], prefix: str) -> None:
        for name, entry in entries.items():
            path = f"{prefix}.{name}"
            rows.append(f"- `{path}`: {decision}.")
            for category in ("parameters", "fields", "methods", "values"):
                for item in entry.get(category, ()):
                    key = cast(Mapping[str, Any], item)["name"] if isinstance(item, dict) else item
                    rows.append(f"  - `{path} {category} {key}`: {decision}.")
            exports(entry.get("members", {}), path)

    for name, entries in surface.data["library"].items():
        exports(entries, name)
    return "\n".join(rows) + "\n"
