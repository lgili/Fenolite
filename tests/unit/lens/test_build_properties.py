# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""User properties on built footprints (capability design-dsl, "User properties on built footprints" and
the property rows of "Build evidence"; change c0027)."""

from __future__ import annotations

import dataclasses
import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest
from _buildhelp import LIBS, blink, build, project, resolver

from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.dsl import Design, placements, to_model
from fenolite.lens.build import PROPERTY_EVIDENCE, BuildOutput, build_design

ESCAPED = 'S-1 "q" \\ µ'


def variant(props: Mapping[str, Mapping[str, str]]) -> Design:
    d = blink()
    for ref, values in props.items():
        d.parts[ref].properties = dict(sorted(values.items()))
    return d


def model_build(extra: Mapping[str, str], ref: str = "R1") -> BuildOutput:
    """``build_design`` of ``to_model(blink)`` with ``extra`` added to ``ref``'s properties in the test."""
    d = blink()
    model = to_model(d)
    components = tuple(
        dataclasses.replace(c, properties={**c.properties, **extra}) if c.ref == ref else c
        for c in model.circuit.components
    )
    model = dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, components=components))
    return build_design(model, placements(d), name=d.name, copper=2, resolver=resolver(10), target=10)


def footprint_props(output: BuildOutput, ref: str) -> list[Node]:
    root = parse(output.files["blink.kicad_pcb"].decode("utf-8"))
    for fp in root.nodes("footprint"):
        props = fp.nodes("property")
        if any(p.atoms()[0].value == "Reference" and p.atoms()[1].value == ref for p in props):
            return props
    raise AssertionError(ref)


def test_written_after_the_path_property() -> None:
    out = build(variant({"R1": {"Supplier code": ESCAPED, "Part number": "PN-330"}}), 10)
    nodes = footprint_props(out, "R1")
    assert [p.atoms()[0].value for p in nodes[-3:]] == [PATH_PROPERTY, "Part number", "Supplier code"]
    for node in nodes[-3:]:
        layer = node.find("layer")
        assert layer is not None and layer.atoms()[0].value == "F.Fab" and node.find("hide") is not None
    back = {
        c.ref: c.properties
        for c in read_board(out.files["blink.kicad_pcb"].decode("utf-8")).circuit.components
    }
    assert back["R1"]["Supplier code"] == ESCAPED and back["R1"]["Part number"] == "PN-330"
    assert PROPERTY_EVIDENCE.hypotheses[0] in out.evidence.hypotheses


def test_bottom_part() -> None:
    out = build(variant({"D1": {"Part number": "PN-LED"}}), 9)
    (node,) = [p for p in footprint_props(out, "D1") if p.atoms()[0].value == "Part number"]
    layer, effects = node.find("layer"), node.find("effects")
    assert layer is not None and layer.atoms()[0].value == "B.Fab" and node.find("hide") is not None
    justify = effects.find("justify") if effects is not None else None
    assert justify is not None and "mirror" in [a.value for a in justify.atoms()]


@pytest.mark.parametrize("target", [9, 10])
def test_writer_accepts_the_properties_and_reads_them_back(target: int) -> None:
    out = build(
        variant({"R1": {"Part number": "PN-330", "Supplier code": ESCAPED}, "D1": {"MPN": "X"}}), target
    )
    assert not [i for i in out.issues if i.code == "kicad.board.projection-read-only"]
    back = {
        c.ref: c.properties
        for c in read_board(out.files["blink.kicad_pcb"].decode("utf-8")).circuit.components
    }
    assert {c.ref: c.properties for c in out.design.circuit.components} == back


def _uuids(output: BuildOutput) -> set[str]:
    def walk(node: Node) -> set[str]:
        found = {a.value for c in node.nodes("uuid") for a in c.atoms()}
        for child in node.children:
            if isinstance(child, Node):
                found |= walk(child)
        return found

    return walk(parse(output.files["blink.kicad_pcb"].decode("utf-8")))


def test_no_other_uuid_moves() -> None:
    plain = _uuids(build(blink(), 10))
    with_prop = _uuids(build(variant({"R1": {"Part number": "PN-330"}}), 10))
    assert plain < with_prop and len(with_prop - plain) == 1


def test_no_properties_give_c0011_bytes() -> None:
    assert build(blink(), 10).files == build(variant({"R1": {}}), 10).files
    assert PROPERTY_EVIDENCE.hypotheses[0] not in build(blink(), 10).evidence.hypotheses


def test_reserved_name_through_the_model() -> None:
    out = model_build({"Datasheet": "x"})
    assert out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.property-reserved"]
    assert found.where == "R1"


@pytest.mark.parametrize("name", ["ki_fp_filters", "FENOLITE.x", "value"])
def test_reserved_prefixes_and_case(name: str) -> None:
    out = model_build({name: "x"})
    assert out.files == {} and "build.property-reserved" in [i.code for i in out.issues]


def test_control_character_through_the_model() -> None:
    out = model_build({"Part number": "A\tB"})
    assert out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.property-invalid"]
    assert found.where == "R1"


def test_case_duplicates_through_the_model() -> None:
    out = model_build({"MPN": "a", "mpn": "b"})
    assert out.files == {} and "build.property-invalid" in [i.code for i in out.issues]


def _library_with_property(tmp_path: Path) -> Path:
    """A project folder whose ``Mini_R_0603`` holds the property ``Part number`` = ``LIB``."""
    pretty = tmp_path / "Mini.pretty"
    shutil.copytree(LIBS / "Mini_v9.pretty", pretty)
    path = pretty / "Mini_R_0603.kicad_mod"
    text = path.read_text(encoding="utf-8")
    anchor = '\t(property "Datasheet" ""'
    extra = (
        '\t(property "Part number" "LIB" (at 0 0 0) (layer "F.Fab") (hide yes) '
        '(uuid "00000000-0000-4000-8000-000000000999") (effects (font (size 1 1) (thickness 0.15))))\n'
    )
    path.write_text(text.replace(anchor, extra + anchor, 1), encoding="utf-8")
    return project(tmp_path, {"Mini": str(pretty)}, {"Mini": str(LIBS / "Mini_v9.kicad_sym")})


def test_library_property_with_the_same_name(tmp_path: Path) -> None:
    folder = _library_with_property(tmp_path)
    clash = build(variant({"R1": {"Part number": "PN-330"}}), 10, project_dir=folder)
    assert clash.files == {}
    (found,) = [i for i in clash.issues if i.code == "build.property-conflict"]
    assert "Part number" in found.message and "LIB" in found.message
    same = build(variant({"R1": {"Part number": "LIB"}}), 10, project_dir=folder)
    names = [p.atoms()[0].value for p in footprint_props(same, "R1")]
    assert names.count("Part number") == 1
