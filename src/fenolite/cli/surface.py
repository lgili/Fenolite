# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The contract surface of the ``fenolite`` command and of its public library, and the judge of its changes
(capability cli-contract, "Contract surface", "Stability of the 1.x contract"; change c0216).

:func:`cli_surface` reads the registered commands, their parsers and the code registries;
``docs/cli-surface.json`` is its :meth:`Surface.to_json`, written by ``tools/gen_cli_surface.py``.
:func:`surface_changes` compares two surfaces and tells an addition from a breaking change.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import importlib
import inspect
import json
import re
import types
import typing
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from fenolite.cli.api import Command

SURFACE_CONTRACT = "v1"
"""The contract that ``docs/cli-surface.json`` describes: the one frozen by the release of ``1.0.0``."""
GLOBAL = "*"
"""The entry of ``commands`` that holds the options every command accepts."""
LIBRARY_MODULES = ("fenolite.api", "fenolite.dsl")
"""The modules whose ``__all__`` is frozen with the CLI (the maintainer's answer of 2026-10-27)."""
EXPERIMENTAL_TABLES = frozenset(
    {
        ("fenolite.lens.altium", "ALTIUM_ISSUE_CODES"),
        ("fenolite.lens.altium_copper", "COPPER_ISSUE_CODES"),
        ("fenolite.lens.altium_schematic", "ISSUE_CODES"),
    }
)
"""The issue-code tables of the experimental Altium writers (``result.experimental`` of ``capabilities``). An
issue code is experimental when every table that holds it is one of these."""
SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}
_ADDRESS = re.compile(r" at 0x[0-9a-fA-F]+")

Kind = Literal[
    "added",
    "removed",
    "narrowed",
    "default-changed",
    "type-changed",
    "required-added",
    "severity-raised",
    "severity-lowered",
]
KINDS: tuple[Kind, ...] = (
    "added",
    "removed",
    "narrowed",
    "default-changed",
    "type-changed",
    "required-added",
    "severity-raised",
    "severity-lowered",
)


@dataclass(frozen=True, slots=True)
class Surface:
    """The contract surface as data: the shape of ``docs/cli-surface.json`` (design c0216, decision 1)."""

    commands: Mapping[str, Mapping[str, Any]]
    exit_codes: Mapping[str, int]
    fen_codes: Mapping[str, int]
    issue_codes: Mapping[str, Mapping[str, Any]]
    library: Mapping[str, Mapping[str, Mapping[str, Any]]]
    contract: str = SURFACE_CONTRACT

    def to_json(self) -> dict[str, Any]:
        """The surface as plain JSON values, every mapping with its keys in sorted order."""
        return cast(
            dict[str, Any],
            _sorted(
                {
                    "contract": self.contract,
                    "commands": self.commands,
                    "exit_codes": self.exit_codes,
                    "fen_codes": self.fen_codes,
                    "issue_codes": self.issue_codes,
                    "library": self.library,
                }
            ),
        )

    def dumps(self) -> str:
        """The text of ``docs/cli-surface.json``: sorted keys, two-space indent, LF, a final newline."""
        return json.dumps(self.to_json(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Surface:
        return cls(
            commands=data["commands"],
            exit_codes=data["exit_codes"],
            fen_codes=data["fen_codes"],
            issue_codes=data["issue_codes"],
            library=data["library"],
            contract=data["contract"],
        )


@dataclass(frozen=True, slots=True)
class SurfaceChange:
    """One difference between two surfaces. ``path`` names the item: ``check --gate``, ``build --target
    altium`` (a choice), ``* --json`` (a global option), ``exit:FINDINGS``, ``FEN-3001``, an issue code, or
    ``fenolite.api.convert(name)`` (a library parameter)."""

    kind: Kind
    path: str
    before: Any = None
    after: Any = None
    breaking: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "before": self.before,
            "after": self.after,
            "breaking": self.breaking,
        }

    def __str__(self) -> str:
        mark = "BREAKING " if self.breaking else ""
        return f"{mark}{self.kind}: {self.path} ({self.before!r} -> {self.after!r})"


# --------------------------------------------------------------------------------------------- generation


def _sorted(value: Any) -> Any:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, Any], value)
        return {key: _sorted(mapping[key]) for key in sorted(mapping)}
    if isinstance(value, list | tuple):
        return [_sorted(item) for item in cast(Sequence[Any], value)]
    return value


