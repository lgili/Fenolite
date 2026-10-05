# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic reader (capability kicad-schematic: "Schematic file reading", "Schematic version
policy", "Modelled schematic content", "Symbol instances", "Labels, no-connect flags and sheet
references", "Embedded symbol definitions", "Unmodelled schematic content is kept as slots", "Exact
numbers on schematics", "Identifiers of schematic items" and "Schematic read issue codes"; c0060)."""

from __future__ import annotations

import re
from pathlib import Path

import _schfix as fx
import pytest

from fenolite.backends.kicad import sch
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.sexpr import Node
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.backends.kicad.versions import FileKind, FutureFormatError, UnsupportedFormatError, min_version
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id
from fenolite.model.base import Modeled, Opaque, Slot
from fenolite.model.presentation import SheetFrameRef
from fenolite.model.schematic import SchematicSheet, SymbolInstance

ROOT = Path(__file__).resolve().parents[4]
MM = 1_000_000


def read(name: str, issues: list[Issue] | None = None) -> SchematicSheet:
    return sch.read_schematic(fx.SCHEMATICS / name, issues=issues)


def by_ref(sheet: SchematicSheet, ref: str) -> SymbolInstance:
    return next(s for s in sheet.symbols if s.ref == ref)


def slots_of(entity: object, rel: str = ".") -> tuple[Slot, ...]:
    return slotlib.from_ext(entity.ext["kicad"], rel)  # type: ignore[attr-defined]


def codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


# -- "Schematic file reading"


def test_authored_flat_sheet() -> None:
    issues: list[Issue] = []
    sheet = read("flat.kicad_sch", issues)
    assert sheet.name == "flat" and issues == []
    assert [s.ref for s in sheet.symbols] == ["R1", "D1", "U1", "#PWR01", "R2", "R3"]
    kinds = [label.kind for label in sheet.labels]
    assert kinds.count("local") == 1 and kinds.count("global") >= 3
    assert sheet.provenance is not None and sheet.provenance.backend == "kicad"


def test_text_and_node_sources() -> None:
    text = fx.text_of("flat.kicad_sch")
    from_text = sch.read_schematic(text)
    assert from_text.name == ""
    from_node = sch.read_schematic(fx.tree_of("flat.kicad_sch"), file="some/dir/flat.kicad_sch")
    assert from_node.name == "flat"
    assert [s.id for s in from_node.symbols] == [s.id for s in from_text.symbols]


def test_wrong_root() -> None:
    with pytest.raises(FormatError, match="kicad_pcb"):
        sch.read_schematic("(kicad_pcb (version 20241229))")


def test_reads_are_repeatable() -> None:
    first, second = read("flat.kicad_sch"), read("flat.kicad_sch")
    assert first == second
    ids = [e.id for e in sch._entities(first)]  # pyright: ignore[reportPrivateUsage]
    assert len(ids) == len(set(ids))


# -- "Schematic version policy"


def test_older_than_the_floor() -> None:
    old = fx.text(fx.with_version(fx.tree_of("flat.kicad_sch"), 20230121))
    with pytest.raises(UnsupportedFormatError) as caught:
        sch.read_schematic(old)
    assert "20230121" in str(caught.value) and "20231120" in str(caught.value)


def test_newer_than_the_newest_constant() -> None:
    issues: list[Issue] = []
    sheet = sch.read_schematic(
        fx.text(fx.with_version(fx.tree_of("flat.kicad_sch"), 20990101)), issues=issues
    )
    assert "kicad.version.future" in codes(issues)
    assert len(sheet.symbols) == 6
    with pytest.raises(FutureFormatError):
        sch.rebuild_schematic(sheet)


def test_development_version() -> None:
    issues: list[Issue] = []
    sheet = sch.read_schematic(
        fx.text(fx.with_version(fx.tree_of("flat_v9.kicad_sch"), 20250610)), issues=issues
    )
    assert not [i for i in issues if i.code.startswith("kicad.version.") and i.severity == "error"]
    info = sch.source_info(sheet)
    assert info is not None and info.version == 20250610 and info.major == 10


