# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Declared command/option deprecations, independent of argument values and plan identity."""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterator, Mapping
from typing import Any, cast

from fenolite.cli.api import Command
from fenolite.core.errors import Issue


def validate(since: str, use: str) -> None:
    if re.fullmatch(r"v?\d+\.\d+\.\d+", since) is None or not use.strip():
        raise ValueError("a deprecation declares a release (major.minor.patch) and a replacement")


def declare(parser: argparse.ArgumentParser, flag: str, *, since: str, use: str) -> None:
    validate(since, use)
    for action in parser._actions:  # pyright: ignore[reportPrivateUsage]
        if flag not in action.option_strings:
            continue
        value = {"since": since, "use": use}
        cast(Any, action)._fenolite_deprecation = {"option": flag, **value}
        marked = cast(dict[str, dict[str, str]], getattr(parser, "_fenolite_deprecations", {}))
        marked.update({alias: value for alias in action.option_strings})
        cast(Any, parser)._fenolite_deprecations = marked
        return
    raise ValueError(f"no option {flag!r} in {parser.prog}")


def _parsers(parser: argparse.ArgumentParser) -> Iterator[argparse.ArgumentParser]:
    yield parser
    for action in parser._actions:  # pyright: ignore[reportPrivateUsage]
        if type(action).__name__ == "_SubParsersAction":
            for child in cast(Mapping[str, argparse.ArgumentParser], action.choices).values():
                yield from _parsers(child)


def _issue(command: str, option: str | None, since: str, use: str) -> Issue:
    where = command if option is None else f"{command} {option}"
    return Issue(
        "cli.deprecated",
        "warning",
        f"{where} is deprecated since {since}; use {use}",
        where=where,
        hint=f"use {use}; the deprecated spelling remains available through 1.x",
    )


def record(parser: argparse.ArgumentParser, action: argparse.Action) -> None:
    """Called only for an action actually consumed by argparse, after its value was validated."""
    mark = cast(dict[str, str] | None, getattr(action, "_fenolite_deprecation", None))
    if mark is None:
        return
    used = cast(dict[str, Issue], getattr(parser, "_fenolite_used_deprecations", {}))
    used[mark["option"]] = _issue(
        parser.prog.removeprefix("fenolite ") if parser.prog != "fenolite" else "*",
        mark["option"],
        mark["since"],
        mark["use"],
    )
    cast(Any, parser)._fenolite_used_deprecations = used


def notices(parser: argparse.ArgumentParser, command: Command) -> tuple[Issue, ...]:
    used: dict[str, Issue] = {}
    shared = cast(dict[str, dict[str, str]], getattr(parser, "_fenolite_deprecations", {}))
    if command.deprecated is not None:
        used[command.name] = _issue(command.name, None, command.deprecated, command.replacement or "")
    for child in _parsers(parser):
        for issue in cast(dict[str, Issue], getattr(child, "_fenolite_used_deprecations", {})).values():
            option = issue.where.split(" ", 1)[-1]
            if option in shared:
                issue = _issue("*", option, shared[option]["since"], shared[option]["use"])
            used[issue.where] = issue
    return tuple(used[key] for key in sorted(used))


def entries(commands: Mapping[str, Command]) -> list[dict[str, str | None]]:
    from fenolite.cli.main import build_parser

    result: list[dict[str, str | None]] = []
    for name, command in sorted(commands.items()):
        if command.deprecated is not None:
            result.append(
                {"command": name, "option": None, "since": command.deprecated, "use": command.replacement}
            )
    root = build_parser(dict(commands))
    shared = cast(dict[str, dict[str, str]], getattr(root, "_fenolite_deprecations", {}))
    for parser in _parsers(root):
        command = parser.prog.removeprefix("fenolite ") if parser.prog != "fenolite" else "*"
        for action in parser._actions:  # pyright: ignore[reportPrivateUsage]
            mark = cast(dict[str, Any] | None, getattr(action, "_fenolite_deprecation", None))
            if mark is not None:
                if command != "*" and mark["option"] in shared:
                    continue
                result.append({"command": command, **mark})
    return sorted(result, key=lambda row: (row["command"] or "", row["option"] or ""))
