# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium backend as a board frame and as a rules source for the copper check (capability
altium-verification, "Board frame of an imported board" and "Clearance rules of a PCB document"; change
c0088). The boards are the committed samples and models authored here."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.altium import frame
from fenolite.backends.altium.backend import UNIT_SLACK_NM, AltiumBackend
from fenolite.backends.altium.frame import corner_radius, shape_entries
from fenolite.backends.base import BoardFrame, DesignRulesSource, DocumentParity, ProjectSet
from fenolite.core.coords import Point, Size
from fenolite.core.evidence import Level
from fenolite.model.base import ExtBag
from fenolite.model.board import Board, FootprintInstance, Layer, Pad, Padstack, PadstackLayer
from fenolite.model.circuit import Circuit, Component, Net
from fenolite.model.design import Design

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "altium"
MM = 1_000_000


def sample(name: str) -> tuple[Design, ProjectSet]:
    path = SAMPLES / name / f"{name}.PcbDoc"
    design = AltiumBackend().read(path).design
    assert isinstance(design, Design)
    return design, ProjectSet(path.parent, path.name, {path.name: path})


def layers(*names: str) -> tuple[Layer, ...]:
    return tuple(
        Layer(id=f"lyr_{index}", name=name, kind="copper", ordinal=index) for index, name in enumerate(names)
    )


ORIGIN = Point(0, 0)


def one_pad(pad: Pad, *, at: Point = ORIGIN, rotation: int = 0, side: str = "top") -> Design:
    footprint = FootprintInstance(
        id="fp_1",
        component_id="cmp_1",
        lib_ref="L:F",
        position=at,
        rotation=rotation,
        side=side,  # type: ignore[arg-type]
        pads=(pad,),
    )
    board = Board(id="brd_1", layers=layers("F.Cu", "In1.Cu", "B.Cu"), footprints=(footprint,))
    circuit = Circuit(
        components=(Component(id="cmp_1", ref="U1", path="top/U1"),), nets=(Net(id="net_a", name="A"),)
    )
    return dataclasses.replace(Design.new("pcb", seed=1), circuit=circuit, board=board)


def pad(shape: str = "rect", w: int = 2 * MM, h: int = MM, **more: object) -> Pad:
    values: dict[str, object] = {"position": Point(MM, 0), "layers": ("F.Cu",), "net_id": "net_a"} | more
    return Pad(id="pad_1", number="1", shape=shape, size=Size(w, h), **values)  # type: ignore[arg-type]


def test_backend_is_a_frame_a_rules_source_and_a_document_parity() -> None:
    backend = AltiumBackend()
    assert isinstance(backend, BoardFrame) and isinstance(backend, DesignRulesSource)
    assert isinstance(backend, DocumentParity)
    assert backend.capabilities().operations == ("detect", "read")
    assert frame.EVIDENCE.level is Level.INFERRED and "H-A-IMP-FRAME" in frame.EVIDENCE.hypotheses