def test_missing_version() -> None:
    root = fx.edit_root(fx.tree_of("flat.kicad_sch"), lambda kids: kids.pop(0))
    with pytest.raises(FormatError, match="version"):
        sch.read_schematic(fx.text(root))


# -- "Modelled schematic content"


def test_wire_and_junction_stay_opaque() -> None:
    sheet = read("flat.kicad_sch")
    root = fx.tree_of("flat.kicad_sch")
    slots = slots_of(sheet)
    assert len(slots) == len(root.children)
    for slot, child in zip(slots, root.children, strict=True):
        if isinstance(child, Node) and child.name in (
            "wire",
            "junction",
            "text",
            "version",
            "embedded_fonts",
        ):
            assert isinstance(slot, Opaque) and slot.fragment.startswith(f"({child.name} ")
    assert not {"wires", "junctions"} & {f for f in SchematicSheet.__dataclass_fields__}


def test_unknown_root_child_survives_in_place() -> None:
    root = fx.edit_root(
        fx.tree_of("flat.kicad_sch"), lambda kids: kids.insert(6, fx.fragment("(frobnicate 1)"))
    )
    sheet = sch.read_schematic(fx.text(root))
    slot = slots_of(sheet)[6]
    assert isinstance(slot, Opaque) and slot.fragment == "(frobnicate 1)"
    assert sch.rebuild_schematic(sheet) == root


def test_paper_and_title_block() -> None:
    sheet = read("flat.kicad_sch")
    assert sheet.paper == SheetFrameRef("A4")
    assert sheet.title_block is not None
    assert sheet.title_block.title == "Flat" and sheet.title_block.revision == "A"
    assert sheet.native_ids["kicad"] == fx.tree_of("flat.kicad_sch").find("uuid").atoms()[0].value  # type: ignore[union-attr]
    bare = fx.edit_root(
        fx.tree_of("flat.kicad_sch"),
        lambda kids: kids.pop(
            next(i for i, c in enumerate(kids) if isinstance(c, Node) and c.name == "title_block")
        ),
    )
    assert sch.read_schematic(fx.text(bare)).title_block is None


def test_unmodelled_paper_is_kept() -> None:
    issues: list[Issue] = []
    root = fx.edit_root(
        fx.tree_of("flat.kicad_sch"), lambda kids: fx.set_child(kids, fx.fragment('(paper "USLetter")'))
    )
    sheet = sch.read_schematic(fx.text(root), issues=issues)
    assert codes(issues) == ["kicad.sch.kept-opaque"]
    assert sch.rebuild_schematic(sheet) == root


def test_pages() -> None:
    assert [(p.path, p.page) for p in read("flat.kicad_sch").pages] == [("/", "1")]
    assert read("hier/child.kicad_sch").pages == ()


# -- "Symbol instances"


def test_resistor_of_the_flat_sheet() -> None:
    r1 = by_ref(read("flat.kicad_sch"), "R1")
    assert r1.lib_ref == "Mini:Mini_R" and r1.unit == 1 and r1.value == "330"
    assert r1.footprint == "Mini:Mini_R_0603" and r1.dnp is False and r1.lib_name == ""
    assert r1.position == Point(100 * MM, 50 * MM) and r1.rotation == 0 and r1.mirror == ""
    assert len(r1.uses) == 1
    use = r1.uses[0]
    assert use.project == "flat" and use.ref == "R1" and use.path.startswith("/") and use.unit == 1
    assert r1.properties["Description"] == "Series resistor"


def test_flags() -> None:
    sheet = read("flat.kicad_sch")
    assert by_ref(sheet, "R2").dnp is True and by_ref(sheet, "R2").on_board is True
    assert by_ref(sheet, "R3").on_board is False and by_ref(sheet, "R3").dnp is False
    assert by_ref(sheet, "R1").in_bom is True and by_ref(sheet, "R1").exclude_from_sim is False


def test_three_units_under_one_reference() -> None:
    for name in ("units.kicad_sch", "units_v9.kicad_sch"):
        sheet = read(name)
        assert [s.ref for s in sheet.symbols] == ["U2", "U2", "U2"]
        assert [s.unit for s in sheet.symbols] == [1, 2, 3]


