# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``Reference`` and ``Value`` fields of every placed footprint (capabilities kicad-file-backend,
"Mandatory fields of a placed footprint", and dsl-footprint-authoring, "Authored footprints carry
Reference and Value"; change c0077). Every value here is authored for Fenolite."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite import catalog
from fenolite.backends.kicad import embed, mod
from fenolite.backends.kicad.embed import (
    FIELD_GAP,
    FIELD_SIZE,
    FIELD_THICKNESS,
    FieldDefault,
    default_fields,
    footprint_extent,
    place_footprint,
    placement_uuid,
)
from fenolite.backends.kicad.fields import DEFAULT_GAP
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import prepare_authored_definition, read_footprint, write_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.core.coords import Point, Size
from fenolite.model.board import FootprintField, FootprintInstance
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

LIBS = Path(__file__).resolve().parents[4] / "tests" / "data" / "libs"
MM = 1_000_000
AT = Point(10 * MM, 10 * MM)
TWO_PAD = (
    "from fenolite.dsl import Design, Footprint, Part, mm\n"
    "design = Design('authored')\n"
    "design.board(mm(20), mm(15))\n"
    "fp = Footprint('Local', 'TwoPad', kind='smd')\n"
    "fp.pad('1', at=(mm(-1), mm(0)), size=(mm(1), mm(1)))\n"
    "fp.pad('2', at=(mm(1), mm(0)), size=(mm(1), mm(1)))\n"
    "fp.pad('2', at=(mm(1), mm(1)), size=(mm(2), mm(2)), shared=True)\n"
    "fp.rect((mm(-2), mm(-1)), (mm(2), mm(1)), layer='F.SilkS', width=mm(0.12))\n"
    "design.add_footprint(fp)\n"
    "r1 = Part('R1', 'Fenolite:Resistor', footprint=fp.lib_id, value='1k')\n"
    "design.add(r1)\n"
    "r1.place(mm(10), mm(7))\n"
)
"""The footprint ``Local:TwoPad`` of ``docs/dsl.md``, "Authored footprints", on a catalog symbol."""
CATALOG_PART = (
    "from fenolite.dsl import Design, Part, mm\n"
    "design = Design('catalog_part')\n"
    "design.board(mm(20), mm(15))\n"
    "r1 = Part('R1', 'Fenolite:Resistor', footprint='{footprint}', value='330')\n"
    "design.add(r1)\n"
    "r1.place(mm(10), mm(7))\n"
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def chip() -> FootprintDef:
    return prepare_authored_definition(catalog.get_footprint("Fenolite:Chip_0603"))


def component(ref: str = "R1", value: str = "330", n: int = 1) -> Component:
    return Component(id=f"cmp_00000000-0000-4000-8000-{n:012d}", ref=ref, value=value)


def design_with(part: Component, instance: FootprintInstance) -> Design:
    design = Design.new("placed", seed=1)
    assert design.board is not None
    board = dataclasses.replace(design.board, layers=created_layers(2), footprints=(instance,))
    return dataclasses.replace(design, circuit=Circuit(components=(part,)), board=board)


def written(part: Component, instance: FootprintInstance, target: int = 10) -> tuple[Node, str]:
    text = write_board(design_with(part, instance), target=target).text
    (fp,) = parse(text).nodes("footprint")
    return fp, text


def prop(fp: Node, name: str) -> Node:
    (found,) = [p for p in fp.nodes("property") if p.atoms()[0].value == name]
    return found


def field(instance: FootprintInstance, name: str) -> FootprintField:
    (found,) = [f for f in instance.fields if f.name == name]
    return found


def build(
    monkeypatch: pytest.MonkeyPatch, script: Path, out: Path, *flags: str, target: int = 10
) -> tuple[int, dict[str, object], dict[str, object]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    args = ["--kicad-version", str(target), "build", str(script), "--out", str(out), "--json"]
    code = cli_main.main([*args, *flags])
    return code, json.loads(stdout.getvalue() or "{}"), json.loads(stderr.getvalue() or "{}")


def changed(env: dict[str, object], out: Path) -> list[str]:
    """The planned files whose bytes differ from the file under ``out`` (or that ``out`` lacks)."""
    plan = env["result"]["plan"]  # type: ignore[index]
    assert plan
    return [
        Path(p["path"]).relative_to(out).as_posix()
        for p in plan
        if not Path(p["path"]).is_file()
        or hashlib.sha256(Path(p["path"]).read_bytes()).hexdigest() != p["sha256"]
    ]


def board_footprint(out: Path, name: str, ref: str) -> FootprintInstance:
    design = read_board(out / f"{name}.kicad_pcb")
    assert design.board is not None
    target = design.by_ref[ref].id
    return next(fp for fp in design.board.footprints if fp.component_id == target)


# --- default fields ---------------------------------------------------------------------------------


def test_default_fields_of_a_catalog_chip() -> None:
    defn = catalog.get_footprint("Fenolite:Chip_0603")
    box = footprint_extent(defn)
    assert (FIELD_GAP, FIELD_SIZE, FIELD_THICKNESS) == (MM, Size(MM, MM), 150_000)
    assert default_fields(defn) == (
        FieldDefault("Reference", "REF**", "F.SilkS", Point(0, box.y0 - MM)),
        FieldDefault("Value", "Chip_0603", "F.Fab", Point(0, box.y1 + MM)),
    )


def test_default_fields_without_courtyard_and_without_pads() -> None:
    defn = catalog.get_footprint("Fenolite:Chip_0603")
    pads_only = dataclasses.replace(defn, graphics=())
    box = footprint_extent(pads_only)
    reference, value = default_fields(pads_only)
    assert (reference.position, value.position) == (Point(0, box.y0 - MM), Point(0, box.y1 + MM))
    empty = dataclasses.replace(defn, graphics=(), pads=())
    assert [d.position for d in default_fields(empty)] == [Point(0, -MM), Point(0, MM)]


def test_prepared_definition_holds_both_properties() -> None:
    defn = catalog.get_footprint("Fenolite:Chip_0603")
    assert dict(defn.properties) == {}
    prepared = prepare_authored_definition(defn)
    assert (prepared.properties["Reference"], prepared.properties["Value"]) == ("REF**", "Chip_0603")
    assert (prepared.reference, prepared.value) == ("REF**", "Chip_0603")
    assert prepare_authored_definition(prepared) is prepared
    tree = parse(write_footprint(defn, target=10))
    heads = [c.name for c in tree.children if isinstance(c, Node)]
    first = heads.index("property")
    assert heads[first : first + 2] == ["property", "property"] and "pad" not in heads[:first]
    assert heads.index("attr") < first < heads.index("pad")
    reference, value = prop(tree, "Reference"), prop(tree, "Value")
    assert reference.atoms()[1].value == "REF**" and value.atoms()[1].value == "Chip_0603"
    assert reference.find("layer") == parse('(layer "F.SilkS")')
    assert value.find("layer") == parse('(layer "F.Fab")')
    for found, name in ((reference, "Reference"), (value, "Value")):
        assert found.find("uuid") == parse(f'(uuid "{embed.library_field_uuid("Fenolite:Chip_0603", name)}")')
        assert found.find("effects") == parse("(effects (font (size 1 1) (thickness 0.15)))")
        assert found.find("hide") is None
    for target in (9, 10):
        assert write_footprint(defn, target=target) == write_footprint(defn, target=target)
        again = read_footprint(write_footprint(defn, target=target), library="Fenolite")
        assert (again.reference, again.value) == ("REF**", "Chip_0603")


def test_an_authored_property_wins_over_the_default_text() -> None:
    defn = dataclasses.replace(
        catalog.get_footprint("Fenolite:Chip_0603"), properties={"Reference": "R**", "Tolerance": "1 %"}
    )
    prepared = prepare_authored_definition(defn)
    assert prepared.properties["Reference"] == "R**" and prepared.properties["Value"] == "Chip_0603"
    instance = place_footprint(prepared, component=component(), at=AT, key="R1")
    assert {"Reference", "Value"} <= {f.name for f in instance.fields}


def test_a_definition_that_is_not_prepared_gains_nothing() -> None:
    defn = catalog.get_footprint("Fenolite:Chip_0603")
    prepare_authored_definition(defn)
    assert dict(defn.properties) == {} and "kicad" not in defn.ext
    assert dict(catalog.get_footprint("Fenolite:Chip_0603").properties) == {}


# --- placement --------------------------------------------------------------------------------------


def test_catalog_footprint_placed_on_top() -> None:
    r1 = component()
    defn = chip()
    box = footprint_extent(defn)
    instance = place_footprint(defn, component=r1, at=AT, key="R1")
    fp, text = written(r1, instance)
    reference, value = prop(fp, "Reference"), prop(fp, "Value")
    assert reference.atoms()[1].value == "R1" and value.atoms()[1].value == "330"
    assert reference.find("layer") == parse('(layer "F.SilkS")')
    assert value.find("layer") == parse('(layer "F.Fab")')
    for found in (reference, value):
        assert found.find("effects") == parse("(effects (font (size 1 1) (thickness 0.15)))")
    above, below = field(instance, "Reference"), field(instance, "Value")
    assert above.position == Point(0, box.y0 - FIELD_GAP) and above.position.y < box.y0
    assert below.position == Point(0, box.y1 + FIELD_GAP) and below.position.y > box.y1
    for found in (above, below):
        assert (found.size, found.thickness, found.rotation) == (FIELD_SIZE, FIELD_THICKNESS, 0)
        assert (found.visible, found.mirrored, found.h_justify, found.v_justify) == (
            True,
            False,
            "center",
            "center",
        )
    names = [p.atoms()[0].value for p in fp.nodes("property")]
    assert names == ["Reference", "Value"]
    read = read_board(text)
    assert [c.ref for c in read.circuit.components] == ["R1"]
    assert read.circuit.components[0].value == "330"
    assert read.board is not None
    assert [f.name for f in read.board.footprints[0].fields] == ["Reference", "Value"]


def test_bottom_side() -> None:
    r1 = component()
    instance = place_footprint(chip(), component=r1, at=AT, side="bottom", key="R1")
    reference, value = field(instance, "Reference"), field(instance, "Value")
    assert (reference.layer, value.layer) == ("B.SilkS", "B.Fab")
    assert reference.mirrored and value.mirrored
    fp, _ = written(r1, instance)
    for name in ("Reference", "Value"):
        justify = prop(fp, name).find("effects")
        assert justify is not None and justify.find("justify") == parse("(justify mirror)")


def test_deterministic_uuids() -> None:
    first = place_footprint(chip(), component=component(), at=AT, key="R1")
    again = place_footprint(chip(), component=component(), at=AT, key="R1")
    other = place_footprint(chip(), component=component("R2", n=2), at=AT, key="R2")

    def uuids(instance: FootprintInstance) -> list[str]:
        return [f.native_ids["kicad"] for f in instance.fields]

    assert uuids(first) == uuids(again) and len(set(uuids(first))) == 2
    assert set(uuids(first)).isdisjoint(uuids(other))
    assert first == again
    # the fields of a prepared definition are children of the definition: their uuids follow its locators
    assert uuids(first) == [placement_uuid("R1", f"/footprint/property[{i}]") for i in range(2)]


def test_every_catalog_footprint() -> None:
    entries = catalog.list_entries(kind="footprint")
    assert len(entries) >= 100
    for n, entry in enumerate(entries, start=1):
        defn = prepare_authored_definition(catalog.get_footprint(entry.lib_id))
        box = footprint_extent(defn)
        part = component(f"X{n}", "V", n)
        instance = place_footprint(defn, component=part, at=Point(0, 0), key=part.ref)
        names = [f.name for f in instance.fields]
        assert names.count("Reference") == 1 and names.count("Value") == 1, entry.lib_id
        for name in ("Reference", "Value"):
            assert not box.contains_point(field(instance, name).position), (entry.lib_id, name)
        assert defn.properties["Value"] == defn.name and defn.properties["Reference"] == "REF**"


# --- library footprints -----------------------------------------------------------------------------


def mini(name: str = "Mini_R_0603") -> FootprintDef:
    return read_footprint(LIBS / "Mini.pretty" / f"{name}.kicad_mod", library="Mini")


def test_library_footprint_keeps_its_own_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    r1 = component(value="1k")
    after = place_footprint(mini(), component=r1, at=AT, key="R1")
    with monkeypatch.context() as patch:
        # the placement before this requirement: no field is ever added
        patch.setattr(embed, "_with_mandatory", lambda tree, defn, key: tree)
        before = place_footprint(mini(), component=r1, at=AT, key="R1")
    assert after == before
    assert embed.uuid_locators(mini()).count("/footprint/property:Reference") == 0
    assert not any(loc.startswith("/footprint/property:") for loc in embed.uuid_locators(mini()))


def no_reference_library(folder: Path, drop: str = "Reference") -> Path:
    """A project folder whose library ``NoRef`` holds a copy of ``Mini_R_0603`` without ``drop``."""
    library = folder / "NoRef.pretty"
    library.mkdir(parents=True)
    source = parse((LIBS / "Mini_v9.pretty" / "Mini_R_0603.kicad_mod").read_text(encoding="utf-8"))
    kept = [
        c
        for c in source.children
        if not (isinstance(c, Node) and c.name == "property" and c.atoms()[0].value == drop)
    ]
    assert len(kept) == len(source.children) - 1
    text = dumps(source.with_children(kept), style="kicad").replace('"Mini_R_0603"', '"NoRef_R"', 1)
    (library / "NoRef_R.kicad_mod").write_text(text, encoding="utf-8")
    row = f'\t(lib (name "NoRef") (type "KiCad") (uri "{library.as_posix()}") (options "") (descr ""))\n'
    (folder / "fp-lib-table").write_text(f"(fp_lib_table\n\t(version 7)\n{row})\n", encoding="utf-8")
    script = folder / "design.py"
    script.write_text(CATALOG_PART.format(footprint="NoRef:NoRef_R"), encoding="utf-8")
    return script


def test_library_footprint_without_a_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = no_reference_library(tmp_path / "P")
    out = tmp_path / "out"
    code, env, err = build(monkeypatch, script, out, "--confirm")
    assert code == 0, err
    issues = [i for i in env["issues"] if i["code"] == "build.field-added"]  # type: ignore[index, union-attr]
    assert len(issues) == 1 and issues[0]["severity"] == "info"
    assert "NoRef:NoRef_R" in issues[0]["message"] and "Reference" in issues[0]["message"]
    assert "Value" not in issues[0]["message"] and issues[0]["where"] == "NoRef:NoRef_R"
    defn = read_footprint(tmp_path / "P" / "NoRef.pretty" / "NoRef_R.kicad_mod", library="NoRef")
    assert "Reference" not in defn.properties
    expected = default_fields(defn)[0]
    placed = board_footprint(out, "catalog_part", "R1")
    reference = field(placed, "Reference")
    assert (reference.position, reference.layer) == (expected.position, "F.SilkS")
    assert (reference.size, reference.thickness, reference.visible) == (FIELD_SIZE, FIELD_THICKNESS, True)
    assert reference.native_ids["kicad"] == placement_uuid("R1", "/footprint/property:Reference")
    assert [f.name for f in placed.fields][:2] == ["Reference", "Value"]
    assert "/footprint/property:Reference" in embed.uuid_locators(defn)
    # the same build again plans no change
    code, env, err = build(monkeypatch, script, out, "--dry-run")
    assert code == 0, err
    assert changed(env, out) == []


def test_library_footprint_without_a_reference_on_the_bottom() -> None:
    source = parse((LIBS / "Mini.pretty" / "Mini_R_0603.kicad_mod").read_text(encoding="utf-8"))
    kept = [
        c
        for c in source.children
        if not (isinstance(c, Node) and c.name == "property" and c.atoms()[0].value == "Reference")
    ]
    defn = read_footprint(dumps(source.with_children(kept), style="kicad"), library="Mini")
    instance = place_footprint(defn, component=component(), at=AT, side="bottom", key="R1")
    reference = field(instance, "Reference")
    assert (reference.layer, reference.mirrored) == ("B.SilkS", True)
    fp, _ = written(component(), instance)
    assert prop(fp, "Reference").atoms()[1].value == "R1"
    # the fields the library gave keep the uuids they had before a field was added
    with_reference = place_footprint(mini(), component=component(), at=AT, side="bottom", key="R1")
    assert field(instance, "Value").native_ids["kicad"] == placement_uuid("R1", "/footprint/property[0]")
    assert field(with_reference, "Value").native_ids["kicad"] == placement_uuid(
        "R1", "/footprint/property[1]"
    )


def test_library_footprint_prepared_definitions_report_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "design.py"
    script.write_text(CATALOG_PART.format(footprint="Fenolite:Chip_0603"), encoding="utf-8")
    code, env, err = build(monkeypatch, script, tmp_path / "out", "--dry-run")
    assert code == 0, err
    assert not [i for i in env["issues"] if i["code"] == "build.field-added"]  # type: ignore[index, union-attr]


# --- authored footprints and field requests ---------------------------------------------------------


@pytest.mark.parametrize("target", [9, 10])
def test_authored_two_pad_footprint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int) -> None:
    script = tmp_path / "design.py"
    script.write_text(TWO_PAD, encoding="utf-8")
    first, second = tmp_path / "A", tmp_path / "B"
    for out in (first, second):
        code, env, err = build(monkeypatch, script, out, "--confirm", target=target)
        assert code == 0, err
        assert env["result"]["libraries"]["Local:TwoPad"] == "authored"  # type: ignore[index]
        assert not [i for i in env["issues"] if i["code"] == "build.field-added"]  # type: ignore[index, union-attr]
    library = (first / "lib" / "Local.pretty" / "TwoPad.kicad_mod").read_text(encoding="utf-8")
    assert '(property "Reference" "REF**"' in library and '(property "Value" "TwoPad"' in library
    placed = board_footprint(first, "authored", "R1")
    assert {"Reference", "Value"} <= {f.name for f in placed.fields}
    board = (first / "authored.kicad_pcb").read_text(encoding="utf-8")
    assert '(property "Reference" "R1"' in board and '(property "Value" "1k"' in board
    for rel in ("lib/Local.pretty/TwoPad.kicad_mod", "authored.kicad_pcb"):
        assert (first / rel).read_bytes() == (second / rel).read_bytes()


def test_field_request_on_a_catalog_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = tmp_path / "design.py"
    requests = "r1.field('Reference', outside='top')\nr1.field('Value', visible=False)\n"
    script.write_text(CATALOG_PART.format(footprint="Fenolite:Chip_0603") + requests, encoding="utf-8")
    code, _, err = build(monkeypatch, script, tmp_path / "out", "--confirm")
    assert code == 0, err
    placed = board_footprint(tmp_path / "out", "catalog_part", "R1")
    box = footprint_extent(catalog.get_footprint("Fenolite:Chip_0603"))
    reference, value = field(placed, "Reference"), field(placed, "Value")
    assert reference.position == Point(0, box.y0 - DEFAULT_GAP - FIELD_THICKNESS // 2)
    assert (reference.v_justify, reference.visible) == ("bottom", True)
    assert value.visible is False and value.position == Point(0, box.y1 + FIELD_GAP)


def test_mod_module_names_the_function() -> None:
    assert mod.prepare_authored_definition is prepare_authored_definition
