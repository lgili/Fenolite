# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Mask and paste of imported pads, and the pad margins of the KiCad writers (capability design-conversion,
"Mask and paste of imported pads" and "Pad margins in the KiCad writers"; change c0223)."""

from __future__ import annotations

import dataclasses

import pytest

from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point, Size
from fenolite.model.board import Pad
from fenolite.model.library import FootprintDef

MASK = 100_000  # 0.1 mm

READ = """(footprint "R" (version 20241229) (generator "pcbnew")
  (layer "F.Cu")
  (attr smd)
  (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05)
    (uuid "00000000-0000-0000-0000-000000000001"))
)
"""


def _pad(**changes: object) -> Pad:
    pad = Pad(
        id="pad-1",
        number="1",
        shape="rect",
        size=Size(1_000_000, 1_000_000),
        position=Point(0, 0),
        layers=("F.Cu", "F.Paste", "F.Mask"),
    )
    return dataclasses.replace(pad, **changes)  # type: ignore[arg-type]


def _margins(text: str) -> list[tuple[str, str]]:
    root = parse(text)
    pads = [*root.nodes("pad"), *(p for fp in root.nodes("footprint") for p in fp.nodes("pad"))]
    return [
        (child.name, child.atoms()[0].value)
        for pad in pads
        for child in pad.nodes()
        if child.name in ("solder_mask_margin", "solder_paste_margin")
    ]


def test_writer_writes_the_margins_of_an_authored_pad() -> None:
    """Scenario "A margin written and a kept one guarded", the first footprint."""
    definition = FootprintDef(id="fpd-r", name="R", pads=(_pad(mask_margin=MASK, paste_margin=-50_000),))
    text = write_footprint(definition, target=10)
    assert _margins(text) == [("solder_mask_margin", "0.1"), ("solder_paste_margin", "-0.05")]
    pad = parse(text).nodes("pad")[0]
    heads = [child.name for child in pad.nodes()]
    assert heads.index("layers") < heads.index("solder_mask_margin") < heads.index("solder_paste_margin")


def test_writer_keeps_a_read_margin_and_refuses_another() -> None:
    """Scenario "A margin written and a kept one guarded", the second footprint."""
    read = read_footprint(READ)
    assert read.pads[0].mask_margin == 50_000
    assert _margins(write_footprint(read, target=10)) == [("solder_mask_margin", "0.05")]
    same = dataclasses.replace(read, pads=(dataclasses.replace(read.pads[0], mask_margin=50_000),))
    assert _margins(write_footprint(same, target=10)) == [("solder_mask_margin", "0.05")]
    other = dataclasses.replace(read, pads=(dataclasses.replace(read.pads[0], mask_margin=MASK),))
    with pytest.raises(LossyWriteError) as refused:
        write_footprint(other, target=10)
    assert any("mask_margin" in issue.message for issue in refused.value.issues)


def test_writer_writes_the_margin_of_a_board_pad() -> None:
    """The board writer writes the field of a created pad, after its net and before its uuid."""
    from _convert import two_layer

    design = two_layer()
    assert design.board is not None
    footprint = design.board.footprints[0]
    stripped = dataclasses.replace(
        footprint.pads[0], ext={}, native_ids={}, mask_margin=MASK, paste_margin=None
    )
    footprints = (dataclasses.replace(footprint, pads=(stripped, *footprint.pads[1:])),)
    board = dataclasses.replace(design.board, footprints=(*footprints, *design.board.footprints[1:]))
    text = write_board(dataclasses.replace(design, board=board), target=10).text
    assert _margins(text) == [("solder_mask_margin", "0.1")]
    again = read_board(text)
    assert again.board is not None and again.board.footprints[0].pads[0].mask_margin == MASK


def _imported(number: str, kind: str, layers: tuple[str, ...], **pairs: str) -> Pad:
    from fenolite.model.base import ExtBag

    pad = _pad(number=number, kind=kind, layers=layers, drill=None if kind == "smd" else 800_000)
    ext = {"altium": ExtBag("altium", tuple(pairs.items()))} if pairs else {}
    return dataclasses.replace(pad, id=f"pad-{number}", ext=ext)


def test_openings_by_kind() -> None:
    """Scenario "Openings after conversion": the layers and the margins of the three kinds."""
    from fenolite.convert.openings import RuleExpansions, open_pad

    rules = RuleExpansions()
    surface, why = open_pad(_imported("1", "smd", ("F.Cu",), mask="2,20000"), rules)
    assert surface.layers == ("F.Cu", "F.Paste", "F.Mask") and why == ()
    assert (surface.mask_margin, surface.paste_margin) == (50_800, None)
    bottom, _ = open_pad(_imported("2", "smd", ("B.Cu",), paste="2,-10000"), rules)
    assert bottom.layers == ("B.Cu", "B.Paste", "B.Mask") and bottom.paste_margin == -25_400
    plated, _ = open_pad(_imported("3", "thru_hole", ("F.Cu", "B.Cu")), rules)
    hole, _ = open_pad(_imported("4", "np_thru_hole", ("F.Cu", "B.Cu")), rules)
    for pad in (plated, hole):
        assert pad.layers == ("F.Cu", "B.Cu", "F.Mask", "B.Mask") and pad.paste_margin is None
    inner, _ = open_pad(_imported("5", "smd", ("In1.Cu",)), rules)
    assert inner.layers == ("In1.Cu",)


def test_rule_expansions() -> None:
    """Scenario "A scoped rule is reported", and the rule of scope ``All`` alone."""
    from fenolite.convert.openings import MASK_RULE, SCOPED_REASON, RuleExpansions, open_pad, rule_expansion

    every = {"RULEKIND": MASK_RULE, "PRIORITY": "2", "SCOPE1EXPRESSION": "All", "EXPANSION": "4mil"}
    scoped = {**every, "PRIORITY": "1", "SCOPE1EXPRESSION": "IsPad", "EXPANSION": "1mil"}
    off = {**scoped, "ENABLED": "FALSE"}
    assert rule_expansion([every, off], MASK_RULE).scoped is False
    found = rule_expansion([every, scoped], MASK_RULE)
    assert found.value == 101_600 and found.scoped
    pad, why = open_pad(_imported("1", "smd", ("F.Cu",)), RuleExpansions(mask=found))
    assert pad.mask_margin == 101_600 and why == (SCOPED_REASON,)
    only = RuleExpansions(mask=rule_expansion([every], MASK_RULE))
    alone, why = open_pad(_imported("1", "smd", ("F.Cu",)), only)
    assert alone.mask_margin == 101_600 and why == ()


@pytest.mark.parametrize("scope", ["IsVia", "IsTrack", "IsVia Or IsTrack", "IsVia And InNet('GND')"])
def test_rule_of_no_pad_is_left_out(scope: str) -> None:
    """Scenario "A rule of vias is no pad's": a rule whose scope selects no pad comes before the rule of
    scope ``All`` (the public documents of the census hold ``IsVia`` so) and makes no ``pad-margin`` row."""
    from fenolite.convert.openings import MASK_RULE, rule_expansion

    every = {"RULEKIND": MASK_RULE, "PRIORITY": "2", "SCOPE1EXPRESSION": "All", "EXPANSION": "4mil"}
    vias = {**every, "PRIORITY": "1", "SCOPE1EXPRESSION": scope, "EXPANSION": "1mil"}
    found = rule_expansion([every, vias], MASK_RULE)
    assert found.value == 101_600 and not found.scoped
    either = {**vias, "SCOPE1EXPRESSION": "IsVia Or IsPad"}
    assert rule_expansion([every, either], MASK_RULE).scoped


def test_converted_blink_has_openings() -> None:
    """The authored Altium project ``blink``: surface pads gain paste and mask, through-hole pads both
    masks, and the derived library keeps them."""
    from pathlib import Path

    from fenolite.convert import convert_project

    root = Path(__file__).resolve().parents[3]
    project = root / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
    conversion = convert_project(project, to="kicad", kicad_version=10, allow_lossy=True)
    board = parse(conversion.files["blink.kicad_pcb"].decode())
    found: set[tuple[str, tuple[str, ...]]] = set()
    for footprint in board.nodes("footprint"):
        for pad in footprint.nodes("pad"):
            layers = pad.find("layers")
            assert layers is not None
            found.add((pad.atoms()[1].value, tuple(atom.value for atom in layers.atoms())))
    assert ("smd", ("F.Cu", "F.Paste", "F.Mask")) in found
    assert ("thru_hole", ("F.Cu", "B.Cu", "F.Mask", "B.Mask")) in found
    library = [data.decode() for key, data in conversion.files.items() if key.endswith(".kicad_mod")]
    assert library and all('"F.Mask"' in text for text in library)
    row = conversion.report.row("pad-margin")
    assert row is not None and row.lost == 0
