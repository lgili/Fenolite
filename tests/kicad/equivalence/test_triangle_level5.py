# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level 5 over the triangle (capability design-equivalence, "Level 5 over the triangle"; change c0089;
``H-G-EQ-L5-TRIANGLE``; S-0020, S-0166).

Two sets of boards:

- **The routed sample** (``tests/kicad/_routetriangle.py``): its KiCad board, the Altium PCB document that
  Fenolite writes from it, and KiCad's import of that document are compared pairwise. It is authored for
  Fenolite, so this part needs no corpus; the probe ``equiv-l5-triangle`` records its outcome.
- **The public PCB documents** of the triangle of c0045 (the ``altium-pcbdoc`` rows): Fenolite's read of
  each document and the read of KiCad's conversion of it. Fenolite writes nothing here, so a row has two
  corners.

No level-5 difference may remain within the tolerances of the importer's profile. What level 5 does not
judge is asserted by count: the nets that depend on a zone without a fill (KiCad's importer leaves the
zones of a document unfilled) and one stub notice whose cause is Fenolite's own reader. The counts are
recorded in ``docs/evidence/equivalence-triangle.md``, "Level 5". The test writes counts only.
"""

from __future__ import annotations

import dataclasses
from collections import Counter

import _probes
import pytest
from _corpus import manifest_items, require
from _routetriangle import PAIRS, compare, corners
from _triangle import Sides, profile_for, report, sides

from fenolite.checks.equivalence import EquivalenceReport, LevelResult, routing
from fenolite.checks.equivalence.levels import level_components

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
ROWS = [item for item in manifest_items("altium-pcbdoc") if not item.heavy]
IDS = [item.id for item in ROWS]
IGNORED_REFS = ("", "[*]")
"""The references that a document holds several times and that cannot be paired (c0045): the empty
reference of pads that belong to no component, and the designator ``*``."""
NOTICES: dict[str, dict[str, int]] = {
    "altium-third-party-pcbdoc-01": {"route-unjudged": 8},
    "altium-third-party-pcbdoc-02": {"route-unjudged": 4},
    "altium-third-party-pcbdoc-03": {"route-stub": 1},
}
"""Row id → the notices of level 5 by kind (every other row has none).

``route-unjudged``: the net holds a zone that KiCad's conversion leaves without a fill, while the document
holds its poured copper, so the two reads cannot be compared on it.

``route-stub`` on one row: Fenolite's Altium adapter reads a poured region by its outline and drops its
holes, so five islands of copper that lie in holes of a pour are joined to the pour in Fenolite's read and
are five pieces without a pad in KiCad's. The cause is Fenolite's, so it gets no rule; it is recorded as
an open fault of the adapter."""
MEASURED_NM = 20
MEASURED_PPM = 18
"""The largest difference of a routed length on one copper span over the public documents, in nanometres
and (for the differences above the absolute tolerance) in parts per million of the longer length."""


def _line(name: str, result: LevelResult) -> str:
    summary = result.summary
    return (
        f"{name} level 5: compared {result.compared}, differences {len(result.differences)}, "
        f"excluded {len(result.excluded)}, notices {len(result.notices)}, pieces {summary['pieces']}, "
        f"vias {summary['vias']}, length {summary['length']}, zones_unfilled {summary['zones_unfilled']}"
    )


def _kinds(result: LevelResult) -> dict[str, int]:
    return dict(Counter(notice.kind for notice in result.notices))


# --- the routed sample -----------------------------------------------------------------------------


@pytest.mark.parametrize("pair", PAIRS, ids=["-".join(pair) for pair in PAIRS])
def test_sample(pair: tuple[str, str], capsys: pytest.CaptureFixture[str]) -> None:
    """The three corners are pairwise equal at levels 1 to 5, with no relative tolerance at all."""
    found = corners()
    result = compare(found.of(pair[0]), found.of(pair[1]), found.version, ppm=0)
    fifth = result.levels[-1]
    with capsys.disabled():
        print("\n" + _line("sample " + "-".join(pair), fifth))
    assert [len(level.differences) for level in result.levels] == [0, 0, 0, 0, 0] and result.equivalent
    assert fifth.compared == 4 and fifth.excluded == ()
    assert fifth.summary["pieces"] == {"a": 5, "b": 5} and fifth.summary["vias"] == {"a": 3, "b": 3}
    assert fifth.summary["nets_unpaired"] == {"a": 0, "b": 0}
    assert fifth.summary["copper_no_net"] == {"a": 0, "b": 0} and fifth.summary["unshaped"] == {
        "a": 0,
        "b": 0,
    }
    lengths = fifth.summary["length"]
    assert abs(lengths["a"] - lengths["b"]) <= 10 and lengths["a"] > 50_000_000
    # the sample's zone is written unpoured, so the one net it would join is not judged
    assert [(notice.kind, notice.where) for notice in fifth.notices] == [("route-unjudged", "GND")]


def test_sample_pieces() -> None:
    """What the three reads hold, read by ``pieces``: the same pads joined, the same vias, and lengths
    within the 10 nm of the importer's steps, span by span."""
    found = corners()
    held = {}
    for name in ("kicad", "altium", "imported"):
        design = found.of(name)
        names = {net.id: net.name for net in design.circuit.nets}
        held[name] = {
            names[net]: [(p.pads, p.vias, p.copper) for p in pieces if p.copper]
            for net, pieces in routing.pieces(design).items()
        }
    assert held["kicad"] == held["altium"] == held["imported"]
    assert held["kicad"] == {
        "GND": [(("U1-10",), (("top-bottom", 1),), True)],
        "LED_A": [(("D1-2", "R1-2"), (("top-bottom", 1),), True)],
        "LED_DRV": [(("R1-1", "U1-1"), (), True)],
        "VIN": [(("U1-9",), (("top-bottom", 1),), True)],
    }
    spans = {
        name: sorted(
            (span, length)
            for pieces in routing.pieces(found.of(name)).values()
            for piece in pieces
            for span, length in piece.lengths
        )
        for name in held
    }
    assert [span for span, _ in spans["kicad"]] == ["bottom", "inner1", "inner2", "top"]
    for name in ("altium", "imported"):
        for (span, length), (other, twin) in zip(spans["kicad"], spans[name], strict=True):
            assert span == other and abs(length - twin) <= 10, (name, span)


