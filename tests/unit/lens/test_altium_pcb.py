# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The PCB side of the Altium build (change c0035, capability altium-build, "Altium footprint sources",
"PCB library outputs"; capability altium-pcb-writer, "PCB library name"; altium-schematic-writer,
"Designator, comment and links")."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from _altium import (
    BLINK_DIR,
    HIER_BOARD_DIR,
    blink,
    blink_resolver,
    blink_tree,
    example,
    hier_board,
    sample,
)
from _altium_pcb_read import read_pcblib
from _cfb_read import deframe, read_compound

from fenolite.backends.altium.project import pcblib_name
from fenolite.backends.kicad.mod import read_footprint
from fenolite.dsl import placements, to_model
from fenolite.lens.altium import (
    build_altium,
    footprint_source,
    footprint_texts,
    kicad_footprint_ids,
    pad_extras,
)
from fenolite.lens.build import BuildOutput

LIBS = Path(__file__).resolve().parents[2] / "data" / "libs"
BLINK_NAMES = ["Mini_LED_THT_3mm", "Mini_QFP-32_7x7mm_P0.8mm", "Mini_R_0603"]


def records(data: bytes) -> list[dict[str, str]]:
    """The records of a binary schematic, each as ``{key: value}``."""
    return [dict(fields) for fields in deframe(read_compound(data)["FileHeader"])]


def build_blink(root: Path, *, text: str = "", new: str = "", **tree: object) -> BuildOutput:
    project = blink_tree(root, **tree)  # type: ignore[arg-type]
    design = blink(text, new) if text else blink()
    return build_altium(
        to_model(design),
        name=design.name,
        placed=tuple(placements(design)),
        resolver=blink_resolver(root, project),
    )


def test_pcblib_names() -> None:
    """Scenario "Names" of "PCB library name"."""
    assert pcblib_name("Mini:Mini_R_0603", design="blink") == "blink.PcbLib"
    assert pcblib_name("FenoliteSample.PcbLib:R0603", design="blink") == "FenoliteSample.PcbLib"
    assert pcblib_name("My.pcblib:X", design="blink") == "My.pcblib"
    for bad in ("R0603", ":X", "Lib:"):
        with pytest.raises(ValueError):
            pcblib_name(bad, design="blink")


def test_footprint_source() -> None:
    assert footprint_source("FenoliteSample.PcbLib:R0603") == "altium"
    assert footprint_source("x.PCBLIB:R") == "altium"
    assert footprint_source("Mini:Mini_R_0603") == "kicad"


def test_kicad_footprint_ids() -> None:
    assert kicad_footprint_ids(to_model(sample())) == ()
    assert kicad_footprint_ids(to_model(blink())) == ("Mini:Mini_LED_THT_3mm", "Mini:Mini_R_0603")


def test_pad_extras_of_the_mini_footprints() -> None:
    qfp = read_footprint(LIBS / "Mini_v9.pretty" / "Mini_QFP-32_7x7mm_P0.8mm.kicad_mod", library="Mini")
    extras = pad_extras(qfp)
    assert {e.corner_ratio for e in extras.values()} == {Decimal("0.25")}
    assert all(e.refusal is None and e.dropped == () for e in extras.values())
    led = read_footprint(LIBS / "Mini_v9.pretty" / "Mini_LED_THT_3mm.kicad_mod", library="Mini")
    assert {e.corner_ratio for e in pad_extras(led).values()} == {None}
    r = read_footprint(LIBS / "Mini_v9.pretty" / "Mini_R_0603.kicad_mod", library="Mini")
    assert footprint_texts(r) == 1 and footprint_texts(led) == 0


def test_pad_extras_refusals_and_drops(tmp_path: Path) -> None:
    source = (LIBS / "Mini_v9.pretty" / "Mini_LED_THT_3mm.kicad_mod").read_text(encoding="utf-8")
    text = source.replace("(drill 0.9)", "(drill oval 0.9 1.2)", 1).replace(
        "(remove_unused_layers no)", "(remove_unused_layers no)\n\t\t(solder_mask_margin 0.1)", 1
    )
    path = tmp_path / "x.kicad_mod"
    path.write_text(text, encoding="utf-8")
    defn = read_footprint(path, library="X")
    first, second = (pad_extras(defn)[p.id] for p in defn.pads)
    assert first.refusal == "the drill is oval or has an offset"
    assert first.dropped == ("solder mask margin",) and second == type(second)()


def test_sample_reads_no_footprint_library() -> None:
    """Scenario "Sample reads no footprint library": Altium links only, no PCB file."""
    output = build_altium(to_model(sample()), name="altium_sample")
    assert not [p for p in output.files if p.endswith((".PcbLib", ".PcbDoc"))]
    assert "altium.footprint-unresolved" not in {i.code for i in output.issues}
    assert output.summary["footprints"] == 0


def test_library_of_the_blink_build(tmp_path: Path) -> None:
    """Scenario "Library of the KiCad-footprint sample"."""
    output = build_blink(tmp_path)
    lib = read_pcblib(output.files["blink.PcbLib"])
    assert sorted(lib.footprints) == BLINK_NAMES
    assert output.summary["footprints"] == 3
    assert output.summary["libraries"] == ["blink.PcbLib", "blink.SchLib"]
    assert b"DocumentPath=blink.PcbLib" in output.files["blink.PrjPcb"]
    dropped = [i for i in output.issues if i.code == "altium.primitive-dropped"]
    assert len(dropped) == 1 and "Mini_QFP-32_7x7mm_P0.8mm" in dropped[0].message
    assert "filled polygon" in dropped[0].message


def test_unresolved_footprints_warn() -> None:
    """Scenario "Unresolved footprints warn": the c0034 example names a library with no table."""
    design = example()
    with tempfile.TemporaryDirectory() as folder:
        from _altium import example_resolver

        output = build_altium(to_model(design), name=design.name, resolver=example_resolver(Path(folder)))
    found = [i for i in output.issues if i.code == "altium.footprint-unresolved"]
    links = sorted({c.lib_footprint_ref for c in output.design.circuit.components if c.lib_footprint_ref})
    assert sorted(i.where for i in found) == links and all(i.severity == "warning" for i in found)
    assert not [i for i in output.issues if i.code.startswith("kicad.lib.")]
    assert not [p for p in output.files if p.endswith((".PcbLib", ".PcbDoc"))]


def test_refused_footprint(tmp_path: Path) -> None:
    """Scenario "Refused footprint": the two other footprints are written."""
    output = build_blink(
        tmp_path, footprint=("Mini_R_0603", '(pad "1" smd roundrect', '(pad "1" smd trapezoid')
    )
    found = [i for i in output.issues if i.code == "altium.footprint-unsupported"]
    assert len(found) == 1 and "pad '1'" in found[0].message and "trapezoid" in found[0].message
    assert sorted(read_pcblib(output.files["blink.PcbLib"]).footprints) == BLINK_NAMES[:2]


