# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The directions to KiCad (capability design-conversion): from KiCad ("KiCad to KiCad direction"; changes
c0159 and c0162) and from Altium ("Altium to KiCad direction", "Layers of a converted Altium board",
"Keep-out outlines of a converted Altium board" and "Slots of a converted Altium board"; change c0161)."""

from __future__ import annotations

import dataclasses
import json
import shutil
from functools import cache
from pathlib import Path

import pytest
from _convert import BLINK_T9, BLINK_T10, TWO_LAYER

from fenolite.api.conversion import convert
from fenolite.backends.kicad.layers import USER_LAYERS, flip_layer
from fenolite.backends.kicad.pcb import undeclared_layers, write_board
from fenolite.convert import LossyConversionError, convert_project, from_altium
from fenolite.convert.from_altium import footprint_name, keepout_rings, lower_board
from fenolite.convert.kicad_project import derived_library, footprint_key, generic_symbols
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.base import ExtBag
from fenolite.model.board import Graphic, Layer, Pad, Padstack
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
WITH_SHEET = ROOT / "tests" / "data" / "kicad" / "parity" / "agree"
TOKENS = ROOT / "tests" / "data" / "kicad" / "tokens"


def test_downgrade_needs_consent_for_design_rows() -> None:
    """Change c0162 (it replaces c0159's "Older target refused"): a board of KiCad 10 is written for 9, and
    the keys every KiCad 10 project holds (component classes, tuning profiles) are ``design`` rows of the
    resolver, a loss that needs consent."""
    with pytest.raises(LossyConversionError) as refused:
        convert_project(BLINK_T10, to="kicad", kicad_version=9)
    assert set(refused.value.report.refused) == {
        "downgrade:project:/component_class_settings",
        "downgrade:project:/net_settings/classes/*/tuning_profile",
        "downgrade:project:/tuning_profiles",
    }


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
    lost = conversion.report.row("downgrade:project:/tuning_profiles")
    assert lost is not None and lost.lost == 1 and lost.loss == "refuse"
    assert lost.reasons[0].ids == ("blink.kicad_pro:/tuning_profiles",)
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


# --- Altium to KiCad (change c0161) --------------------------------------------------------------------

ALTIUM_BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
ALTIUM_BOARD = ALTIUM_BLINK.with_suffix(".PcbDoc")
MM = 1_000_000
KIPRJMOD = "${KIPRJMOD}"


@cache
def _altium_design() -> Design:
    return read_source(ALTIUM_BOARD).design


def _layer(name: str, kind: str, ordinal: int, altium_name: str = "") -> Layer:
    pairs = (("altium_name", altium_name),) if altium_name else ()
    return Layer(
        id=derived_id("lay", "altium", name),
        name=name,
        kind=kind,  # type: ignore[arg-type]
        ordinal=ordinal,
        ext={"altium": ExtBag(None, pairs)} if pairs else {},
    )


def _line(layer: str, a: Point, b: Point, n: int) -> Graphic:
    return Graphic(
        id=derived_id("gfx", "test", f"{layer}:{n}"), kind="line", layer=layer, points=(a, b), width=MM // 10
    )


def _with_items(*graphics: Graphic, layers: tuple[Layer, ...] = ()) -> Design:
    design = _altium_design()
    assert design.board is not None
    board = dataclasses.replace(
        design.board, layers=(*design.board.layers, *layers), graphics=(*design.board.graphics, *graphics)
    )
    return dataclasses.replace(design, board=board)


def test_layers_rows_and_map() -> None:
    """Scenario "Mechanical layers": ``Mech.<n>`` on ``User.<n>`` with the Altium name as the user name,
    ``Altium.<id>`` and the drill layers lost with their reasons, the full table of KiCad declared."""
    extra = (
        _layer("Mech.1", "mechanical", 157, "Board Shape"),
        _layer("Mech.2", "mechanical", 158, "Fab Notes"),
        _layer("Altium.74", "user", 174),
        _layer("Altium.DrillDrawing", "user", 173),
    )
    design = _with_items(
        _line("Mech.1", Point(0, 0), Point(MM, 0), 1),
        _line("Mech.2", Point(0, 0), Point(MM, 0), 2),
        _line("Altium.74", Point(0, 0), Point(MM, 0), 3),
        _line("Altium.DrillDrawing", Point(0, 0), Point(MM, 0), 4),
        layers=extra,
    )
    lowered = lower_board(design, project="blink", target=10)
    board = lowered.design.board
    assert board is not None
    assert undeclared_layers(board) == {}
    rows = {layer.name: dict(layer.ext["kicad"].payload) for layer in board.layers}
    assert rows["User.1"] == {"number": "39", "type": "user", "user_name": "Board Shape"}
    assert rows["User.2"] == {"number": "41", "type": "user", "user_name": "Fab Notes"}
    assert {"F.Fab", "B.CrtYd", "Edge.Cuts", "Margin"} <= set(rows)
    layers_of = {g.id: g.layer for g in board.graphics}
    assert layers_of[derived_id("gfx", "test", "Mech.1:1")] == "User.1"
    assert layers_of[derived_id("gfx", "test", "Mech.2:2")] == "User.2"
    lost = lowered.items(lowered.lost)["graphic"]
    assert lost[from_altium.REASON_OUTSIDE] == (derived_id("gfx", "test", "Altium.74:3"),)
    assert lost[from_altium.REASON_DRILL] == (derived_id("gfx", "test", "Altium.DrillDrawing:4"),)
    write_board(lowered.design, target=10)


def test_layers_beyond_the_user_layers_are_lost() -> None:
    """Decided by the maintainer on 2026-10-09: a mechanical layer beyond KiCad's user layers is lost,
    never merged onto the last one."""
    beyond = USER_LAYERS[9] + 1
    design = _with_items(
        _line(f"Mech.{beyond}", Point(0, 0), Point(MM, 0), 1),
        layers=(_layer(f"Mech.{beyond}", "mechanical", 200),),
    )
    lowered = lower_board(design, project="blink", target=9)
    assert lowered.items(lowered.lost)["graphic"] == {
        from_altium.REASON_MECH: (derived_id("gfx", "test", f"Mech.{beyond}:1"),)
    }
    assert lowered.design.board is not None
    assert f"User.{beyond}" not in {layer.name for layer in lowered.design.board.layers}


@pytest.mark.parametrize("copper", [2, 3, 4, 5, 32])
def test_layers_copper_counts(copper: int) -> None:
    """Even counts keep their rows; an odd count gets one empty inner layer before ``B.Cu``, counted
    ``changed`` under ``stackup``."""
    design = _altium_design()
    assert design.board is not None
    names = ["F.Cu", *(f"In{k}.Cu" for k in range(1, copper - 1)), "B.Cu"]
    others = [layer for layer in design.board.layers if layer.kind != "copper"]
    layers = tuple(_layer(name, "copper", i) for i, name in enumerate(names)) + tuple(others)
    board = dataclasses.replace(design.board, layers=layers, stackup=None)
    lowered = lower_board(dataclasses.replace(design, board=board), project="blink", target=10)
    assert lowered.design.board is not None
    copper_rows = [layer.name for layer in lowered.design.board.layers if layer.kind == "copper"]
    assert len(copper_rows) == copper + copper % 2 and copper_rows[0] == "F.Cu"
    assert ("stackup" in lowered.items(lowered.changed)) == bool(copper % 2)


def test_layers_odd_count_with_a_stackup() -> None:
    """The empty inner layer of an odd count takes a copy of the last dielectric and copper sheet, so the
    stack-up names the copper of the table and is written."""
    design = _altium_design()
    assert design.board is not None and design.board.stackup is not None
    copper = [e for e in design.board.stackup.layers if e.kind == "copper"]
    entries = list(design.board.stackup.layers)
    index = entries.index(copper[-1])
    dielectric = next(e for e in entries if e.kind == "dielectric")
    middle = dataclasses.replace(copper[-1], id="sly_mid", name="In1.Cu")
    entries[index:index] = [middle, dataclasses.replace(dielectric, id="sly_d2")]
    names = ["F.Cu", "In1.Cu", "B.Cu"]
    others = [layer for layer in design.board.layers if layer.kind != "copper"]
    layers = tuple(_layer(name, "copper", i) for i, name in enumerate(names)) + tuple(others)
    stackup = dataclasses.replace(design.board.stackup, layers=tuple(entries))
    board = dataclasses.replace(design.board, layers=layers, stackup=stackup)
    lowered = lower_board(dataclasses.replace(design, board=board), project="blink", target=10)
    assert lowered.design.board is not None and lowered.design.board.stackup is not None
    stacked = [e.name for e in lowered.design.board.stackup.layers if e.kind == "copper"]
    assert stacked == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    assert "(stackup" in write_board(lowered.design, target=10).text


def test_keepout_outlines_become_rule_areas() -> None:
    """Scenario "Mechanical and keep-out layers": a closed ring of lines on ``Altium.KeepOut``, with ends
    a few nanometres apart, is a rule area on every copper layer that keeps out tracks, vias and copper
    pour; an open line is lost with its reason (S-0742, ``H-A-IMP-KEEPOUT-LAYER``)."""
    k = "Altium.KeepOut"
    ring = (
        _line(k, Point(0, 0), Point(10 * MM, 0), 1),
        _line(k, Point(10 * MM, 3), Point(10 * MM, 10 * MM), 2),
        _line(k, Point(10 * MM, 10 * MM), Point(0, 10 * MM), 3),
        _line(k, Point(0, 10 * MM), Point(0, 0), 4),
    )
    open_line = _line(k, Point(20 * MM, 0), Point(30 * MM, 0), 5)
    design = _with_items(*ring, open_line, layers=(_layer(k, "user", 156),))
    assert design.board is not None
    before = {area.id for area in design.board.keepouts}
    lowered = lower_board(design, project="blink", target=10)
    board = lowered.design.board
    assert board is not None
    (area,) = [a for a in board.keepouts if a.id not in before]
    assert area.no_tracks and area.no_vias and area.no_copper_pour and not area.no_footprints
    assert set(area.layers) == {layer.name for layer in board.layers if layer.kind == "copper"}
    assert len(area.outline) == 4
    changed = lowered.items(lowered.changed)
    assert len(changed["graphic"]["a keep-out outline is a rule area on every copper layer"]) == 4
    assert lowered.items(lowered.lost)["graphic"] == {from_altium.REASON_KEEPOUT_OPEN: (open_line.id,)}
    assert not [g for g in board.graphics if g.layer == k]
    assert "(keepout" in write_board(lowered.design, target=10).text


def test_keepout_rings_of_closed_shapes() -> None:
    k = "Altium.KeepOut"
    circle = Graphic(id="gfx_c", kind="circle", layer=k, points=(Point(0, 0), Point(MM, 0)))
    rect = Graphic(id="gfx_r", kind="rect", layer=k, points=(Point(0, 0), Point(MM, MM)))
    rings, left = keepout_rings([circle, rect])
    assert left == [] and len(rings) == 2
    assert rings[0][2] is True
    assert rings[1] == ((Point(0, 0), Point(MM, 0), Point(MM, MM), Point(0, MM)), ["gfx_r"], False)


def test_slot_frame_and_lost_pads() -> None:
    """Scenario "Round pad with a turned slot" through the lowering: the import's slot axis (the
    footprint's frame) becomes the pad's; a slot along an oval pad is kept, one turned against a
    rectangle is a lost pad with its reason."""
    design = _altium_design()
    assert design.board is not None
    fp = design.board.footprints[0]
    base = fp.pads[0]

    def slotted(shape: str, size: Size, rotation: int, axis: int, n: str) -> Pad:
        stack = Padstack(id=f"pst_{n}", hole_shape="slot", hole_length=3 * MM, hole_rotation=axis)
        return dataclasses.replace(
            base, id=f"{base.id}{n}", number=f"S{n}", kind="thru_hole", shape=shape, size=size,  # type: ignore[arg-type]
            rotation=rotation, drill=MM, padstack=stack, layers=("F.Cu", "B.Cu"),
        )  # fmt: skip

    along = slotted("oval", Size(4 * MM, 2 * MM), 45_000_000, 45_000_000, "1")
    round_pad = slotted("circle", Size(2 * MM, 2 * MM), 0, 45_000_000, "2")
    against = slotted("rect", Size(4 * MM, 2 * MM), 0, 45_000_000, "3")
    turned = dataclasses.replace(fp, pads=(*fp.pads, along, round_pad, against))
    board = dataclasses.replace(design.board, footprints=(turned, *design.board.footprints[1:]))
    lowered = lower_board(dataclasses.replace(design, board=board), project="blink", target=10)
    assert lowered.design.board is not None
    pads = {p.number: p for p in lowered.design.board.footprints[0].pads}
    assert pads["S1"].padstack is not None and pads["S1"].padstack.hole_rotation == 0
    assert pads["S2"].padstack is not None and pads["S2"].padstack.hole_rotation == 45_000_000
    assert "S3" not in pads
    assert lowered.items(lowered.lost)["pad"] == {from_altium.REASON_SLOT: (against.id,)}
    write_board(lowered.design, target=10)


def test_names_footprints_and_nets() -> None:
    """Footprints are named ``<project>:<name>``; a name with a character a KiCad name cannot hold is
    written with ``_``; a net whose stored form another net holds is renamed, ``changed``."""
    assert footprint_name("Lib/A:SOT-23/5") == "SOT-23_5"
    assert footprint_name("R 0603") == "R 0603"
    design = _altium_design()
    assert design.board is not None
    first, second = design.circuit.nets[0], design.circuit.nets[1]
    nets = (
        dataclasses.replace(first, name="A/B"),
        dataclasses.replace(second, name="A{slash}B"),
        *design.circuit.nets[2:],
    )
    lowered = lower_board(
        dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, nets=nets)),
        project="blink",
        target=10,
    )
    assert lowered.design.board is not None
    assert {fp.lib_ref.partition(":")[0] for fp in lowered.design.board.footprints if fp.lib_ref} == {"blink"}
    assert lowered.design.circuit.nets[1].name == "A{slash}B_2"
    assert lowered.items(lowered.changed)["net"] == {from_altium.REASON_NET: (second.id,)}


def test_library_derived_from_instances() -> None:
    """``<project>.pretty`` holds one footprint per name, from its first instance in reference order; a
    bottom instance is taken back to the library's frame."""
    conversion = convert_project(ALTIUM_BLINK, to="kicad")
    design = conversion.design
    assert design.board is not None
    mods = sorted(k for k in conversion.files if k.startswith("blink.pretty/"))
    names = {fp.lib_ref.partition(":")[2] for fp in design.board.footprints if fp.lib_ref}
    assert mods == sorted(f"blink.pretty/{name}.kicad_mod" for name in names)
    table = conversion.files["fp-lib-table"].decode("utf-8")
    assert '(name "blink")' in table and f"{KIPRJMOD}/blink.pretty" in table
    library = derived_library(design, "blink")
    fp = next(fp for fp in design.board.footprints if fp.side == "top")
    flipped = dataclasses.replace(
        fp,
        side="bottom",
        pads=tuple(
            dataclasses.replace(p, position=Point(p.position.x, -p.position.y),
                                rotation=(-p.rotation) % 360_000_000,
                                layers=tuple(flip_layer(n) for n in p.layers))
            for p in fp.pads
        ),
        graphics=tuple(
            dataclasses.replace(g, layer=flip_layer(g.layer),
                                points=tuple(Point(q.x, -q.y) for q in g.points))
            for g in fp.graphics
        ),
    )  # fmt: skip
    alone = derived_library(
        dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(flipped,))), "blink"
    )
    name = fp.lib_ref.partition(":")[2]
    mine, theirs = alone.definitions[name], library.definitions[name]
    assert footprint_key(mine.pads, mine.graphics) == footprint_key(theirs.pads, theirs.graphics)


