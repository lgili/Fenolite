# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The arguments of a command as data, read from the command's own parser (capability cli-contract,
"Command description"; ``docs/cli-contract.md``, "Discovery").

Nothing is declared a second time: :func:`describe` builds the parser that ``fenolite.cli.main.build_parser``
gives the command and reads its actions, so ``--dry-run`` and ``--confirm`` appear for a mutating command
and a flag added to a command appears here by itself. It runs no command and has no side effect.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Literal, cast

from fenolite.cli.api import Command

Kind = Literal["positional", "option", "flag"]
ValueType = Literal["string", "integer", "number", "boolean"]
_REPEATING = frozenset({"_AppendAction", "_AppendConstAction", "_ExtendAction", "_CountAction"})
_NOT_ARGUMENTS = frozenset({"_HelpAction", "_VersionAction", "_SubParsersAction"})


@dataclass(frozen=True, slots=True)
class Argument:
    """One argument of a command line."""

    name: str
    """The name the parser stores the value under."""
    flags: tuple[str, ...]
    """The option strings; empty for a positional."""
    kind: Kind
    """``positional``, ``option`` (takes a value) or ``flag`` (takes none)."""
    type: ValueType
    choices: tuple[Any, ...] | None
    """The accepted values, sorted, or ``None`` when any value of the type is accepted."""
    default: Any
    """A JSON value, or ``None`` without a default."""
    required: bool
    repeatable: bool
    """Whether it may be given more than once or takes several values."""
    help: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "flags": list(self.flags),
            "kind": self.kind,
            "type": self.type,
            "choices": None if self.choices is None else list(self.choices),
            "default": self.default,
            "required": self.required,
            "repeatable": self.repeatable,
            "help": self.help,
        }


@dataclass(frozen=True, slots=True)
class CommandDescription:
    """A command and its own arguments, in the parser's order; the global flags are not among them."""

    name: str
    summary: str
    mutates: bool
    usage: str
    arguments: tuple[Argument, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "mutates": self.mutates,
            "usage": self.usage,
            "arguments": [argument.to_json() for argument in self.arguments],
        }


def _json_value(value: object) -> Any:
    """``value`` as a plain JSON value: what is neither a number, a string, a boolean nor a list of
    them is written as its text."""
    if value is None or value is argparse.SUPPRESS:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in cast("list[object]", value)]
    return str(value)


def _actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    """The actions of ``parser`` that are arguments: not ``--help``, ``--version`` or the sub-commands."""
    actions: list[argparse.Action] = parser._actions  # pyright: ignore[reportPrivateUsage]
    return [action for action in actions if type(action).__name__ not in _NOT_ARGUMENTS]


def _argument(action: argparse.Action) -> Argument:
    positional = not action.option_strings
    flag = not positional and action.nargs == 0
    kind: Kind = "positional" if positional else "flag" if flag else "option"
    value_type: ValueType = (
        "boolean"
        if flag
        else "integer"
        if action.type is int
        else "number"
        if action.type is float
        else "string"
    )
    choices = None if action.choices is None else tuple(sorted(_json_value(c) for c in action.choices))
    several = action.nargs in ("*", "+") or (isinstance(action.nargs, int) and action.nargs > 1)
    required = action.nargs not in ("?", "*") if positional else bool(action.required)
    return Argument(
        name=action.dest,
        flags=tuple(action.option_strings),
        kind=kind,
        type=value_type,
        choices=choices,
        default=_json_value(action.default),
        required=required,
        repeatable=several or type(action).__name__ in _REPEATING,
        help=action.help or "",
    )


def _child(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    actions: list[argparse.Action] = parser._actions  # pyright: ignore[reportPrivateUsage]
    for action in actions:
        if type(action).__name__ == "_SubParsersAction" and action.choices is not None:
            return cast("dict[str, argparse.ArgumentParser]", action.choices)[name]
    raise KeyError(name)


def _placeholder(action: argparse.Action, argument: Argument) -> str:
    if isinstance(action.metavar, str):
        return action.metavar
    if argument.choices is not None:
        return "{" + ",".join(str(choice) for choice in argument.choices) + "}"
    return action.dest if argument.kind == "positional" else action.dest.upper()


def _usage(name: str, described: list[tuple[argparse.Action, Argument]]) -> str:
    """One line: the options in the parser's order, then the positionals."""
    words = [f"fenolite {name}"]
    for action, argument in described:
        if argument.kind == "positional":
            continue
        word = (
            argument.flags[0]
            if argument.kind == "flag"
            else f"{argument.flags[0]} {_placeholder(action, argument)}"
        )
        words.append(word if argument.required else f"[{word}]")
    for action, argument in described:
        if argument.kind == "positional":
            word = _placeholder(action, argument)
            words.append(word if argument.required else f"[{word}]")
    return " ".join(words)


def _global_flags(parser: argparse.ArgumentParser) -> frozenset[str]:
    return frozenset(flag for action in _actions(parser) for flag in action.option_strings)


def describe(command: Command) -> CommandDescription:
    """The description of ``command``, from the parser the dispatcher builds for it."""
    from fenolite.cli.main import build_parser  # the dispatcher imports the commands, which import this

    parser = build_parser({command.name: command})
    shared = _global_flags(parser)
    described = [
        (action, _argument(action))
        for action in _actions(_child(parser, command.name))
        if not shared.intersection(action.option_strings)
    ]
    return CommandDescription(
        name=command.name,
        summary=command.help or "",
        mutates=command.mutates,
        usage=_usage(command.name, described),
        arguments=tuple(argument for _, argument in described),
    )


def global_arguments() -> tuple[Argument, ...]:
    """The flags every command takes, once, read from the dispatcher's own parser."""
    from fenolite.cli.main import build_parser

    return tuple(_argument(action) for action in _actions(build_parser({})))


__all__ = ["Argument", "CommandDescription", "describe", "global_arguments"]
