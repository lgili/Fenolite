# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated copper (change c0224; capability design-dsl, "Generated copper calls" and the requirements
after it): what a script records, what is refused at the call, and what the KiCad build makes of it on
the blink, measured exactly."""

from __future__ import annotations

import dataclasses
import io
import json
from pathlib import Path

import pytest
from _buildhelp import blink, blink_variant, build

import fenolite.cli.main as cli_main
import fenolite.dsl as dsl
from fenolite.backends.kicad import boarditems
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.frame import board_pads, placed_extents
from fenolite.core.coords import Point
from fenolite.dsl import BOARD_ORIGIN, DslError, Part, mm
from fenolite.dsl.generate import (
    BandIntent,
    BarrierIntent,
    BodyKeepoutIntent,
    FanoutZoneIntent,
    RingIntent,
    StitchPiecesIntent,
    generated,
)
from fenolite.geometry import (
    Location,
    Polygon,
    Thick,
    dist2_point_segment,
    point_in_ring,
    thick_closer_than,
    thick_touch,
)
from fenolite.lens.build import BuildOutput
from fenolite.model.board import Keepout, Zone

MM = 1_000_000


def _at(x: float, y: float) -> Point:
    return Point(BOARD_ORIGIN.x + round(x * MM), BOARD_ORIGIN.y + round(y * MM))


# --- what a script records --------------------------------------------------------------------------


def test_record_every_call_in_key_order() -> None:
    design = blink()
    vin, gnd = design.nets["VIN"], design.nets["GND"]
    h1 = design.hole("H1", mm(4), mm(4), drill=mm(3))
    r1 = design.parts["R1"]
    design.band(vin, ((mm(26), mm(24.5)), (mm(46), mm(24.5))), width=mm(3), layers=("B.Cu",))
    design.keepout_ring(h1, setback=mm(2), sides=16)
    design.barrier("PWR", setback=mm(1), pieces=True)
    design.body_keepout(r1, setback=mm(0.5), layers=("B.Cu",), forbid=("tracks",))
    design.fanout_zone(gnd, refs=(design.parts["U1"],), diameter=mm(0.6), drill=mm(0.3))
    design.stitch_pieces(gnd, pitch=mm(2))
    found = generated(design)
    assert [intent.key for intent in found] == [
        "band.VIN", "barrier.PWR", "body_keepout.R1", "fanout_zone.GND", "keepout_ring.H1",
        "stitch_pieces.GND",
    ]  # fmt: skip
    band, barrier, body, fanout, ring, stitch = found
    assert band == BandIntent(
        "VIN", "VIN", (_at(26, 24.5), _at(46, 24.5)), 3 * MM, 3 * MM, 1_500_000, ("B.Cu",)
    )
    assert barrier == BarrierIntent("PWR", "PWR", MM, ("F.Cu", "B.Cu"), ("tracks", "vias", "pours"), True)
    assert body == BodyKeepoutIntent("R1", "R1", 500_000, ("B.Cu",), ("tracks",))
    assert fanout == FanoutZoneIntent("GND", "GND", "top", ("U1",), None, 600_000, 300_000)
    assert ring == RingIntent("H1", "H1", 2 * MM, ("F.Cu", "B.Cu"), ("tracks", "vias", "pours"), 16)
    assert stitch == StitchPiecesIntent("GND", "GND", 2 * MM, ("F.Cu", "B.Cu"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        band.width = 1  # type: ignore[misc]
    assert "generated" in dsl.__all__ and dsl.generated is generated


def test_record_band_levels() -> None:
    design = blink()
    vin = design.nets["VIN"]
    spine = ((mm(26), mm(24.5)), (mm(46), mm(24.5)), (mm(46), mm(12)))
    design.band(vin, spine, width=mm(3), max_width=mm(6), step=mm(0.5), layers=("B.Cu",), clearance=mm(1))
    (band,) = generated(design)
    assert isinstance(band, BandIntent)
    assert (band.width, band.max_width, band.step, band.clearance) == (3 * MM, 6 * MM, MM // 2, MM)
    other = blink()
    other.band(other.nets["VIN"], spine, width=mm(3), max_width=mm(6), layers=("B.Cu",))
    (default,) = generated(other)
    assert isinstance(default, BandIntent) and default.step == 1_500_000


@pytest.mark.parametrize(
    ("spine", "match"),
    [
        (((mm(1), mm(1)), (mm(5), mm(5))), "horizontal or vertical"),
        (((mm(1), mm(1)),), "at least two"),
        (((mm(1), mm(1)), (mm(5), mm(1)), (mm(2), mm(1))), "turns back"),
        (((mm(1), mm(1)), (mm(1), mm(1))), "not empty"),
    ],
)
def test_record_refuses_a_spine(spine: object, match: str) -> None:
    design = blink()
    with pytest.raises(DslError, match=match):
        design.band(design.nets["VIN"], spine, width=mm(3), layers=("B.Cu",))  # type: ignore[arg-type]


def test_record_refuses_wrong_arguments() -> None:
    design = blink()
    vin, gnd = design.nets["VIN"], design.nets["GND"]
    h1 = design.hole("H1", mm(4), mm(4), drill=mm(3))
    spine = ((mm(26), mm(24.5)), (mm(46), mm(24.5)))
    with pytest.raises(DslError, match="max_width must be at least width"):
        design.band(vin, spine, width=mm(3), max_width=mm(2), layers=("B.Cu",))
    with pytest.raises(DslError, match="shorter than max_width"):
        design.band(
            vin, ((mm(26), mm(24.5)), (mm(29), mm(24.5))), width=mm(3), max_width=mm(4), layers=("B.Cu",)
        )
    with pytest.raises(DslError, match="step must be at most"):
        design.band(vin, spine, width=mm(3), max_width=mm(4), step=mm(1), layers=("B.Cu",))
    with pytest.raises(DslError, match="not a copper layer"):
        design.band(vin, spine, width=mm(3), layers=("In1.Cu",))
    with pytest.raises(DslError, match="forbid: 'zones' is not one of"):
        design.keepout_ring(h1, setback=mm(2), forbid=("zones",))
    with pytest.raises(DslError, match="sides must divide"):
        design.keepout_ring(h1, setback=mm(2), sides=7_000)
    with pytest.raises(DslError, match="at least 8"):
        design.keepout_ring(h1, setback=mm(2), sides=6)
    with pytest.raises(DslError, match="give a Part"):
        design.body_keepout("R1", setback=mm(1))  # type: ignore[arg-type]
    with pytest.raises(DslError, match="side must be one of"):
        design.fanout_zone(gnd, side="left")
    with pytest.raises(DslError, match="drill must be smaller"):
        design.fanout_zone(gnd, diameter=mm(0.3), drill=mm(0.3))
    with pytest.raises(DslError, match="at least two copper layers"):
        design.stitch_pieces(gnd, pitch=mm(2), layers=("B.Cu",))
    with pytest.raises(DslError, match="pieces must be a bool"):
        design.barrier("PWR", setback=mm(1), pieces="yes")  # type: ignore[arg-type]
    design.keepout_ring(h1, setback=mm(2))
    with pytest.raises(DslError, match="already used"):
        design.keepout_ring(h1, setback=mm(3))
    design.keepout_ring(h1, setback=mm(3), name="H1-wide")
    with pytest.raises(DslError, match="must match"):
        design.barrier("HV class", setback=mm(1))
    assert [intent.key for intent in generated(design)] == ["keepout_ring.H1", "keepout_ring.H1-wide"]


def test_record_needs_a_board_and_parts_of_the_design() -> None:
    design = dsl.Design("bare")
    with pytest.raises(DslError, match="call board"):
        design.barrier("PWR", setback=mm(1))
    design = blink()
    stranger = Part("R9", "Mini:Mini_R", footprint="Mini:Mini_R_0603")
    design.body_keepout(stranger, setback=mm(1))
    with pytest.raises(DslError, match="R9 is not in the design"):
        generated(design)


# --- what the build makes of it -----------------------------------------------------------------------


def _build(design: dsl.Design) -> BuildOutput:
    """``build_design`` of ``design`` with its copper and generated records and the definitions it
    authored (the holes)."""
    return build(
        design,
        generated_copper=generated(design),
        copper_intents=dsl.copper(design),
        authored_footprints={key: fp.definition for key, fp in design.footprints.items()},
        authored_symbols={key: symbol.definition for key, symbol in design.symbols.items()},  # type: ignore[attr-defined]
    )


def _areas(output: BuildOutput, prefix: str) -> list[Keepout]:
    board = output.design.board
    assert board is not None
    return [area for area in board.keepouts if area.name.startswith(prefix)]


def _errors(output: BuildOutput) -> list[str]:
    return [found.code for found in output.issues if found.severity == "error"]


def _named(output: BuildOutput, prefix: str) -> list[Zone]:
    board = output.design.board
    assert board is not None
    return [zone for zone in board.zones if zone.name.startswith(prefix)]


def _octilinear(ring: tuple[Point, ...]) -> bool:
    edges = zip(ring, (*ring[1:], ring[0]), strict=True)
    return all(a.x == b.x or a.y == b.y or abs(a.x - b.x) == abs(a.y - b.y) for a, b in edges)


def _other_copper(output: BuildOutput, net: str, layer: str) -> list[Thick]:
    return [
        Thick(entry.core, entry.width, entry.filled)
        for pad in board_pads(output.design)
        if pad.net != net
        for entry in pad.copper
        if entry.layer == layer
    ]


SPINE = ((mm(26), mm(24.5)), (mm(46), mm(24.5)), (mm(46), mm(12)))
"""A spine on the bottom of the blink, 3.6 mm from the pads of ``D1``, turning up at its right end."""


def test_band_keeps_its_clearance() -> None:
    """Scenario "A band keeps its clearance"."""
    design = blink()
    vin = design.nets["VIN"]
    design.band(vin, SPINE, width=mm(3), max_width=mm(6), step=mm(0.5), layers=("B.Cu",), clearance=mm(1))
    output = _build(design)
    assert _errors(output) == [] and output.files
    (zone,) = _named(output, "band.")
    assert (
        zone.name == "band.VIN" and zone.locked and zone.layers == ("B.Cu",) and zone.settings.clearance == MM
    )
    others = _other_copper(output, "VIN", "B.Cu")
    shape = Thick(zone.outline, 0, filled=True)
    assert others and not any(thick_closer_than(shape, other, MM) for other in others)
    assert _octilinear(zone.outline) and Polygon(zone.outline).is_simple()
    points = {(p.x - BOARD_ORIGIN.x, p.y - BOARD_ORIGIN.y) for p in zone.outline}
    expected = {
        (36 * MM, 22 * MM), (42 * MM, 22 * MM),  # 2.5 mm on the side of D1, beside its pads
        (26_500_000, 21_500_000), (26_500_000, 27_500_000),  # 3 mm on both sides elsewhere
        (44 * MM, 21_500_000),  # the inside of the turn: one point
        (47_250_000, 27_500_000), (48 * MM, 26_750_000),  # the outside of the turn: a bevel
        (44 * MM, 12_500_000), (48 * MM, 12_500_000),  # the vertical run, shorter than five widths: 2 mm
    }  # fmt: skip
    assert expected <= points, sorted(points)
    assert output.summary["generated"] == {"records": 1, "zones": 1, "rule_areas": 0, "tracks": 0, "vias": 0}
    assert "H-K-GEN-DRC" in output.evidence.hypotheses
    text = output.files["blink.kicad_pcb"].decode("utf-8")
    assert text.count('(name "band.VIN")') == 1


def test_band_off_the_board_is_refused() -> None:
    design = blink()
    design.band(design.nets["VIN"], ((mm(26), mm(24.5)), (mm(56), mm(24.5))), width=mm(3), layers=("B.Cu",))
    output = _build(design)
    assert _errors(output) == ["kicad.generate.off-board"] and not output.files


def test_band_needs_a_clearance() -> None:
    design = blink()
    design.band(design.nets["LED_A"], SPINE, width=mm(1), layers=("B.Cu",))
    output = _build(design)
    assert _errors(output) == ["kicad.generate.size-missing"]


def test_band_that_crosses_itself_is_refused() -> None:
    design = blink()
    spine = ((mm(10), mm(5)), (mm(20), mm(5)), (mm(20), mm(9)), (mm(12), mm(9)), (mm(12), mm(3)))
    design.band(design.nets["VIN"], spine, width=mm(3), layers=("B.Cu",))
    assert _errors(_build(design)) == ["kicad.generate.crossing"]


def test_altium_target_refuses_generated_copper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``kicad.generate.altium``: the Altium target writes nothing for a script with a generated call."""
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    line = 'design.band(vin, ((mm(26), mm(24.5)), (mm(46), mm(24.5))), width=mm(3), layers=("B.Cu",))\n'
    script = blink_variant(tmp_path / "src", append="\n" + line)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    out = tmp_path / "out"
    arguments = ["build", str(script), "--out", str(out), "--target", "altium", "--dry-run", "--json"]
    code = cli_main.main(arguments)
    env = json.loads(stdout.getvalue() or "{}")
    refused = [found for found in env["issues"] if found["code"] == "kicad.generate.altium"]
    assert code != 0 and len(refused) == 1 and refused[0]["where"] == "band.VIN"
    assert not out.exists() or not any(out.iterdir())


