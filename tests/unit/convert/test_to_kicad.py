# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The direction from KiCad to KiCad (capability design-conversion, "KiCad to KiCad direction" and "KiCad
downgrade refused"; change c0159)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from _convert import BLINK_T9, BLINK_T10, TWO_LAYER

from fenolite.api.conversion import convert
from fenolite.convert import LossyConversionError, convert_project

ROOT = Path(__file__).resolve().parents[3]
WITH_SHEET = ROOT / "tests" / "data" / "kicad" / "parity" / "agree"
TOKENS = ROOT / "tests" / "data" / "kicad" / "tokens"


DEFAULT_SECTIONS = {
    "downgrade:project:/component_class_settings",
    "downgrade:project:/net_settings/classes/*/tuning_profile",
    "downgrade:project:/tuning_profiles",
}
"""The report rows of the sections every KiCad 10 project holds (component classes, tuning profiles)."""


def _with_profile(tmp_path: Path) -> Path:
    """A copy of the blink project whose tuning profiles and component classes hold content."""
    folder = tmp_path / "blink"
    shutil.copytree(BLINK_T10, folder)
    path = folder / "blink.kicad_pro"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tuning_profiles"]["tuning_profiles_impedance_geometric"] = [{"profile_name": "Z50"}]
    data["component_class_settings"]["assignments"] = [{"component_class": "X", "conditions": []}]
    data["net_settings"]["classes"][-1]["tuning_profile"] = "Z50"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return folder


def test_downgrade_of_default_sections_needs_no_consent() -> None:
    """Change c0162 (it replaces c0159's "Older target refused"): a board of KiCad 10 is written for 9; the
    sections every KiCad 10 project holds are dropped as ``same`` when they hold the defaults of a fresh
    project (the maintainer's decision of 2026-10-09), so no consent is needed."""
    conversion = convert_project(BLINK_T10, to="kicad", kicad_version=9)
    assert conversion.report.refused == ()
    for kind in DEFAULT_SECTIONS:
        row = conversion.report.row(kind)
        assert row is not None and (row.changed, row.lost, row.loss) == (1, 0, "refuse"), kind


def test_downgrade_needs_consent_for_design_rows(tmp_path: Path) -> None:
    """The same sections with content are ``design`` rows of the resolver, a loss that needs consent."""
    with pytest.raises(LossyConversionError) as refused:
        convert_project(_with_profile(tmp_path), to="kicad", kicad_version=9)
    assert set(refused.value.report.refused) == DEFAULT_SECTIONS
    conversion = convert_project(
        _with_profile(tmp_path / "again"), to="kicad", kicad_version=9, allow_lossy=True
    )
    lost = conversion.report.row("downgrade:project:/tuning_profiles")
    assert lost is not None and lost.lost == 1 and lost.loss == "refuse"
    assert lost.reasons[0].ids == ("blink.kicad_pro:/tuning_profiles",)
    assert "tuning_profiles" not in json.loads(conversion.files["blink.kicad_pro"])


def test_downgrade_rows_per_resolver_id() -> None:
    """Scenario "Rows per resolver id" on the blink example: one row per resolver id, the project's
    libraries written for the target, and the verification under the profile ``kicad-downgrade``."""
    conversion = convert_project(BLINK_T10, to="kicad", kicad_version=9, allow_lossy=True)
    assert conversion.profile == "kicad-downgrade" and conversion.direction.downgrade
    files = sorted(conversion.files)
    assert "fp-lib-table" in files and "lib/Mini.pretty/Mini_R_0603.kicad_mod" in files
    board = conversion.files["blink.kicad_pcb"].decode("utf-8")
    assert "(version 20241229)" in board.splitlines()[1]
    for key in files:
        if key.endswith(".kicad_mod"):
            assert "(version 20241229)" in conversion.files[key].decode("utf-8"), key
    nets = conversion.report.row("downgrade:net-by-name")
    assert nets is not None and nets.changed > 0 and nets.lost == 0 and nets.loss == "report"
    version = conversion.report.row("downgrade:project:/net_settings/meta/version")
    assert version is not None and version.changed == 1
    dropped = conversion.report.row("downgrade:project:/tuning_profiles")
    assert dropped is not None and (dropped.changed, dropped.lost, dropped.loss) == (1, 0, "refuse")
    assert dropped.reasons[0].ids == ("blink.kicad_pro:/tuning_profiles",)
    project = json.loads(conversion.files["blink.kicad_pro"])
    assert "tuning_profiles" not in project and project["net_settings"]["meta"]["version"] == 4


