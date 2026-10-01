# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite capabilities``: what this installation can do. Agents should call it first."""

from __future__ import annotations

import argparse
import importlib.metadata
import re
import shutil
import subprocess
from functools import cache
from typing import Any

from fenolite import __version__
from fenolite.backends import registry
from fenolite.cli.api import Command, Context, Result, discover

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


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    commands = [
        {"name": c.name, "mutates": c.mutates, "schema": c.schema, "hidden": c.hidden}
        for c in sorted(discover().values(), key=lambda c: c.name)
    ]
    result: dict[str, Any] = {
        "fenolite_version": __version__,
        "commands": commands,
        "backends": [backend.capabilities().to_json() for backend in registry.all_backends()],
        "extras": _extras(),
        "tools": {} if args.no_tools else detect_tools(),
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
