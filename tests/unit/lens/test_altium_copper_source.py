# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper sources of the Altium build (change c0038, capability altium-build, "Script copper in an Altium
build", "Copper from a routed KiCad board" and "Copper issue codes").

A ``CopperSource`` is a model with placed footprints and copper. Here it is the KiCad build of the routed
sample's script in memory with the sample's copper put into its model: what change c0028 hands over as
script copper. The same model stands for a routed board when its origin is ``board``. ``match_source``
checks it against the script's design before any copper is written, and the source's placements win.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from functools import cache
from pathlib import Path

import pytest
from _altium import blink_tree
from _altium_copper import at, routed_build, routed_design, routed_kicad_design, routed_model
from _altium_pcb_read import read_pcbdoc

from fenolite.core.errors import Issue
from fenolite.dsl import to_model
from fenolite.lens.altium import CopperSource, match_source
from fenolite.lens.build import BuildOutput
from fenolite.model.board import Graphic, Hole, Keepout, Text
from fenolite.model.design import Design

BOARD = "routed.kicad_pcb"
MISMATCH = "altium.copper-board-mismatch"


@cache
def kicad() -> Design:
    return routed_kicad_design()


def script(board: str = "design.board(mm(50), mm(30), copper=4)", old: str = "", new: str = "") -> Design:
    design = routed_design(board)
    if old:
        from _altium_copper import routed_script

        source = routed_script(board)
        assert old in source, old
        namespace: dict[str, object] = {}
        exec(compile(source.replace(old, new), "design.py", "exec"), namespace)  # noqa: S102
        design = namespace["design"]  # type: ignore[assignment]
    return to_model(design)


def build(root: Path, source: CopperSource, model: Design | None = None, **kwargs: object) -> BuildOutput:
    return routed_build(root, script() if model is None else model, copper_source=source, **kwargs)


def errors(output: BuildOutput) -> list[Issue]:
    return [found for found in output.issues if found.severity == "error"]


def board_of(design: Design, **changes: object) -> Design:
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, **changes))  # type: ignore[arg-type]


def ref_of(design: Design) -> dict[str, str]:
    return {component.id: component.ref for component in design.circuit.components}


def edit_footprint(design: Design, ref: str, edit: Callable[[object], object]) -> Design:
    assert design.board is not None
    refs = ref_of(design)
    footprints = tuple(edit(f) if refs[f.component_id] == ref else f for f in design.board.footprints)
    return board_of(design, footprints=footprints)


# --- the script source ------------------------------------------------------------------------------


def test_source_of_origin_script_is_written(tmp_path: Path) -> None:
    output = build(tmp_path, CopperSource(kicad(), "script"))
    assert not errors(output) and "routed.PcbDoc" in output.files
    copper = output.summary["copper"]
    assert isinstance(copper, dict)
    assert (copper["source"], copper["from"], copper["placements_from_board"]) == ("script", None, 0)
    assert [copper[key] for key in ("layers", "tracks", "arcs", "vias", "zones")] == [4, 5, 1, 3, 2]
    codes = {found.code for found in output.issues}
    assert "altium.placement-from-board" not in codes and "altium.pcb-staged" not in codes
    assert "altium.zones-unpoured" in codes
    doc = read_pcbdoc(output.files["routed.PcbDoc"])
    assert len(doc.free_tracks) == 5 and len(doc.vias) == 3 and len(doc.polygons) == 2


def test_source_origin_is_script_or_board() -> None:
    with pytest.raises(ValueError, match="script or board, not 'model'"):
        CopperSource(kicad(), "model")  # type: ignore[arg-type]
    assert CopperSource(kicad(), "script").label == "script copper: "
    assert CopperSource(kicad(), "board", "a/b.kicad_pcb").label == "a/b.kicad_pcb: "


def test_two_sources_refused(tmp_path: Path) -> None:
    """Scenario "Two sources refused"."""
    with pytest.raises(ValueError, match="two copper sources.*model source.*origin script"):
        routed_build(tmp_path, routed_model(), copper_source=CopperSource(kicad(), "script"))


