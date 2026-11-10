# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawn Altium records retain authored geometry and are verified before any planned write."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import _drawn
import pytest
from _buildhelp import LIBS

from fenolite.api import run
from fenolite.backends.altium import drawn
from fenolite.backends.altium.read import sch


def copy_source(root: Path, name: str = "example") -> Path:
    shutil.copytree(_drawn.folder(name), root)
    row = '\t(lib (name "Mini") (type "KiCad") (uri "{}") (options "") (descr ""))\n'
    for table, head, uri in (
        ("fp-lib-table", "fp_lib_table", LIBS / "Mini_v9.pretty"),
        ("sym-lib-table", "sym_lib_table", LIBS / "Mini_v9.kicad_sym"),
    ):
        (root / table).write_text(
            f"({head}\n\t(version 7)\n{row.format(uri.as_posix())})\n", encoding="utf-8"
        )
    return root / "design.py"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    for key in ("KICAD9_SYMBOL_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD10_FOOTPRINT_DIR"):
        monkeypatch.delenv(key, raising=False)


def build(script: Path, tmp_path: Path, *args: str):
    return run(
        "build",
        str(script),
        "--out",
        "out",
        "--target",
        "altium",
        *args,
        cwd=tmp_path,
        timestamp="2026-11-01T00:00:00Z",
    )


