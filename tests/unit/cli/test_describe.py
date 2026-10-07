# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Command descriptions are read from the parsers (capability cli-contract, "Command description";
change c0079)."""

from __future__ import annotations

import argparse
import dataclasses
import json
import re

import pytest

from fenolite.cli.api import Command, Context, Result, discover
from fenolite.cli.describe import Argument, CommandDescription, describe, global_arguments
from fenolite.cli.main import main

COMMANDS = discover()
NAMES = sorted(COMMANDS)
ARGUMENT_KEYS = ["name", "flags", "kind", "type", "choices", "default", "required", "repeatable", "help"]
GLOBAL_FLAGS = [
    "--json", "--text", "--fields", "--limit", "--cursor", "--format", "--progress", "--seed", "--timestamp",
    "--no-backup", "--kicad-version", "--allow-lossy",
]  # fmt: skip
OPTION_LINE = re.compile(r"^  (-\S.*?)(?:  .*)?$")


def help_flags(text: str) -> set[str]:
    """The option strings that a ``--help`` text lists, apart from ``-h`` and ``--help``: the first word
    of each comma-separated form at the start of an option's line."""
    found: set[str] = set()
    for line in text.splitlines():
        match = OPTION_LINE.match(line)
        if match is not None:
            found |= {form.split()[0] for form in match.group(1).split(", ")}
    return found - {"-h", "--help"}


def _flags(arguments: tuple[Argument, ...]) -> set[str]:
    return {flag for argument in arguments for flag in argument.flags}


def _by_flag(arguments: tuple[Argument, ...], flag: str) -> Argument:
    (found,) = [argument for argument in arguments if flag in argument.flags]
    return found


def test_build_is_described() -> None:
    """Scenario "Build is described"."""
    description = describe(COMMANDS["build"])
    assert isinstance(description, CommandDescription)
    assert description.name == "build" and description.mutates is True
    assert description.summary == COMMANDS["build"].help
    assert description.usage.startswith("fenolite build ") and "\n" not in description.usage
    positionals = [a for a in description.arguments if a.kind == "positional"]
    assert len(positionals) == 1 and positionals[0].flags == () and positionals[0].required
    out = _by_flag(description.arguments, "--out")
    assert (out.kind, out.type, out.required, out.repeatable) == ("option", "string", True, False)
    target = _by_flag(description.arguments, "--target")
    assert target.kind == "option" and target.choices == ("altium", "kicad") and not target.required
    for flag in ("--dry-run", "--confirm"):
        protocol = _by_flag(description.arguments, flag)
        assert (protocol.kind, protocol.type, protocol.default) == ("flag", "boolean", False)
    assert "--json" not in _flags(description.arguments)


def test_read_only_command_has_no_protocol_flags() -> None:
    """Scenario "Read-only command has no protocol flags"."""
    description = describe(COMMANDS["check"])
    assert description.mutates is False
    assert not {"--confirm", "--dry-run"} & _flags(description.arguments)


@pytest.mark.parametrize("name", NAMES)
def test_protocol_flags_follow_mutates(name: str) -> None:
    flags = _flags(describe(COMMANDS[name]).arguments)
    assert ({"--dry-run", "--confirm"} <= flags) is COMMANDS[name].mutates
    assert COMMANDS[name].mutates or not {"--dry-run", "--confirm"} & flags


def test_global_flags_are_listed_once() -> None:
    """Scenario "Global flags are listed once"."""
    shared = global_arguments()
    assert [argument.flags[0] for argument in shared] == GLOBAL_FLAGS
    limit = _by_flag(shared, "--limit")
    assert (limit.kind, limit.type, limit.default) == ("option", "integer", None)
    assert _by_flag(shared, "--cursor").type == "string"
    assert _by_flag(shared, "--format").choices == ("concise", "detailed")
    assert _by_flag(shared, "--format").default == "detailed"
    version = _by_flag(shared, "--kicad-version")
    assert (version.type, version.choices, version.default) == ("integer", (9, 10), 10)
    assert _by_flag(shared, "--json").kind == "flag" and _by_flag(shared, "--json").type == "boolean"
    for name in NAMES:
        assert not _flags(describe(COMMANDS[name]).arguments) & set(GLOBAL_FLAGS), name