def _plain(value: Any) -> Any:
    """A default value as JSON: scalars as they are, sequences item by item, anything else as its repr
    without a memory address."""
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, enum.Enum):
        return f"{type(value).__name__}.{value.name}"
    if isinstance(value, list | tuple | frozenset | set):
        items = [_plain(item) for item in cast(Sequence[Any], value)]
        return sorted(items, key=repr) if isinstance(value, frozenset | set) else items
    return _ADDRESS.sub("", repr(value))


def _type_name(action: argparse.Action) -> str:
    if isinstance(action, argparse._StoreTrueAction | argparse._StoreFalseAction):  # pyright: ignore[reportPrivateUsage]
        return "flag"
    if isinstance(action, argparse._CountAction):  # pyright: ignore[reportPrivateUsage]
        return "count"
    if isinstance(action, argparse._StoreConstAction):  # pyright: ignore[reportPrivateUsage]
        return "const"
    if isinstance(action, argparse._VersionAction):  # pyright: ignore[reportPrivateUsage]
        return "version"
    kind = action.type
    if kind is None:
        return "str"
    return str(getattr(kind, "__name__", type(kind).__name__))


def _key(action: argparse.Action) -> str:
    """The name of an argument in the surface: its first long flag, or ``<dest>`` for a positional."""
    if not action.option_strings:
        return f"<{action.dest}>"
    longs = [flag for flag in action.option_strings if flag.startswith("--")]
    return (longs or list(action.option_strings))[0]


def _option(action: argparse.Action, position: int | None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": _type_name(action),
        "choices": None if action.choices is None else [str(c) for c in cast(Sequence[Any], action.choices)],
        "default": None if action.default is argparse.SUPPRESS else _plain(action.default),
        "required": bool(action.required) if action.option_strings else action.nargs not in ("?", "*"),
        "nargs": action.nargs,
        "experimental": False,
        "experimental_choices": [],
        "deprecated": None,
    }
    if isinstance(action, argparse._AppendAction):  # pyright: ignore[reportPrivateUsage]
        entry["nargs"] = "append" if action.nargs is None else action.nargs
    aliases = sorted(flag for flag in action.option_strings if flag != _key(action))
    if aliases:
        entry["aliases"] = aliases
    if position is not None:
        entry["position"] = position
    return entry


