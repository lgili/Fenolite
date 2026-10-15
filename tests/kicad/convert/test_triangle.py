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
SLOT_IMPORT_PINS = ("1", "2", "3", "4", "6", "7", "8", "9")
"""ecc83's rotated slots read by 10.0.6 as one-number ``(drill oval 0.762)``.

Native Altium retains all nine 1.02 by 2.03 mm slots. Pin 5, at zero hole angle,
does not produce this importer discrepancy. See c0166's native evidence.
"""


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
    if key == "04":
        slots = [d for d in found.unexplained if d.kind == "pad-drill"]
        assert {(d.where, d.a, d.b) for d in slots} == {
            (f"U1-{pin}", "1020000", "") for pin in SLOT_IMPORT_PINS
        }
        expected.update(("pad-drill", f"U1-{pin}") for pin in SLOT_IMPORT_PINS)
    assert {(d.kind, d.where) for d in found.unexplained} == expected
