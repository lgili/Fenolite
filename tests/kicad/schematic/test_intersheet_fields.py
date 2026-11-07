# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual project-driven field expansion, including repeated instances (c0348)."""

from __future__ import annotations

import hashlib

import _intersheet
import pytest
from _probes import major, runner

pytestmark = pytest.mark.needs_kicad
CASES = (
    ("off", ("2",), {"intersheets_ref_show": False}, False, (), ()),
    ("on", ("2",), {"intersheets_ref_show": True}, False, ("2",), ("1",)),
    ("stored-hide", ("2",), {"intersheets_ref_show": True}, True, ("2",), ("1",)),
    ("no-project-visible", ("2",), None, False, (), ()),
    ("no-project-hidden", ("2",), None, True, (), ()),
    (
        "own",
        ("2",),
        {"intersheets_ref_show": True, "intersheets_ref_own_page": True},
        False,
        ("1,2",),
        ("1,2",),
    ),
    (
        "affix",
        ("2",),
        {"intersheets_ref_show": True, "intersheets_ref_prefix": "[P", "intersheets_ref_suffix": "]"},
        False,
        ("[P2]",),
        ("[P1]",),
    ),
    ("repeat-full", ("2", "3", "4"), {"intersheets_ref_show": True}, False, ("2,3,4",), ("1,3,4",)),
    (
        "repeat-short",
        ("2", "3", "4"),
        {"intersheets_ref_show": True, "intersheets_ref_short": True},
        False,
        ("2..4",),
        ("1..4",),
    ),
    ("numeric-order", ("3", "12", "4"), {"intersheets_ref_show": True}, False, ("3,4,12",), ("1,4,12",)),
    ("text-order", ("B", "A2", "A1"), {"intersheets_ref_show": True}, False, ("A1,A2,B",), ("1,A1,A2",)),
    ("leading-zero", ("2", "02", "10"), {"intersheets_ref_show": True}, False, ("2,02,10",), ("1,02,10",)),
    (
        "natural-text",
        ("A10", "A2", "A1"),
        {"intersheets_ref_show": True},
        False,
        ("A1,A2,A10",),
        ("1,A1,A2",),
    ),
    (
        "numeric-tie-reverse",
        ("02", "2", "10"),
        {"intersheets_ref_show": True},
        False,
        ("02,2,10",),
        ("1,2,10",),
    ),
    ("mixed-case", ("a10", "A2", "B"), {"intersheets_ref_show": True}, False, ("A2,B,a10",), ("1,A2,B",)),
    (
        "punctuation",
        ("2.1", "2.10", "2.2"),
        {"intersheets_ref_show": True},
        False,
        ("2.1,2.2,2.10",),
        ("1,2.2,2.10",),
    ),
)


@pytest.mark.parametrize(
    "case,pages,settings,hidden,root_expected,child_expected", CASES, ids=[case[0] for case in CASES]
)
def test_native_effective_reference_matrix(
    case, pages, settings, hidden, root_expected, child_expected, tmp_path, record_property
) -> None:
    payload = _intersheet.files(major(), pages, settings=settings, hidden=hidden)
    before = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    for name, data in payload.items():
        (tmp_path / name).write_bytes(data)
    cli = runner()
    result = cli.run(["sch", "export", "svg", "-o", "svg", "tiny.kicad_sch"], files=payload, folders=("svg",))
    assert result.ok, result.stderr
    outputs = {name: data for name, data in result.outputs.items() if name.endswith(".svg")}
    assert len(outputs) == len(pages) + 1
    assert _intersheet.field_text(outputs["svg/tiny.svg"]) == root_expected
    assert _intersheet.field_text(outputs[f"svg/tiny-PAGE{pages[0]}.svg"]) == child_expected
    assert before == {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() for name in payload}
    record_property("native_version", cli.version())
    record_property("input_sha256", str(before))


def test_same_page_duplicate_labels_do_not_duplicate_reference_pages() -> None:
    cli = runner()
    payload = _intersheet.files(major(), settings={"intersheets_ref_show": True}, same_page_labels=True)
    result = cli.run(["sch", "export", "svg", "-o", "svg", "tiny.kicad_sch"], files=payload, folders=("svg",))
    assert result.ok, result.stderr
    assert _intersheet.field_text(result.outputs["svg/tiny.svg"]) == ("2",)
    assert _intersheet.field_text(result.outputs["svg/tiny-PAGE2.svg"]) == ("1",)