@pytest.mark.parametrize("name", ["example", "flat", "full", "hier", "bus", "repeat"])
@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_drawn_example_written_and_read_back(form: str, name: str, tmp_path: Path) -> None:
    script = copy_source(tmp_path / "source", name)
    reply = build(script, tmp_path, "--altium-format", form, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    documents = [
        sch.read_schematic(path.read_bytes(), file=path.name) for path in (tmp_path / "out").glob("*.SchDoc")
    ]
    value = _drawn.drawn(name)
    assert len(documents) == len(value.walk()[0])
    assert sum(len(doc.of_type(sch.Wire)) for doc in documents) == sum(
        len(sheet.wires) for sheet in value.sheets
    )
    assert sum(len(doc.of_type(sch.Junction)) for doc in documents) == sum(
        len(sheet.junctions) for sheet in value.sheets
    )
    assert reply.result["schematic"]["source"] == "drawn"
    assert reply.envelope["evidence"]["level"] == "INFERRED"
    assert "H-A-DRAWN-WRITE" in reply.envelope["evidence"]["hypotheses"]


def test_off_grid_point_requires_explicit_loss(tmp_path: Path) -> None:
    script = copy_source(tmp_path / "source")
    source = script.parent / "schematic.toml"
    source.write_text(
        source.read_text(encoding="utf-8") + "\n[[sheet.wire]]\npts = [[0.0001, 0], [2.54, 0]]\n",
        encoding="utf-8",
    )
    refused = build(script, tmp_path, "--dry-run")
    assert refused.exit_code == 7 and refused.error["code"] == "FEN-7001"
    assert not (tmp_path / "out").exists()
    allowed = build(script, tmp_path, "--allow-lossy", "--confirm")
    assert allowed.exit_code == 0, (allowed.error, (allowed.envelope or {}).get("issues"))
    findings = [i for i in allowed.envelope["issues"] if i["code"] == "drawn.coordinate-rounded"]
    assert len(findings) == 1 and findings[0]["severity"] == "warning"
    assert "100" in findings[0]["message"]


def test_opaque_text_is_reported(tmp_path: Path) -> None:
    script = copy_source(tmp_path / "source")
    source = script.parent / "schematic.toml"
    source.write_text(
        source.read_text(encoding="utf-8") + "\n[[sheet.opaque]]\nkicad = '(text \"authored\")'\n",
        encoding="utf-8",
    )
    reply = build(script, tmp_path, "--dry-run")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    assert len([i for i in reply.envelope["issues"] if i["code"] == "drawn.opaque-dropped"]) == 1


@pytest.mark.parametrize(
    "native",
    ["|RECORD=4|BAD KEY=value", "|RECORD=1|LIBREFERENCE=authored", "|RECORD=4|RECORD=4"],
)
def test_opaque_native_fields_refuse_before_staging(tmp_path: Path, native: str) -> None:
    script = copy_source(tmp_path / "source")
    source = script.parent / "schematic.toml"
    source.write_text(
        source.read_text() + "\n[[sheet.opaque]]\nkicad = '(text \"authored\")'\n" + f"altium = '{native}'\n"
    )
    reply = build(script, tmp_path, "--dry-run")
    assert reply.exit_code == 3 and reply.error["code"] == "FEN-3004"
    assert "opaque" in reply.error.get("where", "") or "opaque" in reply.error["message"]
    assert not (tmp_path / "out").exists()


def test_opaque_native_graphic_is_kept(tmp_path: Path) -> None:
    script = copy_source(tmp_path / "source")
    source = script.parent / "schematic.toml"
    source.write_text(
        source.read_text()
        + "\n[[sheet.opaque]]\nkicad = '(text \"authored\")'\n"
        + "altium = '|RECORD=4|OWNERPARTID=-1|TEXT=AUTHORED_NATIVE_GRAPHIC|LOCATION.X=10|LOCATION.Y=10'\n"
    )
    reply = build(script, tmp_path, "--altium-format", "ascii", "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    assert any(
        b"AUTHORED_NATIVE_GRAPHIC" in path.read_bytes() for path in (tmp_path / "out").glob("*.SchDoc")
    )


def test_repeated_sheets_are_separate_native_instances(tmp_path: Path) -> None:
    script = copy_source(tmp_path / "source", "repeat")
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    documents = list((tmp_path / "out").glob("*.SchDoc"))
    assert len(documents) == 3
    assert len([i for i in reply.envelope["issues"] if i["code"] == "drawn.altium-repeat-flattened"]) == 1


def test_native_readback_catches_writer_defect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = copy_source(tmp_path / "source")
    lower = drawn.lower_drawn

    def broken(*args, **kwargs):
        result = lower(*args, **kwargs)
        first = result.sheets[0]
        records = list(first.plan.drawn_records)
        index = next(index for index, record in enumerate(records) if dict(record).get("RECORD") == "27")
        records[index] = tuple(
            (key, str(int(value) + 10) if key == "X1" else value) for key, value in records[index]
        )
        plan = dataclasses.replace(first.plan, drawn_records=tuple(records))
        return dataclasses.replace(result, sheets=(dataclasses.replace(first, plan=plan), *result.sheets[1:]))

    monkeypatch.setattr(drawn, "lower_drawn", broken)
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 5
    assert any(i["code"] == "build.schematic-netlist-differs" for i in reply.envelope["issues"])
    assert not (tmp_path / "out").exists()


def test_reviewed_drawing_input_is_bound(tmp_path: Path) -> None:
    script = copy_source(tmp_path / "source")
    preview = build(script, tmp_path, "--dry-run")
    assert preview.exit_code == 0, preview.error
    source = script.parent / "schematic.toml"
    source.write_text(source.read_text(encoding="utf-8") + "\n# changed after review\n", encoding="utf-8")
    replay = build(script, tmp_path, "--confirm", "--plan", preview.result["plan_id"])
    assert replay.exit_code == 4 and replay.error["code"] == "FEN-4002"
    assert not (tmp_path / "out").exists()


def unconnected_source(root: Path) -> Path:
    script = copy_source(root, "flat")
    script.write_text(
        script.read_text() + '\ndesign.add(Part("X9", "Mini:Mini_QFP32_IC", value="UNCONNECTED"))\n'
    )
    from fenolite.core.coords import Point
    from fenolite.lens.drawn import read_drawn, write_drawn
    from fenolite.model.drawn import DrawnSymbol

    path = root / "schematic.toml"
    value = read_drawn(path.read_text())
    sheet = value.sheets[0]
    sheet = dataclasses.replace(
        sheet, symbols=(*sheet.symbols, DrawnSymbol("X9", 1, Point(20_320_000, 20_320_000)))
    )
    path.write_text(write_drawn(dataclasses.replace(value, sheets=(sheet,))))
    return script


@pytest.mark.parametrize("defect", ["component", "pin", "duplicate"])
def test_unconnected_native_coverage_defects_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    from fenolite.backends.altium import schdoc

    script = unconnected_source(tmp_path / "source")
    control = build(script, tmp_path, "--dry-run")
    assert control.exit_code == 0, (control.error, (control.envelope or {}).get("issues"))
    producer = schdoc.component_records

    def broken(placed):
        records = producer(placed)
        if placed.spec.ref != "X9":
            return records
        if defect == "component":
            return ()
        if defect == "pin":
            removed = next(
                i
                for i, record in enumerate(records)
                if dict(record).get("RECORD") == "2" and dict(record).get("DESIGNATOR") == "1"
            )
            return tuple(
                tuple(
                    (key, str(int(value) - (int(value) > removed)) if key == "OWNERINDEX" else value)
                    for key, value in record
                )
                for i, record in enumerate(records)
                if i != removed
            )
        duplicate = tuple(
            tuple(
                (key, str(int(value) + len(records)) if key == "OWNERINDEX" else value)
                for key, value in record
            )
            for record in records
        )
        return (*records, *duplicate)

    monkeypatch.setattr(schdoc, "component_records", broken)
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 5, (reply.error, (reply.envelope or {}).get("issues"))
    assert any(i["code"] == "build.schematic-netlist-differs" for i in reply.envelope["issues"])
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("defect", ["missing", "unreadable"])
def test_native_document_defects_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str) -> None:
    from fenolite.backends.altium import project
    from fenolite.lens.drawn import write_drawn
    from fenolite.model.drawn import DrawnSchematic, DrawnSheet

    script = copy_source(tmp_path / "source", "flat")
    script.write_text(
        "# SPDX-License-Identifier: Apache-2.0\n# Copyright (c) 2026 Fenolite contributors\n"
        "from fenolite.dsl import Design, mm\n"
        'design = Design("blank")\ndesign.board(mm(40), mm(30))\n'
        'design.load_schematic("schematic.toml")\n'
    )
    (script.parent / "schematic.toml").write_text(write_drawn(DrawnSchematic("root", (DrawnSheet("root"),))))
    control = build(script, tmp_path, "--dry-run")
    assert control.exit_code == 0, (control.error, (control.envelope or {}).get("issues"))
    producer = project.write_project

    def broken(*args, **kwargs):
        files = producer(*args, **kwargs)
        document = next(name for name in files if name.endswith(".SchDoc"))
        if defect == "missing":
            del files[document]
        else:
            files[document] = b"AUTHORED_UNREADABLE_DOCUMENT"
        return files

    monkeypatch.setattr(project, "write_project", broken)
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 5, (reply.error, (reply.envelope or {}).get("issues"))
    assert any(i["code"] == "build.schematic-netlist-differs" for i in reply.envelope["issues"])
    assert not (tmp_path / "out").exists()


