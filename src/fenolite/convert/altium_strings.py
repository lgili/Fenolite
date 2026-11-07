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
from fenolite.model.design import Design
from fenolite.model.presentation import PARAM_NAME

if TYPE_CHECKING:
    from fenolite.convert.altium_to_kicad import Ledger

QUOTED = re.compile(r"'\.([^']+)'")
"""One special string inside other text: a name after ``.``, enclosed in apostrophes."""
UNMAPPED = "the special string {names} names no project parameter: written as typed"
UNDEFINED = (
    "the special string {names} names no project parameter: written as a KiCad text variable the project "
    "does not define"
)
"""The reason of a special string whose name is a variable name and that names no project parameter and no
predefined string (change c0451): ``${NAME}``, which a KiCad user may define and the way back writes as
``.NAME`` again."""
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


def _undefined(name: str) -> str | None:
    """``${NAME}`` for a special string of no project parameter whose name is a variable name (c0451)."""
    return "${" + name + "}" if PARAM_NAME.fullmatch(name) else None


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
            return _undefined(text[1:]) or text, (text,), ()
        return found, (), (() if text[1:] in params else (text,))
    others: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        found = _variable(name, params)
        if found is None:
            others.append("." + name)
            return _undefined(name) or match.group(0)
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
        undefined = [name for name in others if PARAM_NAME.fullmatch(name[1:])]
        typed = [name for name in others if name not in undefined]
        if undefined:
            ledger.change("text", text.id, UNDEFINED.format(names=", ".join(undefined)))
        if typed:
            ledger.change("text", text.id, UNMAPPED.format(names=", ".join(typed)))
        texts.append(dataclasses.replace(text, text=written) if written != text.text else text)
    return dataclasses.replace(board, texts=tuple(texts))


KICAD_PREDEFINED = {
    "CURRENT_DATE": "Print_Date",
    "FILENAME": "Pcb_File_Name_No_Path",
    "FILEPATH": "Pcb_File_Name",
    "LAYER": "Layer_Name",
}
"""KiCad's board variables of ``PREDEFINED`` → the predefined special string of the same meaning, in the case
the Altium documentation writes it (S-1871; change c0451)."""
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
"""One KiCad text variable whose name is a variable name."""
BACK = "the KiCad text variable {names} is written as the special string of its name"


def altium_text(text: str) -> tuple[str, tuple[str, ...]]:
    """``text`` (a KiCad board text) with a text that is one ``${NAME}`` written as ``.NAME`` and each
    ``${NAME}`` inside other text as ``'.NAME'``, a predefined board variable as its special string
    (``KICAD_PREDEFINED``), and the variables written (change c0451)."""
    found: list[str] = []

    def name_of(match: re.Match[str]) -> str:
        name = match.group(1)
        found.append(match.group(0))
        return KICAD_PREDEFINED.get(name, name)

    whole = VARIABLE.fullmatch(text)
    if whole is not None:
        return "." + name_of(whole), tuple(found)
    return VARIABLE.sub(lambda match: "'." + name_of(match) + "'", text), tuple(found)


def altium_strings(design: Design) -> tuple[Design, dict[str, tuple[str, ...]]]:
    """``design`` (read from a KiCad project) whose board texts hold their text variables as special strings
    (``altium_text``), and the ids of the changed texts by reason."""
    board = design.board
    if board is None:
        return design, {}
    texts: list[Text] = []
    changed: dict[str, list[str]] = {}
    for text in board.texts:
        written, names = altium_text(text.text)
        if names:
            changed.setdefault(BACK.format(names=", ".join(names)), []).append(text.id)
            text = dataclasses.replace(text, text=written)
        texts.append(text)
    if not changed:
        return design, {}
    board = dataclasses.replace(board, texts=tuple(texts))
    return dataclasses.replace(design, board=board), {k: tuple(v) for k, v in changed.items()}


def project_parameter_pairs(design: Design) -> tuple[tuple[str, str], ...]:
    """The text variables of the board (a KiCad project's), as the ``[Parameter<n>]`` entries of an Altium
    project, in their order (change c0451)."""
    board = design.board
    block = board.title_block if board is not None else None
    return tuple(block.params.items()) if block is not None else ()


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
