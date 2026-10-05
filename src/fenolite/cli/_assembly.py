# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What ``bom`` and ``pnp`` share: the board a path names, its design, the template file and the planned
CSV file (capability cli-contract, "Bom command" and "Pnp command"; user guide ``docs/assembly.md``)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends import registry
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.cli.api import Context, PlannedWrite
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FenoliteError
from fenolite.core.evidence import Evidence
from fenolite.exports.assembly import DEFAULT, AssemblyTemplate, CsvOptions, read_template, render_csv
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design

CACHE_DIR = ".fenolite"
BUILT_MARKERS = ("meta.json", "build.json")
DEFAULT_NAME = "default"


@dataclass(frozen=True, slots=True)
class BoardInput:
    """The board that a ``PATH`` argument names."""

    path: Path
    sha256: str

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def built(self) -> bool:
        """True when Fenolite built this project: its folder holds a ``.fenolite/`` model."""
        return any((self.root / CACHE_DIR / marker).is_file() for marker in BUILT_MARKERS)

    def ref(self) -> InputRef:
        return InputRef(path=self.path.name, sha256=self.sha256, kind="kicad_pcb", format_version=None)


def board_input(argument: str, ctx: Context) -> BoardInput:
    """The board of ``argument`` (a board, a project file or a folder), resolved as ``check`` does."""
    given = Path(argument)
    board = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    return BoardInput(board, hashlib.sha256(board.read_bytes()).hexdigest())


def read_design(board: BoardInput) -> tuple[Design, Evidence]:
    """The design read from the board file, and the evidence of that read."""
    backend = registry.for_path(board.path)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {board.path.name}", hint="pass a KiCad .kicad_pcb")
    read = backend.read(board.path)
    return read.design, read.evidence


def built_model(board: BoardInput) -> Design:
    """The ``.fenolite/`` model of a built project; ``FEN-3004`` when it cannot be read."""
    try:
        return load_dir(board.root / CACHE_DIR)
    except (OSError, ValueError, KeyError, TypeError, FenoliteError) as exc:
        raise CliError(
            "FEN-3004",
            f"the model in {CACHE_DIR}/ cannot be read: {type(exc).__name__}",
            hint="build the project again",
            where=CACHE_DIR,
        ) from exc


def template_of(argument: str | None, ctx: Context) -> tuple[AssemblyTemplate, str]:
    """The template of ``--template`` and its name for the result: the file name without its folder, or
    ``default``. A file that cannot be read is ``FEN-3001``; an invalid one raises ``TemplateError``."""
    if argument is None:
        return DEFAULT, DEFAULT_NAME
    given = Path(argument)
    path = given if given.is_absolute() else ctx.cwd / given
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else "not UTF-8 text"
        raise CliError("FEN-3001", f"cannot read {given.name}: {reason}", where=given.name) from None
    return read_template(text, file=given.name), given.name


def objects(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[dict[str, str]]:
    """Each row as an object keyed by column name, with the text the file would hold."""
    return [dict(zip(header, row, strict=True)) for row in rows]


def planned(
    out: str | None, kind: str, header: Sequence[str], rows: Sequence[Sequence[str]], options: CsvOptions
) -> tuple[PlannedWrite, ...]:
    """The one CSV file of ``--out``, or nothing without it."""
    if out is None:
        return ()
    return (PlannedWrite(path=str(out), data=render_csv(header, rows, options), kind=kind),)


__all__ = [
    "DEFAULT_NAME",
    "BoardInput",
    "board_input",
    "built_model",
    "objects",
    "planned",
    "read_design",
    "template_of",
]