def test_logical_pins_and_physical_map_are_checked_separately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fenolite.backends.altium import schdoc

    script = copy_source(tmp_path / "source", "flat")
    text = script.read_text().replace('value="4k7")', 'value="4k7", pad_map={"1": "2", "2": "1"})')
    assert "pad_map=" in text
    script.write_text(text)
    control = build(script, tmp_path, "--dry-run")
    assert control.exit_code == 0, (control.error, (control.envelope or {}).get("issues"))
    producer = schdoc.component_records

    def broken(placed):
        records = producer(placed)
        if placed.spec.ref == "R1":
            return tuple(record for record in records if dict(record).get("RECORD") != "47")
        return records

    monkeypatch.setattr(schdoc, "component_records", broken)
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 5
    assert any(i["code"] == "build.schematic-netlist-differs" for i in reply.envelope["issues"])
    assert not (tmp_path / "out").exists()


def test_final_native_template_wire_fault_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import re

    from fenolite.backends.altium.binary import file_header_stream, storage_stream
    from fenolite.backends.altium.cfb import write_compound
    from fenolite.backends.altium.native_template import NativeTemplate
    from fenolite.backends.altium.read.cfb import open_compound
    from fenolite.backends.altium.read.sch.framing import deframe, enframe
    from fenolite.backends.altium.read.sch.props import parse

    script = copy_source(tmp_path / "source")
    template = tmp_path / "authored.SchDot"
    template.write_bytes(
        write_compound(
            (
                (
                    "FileHeader",
                    file_header_stream(
                        [
                            [
                                ("RECORD", "31"),
                                ("FONTIDCOUNT", "1"),
                                ("FONTNAME1", "Arial"),
                                ("SIZE1", "14"),
                                ("SHEETSTYLE", "1"),
                            ]
                        ]
                    ),
                ),
                ("Storage", storage_stream()),
            )
        )
    )
    control = build(script, tmp_path, "--altium-template", str(template), "--dry-run")
    assert control.exit_code == 0, (control.error, (control.envelope or {}).get("issues"))
    apply = NativeTemplate.apply
    faulted = []

    def broken(self, generated, *, parameters=()):
        candidate = apply(self, generated, parameters=parameters)
        compound = open_compound(candidate)
        streams = {name: compound.read(name) for name in compound.streams()}
        key = next(name for name in streams if name.casefold() == "fileheader")
        records = list(deframe(streams[key], where="authored fault"))
        for index, frame in enumerate(records):
            if frame.kind == 0 and parse(frame.payload.removesuffix(b"\0")).int("RECORD") == 27:
                changed, count = re.subn(
                    rb"(\|X1=)(-?\d+)", lambda m: m[1] + str(int(m[2]) + 10).encode(), frame.payload
                )
                assert count == 1
                records[index] = dataclasses.replace(frame, payload=changed)
                faulted.append(True)
                break
        else:
            return candidate
        streams[key] = enframe(records)
        return write_compound(tuple(streams.items()))

    monkeypatch.setattr(NativeTemplate, "apply", broken)
    reply = build(script, tmp_path, "--altium-template", str(template), "--confirm")
    assert faulted, "the authored control needs a native wire"
    assert reply.exit_code == 5, (reply.error, (reply.envelope or {}).get("issues"))
    assert any(i["code"] == "build.schematic-netlist-differs" for i in reply.envelope["issues"])
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("defect", ["", "incompatible", "missing", "edited_after_review"])
def test_per_unit_native_alias_body_and_library(tmp_path: Path, defect: str) -> None:
    from fenolite.backends.kicad.sym import write_symbol_library
    from fenolite.core.coords import Point
    from fenolite.core.ids import derived_id
    from fenolite.lens.drawn import write_drawn
    from fenolite.model.drawn import DrawnSchematic, DrawnSheet, DrawnSymbol
    from fenolite.model.library import SymbolDef, SymbolGraphic

    script = copy_source(tmp_path / "source", "flat")
    script.write_text(
        "# SPDX-License-Identifier: Apache-2.0\n# Copyright (c) 2026 Fenolite contributors\n"
        "from fenolite.dsl import Design, Part, mm\n"
        'design = Design("alias_units")\ndesign.board(mm(40), mm(30))\n'
        'design.add(Part("U2", "Mini:Mini_DualGate", value="DUAL"))\n'
        'design.load_schematic("schematic.toml")\n'
    )
    base = _drawn.library()["Mini:Mini_DualGate"]
    alias = SymbolDef(
        id=derived_id("sym", "authored", "native-unit-alias"),
        name="AliasDual",
        library="Authored",
        properties={"Reference": "U", "Value": "ALIAS"},
        units=base.units,
        pins=tuple(
            pin for pin in base.pins if not (defect == "incompatible" and pin.unit == 2 and pin.number == "5")
        ),
        graphics=(
            *base.graphics,
            SymbolGraphic("circle", (Point(0, 0), Point(1_270_000, 0)), unit=2, body_style=1),
        ),
    )
    alias_path = script.parent / "alias.kicad_sym"
    alias_path.write_text(write_symbol_library((alias,), target=9))
    table = script.parent / "sym-lib-table"
    text = table.read_text()
    table.write_text(
        text[: text.rfind(")")] + '(lib (name "Authored") (type "KiCad") '
        '(uri "${KIPRJMOD}/alias.kicad_sym") (options "") (descr ""))\n)\n'
    )
    alternate = "Authored:Missing" if defect == "missing" else "Authored:AliasDual"
    value = DrawnSchematic(
        "root",
        (
            DrawnSheet(
                "root",
                symbols=(
                    DrawnSymbol("U2", 1, Point(50_800_000, 50_800_000)),
                    DrawnSymbol("U2", 2, Point(101_600_000, 50_800_000), symbol=alternate),
                    DrawnSymbol("U2", 3, Point(50_800_000, 101_600_000)),
                ),
            ),
        ),
    )
    (script.parent / "schematic.toml").write_text(write_drawn(value))
    if defect == "edited_after_review":
        preview = build(script, tmp_path, "--dry-run")
        assert preview.exit_code == 0, preview.error
        alias_path.write_text(alias_path.read_text() + "\n; authored dependency edit\n")
        refused = build(script, tmp_path, "--confirm", "--plan", preview.result["plan_id"])
        assert refused.exit_code == 4 and refused.error["code"] == "FEN-4002"
        assert not (tmp_path / "out").exists()
        return
    reply = build(script, tmp_path, "--confirm")
    if defect:
        assert reply.exit_code in (3, 5), (reply.error, (reply.envelope or {}).get("issues"))
        assert not (tmp_path / "out").exists()
        return
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    native = sch.read_schematic(next((tmp_path / "out").glob("*.SchDoc")).read_bytes())
    assert {(part.current_part, part.lib_reference) for part in native.components()} == {
        (1, "Mini_DualGate"),
        (2, "AliasDual"),
        (3, "Mini_DualGate"),
    }
    from fenolite.backends.altium.read.schlib import read_schlib

    library = read_schlib((tmp_path / "out/alias_units.SchLib").read_bytes())
    assert "AliasDual" in {component.name for component in library.components}