def test_ring_holds_the_circle() -> None:
    """Scenario "A ring holds the circle"."""
    design = blink()
    h1 = design.hole("H1", mm(4), mm(4), drill=mm(3))
    design.keepout_ring(h1, setback=mm(2), sides=16)
    output = _build(design)
    assert _errors(output) == []
    (ring,) = _areas(output, "keepout_ring.")
    assert ring.name == "keepout_ring.H1" and len(ring.outline) == 16
    assert ring.layers == ("F.Cu", "B.Cu") and (ring.no_tracks, ring.no_vias, ring.no_copper_pour) == (
        True, True, True,
    )  # fmt: skip
    assert boarditems.is_item_uuid(ring.native_ids["kicad"])
    centre, radius = _at(4, 4), 3_500_000
    assert point_in_ring(centre, ring.outline) is Location.INSIDE and Polygon(ring.outline).is_convex()
    edges = zip(ring.outline, (*ring.outline[1:], ring.outline[0]), strict=True)
    assert all(dist2_point_segment(centre, a, b) >= radius * radius for a, b in edges)
    # tight: no vertex lies more than 3 % beyond the circle
    assert all(
        (p.x - centre.x) ** 2 + (p.y - centre.y) ** 2 < (radius * 103 // 100) ** 2 for p in ring.outline
    )


def test_ring_needs_a_hole() -> None:
    design = blink()
    design.keepout_ring(design.parts["R1"], setback=mm(1))
    assert _errors(_build(design)) == ["kicad.generate.no-hole"]


def _hv(design: dsl.Design) -> None:
    design.rules.netclass("HV", clearance=mm(0.5), nets=(design.nets["LED_A"],))


def test_barrier_in_pieces_is_refused() -> None:
    """Scenario "A barrier in pieces is refused": the copper of ``LED_A`` lies at ``R1`` and at ``D1``."""
    design = blink()
    _hv(design)
    design.barrier("HV", setback=mm(2))
    output = _build(design)
    assert _errors(output) == ["kicad.generate.pieces"] and not output.files
    (refused,) = [found for found in output.issues if found.code == "kicad.generate.pieces"]
    assert "pieces=True" in refused.hint and "2 pieces" in refused.message


def test_barrier_in_pieces_when_asked() -> None:
    design = blink()
    _hv(design)
    design.barrier("HV", setback=mm(2), pieces=True, layers=("F.Cu",), forbid=("tracks",))
    output = _build(design)
    assert _errors(output) == []
    areas = _areas(output, "barrier.")
    names = ["barrier.HV.0.a", "barrier.HV.0.b", "barrier.HV.1.a", "barrier.HV.1.b"]
    assert [area.name for area in areas] == names
    assert all(area.layers == ("F.Cu",) and area.no_tracks and not area.no_vias for area in areas)
    assert all(Polygon(area.outline).is_simple() for area in areas)
    own = [pad for pad in board_pads(output.design) if pad.net == "LED_A"]
    assert len(own) == 2
    for pad in own:  # the class's copper is inside the band, never under it
        assert all(point_in_ring(pad.position, area.outline) is Location.OUTSIDE for area in areas)
        beside = Point(pad.position.x, pad.position.y - 2 * MM)  # 2 mm away: inside the 2 mm band
        assert any(point_in_ring(beside, area.outline) is not Location.OUTSIDE for area in areas)
    # the pads of other nets beside R1 and D1 are named: a convex band closes around them
    enclosed = [found.message for found in output.issues if found.code == "kicad.generate.encloses"]
    assert len(enclosed) == 2 and any("R1-1" in text for text in enclosed)


def test_barrier_needs_a_class() -> None:
    design = blink()
    design.barrier("HV", setback=mm(2))
    assert _errors(_build(design)) == ["kicad.generate.unknown"]


def test_body_keepout_under_a_part() -> None:
    """Scenario "Keep-out under a part on the other side"."""
    design = blink()
    design.body_keepout(design.parts["R1"], setback=mm(0.5), layers=("B.Cu",))
    output = _build(design)
    assert _errors(output) == []
    (area,) = _areas(output, "body_keepout.")
    assert area.name == "body_keepout.R1" and area.layers == ("B.Cu",)
    assert Polygon(area.outline).is_convex()
    owned = {pad.footprint_id for pad in board_pads(output.design) if pad.ref == "R1"}
    (extent,) = [found for found in placed_extents(output.design) if found.footprint_id in owned]
    corners = [point for ring in extent.own for point in ring]
    assert corners
    for p in corners:
        for dx, dy in ((500_000, 0), (-500_000, 0), (0, 500_000), (0, -500_000)):
            assert point_in_ring(Point(p.x + dx, p.y + dy), area.outline) is not Location.OUTSIDE


def _pours(design: dsl.Design) -> None:
    """A ``GND`` pour over the bottom and one over a square of the top, clear of the parts."""
    gnd = design.nets["GND"]
    design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3))
    top = ((mm(20), mm(18)), (mm(30), mm(18)), (mm(30), mm(28)), (mm(20), mm(28)))
    design.zone(gnd, name="GND_TOP", layers=("F.Cu",), clearance=mm(0.3), outline=top)


