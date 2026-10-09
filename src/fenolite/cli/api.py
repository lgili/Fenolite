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
import os
import pkgutil
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fenolite.cli.output import Evidence, InputRef, Issue, OutputMode
from fenolite.core.progress import NULL_PROGRESS, Progress


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
    progress: Progress = NULL_PROGRESS
    """Where a command reports its units of work; it writes on stderr only under ``--progress``."""
    state: Path | None = None
    """The state folder (``fenolite.core.state.state_dir()``), ``None`` when it is off."""


@dataclass(frozen=True, slots=True)
class PlannedWrite:
    """A file a mutating command wants to write. ``path`` is relative to the working directory.

    A *deferred* write names a ``source`` instead of its bytes, with the ``size`` and the ``sha256`` those
    bytes must have: the plan lists the declared values, and the dispatcher calls ``source`` only with
    ``--confirm``, before it writes any file, and checks what it returns (cli-contract, "Deferred writes")."""

    path: str
    data: bytes
    kind: str
    source: Callable[[], bytes] | None = None
    size: int | None = None
    sha256: str | None = None

    def __post_init__(self) -> None:
        if self.source is None:
            if self.size is not None or self.sha256 is not None:
                raise ValueError("a planned write without a source declares neither size nor sha256")
        elif self.data or self.size is None or self.sha256 is None:
            raise ValueError("a deferred write has empty data and declares both size and sha256")

    @property
    def deferred(self) -> bool:
        return self.source is not None


@dataclass(frozen=True, slots=True)
class Result:
    """What a command returns to the dispatcher."""

    result: dict[str, Any] = field(default_factory=lambda: {})
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = Evidence()
    input: InputRef | None = None
    writes: tuple[PlannedWrite, ...] = ()
    text: str | None = None
    """A text the command wants printed as it is in text mode, after the status line (a page of the
    guide). JSON mode ignores it: the envelope holds no key for it."""
    depends: tuple[str, ...] = ()
    """The inputs of the command that are not its targets, as :func:`depends_on` spells them: a plan id
    binds their digests, and ``--confirm --plan`` refuses when one changed (cli-contract, "Staged plans")."""
    write_on_error: bool = False
    """Write although the issues hold an error. Only ``place --force`` sets it (cli-contract, "Error
    findings plan no write")."""
    written: Callable[[], None] | None = None
    """Called by the dispatcher once, after the writes of this result were all written."""


def depends_on(cwd: Path, *paths: str | Path | None) -> tuple[str, ...]:
    """The value of ``Result.depends`` for the files at ``paths``: each one relative to ``cwd`` in POSIX
    form when it lies inside it, else absolute; sorted, without repeats and without ``None``."""
    found: set[str] = set()
    for path in paths:
        if path is None:
            continue
        full = Path(os.path.abspath(path if Path(path).is_absolute() else cwd / path))
        try:
            found.add(full.relative_to(Path(os.path.abspath(cwd))).as_posix())
        except ValueError:
            found.add(full.as_posix())
    return tuple(sorted(found))


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
    discovery: tuple[tuple[str, tuple[str | int, ...]], ...] = ()
    """Keys that the command's entry in ``fenolite capabilities`` holds besides those of every entry, each
    with its list (``equivalent``: ``levels`` and ``sides``; change c0158)."""

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


__all__ = ["Command", "Context", "PlannedWrite", "Result", "depends_on", "discover", "module_name_for"]