def test_downgrade_verified() -> None:
    result = convert(BLINK_T10, to="kicad", kicad_version=9, allow_lossy=True)
    assert result.equivalence is not None and result.equivalence.report is not None
    assert result.unexplained == () and result.equivalence.report.equivalent


def test_downgrade_of_a_schematic(tmp_path: Path) -> None:
    """A schematic of KiCad 10 is re-targeted with the board (change c0162)."""
    folder = tmp_path / "blink"
    shutil.copytree(BLINK_T10, folder)
    sheet = (TOKENS / "skeleton.kicad_sch").read_text(encoding="utf-8")
    sheet = sheet.replace("(version 20231120)", "(version 20260306)").replace(
        "\t\t(unit 1)\n", "\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(in_pos_files yes)\n", 1
    )
    (folder / "blink.kicad_sch").write_text(sheet, encoding="utf-8")
    conversion = convert_project(folder, to="kicad", kicad_version=9, allow_lossy=True)
    written = conversion.files["blink.kicad_sch"].decode("utf-8")
    assert "(version 20250114)" in written and "(convert 1)" in written and "in_pos_files" not in written
    assert conversion.schematic == "blink.kicad_sch"
    row = conversion.report.row("downgrade:sch-symbol-body-style")
    assert row is not None and row.changed == 1
    schematic = conversion.report.row("schematic")
    assert schematic is not None and (schematic.source, schematic.written, schematic.lost) == (1, 1, 0)


def test_same_major_gives_the_project_back() -> None:
    """A project converted to its own major is its own files: the board keeps its content, the project
    file is updated to what it holds, and the rules file is written again in its order."""
    conversion = convert_project(BLINK_T10, to="kicad", kicad_version=10)
    assert sorted(conversion.files) == ["blink.kicad_dru", "blink.kicad_pcb", "blink.kicad_pro"]
    for name, data in conversion.files.items():
        assert data == (BLINK_T10 / name).read_bytes(), name
    assert not conversion.report.lossy and not conversion.direction.experimental
    assert conversion.read_back == "blink.kicad_pcb"


def test_nine_to_ten() -> None:
    """A KiCad 9 project written for 10: the board's header is that of 10, the classes and rules of the
    project are kept, and nothing is lost."""
    conversion = convert_project(BLINK_T9, to="kicad", kicad_version=10)
    board = conversion.files["blink.kicad_pcb"].decode("utf-8")
    assert "(version 20260206)" in board.splitlines()[1]
    assert conversion.files["blink.kicad_dru"] == (BLINK_T9 / "blink.kicad_dru").read_bytes()
    netclass = conversion.report.row("netclass")
    assert netclass is not None and netclass.source == netclass.written == 2
    assert not conversion.report.lossy


def test_name_renames_the_triad() -> None:
    conversion = convert_project(TWO_LAYER, to="kicad", name="renamed")
    assert sorted(conversion.files) == ["renamed.kicad_dru", "renamed.kicad_pcb", "renamed.kicad_pro"]


def test_schematic_copied_for_the_same_major(tmp_path: Path) -> None:
    folder = tmp_path / "blink"
    shutil.copytree(WITH_SHEET, folder)
    conversion = convert_project(folder, to="kicad", kicad_version=10)
    assert conversion.files["blink.kicad_sch"] == (WITH_SHEET / "blink.kicad_sch").read_bytes()
    row = conversion.report.row("schematic")
    assert row is not None and (row.source, row.written, row.lost) == (1, 1, 0)