def test_fanout_joins_a_pad_to_the_bottom_pour() -> None:
    """Scenario "A pad joined to the bottom pour"."""
    design = blink()
    _pours(design)
    design.fanout_zone(design.nets["GND"], width=mm(0.3), diameter=mm(0.6), drill=mm(0.3))
    output = _build(design)
    assert _errors(output) == []
    board = output.design.board
    assert board is not None
    (track,) = board.tracks
    (via,) = board.vias
    pads = board_pads(output.design)
    (own,) = [pad for pad in pads if pad.net == "GND" and pad.ref == "U1"]
    assert track.start == own.position and track.end == via.position and track.layer == "F.Cu"
    assert via.layers == ("F.Cu", "B.Cu") and via.diameter == 600_000
    assert via.native_ids["kicad"] == copper_uuid("fanout_zone.GND", "U1-10/via")
    assert track.native_ids["kicad"] == copper_uuid("fanout_zone.GND", "U1-10/track")
    disc_of_via = Thick((via.position,), via.diameter)
    for pad in pads:
        for entry in pad.copper:
            assert not thick_touch(disc_of_via, Thick(entry.core, entry.width, entry.filled)), pad.ref
    assert output.summary["generated"] == {"records": 1, "zones": 0, "rule_areas": 0, "tracks": 1, "vias": 1}


