# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Faithful schematic conversion (change c0470; capability design-conversion)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _drawings import BLINK, HIER, altium_drawing, altium_sheets, hier_board, kicad_drawing, level_s, paths_of

from fenolite.convert.altium_to_kicad import Ledger, schematic_files
from fenolite.convert.report import KINDS as REPORT_KINDS
from fenolite.convert.sources import read_source

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs" / "evidence" / "conversion.md"
KINDS = ("item-missing", "symbol-field", "symbol-missing", "symbol-pose")


def _baseline_table() -> dict[str, tuple[int, ...]]:
    text = DOC.read_text(encoding="utf-8")
    start = text.index("### Generated schematic before c0470")
    rows: dict[str, tuple[int, ...]] = {}
    for line in text[start:].splitlines()[1:]:
        if rows and not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if line.startswith("|") and cells[1].isdecimal():
            rows[cells[0]] = tuple(int(cell) for cell in cells[1:])
    return rows


@pytest.mark.parametrize("name", ["blink", "hier", "altium_hier_board"])
def test_baseline_of_the_generated_schematic(name: str, tmp_path: Path) -> None:
    """Task 1.2: the loss of the generated path, as the table of ``docs/evidence/conversion.md`` records."""
    project = {"blink": BLINK, "hier": HIER}.get(name) or hier_board(tmp_path)
    read = read_source(project)
    ledger = Ledger()
    texts, _ = schematic_files(read, read.design, project.stem, 10, ledger)
    files = {key: text.encode() for key, text in texts.items()}
    written = kicad_drawing(files, paths_of(read.design.circuit))
    found = level_s(altium_drawing(project), written).differences
    kinds = Counter(difference.kind for difference in found)
    assert (len(found), *(kinds[kind] for kind in KINDS)) == _baseline_table()[name]
    assert set(kinds) <= set(KINDS)
    assert {kind: list(reasons) for kind, reasons in ledger.changed.items()} == {
        "schematic": ["positions and wires are regenerated from the circuit"]
    }


# --- 4.1 the conversion writes the source drawing ---


def _converted(project: Path) -> tuple[object, object]:
    from fenolite.convert import convert_project
    from fenolite.convert import schematic as drawing_lib

    conversion = convert_project(project, to="kicad", allow_lossy=True)
    source = drawing_lib.drawing_of(read_source(project))
    assert source is not None
    return conversion, source


@pytest.mark.parametrize("name", ["blink", "altium_hier_board"])
def test_writes_the_source_drawing(name: str, tmp_path: Path) -> None:
    """Task 4.1: ``convert`` writes the drawing of the Altium sheets; read back, level S finds no difference
    with the source drawing, and the report has a row per drawn kind."""
    from fenolite.checks.equivalence.drawn import compare_drawn
    from fenolite.convert import schematic as drawing_lib

    project = BLINK if name == "blink" else hier_board(tmp_path)
    conversion, source = _converted(project)
    back, pins, issues = drawing_lib.read_kicad_drawing(
        conversion.files,  # type: ignore[attr-defined]
        paths_of(conversion.design.circuit),  # type: ignore[attr-defined]
    )
    assert [i for i in issues if i.severity == "error"] == []
    found = compare_drawn(source.extracted.drawn, back, pins_a=source.extracted.pins, pins_b=pins)  # type: ignore[attr-defined]
    assert found.differences == ()
    report = conversion.report  # type: ignore[attr-defined]
    row = report.row("schematic")
    assert (row.changed, row.lost) == (0, 0)
    assert report.row("schematic-symbol").written == report.row("schematic-symbol").source > 0


def test_board_alone_keeps_the_generated_schematic() -> None:
    """Task 4.1: a PCB document alone has no sheets: ``schgen`` still draws its schematic."""
    from fenolite.convert import convert_project

    conversion = convert_project(BLINK.with_suffix(".PcbDoc"), to="kicad", allow_lossy=True)
    row = conversion.report.row("schematic")
    assert row is not None and row.changed == 1
    assert row.reasons[0].reason == "positions and wires are regenerated from the circuit"
    assert conversion.report.row("schematic-symbol") is None


# --- 4.2 the carrier of an Altium sheet in KiCad ---


def test_altium_carrier_in_comment_9() -> None:
    """Task 4.2: each written sheet holds ``Fenolite.Altium.Sheet`` in its title block's comment 9, with the
    sheet record, the opaque records and the Altium fields; the carrier restores the opaque records."""
    from fenolite.backends.kicad import sheet_carrier

    conversion, source = _converted(BLINK)
    text = conversion.files["blink.kicad_sch"].decode("utf-8")  # type: ignore[attr-defined]
    carried = sheet_carrier.take(text)
    assert carried is not None
    carrier = sheet_carrier.AltiumSheet.parse(carried)
    assert carrier.text() == carried
    assert carrier.sheet.startswith("|RECORD=31|")
    assert [t.split("|")[1] for _, t in carrier.opaques] == ["RECORD=43", "RECORD=43"]
    assert carrier.fields["power:0"] == {"SHOWNETNAME": "T", "STYLE": "4"}
    assert '(comment 9 "{' in text and text.count("(comment 9") == 1
    assert sheet_carrier.take(sheet_carrier.put(text, carried)) == carried  # put replaces, never adds