def test_name_collision_writes_neither(tmp_path: Path) -> None:
    """Scenario "Name collision writes neither"."""
    row = (
        '(descr "Authored CC0 mini library"))',
        '(descr "Authored CC0 mini library"))\n\t(lib (name "Other") (type "KiCad") '
        '(uri "${KIPRJMOD}/../../tests/data/libs/Mini.pretty") (options "") (descr ""))',
    )
    output = build_blink(
        tmp_path,
        text="design.add(u1, r1, d1)",
        new='r2 = Part("R2", "Mini:Mini_R", footprint="Other:Mini_R_0603", value="1k")\n'
        "design.add(u1, r1, d1, r2)",
        fp_table=row,
    )
    found = [i for i in output.issues if i.code == "altium.footprint-name-collision"]
    assert (
        len(found) == 1 and "Mini:Mini_R_0603" in found[0].message and "Other:Mini_R_0603" in found[0].message
    )
    assert sorted(read_pcblib(output.files["blink.PcbLib"]).footprints) == BLINK_NAMES[:2]


def test_links_of_a_kicad_footprint(tmp_path: Path) -> None:
    """Scenarios "Links of a KiCad footprint" and "Unresolved KiCad footprint keeps its link"."""
    output = build_blink(tmp_path)
    found = records(output.files["blink.SchDoc"])
    models = [r for r in found if r.get("RECORD") == "45"]
    by_name = {r["MODELNAME"]: r for r in models}
    assert by_name["Mini_R_0603"]["MODELDATAFILEENTITY0"] == "Mini_R_0603"
    assert {r["MODELDATAFILE0"] for r in models} == {"blink.PcbLib"}
    design = blink('footprint="Mini:Mini_R_0603"', 'footprint="Nowhere:X"')
    unresolved = build_altium(to_model(design), name="board", resolver=blink_resolver(tmp_path / "other"))
    found = records(unresolved.files["board.SchDoc"])
    model = next(r for r in found if r.get("RECORD") == "45" and r["MODELNAME"] == "X")
    assert model["MODELDATAFILE0"] == "board.PcbLib"


def test_sample_links_unchanged() -> None:
    found = records(build_altium(to_model(sample()), name="altium_sample").files["altium_sample.SchDoc"])
    assert {r["MODELDATAFILE0"] for r in found if r.get("RECORD") == "45"} == {"FenoliteSample.PcbLib"}


# --- the PCB document in the build (task 4.4) ------------------------------------------------------


def build_blink_placed(root: Path, text: str = "", new: str = "", **kwargs: object) -> BuildOutput:
    project = blink_tree(root)
    design = blink(text, new) if text else blink()
    return build_altium(
        to_model(design),
        name=design.name,
        placed=tuple(placements(design)),
        placements=placements(design),
        resolver=blink_resolver(root, project),
        **kwargs,  # type: ignore[arg-type]
    )


def test_document_of_the_blink_build(tmp_path: Path) -> None:
    """Scenario "Document of the KiCad-footprint sample"."""
    from _altium_pcb_read import read_pcbdoc

    output = build_blink_placed(tmp_path)
    assert output.summary["pcb_document"] == "blink.PcbDoc"
    assert b"[Document2]\r\nDocumentPath=blink.PcbDoc\r\n" in output.files["blink.PrjPcb"]
    assert not [i for i in output.issues if i.code == "altium.not-lowered"]  # the document holds the class
    assert "altium.pcb-staged" not in {i.code for i in output.issues}
    doc = read_pcbdoc(output.files["blink.PcbDoc"])
    assert sorted(c["SOURCEDESIGNATOR"] for c in doc.components) == ["D1", "R1", "U1"]


def test_no_board_no_document(tmp_path: Path) -> None:
    """Scenario "No board, no document"."""
    output = build_blink_placed(tmp_path, "design.board(mm(50), mm(30))\n", "")
    assert "blink.PcbLib" in output.files and "blink.PcbDoc" not in output.files
    found = [i for i in output.issues if i.code == "altium.pcbdoc-not-written"]
    assert len(found) == 1 and "no board outline" in found[0].message
    assert output.summary["pcb_document"] is None


def test_unplaced_part_is_staged(tmp_path: Path) -> None:
    """Scenario "Unplaced part is staged": R1 lands where the KiCad build of the variant stages it."""
    from _altium_pcb_read import read_pcbdoc

    from fenolite.backends.altium.pcbrecords import mil_text, to_units
    from fenolite.lens.build import build_design

    text, new = "r1.place(mm(32), mm(9))", ""
    output = build_blink_placed(tmp_path, text, new)
    staged = [i for i in output.issues if i.code == "altium.pcb-staged"]
    assert len(staged) == 1 and "R1" in staged[0].message
    design = blink(text, new)
    kicad = build_design(
        to_model(design), placements(design), name="blink", copper=2, resolver=blink_resolver(tmp_path / "k")
    )
    assert kicad.design.board is not None and kicad.design.board.outline is not None
    by_id = {c.id: c.ref for c in kicad.design.circuit.components}
    (r1,) = [f for f in kicad.design.board.footprints if by_id[f.component_id] == "R1"]
    outline = kicad.design.board.outline.points
    x = to_units(r1.position.x - min(p.x for p in outline)) + 10_000_000
    y = to_units(max(p.y for p in outline) - r1.position.y) + 10_000_000
    doc = read_pcbdoc(output.files["blink.PcbDoc"])
    (record,) = [c for c in doc.components if c["SOURCEDESIGNATOR"] == "R1"]
    assert (record["X"], record["Y"]) == (mil_text(x), mil_text(y))
    assert record["LAYER"] == "TOP" and record["ROTATION"] == " 0.00000000000000E+0000"


# --- the PCB link of parts on module sheets (change c0037) -------------------------------------------


def build_hier_board(folder: Path, **kwargs: object) -> BuildOutput:
    design = hier_board()
    return build_altium(
        to_model(design),
        name=design.name,
        placed=tuple(placements(design)),
        placements=placements(design),
        resolver=blink_resolver(folder, HIER_BOARD_DIR),
        **kwargs,  # type: ignore[arg-type]
    )


def _schematic_ids(files: dict[str, bytes]) -> tuple[dict[str, str], dict[str, str]]:
    """(designator → component ``UNIQUEID``, sheet name → sheet symbol ``UNIQUEID``) of the binary sheets."""
    components: dict[str, str] = {}
    symbols: dict[str, str] = {}
    for name, data in files.items():
        if not name.endswith(".SchDoc"):
            continue
        rows = records(data)[1:]
        for row in rows:
            if row["RECORD"] == "34":
                components.setdefault(row["TEXT"], rows[int(row["OWNERINDEX"])]["UNIQUEID"])
            if row["RECORD"] == "32":
                symbols[row["TEXT"]] = rows[int(row["OWNERINDEX"])]["UNIQUEID"]
    return components, symbols


