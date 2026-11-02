# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing specification lowered to measured Draftsman shells (c0172).

Layout uses c0117's pure glyph bounds and page packing. The board table is readable Texts until its
native serialization is observed. Native dimensions, BOM filtering and board refresh await Part F.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from fenolite.backends.altium.draftsman import DraftsmanItem, DraftsmanSheet, DraftsmanSpec
from fenolite.core.errors import Issue
from fenolite.exports.drawing_layout import Obstacles, choose_paper
from fenolite.exports.drawing_spec import DEFAULT, DrawingSpec
from fenolite.exports.drawing_tables import Block, fab_blocks, make_block, notes_block, outline_box
from fenolite.model.design import Design

_MM = 1_000_000
DEFERRED = (
    "PCB data refresh and source binding await FP4",
    "native board Table and Linear Dimensions await F0",
    "native table sizing and BOM view filtering await F0/FP4",
)


def title_parameters(design: Design) -> tuple[tuple[str, str], ...]:
    """The non-empty title-block fields, in the existing Altium mapping's argument order."""
    from fenolite.lens.altium import SHEET_PARAMETERS

    block = design.board.title_block if design.board is not None else None
    if block is None:
        return ()
    result = [(name, getattr(block, field)) for field, name in SHEET_PARAMETERS if getattr(block, field)]
    taken = {name.casefold() for _, name in SHEET_PARAMETERS}
    for name, value in sorted(block.params.items()):
        if name.casefold() in taken:
            raise ValueError(f"title-block parameter {name!r} duplicates a reserved field")
        if value:
            result.append((name, value))
        taken.add(name.casefold())
    return tuple(result)


def _not_lowered(message: str, where: str = "draftsman") -> Issue:
    return Issue("altium.not-lowered", "info", message, where=where)


def _sheet(
    *,
    name: str,
    title: str,
    kind: str,
    side: str,
    bounds: tuple[int, int],
    blocks: Sequence[Block],
    spec: DrawingSpec,
    notes: tuple[str, ...],
    fixed: dict[str, tuple[int, int]],
) -> DraftsmanSheet:
    def obstacles(width: int, height: int) -> Obstacles:
        return Obstacles(
            (10 * _MM, 10 * _MM, width - 10 * _MM, height - 10 * _MM),
            ((width - 110 * _MM, height - 45 * _MM, width - 10 * _MM, height - 10 * _MM),),
        )

    board = (20 * _MM, 20 * _MM, 20 * _MM + bounds[0], 20 * _MM + bounds[1])
    page = choose_paper(
        blocks,
        paper=spec.page.paper,
        portrait=spec.page.portrait,
        board_box=lambda _: board,
        obstacles=obstacles,
        gap=spec.page.gap,
        fixed=fixed,
    )
    if page.problem is not None:
        raise ValueError(f"Draftsman {name}: {page.problem.what} does not fit {page.paper}")
    height = page.size[1]
    view_kind: Literal["DrillViewView", "BoardAssemblyViewData"] = (
        "DrillViewView" if kind == "fab" else "BoardAssemblyViewData"
    )
    view_side: Literal["Top", "Bottom"] = "Bottom" if side == "bottom" else "Top"
    items = [
        DraftsmanItem(
            "view",
            view_kind,
            (board[0], height - board[3]),
            bounds,
            title=title,
            side=view_side,
            designators=spec.assembly.designators,
        )
    ]
    by_name = {block.name: block for block in blocks}
    for placed in page.placed:
        block = by_name[placed.name]
        at = (placed.at[0], height - placed.at[1] - placed.size[1])
        native = {
            "drill": "DrillTableBoardView",
            "stackup": "LayerStackLegendView",
            "bom": "BillOfMaterialsView",
        }
        if block.name == "notes":
            item = DraftsmanItem("notes", "Note", at, placed.size, title="Notes", texts=notes)
        elif block.name in native:
            # These three tags are already measured. Their unseen binding/filter fields are not guessed.
            if block.name == "drill":
                item = DraftsmanItem("drill", "DrillTableBoardView", at, placed.size)
            elif block.name == "stackup":
                item = DraftsmanItem("stackup", "LayerStackLegendView", at, placed.size)
            else:
                item = DraftsmanItem("bom", "BillOfMaterialsView", at, placed.size, side=view_side)
        else:
            text = "\r\n".join("  ".join(row) for row in block.rows)
            item = DraftsmanItem(block.name, "Text", at, placed.size, texts=(text,))
        items.append(item)
    # The reserved title area is expressed in the same lower-left frame as every item.
    fields = (title, "=Title", "=Revision", "=Date", "=SheetNumber", "=SheetTotal")
    for number, value in enumerate(fields):
        items.append(
            DraftsmanItem(
                f"title/{number}",
                "Text",
                (page.size[0] - 110 * _MM, (35 - number * 4) * _MM),
                (100 * _MM, 4 * _MM),
                texts=(value,),
            )
        )
    return DraftsmanSheet(name, title, page.paper, page.size, tuple(items))


