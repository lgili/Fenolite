# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The special strings of an Altium board's texts on its KiCad board (change c0409, B10).

A PCB text that starts with ``.`` is one special string; inside other text each special string is enclosed in
apostrophes, and the text around them is kept as typed (``docs/formats/altium/project.md``,
``H-A-PRJ-SPECIAL``; S-1681, INFERRED). A special string that names a project parameter, which
the import keeps as a text variable of the board (``TitleBlock.params``), is written as KiCad's ``${NAME}``.
Names are compared with their letter case, which no public source states. Every other special string (the
predefined ones such as ``.Designator``) is written as typed, with a ``text`` change in the report.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from fenolite.model.board import Board, Text

if TYPE_CHECKING:
    from fenolite.convert.altium_to_kicad import Ledger

QUOTED = re.compile(r"'\.([^']+)'")
"""One special string inside other text: a name after ``.``, enclosed in apostrophes."""
UNMAPPED = "the special string {names} names no project parameter: written as typed"
PREDEFINED = {
    "layer_name": "LAYER",
    "pcb_file_name": "FILEPATH",
    "pcb_file_name_no_path": "FILENAME",
    "print_date": "CURRENT_DATE",
}
"""Predefined PCB special strings (S-1871), by their names in lower case, and the KiCad text variable of the
same meaning on a board (S-1870) that each is written as (change c0428; ``H-A-PRJ-PREDEF``,
``H-K-PCB-TEXTVARS``, both INFERRED)."""
MAPPED = "the special string {names} is written as KiCad's text variable of the same meaning"
PROJECT_DEPTH = 3
"""How many folders, from a board document's own up, are searched for the project that lists it."""


def _variable(name: str, params: Mapping[str, str]) -> str | None:
    if name in params:
        return "${" + name + "}"
    known = PREDEFINED.get(name.lower())
    return "${" + known + "}" if known is not None else None


def special_text(text: str, params: Mapping[str, str]) -> tuple[str, tuple[str, ...]]:
    """``text`` with each special string that names a key of ``params`` written as ``${NAME}``, each
    predefined one of ``PREDEFINED`` as its KiCad variable, and the names of the other special strings,
    which stay as typed."""
    written, others, _mapped = _special(text, params)
    return written, others


def _special(text: str, params: Mapping[str, str]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """``special_text`` and the predefined special strings written as KiCad variables."""
    mapped: list[str] = []
    if text.startswith(".") and "'" not in text:
        found = _variable(text[1:], params)
        if found is None:
            return text, (text,), ()
        return found, (), (() if text[1:] in params else (text,))
    others: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        found = _variable(name, params)
        if found is None:
            others.append("." + name)
            return match.group(0)
        if name not in params:
            mapped.append("." + name)
        return found

    return QUOTED.sub(replace, text), tuple(others), tuple(mapped)


def board_strings(board: Board, ledger: Ledger) -> Board:
    """``board`` with the special strings of its texts that name its text variables written as ``${NAME}``,
    and the predefined ones of ``PREDEFINED`` as KiCad's variables."""
    params = board.title_block.params if board.title_block is not None else {}
    texts: list[Text] = []
    for text in board.texts:
        written, others, mapped = _special(text.text, params)
        if mapped:
            ledger.change("text", text.id, MAPPED.format(names=", ".join(mapped)))
        if others:
            ledger.change("text", text.id, UNMAPPED.format(names=", ".join(others)))
        texts.append(dataclasses.replace(text, text=written) if written != text.text else text)
    return dataclasses.replace(board, texts=tuple(texts))


def owning_project(document: Path) -> Path | None:
    """The one ``.PrjPcb`` that lists the board document ``document``, looked for in its folder and up to
    ``PROJECT_DEPTH`` folders up, the nearest first; ``None`` when none or several at the nearest level do
    (change c0428)."""
    from fenolite.backends.altium.read.project import locate, read_project

    try:
        target = document.resolve()
    except OSError:
        return None
    folder = target.parent
    for _ in range(PROJECT_DEPTH):
        owners: list[Path] = []
        try:
            projects = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".prjpcb")
        except OSError:
            projects = []
        for project in projects:
            try:
                read = read_project(project.read_bytes(), file=project.name)
            except (OSError, ValueError):
                continue
            for entry in read.documents:
                found = locate(folder, entry.posix) if entry.kind == "pcb" else None
                if found is not None and found.resolve() == target:
                    owners.append(project)
                    break
        if owners:
            return owners[0] if len(owners) == 1 else None
        if folder.parent == folder:
            break
        folder = folder.parent
    return None


def project_parameters(document: Path) -> dict[str, str]:
    """The ``[Parameter<n>]`` entries (name: value, a later one of a name winning) of the project that
    lists the board document ``document`` (``owning_project``); empty when no one project does."""
    from fenolite.backends.altium.read.project import read_project

    project = owning_project(document)
    if project is None:
        return {}
    try:
        read = read_project(project.read_bytes(), file=project.name)
    except (OSError, ValueError):
        return {}
    return {p.name: p.value for p in read.parameters if p.name}


__all__ = [
    "MAPPED",
    "PREDEFINED",
    "QUOTED",
    "board_strings",
    "owning_project",
    "project_parameters",
    "special_text",
]