def test_rotated_and_mirrored() -> None:
    def change(kids: fx.Children) -> None:
        fx.set_child(kids, fx.fragment("(at 100 50 90)"))
        kids.insert(2, fx.fragment("(mirror y)"))

    root = fx.edit_symbol(fx.tree_of("flat.kicad_sch"), "D1", change)
    d1 = by_ref(sch.read_schematic(fx.text(root)), "D1")
    assert d1.rotation == 90_000_000 and d1.mirror == "y" and d1.position == Point(100 * MM, 50 * MM)


def test_undefined_symbol() -> None:
    def drop(kids: fx.Children) -> None:
        index = next(i for i, c in enumerate(kids) if isinstance(c, Node) and c.name == "lib_symbols")
        lib = kids[index]
        assert isinstance(lib, Node)
        kids[index] = lib.with_children(
            [c for c in lib.children if not (isinstance(c, Node) and c.atoms()[0].value == "Mini:Mini_LED")]
        )

    issues: list[Issue] = []
    sheet = sch.read_schematic(fx.text(fx.edit_root(fx.tree_of("flat.kicad_sch"), drop)), issues=issues)
    assert by_ref(sheet, "D1").lib_ref == "Mini:Mini_LED"
    found = [i for i in issues if i.code == "kicad.sch.symbol-undefined"]
    assert len(found) == 1 and found[0].severity == "warning" and "Mini:Mini_LED" in found[0].message


def test_lib_name_decides_the_embedded_symbol() -> None:
    root = fx.edit_symbol(
        fx.tree_of("flat.kicad_sch"), "R1", lambda kids: kids.insert(0, fx.fragment('(lib_name "Mini_R_1")'))
    )
    issues: list[Issue] = []
    r1 = by_ref(sch.read_schematic(fx.text(root), issues=issues), "R1")
    assert r1.lib_name == "Mini_R_1" and r1.lib_ref == "Mini:Mini_R"
    assert [i.code for i in issues] == ["kicad.sch.symbol-undefined"] and "Mini_R_1" in issues[0].message


def test_duplicate_property() -> None:
    root = fx.edit_symbol(
        fx.tree_of("flat.kicad_sch"),
        "R1",
        lambda kids: kids.append(fx.fragment('(property "Value" "470" (at 0 0 0))')),
    )
    issues: list[Issue] = []
    sheet = sch.read_schematic(fx.text(root), issues=issues)
    assert next(s for s in sheet.symbols if s.ref == "R1").value == "470"
    assert codes(issues) == ["kicad.sch.duplicate-property"] and issues[0].severity == "warning"


def test_two_uses_of_one_symbol() -> None:
    cell = read("multi/cell.kicad_sch")
    resistor = cell.symbols[0]
    assert [u.ref for u in resistor.uses] == ["R1", "R2"]
    assert {u.project for u in resistor.uses} == {"top"} and resistor.uses[0].path != resistor.uses[1].path


# -- "Labels, no-connect flags and sheet references"


def test_three_kinds_of_label() -> None:
    child = read("hier/child.kicad_sch")
    assert [(lb.kind, lb.name, lb.shape) for lb in child.labels] == [("hierarchical", "IN", "input")]
    flat = read("flat.kicad_sch")
    local = next(lb for lb in flat.labels if lb.kind == "local")
    assert local.name == "LED_A" and local.shape == "" and local.position == Point(102_540_000, 57_150_000)
    vcc = next(lb for lb in flat.labels if lb.kind == "global")
    assert vcc.name == "VCC" and vcc.shape == "input" and vcc.rotation == 90_000_000
    label_slots = slots_of(vcc)
    assert isinstance(label_slots[0], Modeled) and label_slots[0].field == "name"
    opaque = [s.fragment.split(" ")[0] for s in label_slots if isinstance(s, Opaque)]
    assert opaque == ["(fields_autoplaced", "(effects", "(property"]


