# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A public PCB document converted to KiCad and back to Altium keeps each pad's solder-mask expansion
(change c0440, capability design-conversion, "Mask and paste of imported pads"; capability
design-equivalence, "Pad mask expansion").

On ``origin/cac/lote-24`` 2ca60daf4 every pad of ``altium-third-party-pcbdoc-01`` came back "from the rules"
with no mask rule written, and its manual pads (20 of 0, 16 of 3.1496 mil, under a 3 mil rule) lost their
values (S-1991). The test reads modes, values and difference kinds: no name, coordinate or identifier of the
document.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.api import run
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
ITEM = next(item for item in manifest_items("altium-import") if item.id == "altium-third-party-pcbdoc-01")
STAMP = "2026-11-06T00:00:00Z"
RULE = "2,30000"  # the document's Solder Mask Expansion of scope All, 3 mil, as a manual expansion


def _convert(source: Path, to: str, out: str, cwd: Path) -> Path:
    planned = run("convert", str(source), "--to", to, "--out", out, "--allow-lossy", "--dry-run", cwd=cwd,
                  timestamp=STAMP)  # fmt: skip
    assert planned.exit_code == 0, planned.error
    written = run("convert", str(source), "--to", to, "--out", out, "--allow-lossy", "--confirm", "--plan",
                  str(planned.result["plan_id"]), cwd=cwd, timestamp=STAMP)  # fmt: skip
    assert written.exit_code == 0, written.error
    return cwd / out


def _masks(design: Design) -> dict[tuple[str, str], str]:
    """(reference, pad number) → the pad's mask entry of the Altium bag, ``rules`` without one."""
    assert design.board is not None
    refs = {component.id: component.ref for component in design.circuit.components}
    found: dict[tuple[str, str], str] = {}
    for footprint in design.board.footprints:
        for pad in footprint.pads:
            held = pad.ext.get("altium")
            entry = dict(held.payload).get("mask", "rules") if held is not None else "rules"
            found[refs.get(footprint.component_id, footprint.id), pad.number] = entry
    return found


def test_each_pad_keeps_its_mask_expansion(tmp_path: Path) -> None:
    source = require(ITEM)
    kicad = _convert(source, "kicad", "k", tmp_path)
    altium = _convert(next(kicad.rglob("*.kicad_pro")), "altium", "a", tmp_path)
    document = next(altium.rglob("*.PcbDoc"))
    before = _masks(AltiumBackend().read(source).design)
    after = _masks(AltiumBackend().read(document).design)
    pairs = Counter((before[key], after[key]) for key in before.keys() & after.keys())
    assert all(old == new or (old, new) == ("rules", RULE) for old, new in pairs), pairs
    assert pairs["2,0", "2,0"] >= 1 and pairs["2,31496", "2,31496"] == 16
    reply = run("equivalent", str(source), str(document), "--level", "3")
    rows = [row for row in reply.result["differences"] if row["kind"] == "pad-mask"]
    assert rows == []