def _arguments(parser: argparse.ArgumentParser, skip: frozenset[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    position = 0
    for action in parser._actions:  # pyright: ignore[reportPrivateUsage]
        if isinstance(action, argparse._HelpAction | argparse._SubParsersAction):  # pyright: ignore[reportPrivateUsage]
            continue
        key = _key(action)
        if key in skip:
            continue
        if action.option_strings:
            found[key] = _option(action, None)
        else:
            found[key] = _option(action, position)
            position += 1
    return found


def _groups(parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    groups = [
        {"options": sorted(_key(a) for a in group._group_actions), "required": bool(group.required)}  # pyright: ignore[reportPrivateUsage]
        for group in parser._mutually_exclusive_groups  # pyright: ignore[reportPrivateUsage]
    ]
    return sorted(groups, key=lambda g: "|".join(g["options"]))


def _mark_experimental(commands: dict[str, dict[str, Any]], features: Sequence[Mapping[str, Any]]) -> None:
    """Mark what ``result.experimental`` names: a whole option (``--x``), one choice (``--x value``), and
    the options of the same command whose flag starts with ``--<value>-`` (they only act with that choice:
    ``--altium-pour`` with ``--target altium``). A feature without an option marks its command."""
    for feature in features:
        entry = commands.get(str(feature.get("command", "")))
        if entry is None:
            continue
        words = str(feature.get("option") or "").split()
        if not words:
            entry["experimental"] = True
            continue
        option = entry["options"].get(words[0])
        if option is None:
            continue
        if len(words) == 1:
            option["experimental"] = True
            continue
        choice = words[1]
        if choice not in option["experimental_choices"]:
            option["experimental_choices"] = sorted([*option["experimental_choices"], choice])
        for flag, other in entry["options"].items():
            if flag.startswith(f"--{choice}-"):
                other["experimental"] = True


def _command_entry(command: Command, parser: argparse.ArgumentParser, skip: frozenset[str]) -> dict[str, Any]:
    return {
        "mutates": command.mutates,
        "paged": command.paged,
        "default_limit": command.default_limit,
        "experimental": False,
        "deprecated": None,
        "options": _arguments(parser, skip),
        "exclusive": _groups(parser),
    }


def _issue_codes() -> dict[str, dict[str, Any]]:
    from fenolite.cli.errors import REGISTRY
    from fenolite.cli.explain import SEVERITY_ORDER, TABLES
    from fenolite.cli.explain import _spelled as spelled  # pyright: ignore[reportPrivateUsage]

    severities: dict[str, set[str]] = {}
    stable: set[str] = set()
    for module, name in TABLES:
        table = cast(Mapping[str, Any], getattr(importlib.import_module(module), name))
        for key, value in table.items():
            found = (value,) if isinstance(value, str) else tuple(cast(Sequence[str], value))
            for code in spelled(key):
                if code in REGISTRY:
                    continue
                severities.setdefault(code, set()).update(found)
                if (module, name) not in EXPERIMENTAL_TABLES:
                    stable.add(code)
    return {
        code: {
            "severities": [s for s in SEVERITY_ORDER if s in severities[code]],
            "experimental": code not in stable,
            "deprecated": None,
        }
        for code in sorted(severities)
    }


# ---------------------------------------------------------------------------------------------- library


def _parameters(target: Callable[..., Any], *, drop_self: bool = False) -> dict[str, dict[str, Any]]:
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return {}
    parameters = list(signature.parameters.values())
    if drop_self and parameters and parameters[0].name in ("self", "cls"):
        parameters = parameters[1:]
    found: dict[str, dict[str, Any]] = {}
    for position, parameter in enumerate(parameters):
        has_default = parameter.default is not inspect.Parameter.empty
        found[parameter.name] = {
            "kind": parameter.kind.name.lower(),
            "position": position,
            "has_default": has_default,
            "default": _plain(parameter.default) if has_default else None,
        }
    return found


def _own(cls: type) -> Iterator[type]:
    """The classes of ``cls``'s MRO that Fenolite defines."""
    for base in cls.__mro__:
        if base.__module__.split(".")[0] == "fenolite":
            yield base


def _class(value: Any) -> dict[str, Any]:
    cls = cast(type, value)
    fields: dict[str, dict[str, Any]] = {}
    if dataclasses.is_dataclass(value):
        for item in dataclasses.fields(cast(Any, value)):
            if item.name.startswith("_"):
                continue
            has_default = (
                item.default is not dataclasses.MISSING or item.default_factory is not dataclasses.MISSING
            )
            fields[item.name] = {"kind": "field", "has_default": has_default}
    methods: dict[str, dict[str, Any]] = {}
    for base in reversed(list(_own(cls))):
        for name, member in cast(Mapping[str, Any], vars(base)).items():
            if name.startswith("_"):
                continue
            if isinstance(member, property):
                fields[name] = {"kind": "property", "has_default": False}
            elif isinstance(member, staticmethod):
                methods[name] = {"parameters": _parameters(cast(Any, member).__func__)}
            elif isinstance(member, classmethod):
                methods[name] = {"parameters": _parameters(cast(Any, member).__func__, drop_self=True)}
            elif inspect.isfunction(member):
                methods[name] = {"parameters": _parameters(member, drop_self=True)}
    if isinstance(cls, enum.EnumMeta):
        enum_type = cast(type[enum.Enum], cls)
        return {"kind": "enum", "members": sorted(member.name for member in enum_type)}
    entry: dict[str, Any] = {"kind": "class", "fields": fields, "methods": methods}
    if not issubclass(cls, BaseException) or "__init__" in vars(cls):
        entry["parameters"] = _parameters(cast(Any, value))
    return entry


def _describe(value: Any, *, depth: int = 0) -> dict[str, Any]:
    if isinstance(value, types.ModuleType):
        names = list(getattr(value, "__all__", ()))
        if depth > 0:
            return {"kind": "module", "names": sorted(names)}
        return {"kind": "module", "names": {n: _describe(getattr(value, n), depth=depth + 1) for n in names}}
    if inspect.isclass(value):
        return _class(value)
    if inspect.isfunction(value) or inspect.isbuiltin(value):
        return {"kind": "function", "parameters": _parameters(value)}
    if isinstance(value, types.UnionType) or typing.get_origin(value) is not None:
        return {"kind": "alias", "value": _ADDRESS.sub("", str(value))}
    return {"kind": "constant", "type": type(value).__name__}


def library_surface() -> dict[str, dict[str, dict[str, Any]]]:
    """Every name of the ``__all__`` of each module of :data:`LIBRARY_MODULES`, described."""
    found: dict[str, dict[str, dict[str, Any]]] = {}
    for module_name in LIBRARY_MODULES:
        module = importlib.import_module(module_name)
        found[module_name] = {name: _describe(getattr(module, name)) for name in module.__all__}
    return found


def cli_surface(commands: Mapping[str, Command]) -> Surface:
    """The surface of ``commands`` (usually :func:`fenolite.cli.api.discover`), of the code registries and
    of the library. Hidden commands are left out."""
    from fenolite.cli.cmd_capabilities import experimental_features
    from fenolite.cli.errors import REGISTRY
    from fenolite.cli.exitcodes import ExitCode
    from fenolite.cli.main import build_parser

    parser = build_parser(dict(commands))
    entries: dict[str, dict[str, Any]] = {
        GLOBAL: {
            "mutates": False,
            "paged": None,
            "default_limit": None,
            "experimental": False,
            "deprecated": None,
            "options": _arguments(parser, frozenset()),
            "exclusive": [],
        }
    }
    shared = frozenset(entries[GLOBAL]["options"])
    children: Mapping[str, argparse.ArgumentParser] = {}
    for action in parser._actions:  # pyright: ignore[reportPrivateUsage]
        if isinstance(action, argparse._SubParsersAction):  # pyright: ignore[reportPrivateUsage]
            children = cast(Mapping[str, argparse.ArgumentParser], action.choices)  # pyright: ignore[reportUnknownMemberType]
    for name, command in sorted(commands.items()):
        if command.hidden:
            continue
        entries[name] = _command_entry(command, children[name], shared)
    _mark_experimental(entries, experimental_features())
    return Surface(
        commands=entries,
        exit_codes={code.name: int(code) for code in ExitCode},
        fen_codes={code: int(spec.exit_code) for code, spec in sorted(REGISTRY.items())},
        issue_codes=_issue_codes(),
        library=library_surface(),
    )


# ------------------------------------------------------------------------------------------------- judge


def _change(kind: Kind, path: str, before: Any, after: Any, *, free: bool, breaking: bool) -> SurfaceChange:
    return SurfaceChange(kind, path, before, after, breaking and not free)


def _free(entry: Mapping[str, Any] | None) -> bool:
    """An item that may change: experimental, or deprecated in the baseline."""
    return entry is not None and (bool(entry.get("experimental")) or entry.get("deprecated") is not None)


def _options(
    name: str, before: Mapping[str, Any], after: Mapping[str, Any], free: bool
) -> list[SurfaceChange]:
    changes: list[SurfaceChange] = []
    old = cast(Mapping[str, Mapping[str, Any]], before.get("options", {}))
    new = cast(Mapping[str, Mapping[str, Any]], after.get("options", {}))
    for flag in sorted(set(old) | set(new)):
        path = f"{name} {flag}"
        a, b = old.get(flag), new.get(flag)
        if a is None and b is not None:
            required = bool(b.get("required"))
            kind: Kind = "required-added" if required else "added"
            changes.append(_change(kind, path, None, b, free=free, breaking=required))
            continue
        if b is None and a is not None:
            changes.append(_change("removed", path, a, None, free=free or _free(a), breaking=True))
            continue
        assert a is not None and b is not None
        item_free = free or _free(a)
        if a.get("type") != b.get("type") or a.get("nargs") != b.get("nargs"):
            was = {"type": a.get("type"), "nargs": a.get("nargs")}
            now = {"type": b.get("type"), "nargs": b.get("nargs")}
            changes.append(_change("type-changed", path, was, now, free=item_free, breaking=True))
        if a.get("position") != b.get("position"):
            changes.append(
                _change(
                    "type-changed", path, a.get("position"), b.get("position"), free=item_free, breaking=True
                )
            )
        if a.get("default") != b.get("default"):
            changes.append(
                _change(
                    "default-changed", path, a.get("default"), b.get("default"), free=item_free, breaking=True
                )
            )
        if not a.get("required") and b.get("required"):
            changes.append(_change("required-added", path, False, True, free=item_free, breaking=True))
        old_choices, new_choices = a.get("choices"), b.get("choices")
        experimental_choices = set(cast(Sequence[str], a.get("experimental_choices") or ()))
        if old_choices is not None or new_choices is not None:
            was_set = None if old_choices is None else set(cast(Sequence[str], old_choices))
            now_set = None if new_choices is None else set(cast(Sequence[str], new_choices))
            if was_set is None:  # free text became a list of choices
                changes.append(_change("narrowed", path, None, new_choices, free=item_free, breaking=True))
            elif now_set is None:  # a list of choices became free text: wider
                changes.append(_change("added", path, old_choices, None, free=item_free, breaking=False))
            else:
                for choice in sorted(was_set - now_set):
                    free_choice = item_free or choice in experimental_choices
                    changes.append(
                        _change("narrowed", f"{path} {choice}", choice, None, free=free_choice, breaking=True)
                    )
                for choice in sorted(now_set - was_set):
                    changes.append(
                        _change("added", f"{path} {choice}", None, choice, free=True, breaking=False)
                    )
        for key in ("experimental", "experimental_choices", "deprecated", "aliases"):
            if a.get(key) != b.get(key):
                gone = key == "aliases" and bool(set(a.get(key) or ()) - set(b.get(key) or ()))
                changes.append(
                    _change(
                        "removed" if gone else "added",
                        f"{path} [{key}]",
                        a.get(key),
                        b.get(key),
                        free=item_free,
                        breaking=gone or (key == "experimental" and bool(b.get(key)) and not a.get(key)),
                    )
                )
    old_groups = {
        "|".join(g["options"]): g for g in cast(Sequence[Mapping[str, Any]], before.get("exclusive", []))
    }
    new_groups = {
        "|".join(g["options"]): g for g in cast(Sequence[Mapping[str, Any]], after.get("exclusive", []))
    }
    for key in sorted(set(old_groups) | set(new_groups)):
        path = f"{name} ({key})"
        g_old, g_new = old_groups.get(key), new_groups.get(key)
        if g_old is None and g_new is not None:
            existing = any(flag in old for flag in g_new["options"])
            kind = "required-added" if g_new["required"] else ("narrowed" if existing else "added")
            changes.append(
                _change(kind, path, None, g_new, free=free, breaking=existing or g_new["required"])
            )
        elif g_new is None and g_old is not None:
            changes.append(_change("removed", path, g_old, None, free=free, breaking=False))
        elif g_old is not None and g_new is not None and g_new["required"] and not g_old["required"]:
            changes.append(_change("required-added", path, False, True, free=free, breaking=True))
    return changes


def _commands(before: Surface, after: Surface) -> list[SurfaceChange]:
    changes: list[SurfaceChange] = []
    for name in sorted(set(before.commands) | set(after.commands)):
        a, b = before.commands.get(name), after.commands.get(name)
        if a is None and b is not None:
            changes.append(
                _change("added", name, None, sorted(b.get("options", {})), free=True, breaking=False)
            )
            continue
        if b is None and a is not None:
            changes.append(
                _change("removed", name, sorted(a.get("options", {})), None, free=_free(a), breaking=True)
            )
            continue
        assert a is not None and b is not None
        free = _free(a)
        for key in ("mutates", "paged"):
            if a.get(key) != b.get(key):
                changes.append(
                    _change(
                        "type-changed", f"{name} [{key}]", a.get(key), b.get(key), free=free, breaking=True
                    )
                )
        if a.get("default_limit") != b.get("default_limit"):
            changes.append(
                _change(
                    "default-changed",
                    f"{name} [default_limit]",
                    a.get("default_limit"),
                    b.get("default_limit"),
                    free=free,
                    breaking=True,
                )
            )
        for key in ("experimental", "deprecated"):
            if a.get(key) != b.get(key):
                breaking = key == "experimental" and bool(b.get(key))
                changes.append(
                    _change("added", f"{name} [{key}]", a.get(key), b.get(key), free=free, breaking=breaking)
                )
        changes.extend(_options(name, a, b, free))
    return changes


def _codes(
    prefix: str,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    judge: Callable[[str, Any, Any], list[SurfaceChange]],
) -> list[SurfaceChange]:
    changes: list[SurfaceChange] = []
    for code in sorted(set(before) | set(after)):
        path = f"{prefix}{code}"
        a, b = before.get(code), after.get(code)
        if a is None:
            changes.append(_change("added", path, None, b, free=True, breaking=False))
        elif b is None:
            changes.append(
                _change(
                    "removed",
                    path,
                    a,
                    None,
                    free=_free(cast(Mapping[str, Any], a)) if isinstance(a, Mapping) else False,
                    breaking=True,
                )
            )
        else:
            changes.extend(judge(path, a, b))
    return changes


def _number(path: str, a: Any, b: Any) -> list[SurfaceChange]:
    if a == b:
        return []
    return [_change("type-changed", path, a, b, free=False, breaking=True)]


def _severity(path: str, a: Any, b: Any) -> list[SurfaceChange]:
    old = cast(Mapping[str, Any], a)
    new = cast(Mapping[str, Any], b)
    was = [SEVERITY_RANK[s] for s in cast(Sequence[str], old["severities"])] or [0]
    now = [SEVERITY_RANK[s] for s in cast(Sequence[str], new["severities"])] or [0]
    free = _free(old)
    changes: list[SurfaceChange] = []
    if max(now) > max(was) or min(now) > min(was):
        changes.append(
            _change("severity-raised", path, old["severities"], new["severities"], free=free, breaking=True)
        )
    elif old["severities"] != new["severities"]:
        changes.append(
            _change("severity-lowered", path, old["severities"], new["severities"], free=free, breaking=False)
        )
    for key in ("experimental", "deprecated"):
        if old.get(key) != new.get(key):
            breaking = key == "experimental" and bool(new.get(key))
            changes.append(
                _change("added", f"{path} [{key}]", old.get(key), new.get(key), free=free, breaking=breaking)
            )
    return changes


def _parameter_changes(path: str, old: Mapping[str, Any], new: Mapping[str, Any]) -> list[SurfaceChange]:
    changes: list[SurfaceChange] = []
    for name in sorted(set(old) | set(new)):
        where = f"{path}({name})"
        a, b = old.get(name), new.get(name)
        if a is None and b is not None:
            if b["has_default"] or b["kind"] in ("var_positional", "var_keyword"):
                changes.append(_change("added", where, None, b, free=False, breaking=False))
            else:
                changes.append(_change("required-added", where, None, b, free=False, breaking=True))
        elif b is None and a is not None:
            changes.append(_change("removed", where, a, None, free=False, breaking=True))
        elif a is not None and b is not None:
            positional = ("positional_only", "positional_or_keyword")
            moved = a["kind"] in positional and a.get("position") != b.get("position")
            if a["kind"] != b["kind"] or moved:
                changes.append(_change("type-changed", where, a, b, free=False, breaking=True))
            if a["has_default"] and not b["has_default"]:
                changes.append(_change("required-added", where, a, b, free=False, breaking=True))
            elif a.get("default") != b.get("default"):
                changes.append(
                    _change(
                        "default-changed",
                        where,
                        a.get("default"),
                        b.get("default"),
                        free=False,
                        breaking=False,
                    )
                )
    return changes


def _name_changes(path: str, a: Mapping[str, Any], b: Mapping[str, Any]) -> list[SurfaceChange]:
    if a.get("kind") != b.get("kind"):
        return [_change("type-changed", path, a.get("kind"), b.get("kind"), free=False, breaking=True)]
    changes: list[SurfaceChange] = []
    if "parameters" in a or "parameters" in b:
        changes.extend(_parameter_changes(path, a.get("parameters", {}), b.get("parameters", {})))
    if a.get("kind") == "class":
        old_fields = cast(Mapping[str, Any], a.get("fields", {}))
        new_fields = cast(Mapping[str, Any], b.get("fields", {}))
        for name in sorted(set(old_fields) | set(new_fields)):
            if name not in new_fields:
                changes.append(
                    _change("removed", f"{path}.{name}", old_fields[name], None, free=False, breaking=True)
                )
            elif name not in old_fields:
                changes.append(
                    _change("added", f"{path}.{name}", None, new_fields[name], free=False, breaking=False)
                )
        old_methods = cast(Mapping[str, Mapping[str, Any]], a.get("methods", {}))
        new_methods = cast(Mapping[str, Mapping[str, Any]], b.get("methods", {}))
        for name in sorted(set(old_methods) | set(new_methods)):
            where = f"{path}.{name}"
            if name not in new_methods:
                changes.append(_change("removed", where, old_methods[name], None, free=False, breaking=True))
            elif name not in old_methods:
                changes.append(_change("added", where, None, new_methods[name], free=False, breaking=False))
            else:
                changes.extend(
                    _parameter_changes(
                        where, old_methods[name]["parameters"], new_methods[name]["parameters"]
                    )
                )
    elif a.get("kind") == "enum":
        for member in sorted(set(a.get("members", ())) - set(b.get("members", ()))):
            changes.append(_change("removed", f"{path}.{member}", member, None, free=False, breaking=True))
        for member in sorted(set(b.get("members", ())) - set(a.get("members", ()))):
            changes.append(_change("added", f"{path}.{member}", None, member, free=False, breaking=False))
    elif a.get("kind") == "module":
        old_names = cast(Mapping[str, Any] | Sequence[str], a.get("names", {}))
        new_names = cast(Mapping[str, Any] | Sequence[str], b.get("names", {}))
        if isinstance(old_names, Mapping) and isinstance(new_names, Mapping):
            changes.extend(_library(path, old_names, new_names))
        else:
            for name in sorted(set(old_names) - set(new_names)):
                changes.append(_change("removed", f"{path}.{name}", name, None, free=False, breaking=True))
            for name in sorted(set(new_names) - set(old_names)):
                changes.append(_change("added", f"{path}.{name}", None, name, free=False, breaking=False))
    return changes


def _library(prefix: str, before: Mapping[str, Any], after: Mapping[str, Any]) -> list[SurfaceChange]:
    changes: list[SurfaceChange] = []
    for name in sorted(set(before) | set(after)):
        path = f"{prefix}.{name}"
        a, b = before.get(name), after.get(name)
        if a is None:
            changes.append(_change("added", path, None, b, free=False, breaking=False))
        elif b is None:
            changes.append(_change("removed", path, a, None, free=False, breaking=True))
        else:
            changes.extend(_name_changes(path, a, b))
    return changes


def surface_changes(before: Surface, after: Surface) -> tuple[SurfaceChange, ...]:
    """Every difference from ``before`` (the baseline) to ``after``, each with whether it breaks the 1.x
    contract (cli-contract, "Breaking changes of the surface"). Items marked experimental, or deprecated in
    ``before``, never break."""
    changes = _commands(before, after)
    changes.extend(_codes("exit:", before.exit_codes, after.exit_codes, _number))
    changes.extend(_codes("", before.fen_codes, after.fen_codes, _number))
    changes.extend(_codes("", before.issue_codes, after.issue_codes, _severity))
    for module in sorted(set(before.library) | set(after.library)):
        changes.extend(_library(module, before.library.get(module, {}), after.library.get(module, {})))
    return tuple(changes)


def breaking(changes: Sequence[SurfaceChange]) -> tuple[SurfaceChange, ...]:
    """The breaking changes of ``changes``."""
    return tuple(change for change in changes if change.breaking)


__all__ = [
    "GLOBAL",
    "KINDS",
    "LIBRARY_MODULES",
    "SURFACE_CONTRACT",
    "Kind",
    "Surface",
    "SurfaceChange",
    "breaking",
    "cli_surface",
    "library_surface",
    "surface_changes",
]
