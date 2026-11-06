# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule records of an Altium document through KiCad and back (change c0434; capability
design-conversion, "Rule records through KiCad"; altium-pcb-writer, "Source rule records written back").

The source is written by Fenolite from the committed ``tests/data/kicad/board/two_layer.kicad_pcb`` with five
authored rule records: a Width of its own name and priority, an enabled and a disabled Clearance, and a
Height and a Minimum Solder Mask Sliver that KiCad has no rule for. Authored values only."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path

import pytest

from fenolite.api import convert
from fenolite.backends.altium import lower
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad import boardcarrier, fpitems
from fenolite.convert import LossyConversionError, pads, rulecarrier
from fenolite.convert.report import SOURCE_RULE_LOST, ConversionReport
from fenolite.convert.sources import read_source

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
Record = tuple[int, tuple[tuple[str, str], ...]]


def _head(
    kind: str, name: str, priority: int, scope: str = "All", enabled: str = "TRUE"
) -> list[tuple[str, str]]:
    return [
        ("RULEKIND", kind), ("NETSCOPE", "DifferentNets" if kind == "Clearance" else "AnyNet"),
        ("LAYERKIND", "SameLayer"), ("SCOPE1EXPRESSION", scope), ("SCOPE2EXPRESSION", "All"), ("NAME", name),
        ("ENABLED", enabled), ("PRIORITY", str(priority)), ("COMMENT", "authored"),
        ("UNIQUEID", f"AUTH{priority}{kind[:4].upper()}"), ("DEFINEDBYLOGICALDOCUMENT", "FALSE"),
    ]  # fmt: skip


def _gap(value: str) -> list[tuple[str, str]]:
    return [("GAP", value), ("GENERICCLEARANCE", value), ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
            ("OBJECTCLEARANCES", "")]  # fmt: skip


AUTHORED: tuple[Record, ...] = (
    (2, (*_head("Width", "Signal Width", 3), ("MAXLIMIT", "40mil"), ("MINLIMIT", "4mil"),
         ("PREFEREDWIDTH", "6mil"))),
    (0, (*_head("Clearance", "Board Gap", 1), *_gap("6mil"))),
    (0, (*_head("Clearance", "Ground Gap", 2, "InNet('GND')", "FALSE"), *_gap("8mil"))),
    (50, (*_head("Height", "Tall Parts", 1), ("MINHEIGHT", "0mil"), ("MAXHEIGHT", "1000mil"),
          ("PREFHEIGHT", "500mil"))),
    (53, (*_head("MinimumSolderMaskSliver", "Mask Web", 1), ("MINSOLDERMASKWIDTH", "4mil"))),
)  # fmt: skip


def _write(files: Mapping[str, bytes], folder: Path) -> None:
    for name, data in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def _records(path: Path) -> list[Record]:
    found: list[Record] = []
    for rule in read_pcbdoc(path.read_bytes()).rules:
        fields = tuple((key, value or "") for key, value in rule.record.fields)
        start = [key for key, _value in fields].index("RULEKIND")
        found.append((rule.kind_number, fields[start:]))
    return found


def _source(tmp_path: Path) -> Path:
    design = read_source(BOARD).design
    design = pads.project(fpitems.with_graphic_nets(fpitems.with_footprint_items(design).design))
    written = lower.write_design(
        dataclasses.replace(design, rules=None), allow_lossy=True, source_rules=AUTHORED, full_drill=True
    )
    _write(written.files, tmp_path / "source")
    (source,) = (tmp_path / "source").glob("*.PcbDoc")
    return source


def _to_kicad(tmp_path: Path) -> tuple[Path, list[Record]]:
    source = _source(tmp_path)
    _write(convert(source, to="kicad", allow_lossy=True).conversion.files, tmp_path / "kicad")
    (board,) = (tmp_path / "kicad").glob("*.kicad_pcb")
    return board, _records(source)


def _back(board: Path, tmp_path: Path, allow_lossy: bool = True) -> tuple[list[Record], ConversionReport]:
    result = convert(board, to="altium", allow_lossy=allow_lossy).conversion
    _write(result.files, tmp_path / "back")
    (document,) = (tmp_path / "back").glob("*.PcbDoc")
    return _records(document), result.report


