# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What a command module provides, what it receives and what it returns.

A command lives in ``fenolite/cli/cmd_<name>.py`` (dashes become underscores) and exposes a
module-level ``COMMAND`` (:class:`Command`). Commands never write files themselves: they return
:class:`PlannedWrite` objects and the dispatcher applies the mutation protocol
(``--dry-run`` / ``--confirm``, atomic writes, backups, receipts).
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fenolite.cli.output import Evidence, InputRef, Issue, OutputMode


@dataclass(frozen=True, slots=True)
class Context:
    """Everything a command may depend on besides its own arguments."""

    mode: OutputMode
    seed: int | None
    timestamp: datetime
    rng: random.Random
    no_backup: bool
    cwd: Path
    kicad_target: int = 10
    allow_lossy: bool = False


@dataclass(frozen=True, slots=True)
class PlannedWrite:
    """A file a mutating command wants to write. ``path`` is relative to the working directory."""

    path: str
    data: bytes
    kind: str


@dataclass(frozen=True, slots=True)
class Result:
    """What a command returns to the dispatcher."""

    result: dict[str, Any] = field(default_factory=lambda: {})
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = Evidence()
    input: InputRef | None = None
    writes: tuple[PlannedWrite, ...] = ()


@dataclass(frozen=True, slots=True)
class Command:
    """A registered sub-command. ``help=None`` hides it from ``--help``."""

    name: str
    help: str | None
    mutates: bool
    register: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace, Context], Result]
    example_args: tuple[str, ...] = ()
    mutation_example_args: tuple[str, ...] | None = None
    example_tools: tuple[str, ...] = ()
    """External tools the examples need (``kicad-cli``); the test suites provide a fake for each."""
    paged: str | None = None
    """The list that ``--limit`` and ``--cursor`` cut: a dotted path in ``result``, or ``"issues"`` for
    the envelope's issues. Several paths separated by ``|`` name alternatives: the first one that the
    result holds is paged."""
    default_limit: int | None = None
    """The page size in force without ``--limit``; ``None`` gives the whole list."""

    @property
    def hidden(self) -> bool:
        return self.help is None

    @property
    def schema(self) -> str:
        return f"fenolite.{self.name}.v0"


def module_name_for(command_name: str) -> str:
    return "cmd_" + command_name.replace("-", "_")


def discover() -> dict[str, Command]:
    """Import every ``fenolite.cli.cmd_*`` module and return its ``COMMAND`` keyed by name."""
    import fenolite.cli as package

    found: dict[str, Command] = {}
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        if not info.name.startswith("cmd_"):
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        command = getattr(module, "COMMAND", None)
        if not isinstance(command, Command):
            raise TypeError(f"{module.__name__} does not define COMMAND as fenolite.cli.api.Command")
        if module_name_for(command.name) != info.name:
            raise ValueError(f"{module.__name__} declares command {command.name!r}; module name must match")
        found[command.name] = command
    return found


__all__ = ["Command", "Context", "PlannedWrite", "Result", "discover", "module_name_for"]