def test_schematic_of_another_major_is_reported(tmp_path: Path) -> None:
    """A schematic is not re-targeted (change c0162): converting a board of 9 that has one to 10 reports
    the sheet as lost, a ``report`` kind that needs no consent."""
    folder = tmp_path / "blink"
    shutil.copytree(BLINK_T9, folder)
    shutil.copy(WITH_SHEET / "blink.kicad_sch", folder / "blink.kicad_sch")
    conversion = convert_project(folder, to="kicad", kicad_version=10)
    assert "blink.kicad_sch" not in conversion.files
    row = conversion.report.row("schematic")
    assert row is not None and row.lost == 1 and row.loss == "report"
    assert "not re-targeted" in row.reasons[0].reason and conversion.report.refused == ()


def test_altium_mechanical_layers() -> None:
    import dataclasses

    from _convert import two_layer

    from fenolite.convert.altium_to_kicad import Ledger, map_layers
    from fenolite.core.coords import Point
    from fenolite.model.board import Graphic

    design = two_layer()
    assert design.board is not None
    graphics = tuple(
        Graphic(
            id=f"gra-{i}", kind="line", layer=layer, points=(Point(0, 0), Point(1000000, 0)), width=100000
        )
        for i, layer in enumerate(("Mech.1", "Mech.2", "Altium.74"))
    )
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, graphics=graphics))
    ledger = Ledger()
    result = map_layers(design, 10, ledger)
    assert result.board is not None
    assert [g.layer for g in result.board.graphics] == ["User.1", "User.2"]
    assert ledger.lost["graphic"]["a layer outside the stack"] == ["gra-2"]
    assert dict(result.board.layers[-1].ext["kicad"].payload)["user_name"] == "Mech.2"


def test_altium_drill_layers_take_user_rows() -> None:
    """Change c0428: drawings on the drill drawing and drill guide layers are written on user rows named
    after them, after the mechanical layers, and none is a ``graphic`` loss."""
    import dataclasses

    from _convert import two_layer

    from fenolite.convert.altium_to_kicad import Ledger, map_layers
    from fenolite.core.coords import Point
    from fenolite.model.board import Graphic

    design = two_layer()
    assert design.board is not None
    graphics = tuple(
        Graphic(
            id=f"gra-{i}", kind="line", layer=layer, points=(Point(0, 0), Point(1000000, 0)), width=100000
        )
        for i, layer in enumerate(("Altium.DrillDrawing", "Mech.3", "Altium.DrillGuide"))
    )
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, graphics=graphics))
    ledger = Ledger()
    result = map_layers(design, 10, ledger)
    assert result.board is not None
    assert [g.layer for g in result.board.graphics] == ["User.3", "User.1", "User.2"]
    assert not ledger.lost.get("graphic")
    names = {layer.name: dict(layer.ext["kicad"].payload).get("user_name") for layer in result.board.layers}
    assert (names["User.1"], names["User.2"], names["User.3"]) == (
        "Mech.3",
        "Altium.DrillGuide",
        "Altium.DrillDrawing",
    )


@pytest.mark.parametrize("count", (0, 1, 3, 5))
def test_altium_odd_layers(count: int) -> None:
    from dataclasses import replace

    from _convert import two_layer

    from fenolite.backends.kicad.layers import board_rows
    from fenolite.convert.altium_to_kicad import Ledger, map_layers

    design = two_layer()
    assert design.board is not None
    rows = tuple(row for row in board_rows(6) if row.kind == "copper")
    rows = (*rows[: count - 1], rows[-1]) if count > 1 else rows[:count]
    design = replace(design, board=replace(design.board, layers=rows, footprints=()))
    ledger = Ledger()
    result = map_layers(design, 10, ledger)
    assert result.board is not None
    assert sum(row.kind == "copper" for row in result.board.layers) == max(2, count + count % 2)
    assert ledger.changed["stackup"]


