# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.run``: every command in this process (capability python-api, "In-process command runner"
and "Mutation protocol in process"; change c0206; ``docs/api.md``).

``run`` hands its command line to the dispatcher that ``fenolite`` runs (``fenolite.cli.main.invoke``) and
returns what the command line would print with ``--json``: the exit code, the envelope and the error object.
It starts no process, writes nothing on ``sys.stdout`` or ``sys.stderr`` and does not change the process's
working folder; ``cwd`` is the working folder of the command. The CLI is imported inside ``run`` only, the
one edge from ``api`` to ``cli`` (capability package-layering, "Public API runs the commands lazily"), so
``import fenolite.api`` does not load the command modules.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

COMMAND_NAME = re.compile(r"^[a-z_][a-z0-9-]*$")
"""What ``run``'s first argument looks like: a command name, never a flag."""
RUN_KEYWORDS = {"seed": "--seed", "timestamp": "--timestamp"}
"""The keywords of ``run`` and the flags they stand for."""


@dataclass(frozen=True, slots=True)
class Reply:
    """What one command gives: the exit code, the envelope as the JSON object ``fenolite --json`` prints
    on stdout (``None`` when stdout stays empty: a usage error found before the command ran), and the
    error object it prints on stderr (``None`` on exit 0)."""

    exit_code: int
    envelope: Mapping[str, Any] | None
    error: Mapping[str, Any] | None

    @property
    def ok(self) -> bool:
        """Whether the command exited 0."""
        return self.exit_code == 0

    @property
    def result(self) -> Mapping[str, Any]:
        """``envelope["result"]``, or an empty mapping without an envelope."""
        return {} if self.envelope is None else self.envelope["result"]


def _folder(cwd: str | os.PathLike[str] | None) -> Path:
    if cwd is None:
        return Path.cwd()
    folder = Path(cwd).resolve()
    if not folder.is_dir():
        raise ValueError(f"cwd: {os.fspath(cwd)!r} is not a folder")
    return folder


def run(
    command: str,
    *args: str,
    cwd: str | os.PathLike[str] | None = None,
    seed: int | None = None,
    timestamp: str | datetime | None = None,
) -> Reply:
    """Run ``fenolite COMMAND ARGS... --json`` in this process and return its reply.

    ``cwd`` is the command's working folder (default: the process's); relative paths in ``args`` and the
    paths of planned writes are relative to it. ``seed`` and ``timestamp`` stand for ``--seed`` and
    ``--timestamp``. A writing command keeps the mutation protocol: without ``--confirm`` it plans and
    writes nothing (exit 4, or 0 with ``--dry-run``), and ``--confirm --plan ID`` writes the reviewed plan.
    ``--help``, ``--text``, ``restore -`` and ``view --serve`` are usage errors (exit 2).

    A ``command`` that is not a command name, or a keyword given twice, raises ``ValueError``; an
    argument that is not a ``str`` raises ``TypeError``. Every other fault is in the reply.
    """
    if not isinstance(command, str) or COMMAND_NAME.fullmatch(command) is None:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError(f"command: {command!r} is not a command name; pass flags after it")
    for arg in args:
        if not isinstance(arg, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"run takes str arguments, not {type(arg).__name__}: {arg!r}")
    given = {"seed": seed, "timestamp": timestamp}
    extra: list[str] = []
    for key, flag in RUN_KEYWORDS.items():
        value = given[key]
        if value is None:
            continue
        if any(arg == flag or arg.startswith(flag + "=") for arg in args):
            raise ValueError(f"{key} is given twice: as a keyword and as {flag}")
        extra += [flag, value.isoformat() if isinstance(value, datetime) else str(value)]
    folder = _folder(cwd)
    from fenolite.cli.main import invoke  # the one edge api → cli, at call time (decision 3 of c0206)

    code, envelope, error = invoke([command, *extra, *args], cwd=folder)
    return Reply(code, envelope, error)


__all__ = ["Reply", "run"]
