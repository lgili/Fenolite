# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite capabilities``: what this installation can do. Agents should call it first."""

from __future__ import annotations

import argparse
import difflib
import importlib.metadata
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from functools import cache
from typing import Any

from fenolite import __version__
from fenolite.agent import guide
from fenolite.backends import registry
from fenolite.cli import describe
from fenolite.cli.api import Command, Context, Result, discover
from fenolite.cli.errors import CliError
from fenolite.core.evidence import Evidence
from fenolite.routing.protocol import router_features
from fenolite.routing.registry import routers as routing_routers

_EXTRA_MARKER = re.compile(r"extra\s*==\s*['\"]([^'\"]+)['\"]")
_DIST_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _extras() -> dict[str, dict[str, Any]]:
    """Each optional extra of the installed distribution and whether its packages are installed."""
    try:
        requires = importlib.metadata.metadata("fenolite").get_all("Requires-Dist") or []
    except importlib.metadata.PackageNotFoundError:
        return {}
    wanted: dict[str, list[str]] = {}
    for requirement in requires:
        extra = _EXTRA_MARKER.search(requirement)
        name = _DIST_NAME.match(requirement)
        if extra and name:
            wanted.setdefault(extra.group(1), []).append(name.group(1))
    report: dict[str, dict[str, Any]] = {}
    for extra, dists in sorted(wanted.items()):
        missing: list[str] = []
        for dist in sorted(dists):
            try:
                importlib.metadata.version(dist)
            except importlib.metadata.PackageNotFoundError:
                missing.append(dist)
        report[extra] = {"installed": not missing, "missing": missing}
    return report


def _run_version(argv: list[str]) -> str | None:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    text = (proc.stdout or proc.stderr).strip()
    return text.splitlines()[0].strip() if text else None


def _kicad_cli_path() -> str | None:
    from fenolite.backends.kicad.cli import find_kicad_cli

    found = find_kicad_cli()
    return None if found is None else str(found)


@cache
def detect_tools() -> dict[str, dict[str, str] | None]:
    """External tools Fenolite can drive, with their version, or ``None`` when absent or unusable."""
    tools: dict[str, dict[str, str] | None] = {}
    probes: dict[str, tuple[str | None, list[str]]] = {
        "kicad-cli": (_kicad_cli_path(), ["version"]),
        "java": (shutil.which("java"), ["-version"]),
        "docker": (shutil.which("docker"), ["--version"]),
    }
    for name, (path, version_args) in probes.items():
        version = _run_version([path, *version_args]) if path else None
        tools[name] = {"path": path, "version": version} if path and version else None
    return tools


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-tools", action="store_true", help="skip external tool detection")
    parser.add_argument(
        "--brief",
        action="store_true",
        help="the small first reply: commands with a summary, targets, tools, routers, guide pages, starters",
    )
    parser.add_argument(
        "--command",
        dest="described",
        metavar="NAME",
        help="describe one command: its entry, its usage and its arguments as data",
    )


def _experimental(features: Sequence[tuple[Mapping[str, object], Evidence]]) -> list[dict[str, Any]]:
    """One entry per experimental feature, sorted by name, its evidence written as a backend's
    (``docs/cli-contract.md``, "Discovery")."""
    entries: list[dict[str, Any]] = [
        {
            **entry,
            "evidence": {
                "level": evidence.level.value,
                "oracle": evidence.oracle,
                "hypotheses": list(evidence.hypotheses),
            },
        }
        for entry, evidence in features
    ]
    return sorted(entries, key=lambda e: str(e["name"]))


def _entry(command: Command) -> dict[str, Any]:
    """The entry of ``command`` in ``result.commands`` of the default view."""
    return (
        {"name": command.name, "mutates": command.mutates, "schema": command.schema, "hidden": command.hidden}
        | ({"example_tools": list(command.example_tools)} if command.example_tools else {})
        | ({"paged": command.paged, "default_limit": command.default_limit} if command.paged else {})
        | {key: list(values) for key, values in command.discovery}
    )