def test_altium_keepout_closed_and_open() -> None:
    """A closed outline of width 0 is one rule area; a line drawn with a width is the band it covers (change
    c0407: it was a loss, "a keep-out line that encloses no area"); a line of width 0 covers no area."""
    import dataclasses

    from _convert import two_layer

    from fenolite.convert.altium_to_kicad import KEEPOUT_AREA, KEEPOUT_BAND, KEEPOUT_NO_AREA, Ledger, keepouts
    from fenolite.core.coords import Point
    from fenolite.model.board import Graphic

    design = two_layer()
    assert design.board is not None
    polygon = Graphic(
        id="gra-closed",
        kind="polygon",
        layer="Altium.KeepOut",
        points=(Point(0, 0), Point(1000000, 0), Point(1000000, 1000000)),
        width=0,
    )
    line = Graphic(
        id="gra-open",
        kind="line",
        layer="Altium.KeepOut",
        points=(Point(2000000, 0), Point(3000000, 0)),
        width=100000,
    )
    thin = dataclasses.replace(line, id="gra-thin", width=0)
    graphics = (polygon, line, thin)
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, graphics=graphics))
    ledger = Ledger()
    result = keepouts(design, ledger)
    assert result.board is not None
    area, band = result.board.keepouts[-2:]
    assert area.outline == polygon.points
    assert area.no_tracks and area.no_vias and area.no_pads and area.no_copper_pour
    ys = [p.y for p in band.outline]
    xs = [p.x for p in band.outline]
    assert (min(ys), max(ys), min(xs), max(xs)) == (-50000, 50000, 1950000, 3050000)
    assert band.no_tracks and band.no_vias and band.no_pads and band.no_copper_pour  # pads: change c0410
    assert not result.board.graphics
    assert ledger.changed["graphic"][KEEPOUT_AREA] == [polygon.id]
    assert ledger.changed["graphic"][KEEPOUT_BAND] == [line.id]
    assert ledger.lost["graphic"][KEEPOUT_NO_AREA] == [thin.id]


def test_altium_keepout_restrictions_reach_the_rule_areas() -> None:
    """Scenario "A keep-out forbids what its value forbids" (change c0420, N2 and N3): the rule area of a
    keep-out of the Keep-Out layer forbids the kinds of its record's restrictions value alone (1 vias, 2
    tracks, 4 poured copper, 8 with 16 pads); a drawing without a value forbids all four (change c0410)."""
    import dataclasses

    from _convert import two_layer

    from fenolite.convert.altium_to_kicad import Ledger, keepouts
    from fenolite.core.coords import Point
    from fenolite.model.board import Graphic

    design = two_layer()
    assert design.board is not None
    square = (Point(0, 0), Point(1000000, 0), Point(1000000, 1000000), Point(0, 1000000))

    def drawn(ident: str) -> Graphic:
        return Graphic(id=ident, kind="polygon", layer="Altium.KeepOut", points=square, width=0)

    graphics = tuple(drawn(ident) for ident in ("gra-7", "gra-24", "gra-8", "gra-none"))
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, graphics=graphics))
    result = keepouts(design, Ledger(), {"gra-7": 7, "gra-24": 24, "gra-8": 8})
    assert result.board is not None
    held = [(k.no_vias, k.no_tracks, k.no_copper_pour, k.no_pads) for k in result.board.keepouts[-4:]]
    assert held == [
        (True, True, True, False),
        (False, False, False, True),
        (False, False, False, False),
        (True, True, True, True),
    ]


def test_altium_keepout_restrictions_are_read_from_the_source_records(tmp_path: Path) -> None:
    """Change c0420, N2 and N3: ``keepout_restrictions`` reads the restrictions value of each keep-out of the
    Keep-Out layer from its record in the source document, by the drawing's locator; the keep-out tracks of
    the authored document hold 31, every restriction. A document whose bytes changed gives none."""
    import hashlib

    import _altium_keepouts as cases

    from fenolite.backends.altium.adapter import import_board
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.convert.altium_to_kicad import keepout_restrictions
    from fenolite.convert.sources import SourceProject

    data = cases.keepout_document()
    path = tmp_path / "k.PcbDoc"
    path.write_bytes(data)
    design = import_board(read_pcbdoc(data), file="k.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    source = SourceProject(
        given=path, path=path, root=tmp_path, backend="altium", kind="pcbdoc", design=design
    )
    assert design.board is not None
    drawn = [g.id for g in design.board.graphics if g.layer == "Altium.KeepOut"]
    assert keepout_restrictions(source, design) == dict.fromkeys(drawn, 31) and len(drawn) == 4
    path.write_bytes(data + b"\0")
    assert keepout_restrictions(source, design) == {}


