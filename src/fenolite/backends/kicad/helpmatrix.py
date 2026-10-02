# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Which ``kicad-cli`` subcommands and options exist, read from its help pages (capability kicad-oracle,
"Subcommand matrix from help text"; ``docs/formats/kicad/cli.md``).

The grammar was recorded from running the binary (S-0020): the ``Usage:`` line of a group page ends
with a ``{a,b,…}`` group of subcommands, and that of a leaf page holds one ``[--name …]`` group per
long option (``H-K-CLI-HELP``). Every page is read through the package runner, because even
``--help`` writes a configuration folder.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from fenolite.backends.kicad.cli import KicadCli
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-CLI-HELP",))
"""Raised to ``KICAD-VERIFIED`` only when ``H-K-CLI-HELP`` is verified on both majors (c0013 task 9.2)."""


@dataclass(frozen=True, slots=True)
class MatrixEntry:
    """A command (its words after ``kicad-cli``) and the long options whose presence is reported."""

    command: tuple[str, ...]
    options: tuple[str, ...] = ()


_EXPORTS = ("ipcd356", "pos", "svg", "gerbers", "drill", "stats", "ipc2581", "odb")
MATRIX: tuple[MatrixEntry, ...] = (
    MatrixEntry(
        ("pcb", "drc"), ("--format", "--severity-all", "--schematic-parity", "--refill-zones", "--save-board")
    ),
    MatrixEntry(("pcb", "upgrade")),
    MatrixEntry(("pcb", "import")),
    MatrixEntry(("pcb", "render")),
    *(MatrixEntry(("pcb", "export", name)) for name in _EXPORTS),
    MatrixEntry(("fp", "upgrade")),
    MatrixEntry(("sym", "upgrade")),
    MatrixEntry(("sch", "erc")),
    MatrixEntry(("sch", "export", "netlist")),
    MatrixEntry(("jobset", "run")),
)

_GROUPS: tuple[tuple[str, ...], ...] = (
    ("pcb",),
    ("pcb", "export"),
    ("fp",),
    ("sym",),
    ("sch",),
    ("sch", "export"),
    ("jobset",),
)
"""Group pages read after the root page, each only when its parent page lists it."""
_SUBCOMMANDS = re.compile(r"\{([^{}]*)\}")
_OPTION = re.compile(r"\[(--[A-Za-z0-9][A-Za-z0-9-]*)")


@dataclass(frozen=True, slots=True)
class HelpPage:
    subcommands: frozenset[str]
    options: frozenset[str]


def parse_help(text: str) -> HelpPage | None:
    """The subcommands and long options of a help page's ``Usage:`` line; ``None`` without that line."""
    for line in text.splitlines():
        _, found, usage = line.partition("Usage:")
        if not found:
            continue
        groups = _SUBCOMMANDS.findall(usage)
        subcommands = frozenset(w.strip() for g in groups for w in g.split(",") if w.strip())
        return HelpPage(subcommands, frozenset(_OPTION.findall(usage)))
    return None


def row_key(command: tuple[str, ...], option: str = "") -> str:
    """The matrix row name, for example ``"pcb drc --refill-zones"``."""
    return " ".join((*command, option) if option else command)


def probe_id(command: tuple[str, ...], option: str = "") -> str:
    """The probe of a row, for example ``"check-help-pcb-drc-refill-zones"``."""
    words = (*command, option.removeprefix("--")) if option else command
    return "check-help-" + "-".join(words)


@dataclass(frozen=True, slots=True)
class CommandMatrix:
    """One row per command and option of ``MATRIX`` (rows of an unparsed page left out)."""

    version: str
    rows: Mapping[str, bool]
    unparsed: tuple[str, ...]


def _page_name(words: tuple[str, ...]) -> str:
    return " ".join(("kicad-cli", *words, "--help"))


def command_matrix(cli: KicadCli) -> CommandMatrix:
    """Read the root page, the group pages that exist and ``pcb drc``, and fill the rows of ``MATRIX``."""
    pages: dict[tuple[str, ...], HelpPage | None] = {}

    def read(words: tuple[str, ...]) -> None:
        run = cli.run([*words, "--help"], files={})
        pages[words] = parse_help(run.stdout) if run.ok else None

    def exists(command: tuple[str, ...]) -> bool | None:
        """Whether ``command`` is listed on its parent's page; ``None`` when that page did not parse."""
        parent = command[:-1]
        if parent and not exists(parent):
            return exists(parent)  # absent (False) or unknown (None) parent
        if parent not in pages:
            read(parent)
        page = pages[parent]
        return None if page is None else command[-1] in page.subcommands

    for group in _GROUPS:
        if exists(group):
            read(group)
    drc = ("pcb", "drc")
    if exists(drc):
        read(drc)
    rows: dict[str, bool] = {}
    for entry in MATRIX:
        present = exists(entry.command)
        if present is None:
            continue
        rows[row_key(entry.command)] = present
        for option in entry.options:
            if not present:
                rows[row_key(entry.command, option)] = False
                continue
            if entry.command not in pages:
                read(entry.command)
            page = pages[entry.command]
            if page is not None:
                rows[row_key(entry.command, option)] = option in page.options
    unparsed = tuple(_page_name(words) for words, page in pages.items() if page is None)
    return CommandMatrix(cli.version(), rows, unparsed)


__all__ = [
    "EVIDENCE",
    "MATRIX",
    "CommandMatrix",
    "HelpPage",
    "MatrixEntry",
    "command_matrix",
    "parse_help",
    "probe_id",
    "row_key",
]
