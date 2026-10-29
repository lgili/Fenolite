# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``analysis.region``: one region of a board drawn as SVG from the model (change c0211; capability
manufacturing-exports, "Region renders"). Hermetic: the tests read the SVG's elements and their coordinates,
never pixels, on the authored bench of ``tests/_regionviewbench.py``."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import _regionviewbench as rv
import pytest
from _groundties import ground

from fenolite.analysis import connectivity as conn
from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.connectivity import connectivity
from fenolite.analysis.pour import pour_copper
from fenolite.analysis.region import (
    EVIDENCE,
    MAX_LINES,
    Region,
    RegionDrawing,
    auto_grid,
    check_grid,
    draw_region,
    grid_lines,
    mm,
)
from fenolite.backends.kicad.frame import board_pads
from fenolite.model.design import Design

MM = 1_000_000
NS = "{http://www.w3.org/2000/svg}"
REGION = Region(0, 0, 20 * MM, 20 * MM)


def drawn(design: Design, **options: object) -> tuple[RegionDrawing, ET.Element]:
    pads = board_pads(design)
    assert design.board is not None
    boundary = board_boundary(design.board)
    pour = pour_copper(design, pads=pads, boundary=boundary)
    opened = connectivity(design, pads=pads, pour=pour)
    drawing = draw_region(
        design,
        region=REGION,
        pads=pads,
        boundary=boundary,
        pour=pour,
        opened=opened,
        **options,  # type: ignore[arg-type]
    )
    return drawing, ET.fromstring(drawing.svg)


def of_class(root: ET.Element, name: str) -> list[ET.Element]:
    return [element for element in root.iter() if element.get("class") == name]


def test_open_connections_in_a_region() -> None:
    """Scenario "Open connections in a region": two lines of the class ``open`` and one net label per pad
    with a net in the region, at the pads' board coordinates in millimetres."""
    drawing, root = drawn(rv.bench(), nets=True)
    lines = sorted(
        (line.get("data-net"), line.get("x1"), line.get("y1"), line.get("x2"), line.get("y2"))
        for line in of_class(root, "open")
    )
    assert lines == [("L1", "5", "5", "15", "5"), ("L2", "5", "15", "15", "15")]
    labels = {
        label.get("data-pad"): (label.text, label.get("x"), label.get("y"))
        for label in of_class(root, "net-label")
    }
    assert sorted(labels) == list(rv.LABELLED)
    assert labels["H1-1"] == ("H", "10", "10") and labels["B2-1"] == ("L2", "15", "15")
    assert [(net, link.a.where, link.b.where) for net, link in drawing.open] == [
        ("L1", "A1-1", "B1-1"),
        ("L2", "A2-1", "B2-1"),
    ]


def test_items_of_the_region() -> None:
    """Pads, the slot, the via and its hole, the saved fill and the edge are drawn; the parts outside the
    region are not."""
    drawing, root = drawn(rv.bench())
    pads = {(pad.get("data-where"), pad.get("data-layer")) for pad in of_class(root, "pad")}
    assert ("H1-1", "B.Cu") in pads and ("H1-1", "F.Cu") in pads and ("A1-1", "F.Cu") in pads
    assert not {where for where, _ in pads} & {"C1-1", "C2-1"} and not of_class(root, "track")
    (slot,) = of_class(root, "slot")
    assert (slot.get("d"), slot.get("stroke-width"), slot.get("data-plated")) == (
        "M9.25 10 L10.75 10",
        "0.5",
        "true",
    )
    (via,) = of_class(root, "via")
    assert (via.get("cx"), via.get("cy"), via.get("r"), via.get("data-net")) == ("10", "18", "0.3", "GND")
    (hole,) = of_class(root, "hole")
    assert (hole.get("cx"), hole.get("cy"), hole.get("r")) == ("10", "18", "0.15")
    (zone,) = of_class(root, "zone")
    assert (zone.get("data-state"), zone.get("data-layer"), zone.get("d")) == (
        "saved_fill",
        "B.Cu",
        "M2 17 L18 17 L18 19 L2 19 Z",
    )
    assert [z.state for z in drawing.zones] == ["saved_fill"]
    (edge,) = of_class(root, "edge")
    assert edge.get("d") == "M0 0 L60 0 L60 40 L0 40 Z"
    layers = [group.get("data-layer") for group in root.iter(f"{NS}g") if group.get("class") == "layer"]
    assert layers == ["B.Cu", "F.Cu"]  # the bottom layer is drawn first
    assert not of_class(root, "net-label")  # without nets=True


