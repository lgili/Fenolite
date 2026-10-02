# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout predictor (capability sheet-templates, "Sheet layout prediction" and "Zone labels on A4 and A3";
change c0012). ``layout`` reproduces the literal expectations of the probe spike (task 8.3)."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import _expected as ex
import pytest
from _sheet_bench import SHEETS
from _specs import ZONES

from fenolite.backends.kicad.wks import read_drawing_sheet
from fenolite.model.presentation import (
    DrawingSheet,
    SheetPoint,
    SheetRepeat,
    SheetSetup,
    SheetShape,
    SheetText,
    TitleBlock,
)
from fenolite.templates import build_sheet, layout, load_spec, resolve_text

MM = 1_000_000
SETUP = SheetSetup((1_500_000, 1_500_000), 150_000, 150_000, 10 * MM, 10 * MM, 10 * MM, 10 * MM)


def sheet(*items: object) -> DrawingSheet:
    from fenolite.core.ids import derived_id

    return DrawingSheet(id=derived_id("wks", "template", "l"), name="l", setup=SETUP, items=tuple(items))  # type: ignore[arg-type]


def test_default_corner_is_bottom_right() -> None:
    lay = layout(sheet(SheetText("X", SheetPoint("rb", 5 * MM, 3 * MM))), width=297 * MM, height=210 * MM)
    assert [(t.x, t.y) for t in lay.texts] == [(282 * MM, 197 * MM)]


def test_copies_stop_at_the_margin_box() -> None:
    item = SheetText(
        "A", SheetPoint("lt", 0, 10 * MM), repeat=SheetRepeat(count=10, step_y=50 * MM, label_step=1)
    )
    lay = layout(sheet(item), width=297 * MM, height=210 * MM)
    assert [t.text for t in lay.texts] == ["A", "B", "C", "D"]


def test_scopes_and_shapes() -> None:
    items = (
        SheetText("first", SheetPoint("lt", MM, MM), scope="first_only"),
        SheetText("later", SheetPoint("lt", MM, MM), scope="not_first"),
        SheetShape("rect", SheetPoint("lt"), SheetPoint("rb")),
        SheetShape("line", SheetPoint("lt"), SheetPoint("lt", MM, 0)),
    )
    one = layout(sheet(*items), width=100 * MM, height=50 * MM)
    two = layout(sheet(*items), width=100 * MM, height=50 * MM, page=2)
    assert [t.text for t in one.texts] == ["first"] and [t.text for t in two.texts] == ["later"]
    assert len(one.lines) == 5


def test_numbers_step_past_nine() -> None:
    item = SheetText("1", SheetPoint("lt"), repeat=SheetRepeat(count=12, step_x=5 * MM))
    assert [t.text for t in layout(sheet(item), width=297 * MM, height=210 * MM).texts][-3:] == [
        "10",
        "11",
        "12",
    ]


def test_tokens_resolved() -> None:
    block = TitleBlock(title="Bench", revision="B", params={"LOT": "7"})
    text = "{title} rev {revision} lot {param:LOT} {sheet}/{sheets} {{x}}"
    assert resolve_text(text, block, paper="A4", filename="b.kicad_pcb") == "Bench rev B lot 7 1/1 {x}"
    assert (
        resolve_text("{param:NOPE} {paper} {filename}", block, paper="User", filename="f")
        == "{param:NOPE} User f"
    )


def test_zone_labels_on_a4_and_a3() -> None:
    built = build_sheet(load_spec(ZONES))
    a4 = sorted(t.text for t in layout(built, width=297 * MM, height=210 * MM).texts)
    a3 = sorted(t.text for t in layout(built, width=420 * MM, height=297 * MM).texts)
    assert a4 == sorted([*"12345" * 2, *"ABCD" * 2])
    assert a3 == sorted([*"12345678" * 2, *"ABCDEF" * 2])


PAGES = {"A4": (Decimal("297.0022"), Decimal("210.0072")), "A3": (Decimal("419.9890"), Decimal("297.0022"))}
PROBES = {"wks-corners": ("probe_corners", ("A4", "A3")), "wks-repeat": ("probe_repeat", ("A4", "A3")),
          "wks-tokens": ("probe_tokens", ("A4",))}  # fmt: skip
"""``wks-percent`` is left out: its texts hold legacy ``%`` codes, so the reader keeps them opaque and no
neutral sheet holds them (``kicad.wks.literal-variable``)."""


def predicted(probe: str, page: str) -> list[tuple[str, Decimal, Decimal]]:
    name, _ = PROBES[probe]
    width, height = PAGES[page]
    read = read_drawing_sheet(SHEETS / f"{name}.kicad_wks")
    block = dataclasses.replace(ex.TITLE, params=dict([ex.PARAMETER]))
    lay = layout(read, width=int(width * MM), height=int(height * MM))
    return sorted(
        (
            resolve_text(t.text, block, paper=page, filename="board.kicad_pcb"),
            Decimal(t.x) / MM,
            Decimal(t.y) / MM,
        )
        for t in lay.texts
    )


@pytest.mark.parametrize(("probe", "page"), [(p, page) for p, (_, pages) in PROBES.items() for page in pages])
def test_layout_reproduces_the_literal_expectations(probe: str, page: str) -> None:
    width, height = PAGES[page]
    literal = sorted((e.text, e.x, e.y) for e in ex.expected(probe, width, height))
    assert predicted(probe, page) == literal