def test_no_connect_flags() -> None:
    sheet = read("flat.kicad_sch")
    root = fx.tree_of("flat.kicad_sch")
    assert len(sheet.no_connects) == len(root.nodes("no_connect")) == 2
    assert [f.position for f in sheet.no_connects] == [
        Point(147_300_000, 60_950_000),
        Point(147_300_000, 63_490_000),
    ]


def test_sheet_reference() -> None:
    top = read("hier/top.kicad_sch")
    assert len(top.sheets) == 1
    ref = top.sheets[0]
    assert ref.name == "Child" and ref.file == "child.kicad_sch"
    assert ref.position == Point(100 * MM, 50 * MM) and (ref.size.w, ref.size.h) == (20 * MM, 10 * MM)
    assert [(u.project, u.page) for u in ref.uses] == [("top", "2")] and ref.uses[0].path.startswith("/")
    opaque = [s.fragment.split(" ")[0] for s in slots_of(ref) if isinstance(s, Opaque)]
    assert "(pin" in opaque and "(stroke" in opaque and "(fill" in opaque and opaque.count("(property") == 2


def test_sheet_without_a_file() -> None:
    def drop(kids: fx.Children) -> None:
        index = next(i for i, c in enumerate(kids) if isinstance(c, Node) and c.name == "sheet")
        sheet = kids[index]
        assert isinstance(sheet, Node)
        kids[index] = sheet.with_children(
            [
                c
                for c in sheet.children
                if not (isinstance(c, Node) and c.name == "property" and c.atoms()[0].value == "Sheetfile")
            ]
        )

    issues: list[Issue] = []
    top = sch.read_schematic(fx.text(fx.edit_root(fx.tree_of("hier/top.kicad_sch"), drop)), issues=issues)
    assert top.sheets[0].file == "" and codes(issues) == ["kicad.sch.sheet-file-missing"]


# -- "Embedded symbol definitions"


def test_embedded_resistor() -> None:
    sheet = read("flat.kicad_sch")
    resistor = next(s for s in sheet.lib_symbols if s.name == "Mini_R")
    assert resistor.library == "Mini" and [p.number for p in resistor.pins] == ["1", "2"]
    library = read_symbol_library(ROOT / "tests" / "data" / "libs" / "Mini.kicad_sym")
    assert resistor.id != next(s for s in library if s.name == "Mini_R").id
    uuid = sheet.native_ids["kicad"]
    assert resistor.id == derived_id("sym", "kicad", f"sch:{uuid}:Mini:Mini_R")
    assert any(
        isinstance(s, Opaque) and s.fragment.startswith('(symbol "Mini_R_1_1"') for s in slots_of(resistor)
    )
    assert [s.name for s in sheet.lib_symbols] == ["Mini_GND", "Mini_LED", "Mini_QFP32_IC", "Mini_R"]


def test_embedded_name_without_a_library() -> None:
    def rename(kids: fx.Children) -> None:
        index = next(i for i, c in enumerate(kids) if isinstance(c, Node) and c.name == "lib_symbols")
        lib = kids[index]
        assert isinstance(lib, Node)
        text = fx.text(lib).replace('"Mini:Mini_GND"', '"Local_R"').replace('"Mini_GND_', '"Local_R_')
        kids[index] = fx.fragment(text)

    sheet = sch.read_schematic(fx.text(fx.edit_root(fx.tree_of("flat.kicad_sch"), rename)))
    first = sheet.lib_symbols[0]
    assert first.library == "" and first.name == "Local_R"


# -- "Unmodelled schematic content is kept as slots"


def test_property_is_projected() -> None:
    r1 = by_ref(read("flat.kicad_sch"), "R1")
    fragments = [s.fragment for s in slots_of(r1) if isinstance(s, Opaque)]
    assert any(f.startswith('(property "Value" "330"') for f in fragments) and r1.value == "330"
    assert any(f.startswith("(instances ") for f in fragments)
    assert sum(f.startswith("(pin ") for f in fragments) == 2
    modeled = [s.field for s in slots_of(r1) if isinstance(s, Modeled)]
    assert modeled == [
        "lib_ref", "position", "unit", "body_style", "exclude_from_sim", "in_bom", "on_board", "dnp",
        "native_ids",
    ]  # fmt: skip


