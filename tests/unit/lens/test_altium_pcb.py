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
from _altium import blink, blink_resolver, blink_tree, example, sample
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
    lowered = [i for i in output.issues if i.code == "altium.not-lowered"]
    assert len(lowered) == 1 and "PWR" in lowered[0].message
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
    assert record["LAYER"] == "TOP" and record["ROTATION"] == "0"
