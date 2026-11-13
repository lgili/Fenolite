# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Arcs, fills, regions and polygons in an edit session, and the matching of an item (change c0452). The
documents are the kit board and copies of it with records authored here: a second track, a fill of the
46-byte saved form (its bytes after 37 zero, which no session writes itself), a poured region. Every gate
is opened by the test: ``edit.GATES`` stays off."""

from __future__ import annotations

import struct
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import integrity
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.ops import View
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.pcbrecords import prefix, to_units
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import FILL, ArcRecord, FillRecord, RegionRecord, TrackRecord
from tests.unit.backends.altium.edit.conftest import OPEN, mm
from tests.unit.backends.altium.edit.test_session import PROBE

MECH = "Mechanical 13"
BOX = edit.Region(MECH, (mm(30), mm(24)))
"""The kit's filled rectangle, (30, 2)–(36, 6) mm in ``place()``'s frame: its lower-left corner in the
document's frame."""
GND_NET = 0
Build = Callable[[edit.Session], object]


def _session(board: Path) -> edit.Session:
    session = edit.open(board, gates=OPEN)
    assert isinstance(session, edit.Session)
    return session


def _diff(before: bytes, after: bytes) -> dict[str, tuple[int, int]]:
    """Per storage, the records removed and added."""
    old, new = State.of(before), State.of(after)
    out: dict[str, tuple[int, int]] = {}
    for name in ("Arcs6", "Fills6", "Polygons6", "Regions6", "ShapeBasedRegions6", "Tracks6", "Vias6"):
        a = Counter(old.get(name) if old.has(name) else [])
        b = Counter(new.get(name) if new.has(name) else [])
        if a != b:
            out[name] = (sum((a - b).values()), sum((b - a).values()))
    return out


def _author(board: Path, change: Callable[[State, View], None]) -> bytes:
    """The kit board with records added by ``change``, written back to ``board``."""
    state = State.of(board.read_bytes())
    change(state, View(state))
    data = state.data()
    board.write_bytes(data)
    return data


def _track(state: State, view: View, ends: tuple[float, float, float, float], width: float) -> None:
    raw = _probe_raw(state)
    a, b = view.units((mm(ends[0]), mm(ends[1]))), view.units((mm(ends[2]), mm(ends[3])))
    state.append("Tracks6", rec.patch(raw, 13, "<5i", *a, *b, to_units(mm(width))))


def _probe_raw(state: State) -> bytes:
    view = View(state)
    a, b = view.units(PROBE.start), view.units(PROBE.end)
    for raw in state.get("Tracks6"):
        x1, y1, x2, y2 = struct.unpack_from("<4i", rec.split(raw)[1][0], 13)
        if (x1, y1, x2, y2) == (*a, *b):
            return raw
    raise AssertionError("no probe track")


def _commit(board: Path, out: Path, build: Callable[[edit.Session], object]) -> edit.Receipt:
    session = _session(board)
    build(session)
    return session.commit(out, backup=False)


def _free_regions(data: bytes) -> list[RegionRecord]:
    doc = read_pcbdoc(data)
    regions = [*doc.regions, *doc.shape_regions]
    return [r for r in regions if isinstance(r, RegionRecord) and r.prefix.polygon is None]


def _corner_mm(region: RegionRecord, origin: tuple[int, int]) -> tuple[float, float]:
    x = min(float(v.x) for v in region.outline) - origin[0]
    y = min(float(v.y) for v in region.outline) - origin[1]
    return round(x * 127 / 50 / 1e6, 3), round(y * 127 / 50 / 1e6, 3)


# --- 1: a region moves with its twin -----------------------------------------------------------------


