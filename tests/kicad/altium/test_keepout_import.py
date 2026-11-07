# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keep-out tracks and a polygon cut-out against ``kicad-cli pcb import`` (change c0407; ``pcb-records.md``,
"Regions and keep-outs").

The authored document of ``_altium_keepouts`` goes through KiCad 10's importer and through Fenolite's reader
and ``convert.altium_to_kicad.keepouts``; both give six rule areas of the same layers and shapes: a band of
the track's width per keep-out track, and the polygon cut-out's outline. ``pcb import`` exists from 10.0
only. A pass says what KiCad's importer reads; it settles nothing for Altium Designer.
"""

from __future__ import annotations

import dataclasses
import hashlib

import _altium_keepouts as keepouts
import _altium_slotcases as cases
import pytest
from _resources import kicad_cli_major

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.convert.altium_to_kicad import Ledger
from fenolite.convert.altium_to_kicad import keepouts as convert_keepouts
from fenolite.core.coords import Point
from fenolite.geometry import area2
from fenolite.model.board import Keepout
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

pytestmark = pytest.mark.needs_kicad
SHAPE_TOLERANCE = 10_000
"""KiCad polygonises a round end with fewer vertices than Fenolite: a corner of the box may differ by this
much (nm)."""


def _corner(design: Design) -> Point:
    assert design.board is not None
    edge = [p for g in design.board.graphics if g.layer == "Edge.Cuts" for p in g.points]
    return Point(min(p.x for p in edge), min(p.y for p in edge))


def _shapes(design: Design) -> list[tuple[tuple[str, ...], tuple[int, int, int, int], int]]:
    """Each rule area as (layers, box relative to the board's corner, area in nm²), sorted."""
    assert design.board is not None
    corner = _corner(design)

    def shape(area: Keepout) -> tuple[tuple[str, ...], tuple[int, int, int, int], int]:
        xs = [p.x - corner.x for p in area.outline]
        ys = [p.y - corner.y for p in area.outline]
        return tuple(sorted(area.layers)), (min(xs), min(ys), max(xs), max(ys)), abs(area2(area.outline)) // 2

    return sorted(shape(area) for area in design.board.keepouts)


def test_rule_areas_match_kicad_import() -> None:
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    data = keepouts.keepout_document()
    kicad = cases.import_document(data, "keepouts.PcbDoc").design
    read = import_board(read_pcbdoc(data), file="keepouts.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    ours = convert_keepouts(read, Ledger())
    theirs, mine = _shapes(kicad), _shapes(ours)
    assert len(theirs) == len(mine) == 6
    for (layers_k, box_k, area_k), (layers_m, box_m, area_m) in zip(theirs, mine, strict=True):
        assert layers_k == layers_m
        assert all(abs(a - b) <= SHAPE_TOLERANCE for a, b in zip(box_k, box_m, strict=True)), (box_k, box_m)
        assert abs(area_k - area_m) <= area_k // 100, (area_k, area_m)
    # the same restrictions on every area (change c0410: the bands forbid pads too); the polygon cut-out
    # keeps out poured copper alone
    assert kicad.board is not None and ours.board is not None
    assert _restrictions(kicad) == _restrictions(ours)
    assert _restrictions(ours).count((False, False, False, True, False)) == 1


def _restrictions(design: Design) -> list[tuple[bool, bool, bool, bool, bool]]:
    assert design.board is not None
    return sorted(
        (k.no_tracks, k.no_vias, k.no_pads, k.no_copper_pour, k.no_footprints) for k in design.board.keepouts
    )


def _zones(footprint: object) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    """Each zone of a ``.kicad_mod`` as (its layers, the kinds it does not allow)."""
    found: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for zone in footprint.nodes("zone"):  # type: ignore[attr-defined]
        held = zone.find("layers") or zone.find("layer")
        layers = tuple(str(a.value) for a in held.atoms()) if held is not None else ()
        keepout = zone.find("keepout")
        kinds = tuple(
            child.name for child in (keepout.nodes() if keepout is not None else ()) if
            [str(a.value) for a in child.atoms()] == ["not_allowed"]
        )  # fmt: skip
        found.append((layers, kinds))
    return found


def test_library_keepouts_as_kicad_upgrades_them() -> None:
    """Change c0410 measures what ``fp upgrade`` 10.0.6 makes of the keep-outs of a library footprint (the
    target of change c0411): five rule areas of the footprint. Fenolite makes no copper of the three on copper
    (``test_keepout_primitives``)."""
    if kicad_cli_major() == 9:
        pytest.skip("Altium libraries are read by `fp upgrade` from 10.0 on only")
    from fenolite.backends.kicad.sexpr import parse_bytes

    run = cases.runner().run(
        ["fp", "upgrade", "-o", "out.pretty", "keepouts.PcbLib"],
        files={"keepouts.PcbLib": keepouts.keepout_library()},
    )
    assert run.ok, run.stdout + run.stderr
    (name,) = [n for n in run.outputs if n.endswith(".kicad_mod")]
    zones = _zones(parse_bytes(run.outputs[name]))
    every = ("tracks", "vias", "pads", "copperpour")
    on_copper = [(layers, kinds) for layers, kinds in zones if len(layers) == 1]
    assert sorted(on_copper) == [
        (("B.Cu",), ("tracks", "vias")),
        (("F.Cu",), ("copperpour",)),
        (("F.Cu",), every),
    ]
    everywhere = sorted(kinds for layers, kinds in zones if len(layers) > 1)
    assert everywhere == [(), every]  # the plain track of the Keep-Out layer forbids nothing in KiCad


def _box(area: Keepout) -> tuple[int, int, int, int]:
    xs, ys = [p.x for p in area.outline], [p.y for p in area.outline]
    return min(xs), min(ys), max(xs), max(ys)


def _flags(area: Keepout) -> tuple[bool, bool, bool, bool]:
    return area.no_tracks, area.no_vias, area.no_pads, area.no_copper_pour


def _library_through_both() -> tuple[FootprintDef, FootprintDef, FootprintDef]:
    """The authored library imported by Fenolite, that definition written as a ``.kicad_mod`` by Fenolite
    and read back, and the library upgraded by ``fp upgrade`` and read by Fenolite."""
    from fenolite.backends.altium.adapter.library import import_footprints
    from fenolite.backends.altium.read.pcblib import read_pcblib
    from fenolite.backends.kicad.mod import read_footprint, write_footprint

    data = keepouts.keepout_library()
    library = import_footprints(
        read_pcblib(data), name="keepouts", file="keepouts.PcbLib", sha256=hashlib.sha256(data).hexdigest()
    )
    (imported,) = library.footprints
    # the drawings of the Keep-Out layer and the Altium height are out of this proof (``convert`` makes
    # the rule areas of the former, as on a board)
    authored = dataclasses.replace(
        imported, properties={}, graphics=tuple(g for g in imported.graphics if g.layer != "Altium.KeepOut")
    )
    written = read_footprint(write_footprint(authored, target=10), library="keepouts")
    run = cases.runner().run(
        ["fp", "upgrade", "-o", "out.pretty", "keepouts.PcbLib"], files={"keepouts.PcbLib": data}
    )
    assert run.ok, run.stdout + run.stderr
    (name,) = [n for n in run.outputs if n.endswith(".kicad_mod")]
    upgraded = read_footprint(run.outputs[name].decode("utf-8"), library="keepouts")
    return imported, written, upgraded


def test_library_rule_areas_match_fp_upgrade() -> None:
    """Change c0411: the three rule areas on copper that Fenolite imports from the authored library, and
    writes into a ``.kicad_mod``, are those ``fp upgrade`` 10.0.6 makes: layers, restrictions, boxes within
    10 µm and areas within 1 %. KiCad's two areas on every copper layer stand for the drawings of the Keep-Out
    layer, which Fenolite keeps as drawings for ``convert``."""
    if kicad_cli_major() == 9:
        pytest.skip("Altium libraries are read by `fp upgrade` from 10.0 on only")
    imported, written, upgraded = _library_through_both()
    assert [g.layer for g in imported.graphics] == ["Altium.KeepOut"] * 2
    assert [k.layers for k in upgraded.keepouts].count(("*.Cu",)) == 2  # its 32 copper layers
    theirs = sorted((k for k in upgraded.keepouts if k.layers != ("*.Cu",)), key=_box)
    for ours in (imported.keepouts, written.keepouts):
        mine = sorted(ours, key=_box)
        assert len(mine) == len(theirs) == 3
        for a, b in zip(mine, theirs, strict=True):
            assert a.layers == b.layers and _flags(a) == _flags(b), (a, b)
            assert all(abs(x - y) <= SHAPE_TOLERANCE for x, y in zip(_box(a), _box(b), strict=True))
            area_a, area_b = abs(area2(a.outline)) // 2, abs(area2(b.outline)) // 2
            assert abs(area_a - area_b) <= area_b // 100, (area_a, area_b)


def test_a_placed_library_rule_area_keeps_a_track_out_in_kicad_drc() -> None:
    """Change c0411: the written footprint placed at (50, 50) mm turned 90 degrees on a board that KiCad
    10.0.6 loads in ``pcb drc``: a track at the placed band of the keep-out track is reported, and a track
    where the band would lie without the turn is not."""
    if kicad_cli_major() == 9:
        pytest.skip("Altium libraries are read by `fp upgrade` from 10.0 on only")
    import json

    from fenolite.backends.kicad.embed import place_footprint
    from fenolite.backends.kicad.layers import created_layers
    from fenolite.backends.kicad.pcb import write_board
    from fenolite.model.board import Track, placed_keepout
    from fenolite.model.circuit import Circuit, Component

    _, written, _ = _library_through_both()
    part = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="U1", value="KO")
    at = Point(50_000_000, 50_000_000)
    instance = place_footprint(written, component=part, at=at, rotation=90_000_000, key="U1")
    (band,) = [k for k in instance.keepouts if k.layers == ("F.Cu",) and k.no_tracks]

    def centre(area: Keepout) -> Point:
        x0, y0, x1, y1 = _box(area)
        return Point((x0 + x1) // 2, (y0 + y1) // 2)

    def short(ident: str, middle: Point) -> Track:
        return Track(
            id=ident,
            start=Point(middle.x - 100_000, middle.y),
            end=Point(middle.x + 100_000, middle.y),
            width=100_000,
            layer="F.Cu",
        )

    inside = centre(placed_keepout(instance, band))
    unturned = centre(
        dataclasses.replace(band, outline=tuple(Point(at.x + p.x, at.y + p.y) for p in band.outline))
    )
    assert abs(inside.x - unturned.x) > 1_000_000  # the turn moves the band
    design = Design.new("placed", seed=1)
    assert design.board is not None
    board = dataclasses.replace(
        design.board,
        layers=created_layers(2),
        footprints=(instance,),
        tracks=(short("trk_inside", inside), short("trk_unturned", unturned)),
    )
    design = dataclasses.replace(design, circuit=Circuit(components=(part,)), board=board)
    text = write_board(design, target=10).text
    run = cases.runner().run(
        ["pcb", "drc", "--format", "json", "--severity-all", "-o", "drc.json", "b.kicad_pcb"],
        files={"b.kicad_pcb": text.encode("utf-8")},
    )
    report = json.loads(run.outputs["drc.json"])
    banned = [v for v in report.get("violations", []) if v["type"] == "items_not_allowed"]
    tracks = [item for v in banned for item in v["items"] if item["description"].startswith("Track")]
    assert len(tracks) == 1, banned
    x = round(float(tracks[0]["pos"]["x"]) * 1_000_000)
    assert abs(x - inside.x) <= 200_000, (tracks, inside)


@pytest.mark.needs_corpus
def test_component_keep_outs_of_a_public_document_hold_their_restrictions() -> None:
    """The keep-out fills and arcs of the components of the public row ``-08`` (``pcb-records.md``,
    "Regions and keep-outs"): KiCad 10.0.6's ``pcb import`` and Fenolite's import give each footprint rule
    areas with the same restrictions, read from the byte after the record's long layer id. The fills of
    ``J13`` to ``J17`` hold 24 and forbid pads alone, that of ``J12`` holds 0 and forbids nothing, and the
    arcs of the fiducials hold 31. Before, Fenolite gave every keep-out fill all restrictions, and its
    copper check judged 343 tracks and vias of the connectors' own nets under them."""
    from collections import Counter

    from _corpus import heavy_enabled, manifest_items, require

    from fenolite.backends.altium.backend import AltiumBackend

    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    if not heavy_enabled():
        pytest.skip("altium-third-party-pcbdoc-08 is a heavy corpus item: set FENOLITE_HEAVY=1 to include it")
    item = next(i for i in manifest_items("rta") if i.id == "altium-third-party-pcbdoc-08")
    path = require(item)

    def areas(design: Design) -> Counter[tuple[str, tuple[bool, bool, bool, bool, bool]]]:
        assert design.board is not None
        refs = {c.id: c.ref for c in design.circuit.components}
        return Counter(
            (refs[fp.component_id], (k.no_tracks, k.no_vias, k.no_pads, k.no_copper_pour, k.no_footprints))
            for fp in design.board.footprints
            for k in fp.keepouts
        )

    kicad = areas(cases.import_document(path.read_bytes(), path.name).design)
    ours = areas(AltiumBackend().read(path).design)
    pads_only = (False, False, True, False, False)
    assert {ref: n for (ref, flags), n in kicad.items() if flags == pads_only} == {
        f"J{n}": 2 for n in range(13, 18)
    }
    assert kicad[("J12", (False,) * 5)] == 1
    # a full keep-out circle is two half bands in Fenolite and one zone in KiCad: compare the kinds
    assert set(ours) == set(kicad)
    assert {k: n for k, n in ours.items() if not k[0].startswith("FID")} == {
        k: n for k, n in kicad.items() if not k[0].startswith("FID")
    }