@pytest.mark.parametrize("rotation,mirror", [(90, ""), (180, "x"), (270, "y")])
def test_component_pose_geometry_and_field_metadata(tmp_path: Path, rotation: int, mirror: str) -> None:
    from fenolite.core.coords import Point
    from fenolite.lens.drawn import read_drawn, write_drawn
    from fenolite.model.drawn import DrawnField

    script = unconnected_source(tmp_path / "source")
    path = script.parent / "schematic.toml"
    value = read_drawn(path.read_text())
    pose = DrawnField("Reference", Point(20_320_000, 30_480_000), 90_000_000, "right top mirror", True)
    symbols = tuple(
        dataclasses.replace(s, rotation=rotation * 1_000_000, mirror=mirror, fields=(pose,))
        if s.part == "X9"
        else s
        for s in value.sheets[0].symbols
    )
    path.write_text(
        write_drawn(
            dataclasses.replace(value, sheets=(dataclasses.replace(value.sheets[0], symbols=symbols),))
        )
    )
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    native = sch.read_schematic(next((tmp_path / "out").glob("*.SchDoc")).read_bytes())
    field = next(record for record in native.of_type(sch.Designator) if record.text == "X9")
    assert field.orientation == 1 and field.mirrored and field.hidden
    assert field.location[0].nm() == pose.at.x
    from fenolite.backends.altium.altsym import NM_PER_MIL
    from fenolite.backends.altium.layout import SHEET_SIZES
    from fenolite.backends.kicad.schlayout import pin_point

    component = next(
        c
        for c in native.components()
        if any(isinstance(r, sch.Designator) and r.text == "X9" for r in native.children_of(c))
    )
    pin = next(r for r in native.shown_children(component) if isinstance(r, sch.Pin) and r.designator == "1")
    original = next(p for p in _drawn.library()["Mini:Mini_QFP32_IC"].pins if p.number == "1")
    expected = pin_point(Point(20_320_000, 20_320_000), original.position, rotation, mirror)
    height = next(size.height for size in SHEET_SIZES if size.name == "A4") * NM_PER_MIL
    assert (pin.hot_end[0].nm(), height - pin.hot_end[1].nm()) == (expected.x, expected.y)
    # the justification is written (change c0470): right and top, which a quarter turn keeps, is 8
    assert field.props is not None and field.props.int("JUSTIFICATION") == 8
    assert not any(
        i["code"] == "altium.not-lowered" and "justification" in i["message"]
        for i in reply.envelope["issues"]
    )
    for rectangle in native.of_type(sch.Rectangle):
        assert rectangle.location[0] <= rectangle.corner[0] and rectangle.location[1] <= rectangle.corner[1]