def test_region_move_moves_its_twin(board: Path, tmp_path: Path) -> None:
    """Scenario "A free region moved with its twin" (gap 1: the twin was looked up after the replace)."""
    out = tmp_path / "moved.PcbDoc"
    receipt = _commit(board, out, lambda s: s.move(BOX, mm(1), 0))
    assert receipt.written and receipt.issues == (), receipt.issues
    data = out.read_bytes()
    assert _diff(board.read_bytes(), data) == {"Regions6": (1, 1), "ShapeBasedRegions6": (1, 1)}
    origin = View(State.of(data)).origin
    assert [_corner_mm(r, origin) for r in _free_regions(data)] == [(31.0, 24.0), (31.0, 24.0)]


def test_a_twin_a_little_off_is_still_found(board: Path, tmp_path: Path) -> None:
    """A twin whose vertices lie 100 units (0.25 µm) from the plain form's is the region's twin."""

    def shift_twin(state: State, view: View) -> None:
        (twin,) = state.get("ShapeBasedRegions6")
        state.replace("ShapeBasedRegions6", 0, rec.transform(twin, rec.shift(100, 0), shape_based=True))

    before = _author(board, shift_twin)
    out = tmp_path / "moved.PcbDoc"
    receipt = _commit(board, out, lambda s: s.move(BOX, mm(1), 0).delete(edit.Region(MECH, (mm(31), mm(24)))))
    assert receipt.written, receipt.issues
    assert _diff(before, out.read_bytes()) == {"Regions6": (1, 0), "ShapeBasedRegions6": (1, 0)}


# --- 5: tracks named by width and by the nearest record ----------------------------------------------


def test_coincident_tracks_of_two_widths_are_deleted_one_at_a_time(board: Path, tmp_path: Path) -> None:
    """Scenario "Coincident tracks of two widths deleted one at a time"."""
    before = _author(board, lambda s, v: _track(s, v, (10, 5, 20, 5), 0.5))
    refused = _commit(board, tmp_path / "never.PcbDoc", lambda s: s.delete(PROBE))
    assert not refused.written and refused.exit_code == 5
    [issue] = refused.issues
    assert issue.code == "altium.edit.assertion" and "2 records match" in issue.message
    out = tmp_path / "deleted.PcbDoc"
    wide = edit.Track(PROBE.start, PROBE.end, "GND", width=mm(0.5))
    receipt = _commit(board, out, lambda s: s.delete(wide))
    assert receipt.written, receipt.issues
    assert _diff(before, out.read_bytes()) == {"Tracks6": (1, 0)}
    widths = [t.width for t in read_pcbdoc(out.read_bytes()).tracks if isinstance(t, TrackRecord)]
    assert to_units(mm(0.5)) not in widths and to_units(mm(0.25)) in widths


def test_a_point_rounded_to_the_micrometre_names_the_nearest_track(board: Path, tmp_path: Path) -> None:
    """Scenario "A point rounded to the micrometre": tracks 0.0004 and 0.0019 mm off the stated ends."""

    def two(state: State, view: View) -> None:
        _track(state, view, (10.0004, 7.0004, 20.0004, 7.0004), 0.25)
        _track(state, view, (10.0019, 7.0019, 20.0019, 7.0019), 0.25)

    before = _author(board, two)
    out = tmp_path / "deleted.PcbDoc"
    stated = edit.Track((mm(10), mm(7)), (mm(20), mm(7)), "GND")
    receipt = _commit(board, out, lambda s: s.delete(stated).declare_connectivity("GND"))
    assert receipt.written, receipt.issues
    assert _diff(before, out.read_bytes()) == {"Tracks6": (1, 0)}
    view = View(State.of(out.read_bytes()))
    left = [
        t.x1 - view.origin[0]
        for t in read_pcbdoc(out.read_bytes()).tracks
        if isinstance(t, TrackRecord) and abs(t.y1 - view.origin[1] - to_units(mm(7))) < 1000
    ]
    assert left == [to_units(mm(10.0019))]


