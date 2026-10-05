# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The PCB reader against ``kicad-cli fp upgrade`` on the public corpus libraries (capability
altium-pcb-reader, "PCB library conversion oracle", change c0041; S-0020, S-0162, S-0166;
``H-A-RD-PCB-KICAD-LIB``, ``H-A-RD-PCB-PAD``).

Each ``altium-pcblib`` row is converted by ``kicad-cli fp upgrade <row>.PcbLib -o <dir>.pretty`` (a
subprocess) and each ``.kicad_mod`` is read with ``fenolite.backends.kicad.mod.read_footprint``. Positions
are compared with Y negated after KiCad's length conversion (the test of the document oracle states it),
within 2 nm. The test writes counts only.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from _altium_kicad import PASTE_LAYERS, SLOT, Item, kicad_nm, match
from _boards import census
from _corpus import CorpusItem, manifest_items, require
from _resources import kicad_cli

from fenolite.backends.altium.read.pcblib import PcbLibrary, read_pcblib
from fenolite.backends.altium.read.pcbprims import ArcRecord, PadRecord, TrackRecord
from fenolite.backends.kicad.mod import read_footprint
from fenolite.model.library import FootprintDef

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus]
ITEMS = manifest_items("altium-pcblib")
OVERLAYS = {33: "F.SilkS", 34: "B.SilkS"}


@cache
def _convert(row: str) -> tuple[int, tuple[FootprintDef, ...]]:
    item = next(i for i in ITEMS if i.id == row)
    source = require(item)
    cli = kicad_cli()
    assert cli is not None
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "out.pretty"
        env = {**os.environ, "KICAD_CONFIG_HOME": os.path.join(folder, "config")}
        proc = subprocess.run(
            [cli, "fp", "upgrade", str(source), "-o", str(target)],
            capture_output=True, text=True, timeout=300, env=env, check=False,
        )  # fmt: skip
        files = sorted(target.glob("*.kicad_mod")) if target.is_dir() else []
        return proc.returncode, tuple(read_footprint(f, library="out") for f in files)


@cache
def _read(row: str) -> PcbLibrary:
    item = next(i for i in ITEMS if i.id == row)
    return read_pcblib(require(item).read_bytes())


def _pads(pads: list[PadRecord]) -> list[Item]:
    out: list[Item] = []
    for p in pads:
        round_hole = p.hole and p.hole_shape != SLOT
        name = "" if p.hole and not p.plated else p.name
        plating = "smd" if not p.hole else ("thru_hole" if p.plated else "np_thru_hole")
        size = (kicad_nm(p.size_top[0]), kicad_nm(p.size_top[1]))
        out.append(
            (kicad_nm(p.x), -kicad_nm(p.y), name, *size, kicad_nm(p.hole) if round_hole else None, plating)
        )
    return out


def _kicad_pads(footprint: FootprintDef) -> list[Item]:
    out: list[Item] = []
    for pad in footprint.pads:
        slotted = pad.padstack is not None and pad.padstack.hole_shape != "round"
        hole = None if pad.drill is None or slotted else pad.drill
        kind = pad.kind if pad.kind in ("thru_hole", "np_thru_hole") else "smd"
        out.append((pad.position.x, pad.position.y, pad.number, pad.size.w, pad.size.h, hole, kind))
    return out


def compare(row: str) -> tuple[dict[str, Any], list[str]]:
    lib = _read(row)
    _, converted = _convert(row)
    by_name = {f.name: f for f in converted}
    problems: list[str] = []
    counts: Counter[str] = Counter()
    if set(by_name) != {f.name for f in lib.footprints}:
        problems.append(f"footprint names: {len(set(by_name) ^ {f.name for f in lib.footprints})} differ")
    for footprint in lib.footprints:
        other = by_name.get(footprint.name)
        if other is None:
            continue
        counts["footprints"] += 1
        pads = [p for p in footprint.pads if p.prefix.layer not in PASTE_LAYERS]
        counts["pads_on_a_paste_layer_not_imported"] += len(footprint.pads) - len(pads)
        counts["pads_slotted_hole_size_not_compared"] += sum(1 for p in pads if p.hole_shape == SLOT)
        lonely, extra, worst = match(_pads(pads), _kicad_pads(other), 2)
        counts["pads"] += len(pads)
        counts["largest_difference_nm"] = max(counts["largest_difference_nm"], worst)
        if lonely or extra:
            problems.append(f"pads: {len(lonely)} only read, {len(extra)} only in KiCad")
        for layer, name in OVERLAYS.items():
            lines = sum(
                1 for p in footprint.primitives if isinstance(p, TrackRecord) and p.prefix.layer == layer
            )
            arcs = sum(
                1 for p in footprint.primitives if isinstance(p, ArcRecord) and p.prefix.layer == layer
            )
            klines = sum(1 for g in other.graphics if g.layer == name and g.kind == "line")
            karcs = sum(1 for g in other.graphics if g.layer == name and g.kind in ("arc", "circle"))
            counts["overlay_lines"] += lines
            counts["overlay_arcs"] += arcs
            if (lines, arcs) != (klines, karcs):
                problems.append(
                    f"overlay {name}: {lines} lines and {arcs} arcs read, {klines} and {karcs} in KiCad"
                )
    return dict(counts), problems


@pytest.mark.parametrize("item", ITEMS, ids=lambda item: item.id)
def test_public_libraries_agree(item: CorpusItem) -> None:
    require(item)
    code, converted = _convert(item.id)
    assert code == 0
    assert converted
    counts, problems = compare(item.id)
    census("altium_pcb_read_lib_oracle", item.id, counts)
    print(item.id, counts)
    assert not problems, "; ".join(problems)