def test_power_port_pose_limitations_are_explicit(tmp_path: Path) -> None:
    from fenolite.lens.drawn import read_drawn, write_drawn

    script = copy_source(tmp_path / "source", "flat")
    path = script.parent / "schematic.toml"
    value = read_drawn(path.read_text())
    root = value.sheets[0]
    root = dataclasses.replace(root, powers=tuple(dataclasses.replace(p, mirror="x") for p in root.powers))
    path.write_text(write_drawn(dataclasses.replace(value, sheets=(root,))))
    reply = build(script, tmp_path, "--dry-run")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    assert any(
        i["code"] == "altium.not-lowered" and "power port" in i["message"] for i in reply.envelope["issues"]
    )


def test_opaque_subtree_harness_and_compile_mask_build_directly(tmp_path: Path) -> None:
    """Change c0471: ``build --target altium`` writes imported opaque subtrees (``OWNERINDEX=@<line>``),
    harness records and compile-mask / note records (`209`, `225`), and passes the native readback guard."""
    script = copy_source(tmp_path / "source", "flat")
    source = script.parent / "schematic.toml"
    subtree = (
        "|RECORD=43|OWNERPARTID=-1|LOCATION.X=50|LOCATION.Y=50|NAME=Net Class\n"
        "|RECORD=41|OWNERINDEX=@0|OWNERPARTID=-1|NAME=ClassName|TEXT=HV_DC"
    )
    connector = (
        "|RECORD=215|OWNERPARTID=-1|LOCATION.X=80|LOCATION.Y=80|XSIZE=40|YSIZE=30\n"
        "|RECORD=216|OWNERINDEX=@0|OWNERPARTID=-1|NAME=TX|SIDE=0|DISTANCEFROMTOP=1\n"
        "|RECORD=217|OWNERINDEX=@0|OWNERPARTID=-1|TEXT=UART_H|LOCATION.X=80|LOCATION.Y=80"
    )
    mask = "|RECORD=225|OWNERPARTID=-1|LOCATION.X=10|LOCATION.Y=10|CORNER.X=20|CORNER.Y=20"
    source.write_text(
        source.read_text(encoding="utf-8")
        + f'\n[[sheet.opaque]]\nkicad = \'(text "directive")\'\naltium = """{subtree}"""\n'
        + f'\n[[sheet.opaque]]\nkicad = \'(text "harness")\'\naltium = """{connector}"""\n'
        + f"\n[[sheet.opaque]]\nkicad = '(text \"mask\")'\naltium = '{mask}'\n",
        encoding="utf-8",
    )
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    document = sch.read_schematic(next((tmp_path / "out").glob("*.SchDoc")).read_bytes())
    assert len(document.of_type(sch.WarningSign)) == 1
    assert len(document.of_type(sch.HarnessConnector)) == 1
    assert len(document.of_type(sch.UnknownRecord)) == 1