def test_typed_reference_pose_preserves_the_complete_native_graph() -> None:
    import dataclasses
    import xml.etree.ElementTree as ET

    import _drawn
    import _erc

    from fenolite.core.coords import Point, Size
    from fenolite.model.drawn import DrawnField, DrawnFont

    cli = runner()
    original = _drawn.build("full", major())
    drawing = _drawn.drawn("full")
    root = drawing.sheets[0]
    changed = dataclasses.replace(
        root,
        labels=tuple(
            dataclasses.replace(
                label,
                intersheet_refs=DrawnField(
                    "Intersheetrefs",
                    Point(15_000_000, 22_000_000),
                    90_000_000,
                    "right",
                    True,
                    DrawnFont(Size(500_000, 600_000), bold=True),
                ),
            )
            if label.kind == "global"
            else label
            for label in root.labels
        ),
    )
    output = _drawn.build(
        "full", major(), value=dataclasses.replace(drawing, sheets=(changed, *drawing.sheets[1:]))
    )
    name = _drawn.root_name(output)
    before = _erc.netlist(cli, name, original.files)
    after = _erc.netlist(cli, name, output.files)
    assert before == after
    assert len({pin for group in before.values() for pin in group}) > 0
    project = name.replace(".kicad_sch", ".kicad_pro")
    payload = {
        **output.files,
        project: b'{"schematic":{"drawing":{"intersheets_ref_show":true,'
        b'"intersheets_ref_prefix":"NATIVE_FIELD[","intersheets_ref_suffix":"]"}}}',
    }
    result = cli.run(["sch", "export", "svg", "-o", "svg", name], files=payload, folders=("svg",))
    assert result.ok, result.stderr
    texts = [
        node
        for filename, data in result.outputs.items()
        if filename.endswith(".svg")
        for node in ET.fromstring(data).iter()
        if node.tag.endswith("}text")
    ]
    rendered = [node for node in texts if "".join(node.itertext()).startswith("NATIVE_FIELD[")]
    assert rendered and all("${INTERSHEET_REFS}" not in "".join(node.itertext()) for node in rendered)
    from decimal import Decimal

    moved = dataclasses.replace(
        changed,
        labels=tuple(
            dataclasses.replace(
                label,
                intersheet_refs=dataclasses.replace(label.intersheet_refs, at=Point(20_000_000, 29_000_000)),
            )
            if label.intersheet_refs is not None
            else label
            for label in changed.labels
        ),
    )
    moved_output = _drawn.build(
        "full", major(), value=dataclasses.replace(drawing, sheets=(moved, *drawing.sheets[1:]))
    )
    moved_payload = {**moved_output.files, project: payload[project]}
    shifted = cli.run(["sch", "export", "svg", "-o", "svg", name], files=moved_payload, folders=("svg",))
    assert shifted.ok, shifted.stderr
    moved_texts = [
        node
        for filename, data in shifted.outputs.items()
        if filename.endswith(".svg")
        for node in ET.fromstring(data).iter()
        if node.tag.endswith("}text") and "".join(node.itertext()).startswith("NATIVE_FIELD[")
    ]
    assert len(moved_texts) == len(rendered)
    root_svg = "svg/" + name.removesuffix(".kicad_sch") + ".svg"
    fields = _intersheet.field_poses(result.outputs, "NATIVE_FIELD[")
    assert fields and {key[0] for key in fields} == {root_svg}
    expected = _intersheet.shift_field_poses(fields, {root_svg: (Decimal(5), Decimal(7))})
    assert _intersheet.field_poses(shifted.outputs, "NATIVE_FIELD[") == expected
    assert _erc.netlist(cli, name, moved_output.files) == before


def test_path_presentation_matches_all_native_repeated_reference_texts(tmp_path, record_property) -> None:
    import xml.etree.ElementTree as ET
    from collections import Counter

    from fenolite.cli._presentation import sheet_scenes

    payload = _intersheet.files(
        major(),
        ("2", "3", "4"),
        hidden=True,
        settings={
            "intersheets_ref_show": True,
            "intersheets_ref_short": True,
            "intersheets_ref_prefix": "ORACLE[",
            "intersheets_ref_suffix": "]",
        },
    )
    before = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    for name, data in payload.items():
        (tmp_path / name).write_bytes(data)
    cli = runner()
    exported = cli.run(
        ["sch", "export", "svg", "-o", "svg", "tiny.kicad_sch"], files=payload, folders=("svg",)
    )
    assert exported.ok, exported.stderr
    native = Counter(
        "".join(node.itertext())
        for name, data in exported.outputs.items()
        if name.endswith(".svg")
        for node in ET.fromstring(data).iter()
        if node.tag.endswith("}text") and "".join(node.itertext()).startswith("ORACLE[")
    )
    scenes = sheet_scenes(tmp_path, project=tmp_path / "tiny.kicad_pro")
    actual = Counter(
        primitive["s"]
        for scene in scenes.values()
        for primitive in scene["prims"]
        if primitive.get("role") == "intersheet_refs"
    )
    assert actual == native and sum(actual.values()) == 8
    assert (
        len(scenes) == 4 and len({tuple(scene["meta"]["instance"]["path"]) for scene in scenes.values()}) == 4
    )
    assert before == {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() for name in payload}
    record_property("native_version", cli.version())
    record_property("input_sha256", str(before))
    record_property("native_all_reference_texts", str(native))
