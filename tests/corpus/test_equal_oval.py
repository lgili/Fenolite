# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Equal-sized ovals written to Altium and read back (change c0158, design "Context", measurement 1).

An ``oval`` pad whose two sizes are equal is a disc. Written with ``lens.altium.write_model`` and read back,
it is a ``circle``. Level 3 of ``equivalent`` reported ``pad-shape`` ``oval``/``circle`` for each such pad:
40, 180 and 85 on three KiCad 10.0.6 demo boards. The pairs are counted from the two designs, apart from
the comparison, and the reported differences from ``compare_designs`` at level 3.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.backends import registry
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.equivalence import compare_designs
from fenolite.lens.altium import write_model
from fenolite.model.board import Pad
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
MEASURED = {
    "kicad-demo-10-0-6-pcb-02": 40,  # complex_hierarchy
    "kicad-demo-10-0-6-pcb-07": 180,  # kit-dev-coldfire-xilinx_5213
    "kicad-demo-10-0-6-pcb-17": 85,  # video
}
"""The equal-sized ovals of each board that read back as circles (measured on 2026-10-09)."""
ITEMS = {item.id: item for item in manifest_items("rt0") if item.id in MEASURED}


@cache
def _sides(item_id: str) -> tuple[Design, Design]:
    """The board as read, and the board that the Altium write of it reads back as."""
    path = require(ITEMS[item_id])
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    written = write_model(design, allow_lossy=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in written.files.items():
            target = Path(tmp) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        document = next(Path(tmp) / name for name in written.files if name.lower().endswith(".pcbdoc"))
        backend = registry.for_path(document)
        assert backend is not None
        back = backend.read(document).content
    assert isinstance(back, Design)
    return design, back


def _pads(design: Design) -> Iterator[tuple[tuple[str, str, int], Pad]]:
    """Each pad under its reference, its number and its rank among the pads of that number by position (the
    write may move a pad by a nanometre)."""
    refs = {component.id: component.ref for component in design.circuit.components}
    assert design.board is not None
    for footprint in design.board.footprints:
        ref = refs.get(footprint.component_id, "")
        numbers: dict[str, list[Pad]] = {}
        for pad in footprint.pads:
            numbers.setdefault(pad.number, []).append(pad)
        for number, pads in numbers.items():
            for rank, pad in enumerate(sorted(pads, key=lambda p: (p.position.x, p.position.y))):
                yield (ref, number, rank), pad


def _disc_pairs(a: Design, b: Design) -> int:
    """Pads that are an equal-sized ``oval`` on side ``a`` and a ``circle`` on side ``b``."""
    back = dict(_pads(b))
    return sum(
        1
        for key, pad in _pads(a)
        if pad.shape == "oval"
        and pad.size.w == pad.size.h
        and (other := back.get(key)) is not None
        and other.shape == "circle"
    )


def _reported(a: Design, b: Design) -> int:
    report = compare_designs(a, b, level=3)
    return sum(1 for d in report.differences if d.kind == "pad-shape" and (d.a, d.b) == ("oval", "circle"))


@pytest.mark.parametrize("item_id", sorted(MEASURED))
def test_equal_ovals_read_back_as_circles(item_id: str) -> None:
    a, b = _sides(item_id)
    found = _disc_pairs(a, b)
    print(f"{item_id}: {found} equal-sized ovals read back as circles")
    assert found == MEASURED[item_id]


@pytest.mark.xfail(strict=True, reason="the shape rule of task 4.1: an equal-sized oval is a circle")
@pytest.mark.parametrize("item_id", sorted(MEASURED))
def test_pad_shape_reported_before_the_rule(item_id: str) -> None:
    """Before the shape rule (task 4.1) level 3 reported one ``pad-shape`` per such pad."""
    a, b = _sides(item_id)
    assert _reported(a, b) == MEASURED[item_id]


@pytest.mark.parametrize("item_id", sorted(MEASURED))
def test_no_pad_shape_after_the_rule(item_id: str) -> None:
    """Capability design-equivalence, "Tolerances and normalisation", "Pad shape": none of those pads
    differs in shape."""
    a, b = _sides(item_id)
    assert _reported(a, b) == 0
