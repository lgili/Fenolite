# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper check (capability copper-check; change c0029). Hermetic: no file is written and no tool
runs; pads come from fake board-frame records, or from the KiCad frame where a scenario asks for it."""

from __future__ import annotations

import builtins
import dataclasses
import json
import random
import subprocess
from pathlib import Path

import pytest
from _coppercheck import Copper, disc_entry, mm, rect_entry, renet_bench
from _placed import Part, design_of

from fenolite.backends.base import PadCopper
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.checks import copper as copper_module
from fenolite.checks.copper import ARC_TOL_NM, EVIDENCE, CopperReport, check_copper
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.model.rules import Selector

TWO_LAYER = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
CLASS = "Signal"
ZONE_A = (Point(0, 0), Point(mm(10), 0), Point(mm(10), mm(10)), Point(0, mm(10)))
ZONE_B = (Point(mm(5), mm(5)), Point(mm(15), mm(5)), Point(mm(15), mm(15)), Point(mm(5), mm(15)))


def codes(report: CopperReport) -> list[str]:
    return [issue.code for issue in report.issues]


def classed(clearance: int | None = mm(0.2)) -> Copper:
    """A bench whose nets ``A`` and ``B`` are in the class ``Signal`` with ``clearance``."""
    made = Copper()
    made.netclass(CLASS, clearance)
    made.net("A", CLASS)
    made.net("B", CLASS)
    return made


def parallel(made: Copper, edge_gap: int, *, width: int = 250_000) -> None:
    """Two parallel tracks of nets ``A`` and ``B`` on ``F.Cu`` whose edges are ``edge_gap`` apart."""
    made.track("A", Point(0, 0), Point(mm(10), 0), width=width)
    made.track("B", Point(0, width + edge_gap), Point(mm(10), width + edge_gap), width=width)


# --- items and their shapes -----------------------------------------------------------------------


def test_via_span_on_four_layers() -> None:
    made = Copper(layers=4)
    made.via("A", Point(0, 0), layers=("F.Cu", "In1.Cu"), via_type="blind")
    made.via("B", Point(mm(5), 0))
    made.via("C", Point(mm(9), 0), layers=("B.Cu", "In2.Cu"), via_type="blind")
    made.via("D", Point(mm(13), 0), layers=("F.Cu", "Nowhere.Cu"), via_type="blind")
    items = copper_module._Items(made.build(), None, ARC_TOL_NM)  # pyright: ignore[reportPrivateUsage]
    blind, through, low, unknown = (tuple(item.shapes) for item in items.items)
    assert items.copper == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    assert blind == ("F.Cu", "In1.Cu")
    assert through == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    assert low == ("In2.Cu", "B.Cu")
    assert unknown == through  # layers that do not name two copper layers of the board


def test_blind_via_span_is_judged() -> None:
    made = Copper(layers=4)
    made.via("A", Point(0, 0), layers=("F.Cu", "In1.Cu"), via_type="blind")
    made.track("B", Point(-mm(2), 0), Point(mm(2), 0), layer="In2.Cu")
    assert check_copper(made.build(), pads=None).findings == ()
    made.track("B", Point(-mm(2), 0), Point(mm(2), 0), layer="In1.Cu")
    (short,) = check_copper(made.build(), pads=None).findings
    assert (short.code, short.layer) == ("copper.short", "In1.Cu")


def test_outline_is_not_copper() -> None:
    made = Copper()
    made.zone("GND", ZONE_A)
    made.track("VIN", Point(mm(2), mm(5)), Point(mm(8), mm(5)))
    report = check_copper(made.build(), pads=None)
    assert report.findings == () and report.summary["items"] == {"track": 1}


def test_pads_without_a_frame() -> None:
    design = design_of(
        Part("R1", "Mini_R_0603", 10, 10, nets={"1": "A", "2": "B"}),
        Part("R2", "Mini_R_0603", 20, 10, nets={"1": "A", "2": "B"}),
    )
    report = check_copper(design, pads=None)
    assert report.summary["unsupported"] == {"pad": 4}
    (warning,) = report.issues
    assert (warning.code, warning.severity) == ("copper.item-unsupported", "warning")
    assert warning.message.startswith("4 pad item(s)") and "no board frame" in warning.message


def test_npth_pads_are_not_unsupported() -> None:
    """Scenario "Mounting holes are not unsupported": the unnumbered ``np_thru_hole`` pad of
    ``Mini_Edge_Cases`` has no copper entry, and is not copper."""
    design = design_of(Part("J1", "Mini_Edge_Cases", 0, 0))
    pads = KicadBackend().board_pads(design)
    assert any(pad.kind == "np_thru_hole" and not pad.copper for pad in pads)
    report = check_copper(design, pads=pads)
    assert "pad" not in report.summary["unsupported"]  # type: ignore[operator]
    assert not [i for i in report.issues if i.code == "copper.item-unsupported"]
    assert check_copper(design, pads=None).summary["unsupported"] == {
        "pad": sum(1 for pad in pads if pad.kind != "np_thru_hole" and pad.copper)
    }


def test_pad_entries_become_shapes() -> None:
    made = Copper()
    made.pad("R1", "1", "A", rect_entry(0, 0, mm(1), mm(1)))
    made.pad("R1", "2", "B", disc_entry(mm(1.25), mm(0.5), mm(0.6), exact=False))
    made.pad("H1", "", None, kind="np_thru_hole", layers=("*.Cu",))
    made.pad("X1", "1", "A", layers=("F.Paste",))
    made.pad("X1", "2", "A", layers=("*.Cu",), kind="thru_hole")
    design = made.build()
    report = check_copper(design, pads=made.pads)
    (short,) = report.findings
    assert short.code == "copper.short" and short.where == "R1-1, R1-2"
    assert short.message.endswith("(approximated pad shape)")
    assert report.summary["approximated"] == 1
    assert report.summary["items"] == {"pad": 2}
    assert report.summary["unsupported"] == {"pad": 1}  # X1-2 names copper and has no entry


def test_pad_entry_that_the_kernel_refuses() -> None:
    """A filled ring without area passes ``PadCopper`` and is refused by ``Thick``: the pad is left out."""
    made = Copper()
    flat = PadCopper("F.Cu", (Point(0, 0), Point(5, 5), Point(9, 9)), 0, filled=True)
    made.pad("R1", "1", "A", flat)
    report = check_copper(made.build(), pads=made.pads)
    assert report.summary["unsupported"] == {"pad": 1} and report.evidence.level is Level.UNVERIFIED


def test_fills_are_copper_and_bad_fills_are_counted() -> None:
    made = Copper()
    square = (Point(0, 0), Point(mm(4), 0), Point(mm(4), mm(4)), Point(0, mm(4)), Point(0, 0))
    made.zone("GND", ZONE_A, fills=[square, (Point(0, 0), Point(1, 1), Point(2, 2))], locator="zone[0]")
    made.track("VIN", Point(mm(1), mm(1)), Point(mm(3), mm(1)), locator="segment[0]")
    report = check_copper(made.build(), pads=None)
    (short,) = report.findings
    assert short.where == "zone[0], segment[0]" and [item.kind for item in short.items] == ["fill", "track"]
    assert report.summary["unsupported"] == {"fill": 1}
    assert report.summary["items"] == {"fill": 1, "track": 1}


def test_arc_that_the_kernel_refuses() -> None:
    made = Copper()
    made.arc("A", Point(0, 0), Point(0, 0), Point(mm(1), 0))
    report = check_copper(made.build(), pads=None)
    assert report.summary["unsupported"] == {"arc": 1}
    assert codes(report) == ["copper.item-unsupported"]


def test_invalid_arc_tolerance() -> None:
    with pytest.raises(ValueError, match="arc_tol"):
        check_copper(Copper().build(), pads=None, arc_tol=0)


def test_design_without_a_board() -> None:
    report = check_copper(dataclasses.replace(Copper().build(), board=None), pads=None)
    assert report.findings == () and report.issues == () and report.summary["pairs"] == 0


# --- pairs ----------------------------------------------------------------------------------------


def test_same_net_never_judged() -> None:
    made = Copper()
    made.track("GND", Point(0, 0), Point(mm(5), 0))
    made.track("GND", Point(mm(2), 0), Point(mm(8), 0))
    made.track(None, Point(0, mm(3)), Point(mm(5), mm(3)))
    made.track(None, Point(mm(2), mm(3)), Point(mm(8), mm(3)))
    report = check_copper(made.build(), pads=None)
    assert report.findings == () and report.summary["pairs"] == 0


def test_netless_copper_is_judged_against_a_net() -> None:
    made = Copper()
    made.track("GND", Point(0, 0), Point(mm(5), 0))
    made.track(None, Point(mm(2), 0), Point(mm(8), 0))
    (short,) = check_copper(made.build(), pads=None).findings
    assert "<no net>" in short.message and "GND" in short.message


def test_one_finding_for_a_pair_on_two_layers() -> None:
    made = Copper()
    made.via("A", Point(0, 0))
    made.via("B", Point(mm(0.5), 0))
    report = check_copper(made.build(), pads=None)
    (short,) = report.findings
    assert (short.code, short.layer) == ("copper.short", "F.Cu")
    assert report.summary["pairs"] == 2 and report.summary["layers"] == ["F.Cu", "B.Cu"]


# --- shorts ---------------------------------------------------------------------------------------


def touching(offset: int = 0, made: Copper | None = None) -> Copper:
    """A 0.6 mm ``GND`` via whose centre is 0.425 mm (plus ``offset``) from the centre line of a 0.25 mm
    ``VIN`` track: they touch exactly at offset 0."""
    made = made if made is not None else Copper()
    made.via("GND", Point(0, mm(0.425) + offset), locator="via[0]")
    made.track("VIN", Point(-mm(5), 0), Point(mm(5), 0), locator="segment[0]")
    return made


def test_via_touching_a_track_of_another_net() -> None:
    (short,) = check_copper(touching().build(), pads=None).findings
    assert (short.code, short.severity, short.layer, short.gap) == ("copper.short", "error", "F.Cu", 0)
    assert "GND" in short.message and "VIN" in short.message and "F.Cu" in short.message
    assert short.at == Point(0, 212_500) and "(0, 0.2125) mm" in short.message  # between the two cores
    assert [(item.kind, item.net) for item in short.items] == [("track", "VIN"), ("via", "GND")]
    assert check_copper(touching(1).build(), pads=None).findings == ()


def test_short_reported_without_any_clearance() -> None:
    report = check_copper(touching(-mm(0.1)).build(), pads=None)
    (short,) = report.findings
    assert short.code == "copper.short" and short.clearance is None and short.source == ""
    assert report.summary["max_clearance"] == 0


def test_short_names_the_clearance_in_force() -> None:
    made = Copper()
    made.netclass("Default", mm(0.2))
    (short,) = check_copper(touching(made=made).build(), pads=None).findings
    assert (short.clearance, short.source) == (mm(0.2), "class:Default")


def test_ignore_rule_never_silences_a_short() -> None:
    made = touching(-mm(0.1))
    made.rule("quiet", mm(0.2), severity="ignore")
    report = check_copper(made.build(), pads=None)
    assert [f.code for f in report.findings] == ["copper.short"]
    assert check_copper(touching(mm(0.05), made=_with_ignore()).build(), pads=None).findings == ()


def _with_ignore() -> Copper:
    made = Copper()
    made.netclass("Default", mm(0.2))
    made.rule("quiet", mm(0.2), severity="ignore")
    return made


# --- clearance ------------------------------------------------------------------------------------


def test_strict_comparison() -> None:
    made = classed()
    parallel(made, mm(0.2))
    assert check_copper(made.build(), pads=None).findings == ()
    closer = classed()
    parallel(closer, mm(0.2) - 1)
    (found,) = check_copper(closer.build(), pads=None).findings
    assert (found.code, found.severity) == ("copper.clearance", "error")
    assert (found.gap, found.clearance, found.source) == (199_999, 200_000, f"class:{CLASS}")
    for text in ("A", "B", "F.Cu", "0.199999 mm", "0.2 mm", f"class:{CLASS}", ") mm"):
        assert text in found.message


def test_warning_rule() -> None:
    made = classed(None)
    parallel(made, mm(0.15))
    made.rule("soft", mm(0.2), Selector("net", "A"), Selector("net", "B"), severity="warning")
    (found,) = check_copper(made.build(), pads=None).findings
    assert (found.code, found.severity, found.source) == ("copper.clearance", "warning", "rule:soft")
    assert "rule:soft" in found.message
    (issue,) = [i for i in check_copper(made.build(), pads=None).issues if i.code == "copper.clearance"]
    assert issue.severity == "warning"


def test_board_minimum_and_switches_reach_the_resolver() -> None:
    made = classed(None)
    parallel(made, mm(0.15))
    made.rule("tight", mm(0.1))
    design = made.build()
    assert check_copper(design, pads=None, min_clearance=mm(0.2)).findings == ()
    (found,) = check_copper(design, pads=None, min_clearance=mm(0.2), floor_over_rules=True).findings
    assert found.source == "floor"
    classy = classed()
    parallel(classy, mm(0.15))
    classy.rule("tight", mm(0.1))
    assert check_copper(classy.build(), pads=None).findings == ()
    (found,) = check_copper(classy.build(), pads=None, rules_over_classes=False).findings
    assert found.source == f"class:{CLASS}"


def test_clearance_unset_is_counted() -> None:
    made = Copper()
    parallel(made, 0)  # touching boxes, no clearance anywhere: one candidate pair, a short
    made.track("C", Point(0, mm(0.6)), Point(mm(10), mm(0.6)), width=mm(0.2))
    report = check_copper(made.build(), pads=None)
    assert report.summary["shorts"] == 1
    made = Copper()
    made.track("A", Point(0, 0), Point(mm(10), mm(10)))
    made.track("B", Point(0, mm(1)), Point(mm(9), mm(10)))  # boxes meet, copper does not
    report = check_copper(made.build(), pads=None)
    assert report.findings == () and report.summary["unset_pairs"] == 1
    (info,) = report.issues
    assert (info.code, info.severity) == ("copper.clearance-unset", "info") and info.message.startswith("1 ")
    assert report.evidence.level is Level.INFERRED  # an unset clearance does not lower the level


def test_arc_band_never_hides_a_violation() -> None:
    """A 0.25 mm arc of radius 5 mm and a track whose true edge gap is 5 µm below a 0.2 mm clearance."""
    made = classed()
    made.arc("A", Point(mm(5), 0), Point(0, mm(5)), Point(-mm(5), 0))
    made.track("B", Point(-mm(2), mm(5.445)), Point(mm(2), mm(5.445)))
    (found,) = check_copper(made.build(), pads=None).findings
    assert found.code == "copper.clearance" and found.gap <= 195_000  # a lower bound
    assert found.gap >= 195_000 - 2 * (ARC_TOL_NM + 1) - ARC_TOL_NM - 2


def test_arc_band_reports_a_short_only_when_the_copper_touches() -> None:
    def gap(edge_gap: int) -> list[str]:
        made = Copper()
        made.arc("A", Point(mm(5), 0), Point(0, mm(5)), Point(-mm(5), 0))
        y = mm(5) + 250_000 + edge_gap
        made.track("B", Point(-mm(2), y), Point(mm(2), y))
        return [f.code for f in check_copper(made.build(), pads=None).findings]

    assert gap(-mm(0.01)) == ["copper.short"]  # 10 µm of overlap: the true copper touches
    assert gap(mm(0.01)) == []  # no clearance in force, and the copper does not touch


# --- zone outlines --------------------------------------------------------------------------------


def test_zone_overlap() -> None:
    made = Copper()
    made.zone("GND", ZONE_A, locator="zone[0]")
    made.zone("VIN", ZONE_B, locator="zone[1]")
    report = check_copper(made.build(), pads=None)
    (found,) = report.findings
    assert (found.code, found.severity, found.layer) == ("copper.zone-overlap", "warning", "F.Cu")
    assert found.where == "zone[0], zone[1]" and "GND" in found.message and "VIN" in found.message
    assert report.summary["zone_overlaps"] == 1
    made = Copper()
    made.zone("GND", ZONE_A)
    made.zone("VIN", ZONE_B, priority=1)
    assert check_copper(made.build(), pads=None).findings == ()


def test_zone_overlap_needs_two_nets_a_shared_layer_and_an_outline() -> None:
    made = Copper()
    made.zone("GND", ZONE_A)
    made.zone("GND", ZONE_B)
    made.zone("VIN", ZONE_B, layer="B.Cu")
    made.zone("SIG", ())
    made.zone("SIG", (Point(0, 0), Point(1, 1), Point(2, 2)))
    report = check_copper(made.build(), pads=None)
    assert report.findings == ()
    assert report.summary["unsupported"] == {"zone-outline": 2}
    assert report.issues == () and report.evidence.level is Level.INFERRED


# --- locations and determinism --------------------------------------------------------------------


def located_design() -> Design:
    """``R1`` with pad 2 on ``VIN`` and a ``GND`` via over that pad, written and read back so every
    entity carries its locator."""
    bench = design_of(Part("R1", "Mini_R_0603", 10, 10, nets={"1": "N1", "2": "VIN"}), extra_nets=("GND",))
    assert bench.board is not None
    made = Copper()
    made.nets = {net.name: net for net in bench.circuit.nets}
    via = made.via("GND", Point(mm(10.8), mm(10)))
    board = dataclasses.replace(bench.board, vias=(via,))
    return read_board(
        write_board(dataclasses.replace(bench, board=board), target=10).text, file="located.kicad_pcb"
    )


def test_pad_and_via_located() -> None:
    design = located_design()
    assert design.board is not None
    (via,) = design.board.vias
    assert via.provenance is not None and via.provenance.locator
    report = check_copper(design, pads=KicadBackend().board_pads(design))
    (short,) = report.findings
    assert short.where == f"R1-2, {via.provenance.locator}"
    assert [item.kind for item in short.items] == ["pad", "via"]
    assert "(10.8, 10) mm" in short.message
    assert report.issues[0].where == short.where


def test_same_bytes() -> None:
    def dump() -> str:
        made = Copper()
        made.netclass("Default", mm(0.2))
        for n in range(6):
            made.track(f"N{n % 3}", Point(0, n * mm(0.3)), Point(mm(4), n * mm(0.3)))
        made.via("V", Point(mm(2), mm(0.4)))
        made.zone("GND", ZONE_A)
        made.zone("VIN", ZONE_B)
        report = check_copper(made.build(), pads=None)
        assert len(report.findings) > 4
        return json.dumps(dataclasses.asdict(report), sort_keys=True, default=str)

    assert dump() == dump()


def test_findings_and_issues_are_sorted() -> None:
    made = Copper()
    made.netclass("Default", mm(0.2))
    for n in range(8):
        made.track(f"N{n}", Point(0, n * mm(0.35)), Point(mm(4), n * mm(0.35)), locator=f"segment[{7 - n}]")
    made.via("V", Point(mm(2), mm(0.4)), locator="via[0]")
    report = check_copper(made.build(), pads=None)
    keys = [(f.code, f.where, f.message) for f in report.findings]
    assert keys == sorted(keys) and len({f.code for f in report.findings}) == 2
    issue_keys = [(i.code, i.where, i.message) for i in report.issues]
    assert issue_keys == sorted(issue_keys)
    assert list(report.summary) == sorted(report.summary)
    assert set(report.summary) == {
        "approximated",
        "arc_tol",
        "clearance",
        "items",
        "judged",
        "layers",
        "max_clearance",
        "pairs",
        "shorts",
        "unset_pairs",
        "unsupported",
        "zone_overlaps",
    }


def test_brute_force_agreement() -> None:
    """Scenario "Index agrees with brute force": 300 generated tracks and vias on two layers and four nets
    with a 0.2 mm class clearance."""
    rng = random.Random(29)
    made = Copper()
    made.netclass("Default", mm(0.2))
    span = mm(12)
    for n in range(300):
        net = f"N{rng.randrange(4)}"
        at = Point(rng.randrange(span), rng.randrange(span))
        if n % 3 == 0:
            made.via(net, at, locator=f"via[{n}]")
        else:
            end = Point(at.x + rng.randint(-mm(2), mm(2)), at.y + rng.randint(-mm(2), mm(2)))
            made.track(net, at, end, layer=rng.choice(("F.Cu", "B.Cu")), locator=f"segment[{n}]")
    design = made.build()
    indexed = check_copper(design, pads=None)
    every = copper_module._run(  # pyright: ignore[reportPrivateUsage]
        design,
        pads=None,
        min_clearance=None,
        rules_over_classes=True,
        floor_over_rules=False,
        arc_tol=ARC_TOL_NM,
        inputs=(),
        every_pair=True,
    )
    assert indexed.findings == every.findings
    assert indexed.summary["shorts"] > 20 and indexed.summary["clearance"] > 20  # type: ignore[operator]
    assert indexed.summary["pairs"] < every.summary["pairs"]  # type: ignore[operator]


# --- the re-net benches, evidence and purity ------------------------------------------------------


def test_renet_bench_is_flagged() -> None:
    """Scenario "Fenolite flags the bench": the copper that KiCad loads on one net is a short here."""
    bench = renet_bench("dangling")
    (short,) = check_copper(bench.design, pads=None).findings
    assert (short.code, short.layer) == ("copper.short", "F.Cu")
    assert sorted(item.kind for item in short.items) == ["track", "via"]
    assert {item.net for item in short.items} == {"GND", "VIN"}


@pytest.mark.parametrize("name", ["padded", "tied", "anchored"])
def test_renet_bench_variants_are_flagged(name: str) -> None:
    bench = renet_bench(name)
    report = check_copper(bench.design, pads=KicadBackend().board_pads(bench.design))
    shorts = [f for f in report.findings if f.code == "copper.short"]
    assert len(shorts) == 1 and {item.kind for item in shorts[0].items} == {"track", "via"}


def test_evidence_constant() -> None:
    assert EVIDENCE.level is Level.INFERRED
    assert EVIDENCE.hypotheses == ("H-K-COPPER-SHAPES", "H-K-COPPER-RESOLVE", "H-K-COPPER-ZONES")


def test_evidence_combines_the_inputs() -> None:
    design = touching().build()
    read = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",))
    verified = Evidence(Level.KICAD_VERIFIED, oracle="kicad-cli 10.0.6")
    report = check_copper(design, pads=None, inputs=(read, verified))
    assert report.evidence.level is Level.INFERRED
    assert set(report.evidence.hypotheses) == {*EVIDENCE.hypotheses, "H-K-PCB-READ"}
    assert check_copper(design, pads=None, inputs=(Evidence(),)).evidence.level is Level.UNVERIFIED
    assert check_copper(design, pads=None, inputs=(verified,)).evidence.level is Level.INFERRED


def test_unsupported_item_lowers_the_level() -> None:
    design = design_of(Part("R1", "Mini_R_0603", 10, 10, nets={"1": "A"}))
    assert check_copper(design, pads=None).evidence.level is Level.UNVERIFIED
    assert check_copper(design, pads=KicadBackend().board_pads(design)).evidence.level is Level.INFERRED


def test_pure_and_repeatable(monkeypatch: pytest.MonkeyPatch) -> None:
    design = read_board(TWO_LAYER)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("check_copper reads no file and runs no tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(builtins, "open", refuse)
    first = check_copper(design, pads=None)
    second = check_copper(design, pads=None)
    monkeypatch.undo()
    assert first == second and first.summary["items"]