def draftsman_spec(design: Design, spec: DrawingSpec = DEFAULT) -> tuple[DraftsmanSpec, tuple[Issue, ...]]:
    """A fabrication sheet and each populated requested assembly side, with explicit deferred members."""
    box = outline_box(design)
    if design.board is None or box is None:
        raise ValueError("a Draftsman document needs a board outline")
    bounds = (box[2] - box[0], box[3] - box[1])
    blocks, issues = fab_blocks(design, spec)
    if "drill" in spec.fab.tables and not any(block.name == "drill" for block in blocks):
        blocks = (
            *blocks,
            make_block("drill", (("Drill table",), ("No drilled holes",)), spec.page.text_size),
        )
    sheets = [
        _sheet(
            name="fab",
            title=spec.fab.title,
            kind="fab",
            side="top",
            bounds=bounds,
            blocks=blocks,
            spec=spec,
            notes=spec.fab.notes,
            fixed=dict(spec.fab.at),
        )
    ]
    for side in spec.assembly.sides:
        if not any(fp.side == side for fp in design.board.footprints):
            continue
        blocks = (make_block("bom", (("Bill of materials",), ("Filled by Altium",)), spec.page.text_size),)
        notes = spec.assembly.notes if side == "top" else ()
        note = notes_block(notes, spec.page.notes_width, spec.page.text_size)
        if note is not None:
            blocks = (*blocks, note)
        title = spec.assembly.title_bottom if side == "bottom" else spec.assembly.title_top
        sheets.append(
            _sheet(
                name=f"assembly-{side}",
                title=title,
                kind="assembly",
                side=side,
                bounds=bounds,
                blocks=blocks,
                spec=spec,
                notes=notes,
                fixed=dict(spec.assembly.at),
            )
        )
    found = [
        *(_not_lowered(i.message, f"draftsman.{i.where}") for i in issues),
        *(_not_lowered(text) for text in DEFERRED),
    ]
    refs = sorted(c.ref for c in design.circuit.components if c.dnp)
    if refs:
        found.append(_not_lowered("Draftsman has no variant: DNP parts remain fitted: " + ", ".join(refs)))
    if (
        spec.assembly.values
        or spec.assembly.pads
        or spec.assembly.designator_size != DEFAULT.assembly.designator_size
    ):
        found.append(_not_lowered("Draftsman values/pads/designator-size overrides await F0"))
    if spec.page.drawing_sheet:
        found.append(_not_lowered("Draftsman uses parameter Texts; the drawing-sheet frame is not lowered"))
    return DraftsmanSpec(
        design.header.name, tuple(sheets), title_parameters(design), spec.page.text_size
    ), tuple(found)


def document_summary(spec: DraftsmanSpec) -> dict[str, object]:
    return {
        "file": f"{spec.name}.PCBDwf",
        "route": "native-candidate",
        "sheets": [
            {"title": sheet.title, "paper": sheet.paper, "objects": [item.kind for item in sheet.items]}
            for sheet in spec.sheets
        ],
        "not_lowered": list(DEFERRED),
        "spec": None,
    }


__all__ = ["DEFERRED", "document_summary", "draftsman_spec", "title_parameters"]