def test_frame_module_is_pure() -> None:
    """The frame imports the neutral layers, the import's evidence and nothing else of the project: no
    other backend, no check, and no file, process or environment access."""
    import ast

    tree = ast.parse(Path(frame.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "exec", "eval", "__import__"}
    project = {name for name in imported if name.startswith("fenolite")}
    assert project <= {
        "fenolite.backends.altium.import_evidence",
        "fenolite.backends.base",
        "fenolite.core.coords",
        "fenolite.core.errors",
        "fenolite.core.evidence",
        "fenolite.core.units",
        "fenolite.geometry",
        "fenolite.model.board",
        "fenolite.model.design",
    }
    assert imported - project <= {"__future__", "collections.abc", "fractions"}


def test_frame_of_the_routed_sample() -> None:
    design, _ = sample("routed")
    pads = AltiumBackend().board_pads(design)
    assert len(pads) == 36 and {p.ref for p in pads} == {"D1", "R1", "U1"}
    assert all(entry.exact for p in pads for entry in p.copper)
    hole = [p for p in pads if p.kind == "thru_hole"]
    assert len(hole) == 2 and all(p.side == "bottom" and p.drill and len(p.hole) == 1 for p in hole)
    # a through-hole pad has copper on the four copper layers, a surface pad on its own
    assert all([e.layer for e in p.copper] == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"] for p in hole)
    smd = [p for p in pads if p.kind == "smd"]
    assert all([e.layer for e in p.copper] == ["F.Cu"] and p.hole == () for p in smd)
    nets = {p.net for p in pads if p.net}
    assert nets == {"GND", "LED_A", "LED_DRV", "VIN"}
    # the pad lies where the import put it: the footprint's place plus its turned own position
    by_id = {fp.id: fp for fp in design.board.footprints}  # type: ignore[union-attr]
    for record in pads:
        footprint = by_id[record.footprint_id]
        own = next(p for p in footprint.pads if p.id == record.pad_id)
        assert record.rotation == (own.rotation + footprint.rotation) % 360_000_000
        if footprint.rotation == 0:
            assert record.position == Point(
                footprint.position.x + own.position.x, footprint.position.y + own.position.y
            )


def test_frame_places_and_turns_a_pad() -> None:
    backend = AltiumBackend()
    (straight,) = backend.board_pads(one_pad(pad(), at=Point(10 * MM, 20 * MM)))
    assert straight.position == Point(11 * MM, 20 * MM) and straight.rotation == 0
    (entry,) = straight.copper
    assert entry.filled and entry.width == 0 and entry.exact
    assert sorted(entry.core) == [
        Point(10 * MM, 19_500_000),
        Point(10 * MM, 20_500_000),
        Point(12 * MM, 19_500_000),
        Point(12 * MM, 20_500_000),
    ]
    assert (straight.ref, straight.path, straight.net, straight.number) == ("U1", "top/U1", "A", "1")
    # a quarter turn of the footprint: the pad's own place turns with it, and so does its shape
    (turned,) = backend.board_pads(one_pad(pad(), at=Point(10 * MM, 20 * MM), rotation=90_000_000))
    assert turned.position == Point(10 * MM, 19 * MM) and turned.rotation == 90_000_000
    xs = sorted({p.x for p in turned.copper[0].core})
    ys = sorted({p.y for p in turned.copper[0].core})
    assert xs == [9_500_000, 10_500_000] and ys == [18 * MM, 20 * MM]
    # no mirror on the bottom side: the import stores a bottom pad as it lies
    (bottom,) = backend.board_pads(one_pad(pad(layers=("B.Cu",)), at=Point(10 * MM, 20 * MM), side="bottom"))
    assert bottom.position == Point(11 * MM, 20 * MM) and bottom.side == "bottom"
    assert [e.layer for e in bottom.copper] == ["B.Cu"]


def test_frame_shapes() -> None:
    zero = (0, 0)
    assert shape_entries("circle", Size(MM, MM), None) == [((zero,), MM, False, True)]
    assert shape_entries("oval", Size(MM, MM), None) == [((zero,), MM, False, True)]
    (oval,) = shape_entries("oval", Size(3 * MM, MM), None)
    assert oval[0] == ((-MM, 0), (MM, 0)) and oval[1:] == (MM, False, True)
    (tall,) = shape_entries("oval", Size(MM, 3 * MM), None)
    assert tall[0] == ((0, -MM), (0, MM))
    (rect,) = shape_entries("rect", Size(2 * MM, MM), None)
    assert rect[1:] == (0, True, True) and len(rect[0]) == 4
    # a rounded rectangle: its corner percentage is the share of half the shorter side
    assert corner_radius(Size(2 * MM, MM), 50) == 250_000 and corner_radius(Size(2 * MM, MM), 100) == 500_000
    assert corner_radius(Size(2 * MM, MM), 250) == 500_000 and corner_radius(Size(2 * MM, MM), 0) == 0
    (rounded,) = shape_entries("roundrect", Size(2 * MM, MM), 50)
    assert rounded[1:] == (500_000, True, True)
    assert sorted(rounded[0])[0] == (-750_000, -250_000)
    (stadium,) = shape_entries("roundrect", Size(2 * MM, MM), 100)
    assert stadium[0] == ((-500_000, 0), (500_000, 0)) and stadium[1:] == (MM, False, True)
    (square,) = shape_entries("roundrect", Size(2 * MM, MM), 0)
    assert square[1:] == (0, True, True)
    (disc,) = shape_entries("roundrect", Size(MM, MM), 100)
    assert disc == ((zero,), MM, False, True)
    # what the import does not resolve is the rectangle of its size, which contains it, and says so
    for shape, percent in (("custom", None), ("roundrect", None), ("trapezoid", None)):
        (box,) = shape_entries(shape, Size(2 * MM, MM), percent)  # type: ignore[arg-type]
        assert box[1:] == (0, True, False)
    (wide,) = shape_entries("circle", Size(2 * MM, MM), None)
    assert wide == ((zero,), 2 * MM, False, False)
    assert shape_entries("rect", Size(0, MM), None) == []


def test_frame_reads_the_corner_percentage_and_the_stack() -> None:
    backend = AltiumBackend()
    rounded = pad("roundrect", ext={"altium": ExtBag(payload=(("corner_percent", "50"),))})
    (record,) = backend.board_pads(one_pad(rounded))
    assert record.copper[0].width == 500_000 and record.copper[0].exact
    (unknown,) = backend.board_pads(one_pad(pad("roundrect")))
    assert unknown.copper[0].width == 0 and not unknown.copper[0].exact
    stack = Padstack(
        id="pst_1",
        layers=(
            PadstackLayer("F.Cu", "circle", Size(2 * MM, 2 * MM)),
            PadstackLayer("In1.Cu", "rect", Size(MM, MM), Point(0, 500_000)),
            PadstackLayer("B.Cu", "roundrect", Size(2 * MM, MM)),
        ),
        hole_shape="slot",
        hole_length=2 * MM,
        hole_rotation=90_000_000,
    )
    holed = pad(
        "circle",
        2 * MM,
        2 * MM,
        layers=("F.Cu", "In1.Cu", "B.Cu", "F.Mask"),
        drill=MM,
        kind="thru_hole",
        padstack=stack,
    )
    (record,) = backend.board_pads(one_pad(holed))
    top, inner, bottom = record.copper
    assert (top.layer, top.core, top.width) == ("F.Cu", (Point(MM, 0),), 2 * MM)
    assert inner.layer == "In1.Cu" and {p.y for p in inner.core} == {0, MM}  # moved by its offset
    assert bottom.layer == "B.Cu" and not bottom.exact  # no corner percentage of a per-layer shape
    assert record.drill == MM and record.hole == (Point(MM, -500_000), Point(MM, 500_000))
    # a non-plated hole has no copper; a pad on no copper layer of the board has none either
    (bare,) = backend.board_pads(one_pad(pad(kind="np_thru_hole", drill=MM)))
    assert bare.copper == () and bare.hole == (Point(MM, 0),)
    (paste,) = backend.board_pads(one_pad(pad(layers=("F.Paste",))))
    assert paste.copper == () and paste.hole == ()


def test_frame_extents_are_the_hull_of_the_pads() -> None:
    design, _ = sample("blink")
    extents = AltiumBackend().placed_extents(design)
    assert len(extents) == 3 and all(extent.source == "pads" and not extent.exact for extent in extents)
    for extent in extents:
        assert len(extent.own) == 1 and len(extent.own[0]) >= 3
        assert (extent.front == ()) == (extent.side == "bottom")
    (none,) = AltiumBackend().placed_extents(one_pad(pad(layers=("F.Paste",))))
    assert none.source == "none" and none.own == () and none.exact


def test_rules_source_of_a_built_sample() -> None:
    design, project = sample("routed")
    rules = AltiumBackend().design_rules(design, project)
    assert rules.min_clearance is None and rules.rules_over_classes and not rules.floor_over_rules
    assert rules.opaque_clearance_rules == 0 and rules.unread == () and rules.left_out == ()
    assert rules.evidence.level is Level.INFERRED
    # a polygon has no clearance of its own, and the clearance rules carry the slack of the unit
    assert design.board is not None and rules.design.board is not None
    assert {zone.settings.clearance for zone in design.board.zones} == {500_000}
    assert {zone.settings.clearance for zone in rules.design.board.zones} == {0}
    read = {rule.name: rule.min for rule in design.rules.rules if rule.kind == "clearance"}  # type: ignore[union-attr]
    held = {rule.name: rule.min for rule in rules.design.rules.rules if rule.kind == "clearance"}  # type: ignore[union-attr]
    assert read == {"Clearance": 200_000, "Clearance_PWR": 200_000}
    assert held == {name: value - UNIT_SLACK_NM for name, value in read.items()}
    other = [rule for rule in rules.design.rules.rules if rule.kind != "clearance"]  # type: ignore[union-attr]
    assert other == [rule for rule in design.rules.rules if rule.kind != "clearance"]  # type: ignore[union-attr]
    assert rules.design.board.tracks == design.board.tracks


def test_rules_source_counts_the_clearance_rules_that_stay_opaque() -> None:
    from fenolite.backends.altium.read.pcb import read_rule_fields
    from fenolite.backends.altium.read.rules import map_rules

    design, project = sample("blink")
    data = (project.root / project.board).read_bytes()
    fields = read_rule_fields(data, file=project.board)
    assert len(fields) == 5 and [dict(f)["RULEKIND"] for f in fields].count("Clearance") == 2
    assert map_rules(fields, origin="x").unmapped == ()
    assert read_rule_fields(data) == fields
    # a missing document is named, never raised
    missing = ProjectSet(project.root, "gone.PcbDoc", {"gone.PcbDoc": project.root / "gone.PcbDoc"})
    rules = AltiumBackend().design_rules(design, missing)
    assert rules.unread == (("gone.PcbDoc", "FileNotFoundError"),) and rules.opaque_clearance_rules == 0
    # bytes that are no PCB document are named too
    broken = AltiumBackend().rules_from_bytes(design, b"not a compound file", file="x.PcbDoc")
    assert [name for name, _ in broken.unread] == ["x.PcbDoc"] and broken.unread[0][1]


def test_rules_source_counts_opaque_and_skips_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """An enabled ``Clearance`` record outside the table counts; a disabled one does not apply."""
    from fenolite.backends.altium.read import pcb as pcb_reader

    design, project = sample("blink")
    real = pcb_reader.read_rule_fields((project.root / project.board).read_bytes(), file=project.board)
    clearance = next(fields for fields in real if dict(fields)["RULEKIND"] == "Clearance")
    odd = (*clearance, ("AUTHOREDKEY", "1"))
    off = tuple(("ENABLED", "FALSE") if key == "ENABLED" else (key, value) for key, value in clearance)
    monkeypatch.setattr(pcb_reader, "read_rule_fields", lambda data, file="": (*real, odd, odd, off))
    rules = AltiumBackend().design_rules(design, project)
    assert rules.opaque_clearance_rules == 2


def _imported(chain: tuple[int, ...], tracks: list[object], **extra: str) -> Design:
    import _altium_records as rec

    from fenolite.backends.altium.adapter import import_board

    document = rec.document(rec.board(chain, extra=extra), nets=["GND"], tracks=tracks)  # type: ignore[arg-type]
    return import_board(document, file="x.PcbDoc", sha256=rec.SHA)


def test_rules_source_names_the_planes_and_takes_nothing_out() -> None:
    """Scenario "Planes of an imported board" (change c0124): the import made no copper of the lines on
    the plane, so the rules source holds every track it was given and says what the plane hides."""
    import _altium_records as rec

    line = ((0, 0), (500 * rec.MIL, 0))
    tracks = [rec.track(*line, layer=39), rec.track(*line, layer=39), rec.track(*line, layer=1, net=0)]
    design = _imported((1, 39, 32), tracks, PLANE1NETNAME="GND")
    assert design.board is not None and [t.layer for t in design.board.tracks] == ["F.Cu"]
    rules = AltiumBackend().rules_from_bytes(design, None, file="x.PcbDoc", unread="not given")
    assert rules.design.board is not None and rules.design.board.tracks == design.board.tracks
    ((kind, count, reason),) = rules.left_out
    assert (kind, count) == ("plane", 1) and "the 2 object(s)" in reason and "negative" in reason
    assert rules.unread == (("x.PcbDoc", "not given"),)
    # a plane on no net is a plane, and one that nothing cuts is named too
    bare = _imported((1, 39, 40, 32), tracks[2:])
    ((kind, count, reason),) = AltiumBackend().rules_from_bytes(bare, None, file="x", unread="-").left_out
    assert (kind, count) == ("plane", 2) and "the 0 object(s)" in reason
    # a mid layer is no plane: without a plane nothing is left out
    signal = _imported((1, 2, 3, 32), [rec.track(*line, layer=2)])
    assert AltiumBackend().rules_from_bytes(signal, None, file="x", unread="-").left_out == ()


def test_rules_source_does_not_filter_a_model_it_is_given() -> None:
    """The view is no second importer: a track without a net on an inner layer of a model that did not
    come from the import stays, and a layer without the import's bag is no plane."""
    from fenolite.model.board import Track

    design = one_pad(pad())
    assert design.board is not None
    track = Track(id="trk_1", start=Point(0, 0), end=Point(MM, 0), width=200_000, layer="In1.Cu", net_id=None)
    given = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=(track,)))
    rules = AltiumBackend().rules_from_bytes(given, None, file="x", unread="-")
    assert rules.design.board is not None and rules.design.board.tracks == (track,)
    assert rules.left_out == ()