def test_older_spelling_kept() -> None:
    root = fx.edit_symbol(
        fx.with_version(fx.tree_of("flat_v9.kicad_sch"), 20231120),
        "R1",
        lambda kids: kids.insert(3, fx.fragment("(convert 1)")),
    )
    issues: list[Issue] = []
    sheet = sch.read_schematic(fx.text(root), issues=issues)
    r1 = by_ref(sheet, "R1")
    assert r1.body_style == 1
    slot = slots_of(r1)[3]
    assert isinstance(slot, Opaque) and slot.fragment == "(convert 1)"
    kept = [i for i in issues if i.code == "kicad.sch.kept-opaque" and "/symbol[0]/convert" in i.where]
    assert len(kept) == 1 and kept[0].severity == "info"
    assert sch.rebuild_schematic(sheet) == root


def test_opaque_slots_carry_a_version() -> None:
    sheet = read("flat_v9.kicad_sch")
    for entity in sch._entities(sheet):  # pyright: ignore[reportPrivateUsage]
        for slot in slots_of(entity):
            if isinstance(slot, Opaque):
                assert slot.min_version is not None and 20231120 <= int(slot.min_version) <= 20250114


def test_minimum_version_from_the_inventory() -> None:
    row = min_version(FileKind.SCHEMATIC, "kicad_sch/symbol/in_pos_files")
    if row is None:
        pytest.skip("the inventory has no kicad_sch row for symbol/in_pos_files")
    r1 = by_ref(read("flat.kicad_sch"), "R1")
    slot = next(s for s in slots_of(r1) if isinstance(s, Opaque) and s.fragment.startswith("(in_pos_files"))
    assert slot.min_version == str(row) and row > 20250114 and row != 20260306


# -- "Exact numbers on schematics"


def test_sub_nanometre_position() -> None:
    root = fx.edit_symbol(
        fx.tree_of("flat.kicad_sch"),
        "D1",
        lambda kids: fx.set_child(kids, fx.fragment("(at 100.0000001 50 0)")),
    )
    issues: list[Issue] = []
    sheet = sch.read_schematic(fx.text(root), issues=issues)
    assert "D1" not in [s.ref for s in sheet.symbols] and len(sheet.symbols) == 5
    index = next(i for i, c in enumerate(root.children) if isinstance(c, Node) and fx.reference(c) == "D1")
    slot = slots_of(sheet)[index]
    assert isinstance(slot, Opaque) and slot.fragment.startswith('(symbol (lib_id "Mini:Mini_LED")')
    assert codes(issues) == ["kicad.sch.inexact-length"] and "/kicad_sch/symbol[1]" in issues[0].where
    assert sch.rebuild_schematic(sheet) == root


@pytest.mark.parametrize("child", ["(at 100 50 45)", "(mirror z)"])
def test_odd_symbol_angle_and_mirror(child: str) -> None:
    def change(kids: fx.Children) -> None:
        if child.startswith("(at"):
            fx.set_child(kids, fx.fragment(child))
        else:
            kids.insert(2, fx.fragment(child))

    root = fx.edit_symbol(fx.tree_of("flat.kicad_sch"), "D1", change)
    issues: list[Issue] = []
    sheet = sch.read_schematic(fx.text(root), issues=issues)
    assert len(sheet.symbols) == 5 and codes(issues) == ["kicad.sch.kept-opaque"]
    assert issues[0].where == "/kicad_sch/symbol[1]"
    assert sch.rebuild_schematic(sheet) == root


def test_inexact_label_angle() -> None:
    text = fx.text_of("flat.kicad_sch").replace("(at 102.54 57.15 0)", "(at 102.54 57.15 0.0000001)")
    issues: list[Issue] = []
    sheet = sch.read_schematic(text, issues=issues)
    assert not [lb for lb in sheet.labels if lb.kind == "local"]
    assert codes(issues) == ["kicad.sch.inexact-angle"]


# -- "Identifiers of schematic items"


