# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad reads the converted document as the source (capability design-conversion, "KiCad to Altium
direction", scenario "KiCad reads the converted document as the source"; ``H-K-CONV-TRIANGLE``; change
c0159).

A KiCad board is converted to Altium; ``kicad-cli pcb import`` (10.0) converts the written PCB document
back to a KiCad board, which is compared with the design that was written at level 5 under the importer's
profile ``kicad-import``. Every difference must be explained by a lost item of the conversion's report, or
be one of the importer's own, listed here per demo board with its cause.
"""

from __future__ import annotations

from collections import Counter

import _convcases
import _probes
import pytest
from _corpus import manifest_items, require

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
PREFIX = "kicad-demo-10-0-6-pcb-"
BOARDS = {
    item.id.removeprefix(PREFIX): item
    for item in manifest_items("rt0")
    if item.id.startswith(PREFIX) and item.id.removeprefix(PREFIX) not in ("06", "18")
}
"""The demo boards that the census writes (``jetson-agx-thor-baseboard`` and ``vme-wren`` are not)."""
IMPORTER: dict[str, set[tuple[str, str]]] = {
    # One-Air-Max: KiCad's importer names the six components without a reference "UNK" (measured on
    # 10.0.6); the written document holds them with an empty designator, as the board does.
    "11": {("ref-ambiguous", ""), ("ref-ambiguous", "UNK")},
    # RoyalBlue54L-NFC-Antenna: the importer rounds each end of the antenna's many short segments to 10 nm;
    # the routed length on F.Cu differs by 8491 nm of 396.45 mm, 21.4 parts per million, above the 20 of
    # the profile (measured on 10.0.6).
    "14": {("route-length", "/ANT:J1-1,J1-2")},
}
"""Per demo board, the differences ``(kind, where)`` that KiCad's importer makes and no loss explains."""

FREE_PAD_COUNTS = {"01": 14, "04": 1, "07": 2, "12": 9, "13": 9, "16": 3, "17": 24}
"""c0166 measured importer wrappers: one blank-reference footprint per free pad.

These counts match the separately recorded conversion ledger, not a general
exemption for blank references. The original numbered-component checks remain.
"""
SLOT_BOARD = "04"
"""ecc83, whose nine U1 pads hold a 1.02 by 2.03 mm slot along the pad, the pads turned by 306° to 90°.
Until change c0170 the writer gave each slot the rotation ``hole_rotation`` minus the pad's angle (144°, 108°,
72°, 36° and 0°), across the pad for eight of them, and KiCad 10.0.6 read those eight as one-number oval
drills (c0166). Since c0170 the slot rotation is relative to the pad (90° for all nine), and KiCad's import
gives every drill of the source (c0171 task 1.11, measured on 10.0.6): no ``pad-drill`` difference remains."""


@pytest.mark.parametrize("name", sorted(_convcases.SAMPLES))
def test_samples(name: str) -> None:
    found = _convcases.triangle(_convcases.SAMPLES[name])
    print(f"{name}: level {found.report.levels[-1].level}, {len(found.report.excluded)} excluded")
    assert found.report.levels[-1].level == 5
    assert found.unexplained == () and found.explained == ()


def test_probe() -> None:
    outcome = _probes.run("convert-triangle")
    print(f"convert-triangle: {outcome} on kicad-cli {_probes.version()}")
    assert outcome == "equal"


@pytest.mark.needs_corpus
@pytest.mark.parametrize("key", sorted(BOARDS))
def test_demo_boards(key: str) -> None:
    """Each demo board that the census writes: every difference of the import is explained by the report,
    excluded by the importer's profile, or one of the importer's own listed in ``IMPORTER``."""
    found = _convcases.triangle(require(BOARDS[key]))
    explained = dict(Counter((d.kind, kind) for d, kind in found.explained))
    print(f"{BOARDS[key].path.stem}: {explained}, {len(found.report.excluded)} excluded")
    expected = set(IMPORTER.get(key, set()))
    if key in FREE_PAD_COUNTS:
        wrappers = [d for d in found.unexplained if d.kind == "ref-ambiguous" and not d.where]
        assert len(wrappers) == 1
        assert (wrappers[0].a, wrappers[0].b) == ("0", str(FREE_PAD_COUNTS[key]))
        expected.add(("ref-ambiguous", ""))
    if key == SLOT_BOARD:
        assert not [d for d in found.report.differences if d.kind == "pad-drill"]
        assert not [e for e in found.report.excluded if e.difference.kind == "pad-drill"]
    assert {(d.kind, d.where) for d in found.unexplained} == expected