def test_hier_board_example_is_the_blink_circuit_in_two_modules() -> None:
    board, plain = to_model(hier_board()), to_model(blink())
    assert hier_board().name == "altium_hier_board"

    def parts(model: object) -> set[tuple[str, str, str, str]]:
        found = model.circuit.components  # type: ignore[attr-defined]
        return {(c.ref, c.lib_symbol_ref, c.lib_footprint_ref, c.value) for c in found}

    def nets(model: object) -> dict[str, set[tuple[str, str]]]:
        refs = {c.id: c.ref for c in model.circuit.components}  # type: ignore[attr-defined]
        return {n.name: {(refs[m.component_id], m.pin) for m in n.members} for n in model.circuit.nets}  # type: ignore[attr-defined]

    assert parts(board) == parts(plain) and nets(board) == nets(plain)
    assert board.board is not None and plain.board is not None
    assert board.board.outline == plain.board.outline
    paths = sorted(c.properties["fenolite.path"] for c in board.circuit.components)
    assert paths == ["driver/R1", "driver/U1", "led/D1"]
    wanted = {path.rsplit("/", 1)[-1]: request for path, request in placements(hier_board()).items()}
    assert wanted == dict(placements(blink()))
    for table in ("fp-lib-table", "sym-lib-table"):
        assert (HIER_BOARD_DIR / table).read_bytes() == (BLINK_DIR / table).read_bytes()


def test_link_of_a_part_on_a_module_sheet(tmp_path: Path) -> None:
    """Scenario "Link of a part on a module sheet"."""
    from _altium_pcb_read import read_pcbdoc

    from fenolite.backends.altium.project import unique_id

    output = build_hier_board(tmp_path, sheets="modules")
    assert not [i for i in output.issues if i.severity == "error"]
    assert output.summary["pcb_document"] == "altium_hier_board.PcbDoc"
    assert output.summary["sheets"] == [
        "altium_hier_board.SchDoc",
        "altium_hier_board_driver.SchDoc",
        "altium_hier_board_led.SchDoc",
    ]
    components, symbols = _schematic_ids(output.files)
    assert symbols == {"driver": unique_id("sheet:driver"), "led": unique_id("sheet:led")}
    doc = read_pcbdoc(output.files["altium_hier_board.PcbDoc"])
    by_ref = {c["SOURCEDESIGNATOR"]: c for c in doc.components}
    assert sorted(by_ref) == ["D1", "R1", "U1"]
    d1 = by_ref["D1"]
    assert d1["SOURCEUNIQUEID"] == f"\\{symbols['led']}\\{components['D1']}"
    assert d1["SOURCEHIERARCHICALPATH"] == "altium_hier_board\\led"
    for ref in ("R1", "U1"):
        assert by_ref[ref]["SOURCEUNIQUEID"] == f"\\{symbols['driver']}\\{components[ref]}"
        assert by_ref[ref]["SOURCEHIERARCHICALPATH"] == "altium_hier_board\\driver"
    assert b"DocumentPath=altium_hier_board.PcbDoc" in output.files["altium_hier_board.PrjPcb"]


def test_flat_links_are_unchanged(tmp_path: Path) -> None:
    """Scenario "Flat links are unchanged"."""
    from _altium_pcb_read import read_pcbdoc

    output = build_hier_board(tmp_path)
    components, symbols = _schematic_ids(output.files)
    assert symbols == {} and output.summary["sheet_mode"] == "flat"
    doc = read_pcbdoc(output.files["altium_hier_board.PcbDoc"])
    for record in doc.components:
        assert record["SOURCEUNIQUEID"] == "\\" + components[record["SOURCEDESIGNATOR"]]
        assert record["SOURCEHIERARCHICALPATH"] == ""


def test_hier_link_of_a_top_sheet_part_keeps_the_one_id_form(tmp_path: Path) -> None:
    """A part outside any module is on the top sheet: its link is the flat one in both modes."""
    from _altium_pcb_read import read_pcbdoc

    design = blink()
    for mode in ("flat", "modules"):
        output = build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            placements=placements(design),
            resolver=blink_resolver(tmp_path / mode),
            sheets=mode,  # type: ignore[arg-type]
        )
        doc = read_pcbdoc(output.files["blink.PcbDoc"])
        assert all(c["SOURCEHIERARCHICALPATH"] == "" for c in doc.components)
        assert all(c["SOURCEUNIQUEID"].count("\\") == 1 for c in doc.components)


def test_hier_board_pads_and_nets_do_not_depend_on_the_mode(tmp_path: Path) -> None:
    from _altium_pcb_read import read_pcbdoc

    flat = read_pcbdoc(build_hier_board(tmp_path / "f").files["altium_hier_board.PcbDoc"])
    split = read_pcbdoc(build_hier_board(tmp_path / "m", sheets="modules").files["altium_hier_board.PcbDoc"])
    assert flat.nets == split.nets and flat.pads == split.pads
    for before, after in zip(flat.components, split.components, strict=True):
        changed = {k for k in before if before[k] != after[k]}
        assert changed - {"CHANNELOFFSET"} == {"SOURCEUNIQUEID", "SOURCEHIERARCHICALPATH"}


def test_hier_board_sheets_read_back(tmp_path: Path) -> None:
    """The module sheets of the board example join the model's nets under the hierarchical scope."""
    from _altium_read import nets_from_project, read_sheet

    output = build_hier_board(tmp_path, sheets="modules")
    sheets = {name: read_sheet(data) for name, data in output.files.items() if name.endswith(".SchDoc")}
    refs = {c.id: c.ref for c in output.design.circuit.components}
    expected = {
        n.name: {(refs[m.component_id], m.pin) for m in n.members} for n in output.design.circuit.nets
    }
    found = nets_from_project(sheets, "altium_hier_board.SchDoc")
    assert {name: pins for name, pins in found.items() if not name.startswith("<unnamed ")} == expected
    assert all(len(pins) == 1 for name, pins in found.items() if name.startswith("<unnamed "))
    assert sorted(expected) == ["GND", "LED_A", "LED_DRV", "VIN"]


# --- copper (change c0038, "Copper in an Altium build") ---------------------------------------------

NO_COPPER = {
    "source": "none",
    "from": None,
    "layers": 2,
    "planes": {},
    "tracks": 0,
    "arcs": 0,
    "vias": 0,
    "zones": 0,
    "net_classes": 1,
    "placements_from_board": 0,
}