@pytest.mark.parametrize("name", NAMES)
def test_description_agrees_with_help(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "Descriptions agree with help"."""
    assert main([name, "--help"]) == 0
    listed = help_flags(capsys.readouterr().out)
    own = _flags(describe(COMMANDS[name]).arguments)
    assert own | _flags(global_arguments()) == listed
    assert not own & _flags(global_arguments())


def test_help_flags_reads_every_form() -> None:
    text = (
        "usage: fenolite x [-h] [--json] [-o FILE]\n\n"
        "positional arguments:\n  PATH        a --file to read\n\n"
        "options:\n  -h, --help            show this help message and exit\n"
        "  -o FILE, --output FILE\n                        where --not-a-flag goes\n"
        "  --stages A,B          stages to run\n  --rip\n"
    )
    assert help_flags(text) == {"-o", "--output", "--stages", "--rip"}


def _command(register: object) -> Command:
    def run(_args: argparse.Namespace, _ctx: Context) -> Result:
        raise AssertionError("describe ran the command")

    return Command(name="demo", help="a demo", mutates=False, register=register, run=run)  # type: ignore[arg-type]


def test_kinds_types_and_repeats() -> None:
    def register(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("source", metavar="FILE", help="what to read")
        parser.add_argument("more", nargs="*")
        parser.add_argument("-n", "--count", type=int, default=3, metavar="N")
        parser.add_argument("--ratio", type=float)
        parser.add_argument("--tag", action="append", default=[], choices=["b", "a"])
        parser.add_argument("--pair", nargs=2)
        parser.add_argument("--loud", action="store_true")
        parser.add_argument("--where", default=argparse.SUPPRESS)

    description = describe(_command(register))
    by_name = {argument.name: argument for argument in description.arguments}
    assert list(by_name) == ["source", "more", "count", "ratio", "tag", "pair", "loud", "where"]
    assert (by_name["source"].kind, by_name["source"].required, by_name["source"].help) == (
        "positional",
        True,
        "what to read",
    )
    assert (by_name["more"].required, by_name["more"].repeatable) == (False, True)
    assert (by_name["count"].flags, by_name["count"].type, by_name["count"].default) == (
        ("-n", "--count"),
        "integer",
        3,
    )
    assert by_name["ratio"].type == "number" and by_name["ratio"].default is None
    assert (by_name["tag"].repeatable, by_name["tag"].choices, by_name["tag"].default) == (
        True,
        ("a", "b"),
        [],
    )
    assert by_name["pair"].repeatable and by_name["pair"].kind == "option"
    assert (by_name["loud"].kind, by_name["loud"].type, by_name["loud"].default) == ("flag", "boolean", False)
    assert by_name["where"].default is None and by_name["where"].help == ""
    assert description.usage == (
        "fenolite demo [-n N] [--ratio RATIO] [--tag {a,b}] [--pair PAIR] [--loud] [--where WHERE] "
        "FILE [more]"
    )
    assert description.summary == "a demo"


@pytest.mark.parametrize("name", NAMES)
def test_to_json_is_plain(name: str) -> None:
    description = describe(COMMANDS[name])
    data = description.to_json()
    assert list(data) == ["name", "summary", "mutates", "usage", "arguments"]
    assert all(list(argument) == ARGUMENT_KEYS for argument in data["arguments"])
    assert json.loads(json.dumps(data)) == data
    assert data["usage"].startswith(f"fenolite {name}") and "\n" not in data["usage"]
    kinds = {argument["kind"] for argument in data["arguments"]}
    assert kinds <= {"positional", "option", "flag"}
    for argument in data["arguments"]:
        assert argument["type"] in ("string", "integer", "number", "boolean")
        assert (argument["kind"] == "flag") is (argument["type"] == "boolean")
        assert (argument["kind"] == "positional") is (argument["flags"] == [])
        assert argument["choices"] is None or argument["choices"] == sorted(argument["choices"])


def test_global_arguments_to_json() -> None:
    data = [argument.to_json() for argument in global_arguments()]
    assert all(list(argument) == ARGUMENT_KEYS for argument in data)
    assert json.loads(json.dumps(data)) == data


def test_hidden_command_is_described() -> None:
    description = describe(COMMANDS["_echo"])
    assert description.summary == "" and "--text-body" in _flags(description.arguments)
    assert dataclasses.is_dataclass(description)
