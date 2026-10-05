# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board import against ``kicad-cli pcb import --format altium`` (capability altium-import, "Board
import oracle"; change c0043; S-0020, S-0161; ``H-A-IMP-FRAME``, ``H-A-IMP-LAYERS``,
``H-A-IMP-PADSTACK``, ``H-A-IMP-ZONE``).

Each document is imported by the adapter and converted by ``kicad-cli`` (a subprocess, on a copy under a
temporary folder), whose result is read with ``KicadBackend``. KiCad moves an imported board, so positions
are compared after one common translation; lengths agree within 10 nm (KiCad rounds its conversion to
10 nm) and angles within 1 000 microdegrees. A difference that comes from KiCad's importer is excluded by
kind, never by file; each kind is a row of ``docs/formats/altium/import.md``, "Differences from KiCad's
importer". The test writes counts only.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from collections import Counter
from collections.abc import Callable, Sequence
from functools import cache
from pathlib import Path
from typing import TypeVar

import pytest
from _corpus import manifest_items, require
from _resources import kicad_cli

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import TextRecord
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.core.coords import Point
from fenolite.model.board import Arc, FootprintInstance, Pad, Track, Via, Zone
from fenolite.model.design import Design

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
DATA = Path(__file__).resolve().parents[2] / "data" / "altium"
AUTHORED = {"blink": DATA / "blink" / "blink.PcbDoc", "routed": DATA / "routed" / "routed.PcbDoc"}
ROWS = [item for item in manifest_items("altium-pcbdoc") if not item.heavy]
LENGTH = 10
ANGLE = 1_000
TURN = 360_000_000


def _source(name: str) -> Path:
    if name in AUTHORED:
        return AUTHORED[name]
    return require(next(item for item in ROWS if item.id == name))


@cache
def _kicad(name: str) -> Design:
    cli = kicad_cli()
    assert cli is not None
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / "board.PcbDoc"
        copy.write_bytes(_source(name).read_bytes())
        target = Path(folder) / "board.kicad_pcb"
        env = {**os.environ, "KICAD_CONFIG_HOME": os.path.join(folder, "config")}
        done = subprocess.run(
            [cli, "pcb", "import", "--format", "altium", "-o", str(target), str(copy)],
            capture_output=True, text=True, timeout=900, env=env, check=False,
        )  # fmt: skip
        assert done.returncode == 0, f"{name}: kicad-cli pcb import exits {done.returncode}"
        return KicadBackend().read(target).design


@cache
def _mine(name: str) -> tuple[PcbDocument, Design]:
    data = _source(name).read_bytes()
    document = read_pcbdoc(data)
    return document, import_board(document, file="board.PcbDoc", sha256=hashlib.sha256(data).hexdigest())


def kicad_reference(document: PcbDocument, index: int) -> str:
    """The reference KiCad gives component ``index``: the shown string of its designator text, else its
    ``SOURCEDESIGNATOR``; a name that starts with a digit gets the prefix ``UNK`` (``pcb-read.md``)."""
    shown = next(
        (
            text.text
            for text in document.texts
            if isinstance(text, TextRecord) and text.is_designator and text.prefix.component == index
        ),
        document.components[index].source_designator or "",
    )
    return "UNK" + shown if shown[:1].isdigit() else shown


def compared_pads(footprint: FootprintInstance) -> list[Pad]:
    """The pads KiCad's importer returns with their number: named pads that are not on a paste layer and
    are not unplated holes (``import.md``, "Differences from KiCad's importer")."""
    return [
        pad
        for pad in footprint.pads
        if pad.number
        and pad.kind != "np_thru_hole"
        and not any(layer.endswith(".Paste") for layer in pad.layers)
    ]


def angle_near(a: int, b: int) -> bool:
    delta = (a - b) % TURN
    return min(delta, TURN - delta) <= ANGLE


def _ten(value: int) -> int:
    """``value`` rounded to 10 nm, as KiCad's importer holds a converted length."""
    return (value + 5) // 10 * 10