def test_copper_summary_of_a_design_without_copper(tmp_path: Path) -> None:
    output = build_blink_placed(tmp_path)
    assert output.summary["copper"] == NO_COPPER
    four = build_blink_placed(tmp_path / "four", copper=4)
    assert four.summary["copper"] == {**NO_COPPER, "layers": 4}
    assert (
        build_blink_placed(tmp_path / "none", "design.board(mm(50), mm(30))\n", "").summary["copper"] is None
    )


def test_copper_of_a_routed_model(tmp_path: Path) -> None:
    from _altium_copper import routed_build, routed_model
    from _altium_pcb_read import read_pcbdoc

    output = routed_build(tmp_path, routed_model(("tracks", "arc", "vias", "inner", "class")))
    assert not [i for i in output.issues if i.severity == "error"]
    assert output.summary["copper"] == {
        **NO_COPPER,
        "source": "model",
        "layers": 4,
        "tracks": 5,
        "arcs": 1,
        "vias": 3,
    }
    doc = read_pcbdoc(output.files["routed.PcbDoc"])
    names = [n["NAME"] for n in doc.nets]
    found = sorted((t.prefix.layer, names[t.prefix.net]) for t in doc.free_tracks)
    assert found == [(1, "LED_DRV"), (1, "LED_DRV"), (2, "VIN"), (3, "LED_A"), (32, "VIN")]
    assert [names[a.prefix.net] for a in doc.free_arcs] == ["LED_DRV"]
    assert [names[v.prefix.net] for v in doc.vias] == ["GND", "LED_A", "VIN"]
    assert {(v.diameter, v.hole) for v in doc.vias} == {(236220, 118110)}


def test_copper_bytes_do_not_depend_on_entity_ids(tmp_path: Path) -> None:
    """Routed records are sorted by geometry and net, so the same copper under other ids gives the same
    document."""
    import dataclasses

    from _altium_copper import routed_build, routed_model

    from fenolite.core.ids import derived_id

    model = routed_model(("tracks", "arc", "vias", "inner", "class"))
    assert model.board is not None
    renamed = dataclasses.replace(
        model,
        board=dataclasses.replace(
            model.board,
            tracks=tuple(
                dataclasses.replace(t, id=derived_id("trk", "dsl", f"other:{n}"))
                for n, t in enumerate(reversed(model.board.tracks))
            ),
            vias=tuple(
                dataclasses.replace(v, id=derived_id("via", "dsl", f"other:{n}"))
                for n, v in enumerate(reversed(model.board.vias))
            ),
        ),
    )
    first = routed_build(tmp_path, model).files["routed.PcbDoc"]
    assert routed_build(tmp_path, renamed).files["routed.PcbDoc"] == first


def test_via_blind_written_and_micro_left_out(tmp_path: Path) -> None:
    """A blind via is written and a micro via left out (change c0085, "Copper issue codes" as modified)."""
    import dataclasses

    from _altium_copper import at, routed_build, routed_model

    from fenolite.model.board import Via

    model = routed_model(("tracks", "arc", "vias", "inner", "class"))
    assert model.board is not None
    blind = Via(
        id="via_00000000-0000-4000-8000-000000000001",
        position=at(20, 20),
        diameter=600_000,
        drill=300_000,
        layers=("F.Cu", "In1.Cu"),
        via_type="blind",
    )
    board = dataclasses.replace(model.board, vias=(*model.board.vias, blind))
    output = routed_build(tmp_path, dataclasses.replace(model, board=board))
    # change c0085: a blind via is written; a micro via is left out with a warning
    assert not [i for i in output.issues if i.code == "altium.via-unsupported"] and output.files
    assert output.summary["copper"]["vias"] == len(board.vias)  # type: ignore[index]
    micro = dataclasses.replace(blind, via_type="micro")
    board = dataclasses.replace(model.board, vias=(*model.board.vias, micro))
    output = routed_build(tmp_path / "micro", dataclasses.replace(model, board=board))
    (found,) = [i for i in output.issues if i.code == "altium.via-unsupported"]
    assert found.where == f"via/{micro.id}" and found.severity == "warning" and output.files
    assert "micro" in found.message and "(20, 20) mm" in found.message
    assert output.summary["pcb"]["not_lowered"] == {"via": 1}  # type: ignore[index]


