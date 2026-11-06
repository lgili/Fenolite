# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A public PCB document converted to KiCad and back to Altium opens its vias' solder mask as the source does
(change c0445; capability design-conversion, "Mask of imported vias"; altium-pcb-writer, "Via records").

The untented vias of ``altium-third-party-pcbdoc-01`` (a heavy row, ``FENOLITE_HEAVY=1``) take their mask
from a rule of scope ``IsVia`` of 1 mil measured from the hole. On ``origin/cac/lote-26`` e55b7cd5e the KiCad
board opened them by a margin of 0 and the way back wrote 4 mil from the rules with no mask rule (S-2043).
The test reads sizes, states and counts: no name, coordinate or identifier of the document.
"""

from __future__ import annotations

import struct
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from _corpus import manifest_items, require

from fenolite.api import run
from fenolite.backends.altium.adapter.units import pcb_length
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import ViaRecord
from fenolite.convert import openings

pytestmark = pytest.mark.needs_corpus
ITEM = next(item for item in manifest_items("altium-import") if item.id.endswith("-pcbdoc-01"))
STAMP = "2026-11-06T00:00:00Z"
STATE, TOP, BOTTOM = 66 - 31, 54 - 31, 242 - 31
"""Offsets in ``ViaRecord.tail``, which starts at 31 (``pcb-copper.md``, "Via")."""


def _convert(source: Path, to: str, out: str, cwd: Path, *extra: str) -> Mapping[str, Any]:
    args = ("convert", str(source), "--to", to, "--out", out, "--allow-lossy", *extra)
    planned = run(*args, "--dry-run", cwd=cwd, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    written = run(*args, "--confirm", "--plan", str(planned.result["plan_id"]), cwd=cwd, timestamp=STAMP)
    assert written.exit_code == 0, written.error
    return written.result


def _openings(path: Path) -> Counter[tuple[bool, bool, int | None, int | None]]:
    """Per via: its tenting flags and the width of its mask opening on each side (the
    diameter plus twice its growth) in nanometres, as Altium's record and rules give it."""
    document = read_pcbdoc(path.read_bytes())
    rule = openings.via_rule([dict(record.record.fields) for record in document.rules])
    found: Counter[tuple[bool, bool, int | None, int | None]] = Counter()
    for via in document.vias:
        assert isinstance(via, ViaRecord)
        sides: list[int | None] = []
        for offset in (TOP, BOTTOM):
            own = struct.unpack_from("<i", via.tail, offset)[0]
            diameter, hole = pcb_length(via.diameter), pcb_length(via.hole)
            margin = openings.via_margin(diameter, hole, via.tail[STATE], pcb_length(own), rule)
            sides.append(None if margin is None else diameter + 2 * margin)
        found[(via.tented_top, via.tented_bottom, sides[0], sides[1])] += 1
    return found


def test_the_way_back_opens_the_vias_as_the_source(tmp_path: Path) -> None:
    source = require(ITEM)
    _convert(source, "kicad", "k", tmp_path)
    board = next((tmp_path / "k").rglob("*.kicad_pcb")).read_text(encoding="utf-8")
    assert "(pad_to_mask_clearance -0.1016)" in board
    _convert(next((tmp_path / "k").rglob("*.kicad_pro")), "altium", "a", tmp_path, "--altium-pour", "outline")
    before = _openings(source)
    assert sum(before.values()) == 646 and {key[2:] for key in before} == {(304_800, 304_800)}
    assert _openings(next((tmp_path / "a").rglob("*.PcbDoc"))) == before
