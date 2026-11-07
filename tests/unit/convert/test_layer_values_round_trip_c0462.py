# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every pair a rule's bag takes is a key of the closed table, and a board whose Width record holds a
per-layer value converts to KiCad and back (change c0462, task 4.1; capability altium-project-reader,
"Per-layer values").

Public row ``-01`` broke the way back with ``KeyError: 'layer_value'`` (``FEN-1001``): its Width record holds
per-layer keys of the mid-layers only, which its internal planes do not take, so its import gives no per-layer
rule; the document written back from KiCad declares the two inner layers as mid-layers, and its import then
gives two. The source here is written by Fenolite from the committed
``tests/data/kicad/board/two_layer.kicad_pcb`` with an authored Width record. Authored values only.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path

from fenolite.api import convert
from fenolite.backends.altium import lower
from fenolite.backends.altium.adapter import ids
from fenolite.backends.altium.read import rules as read_rules
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad import fpitems
from fenolite.convert import pads
from fenolite.convert.sources import read_source

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
Record = tuple[int, tuple[tuple[str, str], ...]]
WIDTH: Record = (
    2,
    (
        ("RULEKIND", "Width"), ("NETSCOPE", "AnyNet"), ("LAYERKIND", "SameLayer"),
        ("SCOPE1EXPRESSION", "All"), ("SCOPE2EXPRESSION", "All"), ("NAME", "Layered Width"),
        ("ENABLED", "TRUE"), ("PRIORITY", "1"),
        ("COMMENT", "authored"), ("UNIQUEID", "AUTHLAYW"), ("DEFINEDBYLOGICALDOCUMENT", "FALSE"),
        ("MAXLIMIT", "40mil"), ("MINLIMIT", "4mil"), ("PREFEREDWIDTH", "6mil"),
        ("TOPLAYER_MINWIDTH", "4mil"), ("TOPLAYER_PREFWIDTH", "6mil"), ("TOPLAYER_MAXWIDTH", "40mil"),
        ("BOTTOMLAYER_MINWIDTH", "4mil"), ("BOTTOMLAYER_PREFWIDTH", "6mil"),
        ("BOTTOMLAYER_MAXWIDTH", "20mil"),
    ),
)  # fmt: skip


def test_every_pair_of_the_rule_mapper_is_a_key_of_the_closed_table() -> None:
    """Each ``*_PAIR`` key the rule mapper puts in a rule's bag, but ``record`` (which the import moves to the
    rule's ``kept_text``), is a key of ``adapter.EXT_KEYS``: ``adapter.ids.bag`` raises ``KeyError`` on any
    other. A pair added without its row fails here before any conversion meets it."""
    pairs = {
        name: value
        for name, value in vars(read_rules).items()
        if name.endswith("_PAIR") and isinstance(value, str)
    }
    assert {"LAYER_PAIR", "CELL_PAIR", "UNJUDGED_PAIR"} <= set(pairs)
    assert {name: value for name, value in pairs.items() if value not in ids.EXT_KEYS} == {}


def _write(files: Mapping[str, bytes], folder: Path) -> None:
    for name, data in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def _width(path: Path) -> list[Record]:
    found: list[Record] = []
    for rule in read_pcbdoc(path.read_bytes()).rules:
        fields = tuple((key, value or "") for key, value in rule.record.fields)
        start = [key for key, _value in fields].index("RULEKIND")
        if dict(fields)["RULEKIND"] == "Width":
            found.append((rule.kind_number, fields[start:]))
    return found


def test_a_board_with_a_per_layer_width_converts_to_kicad_and_back(tmp_path: Path) -> None:
    design = read_source(BOARD).design
    design = pads.project(fpitems.with_graphic_nets(fpitems.with_footprint_items(design).design))
    written = lower.write_design(
        dataclasses.replace(design, rules=None), allow_lossy=True, source_rules=(WIDTH,), full_drill=True
    )
    _write(written.files, tmp_path / "source")
    (source,) = (tmp_path / "source").glob("*.PcbDoc")
    imported = read_source(source).design
    assert imported.rules is not None
    widths = [rule for rule in imported.rules.rules if rule.kind == "track_width"]
    layered = [dict(rule.ext["altium"].payload) for rule in widths]
    assert [bag.get(read_rules.LAYER_PAIR) for bag in layered] == [None, "B.Cu"]
    _write(convert(source, to="kicad", allow_lossy=True).conversion.files, tmp_path / "kicad")
    (board,) = (tmp_path / "kicad").glob("*.kicad_pcb")
    _write(convert(board, to="altium", allow_lossy=True).conversion.files, tmp_path / "back")
    (back,) = (tmp_path / "back").glob("*.PcbDoc")
    assert _width(back) == [WIDTH]
    again = read_source(back).design
    assert again.rules is not None
    assert [
        dict(rule.ext["altium"].payload).get(read_rules.LAYER_PAIR)
        for rule in again.rules.rules
        if rule.kind == "track_width"
    ] == [None, "B.Cu"]