def test_source_without_a_document(tmp_path: Path) -> None:
    """Scenario "Source without a document"."""
    output = build(tmp_path, CopperSource(kicad(), "board", BOARD), dataclasses.replace(script(), board=None))
    (found,) = [i for i in output.issues if i.code == "altium.copper-no-document"]
    assert (
        found.severity == "error"
        and BOARD in found.message
        and "routed.PcbDoc is not planned" in found.message
    )
    assert output.files == {}


def test_source_of_another_script_refused(tmp_path: Path) -> None:
    """Scenario "Source of another script refused": the script's ``R1`` has another footprint."""
    other = script(old='footprint="Mini:Mini_R_0603"', new='footprint="Mini:Mini_LED_THT_3mm"')
    output = build(tmp_path, CopperSource(kicad(), "script"), other)
    assert output.files == {}
    (found,) = errors(output)
    assert found.code == MISMATCH and found.where == "R1"
    assert "Mini:Mini_R_0603" in found.message and "Mini:Mini_LED_THT_3mm" in found.message
    assert found.message.startswith("script copper: ")


# --- placements ---------------------------------------------------------------------------------------


def test_source_placements_win(tmp_path: Path) -> None:
    """A part moved on the board is written where the board places it, with one info naming it."""
    moved = edit_footprint(
        kicad(), "R1", lambda f: dataclasses.replace(f, position=at(33, 10), rotation=90_000_000)
    )
    output = build(tmp_path, CopperSource(moved, "board", BOARD))
    assert not errors(output)
    (info,) = [i for i in output.issues if i.code == "altium.placement-from-board"]
    assert (
        info.severity == "info"
        and "R1" in info.message
        and "U1" not in info.message
        and BOARD in info.message
    )
    doc = read_pcbdoc(output.files["routed.PcbDoc"])
    (record,) = [c for c in doc.components if c["SOURCEDESIGNATOR"] == "R1"]
    assert (record["X"], record["Y"]) == (
        "2299.2126mil",
        "1787.4016mil",
    )  # 33 mm right, 20 mm up, plus 1000 mil
    assert record["ROTATION"] == " 9.00000000000000E+0001"
    assert output.summary["copper"]["placements_from_board"] == 3  # type: ignore[index]
    unmoved = build(tmp_path, CopperSource(kicad(), "board", BOARD))
    assert "altium.placement-from-board" not in {i.code for i in unmoved.issues}
    assert unmoved.summary["copper"]["from"] == BOARD  # type: ignore[index]


def test_source_places_a_part_the_script_does_not_place(tmp_path: Path) -> None:
    model = script(old="r1.place(mm(32), mm(9))", new="")
    output = routed_build(
        tmp_path, model, copper_source=CopperSource(kicad(), "board", BOARD), placements={}, placed=()
    )
    assert not errors(output) and "altium.pcb-staged" not in {i.code for i in output.issues}
    (info,) = [i for i in output.issues if i.code == "altium.placement-from-board"]
    assert all(ref in info.message for ref in ("D1", "R1", "U1"))


def test_source_matched_by_reference_without_the_path_property(tmp_path: Path) -> None:
    source = kicad()
    components = tuple(
        dataclasses.replace(c, properties={k: v for k, v in c.properties.items() if k != "fenolite.path"})
        for c in source.circuit.components
    )
    bare = dataclasses.replace(source, circuit=dataclasses.replace(source.circuit, components=components))
    output = build(tmp_path, CopperSource(bare, "board", BOARD))
    assert not errors(output) and output.summary["copper"]["placements_from_board"] == 3  # type: ignore[index]
    placements, _issues = match_source(output.design, CopperSource(bare, "board", BOARD), {})
    assert sorted(placements) == ["D1", "R1", "U1"]
    refs = ref_of(bare)
    assert bare.board is not None
    (r1,) = [f for f in bare.board.footprints if refs[f.component_id] == "R1"]
    assert (placements["R1"].at, placements["R1"].side) == (r1.position, "top")


# --- mismatches ---------------------------------------------------------------------------------------