def test_simulated_pour_is_drawn_as_cells() -> None:
    """A zone without a stored fill is drawn as the cells of its simulated pour, and says so."""
    drawing, root = drawn(rv.bench(fill=False))
    assert [(z.state, z.reason) for z in drawing.zones] == [("simulated", "no-fill")]
    (zone,) = of_class(root, "zone")
    assert zone.get("data-state") == "simulated" and zone.get("data-net") == "GND"
    rows = (zone.get("d") or "").split(" Z")
    assert len([row for row in rows if row.strip()]) >= 1 and (zone.get("d") or "").startswith("M")


def test_open_connections_follow_the_pour() -> None:
    """With the copper of ``analysis.pour``, the unfilled zones of the ground bench join ``Q1-1`` and
    ``U1-1`` as their simulated pours do; on the saved copper alone they are open."""
    design = ground(fill=False)
    pads = board_pads(design)
    assert design.board is not None
    pour = pour_copper(design, pads=pads, boundary=board_boundary(design.board))
    saved = connectivity(design, pads=pads)
    poured = connectivity(design, pads=pads, pour=pour)
    assert saved.total > 0 and saved.evidence == conn.EVIDENCE
    assert poured.total == 0 and poured.evidence == conn.POUR_EVIDENCE


def test_the_grid_is_labelled_in_board_millimetres() -> None:
    drawing, root = drawn(rv.bench())
    assert drawing.grid == 2 * MM == auto_grid(REGION)
    xs = [label.text for label in of_class(root, "grid-label") if label.get("data-axis") == "x"]
    assert xs == [str(n) for n in range(0, 21, 2)]
    assert root.get("data-region") == "0,0,20,20" and root.get("data-grid") == "2"
    fine, _ = drawn(rv.bench(), grid=MM // 2)
    assert fine.counts["grid"] == 2 * 41
    assert grid_lines(-3 * MM, 3 * MM, 2 * MM) == [-2 * MM, 0, 2 * MM]
    with pytest.raises(ValueError, match="lines on one axis"):
        check_grid(REGION, 20 * MM // (MAX_LINES + 1))
    with pytest.raises(ValueError):
        check_grid(REGION, 0)


def test_drawing_is_deterministic_and_exact() -> None:
    first, _ = drawn(rv.bench(), nets=True)
    second, _ = drawn(rv.bench(), nets=True)
    assert first.svg == second.svg
    assert (mm(1_500_000), mm(-250_000), mm(12_345_678), mm(0)) == ("1.5", "-0.25", "12.345678", "0")
    assert EVIDENCE.hypotheses == ("H-G-REGION-RENDER",)
    with pytest.raises(ValueError):
        Region(0, 0, 0, MM)


def test_highlight_layers_and_stable_element_ids():
    drawing, root = drawn(rv.bench(), highlight=("GND",), layers=("B.Cu",))
    assert root.get("data-render") == "fenolite.region.v1"
    copper = [e for e in root.iter() if e.get("data-item")]
    assert copper
    for element in copper:
        assert ("net-hi" in element.get("class", "")) == (element.get("data-net") == "GND")
        assert element.get("data-layer") in (None, "B.Cu")
    assert of_class(root, "edge") and of_class(root, "hole")
    assert drawing.svg == drawn(rv.bench(), highlight=("GND",), layers=("B.Cu",))[0].svg


def test_merged_simulated_zones_count_entities_once():
    import dataclasses

    from fenolite.core.coords import Point

    design = rv.bench(fill=False)
    zone = design.board.zones[0]
    other = dataclasses.replace(
        zone,
        id="zon_00000000-0000-4000-8000-000000000002",
        outline=tuple(Point(p.x + MM, p.y) for p in zone.outline),
    )
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(zone, other)))
    drawing, _ = drawn(design, highlight=("GND",))
    assert drawing.highlighted["zones"] == 2