def _edit(board: Path, old: str, new: str) -> None:
    rules = board.with_suffix(".kicad_dru")
    text = rules.read_text(encoding="utf-8")
    assert old in text, text
    rules.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_the_source_holds_the_authored_records(tmp_path: Path) -> None:
    """The authored records first; the pour adds the Polygon Connect Style records of its polygons."""
    found = _records(_source(tmp_path))
    assert found[: len(AUTHORED)] == list(AUTHORED)
    assert {dict(r[1])["RULEKIND"] for r in found[len(AUTHORED) :]} <= {"PolygonConnect"}


def test_every_record_comes_back_as_it_was_read(tmp_path: Path) -> None:
    board, before = _to_kicad(tmp_path)
    assert not list(tmp_path.rglob("*.json"))  # the board alone carries them
    payload = boardcarrier.carried(board.read_text("utf-8"))[rulecarrier.PROPERTY]
    carried = rulecarrier.read_carrier(payload.decode("utf-8"))
    assert [(c.number, c.fields) for c in carried] == before
    assert [bool(c.blocks) for c in carried][: len(AUTHORED)] == [True, True, False, False, False]
    back, report = _back(board, tmp_path)
    assert back == before
    rows = {row.kind: row for row in report.rows}
    assert rows["rule"].written == rows["rule"].source and rows["rule"].lost == 0


def test_a_rule_edited_in_kicad_is_written_as_kicad_holds_it(tmp_path: Path) -> None:
    board, before = _to_kicad(tmp_path)
    _edit(board, "(opt 0.1524mm)", "(opt 0.2mm)")
    back, _report = _back(board, tmp_path)
    assert [r for r in back if r in before] == before[1:]
    (width,) = [dict(r[1]) for r in back if dict(r[1])["RULEKIND"] == "Width"]
    assert width["PREFEREDWIDTH"] == "7.874mil" and width["PRIORITY"] == "1"


def test_a_source_rule_kicad_lost_needs_consent_and_a_kicad_rule_does_not(tmp_path: Path) -> None:
    board, before = _to_kicad(tmp_path)
    _edit(board, " (opt 0.1524mm)", "")
    back, report = _back(board, tmp_path)
    assert back == before[1:]
    assert "rule" in report.refused
    with pytest.raises(LossyConversionError) as raised:
        convert(board, to="altium")
    assert SOURCE_RULE_LOST in str(raised.value.issues) or "rule" in raised.value.refused
    added = '(rule "own_width"\n\t(constraint track_width (min 0.1mm) (max 1mm))\n)\n'
    fresh, before = _to_kicad(tmp_path / "fresh")
    fresh.with_suffix(".kicad_dru").write_text(
        fresh.with_suffix(".kicad_dru").read_text("utf-8") + added, "utf-8"
    )
    back, report = _back(fresh, tmp_path / "fresh")
    assert back == before and "rule" not in report.refused


def test_the_carrier_text_reads_back() -> None:
    sha = rulecarrier.digest("(rule x)")
    carried = (rulecarrier.Carried(2, (("RULEKIND", "Width"), ("NAME", "W")), {"fenolite_1_w": sha}),)
    assert rulecarrier.read_carrier(rulecarrier.carrier_text(carried)) == carried
    assert carried[0].kept({"fenolite_1_w": sha}) and not carried[0].kept({})
    with pytest.raises(ValueError):
        rulecarrier.read_carrier('{"schema": "other"}')


def test_the_board_property_is_replaced_and_leaves_the_board_as_it_was() -> None:
    """``boardcarrier`` adds its properties after ``setup`` and changes no other byte; a second write of
    the same name replaces the first."""
    text = BOARD.read_text("utf-8")
    once = boardcarrier.with_carried(text, {"Fenolite.Altium.Rules6": b"one", "Fenolite.Altium.Other": b"x"})
    twice = boardcarrier.with_carried(once, {"Fenolite.Altium.Rules6": b"two"})
    assert boardcarrier.carried(twice) == {"Fenolite.Altium.Rules6": b"two", "Fenolite.Altium.Other": b"x"}
    assert boardcarrier.with_carried(twice, {"Fenolite.Altium.Rules6": b"one"}) == once
    lines = [line for line in once.splitlines(keepends=True) if '(property "Fenolite.Altium.' not in line]
    assert "".join(lines) == text and boardcarrier.carried(text) == {}
    for bad in ("Rules6", "Fenolite.Other.X"):
        with pytest.raises(ValueError):
            boardcarrier.with_carried(text, {bad: b""})
    with pytest.raises(ValueError):
        boardcarrier.unpack("not base64!")