def test_stable_ids() -> None:
    first, second = read("flat.kicad_sch"), read("flat.kicad_sch")
    uuid = fx.tree_of("flat.kicad_sch").find("uuid").atoms()[0].value  # type: ignore[union-attr]
    assert first.id == second.id == derived_id("sch", "kicad", uuid)
    r1 = by_ref(first, "R1")
    assert r1.id == derived_id("sci", "kicad", r1.native_ids["kicad"]) and r1.id.startswith("sci_")
    assert first.labels[0].id.startswith("lbl_") and first.no_connects[0].id.startswith("ncf_")
    assert read("hier/top.kicad_sch").sheets[0].id.startswith("shr_")


def test_repeated_uuid() -> None:
    root = fx.tree_of("flat.kicad_sch")
    flags = root.nodes("no_connect")
    first = flags[0].find("uuid").atoms()[0].value  # type: ignore[union-attr]
    second = flags[1].find("uuid").atoms()[0].value  # type: ignore[union-attr]
    issues: list[Issue] = []
    sheet = sch.read_schematic(fx.text_of("flat.kicad_sch").replace(second, first), issues=issues)
    assert [f.id for f in sheet.no_connects] == [
        derived_id("ncf", "kicad", first),
        derived_id("ncf", "kicad", f"{first}:1"),
    ]
    assert [f.native_ids["kicad"] for f in sheet.no_connects] == [first, first]
    assert codes(issues) == ["kicad.sch.duplicate-uuid"] and issues[0].severity == "warning"


def test_items_without_uuid_take_content_ids() -> None:
    def strip(kids: fx.Children) -> None:
        for index, child in enumerate(kids):
            if isinstance(child, Node) and child.name == "no_connect":
                kids[index] = child.with_children(
                    [c for c in child.children if not (isinstance(c, Node) and c.name == "uuid")]
                )

    text = fx.text(fx.edit_root(fx.tree_of("flat.kicad_sch"), strip))
    first, second = sch.read_schematic(text), sch.read_schematic(text)
    ids = [f.id for f in first.no_connects]
    assert len(set(ids)) == 2 and ids == [f.id for f in second.no_connects]
    assert all(f.native_ids == {} for f in first.no_connects)


def test_sheet_without_uuid_is_named_by_its_file() -> None:
    def strip(kids: fx.Children) -> None:
        kids.pop(next(i for i, c in enumerate(kids) if isinstance(c, Node) and c.name == "uuid"))

    text = fx.text(fx.edit_root(fx.tree_of("flat.kicad_sch"), strip))
    sheet = sch.read_schematic(text, file="x/board.kicad_sch")
    assert sheet.id == derived_id("sch", "kicad", "file:board") and sheet.native_ids == {}


# -- "Schematic read issue codes"


def test_codes_are_a_closed_set() -> None:
    source = (ROOT / "src" / "fenolite" / "backends" / "kicad" / "sch.py").read_text(encoding="utf-8")
    literals = set(re.findall(r'"(kicad\.sch\.[a-z0-9.-]+)"', source))
    assert literals == set(sch.ISSUE_CODES) | set(sch.WRITE_ISSUE_CODES)  # the writer's codes: c0061
    assert dict(sch.ISSUE_CODES) == {
        "kicad.sch.kept-opaque": "info",
        "kicad.sch.inexact-length": "info",
        "kicad.sch.inexact-angle": "info",
        "kicad.sch.duplicate-property": "warning",
        "kicad.sch.duplicate-uuid": "warning",
        "kicad.sch.symbol-undefined": "warning",
        "kicad.sch.sheet-file-missing": "warning",
        "kicad.sch.sheet-missing": "warning",
        "kicad.sch.sheet-outside": "info",
        "kicad.sch.sheet-cycle": "error",
    }


def test_evidence() -> None:
    from fenolite.core.evidence import Level

    assert sch.EVIDENCE.hypotheses == ("H-K-SCH-READ", "H-K-SCH-COMPONENTS-2")
    assert sch.EVIDENCE.level == Level.CORPUS_VERIFIED  # the lower of the two rows in the register


def test_fixture_generators() -> None:
    for name in fx.FIXTURES:
        generator = fx.tree_of(name).find("generator")
        assert generator is not None and generator.atoms()[0].value != "eeschema"