def mismatch(tmp_path: Path, source: Design, model: Design | None = None) -> list[Issue]:
    output = build(tmp_path, CopperSource(source, "board", BOARD), model)
    assert output.files == {}
    found = errors(output)
    assert found and all(BOARD in i.message for i in found), [i.message for i in found]
    return found


def test_mismatch_of_a_missing_component(tmp_path: Path) -> None:
    source = kicad()
    assert source.board is not None
    refs = ref_of(source)
    without = board_of(
        source, footprints=tuple(f for f in source.board.footprints if refs[f.component_id] != "D1")
    )
    (found,) = mismatch(tmp_path, without)
    assert (found.code, found.where) == (MISMATCH, "D1") and "has no footprint" in found.message


def test_mismatch_of_a_footprint_the_design_does_not_hold(tmp_path: Path) -> None:
    source = kicad()
    assert source.board is not None
    refs = ref_of(source)
    (d1,) = [c for c in source.circuit.components if c.ref == "D1"]
    extra_component = dataclasses.replace(
        d1, id="cmp_00000000-0000-4000-8000-000000000001", ref="H1", properties={"fenolite.path": "H1"}
    )
    (fp,) = [f for f in source.board.footprints if refs[f.component_id] == "D1"]
    extra = dataclasses.replace(
        fp,
        id="fp_00000000-0000-4000-8000-000000000001",
        component_id=extra_component.id,
        position=at(45, 5),
        pads=(),
    )
    circuit = dataclasses.replace(source.circuit, components=(*source.circuit.components, extra_component))
    grown = board_of(
        dataclasses.replace(source, circuit=circuit), footprints=(*source.board.footprints, extra)
    )
    (found,) = mismatch(tmp_path, grown)
    assert (found.code, found.where) == (MISMATCH, "H1") and "no component in the design" in found.message


def test_mismatch_of_two_footprints_for_one_component(tmp_path: Path) -> None:
    source = kicad()
    assert source.board is not None
    refs = ref_of(source)
    (fp,) = [f for f in source.board.footprints if refs[f.component_id] == "R1"]
    twin = dataclasses.replace(fp, id="fp_00000000-0000-4000-8000-000000000002", position=at(40, 5))
    (found,) = mismatch(tmp_path, board_of(source, footprints=(*source.board.footprints, twin)))
    assert (found.code, found.where) == (MISMATCH, "R1") and "matches 2 footprints" in found.message


def test_mismatch_of_pad_positions(tmp_path: Path) -> None:
    def shift(footprint: object) -> object:
        first, *rest = footprint.pads  # type: ignore[attr-defined]
        pad = dataclasses.replace(
            first, position=dataclasses.replace(first.position, x=first.position.x + 50_000)
        )
        return dataclasses.replace(footprint, pads=(pad, *rest))  # type: ignore[type-var]

    (found,) = mismatch(tmp_path, edit_footprint(kicad(), "R1", shift))
    assert (found.code, found.where) == (
        MISMATCH,
        "R1",
    ) and "the pads of Mini:Mini_R_0603 differ" in found.message
    assert "(pad 1)" in found.message


def test_mismatch_of_a_pad_net(tmp_path: Path) -> None:
    source = kicad()
    gnd = next(net.id for net in source.circuit.nets if net.name == "GND")

    def rewire(footprint: object) -> object:
        pads = tuple(
            dataclasses.replace(pad, net_id=gnd) if pad.number == "2" else pad
            for pad in footprint.pads  # type: ignore[attr-defined]
        )
        return dataclasses.replace(footprint, pads=pads)  # type: ignore[type-var]

    (found,) = mismatch(tmp_path, edit_footprint(source, "R1", rewire))
    assert (found.code, found.where) == (MISMATCH, "R1.2")
    assert "is on GND there, the design puts it on LED_A" in found.message

    def unwire(footprint: object) -> object:
        pads = tuple(dataclasses.replace(pad, net_id=None) for pad in footprint.pads)  # type: ignore[attr-defined]
        return dataclasses.replace(footprint, pads=pads)  # type: ignore[type-var]

    found_two = mismatch(tmp_path, edit_footprint(source, "R1", unwire))
    assert [i.where for i in found_two] == ["R1.1", "R1.2"] and "is on no net there" in found_two[0].message