def test_sample_edit_is_seen() -> None:
    """The triangle is not blind: with one via taken out of KiCad's import, level 5 says which net."""
    found = corners()
    board = found.imported.board
    assert board is not None
    nets = {net.id: net.name for net in found.imported.circuit.nets}
    gone = next(via for via in board.vias if nets[via.net_id or ""] == "LED_A")
    vias = tuple(via for via in board.vias if via is not gone)
    edited = dataclasses.replace(found.imported, board=dataclasses.replace(board, vias=vias))
    result = compare(found.kicad, edited, found.version).levels[-1]
    assert [(d.kind, d.where) for d in result.differences] == [("route-connectivity", "LED_A:D1-2")]


def test_probe() -> None:
    assert _probes.run("equiv-l5-triangle") == "equal"


# --- the public documents --------------------------------------------------------------------------


def _sides(row: str) -> Sides:
    item = next(i for i in ROWS if i.id == row)
    return sides(require(item), row)


def _report(row: str, **options: object) -> EquivalenceReport:
    return report(_sides(row), ignore_refs=IGNORED_REFS, level=5, **options)  # type: ignore[arg-type]


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", IDS)
def test_corpus(row: str, capsys: pytest.CaptureFixture[str]) -> None:
    """No level-5 difference remains under the profile; no rule of the profile is of level 5."""
    found = _report(row)
    fifth = found.levels[-1]
    with capsys.disabled():
        print("\n" + _line(row, fifth))
    assert fifth.level == 5 and fifth.compared > 0
    assert fifth.differences == (), [(d.kind, d.where) for d in fifth.differences][:10]
    assert fifth.excluded == () and not [r for r in profile_for(_sides(row).version).rules if r.level == 5]
    assert fifth.summary["nets_unpaired"] == {"a": 0, "b": 0}
    assert fifth.summary["vias"]["a"] == fifth.summary["vias"]["b"] > 0
    assert _kinds(fifth) == NOTICES.get(row, {})
    assert fifth.summary["unjudged"] == NOTICES.get(row, {}).get("route-unjudged", 0)


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", IDS)
def test_corpus_lengths(row: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Without the relative tolerance the only differences are routed lengths: connectivity and vias agree
    exactly, and no length differs by more than what was measured (the importer rounds each end of each
    segment to 10 nm, ``H-G-EQ-ROUND-2``)."""
    bare = _report(row, ppm=0).levels[-1]
    assert {d.kind for d in bare.differences} <= {"route-length"}
    found = _sides(row)
    _, refs = level_components(found.a, found.b, ignore_refs=IGNORED_REFS)
    pairing = routing.pair_nets(found.a, found.b, refs)
    held_a, held_b = routing.pieces(found.a), routing.pieces(found.b)
    worst_nm = worst_ppm = spans = 0
    for net_a, net_b in pairing.pairs:
        one = routing.net_routing("", held_a.get(net_a, ()), pairing.elements, False)
        other = routing.net_routing("", held_b.get(net_b, ()), pairing.elements, False)
        for pads in set(one.joined) & set(other.joined):
            lengths_a, lengths_b = one.joined[pads].lengths, other.joined[pads].lengths
            for span in set(lengths_a) | set(lengths_b):
                p, q = lengths_a.get(span, 0), lengths_b.get(span, 0)
                spans += 1
                worst_nm = max(worst_nm, abs(p - q))
                if abs(p - q) > profile_for(found.version).tolerance_nm:
                    worst_ppm = max(worst_ppm, -(-abs(p - q) * 1_000_000 // max(p, q)))
    with capsys.disabled():
        print(f"\n{row} level 5 lengths: spans {spans}, largest difference {worst_nm} nm, {worst_ppm} ppm")
    assert spans > 0 and worst_nm <= MEASURED_NM and worst_ppm <= MEASURED_PPM
    assert MEASURED_PPM <= profile_for(found.version).tolerance_ppm == 20