def test_a_record_beyond_reach_is_not_named(board: Path, tmp_path: Path) -> None:
    _author(board, lambda s, v: _track(s, v, (10.003, 7, 20.003, 7), 0.25))
    stated = edit.Track((mm(10), mm(7)), (mm(20), mm(7)), "GND")
    receipt = _commit(board, tmp_path / "never.PcbDoc", lambda s: s.delete(stated))
    [issue] = receipt.issues
    assert issue.code == "altium.edit.assertion" and "0 records match" in issue.message


# --- 2: arcs -----------------------------------------------------------------------------------------


ARC = edit.Arc((mm(30), mm(20)), mm(2), None, layer="Top Overlay")


def test_an_arc_is_created_moved_and_deleted(board: Path, tmp_path: Path) -> None:
    """Scenario "An arc created, moved and deleted": cloned from an arc of a component."""
    first, second, third = (tmp_path / f"{n}.PcbDoc" for n in ("added", "moved", "deleted"))
    receipt = _commit(board, first, lambda s: s.add_arc(ARC.centre, ARC.radius, 0, 90, width=mm(0.2),
                                                        layer="Top Overlay"))  # fmt: skip
    assert receipt.written and receipt.issues == (), receipt.issues
    assert _diff(board.read_bytes(), first.read_bytes()) == {"Arcs6": (0, 1)}
    view = View(State.of(first.read_bytes()))
    free = [
        a
        for a in read_pcbdoc(first.read_bytes()).arcs
        if isinstance(a, ArcRecord) and a.prefix.component is None
    ]
    [arc] = free
    assert (arc.cx, arc.cy) == view.units(ARC.centre) and arc.radius == to_units(ARC.radius)
    assert (arc.start_angle, arc.end_angle, arc.width) == (0.0, 90.0, to_units(mm(0.2)))
    assert arc.prefix.layer == 33 and arc.prefix.net is None and arc.sub_polygon == 0
    receipt = _commit(first, second, lambda s: s.move(ARC, mm(1), 0, expect={"width": mm(0.2)}))
    assert receipt.written, receipt.issues
    assert _diff(first.read_bytes(), second.read_bytes()) == {"Arcs6": (1, 1)}
    moved = edit.Arc((mm(31), mm(20)), mm(2), None, width=mm(0.2))
    receipt = _commit(second, third, lambda s: s.delete(moved))
    assert receipt.written, receipt.issues
    assert _diff(board.read_bytes(), third.read_bytes()) == {}
    assert integrity.check_pcbdoc(first.read_bytes()) == ()


def test_an_arc_width_is_set_at_the_arc_offset(board: Path, tmp_path: Path) -> None:
    first, second = tmp_path / "added.PcbDoc", tmp_path / "wider.PcbDoc"
    _commit(
        board, first, lambda s: s.add_arc(ARC.centre, ARC.radius, 0, 90, width=mm(0.2), layer="Top Overlay")
    )
    receipt = _commit(first, second, lambda s: s.set_property(ARC, "width", mm(0.3), old=mm(0.2)))
    assert receipt.written, receipt.issues
    [arc] = [
        a
        for a in read_pcbdoc(second.read_bytes()).arcs
        if isinstance(a, ArcRecord) and a.prefix.component is None
    ]
    assert arc.width == to_units(mm(0.3)) and arc.radius == to_units(mm(2))


def test_an_arc_without_a_template_is_refused(board: Path, tmp_path: Path) -> None:
    add: Build = lambda s: s.add_arc((0, 0), mm(1), 0, 90, width=mm(0.1), layer="Bottom Layer")  # noqa: E731
    receipt = _commit(board, tmp_path / "never.PcbDoc", add)
    [issue] = receipt.issues
    assert issue.code == "altium.edit.no-template" and "arc on Bottom Layer" in issue.message


# --- 4: fills and regions ----------------------------------------------------------------------------


