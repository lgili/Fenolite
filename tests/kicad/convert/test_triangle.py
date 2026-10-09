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
    assert {(d.kind, d.where) for d in found.unexplained} == IMPORTER.get(key, set())
