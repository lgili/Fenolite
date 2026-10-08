# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The primitives of a component become the graphics, the fields and the texts of its footprint (capability
altium-import, "Graphics, fields and texts of a component" and "Footprint instances and pads";
``H-A-IMP-FPGFX``; change c0126)."""

from __future__ import annotations

from pathlib import Path

import _altium_records as rec

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.adapter.board import read_board
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Ids
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.geometry.transform import Transform
from fenolite.model.board import PPM_PER_PERCENT, Board
from fenolite.model.design import Design

DATA = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium"
MIL = rec.MIL
NM = 254  # nanometres in 100 units


def _blink() -> tuple[Design, list[Issue]]:
    issues: list[Issue] = []
    path = DATA / "blink" / "blink.PcbDoc"
    document = read_pcbdoc(path.read_bytes(), file=path.name)
    return import_board(document, file=path.name, sha256=rec.SHA, issues=issues), issues


def _board(design: Design) -> Board:
    assert design.board is not None
    return design.board


def _unmapped(issues: list[Issue]) -> str:
    return " ".join(issue.message for issue in issues if issue.code == "altium.import.unmapped")


def test_silkscreen_of_the_blink_sample() -> None:
    """Scenario "Silkscreen of the blink sample": 27 graphics (24 lines and 3 arcs), the two fields on
    each footprint, and no ``footprint-graphics`` among the unmapped records."""
    design, issues = _blink()
    board = _board(design)
    graphics = [graphic for footprint in board.footprints for graphic in footprint.graphics]
    kinds = sorted(graphic.kind for graphic in graphics)
    assert len(board.footprints) == 3 and len(graphics) == 27
    assert kinds.count("line") == 24 and kinds.count("arc") + kinds.count("circle") == 3
    for footprint in board.footprints:
        assert [field.name for field in footprint.fields] == ["Reference", "Value"]
        assert footprint.texts == ()
        visible = {field.name: field.visible for field in footprint.fields}
        assert visible == {"Reference": True, "Value": False}  # NAMEON and COMMENTON of a build
    assert "footprint-graphics" not in _unmapped(issues)
    assert all(graphic.provenance is not None for graphic in graphics)
    assert len({graphic.id for graphic in graphics}) == 27
    assert not [issue for issue in design.validate() if issue.severity == "error"]
    # every arc keeps its record (change c0127), in the document's frame
    arcs = [graphic for graphic in graphics if graphic.kind == "arc"]
    assert all(dict(graphic.ext["altium"].payload).get("arc") for graphic in arcs)


def test_corner_ratio_of_the_blink_sample() -> None:
    """Scenario "Corner ratio of the blink sample": 5 000 ppm per percent of the pair ``corner_percent``."""
    board = _board(_blink()[0])
    rounded = [pad for footprint in board.footprints for pad in footprint.pads if pad.shape == "roundrect"]
    assert len(rounded) == 34
    for pad in rounded:
        percent = int(dict(pad.ext["altium"].payload)["corner_percent"])
        assert pad.corner_ratio == PPM_PER_PERCENT * percent
    others = [pad for footprint in board.footprints for pad in footprint.pads if pad.shape != "roundrect"]
    assert all(pad.corner_ratio is None for pad in others)


def test_track_of_a_bottom_component() -> None:
    """Scenario "A track of a bottom component": one line on ``B.SilkS`` whose points, placed with the
    footprint's position and angle and no mirror, are the converted ends of the record."""
    a, b = (2000 * MIL, 1500 * MIL), (2100 * MIL, 1550 * MIL)
    document = rec.document(
        components=[rec.component("R1", rotation=90.0, layer="BOTTOM")],
        tracks=[rec.track(a, b, layer=34, component=0)],
    )
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    (footprint,) = _board(design).footprints
    (line,) = footprint.graphics
    assert (line.kind, line.layer, line.filled) == ("line", "B.SilkS", False)
    placement = Transform.placement(footprint.position, footprint.rotation)
    ends = [placement.apply(point) for point in line.points]
    wanted = [Point(x * NM // 100, -y * NM // 100) for x, y in (a, b)]
    for mine, theirs in zip(ends, wanted, strict=True):
        assert abs(mine.x - theirs.x) <= 1 and abs(mine.y - theirs.y) <= 1
    assert _board(design).graphics == () or all(g.layer == "Edge.Cuts" for g in _board(design).graphics)


def test_designator_and_comment() -> None:
    """Scenario "Designator and comment": the fields at the texts' places, shown as ``NAMEON`` and
    ``COMMENTON`` say; a second designator text and a plain text are texts of the footprint."""
    document = rec.document(
        components=[rec.component("R1", extra={"NAMEON": "TRUE", "COMMENTON": "FALSE"})],
        texts=[
            rec.text("R1", (2000 * MIL, 1600 * MIL), designator=True, component=0),
            rec.text("10k", (2000 * MIL, 1400 * MIL), comment=True, component=0),
        ],
    )
    issues: list[Issue] = []
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    (footprint,) = _board(design).footprints
    reference, value = footprint.fields
    assert (reference.name, reference.visible, value.name, value.visible) == (
        "Reference",
        True,
        "Value",
        False,
    )
    assert reference.position == Point(0, -100 * NM * 100) and value.position == Point(0, 100 * NM * 100)
    assert reference.size.h == 60 * NM * 100 and reference.layer == "F.SilkS"
    assert footprint.texts == () and _board(design).texts == ()
    (component,) = design.circuit.components
    assert (component.ref, component.value) == ("R1", "10k")
    assert "footprint-graphics" not in _unmapped(issues)

    more = rec.document(
        components=[rec.component("R1", rotation=90.0)],
        texts=[
            rec.text("R1", designator=True, component=0),
            rec.text("R1b", designator=True, component=0),
            rec.text(".Designator", component=0),
        ],
    )
    (footprint,) = _board(import_board(more, file="a.PcbDoc", sha256=rec.SHA)).footprints
    assert [field.name for field in footprint.fields] == ["Reference"]
    assert [text.text for text in footprint.texts] == ["R1b", ".Designator"]
    assert footprint.fields[0].rotation == 270_000_000  # the text's angle 0, relative to the footprint
    assert footprint.fields[0].visible is True  # a record without NAMEON: shown


def test_every_kind_is_mapped_and_the_census_is_conserved() -> None:
    """A track, an arc, a full circle, a fill, a turned fill and a region of one component: six graphics in
    the order tracks, arcs, fills, regions; each record counts as mapped; a copper graphic keeps its net."""
    document = rec.document(
        nets=["GND"],
        components=[rec.component("R1"), rec.component("R2", x="")],
        tracks=[
            rec.track((0, 0), (9 * MIL, 0), layer=33, component=0),
            rec.track((0, 0), (9, 0), layer=1, net=0, component=0),
        ],
        arcs=[
            rec.arc((0, 0), 100 * MIL, 0.0, 90.0, layer=33, component=0),
            rec.arc((0, 0), 100 * MIL, 0.0, 360.0, layer=33, component=0),
            rec.arc((0, 0), 0, 0.0, 90.0, layer=33, component=0),
            rec.arc((0, 0), 100 * MIL, 0.0, 90.0, layer=33, component=1),
        ],
        fills=[rec.fill((0, 0), (9 * MIL, 9 * MIL), component=0)],
        regions=[rec.region([(0, 0), (9 * MIL, 0), (9 * MIL, 9 * MIL)], layer=33, component=0)],
    )
    issues: list[Issue] = []
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    (footprint,) = _board(design).footprints  # R2 has no readable position
    assert [(g.kind, g.filled) for g in footprint.graphics] == [
        ("line", False),
        ("line", False),
        ("arc", False),
        ("circle", False),
        ("rect", True),
        ("polygon", True),
    ]
    copper = footprint.graphics[1]
    assert copper.layer == "F.Cu" and dict(copper.ext["altium"].payload)["net"] == "GND"
    assert _board(design).tracks == () and _board(design).arcs == ()
    census = read_board(document, file="a.PcbDoc", sha256=rec.SHA, ids=Ids("altium_pcbdoc", EVIDENCE)).census
    for kind, count in (("tracks", 2), ("arcs", 4), ("fills", 1), ("regions", 1)):
        assert census.total(kind) == count, kind
    message = _unmapped(issues)
    assert "bad-geometry 1" in message and "footprint-graphics 1" in message  # the arc of R2
