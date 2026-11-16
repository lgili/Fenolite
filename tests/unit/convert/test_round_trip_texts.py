# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium board through KiCad and back keeps its texts, values and library links (capability
design-conversion, "Altium round trip keeps texts, values and library links"; change c0451).

The fixture is the authored Altium sample ``tests/data/altium/routed``, written back as an Altium document
after three edits: ``D1`` links the libraries ``Lib_A`` (footprint) and ``Sym_A`` (symbol), which are not the
project's; ``R1`` has an empty value and keeps its hidden ``Value`` field; ``U1`` holds a text without
characters."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

from fenolite.backends.altium import lower
from fenolite.backends.kicad.sexpr import parse
from fenolite.convert import altium_links, convert_project
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import FootprintInstance, Text
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
ROUTED = ROOT / "tests" / "data" / "altium" / "routed"
FOOTPRINT = "Lib_A:Mini_LED_THT_3mm"
SYMBOL = "Sym_A:Mini_LED"
"""The links as the import reads them: without the ``.PcbLib`` and ``.SchLib`` of the document's records."""


def _write(files: dict[str, bytes], folder: Path) -> None:
    for name, data in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)


def _footprint(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    return next(fp for fp in design.board.footprints if refs.get(fp.component_id) == ref)


def _source(tmp_path: Path) -> Path:
    """The edited sample written as an Altium document; its path."""
    shutil.copytree(ROUTED, tmp_path / "sample")
    design = read_source(tmp_path / "sample" / "routed.PrjPcb").design
    board = design.board
    assert board is not None
    d1, r1, u1 = (_footprint(design, ref) for ref in ("D1", "R1", "U1"))
    assert d1.lib_ref.endswith(":Mini_LED_THT_3mm")
    reference = next(f for f in u1.fields if f.name == "Reference")
    empty = Text(
        id=derived_id("txt", "c0451", "empty"),
        text="",
        position=Point(0, 1_000_000),
        layer="F.SilkS",
        size=reference.size,
        thickness=reference.thickness or 150_000,
    )

    def edited(fp: FootprintInstance) -> FootprintInstance:
        if fp.id == d1.id:
            return dataclasses.replace(fp, lib_ref="Lib_A.PcbLib:Mini_LED_THT_3mm")
        if fp.id == u1.id:
            return dataclasses.replace(fp, texts=(*fp.texts, empty))
        return fp

    components = tuple(
        dataclasses.replace(
            c, lib_footprint_ref="Lib_A.PcbLib:Mini_LED_THT_3mm", lib_symbol_ref="Sym_A.SchLib:Mini_LED"
        )
        if c.id == d1.component_id
        else dataclasses.replace(c, value="")
        if c.id == r1.component_id
        else c
        for c in design.circuit.components
    )
    design = dataclasses.replace(
        design,
        board=dataclasses.replace(board, footprints=tuple(edited(fp) for fp in board.footprints)),
        circuit=dataclasses.replace(design.circuit, components=components),
    )
    written = lower.write_design(design, allow_lossy=True, rewrite=True)
    _write(dict(written.files), tmp_path / "src")
    return next((tmp_path / "src").glob("*.PcbDoc"))


def _to_kicad(document: Path, folder: Path) -> Path:
    conversion = convert_project(read_source(document), to="kicad", allow_lossy=True)
    _write(dict(conversion.files), folder)
    return next(folder.glob("*.kicad_pro"))


def _to_altium(project: Path, folder: Path) -> Design:
    back = convert_project(project, to="altium", allow_lossy=True)
    _write(dict(back.files), folder)
    return read_source(next(folder.glob("*.PrjPcb"))).design


def test_links_and_values_come_back(tmp_path: Path) -> None:
    """Scenario "Links and values come back"."""
    document = _source(tmp_path)
    start = read_source(document).design
    d1 = next(c for c in start.circuit.components if c.ref == "D1")
    assert (d1.lib_symbol_ref, _footprint(start, "D1").lib_ref) == (SYMBOL, FOOTPRINT)
    project = _to_kicad(document, tmp_path / "kicad")
    pcb = parse(next((tmp_path / "kicad").glob("*.kicad_pcb")).read_text(encoding="utf-8"))
    props = {
        node.atoms()[0].value: node
        for fp in pcb.nodes("footprint")
        for node in fp.nodes("property")
        if node.atoms()[0].value in altium_links.NAMES and node.atoms()[1].value in (FOOTPRINT, SYMBOL)
    }
    assert set(props) == {altium_links.FOOTPRINT, altium_links.SYMBOL}
    assert all("hide" in str(node) for node in props.values())
    back = _to_altium(project, tmp_path / "back")
    d1_back = next(c for c in back.circuit.components if c.ref == "D1")
    assert (d1_back.lib_symbol_ref, _footprint(back, "D1").lib_ref) == (SYMBOL, FOOTPRINT)
    assert not any(name in c.properties for c in back.circuit.components for name in altium_links.NAMES)
    # Scenario "A source library comes back as a file": the project ships the libraries it links
    files = {path.name for path in (tmp_path / "back").iterdir()}
    assert {"Lib_A.PcbLib", "Sym_A.SchLib"} <= files
    listed = next((tmp_path / "back").glob("*.PrjPcb")).read_text(encoding="utf-8")
    assert "Lib_A.PcbLib" in listed and "Sym_A.SchLib" in listed
    assert b"Mini_LED_THT_3mm" in (tmp_path / "back" / "Lib_A.PcbLib").read_bytes()
    for ref in ("R1", "U1"):
        before = {c.ref: c.lib_symbol_ref for c in start.circuit.components}[ref]
        assert {c.ref: c.lib_symbol_ref for c in back.circuit.components}[ref] == before
    value_a = next(f for f in _footprint(start, "R1").fields if f.name == "Value")
    value_b = next(f for f in _footprint(back, "R1").fields if f.name == "Value")
    assert (value_b.layer, value_b.visible) == (value_a.layer, value_a.visible)
    assert {c.ref: c.value for c in back.circuit.components}["R1"] == ""
    assert [t.text for t in _footprint(back, "U1").texts].count("") == 1


def test_a_swapped_footprint_drops_the_link(tmp_path: Path) -> None:
    """Scenario "A swapped footprint drops the link": ``D1`` linked to another footprint in KiCad keeps the
    conversion's own links."""
    project = _to_kicad(_source(tmp_path), tmp_path / "kicad")
    pcb = next((tmp_path / "kicad").glob("*.kicad_pcb"))
    text = pcb.read_text(encoding="utf-8")
    assert text.count('(footprint "routed:Mini_LED_THT_3mm"') == 1
    pcb.write_text(text.replace('(footprint "routed:Mini_LED_THT_3mm"', '(footprint "routed:Other_LED"'))
    back = _to_altium(project, tmp_path / "back")
    d1 = next(c for c in back.circuit.components if c.ref == "D1")
    assert _footprint(back, "D1").lib_ref == "routed:Other_LED"
    assert d1.lib_symbol_ref != SYMBOL
    assert not any(name in c.properties for c in back.circuit.components for name in altium_links.NAMES)


def test_derived_from() -> None:
    assert altium_links.derived_from("p:Mini_R", "Lib:Mini_R")
    assert altium_links.derived_from("p:Mini_R_2", "Lib:Mini_R")
    assert altium_links.derived_from("p:SOT_23", "Lib:SOT/23")
    assert not altium_links.derived_from("p:Mini_R_x", "Lib:Mini_R")
    assert not altium_links.derived_from("p:Other", "Lib:Mini_R")


def _anchor_trip(tmp_path: Path) -> tuple[Path, Path]:
    """The authored document of change c0492 (``_textanchor``) and its KiCad project."""
    from _textanchor import anchor_design, document

    source = tmp_path / "altium" / "anchor.PcbDoc"
    source.parent.mkdir()
    source.write_bytes(document(anchor_design()))
    return source, _to_kicad(source, tmp_path / "kicad")


def _text_records(data: bytes) -> dict[str, tuple[int, int, float, bool]]:
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.backends.altium.read.pcbprims import RawPrimitive

    return {
        r.text: (r.x, r.y, r.rotation, r.mirrored)
        for r in read_pcbdoc(data).texts
        if not isinstance(r, RawPrimitive)
    }


def _back_document(project: Path) -> bytes:
    back = convert_project(read_source(project), to="altium", allow_lossy=True)
    (data,) = [data for name, data in back.files.items() if name.endswith(".PcbDoc")]
    return data


def test_texts_at_four_angles_on_both_sides(tmp_path: Path) -> None:
    """Scenario "Texts at four angles on both sides" (change c0492): every text and designator record of
    the round trip holds the source's position, rotation and mirror."""
    source, project = _anchor_trip(tmp_path)
    before = _text_records(source.read_bytes())
    assert len(before) >= 20 and any(mirrored for *_, mirrored in before.values())
    assert _text_records(_back_document(project)) == before


def test_a_field_moved_in_kicad(tmp_path: Path) -> None:
    """Scenario "A field moved in KiCad": ``R1``'s reference centred and moved by half its box, its ink in
    place, is written within one stroke width of the source's designator record."""
    from _textanchor import MM, STROKE

    from fenolite.geometry.transform import rotate_point
    from fenolite.silk.extents import TextKey, estimate

    source, project = _anchor_trip(tmp_path)
    pcb = next((tmp_path / "kicad").glob("*.kicad_pcb"))
    text = pcb.read_text(encoding="utf-8")
    head = '(property "Reference" "R1"\n\t\t\t(at 0 -1.43 180)'
    assert text.count(head) == 1 and "(at 45.400001 -40.4 90)" in text
    # the box of the centred text against the left-bottom one, in the reading frame at 90° to the footprint
    centred = estimate(TextKey("R1", MM, MM, STROKE, "center", "center"))
    corner = estimate(TextKey("R1", MM, MM, STROKE, "left", "bottom"))
    assert centred is not None and corner is not None
    half = rotate_point(Point(corner.x0 - centred.x0, corner.y1 - centred.y1), 90_000_000)
    at = f"(at {half.x / MM:.6f} {(-1_430_000 + half.y) / MM:.6f} 180)"
    start = text.index(head)
    end = text.index("(justify left bottom)", start)
    text = (
        text[:start]
        + text[start:end].replace("(at 0 -1.43 180)", at)
        + text[end:].replace("(justify left bottom)", "", 1)
    )
    pcb.write_text(text, encoding="utf-8")
    designator = _text_records(source.read_bytes())["R1"]
    written = _text_records(_back_document(project))["R1"]
    assert written[2:] == designator[2:]
    # a record holds lengths in units of 2.54 nm
    assert max(abs(written[0] - designator[0]), abs(written[1] - designator[1])) * 254 // 100 <= STROKE
