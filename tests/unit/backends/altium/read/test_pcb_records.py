# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Property kinds of the PCB reader (capability altium-pcb-reader, "Nets, components and classes",
"Region and polygon records" and "Rules kept opaque", change c0041)."""

from __future__ import annotations

from fractions import Fraction

from _altium_long import block, document, rule

from fenolite.backends.altium.read.pcb import decode_name, read_pcbdoc


def test_net_unknown_key_and_duplicate() -> None:
    doc = read_pcbdoc(
        document({"Nets6": [block("|NAME=GND|XYZZY=1|XYZZY=2"), block("|NAME=VIN|UNIQUEID=ABC")]})
    )
    gnd, vin = doc.nets
    assert gnd.fields == (("NAME", "GND"), ("XYZZY", "1"), ("XYZZY", "2"))
    assert gnd.name == "GND" and gnd.unique_id is None
    assert vin.unique_id == "ABC"
    assert doc.net_name(0) == "GND" and doc.net_name(1) == "VIN"
    assert doc.net_name(2) is None and doc.net_name(0xFFFF) is None and doc.net_name(None) is None
    assert doc.issues == ()


def test_component_keys() -> None:
    text = (
        "|SELECTION=FALSE|LAYER=BOTTOM|LOCKED=FALSE|X=1000mil|Y=-0.5mil|PATTERN=R0603|NAMEON=TRUE"
        "|COMMENTON=FALSE|ROTATION= 2.70000000000000E+0002|SOURCEDESIGNATOR=R1|SOURCEUNIQUEID=\\ABCDEFGH"
        "|SOURCEHIERARCHICALPATH=|SOURCEFOOTPRINTLIBRARY=lib.PcbLib|SOURCECOMPONENTLIBRARY=lib.SchLib"
        "|SOURCELIBREFERENCE=RES|UNIQUEID=QWERTYUI"
    )
    doc = read_pcbdoc(document({"Components6": [block(text), block("|PATTERN=X")]}))
    first, bare = doc.components
    assert first.layer == "BOTTOM" and first.x == Fraction(10_000_000) and first.y == Fraction(-5000)
    assert first.rotation == 270.0 and first.pattern == "R0603"
    assert first.locked is False and first.name_on is True and first.comment_on is False
    assert first.source_designator == "R1" and first.source_unique_id == "\\ABCDEFGH"
    assert first.source_hierarchical_path == "" and first.source_footprint_library == "lib.PcbLib"
    assert first.source_component_library == "lib.SchLib" and first.source_lib_reference == "RES"
    assert first.unique_id == "QWERTYUI"
    assert bare.x is None and bare.locked is None and bare.source_designator is None
    assert doc.issues == ()


def test_class_members() -> None:
    doc = read_pcbdoc(document({"Classes6": [block("|NAME=PWR|KIND=0|SUPERCLASS=FALSE|M0=GND|M1=VIN")]}))
    (power,) = doc.classes
    assert power.name == "PWR" and power.kind == 0 and power.superclass is False
    assert power.members == ("GND", "VIN")


def test_class_bad_kind_is_a_value_issue() -> None:
    doc = read_pcbdoc(document({"Classes6": [block("|NAME=X|KIND=net")]}))
    assert doc.classes[0].kind is None
    assert [(i.code, i.where) for i in doc.issues] == [("altium.pcb-read.bad-value", "Classes6/Data#0")]


def test_polygon_name_in_character_codes() -> None:
    text = "|LAYER=MID1|NET=2|POURINDEX=0|NAME=71,78,68|POLYGONTYPE=Polygon|HATCHSTYLE=Solid"
    text += "|KIND0=0|VX0=0mil|VY0=0mil|KIND1=0|VX1=10mil|VY1=0mil"
    nets = [block(f"|NAME=N{i}") for i in range(3)]
    doc = read_pcbdoc(document({"Nets6": nets, "Polygons6": [block(text)]}))
    (polygon,) = doc.polygons
    assert polygon.name == "GND" and polygon.layer == "MID1"
    assert polygon.pour_index == 0 and polygon.net == 2
    assert polygon.polygon_type == "Polygon" and polygon.hatch_style == "Solid"
    assert len(polygon.vertices) == 2 and polygon.vertices[1].x == Fraction(100_000)
    assert doc.issues == ()


def test_polygon_name_decoding() -> None:
    assert decode_name("71,78,68") == "GND"
    assert decode_name("GND_L01_P000") == "GND_L01_P000"
    assert decode_name("") == ""
    assert decode_name("71,,68") == "71,,68"


def test_a_width_rule_for_a_class() -> None:
    text = (
        "|RULEKIND=Width|NAME=Width_1A|ENABLED=TRUE|PRIORITY=1|SCOPE1EXPRESSION=InNetClass('PWR')"
        "|SCOPE2EXPRESSION=All|MINLIMIT=10mil|FUTUREKEY=7"
    )
    data = rule(2, text)
    doc = read_pcbdoc(document({"Rules6": [data, rule(0, "|RULEKIND=Clearance|NAME=Clearance")]}))
    width, clearance = doc.rules
    assert width.kind_number == 2 and width.rule_kind == "Width" and width.priority == 1
    assert width.scope1 == "InNetClass('PWR')" and width.scope2 == "All"
    assert width.name == "Width_1A" and width.enabled is True and width.comment is None
    assert len(width.fields) == 8
    assert width.fields[0] == ("RULEKIND", "Width") and width.fields[-1] == ("FUTUREKEY", "7")
    assert width.raw == data
    assert clearance.kind_number == 0 and clearance.rule_kind == "Clearance"
    assert doc.rebuild("rules6") == data + rule(0, "|RULEKIND=Clearance|NAME=Clearance")
