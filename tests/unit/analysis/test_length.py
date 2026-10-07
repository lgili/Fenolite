# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net lengths and pin-to-pin paths (capability board-analyses, "Net length report" and "Pin-to-pin
length"; hypothesis H-G-NETLEN-PATH; change c0106). The benches are those of ``tests/_lengthbench.py``;
the small boards of the join cases are authored here with round values."""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Sequence

import _lengthbench as lb
import pytest
from _lengthbench import mm

from fenolite.analysis import length as lengthmod
from fenolite.analysis.length import LengthReport, LengthRow, measure_lengths
from fenolite.analysis.views import net_list
from fenolite.backends.base import BoardPad, LengthFacts, PadCopper
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.model.design import Design

MM = lb.MM


def bench(case: str, major: int) -> tuple[Design, tuple[BoardPad, ...], LengthFacts]:
    design = lb.read_bench(case, major)
    return design, board_pads(design), KicadBackend().length_facts(design, major=major)


def row(report: LengthReport, net: str) -> LengthRow:
    return next(r for r in report.rows if r.net == net)


def codes(report: LengthReport) -> list[str]:
    return [i.code for i in report.issues]


# --- "Net length report" ----------------------------------------------------------------------------


def test_facts_give_the_totals() -> None:
    design, pads, facts = bench("two", 10)
    report = measure_lengths(design, pads=pads, facts=facts, nets=("L_VIA2",))
    found = row(report, "L_VIA2")
    assert (found.routed, found.vias, found.die, found.total, found.via_count) == (
        20_000_000, 1_580_000, 0, 21_580_000, 1,
    )  # fmt: skip
    assert report.summary == {"nets": 1, "major": 10, "stackup": "default", "count_vias": True}
    assert report.evidence.level is Level.INFERRED
    assert set(report.evidence.hypotheses) >= {"H-G-NETLEN-PATH", "H-K-NETLEN-TOTAL"}
    assert not codes(report) and report.findings().issues == report.issues


def test_no_facts() -> None:
    design, pads, _ = bench("two", 10)
    report = measure_lengths(design, pads=pads, facts=None, nets=("L_VIA2",))
    found = row(report, "L_VIA2")
    assert (found.total, found.vias, found.die, found.via_count) == (20_000_000, 0, 0, 1)
    assert codes(report) == ["analysis.input-missing"]
    assert "length facts" in report.issues[0].message and " 1 via" in report.issues[0].message
    assert report.evidence.level is Level.UNVERIFIED
    assert report.summary == {"nets": 1, "major": None, "stackup": None, "count_vias": None}


def test_no_selection() -> None:
    design, pads, facts = bench("two", 10)
    for nets in ((), ("NOPE*",)):
        report = measure_lengths(design, pads=pads, facts=facts, nets=nets)
        assert report.rows == () and codes(report) == ["analysis.input-missing"]
        assert "net selection" in report.issues[0].message
        assert report.evidence.level is Level.UNVERIFIED


def test_selection_by_glob_sorted_and_equal_to_the_views() -> None:
    design, pads, facts = bench("two", 10)
    report = measure_lengths(design, pads=pads, facts=facts, nets=("L_*",))
    assert [r.net for r in report.rows] == sorted(lb.TWO_NETS)
    views = {r.name: r.length for r in net_list(design, pads=pads)}
    for found in report.rows:
        assert found.routed == views[found.net]
        assert found.total == found.routed + found.vias + found.die
    again = measure_lengths(design, pads=pads, facts=facts, nets=("L_*",))
    assert again == report


# --- "Pin-to-pin length" ----------------------------------------------------------------------------


def test_unbranched_net_through_a_via() -> None:
    design, pads, facts = bench("two", 10)
    found = row(measure_lengths(design, pads=pads, facts=facts, nets=("L_VIAPAD",)), "L_VIAPAD")
    assert found.start == "R7-2" and found.total == 19_980_000 and found.off_path == 0
    (path,) = found.paths
    assert (path.end, path.length, path.vias, path.layers) == ("R8-1", 19_980_000, 1, ("F.Cu", "B.Cu"))


def test_a_track_beyond_a_pad_is_a_stub() -> None:
    design, pads, facts = bench("two", 10)
    report = measure_lengths(design, pads=pads, facts=facts, nets=("L_PASS",))
    found = row(report, "L_PASS")
    assert found.total == 19_200_000 and found.start == "R16-2" and found.off_path == 800_000
    assert [(p.end, p.length) for p in found.paths] == [("R17-1", 18_400_000)]
    assert codes(report) == ["analysis.length-stub"]
    assert report.issues[0].severity == "info" and "0.8 mm" in report.issues[0].message


def test_paths_to_two_loads() -> None:
    design, pads, facts = bench("two", 10)
    report = measure_lengths(design, pads=pads, facts=facts, nets=("L_BRANCH",), starts=("R9",))
    found = row(report, "L_BRANCH")
    assert found.start == "R9-2" and found.total == 23_400_000 and found.off_path == 0
    assert [(p.end, p.length) for p in found.paths] == [("R10-1", 18_400_000), ("R11-1", 14_200_000)]
    other = row(
        measure_lengths(design, pads=pads, facts=facts, nets=("L_BRANCH",), starts=("R11-1",)), "L_BRANCH"
    )
    assert other.start == "R11-1"
    assert [(p.end, p.length) for p in other.paths] == [("R10-1", 14_200_000), ("R9-2", 14_200_000)]
    first = row(measure_lengths(design, pads=pads, facts=facts, nets=("L_BRANCH",)), "L_BRANCH")
    assert first.start == "R10-1"  # the first pad by (ref, number) as texts


def test_kicad_9_counts_no_height_where_the_path_does() -> None:
    for major, total, path in ((10, 18_707_500, 18_707_500), (9, 18_400_000, 18_672_500)):
        design, pads, facts = bench("four-explicit", major)
        found = row(measure_lengths(design, pads=pads, facts=facts, nets=("VIP",)), "VIP")
        assert found.total == total and found.start == "R1-2"
        assert [(p.end, p.length, p.vias, p.layers) for p in found.paths] == [("R2-1", path, 2, ("In1.Cu",))]


@pytest.mark.parametrize(
    ("case", "nets"),
    [
        ("two", ("L_ARC", "L_CC", "L_COL", "L_DIE", "L_EE", "L_THT", "L_VIAPAD")),
        ("two-stackup", ("L_ARC", "L_DIE", "L_VIAPAD")),
        ("four", ("DOGBONE", "VIP", "VIP_BOT")),
        ("four-explicit", ("DOGBONE", "VIP", "VIP_BOT")),
    ],
)
def test_path_equals_total_on_unbranched_benches(case: str, nets: Sequence[str]) -> None:
    """``H-G-NETLEN-PATH``: with the facts of major 10 the one path of an unbranched net is its total."""
    design, pads, facts = bench(case, 10)
    report = measure_lengths(design, pads=pads, facts=facts, nets=nets)
    assert [r.net for r in report.rows] == sorted(nets)
    for found in report.rows:
        assert len(found.paths) == 1 and found.paths[0].length == found.total, found.net
        assert found.off_path == 0
    assert not [c for c in codes(report) if c != "analysis.length-stub"]


def test_a_layer_change_inside_a_pad_weighs_nothing() -> None:
    design, pads, facts = bench("two", 10)
    found = row(measure_lengths(design, pads=pads, facts=facts, nets=("L_THT2",)), "L_THT2")
    by_end = {p.end: p for p in found.paths}
    assert found.start == "D3-2" and found.total == 20_000_000
    assert (by_end["D4-1"].length, by_end["D5-1"].length) == (10_000_000, 20_000_000)
    assert by_end["D5-1"].layers == ("F.Cu", "B.Cu") and by_end["D5-1"].vias == 0


def test_the_project_switch_weighs_no_via() -> None:
    design = lb.read_bench("two", 10)
    pads = board_pads(design)
    facts = KicadBackend().length_facts(design, major=10)
    off = dataclasses.replace(
        facts,
        count_vias=False,
        nets={n: dataclasses.replace(v, vias=0, total=v.routed + v.die) for n, v in facts.nets.items()},
    )
    report = measure_lengths(design, pads=pads, facts=off, nets=("L_VIAPAD",))
    found = row(report, "L_VIAPAD")
    assert found.total == 18_400_000 and found.paths[0].length == 18_400_000 and not codes(report)


# --- joins on authored boards ------------------------------------------------------------------------


def _pad(ref: str, number: str, at: Point, net_id: str, layers: tuple[str, ...] = ("F.Cu",)) -> BoardPad:
    copper = tuple(PadCopper(layer, (at,), MM) for layer in layers)  # a round pad of 1 mm
    return BoardPad(
        footprint_id=f"fp_{ref}", ref=ref, path="", pad_id=f"pad_{ref}_{number}", number=number, kind="smd",
        position=at, rotation=0, side="top", layers=layers, net_id=net_id, net="N", copper=copper,
    )  # fmt: skip


def _board(build: lb.Builder) -> tuple[Design, str]:
    design = build.build("joins")
    return design, build.net("N")


def test_a_pad_the_copper_does_not_reach() -> None:
    b = lb.Builder(10)
    b.track("N", mm(0, 0), mm(10, 0))
    design, net = _board(b)
    pads = [_pad("U1", "1", mm(0, 0), net), _pad("U2", "1", mm(10, 0), net), _pad("U3", "1", mm(30, 0), net)]
    report = measure_lengths(design, pads=pads, nets=("N",))
    found = row(report, "N")
    assert [(p.end, p.length) for p in found.paths] == [("U2-1", 10_000_000), ("U3-1", None)]
    opened = [i for i in report.issues if i.code == "analysis.length-open"]
    assert len(opened) == 1 and opened[0].severity == "warning" and "U3-1" in opened[0].message


def test_join_an_end_splits_a_track_body() -> None:
    """A T junction: the end of the second track lies inside the body of the first."""
    b = lb.Builder(10)
    b.track("N", mm(0, 0), mm(20, 0))
    b.track("N", mm(8, 0.1), mm(8, 6))  # its end is 0.1 mm off the centre line, inside the copper
    design, net = _board(b)
    pads = [_pad("U1", "1", mm(0, 0), net), _pad("U2", "1", mm(8, 6), net), _pad("U3", "1", mm(20, 0), net)]
    found = row(measure_lengths(design, pads=pads, nets=("N",)), "N")
    assert [(p.end, p.length) for p in found.paths] == [("U2-1", 13_900_000), ("U3-1", 20_000_000)]
    assert found.off_path == 0


def test_join_crossing_tracks_are_not_joined() -> None:
    b = lb.Builder(10)
    b.track("N", mm(0, 0), mm(20, 0))
    b.track("N", mm(8, -5), mm(8, 5))
    design, net = _board(b)
    pads = [_pad("U1", "1", mm(0, 0), net), _pad("U2", "1", mm(8, 5), net)]
    report = measure_lengths(design, pads=pads, nets=("N",))
    assert row(report, "N").paths[0].length is None
    assert "analysis.length-open" in codes(report)


def test_join_an_end_splits_an_arc() -> None:
    """A track ends on the middle of a half circle of radius 3 mm: the arc splits into two quarters."""
    b = lb.Builder(10)
    b.arc("N", mm(15, 30), mm(18, 33), mm(21, 30))
    b.track("N", mm(18, 33), mm(18, 40))
    design, net = _board(b)
    pads = [
        _pad("U1", "1", mm(15, 30), net),
        _pad("U2", "1", mm(18, 40), net),
        _pad("U3", "1", mm(21, 30), net),
    ]
    found = row(measure_lengths(design, pads=pads, nets=("N",)), "N")
    assert [(p.end, p.length) for p in found.paths] == [("U2-1", 4_712_389 + 7_000_000), ("U3-1", 9_424_778)]


def test_join_a_via_on_a_track_body_and_between_layers() -> None:
    """A via on the body of a top track, away from its ends, and a bottom track that starts in it."""
    b = lb.Builder(10)
    b.track("N", mm(0, 0), mm(20, 0))
    b.via("N", mm(5, 0))
    b.track("N", mm(5, 0), mm(5, 7), "B.Cu")
    design, net = _board(b)
    pads = [_pad("U1", "1", mm(0, 0), net), _pad("U2", "1", mm(5, 7), net, ("B.Cu",))]
    facts = KicadBackend().length_facts(design, major=10)
    found = row(measure_lengths(design, pads=pads, facts=facts, nets=("N",)), "N")
    (path,) = found.paths
    assert (path.length, path.vias, path.layers) == (5_000_000 + 1_580_000 + 7_000_000, 1, ("F.Cu", "B.Cu"))
    assert found.off_path == 15_000_000


def test_join_equal_paths_take_the_first_ids() -> None:
    """Two tracks of one length between two pads: the path takes the one whose id sorts first."""
    b = lb.Builder(10)
    first = b.track("N", mm(0, 0), mm(10, 0))
    b.track("N", mm(0, 0), mm(10, 0), "B.Cu")
    design, net = _board(b)
    both = ("F.Cu", "B.Cu")
    pads = [_pad("U1", "1", mm(0, 0), net, both), _pad("U2", "1", mm(10, 0), net, both)]
    found = row(measure_lengths(design, pads=pads, nets=("N",)), "N")
    assert found.paths[0].length == 10_000_000 and found.paths[0].layers == (first.layer,)
    assert found.off_path == 10_000_000


def test_two_pads_of_one_number() -> None:
    """A pin bonded to two pads (c0123): each pad has its path, in pad id order."""
    b = lb.Builder(10)
    b.track("N", mm(0, 0), mm(10, 0))
    b.track("N", mm(10, 0), mm(10, 4))
    design, net = _board(b)
    twin = dataclasses.replace(_pad("U2", "1", mm(10, 4), net), pad_id="pad_U2_1b")
    pads = [_pad("U1", "1", mm(0, 0), net), _pad("U2", "1", mm(10, 0), net), twin]
    found = row(measure_lengths(design, pads=pads, nets=("N",)), "N")
    assert [(p.end, p.length) for p in found.paths] == [("U2-1", 10_000_000), ("U2-1", 14_000_000)]


def test_no_pads_no_paths() -> None:
    design, _, facts = bench("two", 10)
    found = row(measure_lengths(design, pads=None, facts=facts, nets=("L_CC",)), "L_CC")
    assert found.start is None and found.paths == () and found.off_path == 0 and found.total == 18_400_000


# --- the property of H-G-NETLEN-PATH ----------------------------------------------------------------


def test_generated_unbranched_chains() -> None:
    """On unbranched chains of tracks, arcs and vias between two pads, the path equals the total with
    the facts of major 10."""
    rng = random.Random(106)
    for _ in range(40):
        b = lb.Builder(10)
        at, layer = mm(10, 10), "F.Cu"
        start = at
        for _ in range(rng.randint(1, 8)):
            kind = rng.choice(("track", "track", "arc", "via"))
            if kind == "via":
                b.via("N", at)
                layer = "B.Cu" if layer == "F.Cu" else "F.Cu"
                kind = "track"
            if kind == "track":
                step = Point(at.x + rng.randint(2, 9) * MM, at.y + rng.choice((0, 1, 2)) * MM)
                b.track("N", at, step, layer)
            else:
                radius = rng.randint(2, 5) * MM
                step = Point(at.x + 2 * radius, at.y)
                b.arc("N", at, Point(at.x + radius, at.y + radius), step, layer)
            at = step
        design, net = _board(b)
        last = "F.Cu" if layer == "F.Cu" else "B.Cu"
        pads = [_pad("U1", "1", start, net), _pad("U2", "1", at, net, (last,))]
        facts = KicadBackend().length_facts(design, major=10)
        # the facts know no pad of these authored pads: give them the same pads
        from fenolite.backends.kicad import lengths as kicad_lengths

        depths, _ = kicad_lengths.layer_depths(design.board, major=10)  # type: ignore[arg-type]
        nets = kicad_lengths.net_lengths(design, pads=pads, depths=depths, major=10)
        facts = dataclasses.replace(facts, nets=nets)
        found = row(measure_lengths(design, pads=pads, facts=facts, nets=("N",)), "N")
        assert found.paths[0].length == found.total, (found, design.board.tracks, design.board.vias)  # type: ignore[union-attr]
        assert found.off_path == 0


def test_module_evidence() -> None:
    assert lengthmod.EVIDENCE.level is Level.INFERRED
    assert lengthmod.EVIDENCE.hypotheses == ("H-G-NETLEN-PATH",)