def test_carried_harness_records_write_to_the_additional_stream(tmp_path: Path) -> None:
    """Change c0474: harness records carried from a source Additional stream (215 to 218) return to the
    Additional stream of the written document, with their owners counted there; the FileHeader holds none,
    and the document re-reads without a warning, as Altium's compiler requires."""
    from fenolite.backends.altium.read.cfb import open_compound
    from fenolite.backends.altium.read.sch.framing import deframe
    from fenolite.backends.altium.read.sch.props import parse

    script = copy_source(tmp_path / "source", "flat")
    source = script.parent / "schematic.toml"
    # Independently authored harness records for the stream and owner regression.
    first = (
        "|RECORD=215|OWNERPARTID=-1|LOCATION.X=250|LOCATION.Y=350|XSIZE=70|YSIZE=30|LINEWIDTH=1|"
        "COLOR=13213327|AREACOLOR=16511725|PRIMARYCONNECTIONPOSITION=10|UNIQUEID=AAAAAAAA\n"
        "|RECORD=216|OWNERINDEXADDITIONALLIST=T|OWNERPARTID=-1|SIDE=1|DISTANCEFROMTOP=1|NAME=TEST_TX|"
        "UNIQUEID=BBBBBBBB|OWNERINDEX=@0\n"
        "|RECORD=217|OWNERINDEXADDITIONALLIST=T|OWNERPARTID=-1|LOCATION.X=250|LOCATION.Y=350|"
        "TEXT=TEST_LINK|FONTID=1|COLOR=8388608|UNIQUEID=CCCCCCCC|OWNERINDEX=@0"
    )
    second = (
        "|RECORD=215|OWNERPARTID=-1|LOCATION.X=250|LOCATION.Y=450|XSIZE=70|YSIZE=30|LINEWIDTH=1|"
        "COLOR=13213327|AREACOLOR=16511725|PRIMARYCONNECTIONPOSITION=10|UNIQUEID=EEEEEEEE\n"
        "|RECORD=216|OWNERINDEXADDITIONALLIST=T|OWNERPARTID=-1|SIDE=1|DISTANCEFROMTOP=1|NAME=TEST_RX|"
        "UNIQUEID=FFFFFFFF|OWNERINDEX=@0"
    )
    line = (
        "|RECORD=218|OWNERPARTID=-1|LINEWIDTH=2|COLOR=15187117|LOCATIONCOUNT=2|X1=210|Y1=340|X2=250|"
        "Y2=340|UNIQUEID=GGGGGGGG"
    )
    source.write_text(
        source.read_text(encoding="utf-8")
        + f'\n[[sheet.opaque]]\nkicad = \'(text "harness")\'\naltium = """{first}"""\n'
        + f'\n[[sheet.opaque]]\nkicad = \'(text "harness")\'\naltium = """{second}"""\n'
        + f'\n[[sheet.opaque]]\nkicad = \'(text "harness")\'\naltium = "{line}"\n',
        encoding="utf-8",
    )
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    data = next((tmp_path / "out").glob("*.SchDoc")).read_bytes()
    compound = open_compound(data)
    kinds = [
        parse(frame.payload.removesuffix(b"\0")).get("RECORD")
        for frame in deframe(compound.read("FileHeader"), where="out")
    ]
    assert not {"215", "216", "217", "218"} & set(kinds)
    additional = [
        parse(frame.payload.removesuffix(b"\0"))
        for frame in deframe(compound.read("Additional"), where="out")
    ]
    assert [props.get("RECORD") for props in additional[1:]] == ["215", "216", "217", "215", "216", "218"]
    # a child of the first connector omits its owner (the connector is the first Additional record), and a
    # child of the second names it by its Additional index, as a native document writes them
    assert additional[2].get("OWNERINDEX") is None and additional[5].get("OWNERINDEX") == "3"
    document = sch.read_schematic(data)
    assert not [i for i in document.issues if i.severity in {"warning", "error"}]


