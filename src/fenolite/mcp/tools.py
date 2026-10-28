# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tools of the MCP server: one per public command (capability mcp-server, "One tool per public command"
and "Commands not exposed"; change c0195).

Nothing is declared twice: a tool's input schema is the command's own parser, read through
:func:`fenolite.cli.describe.describe`, plus the global options that make sense for a call. A writing
command's ``--dry-run``, ``--confirm`` and ``--plan`` become two properties, ``confirm`` and ``plan``: a call
without ``confirm`` is the dry run (capability mcp-server, "Writes through a reviewed plan").
:meth:`Catalog.command_line` checks a call's arguments against the schema and gives the command line;
a refusal is :class:`InputRefused`, carrying the command line's own error object (``FEN-2001``).
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from fenolite.cli.api import Command
from fenolite.cli.describe import Argument, describe, global_arguments
from fenolite.cli.errors import CliError, ErrorInfo
from fenolite.cli.main import build_parser

PREFIX = "fenolite_"
NOT_TOOLS = frozenset({"mcp", "skill"})
"""``mcp`` is this server; ``skill`` installs files into an agent's own folders, outside any project."""
LEFT_OUT = {"view": frozenset({"serve", "port", "no_browser"})}
"""Arguments a tool does not take: ``view --serve`` is a server that does not return."""
GLOBALS = ("fields", "limit", "cursor", "format", "seed", "timestamp", "kicad_version", "allow_lossy")
"""The global options a call may set; ``--json``, ``--text`` and ``--progress`` are the server's."""
WRITING_GLOBALS = ("no_backup",)
WRITE_FLAGS = frozenset({"dry_run", "confirm", "plan"})
INPUT_FILES = {"edit": {"content": "content_file", "edits": "edits_file"}}
"""Tool properties whose value the server writes to a file of its own and passes as the command's file
argument (change c0196): an agent gives text, never a path the command would read."""
EDIT = "edit"
"""Listed only with ``allow_edit``: editing a design script and building it runs that script as the user."""
OPEN_WORLD = frozenset({"fetch"})
"""Commands that reach the network (``openWorldHint``)."""
ENVELOPE = "schemas/fenolite.envelope.v0.json"
INSTRUCTIONS = " ".join(
    (
        "Fenolite designs and checks printed circuit boards for KiCad and Altium.",
        "Each tool runs one fenolite command in the server's project folder and returns",
        f"that command's JSON envelope ({ENVELOPE}).",
        "Read the exit code in the result's _meta 'fenolite/exit' first: 0 ok, 3 bad input,",
        "4 confirmation required, 5 findings (read 'issues'), 6 an external tool missing,",
        "7 a lossy operation refused.",
        "Every tool also takes: fields (keep only these dotted paths of 'result'),",
        "limit and cursor (page the main list; continue from 'next'),",
        "format ('concise' keeps one issue per code), seed and timestamp (byte-identical output),",
        "kicad_version (9 or 10, the KiCad major written files target) and allow_lossy;",
        "a writing tool also takes no_backup.",
        "A writing tool writes in two calls: first without 'confirm', a dry run returning result.plan",
        "and its plan_id; after reviewing the plan, again with confirm: true and plan: <plan_id>.",
        "Start with the resource fenolite://guide/start, or the tool fenolite_guide.",
    )
)
"""The server's ``instructions``: what every tool shares, said once instead of in each schema."""

Json = dict[str, Any]


class InputRefused(ValueError):
    """A call's arguments do not fit its tool; :attr:`error` is the command line's error object."""

    def __init__(self, message: str, *, where: str, hint: str = "") -> None:
        super().__init__(message)
        self.error: ErrorInfo = CliError(
            "FEN-2001", message, where=where, hint=hint or "read the tool's inputSchema"
        ).info()


def tool_name(command: str) -> str:
    """``fenolite_<command>`` with hyphens as underscores."""
    return PREFIX + command.replace("-", "_")