def test_schematic_generated_with_generic_symbols() -> None:
    """The circuit becomes a schematic of the generator with a generic symbol per component, written in
    ``<project>.kicad_sym`` with its table; ``schematic`` is ``changed``."""
    conversion = convert_project(ALTIUM_BLINK, to="kicad")
    files = conversion.files
    assert "blink.kicad_sch" in files and "blink.kicad_sym" in files and "sym-lib-table" in files
    assert f"{KIPRJMOD}/blink.kicad_sym" in files["sym-lib-table"].decode("utf-8")
    row = conversion.report.row("schematic")
    assert row is not None and (row.source, row.changed, row.lost) == (1, 1, 0)
    sheet = files["blink.kicad_sch"].decode("utf-8")
    refs = {c.ref for c in conversion.design.circuit.components if c.ref and c.pins}
    assert all(f'"Reference" "{ref}"' in sheet for ref in refs)
    symbols = generic_symbols(conversion.design, "blink")
    for component in conversion.design.circuit.components:
        if component.pins:
            assert {p.number for p in symbols[component.id].pins} == {p.number for p in component.pins}


@pytest.mark.parametrize("target", [9, 10])
def test_altium_project_converted_and_verified(target: int) -> None:
    result = convert(ALTIUM_BLINK, to="kicad", kicad_version=target)
    assert result.conversion.profile == "altium-to-kicad"
    assert result.equivalence is not None and result.equivalence.equivalent
    assert result.unexplained == ()
    board = result.conversion.files["blink.kicad_pcb"].decode("utf-8")
    assert f'(generator_version "{target}.0")' in board