class Shift:
    """The common translation from the adapter's frame to KiCad's. KiCad rounds each converted coordinate
    to 10 nm and then moves the board by whole nanometres, so the translation is the most frequent
    difference between KiCad's footprint positions and the adapter's, rounded to 10 nm."""

    def __init__(self, pairs: list[tuple[Point, Point]]) -> None:
        xs = Counter(theirs.x - _ten(mine.x) for mine, theirs in pairs)
        ys = Counter(theirs.y - _ten(mine.y) for mine, theirs in pairs)
        self.dx = xs.most_common(1)[0][0] if pairs else 0
        self.dy = ys.most_common(1)[0][0] if pairs else 0

    def near(self, mine: Point, theirs: Point, tolerance: int = LENGTH) -> bool:
        return abs(mine.x + self.dx - theirs.x) <= tolerance and abs(mine.y + self.dy - theirs.y) <= tolerance


A = TypeVar("A")
B = TypeVar("B")


def pair_up(mine: Sequence[A], theirs: list[B], same: Callable[[A, B, int], bool]) -> tuple[list[A], list[B]]:
    """Pair each item of ``mine`` with one of ``theirs`` that ``same`` accepts, one to one: first within
    half the tolerance, so that two items closer to each other than the tolerance are not crossed, then
    within the tolerance. Returns what is left on each side."""
    rest_mine = list(mine)
    rest_theirs = list(theirs)
    for tolerance in (LENGTH // 2, LENGTH):
        unmatched: list[A] = []
        for item in rest_mine:
            hit = next((i for i, q in enumerate(rest_theirs) if same(item, q, tolerance)), None)
            if hit is None:
                unmatched.append(item)
            else:
                rest_theirs.pop(hit)
        rest_mine = unmatched
    return rest_mine, rest_theirs


def compare(name: str) -> Counter[str]:
    """Compare the two readings of one document; return the counts of what was compared and excluded."""
    document, mine = _mine(name)
    theirs = _kicad(name)
    assert mine.board is not None and theirs.board is not None
    board, other = mine.board, theirs.board
    counts: Counter[str] = Counter()

    # --- copper layers (H-A-IMP-LAYERS) ---
    copper = [layer.name for layer in board.layers if layer.kind == "copper"]
    assert copper == [layer.name for layer in other.layers if layer.kind == "copper"], name
    counts["copper-layers"] = len(copper)

    # --- footprints and pads (H-A-IMP-FRAME, H-A-IMP-PADSTACK) ---
    kicad_refs = {c.id: c.ref for c in theirs.circuit.components}
    by_ref: dict[str, list[FootprintInstance]] = {}
    for footprint in other.footprints:
        by_ref.setdefault(kicad_refs.get(footprint.component_id, ""), []).append(footprint)
    my_nets = {net.id: net.name for net in mine.circuit.nets}
    their_nets = {net.id: net.name for net in theirs.circuit.nets}
    pairs: list[tuple[FootprintInstance, FootprintInstance]] = []
    for footprint in board.footprints:
        locator = footprint.provenance.locator if footprint.provenance else ""
        if not locator.startswith("Components6/Data#"):
            counts["free-pads"] += 1  # KiCad makes a footprint of its own too; it has no reference
            continue
        reference = kicad_reference(document, int(locator.rsplit("#", 1)[1]))
        found = by_ref.get(reference, [])
        if len(found) != 1:
            counts["references-not-unique"] += 1
            continue
        pairs.append((footprint, found[0]))
    assert pairs or not document.components, name
    shift = Shift([(a.position, b.position) for a, b in pairs])
    for footprint, twin in pairs:
        assert footprint.side == twin.side, name
        assert angle_near(footprint.rotation, twin.rotation), name
        assert shift.near(footprint.position, twin.position), name
        pads = compared_pads(footprint)
        numbered = [pad for pad in twin.pads if pad.number]
        assert len(pads) == len(numbered), name
        for pad in pads:
            hits = [
                q for q in numbered
                if q.number == pad.number
                and abs(q.position.x - pad.position.x) <= LENGTH
                and abs(q.position.y - pad.position.y) <= LENGTH
            ]  # fmt: skip
            assert hits, name
            assert any(their_nets.get(q.net_id or "") == my_nets.get(pad.net_id or "") for q in hits), name
            if pad.padstack is None and pad.shape != "custom":
                assert any(
                    abs(q.size.w - pad.size.w) <= LENGTH and abs(q.size.h - pad.size.h) <= LENGTH
                    and abs((q.drill or 0) - (pad.drill or 0)) <= LENGTH
                    for q in hits
                ), name  # fmt: skip
                counts["pads-size-and-drill"] += 1
            counts["pads"] += 1
        counts["footprints"] += 1

    # --- vias and tracks (H-A-IMP-LAYERS, H-A-IMP-FRAME) ---
    def net_of(item: Via | Track | Arc | Zone) -> str | None:
        return my_nets.get(item.net_id or "")

    def their_net(item: Via | Track | Arc | Zone) -> str | None:
        return their_nets.get(item.net_id or "")

    def ends(a: Track | Arc, q: Track | Arc, tolerance: int) -> bool:
        straight = shift.near(a.start, q.start, tolerance) and shift.near(a.end, q.end, tolerance)
        return straight or (shift.near(a.start, q.end, tolerance) and shift.near(a.end, q.start, tolerance))

    left = pair_up(
        board.vias,
        list(other.vias),
        lambda via, q, tolerance: (
            shift.near(via.position, q.position, tolerance)
            and abs(q.drill - via.drill) <= LENGTH
            and abs(q.diameter - via.diameter) <= LENGTH
            and their_net(q) == net_of(via)
            and tuple(q.layers) == via.layers
            and q.via_type == via.via_type
        ),
    )
    assert left == ([], []), name
    counts["vias"] = len(board.vias)
    netted = [track for track in board.tracks if track.net_id is not None]
    counts["tracks-without-a-net"] = len(board.tracks) - len(netted)  # KiCad returns no track for them
    left = pair_up(
        netted,
        list(other.tracks),
        lambda track, q, tolerance: (
            q.layer == track.layer
            and abs(q.width - track.width) <= LENGTH
            and their_net(q) == net_of(track)
            and ends(track, q, tolerance)
        ),
    )
    assert left == ([], []), name
    counts["tracks"] = len(netted)
    netted_arcs = [arc for arc in board.arcs if arc.net_id is not None]
    counts["arcs-without-a-net"] = len(board.arcs) - len(netted_arcs)
    left = pair_up(
        netted_arcs,
        list(other.arcs),
        lambda arc, q, tolerance: (
            q.layer == arc.layer
            and abs(q.width - arc.width) <= LENGTH
            and their_net(q) == net_of(arc)
            and ends(arc, q, tolerance)
        ),
    )
    assert left == ([], []), name
    counts["arcs"] = len(netted_arcs)

    # --- zone outlines (H-A-IMP-ZONE) ---
    for zone in board.zones:
        if not zone.outline:
            counts["zones-with-an-arc-outline"] += 1  # the model keeps no arc vertex
            continue
        points = [p for k, p in enumerate(zone.outline) if p != zone.outline[k - 1] or len(zone.outline) == 1]
        counts["zone-vertices-that-repeat"] += len(zone.outline) - len(points)  # KiCad drops them
        hits = [
            q
            for q in other.zones
            if zone.layers[0] in q.layers
            and their_net(q) == net_of(zone)
            and len(q.outline) == len(points)
            and pair_up(points, list(q.outline), shift.near) == ([], [])
        ]
        assert hits, name
        counts["zones"] += 1
    return counts


@pytest.mark.parametrize("name", list(AUTHORED))
def test_authored_documents_against_kicad(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    counts = compare(name)
    with capsys.disabled():
        print(f"\n{name}: {dict(sorted(counts.items()))}")
    assert counts["footprints"] == 3 and counts["pads"] == 36
    assert counts["copper-layers"] == (4 if name == "routed" else 2)
    if name == "routed":
        assert (counts["tracks"], counts["arcs"], counts["vias"], counts["zones"]) == (5, 1, 3, 2)


@pytest.mark.needs_corpus
@pytest.mark.parametrize("name", [item.id for item in ROWS])
def test_corpus_documents_against_kicad(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    counts = compare(name)
    with capsys.disabled():
        print(f"\n{name}: {dict(sorted(counts.items()))}")
    assert counts["footprints"] > 0 and counts["pads"] > 0
