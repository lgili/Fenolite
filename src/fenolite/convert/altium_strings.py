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
from typing import TYPE_CHECKING

from fenolite.model.board import Board, Text

if TYPE_CHECKING:
    from fenolite.convert.altium_to_kicad import Ledger

QUOTED = re.compile(r"'\.([^']+)'")
"""One special string inside other text: a name after ``.``, enclosed in apostrophes."""
UNMAPPED = "the special string {names} names no project parameter: written as typed"


def _variable(name: str, params: Mapping[str, str]) -> str | None:
    return "${" + name + "}" if name in params else None


def special_text(text: str, params: Mapping[str, str]) -> tuple[str, tuple[str, ...]]:
    """``text`` with each special string that names a key of ``params`` written as ``${NAME}``, and the
    names of the other special strings, which stay as typed."""
    if text.startswith(".") and "'" not in text:
        found = _variable(text[1:], params)
        return (found, ()) if found is not None else (text, (text,))
    others: list[str] = []

    def replace(match: re.Match[str]) -> str:
        found = _variable(match.group(1), params)
        if found is None:
            others.append("." + match.group(1))
            return match.group(0)
        return found

    return QUOTED.sub(replace, text), tuple(others)


def board_strings(board: Board, ledger: Ledger) -> Board:
    """``board`` with the special strings of its texts that name its text variables written as ``${NAME}``."""
    params = board.title_block.params if board.title_block is not None else {}
    texts: list[Text] = []
    for text in board.texts:
        written, others = special_text(text.text, params)
        if others:
            ledger.change("text", text.id, UNMAPPED.format(names=", ".join(others)))
        texts.append(dataclasses.replace(text, text=written) if written != text.text else text)
    return dataclasses.replace(board, texts=tuple(texts))


__all__ = ["QUOTED", "board_strings", "special_text"]