def test_plane_of_a_stage_is_reported_as_copper_not_judged() -> None:
    """The copper stage of a document check on an imported board with a plane: one
    ``copper.item-unsupported`` (``where`` = ``plane``), no short from the lines that cut the plane, and
    the level ``UNVERIFIED`` (capability altium-verification, "Copper check on Altium boards")."""
    import _altium_records as rec

    from fenolite.checks.copper import check_copper, rules_issues

    # a via of GND stands on the line that cuts the plane: copper against a void is no short
    line = ((0, 0), (500 * rec.MIL, 0))
    document = rec.document(
        rec.board((1, 39, 32), extra={"PLANE1NETNAME": "GND"}),
        nets=["GND"],
        tracks=[rec.track(*line, layer=39)],
        vias=[rec.via((250 * rec.MIL, 0), net=0)],
    )
    from fenolite.backends.altium.adapter import import_board

    design = import_board(document, file="x.PcbDoc", sha256=rec.SHA)
    rules = AltiumBackend().rules_from_bytes(design, None, file="x.PcbDoc", unread="not given")
    report = check_copper(rules.design, pads=AltiumBackend().board_pads(rules.design))
    assert not [f for f in report.findings if f.code == "copper.short"]
    (left,) = [i for i in rules_issues(rules) if i.code == "copper.item-unsupported"]
    assert left.where == "plane" and left.severity == "warning" and left.message.startswith("1 plane item(s)")