def test_altium_carrier_put_adds_a_title_block() -> None:
    from fenolite.backends.kicad import sheet_carrier

    text = (
        '(kicad_sch\n\t(version 20250114)\n\t(paper "A4")\n'
        '\t(uuid "00000000-0000-0000-0000-000000000001")\n)\n'
    )
    put = sheet_carrier.put(text, '{"schema":"x"}')
    assert sheet_carrier.take(put) == '{"schema":"x"}'
    assert put.index("(paper") < put.index("(title_block") < put.index("(uuid")
    with pytest.raises(ValueError, match="carrier"):
        sheet_carrier.AltiumSheet.parse('{"schema":"x"}')


# --- 4.3 the carrier of a KiCad sheet in Altium ---


def _nested_to_altium(folder: Path):  # type: ignore[no-untyped-def]
    """The authored nested KiCad project converted to Altium, with its source drawing and the read-back."""
    from _schbuild import built_nested, write_files

    from fenolite.backends.altium import drawn_read
    from fenolite.backends.kicad import drawn as kicad_drawn
    from fenolite.backends.kicad import parity_inputs
    from fenolite.convert import convert_project
    from fenolite.convert import schematic as drawing_lib

    write_files(built_nested(), folder / "kicad")
    pro = folder / "kicad" / "nested.kicad_pro"
    conversion = convert_project(pro, to="altium", allow_lossy=True)
    for name, data in conversion.files.items():
        (folder / "altium" / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / "altium" / name).write_bytes(data)
    read = read_source(pro)
    design, _, _ = drawing_lib.inputs(read, read.design)
    assert design is not None
    sheets = parity_inputs.read_sheets(pro.with_suffix(".kicad_sch"))
    first = next(iter(sheets))
    children = {key: value for key, value in sheets.items() if key != first}
    paths = kicad_drawn.refs_to_paths(design.circuit)
    source = kicad_drawn.extract_with_pins(sheets[first], children, components=paths, root_file=first)
    back = drawn_read.extract_with_pins(altium_sheets(folder / "altium" / "nested.PrjPcb"))
    return conversion, source, back


def test_kicad_carrier_round_trip(tmp_path: Path) -> None:
    """Task 4.3: KiCad sheets written to Altium keep in ``Fenolite.KiCad.Sheet`` what no Altium record holds
    (the kind of a global label written as a power port, the power flags); read back, level S finds no
    difference with the source drawing."""
    from fenolite.backends.altium import drawn_carrier
    from fenolite.backends.altium.read import sch
    from fenolite.checks.equivalence.drawn import compare_drawn

    conversion, source, back = _nested_to_altium(tmp_path)
    assert [i.message for i in back.issues if i.severity == "error"] == []
    found = compare_drawn(source.drawn, back.drawn, pins_a=source.pins, pins_b=back.pins)
    assert found.differences == ()
    root = sch.read_schematic(conversion.files["nested.SchDoc"], file="nested.SchDoc")
    params = [
        r for r in root.all_records() if type(r).__name__ == "Parameter" and r.name == drawn_carrier.NAME
    ]
    assert len(params) == 1 and params[0].owner is None
    carrier = drawn_carrier.KiCadSheet.parse(params[0].text)
    assert [flag["symbol"] for flag in carrier.powers] == ["fenolite:PWR_FLAG", "fenolite:PWR_FLAG"]
    assert {next(iter(entry)) for entry in carrier.stand_ins.values()} == {"label"}
    assert drawn_carrier.KiCadSheet.parse(carrier.value()) == carrier


def test_kicad_carrier_refuses_another_schema() -> None:
    import base64

    from fenolite.backends.altium import drawn_carrier

    with pytest.raises(ValueError, match="carrier"):
        drawn_carrier.KiCadSheet.parse(base64.b64encode(b'{"schema":"x"}').decode())
    with pytest.raises(ValueError, match="carrier"):
        drawn_carrier.KiCadSheet.parse("not base64!")


# --- 5.1 report rows per kind ---


