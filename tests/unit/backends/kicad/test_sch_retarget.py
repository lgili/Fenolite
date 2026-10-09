# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A schematic sheet and a symbol library of KiCad 10 written for KiCad 9 (change c0162, task 2.3;
capability kicad-version-gating, "Downgrade edits").

The RT1 of a re-targeted sheet: the written text, read back, holds the model of the source (the model does
not hold the constructs the resolver drops or rewrites), and its tree holds every node of the source but the
edited ones."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fenolite.backends.kicad import resolver
from fenolite.backends.kicad.sch import read_schematic, rebuild_schematic, retarget_schematic
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.backends.kicad.sym import read_symbol_library, retarget_symbol_library
from fenolite.backends.kicad.versions import (
    DowngradeRefusedError,
    FileKind,
    LossyWriteError,
    check_emittable,
)
from fenolite.model.canonical import to_data

TOKENS = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "tokens"
SKELETON = (TOKENS / "skeleton.kicad_sch").read_text(encoding="utf-8")
LIBRARY = (TOKENS / "skeleton.kicad_sym").read_text(encoding="utf-8")


def ten_sheet(*, pos: str = "yes") -> str:
    """The fuzz skeleton at the header of 10.0 with the constructs of the demo sheets of format 10."""
    text = SKELETON.replace("(version 20231120)", "(version 20260306)")
    added = "\t\t\t(power global)\n\t\t\t(in_pos_files yes)\n\t\t\t(duplicate_pin_numbers_are_jumpers no)\n"
    text = text.replace("\t\t\t(exclude_from_sim no)\n", added + "\t\t\t(exclude_from_sim no)\n", 1)
    return text.replace("\t\t(unit 1)\n", f"\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(in_pos_files {pos})\n", 1)


def _model(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _model(v) for k, v in value.items() if k not in ("provenance", "ext")}  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, list):
        return [_model(v) for v in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def test_refused_without_downgrade() -> None:
    with pytest.raises(DowngradeRefusedError) as refused:
        retarget_schematic(read_schematic(ten_sheet()), target=9)
    assert "fenolite convert" in refused.value.hint


def test_rt1_of_a_retargeted_sheet() -> None:
    sheet = read_schematic(ten_sheet(), file="sheet.kicad_sch")
    edits: list[resolver.Edit] = []
    text = retarget_schematic(sheet, target=9, downgrade=True, edits=edits)
    tree = parse(text)
    assert "(version 20250114)" in text.splitlines()[1]
    assert not [i for i in check_emittable(tree, FileKind.SCHEMATIC, 9) if i.severity == "error"]
    assert sorted((e.row, e.action) for e in edits) == [
        ("sch-lib-in-pos-files", "same"), ("sch-lib-power-global", "rewrite"),
        ("sch-symbol-body-style", "rewrite"), ("sch-symbol-in-pos-files", "same"),
        ("sym-jumpers-duplicate", "same"),
    ]  # fmt: skip
    again = read_schematic(text, file="sheet.kicad_sch")
    assert _model(to_data(again)) == _model(to_data(sheet))
    symbol = tree.find("symbol")
    assert symbol is not None and [a.text for a in (symbol.find("convert") or symbol).atoms()] == ["1"]
    source = rebuild_schematic(sheet)
    removed = {"in_pos_files", "duplicate_pin_numbers_are_jumpers", "body_style"}
    kept = [line for line in dumps(source).splitlines() if not any(f"({h}" in line for h in removed)]
    written = text.splitlines()
    assert len(written) == len(kept) + 1  # (convert 1) in place of (body_style 1)


def test_design_loss_needs_consent() -> None:
    """A symbol left out of the position files (``in_pos_files no``) is a design loss (open question 3)."""
    sheet = read_schematic(ten_sheet(pos="no"))
    with pytest.raises(LossyWriteError) as refused:
        retarget_schematic(sheet, target=9, downgrade=True)
    assert [resolver.row_id(i) for i in refused.value.issues] == ["sch-symbol-in-pos-files"]
    issues: list[Any] = []
    text = retarget_schematic(sheet, target=9, downgrade=True, allow_lossy=True, issues=issues)
    assert "in_pos_files" not in text
    assert [i.hint for i in issues if i.code == resolver.LOST_CODE] == [
        "row sch-symbol-in-pos-files (design)"
    ]


def test_same_major_is_the_rebuild() -> None:
    sheet = read_schematic(ten_sheet())
    assert retarget_schematic(sheet, target=10) == dumps(rebuild_schematic(sheet))
    nine = read_schematic(SKELETON.replace("(version 20231120)", "(version 20250114)"))
    with pytest.raises(ValueError, match="older major only"):
        retarget_schematic(nine, target=10)


def test_symbol_library_downgrade() -> None:
    text = LIBRARY.replace("(version 20231120)", "(version 20251024)").replace(
        '\t(symbol "Mini_R"\n', '\t(symbol "Mini_R"\n\t\t(power global)\n\t\t(in_pos_files yes)\n', 1
    )
    assert text.count("(power global)") == 1
    with pytest.raises(DowngradeRefusedError):
        retarget_symbol_library(text, target=9)
    edits: list[resolver.Edit] = []
    written = retarget_symbol_library(text, target=9, downgrade=True, edits=edits)
    assert "(version 20241209)" in written and "in_pos_files" not in written and "(power)" in written
    assert sorted((e.row, e.action) for e in edits) == [
        ("sym-in-pos-files", "same"),
        ("sym-power-global", "rewrite"),
    ]
    assert [s.name for s in read_symbol_library(written, library="L")] == [
        s.name for s in read_symbol_library(text, library="L")
    ]
    assert retarget_symbol_library(text, target=10) == text
