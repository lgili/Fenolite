# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The plan of ``sync --to-source`` (capability layout-lens, "Sync of the source tree"; change c0069)."""

from __future__ import annotations

import re
from pathlib import Path

from _buildhelp import blink
from _layout_edit import D1_SHIFT, edit_blink
from _preserve_help import board_text

from fenolite.dsl import BOARD_ORIGIN, Design, module_moves, moves, net_moves, placements, to_model
from fenolite.lens import preserve
from fenolite.lens.moved import Aliases
from fenolite.lens.placements import read_placements
from fenolite.lens.preserve import ExistingProject
from fenolite.lens.sync import EVIDENCE, SYNC_ISSUE_CODES, SyncPlan, plan_sync

ROOT = Path(__file__).resolve().parents[3]
CODE = re.compile(r'"(sync\.[a-z0-9-]+)"')


def plan(design: Design, text: str, current: str | None = None) -> SyncPlan:
    aliases = Aliases(moves(design), module_moves(design), net_moves(design))
    found = plan_sync(
        to_model(design),
        ExistingProject(board=text),
        name="blink",
        aliases=aliases,
        origin=BOARD_ORIGIN,
        placements_text=current,
    )
    assert all(SYNC_ISSUE_CODES[i.code] == i.severity for i in found.issues if i.code.startswith("sync."))
    return found


def without_r1() -> Design:
    """The blink without ``R1``, whose ``D1`` pin 2 is connected to nothing."""
    d = blink()
    del d.parts["R1"]
    del d.parts["D1"].connections["2"]
    del d.nets["LED_A"]
    return d


def test_edited_board_synced() -> None:
    d = blink()
    found = plan(d, board_text(edit=edit_blink))
    assert list(found.files) == ["placements.toml"] and found.issues == ()
    entries = read_placements(found.files["placements.toml"], origin=BOARD_ORIGIN).entries
    assert list(entries) == ["D1", "R1", "U1"]
    assert entries["D1"].at.x == placements(d)["D1"].at.x + D1_SHIFT
    assert dict(found.result) == {
        "board": "blink.kicad_pcb",
        "placements": 3,
        "unplaced": [],
        "orphans": [],
        "board_only": [],
        "symbols": None,
        "files": ["placements.toml"],
    }


def test_nothing_to_write() -> None:
    text = board_text(edit=edit_blink)
    first = plan(blink(), text)
    again = plan(blink(), text, first.files["placements.toml"])
    assert dict(again.files) == {} and again.result["files"] == [] and again.result["placements"] == 3


def test_orphaned_complement_reported() -> None:
    found = plan(without_r1(), board_text(edit=edit_blink))
    by_code = {i.code: i for i in found.issues}
    assert set(by_code) == {"sync.orphan", "sync.net-dropped"}
    assert "R1" in by_code["sync.orphan"].message and by_code["sync.orphan"].where == "R1"
    dropped = by_code["sync.net-dropped"]
    assert dropped.where == "LED_A" and "2 tracks" in dropped.message and "1 vias" in dropped.message
    assert found.result["orphans"] == ["R1"] and found.result["placements"] == 2


def test_net_alias_covers_the_copper() -> None:
    d = blink()
    net = d.nets.pop("LED_A")
    net.name = "LED_ANODE"
    d.nets["LED_ANODE"] = net
    text = board_text(edit=edit_blink)
    assert [i.code for i in plan(d, text).issues] == ["sync.net-dropped"]
    d.moved_net("LED_A", "LED_ANODE")
    assert plan(d, text).issues == ()


def test_value_edited_in_kicad() -> None:
    text = board_text()
    assert text.count('(property "Value" "330"') == 1
    found = plan(blink(), text.replace('(property "Value" "330"', '(property "Value" "4k7"'))
    (issue,) = found.issues
    assert (issue.code, issue.where) == ("sync.value-differs", "R1")
    assert all(word in issue.message for word in ("R1", "value", "4k7", "330"))


def test_footprint_and_property_differ() -> None:
    d = blink()
    d.parts["R1"].footprint = "Mini:Mini_LED_THT_3mm"
    d.parts["D1"].properties = {"Part number": "PN-2"}
    added = '(property "Part number" "PN-1" (at 0 0 0) (layer "F.Fab"))\n'
    text = board_text().replace('(property "Value" "LED"', added + '(property "Value" "LED"')
    found = plan(d, text)
    messages = {i.where: i.message for i in found.issues if i.code == "sync.value-differs"}
    assert "footprint" in messages["R1"] and "Mini:Mini_R_0603" in messages["R1"]
    assert "property Part number" in messages["D1"] and "PN-1" in messages["D1"] and "PN-2" in messages["D1"]


def test_board_only_and_unplaced_in_the_result() -> None:
    from _board_only import add_h1
    from _preserve_help import fresh

    d = blink()
    d.parts["R1"].request = None
    text = add_h1()(fresh(design=d).files["blink.kicad_pcb"].decode("utf-8"))
    again = blink()
    again.parts["R1"].request = None
    found = plan(again, text)
    assert found.result["unplaced"] == ["R1"] and found.result["board_only"] == ["H1"]
    assert found.result["placements"] == 2 and '[part."R1"]' not in found.files["placements.toml"]


def test_evidence() -> None:
    assert EVIDENCE == preserve.EVIDENCE


def test_closed_set() -> None:
    assert dict(SYNC_ISSUE_CODES) == {
        "sync.would-change": "error",
        "sync.orphan": "warning",
        "sync.net-dropped": "warning",
        "sync.value-differs": "warning",
        "sync.symbol-off-grid": "warning",
    }
    produced: set[str] = set()
    for path in (Path(__file__), ROOT / "tests" / "unit" / "cli" / "test_sync_cmd.py"):
        produced |= set(CODE.findall(path.read_text(encoding="utf-8")))
    # sync.symbol-off-grid belongs to the schematic half, which waits for the schematic reader (c0060)
    waiting = {"sync.symbol-off-grid"}
    assert produced <= set(SYNC_ISSUE_CODES) and set(SYNC_ISSUE_CODES) - waiting <= produced
    source = (ROOT / "src" / "fenolite").rglob("*.py")
    used = {code for path in source for code in CODE.findall(path.read_text(encoding="utf-8"))}
    assert used == set(SYNC_ISSUE_CODES)