def test_report_rows_of_both_directions(tmp_path: Path) -> None:
    """Task 5.1: a conversion that writes a drawing reports each drawn kind with ``source`` and ``written``;
    each changed item has a reason of ``convert.codes.DRAWING_REASONS`` or of ``drawn_symbols.CHANGED``."""
    from fenolite.backends.altium.drawn_symbols import CHANGED
    from fenolite.convert import codes

    to_kicad, _ = _converted(BLINK)
    to_altium, _, _ = _nested_to_altium(tmp_path)
    for conversion, expected in (
        (to_kicad, {"sheet": 1, "schematic-symbol": 3, "wire": 7, "label": 4, "power": 3, "directive": 2}),
        (to_altium, {"sheet": 4, "schematic-symbol": 4, "label": 12, "power": 2, "sheet-symbol": 3}),
    ):
        report = conversion.report  # type: ignore[attr-defined]
        for kind, count in expected.items():
            row = report.row(kind)
            assert row is not None and (row.source, row.written + row.changed, row.lost) == (
                count,
                count,
                0,
            ), kind
        for row in report.rows:
            if row.kind in KINDS_OF_DRAWING:
                assert {r.reason for r in row.reasons} <= {*codes.DRAWING_REASONS, *CHANGED}, row.kind
        assert report.row("schematic").changed == 0  # the drawing, not a generated schematic


KINDS_OF_DRAWING = frozenset(row.name for row in REPORT_KINDS if row.group == "schematic") - {"schematic"}


# --- 5.3 verification of the written drawing ---


def _moving_writer(monkeypatch: pytest.MonkeyPatch, part: str, dx: int) -> None:
    """A test writer that moves the symbols of ``part`` by ``dx`` nm and reports nothing."""
    import dataclasses

    from fenolite.convert import schematic as drawing_lib

    write = drawing_lib.write_kicad_drawing

    def moved(drawing, design, name, target, links=None):  # type: ignore[no-untyped-def]
        found = drawing.extracted
        sheets = tuple(
            dataclasses.replace(
                sheet,
                symbols=tuple(
                    dataclasses.replace(s, at=type(s.at)(s.at.x + dx, s.at.y)) if s.part == part else s
                    for s in sheet.symbols
                ),
            )
            for sheet in found.drawn.sheets
        )
        shifted = dataclasses.replace(found, drawn=dataclasses.replace(found.drawn, sheets=sheets))
        return write(dataclasses.replace(drawing, extracted=shifted), design, name, target, links)

    monkeypatch.setattr(drawing_lib, "write_kicad_drawing", moved)


def test_unexplained_moved_symbol(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Task 5.3, scenario "An unexplained moved symbol": ``convert`` gives ``convert.unexplained`` naming the
    symbol's component path and unit, and exits 5."""
    from fenolite.api import convert, run

    path = next(c.path or c.ref for c in read_source(BLINK).design.circuit.components if c.ref == "R1")
    _moving_writer(monkeypatch, path, 1_000_000)
    result = convert(BLINK, to="kicad", allow_lossy=True)
    poses = [
        (d.kind, d.where, d.field) for d in result.unexplained if d.level == "S" and d.kind != "drawn-net"
    ]
    assert poses == [("symbol-pose", f"/:{path}:1", "at")]
    assert f"/:{path}:1" in [i.where for i in result.issues if i.code == "convert.unexplained"]
    argv = (
        "convert",
        str(BLINK),
        "--to",
        "kicad",
        "--out",
        str(tmp_path / "out"),
        "--allow-lossy",
        "--dry-run",
    )
    reply = run(*argv)
    assert reply.exit_code == 5


def test_unexplained_none_without_change() -> None:
    """Task 5.3: the written drawing of ``blink`` reads back as the source drawing; nothing is unexplained."""
    from fenolite.api import convert
    from fenolite.backends.kicad.cli import find_kicad_cli

    result = convert(BLINK, to="kicad", allow_lossy=True)
    assert result.unexplained == ()
    # a drawn sheet is outside Fenolite's own netlist grammar: its netlist read-back needs kicad-cli, and
    # without one the conversion says so instead of comparing. The level S drawing comparison still runs.
    unverified = [i for i in result.issues if i.code == "convert.schematic-unverified"]
    if find_kicad_cli() is None:
        assert unverified
    else:
        assert not unverified


def test_schematic_net_takes_the_board_spelling_of_a_slash(tmp_path: Path) -> None:
    """KiCad stores the ``/`` of a pin name in a net name as ``{slash}``; the board reader gives the net
    the slash, so the schematic net does too, and the Altium documents name one net (royalblue54L)."""
    from dataclasses import replace

    from _schbuild import built_nested, write_files

    from fenolite.api.sides import read_schematic
    from fenolite.convert import schematic as drawing_lib

    write_files(built_nested(), tmp_path)
    read = read_source(tmp_path / "nested.kicad_pro")
    schematic = read_schematic(drawing_lib.root_schematic(read)).design
    net = schematic.circuit.nets[0]
    stored = replace(net, name="Net-(U1-P1.00{slash}XL1)")
    nets = (stored, *schematic.circuit.nets[1:])
    schematic = replace(schematic, circuit=replace(schematic.circuit, nets=nets))
    design, _, _ = drawing_lib.inputs(replace(read, schematic=schematic), read.design)
    assert design is not None
    names = {n.name for n in design.circuit.nets}
    assert "Net-(U1-P1.00/XL1)" in names and not any("{slash}" in name for name in names)