def test_altium_keepout_track_ring_is_four_bands() -> None:
    """B1 (change c0407): a closed ring of keep-out tracks on the Keep-Out layer keeps out the band of each
    track, one rule area per track on every copper layer, as KiCad 10.0.6 imports it; the inside of the ring
    stays free. The keep-out track and the polygon cut-out on Top are the adapter's rule areas."""
    import hashlib

    import _altium_keepouts as cases

    from fenolite.backends.altium.adapter import import_board
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.convert.altium_to_kicad import KEEPOUT_BAND, Ledger, keepouts
    from fenolite.core.coords import Point
    from fenolite.geometry import Location, point_in_ring

    data = cases.keepout_document()
    design = import_board(read_pcbdoc(data), file="k.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    ledger = Ledger()
    result = keepouts(design, ledger)
    assert result.board is not None
    adapter, bands = result.board.keepouts[:2], result.board.keepouts[2:]
    assert sorted(k.layers for k in adapter) == [("F.Cu",), ("F.Cu",)]
    assert len(bands) == 4 and all(k.layers == ("F.Cu", "B.Cu") for k in bands)
    assert all(k.no_vias and k.no_tracks and k.no_copper_pour and k.no_pads for k in bands)
    assert len(ledger.changed["graphic"][KEEPOUT_BAND]) == 4
    mm = 1_000_000
    for band in bands:
        xs, ys = [p.x for p in band.outline], [p.y for p in band.outline]
        spans = sorted((max(xs) - min(xs), max(ys) - min(ys)))
        assert abs(spans[0] - cases.RING_WIDTH) <= 4 and abs(spans[1] - 11 * mm) <= 4
    lo_x = min(p.x for k in bands for p in k.outline)
    lo_y = min(p.y for k in bands for p in k.outline)
    centre = Point(lo_x + 5 * mm + cases.RING_WIDTH // 2, lo_y + 5 * mm + cases.RING_WIDTH // 2)
    assert all(point_in_ring(centre, k.outline) == Location.OUTSIDE for k in bands)


def test_altium_zone_arc_outline() -> None:
    """A polygon outline with an arc vertex is flattened from vertex k to vertex k + 1 (half disc)."""
    from fractions import Fraction

    from fenolite.backends.altium.adapter.units import units_length
    from fenolite.backends.altium.read.pcbstack import OutlineVertex
    from fenolite.convert.altium_to_kicad import _arc_ring

    r = Fraction(10_000_000)  # 1000 mil in units
    zero = Fraction(0)
    arc = OutlineVertex(1, r, zero, zero, zero, 0.0, 180.0, r)
    line = OutlineVertex(0, -r, zero, zero, zero, 0.0, 0.0, zero)
    ring = _arc_ring((arc, line))
    radius = units_length(r)[0]
    assert len(ring) > 8
    # the Y flip: the arc through Altium's +Y runs through the model's -Y
    assert min(p.y for p in ring) < -radius + 10 and max(p.y for p in ring) == 0
    assert all(abs(p.x) <= radius and (p.x**2 + p.y**2) <= (radius + 1) ** 2 for p in ring)


@pytest.mark.parametrize("points", [0, 1, 2])
def test_altium_zone_without_outline_source_is_dropped(points: int) -> None:
    """A zone of fewer than 3 points (none, or the 1 or 2 that a record of coinciding vertices gives, change
    c0428) and no record is dropped, never written as it is."""
    import dataclasses
    from pathlib import Path

    from _convert import two_layer

    from fenolite.convert.altium_to_kicad import ZONE_NO_OUTLINE, Ledger, zone_outlines
    from fenolite.convert.sources import SourceProject
    from fenolite.model.board import Zone

    design = two_layer()
    assert design.board is not None
    from fenolite.core.coords import Point

    outline = tuple(Point(k, k) for k in range(points))
    empty = Zone(id="zon-arc", outline=outline, name="pour", layers=("F.Cu",))
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(empty,)))
    source = SourceProject(Path("x.PcbDoc"), Path("x.PcbDoc"), Path("."), "altium", "altium_pcbdoc", design)
    ledger = Ledger()
    result = zone_outlines(source, design, ledger)
    assert result.board is not None and not result.board.zones
    assert ledger.lost["zone"][ZONE_NO_OUTLINE] == ["zon-arc"]


