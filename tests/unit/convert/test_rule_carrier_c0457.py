# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Carried rule records against a rules file written again (change c0457; capability design-conversion,
"Rule records through KiCad").

The source is written by Fenolite from the committed ``tests/data/kicad/board/two_layer.kicad_pcb`` with
authored rule records: a Width, an unscoped and a scoped Clearance, a Height KiCad has no rule for.
Authored values only.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Mapping
from pathlib import Path

from fenolite.api import convert, run
from fenolite.backends.altium import lower
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad import boardcarrier, fpitems
from fenolite.convert import pads, rulecarrier
from fenolite.convert.report import SOURCE_RULE_LOST
from fenolite.convert.sources import read_source
from fenolite.convert.to_altium import EDITED_LOWERED, LIMITS_EDITED

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
STAMP = "2026-11-06T00:00:00Z"
Record = tuple[int, tuple[tuple[str, str], ...]]


def _head(kind: str, name: str, priority: int, scope: str = "All") -> list[tuple[str, str]]:
    return [
        ("RULEKIND", kind), ("NETSCOPE", "DifferentNets" if kind == "Clearance" else "AnyNet"),
        ("LAYERKIND", "SameLayer"), ("SCOPE1EXPRESSION", scope), ("SCOPE2EXPRESSION", "All"), ("NAME", name),
        ("ENABLED", "TRUE"), ("PRIORITY", str(priority)), ("COMMENT", "authored"),
        ("UNIQUEID", f"AUTH{priority}{kind[:4].upper()}"), ("DEFINEDBYLOGICALDOCUMENT", "FALSE"),
    ]  # fmt: skip


def _gap(value: str) -> list[tuple[str, str]]:
    return [("GAP", value), ("GENERICCLEARANCE", value), ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
            ("OBJECTCLEARANCES", "")]  # fmt: skip