def _schema(argument: Argument, *, described: bool = True) -> Json:
    item: Json = {"type": argument.type}
    if argument.choices is not None:
        item["enum"] = list(argument.choices)
    prop: Json = {"type": "array", "items": item} if argument.repeatable else dict(item)
    if argument.help and described:
        prop["description"] = argument.help
    if argument.default is not None and not (argument.kind == "flag" and argument.default is False):
        prop["default"] = argument.default
    return prop


def _actions(command: Command) -> dict[str, argparse.Action]:
    """The command's own parser actions by name, to build a command line as the parser reads it."""
    parser = build_parser({command.name: command})
    actions: list[argparse.Action] = parser._actions  # pyright: ignore[reportPrivateUsage]
    sub = next(a for a in actions if type(a).__name__ == "_SubParsersAction")
    child = cast("dict[str, argparse.ArgumentParser]", sub.choices)[command.name]
    found: list[argparse.Action] = child._actions  # pyright: ignore[reportPrivateUsage]
    return {action.dest: action for action in found}


@dataclass(frozen=True)
class Tool:
    """One tool: its command, its MCP definition and what builds its command line."""

    command: str
    mutates: bool
    definition: Json
    arguments: tuple[Argument, ...]
    """The arguments of the command line, in the parser's order (own, then global), without the write
    flags; an argument of :data:`INPUT_FILES` is set by the server, never by a call."""
    actions: Mapping[str, argparse.Action]
    inputs: Mapping[str, str]
    """Tool property → the file argument the server sets from it (:data:`INPUT_FILES`)."""


def _tool(command: Command, shared: Mapping[str, Argument]) -> Tool:
    left_out = LEFT_OUT.get(command.name, frozenset())
    own = [a for a in describe(command).arguments if a.name not in WRITE_FLAGS and a.name not in left_out]
    names = (*GLOBALS, *(WRITING_GLOBALS if command.mutates else ()))
    arguments = (*own, *(shared[name] for name in names))
    properties: Json = {}
    for argument in arguments:
        if argument.name in properties:
            raise ValueError(f"{command.name}: two arguments named {argument.name!r}")
        properties[argument.name] = _schema(argument, described=argument.name not in shared)
    properties["fields"] = {"type": "array", "items": {"type": "string"}}
    inputs = INPUT_FILES.get(command.name, {})
    for argument_name in inputs.values():
        del properties[argument_name]
    if inputs:
        properties["content"] = {"type": "string", "description": "the whole new text of the file"}
        properties["edits"] = {
            "type": "array",
            "description": "exact edits, in order; each old text must be found exactly once",
            "items": {
                "type": "object",
                "properties": {"old": {"type": "string"}, "new": {"type": "string"}},
                "required": ["old", "new"],
                "additionalProperties": False,
            },
        }
    description = command.help or command.name
    if command.mutates:
        properties["confirm"] = {
            "type": "boolean",
            "description": "write the plan named by 'plan'; without it the call is a dry run",
        }
        properties["plan"] = {"type": "string", "description": "the plan_id a dry run of this tool returned"}
        description += (
            ". Writes files in two calls: first without 'confirm' (a dry run returning result.plan and"
            " plan_id), then with confirm: true and that plan."
        )
    definition: Json = {
        "name": tool_name(command.name),
        "title": command.name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": [a.name for a in own if a.required],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": not command.mutates,
            "destructiveHint": command.mutates,
            "idempotentHint": not command.mutates,
            "openWorldHint": command.name in OPEN_WORLD,
        },
    }
    if not definition["inputSchema"]["required"]:
        del definition["inputSchema"]["required"]
    return Tool(command.name, command.mutates, definition, arguments, _actions(command), inputs)


def _check(argument: Argument, value: Any) -> list[Any]:
    """``value`` as the list of values it gives on the command line; raises :class:`InputRefused`."""
    values = cast("list[Any]", value) if isinstance(value, list) else [value]
    if isinstance(value, list) and not argument.repeatable:
        raise InputRefused(f"{argument.name}: one value, not a list", where=argument.name)
    expected = {"string": (str,), "integer": (int,), "number": (int, float), "boolean": (bool,)}[
        argument.type
    ]
    for item in values:
        wrong_bool = isinstance(item, bool) and argument.type != "boolean"
        if wrong_bool or not isinstance(item, expected):
            raise InputRefused(
                f"{argument.name}: expected {argument.type}, got {item!r}", where=argument.name
            )
        if argument.choices is not None and item not in argument.choices:
            choices = ", ".join(map(str, argument.choices))
            raise InputRefused(f"{argument.name}: {item!r} is not one of {choices}", where=argument.name)
    return values