def _fill(state: State, view: View) -> None:
    """A fill of the 46-byte saved form on the Top Layer, (34, 2)–(36, 4) mm on GND, authored here."""
    a, b = view.units((mm(34), mm(2))), view.units((mm(36), mm(4)))
    body = prefix(1, net=GND_NET) + struct.pack("<4id", *a, *b, 0.0) + bytes(9)
    assert len(body) == 46
    state.append("Fills6", bytes((FILL,)) + struct.pack("<I", len(body)) + body)


def test_a_fill_is_created_beside_a_fill_of_the_document(board: Path, tmp_path: Path) -> None:
    """Scenario "A fill created beside a fill of the document"."""
    add: Build = lambda s: s.add_fill((mm(2), mm(2)), (mm(4), mm(3)), layer="Top Layer", net="GND")  # noqa: E731
    refused = _commit(board, tmp_path / "never.PcbDoc", add)
    [issue] = refused.issues
    assert issue.code == "altium.edit.no-template" and "fill on Top Layer" in issue.message
    before = _author(board, _fill)
    out = tmp_path / "added.PcbDoc"
    receipt = _commit(board, out, lambda s: s.add_fill((mm(4), mm(3)), (mm(2), mm(2)), layer="Top Layer",
                                                      net="GND").declare_connectivity("GND"))  # fmt: skip
    assert receipt.written, receipt.issues
    assert _diff(before, out.read_bytes()) == {"Fills6": (0, 1)}
    state = State.of(out.read_bytes())
    view = View(state)
    fills = [f for f in state.typed("Fills6") if isinstance(f, FillRecord)]
    assert len(fills) == 2 and len(fills[1].raw) == len(fills[0].raw)
    new = fills[1]
    assert (new.x1, new.y1) == view.units((mm(2), mm(2))) and (new.x2, new.y2) == view.units((mm(4), mm(3)))
    assert new.prefix.net == GND_NET and new.prefix.layer == 1 and new.tail == fills[0].tail


def test_a_fill_is_moved_and_deleted(board: Path, tmp_path: Path) -> None:
    before = _author(board, _fill)
    fill = edit.Fill((mm(36), mm(4)), (mm(34), mm(2)), "Top Layer", "GND")
    moved, gone = tmp_path / "moved.PcbDoc", tmp_path / "gone.PcbDoc"
    receipt = _commit(board, moved, lambda s: s.move(fill, 0, mm(1), expect={"rotation": 0}))
    assert receipt.written, receipt.issues
    assert _diff(before, moved.read_bytes()) == {"Fills6": (1, 1)}
    receipt = _commit(
        moved, gone, lambda s: s.delete(edit.Fill((mm(34), mm(3)), (mm(36), mm(5)), "Top Layer", "GND"))
    )
    assert receipt.written, receipt.issues
    assert _diff(before, gone.read_bytes()) == {"Fills6": (1, 0)}


def test_a_region_is_created_in_both_forms(board: Path, tmp_path: Path) -> None:
    out = tmp_path / "added.PcbDoc"
    outline = [(mm(20), mm(20)), (mm(24), mm(20)), (mm(24), mm(23)), (mm(20), mm(23)), (mm(19), mm(21.5))]
    receipt = _commit(board, out, lambda s: s.add_region(outline, layer=MECH))
    assert receipt.written and receipt.issues == (), receipt.issues
    data = out.read_bytes()
    assert _diff(board.read_bytes(), data) == {"Regions6": (0, 1), "ShapeBasedRegions6": (0, 1)}
    view = View(State.of(data))
    doc = read_pcbdoc(data)
    plain = doc.regions[-1]
    shaped = doc.shape_regions[-1]
    assert isinstance(plain, RegionRecord) and isinstance(shaped, RegionRecord)
    want = [view.units(p) for p in outline]
    assert [(round(v.x), round(v.y)) for v in plain.outline] == want
    assert [(v.x, v.y) for v in shaped.outline] == want and shaped.closing is not None
    assert plain.properties.fields == doc.regions[0].properties.fields  # type: ignore[union-attr]
    assert plain.hole_count == 0 and integrity.check_pcbdoc(data) == ()
    moved = tmp_path / "moved.PcbDoc"
    receipt = _commit(out, moved, lambda s: s.move(edit.Region(MECH, (mm(19), mm(20))), mm(1), 0))
    assert receipt.written, receipt.issues


