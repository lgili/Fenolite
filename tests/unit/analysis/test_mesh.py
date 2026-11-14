# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The adaptive mesh of the current split (change c0503; capability board-analyses, "Current split"), on the
authored benches of ``tests/_power.py``: the same copper as the raster in far fewer cells, and the same
answers within the tolerances of task 3.3."""

from __future__ import annotations

import dataclasses
from collections import defaultdict

import pytest
from _coppercheck import ident
from _power import (
    DUMBBELL,
    SPLIT4,
    SPLIT4_HOLE,
    fdm_resistance,
    neck_board,
    plane_board,
    strip,
    two_strips,
    via_array,
)

from fenolite.analysis import analyze_power
from fenolite.analysis.mesh import Key, Spans, cell_spans, mesh_layers, ring_spans
from fenolite.analysis.pour import pour_copper, shape_cells
from fenolite.analysis.split import analyze_split
from fenolite.model.board import StackLayer, Stackup
from fenolite.model.design import Design

GRID = 100_000
RHO = 20_000
"""An illustrative resistivity in picoohm-metres, 400 µΩ per square over 50 µm; Fenolite ships none."""
SHEET = 400


def test_cell_count_below_the_raster() -> None:
    """Scenario "Fewer cells than the raster": the ground net of ``plane_board(48)`` at 0.1 mm."""
    design, pads = plane_board(48)
    pour = pour_copper(design, pads=pads, boundary=None, grid=GRID)
    items: dict[str, list[tuple[Key, Spans]]] = defaultdict(list)
    raster: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for number, shape in enumerate(pour.copper.by_net["GND"]):
        cells = shape_cells(shape.shape, GRID)
        raster[shape.layer] |= cells
        spans = ring_spans(shape.shape.core, GRID) if shape.kind == "fill" else cell_spans(cells)
        items[shape.layer].append(((shape.kind, str(number)), spans))
    meshes = mesh_layers(items)
    leaves = sum(len(mesh.leaves) for mesh in meshes.values())
    cells = sum(len(found) for found in raster.values())
    assert leaves * 10 < cells, (leaves, cells)
    for layer, mesh in meshes.items():
        rows: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for (i0, j0), (size, _) in mesh.leaves.items():
            for j in range(j0, j0 + size):
                rows[j].append((i0, i0 + size - 1))
        filled = {j: [(lo, hi) for lo, hi in runs] for j, runs in cell_spans(raster[layer]).items()}
        # the leaves cover the raster's cells, each cell once: the same runs and the same count
        assert sum(size * size for size, _ in mesh.leaves.values()) == len(raster[layer])
        assert {j: _join(runs) for j, runs in rows.items()} == filled


def _join(runs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    joined: list[tuple[int, int]] = []
    for low, high in sorted(runs):
        if joined and low <= joined[-1][1] + 1:
            joined[-1] = (joined[-1][0], max(joined[-1][1], high))
        else:
            joined.append((low, high))
    return joined


def _stacked(design: Design) -> Design:
    assert design.board is not None
    entries = (("F.Cu", "copper", 35_000), ("core", "dielectric", 1_530_000), ("B.Cu", "copper", 35_000))
    layers = tuple(
        StackLayer(id=ident("stk", n), name=name, kind=kind, thickness=thickness)  # type: ignore[arg-type]
        for n, (name, kind, thickness) in enumerate(entries)
    )
    board = dataclasses.replace(design.board, stackup=Stackup(id=ident("stu", 1), layers=layers))
    return dataclasses.replace(design, board=board)


def _neck(width: float) -> list[tuple[float, float, float, float]]:
    return [(0, 0, 10, 10), (10, 5 - width / 2, 13, 5 + width / 2), (13, 0, 23, 10)]


NECK_PADS = ((4.0, 4.0, 6.0, 6.0), (17.0, 4.0, 19.0, 6.0))
STRIP_ENDS = ((0.0, 0.0, 1.0, 5.0), (19.0, 0.0, 20.0, 5.0))
# name: bench, the oracle's squares (None: no oracle for two layers joined by vias), and the shares and
# resistance of the raster solve of this change's parent commit at 0.1 mm, recorded on 2026-11-14
ACCURACY = {
    "strip": (strip(), lambda: fdm_resistance([(0, 0, 20, 5)], [], *STRIP_ENDS), 1440, {"/strip#0": 1000}),
    "dumbbell": (
        neck_board(DUMBBELL),
        lambda: fdm_resistance(_neck(2), [], *NECK_PADS),
        1315,
        {"/pour#0": 1000},
    ),
    "split4": (
        neck_board(SPLIT4, (SPLIT4_HOLE,)),
        lambda: fdm_resistance(_neck(4), [(10.7, 4.2, 12.3, 5.8)], *NECK_PADS),
        1010,
        {"/pour#0": 1000},
    ),
    "two_strips": (
        two_strips(),
        lambda: fdm_resistance([(0, 0, 20, 5)], [], *STRIP_ENDS) / 2,
        720,
        {"/strip-B.Cu#0": 500, "/strip-F.Cu#0": 500},
    ),
    "via_array": (
        via_array(4),
        None,
        1348,
        {"/bottom#0": 1000, "/top#0": 1000, "/via[0]": 266, "/via[1]": 234, "/via[2]": 234, "/via[3]": 266},
    ),
}


@pytest.mark.parametrize("name", sorted(ACCURACY))
def test_accuracy_against_the_raster_and_the_oracle(name: str) -> None:
    """Task 3.3: the mesh resistance within 2 % of the finite-difference oracle, each share within 10
    permille of the parent's raster solve."""
    (design, pads), oracle, raster, shares = ACCURACY[name]
    plating = 25_000 if name == "via_array" else None
    if plating is not None:
        design = _stacked(design)
    kwargs = {"copper_thickness": {"*": 50_000}, "via_plating": plating, "resistivity_pohm_m": RHO}
    power = analyze_power(design, pads=pads, paths=((("J1-1",), ("U1-1",)),), **kwargs)  # type: ignore[arg-type]
    pour = pour_copper(design, pads=pads, boundary=None, grid=GRID)
    (row,) = analyze_split(design, pads=pads, pour=pour, power=power, **kwargs).rows  # type: ignore[arg-type]
    assert row.resistance_uohm is not None and row.complete and row.cell_nm == GRID
    found = {e.where: e.share_permille or 0 for e in row.elements}
    assert found.keys() == shares.keys() and all(abs(found[k] - shares[k]) <= 10 for k in shares), found
    expected = SHEET * oracle() if oracle is not None else raster
    assert abs(row.resistance_uohm - expected) <= 0.02 * expected, (row.resistance_uohm, expected)