def test_fanout_needs_a_zone_and_sizes() -> None:
    design = blink()
    design.fanout_zone(design.nets["GND"], diameter=mm(0.6), drill=mm(0.3))
    assert _errors(_build(design)) == ["kicad.generate.no-zone"]
    design = blink()
    led_a = design.nets["LED_A"]
    design.zone(led_a, layers=("B.Cu",))
    design.fanout_zone(led_a)
    assert _errors(_build(design)) == ["kicad.generate.size-missing"]


def test_stitch_ties_two_pours() -> None:
    """Scenario "Two pours tied"."""
    design = blink()
    _pours(design)
    design.stitch_pieces(design.nets["GND"], pitch=mm(2), diameter=mm(0.6), drill=mm(0.3))
    output = _build(design)
    assert _errors(output) == []
    board = output.design.board
    assert board is not None
    top = next(zone for zone in board.zones if zone.name == "GND_TOP")
    assert len(board.vias) >= 2
    others = [shape for layer in ("F.Cu", "B.Cu") for shape in _other_copper(output, "GND", layer)]
    for via in board.vias:
        assert point_in_ring(via.position, top.outline) is Location.INSIDE
        shape = Thick((via.position,), via.diameter)
        assert not any(thick_closer_than(shape, other, 200_000) for other in others)
    assert not [found for found in output.issues if found.code == "kicad.generate.stitch-short"]


def test_stitch_short_and_without_pieces() -> None:
    design = blink()
    _pours(design)
    design.stitch_pieces(design.nets["GND"], pitch=mm(2), min_vias=100, diameter=mm(0.6), drill=mm(0.3))
    output = _build(design)
    short = [found for found in output.issues if found.code == "kicad.generate.stitch-short"]
    assert _errors(output) == [] and len(short) == 1 and "fewer than 100" in short[0].message
    design = blink()
    design.zone(design.nets["GND"], layers=("B.Cu",))
    design.stitch_pieces(design.nets["GND"], pitch=mm(2), diameter=mm(0.6), drill=mm(0.3))
    assert _errors(_build(design)) == ["kicad.generate.no-zone"]