# --- 3: polygons -------------------------------------------------------------------------------------

VIN = edit.Polygon("VIN")
VIN_OUTLINE = [(mm(2), mm(28)), (mm(8), mm(28)), (mm(8), mm(22)), (mm(2), mm(22))]
"""The kit's ``VIN`` polygon, (2, 2)–(8, 8) mm in ``place()``'s frame, in the document's frame."""


def _outline_mm(data: bytes, name: str) -> list[tuple[float, float]]:
    doc = read_pcbdoc(data)
    view = View(State.of(data))
    [polygon] = [p for p in doc.polygons if p.name == name]
    return [
        (
            round((float(v.x) - view.origin[0]) * 127 / 50 / 1e6, 3),
            round((float(v.y) - view.origin[1]) * 127 / 50 / 1e6, 3),
        )
        for v in polygon.vertices
    ]


def _poured(state: State, view: View) -> None:
    """A poured piece of ``VIN`` (polygon 1): the kit's region and its twin with the polygon's index."""
    for storage in ("Regions6", "ShapeBasedRegions6"):
        (raw,) = state.get(storage)
        state.append(storage, rec.set_prefix(raw, polygon=1))


def test_a_polygon_is_moved_with_its_pour(board: Path, tmp_path: Path) -> None:
    """Scenario "A polygon moved"."""
    before = _author(board, _poured)
    out = tmp_path / "moved.PcbDoc"
    receipt = _commit(board, out, lambda s: s.move(VIN, mm(1), mm(2)))
    assert receipt.written, receipt.issues
    data = out.read_bytes()
    assert _diff(before, data) == {"Polygons6": (1, 1), "Regions6": (1, 1), "ShapeBasedRegions6": (1, 1)}
    old = _outline_mm(before, "VIN")
    assert _outline_mm(data, "VIN") == [(round(x + 1, 3), round(y + 2, 3)) for x, y in old]
    assert _outline_mm(data, "GND") == _outline_mm(before, "GND")
    doc = read_pcbdoc(data)
    poured = [r for r in doc.regions if isinstance(r, RegionRecord) and r.prefix.polygon == 1]
    assert [_corner_mm(r, View(State.of(data)).origin) for r in poured] == [(31.0, 26.0)]


def test_a_polygon_takes_a_new_outline_and_loses_its_pour(board: Path, tmp_path: Path) -> None:
    """Scenario "A polygon given a new outline"."""
    before = _author(board, _poured)
    new = [(mm(2), mm(28)), (mm(10), mm(28)), (mm(10), mm(21)), (mm(2), mm(21))]
    wrong = [(mm(2), mm(28)), (mm(9), mm(28)), (mm(8), mm(22)), (mm(2), mm(22))]
    refused = _commit(board, tmp_path / "never.PcbDoc", lambda s: s.set_outline(VIN, new, old=wrong))
    [issue] = refused.issues
    assert issue.code == "altium.edit.assertion" and "vertex 1" in issue.message
    out = tmp_path / "outlined.PcbDoc"
    receipt = _commit(board, out, lambda s: s.set_outline(VIN, new, old=VIN_OUTLINE))
    assert receipt.written, receipt.issues
    data = out.read_bytes()
    assert _diff(before, data) == {"Polygons6": (1, 1), "Regions6": (1, 0), "ShapeBasedRegions6": (1, 0)}
    assert _outline_mm(data, "VIN") == [(2.0, 28.0), (10.0, 28.0), (10.0, 21.0), (2.0, 21.0), (2.0, 28.0)]
    [vin] = [p for p in read_pcbdoc(data).polygons if p.name == "VIN"]
    assert (vin.layer, vin.net, vin.pour_index) == ("TOP", 2, 1)


