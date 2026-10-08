# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The PCB reader against ``kicad-cli pcb import`` on the public corpus documents (capability
altium-pcb-reader, "PCB document import oracle", change c0041; S-0020, S-0161, S-0166;
``H-A-RD-PCB-KICAD-DOC``, ``H-A-RD-PCB-STACK``, ``H-A-RD-PCB-PAD``, ``H-A-UNIT``).

Each ``altium-pcbdoc`` row is imported by ``kicad-cli pcb import --format altium`` (a subprocess) and read
with ``fenolite.backends.kicad.pcb.read_board``. KiCad moves the board to the middle of its sheet, so
positions are compared after the one translation that maps the reader's first pad onto KiCad's, with Y
negated; the tolerance is 2 nm per coordinate. A reader record that KiCad does not return is counted
under a documented exclusion (``docs/formats/altium/pcb-read.md``, "What KiCad does not import"); an item
of KiCad's board without a reader record fails. The test writes counts only.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from typing import Any

import pytest
from _altium_kicad import KNOWN_IMPORT_FAILURES, PASTE_LAYERS, SLOT, Item, kicad_nm, match
from _boards import census
from _corpus import CorpusItem, manifest_items, require
from _kicad import oracle_env
from _resources import kicad_cli

from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import (
    FillRecord,
    PadRecord,
    RegionRecord,
    TextRecord,
    TrackRecord,
    ViaRecord,
)
from fenolite.backends.kicad.pcb import read_board
from fenolite.geometry.transform import Transform
from fenolite.model.design import Design

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus, pytest.mark.kicad_min_major(10)]
ITEMS = manifest_items("altium-pcbdoc")
KicadPad = tuple[str, Any, tuple[int, int]]
"""A footprint reference, a KiCad pad and its absolute position."""


@dataclass
class Imported:
    code: int
    board: Design | None
    output: str


@cache
def _import(row: str) -> Imported:
    item = next(i for i in ITEMS if i.id == row)
    source = require(item)
    cli = kicad_cli()
    assert cli is not None
    with tempfile.TemporaryDirectory() as folder:
        target = os.path.join(folder, "board.kicad_pcb")
        env = oracle_env(os.path.join(folder, "config"))
        proc = subprocess.run(
            [cli, "pcb", "import", "--format", "altium", "-o", target, str(source)],
            capture_output=True, text=True, timeout=600, env=env, check=False,
        )  # fmt: skip
        board = (
            read_board(open(target, encoding="utf-8").read(), file="board.kicad_pcb")
            if proc.returncode == 0
            else None
        )
        return Imported(proc.returncode, board, proc.stdout + proc.stderr)


@cache
def _read(row: str) -> PcbDocument:
    item = next(i for i in ITEMS if i.id == row)
    return read_pcbdoc(require(item).read_bytes())


@dataclass
class Frame:
    dx: int
    dy: int

    def point(self, x: int, y: int) -> tuple[int, int]:
        return kicad_nm(x) + self.dx, -kicad_nm(y) + self.dy


def designators(doc: PcbDocument) -> list[str]:
    """The reference KiCad gives each component: the shown string of its designator text, else its
    ``SOURCEDESIGNATOR``; a name of digits only gets the prefix ``UNK`` (S-0161)."""
    shown: dict[int, str] = {}
    for text in doc.texts:
        if isinstance(text, TextRecord) and text.is_designator and text.prefix.component is not None:
            shown.setdefault(text.prefix.component, text.text)
    out: list[str] = []
    for index, component in enumerate(doc.components):
        name = shown.get(index, component.source_designator or "")
        out.append("UNK" + name if name[:1].isdigit() else name)
    return out


def _kicad_pads(board: Design) -> list[tuple[str, Any, tuple[int, int]]]:
    """(footprint reference, pad, absolute position) of every footprint pad."""
    assert board.board is not None
    refs = {c.id: c.ref for c in board.circuit.components}
    out: list[tuple[str, Any, tuple[int, int]]] = []
    for footprint in board.board.footprints:
        place = Transform.placement(footprint.position, footprint.rotation)
        for pad in footprint.pads:
            point = place.apply(pad.position)
            out.append((refs.get(footprint.component_id or "", ""), pad, (point.x, point.y)))
    return out


def _ratio(pad: Any) -> Fraction | None:
    bag = pad.ext.get("kicad")
    for _, value in bag.payload if bag else ():
        found = re.fullmatch(r"\(roundrect_rratio ([0-9.]+)\)", value) if isinstance(value, str) else None
        if found:
            return Fraction(found.group(1))
    return None