def test_carried_sheet_fields_style_the_document(tmp_path: Path) -> None:
    """Change c0473, task 1.1: the ``schematic.toml`` footer (``TOML_PREFIX`` lines) styles the written
    document: the carried sheet record, a label's justification and colour, a power port's colour and a
    component's body graphic replace the generated ones."""
    from fenolite.backends.kicad.sheet_carrier import TOML_PREFIX, AltiumSheet

    script = copy_source(tmp_path / "source", "flat")
    source = script.parent / "schematic.toml"
    fields = {
        "__sheet__": {"RECORDS": "|RECORD=31|AREACOLOR=123456|FONTIDCOUNT=1|SIZE1=8|FONTNAME1=Arial|"},
        "label_at:local:120650000,60960000": {"JUSTIFICATION": "2", "COLOR": "255"},
        "power_style:0": {"COLOR": "255"},
        "comp_gfx:0": {
            "POSE": "101600000,76200000,0,",
            "RECORDS": (
                "|RECORD=13|OWNERINDEX=@0|OWNERPARTID=-1|LOCATION.X=1000|LOCATION.Y=1000|"
                "CORNER.X=1100|CORNER.Y=1010"
            ),
        },
    }
    payload = AltiumSheet("", (), fields).text()
    source.write_text(
        source.read_text(encoding="utf-8") + f"\n{TOML_PREFIX}root {payload}\n", encoding="utf-8"
    )
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    document = sch.read_schematic(next((tmp_path / "out").glob("*.SchDoc")).read_bytes())
    sheet = document.sheet
    assert sheet is not None and sheet.props is not None
    assert sheet.props.text("AREACOLOR") == "123456"
    label = next(c for c in document.all_records() if isinstance(c, sch.NetLabel) and c.text == "SDA")
    assert label.props is not None
    assert label.props.text("JUSTIFICATION") == "2" and label.props.text("COLOR") == "255"
    power = next(c for c in document.all_records() if isinstance(c, sch.PowerPort))
    assert power.props is not None and power.props.text("COLOR") == "255"
    component = next(
        c
        for c in document.components()
        if any(isinstance(d, sch.Designator) and d.text == "U1" for d in document.children_of(c))
    )
    body = [c for c in document.children_of(component) if type(c) is sch.Line]
    assert len(body) == 1
    assert body[0].props is not None and body[0].props.text("LOCATION.X") == "1000"