def test_a_polygon_is_created_without_a_pour(board: Path, tmp_path: Path) -> None:
    out = tmp_path / "added.PcbDoc"
    outline = [(mm(30), mm(10)), (mm(38), mm(10)), (mm(38), mm(4)), (mm(30), mm(4))]
    receipt = _commit(board, out, lambda s: s.add_polygon("AUX", outline, layer="Top Layer", net="MID"))
    assert receipt.written and receipt.issues == (), receipt.issues
    data = out.read_bytes()
    assert _diff(board.read_bytes(), data) == {"Polygons6": (0, 1)}
    [aux] = [p for p in read_pcbdoc(data).polygons if p.name == "AUX"]
    assert (aux.layer, aux.pour_index, aux.record.get("NAME")) == ("TOP", 2, "65,85,88")
    assert aux.net == View(State.of(data)).nets.index("MID")
    assert _outline_mm(data, "AUX")[:-1] == [(30.0, 10.0), (38.0, 10.0), (38.0, 4.0), (30.0, 4.0)]
    again: Build = lambda s: s.add_polygon("VIN", outline, layer="Top Layer", net="MID")  # noqa: E731
    refused = _commit(board, tmp_path / "never.PcbDoc", again)
    assert refused.issues[0].code == "altium.edit.assertion"


def test_create_is_behind_its_gate(board: Path, tmp_path: Path) -> None:
    """Scenario "A creation behind its gate"."""
    session = edit.open(board)
    assert isinstance(session, edit.Session)
    receipt = session.add_arc((mm(30), mm(20)), mm(2), 0, 90, width=mm(0.2), layer="Top Overlay").commit(
        tmp_path / "never.PcbDoc"
    )
    [issue] = receipt.issues
    assert issue.code == "altium.edit.gate" and "H-A-EDIT-CREATE" in issue.message
    assert edit.ROWS["set_outline"] == ("H-A-EDIT-SHAPE", "H-A-EDIT-KIT")
    assert OPEN["create"] and not edit.GATES["create"]


def test_region_outline(ops_board: Callable[[str], Path]) -> None:
    """Change c0497 (D7): a free keep-out region given a ring 1 mm larger on each side, its keys kept."""
    from tests.unit.backends.altium.edit.board_ops import KEEPOUT

    path = ops_board("drawn")
    item = edit.Region("Keep-Out Layer", (mm(25), mm(20)))
    old = [(mm(x), mm(y)) for x, y in KEEPOUT]
    new = [(mm(24), mm(19)), (mm(29), mm(19)), (mm(29), mm(24)), (mm(24), mm(24))]
    before = path.read_bytes()
    receipt = _commit(path, path.with_name("out.PcbDoc"), lambda s: s.set_outline(item, new, old=old))
    assert receipt.written, receipt.issues
    after = path.with_name("out.PcbDoc").read_bytes()
    assert _diff(before, after) == {"Regions6": (1, 1), "ShapeBasedRegions6": (1, 1)}
    view = View(State.of(after))
    for storage in ("Regions6", "ShapeBasedRegions6"):
        held = [
            p for p in State.of(after).typed(storage) if isinstance(p, RegionRecord) and p.prefix.layer == 56
        ]
        [region] = [p for p in held if rec.region_keys(p.raw).get("KEEPOUTRESTRICTIONS") == "1"]
        assert [(round(v.x), round(v.y)) for v in region.outline][:4] == [view.units(p) for p in new]
        assert rec.split(region.raw)[1][0][2] == 2
    wrong = [(mm(x + 1), mm(y)) for x, y in KEEPOUT]
    receipt = _commit(path, path.with_name("bad.PcbDoc"), lambda s: s.set_outline(item, new, old=wrong))
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]