def test_mismatch_of_the_outline(tmp_path: Path) -> None:
    source = kicad()
    assert source.board is not None and source.board.outline is not None
    points = source.board.outline.points
    wider = dataclasses.replace(
        source.board.outline, points=(*points[:1], at(60, 0), at(60, 30), *points[3:])
    )
    (found,) = mismatch(tmp_path, board_of(source, outline=wider))
    assert (found.code, found.where) == (MISMATCH, "outline")
    assert "60 x 30 mm" in found.message and "50 x 30 mm" in found.message
    edges = tuple(
        Graphic(
            id=f"gfx_00000000-0000-4000-8000-00000000000{n}", kind="line", layer="Edge.Cuts", points=(a, b)
        )
        for n, (a, b) in enumerate(zip(points, (*points[1:], points[0]), strict=True))
    )
    drawn = board_of(source, outline=None, graphics=edges)
    assert not errors(build(tmp_path, CopperSource(drawn, "board", BOARD)))
    assert [i.where for i in mismatch(tmp_path, board_of(source, outline=None))] == ["outline"]


def test_source_copper_on_a_net_the_design_does_not_hold(tmp_path: Path) -> None:
    source = kicad()
    assert source.board is not None
    extra = dataclasses.replace(
        source.circuit.nets[0], id="net_00000000-0000-4000-8000-000000000009", name="EXTRA", members=()
    )
    first, second, *tracks = source.board.tracks
    renamed = board_of(
        dataclasses.replace(
            source, circuit=dataclasses.replace(source.circuit, nets=(*source.circuit.nets, extra))
        ),
        tracks=(
            dataclasses.replace(first, net_id=extra.id),
            dataclasses.replace(second, net_id=extra.id),
            *tracks,
        ),
    )
    (found,) = mismatch(tmp_path, renamed)
    assert (found.code, found.where) == ("altium.copper-net-missing", "EXTRA")
    assert "2 item(s) on the net EXTRA" in found.message
    assert "track on F.Cu at (9.85, 12.2) mm" in found.message


def test_source_copper_follows_the_copper_codes(tmp_path: Path) -> None:
    """Via types, layers and planes of a source give the same codes, with the board's path."""
    source = kicad()
    assert source.board is not None
    blind = dataclasses.replace(source.board.vias[0], via_type="blind", layers=("F.Cu", "In1.Cu"))
    (found,) = mismatch(tmp_path, board_of(source, vias=(blind, *source.board.vias[1:])))
    assert found.code == "altium.via-unsupported" and "blind" in found.message
    two_layers = build(
        tmp_path, CopperSource(source, "board", BOARD), script("design.board(mm(50), mm(30))"), copper=2
    )
    layer_errors = errors(two_layers)
    assert {i.code for i in layer_errors} == {"altium.copper-layer"} and len(layer_errors) == 3
    assert all(BOARD in i.message for i in layer_errors) and two_layers.files == {}
    assert any("In1.Cu" in i.message for i in layer_errors) and any(
        "In2.Cu" in i.message for i in layer_errors
    )


def test_source_zone_on_a_plane_is_left_to_the_plane(tmp_path: Path) -> None:
    source = kicad()
    assert source.board is not None
    tracks = tuple(track for track in source.board.tracks if track.layer != "In1.Cu")
    output = build(
        tmp_path, CopperSource(board_of(source, tracks=tracks), "board", BOARD), planes={"In1.Cu": "GND"}
    )
    assert not errors(output)
    (merged,) = [i for i in output.issues if i.code == "altium.plane-zone-merged"]
    assert "the GND zone on In1.Cu" in merged.message
    assert output.summary["copper"]["planes"] == {"In1.Cu": "GND"}  # type: ignore[index]
    assert output.summary["copper"]["zones"] == 1  # type: ignore[index]