@pytest.mark.parametrize("count", [1, 2, 3])
def test_carried_body_owners_shift_the_footprint_chain(tmp_path: Path, count: int) -> None:
    """Change c0475, task 1.2: a carried body that replaces the template's own body records with a
    different number of records keeps the footprint chain on the written indexes: the record 45 names
    the record 44 just before it and the records 46 and 48 name that 45, as Altium's compiler needs to
    link the footprint model."""
    from fenolite.backends.altium.read.cfb import open_compound
    from fenolite.backends.altium.read.sch.framing import deframe
    from fenolite.backends.altium.read.sch.props import parse
    from fenolite.backends.kicad.sheet_carrier import TOML_PREFIX, AltiumSheet

    script = copy_source(tmp_path / "source", "flat")
    script.write_text(
        script.read_text().replace('value="4k7")', 'value="4k7", pad_map={"1": "2", "2": "1"})')
    )
    source = script.parent / "schematic.toml"
    graphics = [
        "|RECORD=4|OWNERINDEX=@0|OWNERPARTID=-1|LOCATION.X=1000|LOCATION.Y=1020|COLOR=8388608|"
        "TEXT=carried|FONTID=1|ORIENTATION=0|ISNOTACCESIBLE=T",
        "|RECORD=13|OWNERINDEX=@0|OWNERPARTID=-1|LOCATION.X=1000|LOCATION.Y=1000|CORNER.X=1100|CORNER.Y=1010",
        "|RECORD=6|OWNERINDEX=@0|OWNERPARTID=-1|COLOR=8388608|LINEWIDTH=1|LOCATIONCOUNT=2|"
        "X1=1000|Y1=1030|X2=1100|Y2=1030",
    ]
    fields = {
        "comp_gfx:1": {
            "POSE": "127000000,63500000,0,",
            "RECORDS": "\n".join(graphics[:count]),
        },
    }

    payload = AltiumSheet("", (), fields).text()
    source.write_text(
        source.read_text(encoding="utf-8") + f"\n{TOML_PREFIX}root {payload}\n", encoding="utf-8"
    )
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    data = next((tmp_path / "out").glob("*.SchDoc")).read_bytes()
    # the owner indexes count the records after the header (S-0130): the first frame is the header
    frames = deframe(open_compound(data).read("FileHeader"), where="out")[1:]
    records = [
        {k: props.get(k) for k in props.keys()}
        for props in (parse(frame.payload.removesuffix(b"\0")) for frame in frames)
    ]
    component = next(
        i
        for i, props in enumerate(records)
        if props.get("RECORD") == "1" and props.get("LIBREFERENCE") == "Mini_R"
    )
    block = [props for props in records if props.get("OWNERINDEX") == str(component)]
    # the carried body replaced the template's own one body record: the label of the carrier is there
    assert any(p.get("RECORD") == "4" and p.get("TEXT") == "carried" for p in block)
    assert not any(p.get("RECORD") == "14" for p in block)
    # the footprint chain names the records as written: 45 the 44 just before it, 46 and 48 that 45
    listing = next(
        i
        for i, props in enumerate(records)
        if props.get("RECORD") == "44" and props.get("OWNERINDEX") == str(component)
    )
    model = next(
        i
        for i, props in enumerate(records)
        if props.get("RECORD") == "45" and props.get("OWNERINDEX") == str(listing)
    )
    assert model == listing + 1
    for kind in ("46", "48"):
        assert any(props.get("RECORD") == kind and props.get("OWNERINDEX") == str(model) for props in records)
    maps = next(
        i
        for i, props in enumerate(records)
        if props.get("RECORD") == "46" and props.get("OWNERINDEX") == str(model)
    )
    assert any(props.get("RECORD") == "47" and props.get("OWNERINDEX") == str(maps) for props in records)
    document = sch.read_schematic(data)
    assert not [i for i in document.issues if i.severity in {"warning", "error"}]


def test_component_template_with_unwritten_owner_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fenolite.backends.altium import schdoc

    script = copy_source(tmp_path / "source", "flat")
    producer = schdoc.component_records

    def broken(placed):
        records = producer(placed)
        if placed.spec.ref == "R1":
            for record in records:
                if dict(record).get("RECORD") == "45":
                    record[:] = [(key, "99999" if key == "OWNERINDEX" else value) for key, value in record]
        return records

    monkeypatch.setattr(schdoc, "component_records", broken)
    reply = build(script, tmp_path, "--confirm")
    assert reply.exit_code == 3
    assert reply.error["code"] == "FEN-3004"
    assert not (tmp_path / "out").exists()
