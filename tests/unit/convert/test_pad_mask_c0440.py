# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The solder-mask expansion of each pad survives a conversion both ways, and ``equivalent`` compares it
(change c0440; capability design-conversion, "Mask and paste of imported pads"; capability altium-pcb-writer,
"Pad masks"; capability design-equivalence, "Pad mask expansion").

Before c0440 the conversion to KiCad emptied each pad's Altium bag before it read the pad's mode, so every
pad took the rule's expansion, and the Altium writer wrote every pad "from the rules", leaving a pad's own
margin out. The project is the authored ``tests/data/altium/blink``; its KiCad board is edited here."""

from __future__ import annotations

import dataclasses
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from _gensheets import generated

from fenolite.api import run
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord
from fenolite.checks.equivalence import norm
from fenolite.convert import convert_project
from fenolite.convert.openings import MASK_RULE, RuleExpansions, open_pad, rule_expansion, source_pairs
from fenolite.core.coords import Point, Size
from fenolite.model.base import ExtBag
from fenolite.model.board import Board, Pad

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
MARGIN = 50_000  # 0.05 mm, 19685 Altium units
RULE = {"RULEKIND": MASK_RULE, "PRIORITY": "1", "SCOPE1EXPRESSION": "All", "EXPANSION": "4mil"}


def _pad(**bag: str) -> Pad:
    pad = Pad(id="pad-1", number="1", shape="rect", size=Size(1_000_000, 1_000_000), position=Point(0, 0),
              layers=("F.Cu",), kind="smd")  # fmt: skip
    if not bag:
        return pad
    return dataclasses.replace(pad, ext={"altium": ExtBag("altium", tuple(bag.items()))})


def test_a_manual_zero_is_kept() -> None:
    """A manual expansion of 0 is the pad's own margin, not the rule's: it stays 0."""
    rules = RuleExpansions(mask=rule_expansion([RULE], MASK_RULE))
    manual, _ = open_pad(_pad(mask="2,0"), rules)
    follows, _ = open_pad(_pad(), rules)
    assert (manual.mask_margin, follows.mask_margin) == (0, 101_600)


def test_the_mode_is_read_before_the_bag_is_emptied() -> None:
    """``open_pad`` takes the pairs read before the conversion empties the bag; without them the emptied pad
    took the rule's expansion, which is how a manual pad of a converted board got another opening."""
    rules = RuleExpansions(mask=rule_expansion([RULE], MASK_RULE))
    read = _pad(mask="2,19685", paste="2,-10000")
    emptied = dataclasses.replace(read, ext={})
    kept, _ = open_pad(emptied, rules, source_pairs(read))
    assert (kept.mask_margin, kept.paste_margin) == (MARGIN, -25_400)
    assert open_pad(emptied, rules)[0].mask_margin == 101_600


def _write(files: dict[str, bytes], folder: Path) -> None:
    for name, data in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _with_margins(text: str) -> str:
    """Every board pad with a margin of 0.05 mm, the first one with 0."""
    count = 0

    def margin(found: re.Match[str]) -> str:
        nonlocal count
        count += 1
        value = "0" if count == 1 else "0.05"
        return f"{found.group(0)} (solder_mask_margin {value})"

    return re.sub(
        r'\(layers "F\.Cu"[^)]*\)|\(layers "\*\.Cu"[^)]*\)|\(layers "F\.Cu" "B\.Cu"[^)]*\)', margin, text
    )


def _differences(result: Mapping[str, Any], kind: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = result["differences"]
    return [row for row in rows if row["kind"] == kind]


def test_a_pad_margin_survives_both_ways(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """KiCad → Altium writes each pad's own margin as a manual expansion; Altium → KiCad gives it back; and
    level 3 of ``equivalent`` finds the pads of the original document, which follow the rules of a
    document without a mask rule, different from them. The first leg writes the generated schematic, whose
    netlist the pure way back reads without ``kicad-cli`` (change c0470)."""
    generated(monkeypatch)
    kicad = convert_project(BLINK, to="kicad", kicad_version=10, allow_lossy=True)
    first = tmp_path / "k"
    _write(dict(kicad.files), first)
    board = first / "blink.kicad_pcb"
    board.write_text(_with_margins(board.read_text(encoding="utf-8")), encoding="utf-8")
    altium = convert_project(first / "blink.kicad_pro", to="altium", allow_lossy=True)
    second = tmp_path / "a"
    _write(dict(altium.files), second)
    document = read_pcbdoc((second / "blink.PcbDoc").read_bytes())
    modes = Counter((p.solder_mode, p.solder_expansion) for p in document.pads if isinstance(p, PadRecord))
    assert set(modes) <= {(rec.PAD_EXPANSION_MANUAL, 19_685), (rec.PAD_EXPANSION_MANUAL, 0)}
    assert modes[rec.PAD_EXPANSION_MANUAL, 0] == 1 and modes[rec.PAD_EXPANSION_MANUAL, 19_685] >= 1
    again = convert_project(second / "blink.PrjPcb", to="kicad", kicad_version=10, allow_lossy=True)
    margins = Counter(re.findall(r"\(solder_mask_margin ([^)]*)\)", again.files["blink.kicad_pcb"].decode()))
    assert margins == Counter({"0.05": sum(modes.values()) - 1, "0": 1})
    same = run("equivalent", str(second / "blink.PcbDoc"), str(board), "--level", "3")
    assert _differences(same.result, "pad-mask") == []
    changed = run(
        "equivalent", str(BLINK.parent / "blink.PcbDoc"), str(second / "blink.PcbDoc"), "--level", "3"
    )
    found = _differences(changed.result, "pad-mask")
    assert len(found) == sum(modes.values())
    assert {row["a"] for row in found} == {norm.MASK_RULES}


def test_mask_expansion_of_each_form() -> None:
    """``api.equivalence.mask_of``: the forms an Altium side gives, and a KiCad side's own margin."""
    from fenolite.api.equivalence import mask_of
    from fenolite.model.design import Design, DesignHeader

    def design(board: Board) -> Design:
        header = DesignHeader(id="dsn_m", name="m", schema_version="0", fenolite_version="0")
        return Design(header, board=board)

    altium = mask_of(design(Board(id="board", ext={"altium": ExtBag("altium", ())})))
    assert altium(_pad(mask="2,19685")) == MARGIN
    assert altium(_pad(mask="0,0")) == norm.MASK_NONE
    assert altium(_pad()) == norm.MASK_RULES
    kicad = mask_of(design(Board(id="board")))
    assert kicad(_pad()) is None and kicad(dataclasses.replace(_pad(), mask_margin=0)) == 0