def test_altium_zone_without_area_is_a_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """A zone whose polygon record encloses no area pours no copper: it is left out as a ``changed`` zone,
    not a loss, so the conversion needs no ``--allow-lossy`` for it (change c0428)."""
    import dataclasses
    from pathlib import Path

    from _convert import two_layer

    import fenolite.convert.altium_to_kicad as a2k
    from fenolite.convert.sources import SourceProject
    from fenolite.core.coords import Point
    from fenolite.core.provenance import Provenance
    from fenolite.model.board import Zone

    design = two_layer()
    assert design.board is not None
    where = Provenance(backend="altium", file="x.PcbDoc", file_sha256="0" * 64, locator="Polygons6/Data#0")
    flat = Zone(id="zon-flat", outline=(Point(1, 1),), name="pour", layers=("F.Cu",), provenance=where)
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(flat,)))
    source = SourceProject(Path("x.PcbDoc"), Path("x.PcbDoc"), Path("."), "altium", "altium_pcbdoc", design)
    monkeypatch.setattr(a2k, "_source_document", lambda *args: object())
    monkeypatch.setattr(a2k, "polygon_outline", lambda document, locator: ((), a2k.ZONE_NO_AREA))
    ledger = a2k.Ledger()
    result = a2k.zone_outlines(source, design, ledger)
    assert result.board is not None and not result.board.zones
    assert ledger.changed["zone"][a2k.ZONE_NO_AREA] == ["zon-flat"] and not ledger.lost["zone"]


@pytest.mark.parametrize("target", (9, 10))
def test_altium_schematic_and_libraries(target: int) -> None:
    from fenolite.api import convert

    result = convert(
        ROOT / "tests/data/altium/blink/blink.PrjPcb", to="kicad", kicad_version=target, allow_lossy=True
    )
    assert not result.unexplained
    files = result.conversion.files
    assert {
        "blink.kicad_pcb",
        "blink.kicad_pro",
        "blink.kicad_dru",
        "blink.kicad_sch",
        "fp-lib-table",
        "sym-lib-table",
        "lib/blink.kicad_sym",
    } <= files.keys()
    assert any(key.startswith("blink.pretty/") for key in files)
    assert result.conversion.schematic == "blink.kicad_sch"
    from fenolite.backends.kicad.sexpr import parse

    for key, data in files.items():
        if key.endswith(".kicad_mod"):
            root = parse(data.decode())
            assert root.find("at") is None and root.find("locked") is None


def test_altium_library_undoes_board_rotation_and_bottom_mirror() -> None:
    import dataclasses

    from fenolite.backends.kicad.layers import flip_layer
    from fenolite.backends.kicad.mod import read_footprint
    from fenolite.convert.direction import Options
    from fenolite.convert.sources import read_source
    from fenolite.convert.to_kicad import write_altium
    from fenolite.core.coords import Point

    source = read_source(ROOT / "tests/data/altium/blink/blink.PrjPcb")
    assert source.design.board is not None
    fp = source.design.board.footprints[0]
    pads = tuple(
        dataclasses.replace(
            p,
            position=Point(p.position.x, -p.position.y),
            rotation=(-p.rotation) % 360000000,
            layers=tuple(flip_layer(layer) for layer in p.layers),
        )
        for p in fp.pads
    )
    mirrored = dataclasses.replace(fp, rotation=90000000, side="bottom", pads=pads)
    design = dataclasses.replace(
        source.design,
        board=dataclasses.replace(
            source.design.board, footprints=(mirrored, *source.design.board.footprints[1:])
        ),
    )
    result = write_altium(dataclasses.replace(source, design=design), Options())
    pattern = fp.lib_ref.rsplit(":", 1)[-1]
    actual = read_footprint(result.files[f"{source.name}.pretty/{pattern}.kicad_mod"].decode())
    assert [p.position for p in actual.pads] == [p.position for p in fp.pads]
    assert [p.rotation % 180000000 for p in actual.pads] == [p.rotation % 180000000 for p in fp.pads]