def _brief(commands: Mapping[str, Command], *, no_tools: bool) -> dict[str, Any]:
    """The brief view: what is installed here, what it can do and where to read more, in a reply whose
    size grows with the number of commands only (``docs/cli-contract.md``, "Discovery")."""
    target = next(a for a in describe.describe(commands["build"]).arguments if "--target" in a.flags)
    kicad = registry.get("kicad").capabilities().to_json()
    routers: list[dict[str, Any]] = []
    for router in routing_routers().values():
        status = None if no_tools else router.available()
        routers.append(
            {
                "name": router.name,
                "available": None if status is None else status.available,
                "reason": None if status is None else (status.reason or None),
            }
        )
    return {
        "fenolite_version": __version__,
        "commands": [
            {"name": c.name, "summary": c.help or "", "mutates": c.mutates}
            for c in sorted(commands.values(), key=lambda c: c.name)
            if not c.hidden
        ],
        "targets": {
            "build": sorted(target.choices or ()),
            "kicad": list(kicad["targets"]),
            "default": kicad["default_target"],
        },
        "tools": {} if no_tools else detect_tools(),
        "routers": sorted(routers, key=lambda r: str(r["name"])),
        "guide": [{"topic": p.topic, "title": p.title, "summary": p.summary} for p in guide.pages()],
        "starters": [{"name": s.name, "summary": s.summary} for s in guide.starters()],
        "sends_data_offsite": False,
    }


def _command_view(commands: Mapping[str, Command], name: str) -> dict[str, Any]:
    """The view of one command: its entry of the default view with its description. Runs no tool."""
    command = commands.get(name)
    if command is None:
        public = sorted(n for n, c in commands.items() if not c.hidden)
        close = difflib.get_close_matches(name, public, n=3, cutoff=0.0)
        raise CliError(
            "FEN-2001",
            f"unknown command {name!r}",
            hint=f"the closest commands are: {', '.join(close)}",
            where="--command",
        )
    described = describe.describe(command).to_json()
    return {
        "command": _entry(command) | {key: described[key] for key in ("summary", "usage", "arguments")},
        "global_arguments": [argument.to_json() for argument in describe.global_arguments()],
    }


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.brief and args.described is not None:
        raise CliError("FEN-2001", "--brief and --command are mutually exclusive", hint="use one of them")
    if args.brief:
        return Result(result=_brief(discover(), no_tools=bool(args.no_tools)))
    if args.described is not None:
        return Result(result=_command_view(discover(), str(args.described)))

    from fenolite.backends import matrix  # its rows import the claims of every backend package
    from fenolite.lens.altium import ALTIUM_BUILD_EVIDENCE, EXPERIMENTAL, PCB_BUILD_EVIDENCE, PCB_EXPERIMENTAL

    commands = [_entry(c) for c in sorted(discover().values(), key=lambda c: c.name)]
    from fenolite.cli.main import MUTATION_FLAGS, global_flags

    result: dict[str, Any] = {
        "fenolite_version": __version__,
        "commands": commands,
        "global_flags": global_flags(),
        "mutation_flags": list(MUTATION_FLAGS),
        "backends": [backend.capabilities().to_json() for backend in registry.all_backends()],
        "experimental": _experimental(
            [(EXPERIMENTAL, ALTIUM_BUILD_EVIDENCE), (PCB_EXPERIMENTAL, PCB_BUILD_EVIDENCE)]
        ),
        "matrix": [row.to_json() for row in matrix.rows()],
        "extras": _extras(),
        "tools": {} if args.no_tools else detect_tools(),
        "routers": [
            {
                "name": router.name,
                "description": router.description,
                "sends_data_offsite": router.sends_data_offsite,
                "builtin": router.__class__.__module__.startswith("fenolite."),
                # what the router takes beyond single nets, read without running it (change c0110)
                "features": sorted(router_features(router)),
            }
            for router in routing_routers().values()
        ],
        "sends_data_offsite": False,
    }
    return Result(result=result)


COMMAND = Command(
    name="capabilities",
    help="list commands, backends, extras and external tools available here",
    mutates=False,
    register=_register,
    run=_run,
    example_args=("--no-tools",),
)