def test_source_items_that_are_not_copied(tmp_path: Path) -> None:
    source = kicad()
    assert source.board is not None
    zone = source.board.zones[0]
    extras = board_of(
        source,
        keepouts=(
            Keepout(id="kpo_00000000-0000-4000-8000-000000000001", outline=zone.outline, layers=("F.Cu",)),
        ),
        texts=(
            Text(
                id="txt_00000000-0000-4000-8000-000000000001",
                text="REV A",
                position=at(5, 5),
                layer="F.SilkS",
                size=source.board.footprints[0].pads[0].size,
                thickness=150_000,
            ),
        ),
        graphics=(
            Graphic(
                id="gfx_00000000-0000-4000-8000-000000000009",
                kind="line",
                layer="F.SilkS",
                points=(at(1, 1), at(2, 1)),
            ),
        ),
        holes=(Hole(id="hol_00000000-0000-4000-8000-000000000001", position=at(3, 3), drill=3_000_000),),
    )
    output = build(tmp_path, CopperSource(extras, "board", BOARD))
    found = [i for i in output.issues if i.code == "altium.not-lowered" and i.where == BOARD]
    assert [i.message.split(": ")[1] for i in found] == [
        "1 keep-outs are not copied",
        "1 texts are not copied",
        "1 graphics are not copied",
        "1 holes are not copied",
    ]
    assert all(i.severity == "info" for i in found) and not errors(output)


def test_source_tree_helper_is_the_blink_tree(tmp_path: Path) -> None:
    """The source tests resolve the footprints through the blink folder's own tables."""
    project = blink_tree(tmp_path)
    assert (project / "fp-lib-table").is_file()


# --- the three sources give the same document (change c0038, task 6.3) -------------------------------


def from_board(root: Path, edit: Callable[[Design], Design] | None = None) -> BuildOutput:
    """The build whose copper is read back from the sample's routed ``.kicad_pcb`` text."""
    from _altium_copper import routed_board_text

    from fenolite.backends.kicad.pcb import read_board

    board = read_board(routed_board_text(edit), file=BOARD, issues=[])
    return build(root, CopperSource(board, "board", BOARD))


def test_script_source_gives_the_bytes_of_the_model_source(tmp_path: Path) -> None:
    """Scenario "Script source equals the committed sample", against a build of the routed model; task 8.3
    compares both with the committed file."""
    model = routed_build(tmp_path)
    by_script = build(tmp_path, CopperSource(kicad(), "script"))
    assert not errors(by_script) and by_script.summary["copper"]["source"] == "script"  # type: ignore[index]
    assert by_script.files["routed.PcbDoc"] == model.files["routed.PcbDoc"]
    for name in ("routed.PcbLib", "routed.SchDoc", "routed.SchLib", "routed.PrjPcb"):
        assert by_script.files[name] == model.files[name], name


def test_three_sources_give_equal_bytes(tmp_path: Path) -> None:
    """The same copper gives the same ``routed.PcbDoc`` from the model, the script source and the board."""
    model = routed_build(tmp_path).files["routed.PcbDoc"]
    by_script = build(tmp_path, CopperSource(kicad(), "script")).files["routed.PcbDoc"]
    board = from_board(tmp_path)
    assert not errors(board) and "altium.placement-from-board" not in {i.code for i in board.issues}
    assert board.summary["copper"]["source"] == "board"  # type: ignore[index]
    assert model == by_script == board.files["routed.PcbDoc"]


def test_equal_bytes_do_not_depend_on_the_ids_of_the_board(tmp_path: Path) -> None:
    """Other uuids on the board's copper (a board saved again by KiCad) give the same document."""
    import re

    from _altium_copper import routed_board_text

    from fenolite.backends.kicad.pcb import read_board

    text = routed_board_text()
    count = 0

    def renumber(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f'(uuid "{count:08x}-0000-4000-8000-000000000000")'

    head, copper = text[: text.index("(segment")], text[text.index("(segment") :]
    other = head + re.sub(r'\(uuid "[0-9a-f-]{36}"\)', renumber, copper)
    assert count == 10 and other != text  # five tracks, the arc, three vias, the zone
    again = build(tmp_path, CopperSource(read_board(other, file=BOARD, issues=[]), "board", BOARD))
    assert again.files["routed.PcbDoc"] == from_board(tmp_path).files["routed.PcbDoc"]