def test_copper_stack_of_three_layers_refused(tmp_path: Path) -> None:
    """Scenario "Three copper layers refused"."""
    import dataclasses

    from _altium_copper import routed_build, routed_model

    from fenolite.model.board import Layer

    model = routed_model(())
    assert model.board is not None
    layers = tuple(
        Layer(id=f"lay_00000000-0000-4000-8000-00000000000{n}", name=name, kind="copper", ordinal=n)
        for n, name in enumerate(("F.Cu", "In1.Cu", "B.Cu"))
    )
    output = routed_build(
        tmp_path, dataclasses.replace(model, board=dataclasses.replace(model.board, layers=layers))
    )
    assert output.files == {}
    (found,) = [i for i in output.issues if i.code == "altium.copper-stack"]
    assert "F.Cu, In1.Cu, B.Cu" in found.message
    four = tuple(
        Layer(id=f"lay_00000000-0000-4000-8000-00000000001{n}", name=name, kind="copper", ordinal=n)
        for n, name in enumerate(("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))
    )
    model4 = dataclasses.replace(model, board=dataclasses.replace(model.board, layers=four))
    assert routed_build(tmp_path, model4).summary["copper"]["layers"] == 4  # type: ignore[index]
    (differs,) = [
        i for i in routed_build(tmp_path, model4, copper=2).issues if i.code == "altium.copper-stack"
    ]
    assert "4 copper layers" in differs.message and "asks for 2" in differs.message


# --- stack values (change c0038, task 3.2) ----------------------------------------------------------


def _with_stackup(model: object, names: tuple[str, ...], between: tuple[tuple[int, str, str], ...]) -> object:
    """``model`` with a stack-up of the copper layers ``names`` (35 um each) and one dielectric
    (thickness, constant, material) between neighbours, under a solder mask."""
    import dataclasses

    from fenolite.model.board import StackLayer, Stackup

    def layer(n: int, name: str, kind: str, thickness: int, **more: str) -> StackLayer:
        ident = f"sly_00000000-0000-4000-8000-0000000000{n:02d}"
        return StackLayer(id=ident, name=name, kind=kind, thickness=thickness, **more)  # type: ignore[arg-type]

    layers = [layer(0, "F.Mask", "soldermask", 10_000)]
    for position, name in enumerate(names):
        if position:
            thickness, constant, material = between[position - 1]
            layers.append(
                layer(
                    20 + position,
                    f"dielectric {position}",
                    "dielectric",
                    thickness,
                    epsilon_r=constant,
                    material=material,
                )  # fmt: skip
            )
        layers.append(layer(10 + position, name, "copper", 35_000))
    stackup = Stackup(id="stk_00000000-0000-4000-8000-000000000001", layers=tuple(layers))
    assert model.board is not None  # type: ignore[attr-defined]
    return dataclasses.replace(model, board=dataclasses.replace(model.board, stackup=stackup))  # type: ignore[type-var,attr-defined]


def test_stack_values_come_from_the_stackup(tmp_path: Path) -> None:
    from _altium_copper import FOUR, routed_build, routed_model
    from _altium_pcb_read import read_pcbdoc

    between = ((180_000, "4.4", "PP"), (710_000, "4.5", ""), (180_000, "", "PP"))
    output = routed_build(tmp_path, _with_stackup(routed_model(()), FOUR, between))  # type: ignore[arg-type]
    assert not [i for i in output.issues if i.where == "stackup"]
    board = read_pcbdoc(output.files["routed.PcbDoc"]).board
    assert [board[f"V9_STACK_LAYER{i}_DIELTYPE"] for i in (4, 6, 8)] == ["2", "1", "2"]
    assert (
        board["V9_STACK_LAYER6_DIELHEIGHT"] == "27.9528mil" and board["V9_STACK_LAYER6_DIELCONST"] == "4.500"
    )
    assert board["V9_STACK_LAYER6_DIELMATERIAL"] == "FR-4" and board["V9_STACK_LAYER4_DIELMATERIAL"] == "PP"
    assert board["V9_STACK_LAYER8_DIELCONST"] == "4.800" and board["LAYER1DIELHEIGHT"] == "7.0866mil"
    assert board["LAYER2COPTHICK"] == board["V9_STACK_LAYER3_COPTHICK"] == "1.378mil"
    two = routed_build(
        tmp_path, _with_stackup(routed_model(()), ("F.Cu", "B.Cu"), ((1_500_000, "4.6", "FR-4"),)), copper=2
    )  # type: ignore[arg-type]
    board = read_pcbdoc(two.files["routed.PcbDoc"]).board
    assert board["V9_STACK_LAYER4_DIELTYPE"] == "1" and board["V9_STACK_LAYER4_DIELHEIGHT"] == "59.0551mil"


def test_stack_up_that_does_not_fit_gives_the_default_values(tmp_path: Path) -> None:
    from _altium_copper import routed_build, routed_model
    from _altium_pcb_read import read_pcbdoc

    two_layer_stackup = _with_stackup(routed_model(()), ("F.Cu", "B.Cu"), ((1_500_000, "4.6", "FR-4"),))
    output = routed_build(tmp_path, two_layer_stackup)  # type: ignore[arg-type]
    (found,) = [i for i in output.issues if i.where == "stackup"]
    assert (
        found.code == "altium.not-lowered"
        and found.severity == "info"
        and "default stack values" in found.message
    )
    board = read_pcbdoc(output.files["routed.PcbDoc"]).board
    assert [board[f"V9_STACK_LAYER{i}_DIELHEIGHT"] for i in (4, 6, 8)] == [
        "7.874mil",
        "39.3701mil",
        "7.874mil",
    ]
    assert board["LAYER1COPTHICK"] == "1.4mil"


def test_layer_names_of_the_stack_up_must_match(tmp_path: Path) -> None:
    from _altium_copper import routed_build, routed_model

    other = _with_stackup(routed_model(()), ("F.Cu", "In2.Cu", "In1.Cu", "B.Cu"), ((1, "4", "A"),) * 3)
    output = routed_build(tmp_path, other)  # type: ignore[arg-type]
    assert [i.code for i in output.issues if i.where == "stackup"] == ["altium.not-lowered"]


def test_layer_count_comes_from_the_script_or_the_board(tmp_path: Path) -> None:
    from _altium_copper import routed_build, routed_model
    from _altium_pcb_read import read_pcbdoc

    four = routed_build(tmp_path, routed_model(()))
    assert four.summary["copper"]["layers"] == 4  # type: ignore[index]
    assert read_pcbdoc(four.files["routed.PcbDoc"]).copper_chain == [1, 2, 3, 32]
    two = routed_build(tmp_path, routed_model(()), copper=2)
    assert read_pcbdoc(two.files["routed.PcbDoc"]).copper_chain == [1, 32]


# --- zones (change c0038, task 4.2) -----------------------------------------------------------------


def test_zone_of_the_routed_model_becomes_two_unpoured_polygons(tmp_path: Path) -> None:
    """Scenario "Routed model" of "Copper in an Altium build" (the net-class count comes with task 7.1)."""
    from _altium_copper import routed_build
    from _altium_pcb_read import read_pcbdoc

    output = routed_build(tmp_path)
    assert not [i for i in output.issues if i.severity == "error"] and "routed.PcbDoc" in output.files
    copper = dict(output.summary["copper"])  # type: ignore[call-overload]
    copper.pop("net_classes")
    assert copper == {
        "source": "model",
        "from": None,
        "layers": 4,
        "planes": {},
        "tracks": 5,
        "arcs": 1,
        "vias": 3,
        "zones": 2,
        "placements_from_board": 0,
    }
    (info,) = [i for i in output.issues if i.code == "altium.zones-unpoured"]
    assert (
        info.severity == "info" and info.message.startswith("2 polygon(s)") and info.where == "routed.PcbDoc"
    )
    assert "Tools » Polygon Pours » Repour All" in info.message
    doc = read_pcbdoc(output.files["routed.PcbDoc"])
    names = [n["NAME"] for n in doc.nets]
    assert [(p.layer, names[p.net or 0], len(p.vertices)) for p in doc.polygons] == [
        ("MID1", "GND", 5),
        ("BOTTOM", "GND", 5),
    ]
    assert doc.storages["Regions6"] == (0, b"")


def test_zone_fills_of_the_model_are_not_written(tmp_path: Path) -> None:
    import dataclasses

    from _altium_copper import routed_build, routed_model

    from fenolite.model.board import ZoneFill

    model = routed_model()
    assert model.board is not None
    (zone,) = model.board.zones
    filled = dataclasses.replace(zone, fills=(ZoneFill("B.Cu", zone.outline),))
    board = dataclasses.replace(model.board, zones=(filled,))
    first = routed_build(tmp_path, model).files["routed.PcbDoc"]
    assert routed_build(tmp_path, dataclasses.replace(model, board=board)).files["routed.PcbDoc"] == first


def test_design_without_a_zone_gives_no_unpoured_info(tmp_path: Path) -> None:
    from _altium_copper import routed_build, routed_model

    output = routed_build(tmp_path, routed_model(("tracks", "arc", "vias", "inner", "class")))
    assert "altium.zones-unpoured" not in {i.code for i in output.issues}


# --- internal planes (change c0038, "Internal planes in an Altium build") ----------------------------


def test_plane_variant_builds(tmp_path: Path) -> None:
    """Scenario "Plane variant builds": ``p0`` has the plane on ``GND``, four tracks and one polygon."""
    from _altium_copper import PLANE, plane_model, routed_build
    from _altium_pcb_read import read_pcbdoc

    output = routed_build(tmp_path, plane_model(), planes=PLANE)
    assert not [i for i in output.issues if i.severity == "error"]
    copper = output.summary["copper"]
    assert copper["planes"] == {"In1.Cu": "GND"} and copper["tracks"] == 4 and copper["zones"] == 1  # type: ignore[index]
    assert copper["layers"] == 4 and copper["vias"] == 3  # type: ignore[index]
    doc = read_pcbdoc(output.files["routed.PcbDoc"])
    assert doc.copper_chain == [1, 39, 3, 32] and doc.plane_nets == {1: "GND"}
    assert doc.board["PLANE1NETNAME"] == "GND" and [p.layer for p in doc.polygons] == ["BOTTOM"]
    assert sorted(t.prefix.layer for t in doc.free_tracks) == [1, 1, 3, 32] and len(doc.vias) == 3
    (merged,) = [i for i in output.issues if i.code == "altium.plane-zone-merged"]
    assert merged.severity == "info" and "the GND zone on In1.Cu at (1, 1) mm" in merged.message
    (unpoured,) = [i for i in output.issues if i.code == "altium.zones-unpoured"]
    assert unpoured.message.startswith("1 polygon(s)")


def test_ground_plane_from_the_script_refuses_the_track_on_the_plane(tmp_path: Path) -> None:
    """Scenario "Ground plane from the script": the whole sample with the plane gives one error for its
    track on ``In1.Cu``; the lowering still shows the stack and the polygon that would be written."""
    from _altium_copper import PLANE, routed_build, routed_model

    from fenolite.lens.altium_copper import lower_copper

    output = routed_build(tmp_path, planes=PLANE)
    assert output.files == {}
    (error,) = [i for i in output.issues if i.severity == "error"]
    assert (
        error.code == "altium.plane-copper" and "track on In1.Cu" in error.message and "GND" in error.message
    )
    assert len([i for i in output.issues if i.code == "altium.plane-zone-merged"]) == 1
    plan = lower_copper(routed_model(), copper=4, planes=PLANE, document="routed.PcbDoc")
    assert (
        plan.stack is not None and plan.stack.copper == (1, 39, 3, 32) and plan.stack.plane_nets == ("GND",)
    )
    assert [zone.layers for zone in plan.zones] == [("B.Cu",)] and len(plan.tracks) == 4 and plan.failed


def test_plane_on_an_unknown_net(tmp_path: Path) -> None:
    """Scenario "Plane on an unknown net"."""
    output = build_blink_placed(tmp_path, copper=4, planes={"In1.Cu": "NOPE"})
    assert output.files == {}
    (found,) = [i for i in output.issues if i.code == "altium.copper-stack"]
    assert "In1.Cu" in found.message and "NOPE" in found.message and found.where == "In1.Cu"
    two = build_blink_placed(tmp_path / "two", planes={"In1.Cu": "GND"})
    (found,) = [i for i in two.issues if i.code == "altium.copper-stack"]
    assert "is not on an inner copper layer" in found.message and two.files == {}


def test_two_planes_and_a_zone_on_another_net(tmp_path: Path) -> None:
    from _altium_pcb_read import read_pcbdoc

    output = build_blink_placed(tmp_path, copper=4, planes={"In2.Cu": "VIN", "In1.Cu": "GND"})
    assert output.summary["copper"]["planes"] == {"In1.Cu": "GND", "In2.Cu": "VIN"}  # type: ignore[index]
    doc = read_pcbdoc(output.files["blink.PcbDoc"])
    assert doc.copper_chain == [1, 39, 40, 32] and doc.plane_nets == {1: "GND", 2: "VIN"}


def test_plane_keeps_the_model_unchanged(tmp_path: Path) -> None:
    """A plane layer stays a copper layer of the model: no layer kind is added."""
    from _altium_copper import PLANE, plane_model, routed_build

    output = routed_build(tmp_path, plane_model(), planes=PLANE)
    assert output.design.board is not None
    assert {layer.kind for layer in output.design.board.layers} <= {"copper"}


# --- net classes (change c0038, task 7.1) -----------------------------------------------------------


def test_class_of_the_blink_sample(tmp_path: Path) -> None:
    """Scenario "Class of the blink sample": one net class, ``PWR`` with ``GND`` and ``VIN``, then the
    component class of the single sheet (change c0048)."""
    from _altium_pcb_read import read_pcbdoc

    output = build_blink_placed(tmp_path)
    doc = read_pcbdoc(output.files["blink.PcbDoc"])
    record, sheet = doc.classes
    assert (sheet.name, sheet.kind, sheet.members) == ("blink", "1", ["D1", "R1", "U1"])
    assert record.fields["NAME"] == "PWR" and record.fields["KIND"] == "0"
    assert record.fields["M0"] == "GND" and record.fields["M1"] == "VIN" and "M2" not in record.fields
    assert output.summary["copper"]["net_classes"] == 1  # type: ignore[index]
    assert doc.storages["Vias6"] == (0, b"") and doc.storages["Polygons6"] == (0, b"")


def test_design_without_copper_keeps_its_document(tmp_path: Path) -> None:
    """Scenario "Design without copper keeps its document": without its net class the blink document has
    empty copper storages, and every other stream of the committed ``blink.PcbDoc``."""
    from _altium_pcb_read import read_pcbdoc

    text = 'design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))\n'
    output = build_blink_placed(tmp_path, text, "")
    doc = read_pcbdoc(output.files["blink.PcbDoc"])
    for name in ("Vias6", "Polygons6", "Rules6"):
        assert doc.storages[name] == (0, b""), name
    assert [(c.name, c.kind) for c in doc.classes] == [("blink", "1")]  # the sheet's component class
    committed = read_pcbdoc((LIBS.parent / "altium" / "blink" / "blink.PcbDoc").read_bytes())
    storages = ("Vias6", "Polygons6", "Classes6", "Rules6")
    copper = {f"{name}/{part}" for name in storages for part in ("Header", "Data")}
    assert set(doc.streams) == set(committed.streams)
    for name in sorted(set(doc.streams) - copper):
        assert doc.streams[name] == committed.streams[name], name
    assert output.summary["copper"]["net_classes"] == 0  # type: ignore[index]


def test_class_name_that_cannot_be_written(tmp_path: Path) -> None:
    text, new = 'design.rules.netclass("PWR"', 'design.rules.netclass("PW|R"'
    output = build_blink_placed(tmp_path, text, new)
    assert output.files == {}
    (found,) = [i for i in output.issues if i.severity == "error"]
    assert found.code == "altium.text-unwritable" and "net class name 'PW|R'" in found.message
    quoted = build_blink_placed(tmp_path / "q", text, 'design.rules.netclass("it\'s"')
    (found,) = [i for i in quoted.issues if i.severity == "error"]
    assert found.code == "altium.text-unwritable" and "apostrophe" in found.message and quoted.files == {}


def test_class_is_reported_only_without_the_document(tmp_path: Path) -> None:
    """The class is kept in the model only when no PCB document is planned."""
    planned = build_blink_placed(tmp_path)
    assert not [i for i in planned.issues if i.code == "altium.not-lowered"]
    boardless = build_blink_placed(tmp_path / "b", "design.board(mm(50), mm(30))\n", "")
    rules = [i for i in boardless.issues if i.code == "altium.not-lowered" and i.where == "rules"]
    assert len(rules) == 1 and "PWR" in rules[0].message


def test_board_items_the_document_does_not_write(tmp_path: Path) -> None:
    """Keep-outs, board texts, graphics and holes are reported, one info per kind."""
    import dataclasses

    from _altium_copper import at, routed_build, routed_model

    from fenolite.core.coords import Size
    from fenolite.model.board import Graphic, Hole, Keepout, Text

    model = routed_model()
    assert model.board is not None
    outline = model.board.zones[0].outline
    board = dataclasses.replace(
        model.board,
        keepouts=(Keepout(id="kpo_00000000-0000-4000-8000-000000000001", outline=outline, layers=("F.Cu",)),),
        texts=(
            Text(
                id="txt_00000000-0000-4000-8000-000000000001",
                text="REV A",
                position=at(5, 5),
                layer="F.SilkS",
                size=Size(1_000_000, 1_000_000),
                thickness=150_000,
            ),
        ),
        graphics=(
            Graphic(
                id="gfx_00000000-0000-4000-8000-000000000001",
                kind="line",
                layer="F.SilkS",
                points=(at(1, 1), at(2, 1)),
            ),
        ),
        holes=(Hole(id="hol_00000000-0000-4000-8000-000000000001", position=at(3, 3), drill=3_000_000),),
    )
    output = routed_build(tmp_path, dataclasses.replace(model, board=board))
    # change c0085: the items are written; one that has no record is reported with its id
    found = {i.where: i for i in output.issues if i.code == "altium.not-lowered"}
    assert sorted(found) == [
        "graphic/gfx_00000000-0000-4000-8000-000000000001",  # a line without a width
        "keepout/kpo_00000000-0000-4000-8000-000000000001",  # a keep-out without a restriction
    ]
    assert all(i.severity == "info" for i in found.values()) and "routed.PcbDoc" in output.files
    pcb = output.summary["pcb"]
    assert pcb["not_lowered"] == {"graphic": 1, "keep-out": 1}  # type: ignore[index]
    assert (pcb["written"]["text"], pcb["written"]["hole"]) == (1, 1)  # type: ignore[index]


# --- design rules (change c0038, task 9) -------------------------------------------------------------


def test_rules_of_the_blink_build(tmp_path: Path) -> None:
    """Scenario "Rules of the blink sample" through the build."""
    from _altium_pcb_read import read_pcbdoc

    doc = read_pcbdoc(build_blink_placed(tmp_path).files["blink.PcbDoc"])
    assert [(r.name, r.kind, r.priority) for r in doc.rules] == [
        ("Clearance_PWR", 0, 1),
        ("Clearance", 0, 2),
        ("Width_PWR", 2, 1),
        ("Width", 2, 2),
        ("RoutingVias", 11, 1),
    ]


def test_rules_of_the_routed_build_span_its_copper(tmp_path: Path) -> None:
    from _altium_copper import routed_build
    from _altium_pcb_read import read_pcbdoc

    doc = read_pcbdoc(routed_build(tmp_path).files["routed.PcbDoc"])
    rules = {r.name: r.fields for r in doc.rules}
    assert len(rules) == 5
    assert (rules["Width"]["MINLIMIT"], rules["Width"]["MAXLIMIT"]) == ("9.8425mil", "19.685mil")
    assert (rules["Width_PWR"]["MINLIMIT"], rules["Width_PWR"]["MAXLIMIT"]) == ("19.685mil", "19.685mil")
    assert rules["RoutingVias"]["MINWIDTH"] == rules["RoutingVias"]["MAXWIDTH"] == "23.622mil"


# --- copper together with module sheets (changes c0037 and c0038) -----------------------------------


def test_copper_does_not_depend_on_the_sheet_mode(tmp_path: Path) -> None:
    """The routed sample has no module, so ``modules`` gives the flat document; the hierarchical board
    example keeps its two-id links when a copper layer count and a plane are given."""
    from _altium_copper import routed_build
    from _altium_pcb_read import read_pcbdoc

    flat = routed_build(tmp_path / "f")
    split = routed_build(tmp_path / "m", sheets="modules")
    assert flat.files["routed.PcbDoc"] == split.files["routed.PcbDoc"]
    assert split.summary["copper"] == flat.summary["copper"] and split.summary["sheet_mode"] == "modules"
    board = build_hier_board(tmp_path / "h", sheets="modules", copper=4, planes={"In1.Cu": "GND"})
    assert not [i for i in board.issues if i.severity == "error"]
    doc = read_pcbdoc(board.files["altium_hier_board.PcbDoc"])
    assert doc.copper_chain == [1, 39, 3, 32] and doc.plane_nets == {1: "GND"}
    assert all(c["SOURCEUNIQUEID"].count("\\") == 2 for c in doc.components)
    assert [c.name for c in doc.classes] == ["PWR", "driver", "led"] and len(doc.rules) == 5


# --- every board component links to a schematic component (H-A-SCH-HIER-ECO, step H7) ------------------


def _links_and_board(files: dict[str, bytes], name: str) -> tuple[dict[str, tuple[str, str]], list[str]]:
    from _altium_pcb_read import read_pcbdoc
    from _altium_read import board_link_problems, component_links

    links = component_links(files[f"{name}.PrjPcb"], files, f"{name}.SchDoc")
    return links, board_link_problems(links, read_pcbdoc(files[f"{name}.PcbDoc"]).components)


@pytest.mark.parametrize("mode", ["flat", "modules"])
def test_hier_board_every_component_link_resolves(tmp_path: Path, mode: str) -> None:
    """``H-A-SCH-HIER-ECO``, step H7: every board component's ``SOURCEUNIQUEID`` is the link of a schematic
    component, through a sheet symbol of the top sheet whose file-name record is a sheet that the project
    file lists, and every module sheet is reachable from the top sheet."""
    output = build_hier_board(tmp_path, sheets=mode)
    links, problems = _links_and_board(output.files, "altium_hier_board")
    assert problems == []
    assert sorted(ref for ref, _path in links.values()) == ["D1", "R1", "U1"]
    paths = {ref: path for ref, path in links.values()}
    if mode == "modules":
        assert paths == {
            "D1": "altium_hier_board\\led",
            "R1": "altium_hier_board\\driver",
            "U1": "altium_hier_board\\driver",
        }
    else:
        assert set(paths.values()) == {""}


def test_hier_board_channel_offsets_count_per_sheet(tmp_path: Path) -> None:
    """``H-A-SCH-HIER-ECO``: ``CHANNELOFFSET`` restarts at 0 on every sheet (``pcb-document.md``); ``D1`` is
    the only part of ``led``, so its offset is 0, not its board-wide index 2."""
    from _altium_pcb_read import read_pcbdoc

    doc = read_pcbdoc(build_hier_board(tmp_path, sheets="modules").files["altium_hier_board.PcbDoc"])
    found = {c["SOURCEDESIGNATOR"]: (c["SOURCEHIERARCHICALPATH"], c["CHANNELOFFSET"]) for c in doc.components}
    assert found == {
        "R1": ("altium_hier_board\\driver", "0"),
        "U1": ("altium_hier_board\\driver", "1"),
        "D1": ("altium_hier_board\\led", "0"),
    }
    flat = read_pcbdoc(build_hier_board(tmp_path / "flat").files["altium_hier_board.PcbDoc"])
    assert [c["CHANNELOFFSET"] for c in flat.components] == ["0", "1", "2"]


def test_hier_board_link_faults_are_caught(tmp_path: Path) -> None:
    """The reading of H7 fails on each fault that leaves a module sheet outside the hierarchy."""
    from _altium_pcb_read import read_pcbdoc
    from _altium_read import ReadError, board_link_problems, component_links

    from fenolite.backends.altium.prjpcb import write_prjpcb

    files = dict(build_hier_board(tmp_path, sheets="modules").files)
    project, top = files["altium_hier_board.PrjPcb"], "altium_hier_board.SchDoc"
    led = b"altium_hier_board_led.SchDoc"
    unlisted = write_prjpcb(
        schematic=top,
        sheets=("altium_hier_board_driver.SchDoc",),
        pcb="altium_hier_board.PcbDoc",
        libraries=("altium_hier_board.PcbLib", "altium_hier_board.SchLib"),
    )
    assert led in project and led not in unlisted
    with pytest.raises(ReadError, match="altium_hier_board_led.SchDoc, which the project does not list"):
        component_links(unlisted, files, top)
    upper = "altium_hier_board_LED.SchDoc"
    cased = {**files, upper: files[led.decode()]}
    with pytest.raises(ReadError, match=r"does not list \(the project lists altium_hier_board_LED.SchDoc\)"):
        component_links(project.replace(led, upper.encode()), cased, top)
    other = build_hier_board(tmp_path / "flat").files
    lone = {**files, top: other[top]}
    with pytest.raises(ReadError, match="is not reachable from the top sheet"):
        component_links(project, lone, top)
    links = component_links(project, files, top)
    flat_board = read_pcbdoc(other["altium_hier_board.PcbDoc"]).components
    problems = board_link_problems(links, flat_board)
    assert len([p for p in problems if "is not a schematic component" in p]) == 3
    assert len([p for p in problems if "is not on the board" in p]) == 3


def test_module_without_a_crossing_still_gets_its_sheet_symbol(tmp_path: Path) -> None:
    """Every module sheet has a sheet symbol on the top sheet, even with no sheet entry: a module whose
    nets are all power nets or local nets crosses nothing, and its sheet must still be a child."""
    from _altium_read import component_links

    from fenolite.dsl import Design, Module, Net, Part, Power, connect

    design = Design("lonely")
    a, b = Module("a"), Module("b")
    r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
    r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="2k")
    a.add(r1)
    b.add(r2)
    design.add(a, b)
    vin, gnd = Net("VIN"), Net("GND")
    connect(vin, r1[1], r2[1])
    connect(gnd, r1[2], r2[2])
    design.add(Power(vin, gnd))
    output = build_altium(
        to_model(design),
        name=design.name,
        resolver=blink_resolver(tmp_path, HIER_BOARD_DIR),
        sheets="modules",
    )
    assert output.summary["sheets"] == ["lonely.SchDoc", "lonely_a.SchDoc", "lonely_b.SchDoc"]
    assert (output.summary["ports"], output.summary["sheet_entries"]) == (0, 0)
    top = records(output.files["lonely.SchDoc"])[1:]
    assert [r["RECORD"] for r in top] == ["31", "15", "32", "33", "15", "32", "33"]
    assert [r["TEXT"] for r in top if r["RECORD"] == "33"] == ["lonely_a.SchDoc", "lonely_b.SchDoc"]
    links = component_links(output.files["lonely.PrjPcb"], output.files, "lonely.SchDoc")
    assert sorted(links.values()) == [("R1", "lonely\\a"), ("R2", "lonely\\b")]


def test_hier_board_project_lists_the_schematics_first(tmp_path: Path) -> None:
    """``H-A-SCH-HIER-ORDER``, step H7: in a multi-sheet build every schematic document precedes every
    other document of the project file, and the top sheet is the first. With the PCB document and the
    libraries between the top sheet and the module sheets, Altium Designer took only the first module
    sheet into the hierarchy. No sheet is padded: the records of a small sheet are written as they are."""
    output = build_hier_board(tmp_path, sheets="modules")
    project = output.files["altium_hier_board.PrjPcb"].decode("ascii")
    paths = [line.partition("=")[2] for line in project.split("\r\n") if line.startswith("DocumentPath=")]
    assert paths == [
        "altium_hier_board.SchDoc",
        "altium_hier_board_driver.SchDoc",
        "altium_hier_board_led.SchDoc",
        "altium_hier_board.PcbDoc",
        "altium_hier_board.PcbLib",
        "altium_hier_board.SchLib",
    ]
    sheets = list(output.summary["sheets"])  # type: ignore[call-overload]
    assert paths[: len(sheets)] == sheets, "the top sheet, then the module sheets in their order"
    assert not any(path.endswith(".SchDoc") for path in paths[len(sheets) :])
    sections = [line for line in project.split("\r\n") if line.startswith("[Document")]
    assert sections == [f"[Document{n}]" for n in range(1, len(paths) + 1)]
    for name in sheets:
        rows = records(output.files[name])
        assert rows[0]["WEIGHT"] == str(len(rows) - 1)
        assert all(r.get("NAME") != "FenoliteNote" for r in rows), name