def expected_shape(p: PadRecord) -> tuple[str, Fraction | None] | None:
    """The top-layer shape KiCad gives a simple pad (``pcb-records.md``, "Pad"): round is a circle or an
    oval, a rectangle a rectangle, and alternate shape 9 with a corner percentage a rounded rectangle of
    ratio ``percentage / 200``; ``None`` for an octagon (not compared)."""
    alternate = p.alternate_shapes[0] if p.alternate_shapes else None
    percentage = p.corner_percentages[0] if p.corner_percentages else 0
    if p.shape_top in (1, 2) and alternate == 9 and percentage:
        return "roundrect", Fraction(percentage, 200)
    if p.shape_top == 1:
        return ("circle" if p.size_top[0] == p.size_top[1] else "oval"), None
    if p.shape_top == 2:
        return "rect", None
    return None


def shape_problems(
    pads: Sequence[PadRecord],
    refs: Sequence[str],
    kpads: Sequence[tuple[str, Any, tuple[int, int]]],
    frame: Frame,
) -> tuple[Counter[str], list[str]]:
    """Top-layer size of every component pad, and shape and corner ratio of the simple ones."""
    index: dict[tuple[str, str, int, int], Any] = {}
    for ref, pad, (x, y) in kpads:
        index.setdefault((ref, pad.number, x // 10, y // 10), pad)
    counts: Counter[str] = Counter()
    problems: list[str] = []
    for p in pads:
        if p.prefix.component is None:
            continue
        x, y = frame.point(p.x, p.y)
        name = "" if p.hole and not p.plated else p.name
        keys = (
            (refs[p.prefix.component], name, x // 10 + i, y // 10 + j) for i in (-1, 0, 1) for j in (-1, 0, 1)
        )
        found = next((index[k] for k in keys if k in index), None)
        if found is None:
            continue
        if (found.size.w, found.size.h) != (kicad_nm(p.size_top[0]), kicad_nm(p.size_top[1])):
            counts["size_differs"] += 1
        expected = expected_shape(p)
        if p.stack_mode != 0 or expected is None:
            counts["pads_shape_not_compared"] += 1
            continue
        got = (found.shape, _ratio(found) if found.shape == "roundrect" else None)
        counts["pads_shape_compared"] += 1
        if got != expected:
            counts["shape_differs"] += 1
    if counts["size_differs"]:
        problems.append(f"{counts['size_differs']} pad sizes differ")
    if counts["shape_differs"]:
        problems.append(f"{counts['shape_differs']} pad shapes differ")
    return counts, problems


def compare(row: str) -> tuple[dict[str, Any], list[str]]:
    """Counts of the comparison of one row and the problems found."""
    doc, imported = _read(row), _import(row)
    assert imported.board is not None and imported.board.board is not None
    board = imported.board
    kboard = board.board
    assert kboard is not None
    nets = {n.id: n.name for n in board.circuit.nets}
    problems: list[str] = []
    counts: dict[str, Any] = {}

    names_k, names_a = {n.name for n in board.circuit.nets}, {n.name for n in doc.nets if n.name}
    counts["nets"] = len(names_a)
    if names_k != names_a:
        problems.append(
            f"net names: {len(names_k - names_a)} only in KiCad, {len(names_a - names_k)} only read"
        )

    copper = sum(1 for layer in kboard.layers if layer.kind == "copper")
    counts["copper_layers"] = copper
    if copper != len(doc.board.copper_chain):
        problems.append(f"copper layers: KiCad {copper}, chain {len(doc.board.copper_chain)}")

    refs = designators(doc)
    refs_a = Counter(refs)
    kpads = _kicad_pads(board)
    by_id = {c.id: c.ref for c in board.circuit.components}
    refs_k = Counter(by_id.get(f.component_id or "", "") for f in kboard.footprints)
    free_refs = refs_k - refs_a
    counts["footprints"] = sum(refs_a.values())
    counts["footprints_of_free_pads"] = sum(free_refs.values())
    if refs_a - refs_k:
        problems.append(f"{sum((refs_a - refs_k).values())} components are not footprints of KiCad")

    # pads: (x, y, footprint reference or "*" for a free pad, name, net, hole)
    pads = [p for p in doc.pads if isinstance(p, PadRecord)]
    paste = [p for p in pads if p.prefix.layer in PASTE_LAYERS]
    counts["pads_on_a_paste_layer_not_imported"] = len(paste)
    pads = [p for p in pads if p.prefix.layer not in PASTE_LAYERS]
    slots = sum(1 for p in pads if p.hole_shape == SLOT)
    counts["pads_slotted_hole_size_not_compared"] = slots

    def hole(p: PadRecord) -> int | None:
        return None if p.hole == 0 or p.hole_shape == SLOT else kicad_nm(p.hole)

    def drill(pad: Any) -> int | None:
        slotted = pad.padstack is not None and pad.padstack.hole_shape != "round"
        return None if pad.drill is None or slotted else pad.drill

    theirs: list[Item] = []
    for ref, pad, pos in kpads:
        kind = "*" if ref in free_refs else ref
        theirs.append((*pos, kind, pad.number, nets.get(pad.net_id or ""), drill(pad)))
    first = next(p for p in pads if p.prefix.component is not None)
    first_ref = refs[first.prefix.component or 0]
    anchors = [pos for ref, pad, pos in kpads if ref == first_ref and pad.number == first.name]
    best: tuple[int, Frame, list[Item], list[Item], int] | None = None
    for anchor in anchors:
        frame = Frame(anchor[0] - kicad_nm(first.x), anchor[1] + kicad_nm(first.y))
        mine: list[Item] = []
        for p in pads:
            ref = refs[p.prefix.component] if p.prefix.component is not None else "*"
            name = "" if p.hole and not p.plated else p.name
            mine.append((*frame.point(p.x, p.y), ref, name, doc.net_name(p.prefix.net), hole(p)))
        lonely, extra, gap = match(mine, theirs, 2)
        if best is None or len(lonely) < len(best[2]):
            best = (len(mine), frame, lonely, extra, gap)
    assert best is not None
    count, frame, lonely, extra, worst = best
    shapes, shape_issues = shape_problems(pads, refs, kpads, frame)
    counts.update({k: shapes[k] for k in ("pads_shape_compared", "pads_shape_not_compared")})
    problems += shape_issues
    chain = set(doc.board.copper_chain)
    regions = sum(
        1
        for r in doc.regions
        if isinstance(r, RegionRecord) and r.prefix.component is not None and r.prefix.layer in chain
    )
    fills = sum(
        1
        for f in doc.fills
        if isinstance(f, FillRecord)
        and f.prefix.component is not None
        and f.prefix.layer in chain
        and f.prefix.net is None
    )
    unnamed = [item for item in extra if item[3] == ""]
    counts["pads"] = count
    counts["component_copper_regions_and_fills_as_unnamed_pads"] = len(unnamed)
    counts["pads_not_imported"] = len(lonely)
    if len(unnamed) != regions + fills:
        problems.append(f"{len(unnamed)} unnamed KiCad pads for {regions} regions and {fills} fills")
    if len(extra) != len(unnamed):
        problems.append(f"{len(extra) - len(unnamed)} pads of KiCad have no pad of the reader")
    if lonely:
        problems.append(f"{len(lonely)} pads of the reader are not in KiCad")

    vias = [
        (*frame.point(v.x, v.y), kicad_nm(v.diameter), kicad_nm(v.hole), doc.net_name(v.prefix.net))
        for v in doc.vias
        if isinstance(v, ViaRecord)
    ]
    kvias = [(v.position.x, v.position.y, v.diameter, v.drill, nets.get(v.net_id or "")) for v in kboard.vias]
    lonely_v, extra_v, worst_v = match(vias, kvias, 4)
    counts["vias"] = len(vias)
    if lonely_v or extra_v:
        problems.append(f"vias: {len(lonely_v)} only read, {len(extra_v)} only in KiCad")

    order = {layer: index for index, layer in enumerate(doc.board.copper_chain)}
    klayers = [
        layer.name for layer in sorted(kboard.layers, key=lambda la: la.ordinal) if layer.kind == "copper"
    ]
    tracks: list[Item] = []
    for t in doc.tracks:
        if isinstance(t, TrackRecord) and t.prefix.component is None and t.prefix.net is not None:
            if t.prefix.layer in order:
                a, b = sorted((frame.point(t.x1, t.y1), frame.point(t.x2, t.y2)))
                tracks.append((*a, *b, kicad_nm(t.width), order[t.prefix.layer], doc.net_name(t.prefix.net)))
    ktracks: list[Item] = []
    for t in kboard.tracks:
        a, b = sorted(((t.start.x, t.start.y), (t.end.x, t.end.y)))
        ktracks.append((*a, *b, t.width, klayers.index(t.layer), nets.get(t.net_id or "")))
    lonely_t, extra_t, worst_t = match(tracks, ktracks, 4)
    counts["copper_tracks"] = len(tracks)
    if lonely_t or extra_t:
        problems.append(f"copper tracks: {len(lonely_t)} only read, {len(extra_t)} only in KiCad")

    counts["zones"] = len(kboard.zones)
    if len(kboard.zones) != len(doc.polygons):
        problems.append(f"zones: KiCad {len(kboard.zones)}, polygons {len(doc.polygons)}")
    counts["largest_difference_nm"] = max(worst, worst_v, worst_t)
    return counts, problems


@pytest.mark.parametrize("item", ITEMS, ids=lambda item: item.id)
def test_a_public_board_agrees(item: CorpusItem) -> None:
    require(item)
    imported = _import(item.id)
    if imported.code != 0:
        expected = KNOWN_IMPORT_FAILURES.get(item.id)
        assert expected is not None, imported.output
        expected_code, expected_message = expected
        assert imported.code == expected_code and expected_message in imported.output, imported.output
        pytest.skip(f"kicad-cli fails in its own importer on {item.id} on this platform (recorded)")
    assert imported.code == 0, imported.output
    counts, problems = compare(item.id)
    census("altium_pcb_read_oracle", item.id, counts)
    print(item.id, counts)
    assert not problems, "; ".join(problems)