AUTHORED: tuple[Record, ...] = (
    (2, (*_head("Width", "Signal Width", 3), ("MAXLIMIT", "40mil"), ("MINLIMIT", "4mil"),
         ("PREFEREDWIDTH", "6mil"))),
    (0, (*_head("Clearance", "Board Gap", 1), *_gap("6mil"))),
    (0, (*_head("Clearance", "VCC Gap", 2, "InNet('VCC')"), *_gap("10mil"))),
    (50, (*_head("Height", "Tall Parts", 1), ("MINHEIGHT", "0mil"), ("MAXHEIGHT", "1000mil"),
          ("PREFHEIGHT", "500mil"))),
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


def _source(folder: Path) -> Path:
    design = read_source(BOARD).design
    design = pads.project(fpitems.with_graphic_nets(fpitems.with_footprint_items(design).design))
    written = lower.write_design(
        dataclasses.replace(design, rules=None), allow_lossy=True, source_rules=AUTHORED, full_drill=True
    )
    _write(written.files, folder / "source")
    (source,) = (folder / "source").glob("*.PcbDoc")
    return source


def _to_kicad(folder: Path) -> tuple[Path, list[Record]]:
    source = _source(folder)
    _write(convert(source, to="kicad", allow_lossy=True).conversion.files, folder / "kicad")
    (board,) = (folder / "kicad").glob("*.kicad_pcb")
    return board, _records(source)


def _back(board: Path, folder: Path) -> tuple[list[Record], dict[str, dict[str, int]], dict[str, int]]:
    """The records written back without ``--allow-lossy``, the rule row's reasons by outcome, and its
    counts."""
    result = convert(board, to="altium").conversion
    _write(result.files, folder / "back")
    (document,) = (folder / "back").glob("*.PcbDoc")
    (row,) = [row for row in result.report.rows if row.kind == "rule"]
    reasons: dict[str, dict[str, int]] = {}
    for reason in row.reasons:
        reasons.setdefault(reason.outcome, {})[reason.reason] = reason.count
    return _records(document), reasons, {"changed": row.changed, "lost": row.lost}


def _dru(board: Path) -> Path:
    return board.with_suffix(".kicad_dru")


def test_rules_written_again_with_other_names_and_order_are_the_records(tmp_path: Path) -> None:
    """Every rule renamed, the rules in reverse order, the conditions with other spaces: each record still
    comes back as it was read, and nothing changes or is lost."""
    board, before = _to_kicad(tmp_path)
    rules = rulecarrier.dru_rules(_dru(board).read_text("utf-8"))
    assert len(rules) >= 3
    text = _dru(board).read_text("utf-8")
    blocks = re.findall(r'\(rule "[^"]+"\n.*?\n\)\n', text, flags=re.S)
    assert len(blocks) == len(rules)
    renamed = [re.sub(r'\(rule "([^"]+)"', r'(rule "again_\1"', b, count=1) for b in reversed(blocks)]
    spaced = [b.replace("== ", "==   ") for b in renamed]
    _dru(board).write_text("(version 1)\n" + "".join(spaced), encoding="utf-8")
    back, reasons, counts = _back(board, tmp_path)
    assert back == before
    assert counts == {"changed": 0, "lost": 0} and not reasons


def test_a_record_whose_limit_was_edited_keeps_its_name_and_priority(tmp_path: Path) -> None:
    board, before = _to_kicad(tmp_path)
    text = _dru(board).read_text("utf-8")
    assert "(min 0.254mm)" in text
    _dru(board).write_text(text.replace("(min 0.254mm)", "(min 0.26mm)", 1), encoding="utf-8")
    back, reasons, counts = _back(board, tmp_path)
    (vcc,) = [dict(r[1]) for r in back if dict(r[1]).get("NAME") == "VCC Gap"]
    assert (vcc["PRIORITY"], vcc["SCOPE1EXPRESSION"], vcc["GAP"], vcc["GENERICCLEARANCE"]) == (
        "2", "InNet('VCC')", "10.2362mil", "10.2362mil"
    )  # fmt: skip
    assert [r for r in back if dict(r[1]).get("NAME") != "VCC Gap"] == [
        r for r in before if dict(r[1]).get("NAME") != "VCC Gap"
    ]
    assert reasons == {"changed": {LIMITS_EDITED: 1}} and counts == {"changed": 1, "lost": 0}


def test_a_record_edited_otherwise_is_written_as_a_rule_of_its_kind(tmp_path: Path) -> None:
    """A condition added to the unscoped clearance in KiCad: the rule is written as a Clearance record of its
    own name and the next priority, a change, not a loss; the other records come back as read."""
    board, before = _to_kicad(tmp_path)
    text = _dru(board).read_text("utf-8")
    block = re.search(r'\(rule "fenolite_1_board_gap"\n', text)
    assert block is not None
    edited = text.replace(block.group(0), block.group(0) + "\t(condition \"A.NetName == 'GND'\")\n", 1)
    _dru(board).write_text(edited, encoding="utf-8")
    back, reasons, counts = _back(board, tmp_path)
    assert SOURCE_RULE_LOST not in reasons.get("lost", {})
    assert reasons.get("changed") == {EDITED_LOWERED: 1} and counts["changed"] == 1
    gaps = [dict(r[1]) for r in back if dict(r[1])["RULEKIND"] == "Clearance"]
    assert {(g["NAME"], g["SCOPE1EXPRESSION"], g["GAP"]) for g in gaps} >= {
        ("VCC Gap", "InNet('VCC')", "10mil"),
        ("Clearance_net_GND", "InNet('GND')", "6mil"),
    }
    assert "Board Gap" not in {g["NAME"] for g in gaps}
    assert [r for r in back if r in before] == [r for r in before if dict(r[1]).get("NAME") != "Board Gap"]


def test_a_version_0_property_matches_a_renamed_rule(tmp_path: Path) -> None:
    """A board converted before change c0457 keys each rule list by its text: a rule renamed since still
    matches under the name the record gave."""
    board, before = _to_kicad(tmp_path)
    text = board.read_text("utf-8")
    records = rulecarrier.read_carrier(boardcarrier.carried(text)[rulecarrier.PROPERTY].decode("utf-8"))
    from fenolite.backends.kicad.dru import rule_text

    nodes = {rule.name: rule.node for rule in rulecarrier.dru_rules(_dru(board).read_text("utf-8"))}
    rows = [
        {"number": r.number, "fields": [list(p) for p in r.fields],
         "blocks": {n: rulecarrier.digest(rule_text(nodes[n])) for n in r.blocks}}
        for r in records
    ]  # fmt: skip
    payload = json.dumps({"schema": "fenolite.altium-rules.v0", "records": rows}).encode("utf-8")
    board.write_text(boardcarrier.with_carried(text, {rulecarrier.PROPERTY: payload}), encoding="utf-8")
    rules = _dru(board).read_text("utf-8")
    _dru(board).write_text(rules.replace('"fenolite_3_signal_width"', '"renamed_width"'), encoding="utf-8")
    back, reasons, counts = _back(board, tmp_path)
    assert back == before and counts == {"changed": 0, "lost": 0} and not reasons


def test_an_imported_design_rebuilt_with_one_clearance_edited(tmp_path: Path) -> None:
    """Flow A: ``import --to python``, one clearance edited in ``design.py``, ``build``, then ``convert --to
    altium`` without ``--allow-lossy``: it exits 0, the edited record keeps its name and priority with the new
    gap, and no other record changes."""
    source = _source(tmp_path)
    before = _records(source)

    def go(*args: str) -> None:
        planned = run(*args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
        assert planned.exit_code == 0, planned.error
        done = run(
            *args, "--confirm", "--plan", str(planned.result["plan_id"]), cwd=tmp_path, timestamp=STAMP
        )
        assert done.exit_code == 0, done.error

    go("import", str(source), "--to", "python", "--out", "py", "--licence", "CC0-1.0", "--copyright",
       "2026 Fenolite contributors", "--allow-lossy")  # fmt: skip
    design = tmp_path / "py" / "design.py"
    text = design.read_text("utf-8")
    assert 'min=mm("0.254")' in text
    design.write_text(text.replace('min=mm("0.254")', 'min=mm("0.26")', 1), encoding="utf-8")
    go("build", str(design), "--out", "b")
    (built,) = (tmp_path / "b").glob("*.kicad_pcb")
    back, reasons, _counts = _back(built, tmp_path)
    assert SOURCE_RULE_LOST not in reasons.get("lost", {})
    assert reasons.get("changed") == {LIMITS_EDITED: 1}
    (vcc,) = [dict(r[1]) for r in back if dict(r[1]).get("NAME") == "VCC Gap"]
    assert (vcc["PRIORITY"], vcc["GAP"]) == ("2", "10.2362mil")
    assert [r for r in before if dict(r[1]).get("NAME") != "VCC Gap"] == [
        r for r in back if r in before and dict(r[1]).get("NAME") != "VCC Gap"
    ]
    assert not [
        r for r in back if dict(r[1])["RULEKIND"] == "Clearance" and dict(r[1])["NAME"] == "Clearance"
    ]
