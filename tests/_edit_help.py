# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the command-level tests of the edit merge (change c0250): the base record of a built
blink, token edits of its board and schematic, and the issues of a reply."""

from __future__ import annotations

import json

from _layout_edit import edit_properties
from _project import Project, footprint

from fenolite.backends.kicad.sch import read_schematic


def base_of(p: Project) -> dict[str, dict[str, dict[str, object]]]:
    return json.loads((p.out / "fenolite-base.json").read_text(encoding="utf-8"))["parts"]


def edit(
    p: Project, changes: dict[str, dict[str, object]], *, board: bool = True, schematic: bool = False
) -> None:
    sheet = p.out / "blink.kicad_sch"
    board_text, sheet_text = edit_properties(
        p.board.read_text(encoding="utf-8") if board else None,
        sheet.read_text(encoding="utf-8") if schematic else None,
        changes,
    )
    if board_text is not None:
        p.board.write_text(board_text, encoding="utf-8")
    if sheet_text is not None:
        sheet.write_text(sheet_text, encoding="utf-8")


def value(p: Project, ref: str) -> tuple[str, str]:
    """The value of ``ref`` on the board and in the schematic."""
    _, component = footprint(p.read(), ref)
    sheet = read_schematic(p.out / "blink.kicad_sch")
    (symbol,) = [s for s in sheet.symbols if s.ref == ref]
    return component.value, symbol.value  # type: ignore[attr-defined]


def issues(env: dict[str, object], code: str) -> list[dict[str, str]]:
    return [i for i in env["issues"] if i["code"] == code]  # type: ignore[union-attr, index, misc]


__all__ = ["base_of", "edit", "issues", "value"]