def _words(argument: Argument, action: argparse.Action, value: Any) -> list[str]:
    """The words of one option or flag, ``--flag=value`` so that a value starting with '-' stays a value."""
    flag = next((f for f in argument.flags if f.startswith("--")), argument.flags[0])
    if argument.kind == "flag":
        return [flag] if bool(value) != bool(argument.default) else []
    values = [str(v) for v in _check(argument, value)]
    if not argument.repeatable:
        return [f"{flag}={values[0]}"]
    if type(action).__name__ in ("_AppendAction", "_ExtendAction") and action.nargs in (None, "?"):
        return [f"{flag}={v}" for v in values]
    return [flag, *values]


class Catalog:
    """The tools of the installed commands, filtered by ``read_only`` and ``only`` (command names)."""

    def __init__(
        self,
        commands: Mapping[str, Command],
        *,
        read_only: bool = False,
        only: Iterable[str] | None = None,
        allow_edit: bool = False,
    ) -> None:
        shared = {argument.name: argument for argument in global_arguments()}
        wanted = None if only is None else set(only)
        public = {name: c for name, c in commands.items() if not c.hidden and name not in NOT_TOOLS}
        if wanted is not None and wanted - set(public):
            raise KeyError(sorted(wanted - set(public))[0])
        self.tools: dict[str, Tool] = {}
        for name in sorted(public):
            command = public[name]
            if (wanted is not None and name not in wanted) or (read_only and command.mutates):
                continue
            if name == EDIT and not allow_edit:
                continue
            tool = _tool(command, shared)
            self.tools[tool.definition["name"]] = tool

    def definitions(self) -> list[Json]:
        return [tool.definition for tool in self.tools.values()]

    def command_line(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        dry_run: bool,
        given: Mapping[str, str] | None = None,
    ) -> list[str]:
        """``[command, words...]`` for a call of tool ``name`` (the write flags are the caller's), with the
        file arguments ``given`` by the server; raises :class:`KeyError` for an unknown tool and
        :class:`InputRefused` for arguments that do not fit."""
        tool = self.tools[name]
        allowed = set(cast("Json", tool.definition["inputSchema"]["properties"]))
        unknown = sorted(set(arguments) - allowed)
        if unknown:
            raise InputRefused(f"{name} takes no argument {unknown[0]!r}", where=unknown[0])
        arguments = {k: v for k, v in arguments.items() if k not in tool.inputs} | dict(given or {})
        missing = [a.name for a in tool.arguments if a.required and arguments.get(a.name) is None]
        if missing:
            raise InputRefused(f"{name} needs {missing[0]!r}", where=missing[0])
        options: list[str] = []
        positionals: list[str] = []
        for argument in tool.arguments:
            value = arguments.get(argument.name)
            if value is None:
                continue
            if argument.name == "fields":
                if not isinstance(value, list) or not all(
                    isinstance(v, str) for v in cast("list[Any]", value)
                ):
                    raise InputRefused("fields: a list of dotted paths", where="fields")
                options.append("--fields=" + ",".join(cast("list[str]", value)))
            elif argument.kind == "positional":
                positionals += [str(v) for v in _check(argument, value)]
            else:
                options += _words(argument, tool.actions[argument.name], value)
        words = [tool.command, *options]
        if dry_run:
            words.append("--dry-run")
        return [*words, *(["--", *positionals] if positionals else [])]


__all__ = [
    "EDIT",
    "INPUT_FILES",
    "INSTRUCTIONS",
    "NOT_TOOLS",
    "PREFIX",
    "Catalog",
    "InputRefused",
    "Tool",
    "tool_name",
]
