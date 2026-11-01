# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The plan of ``sync --to-source`` (capability layout-lens, "Sync of the source tree"; change c0069)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from _buildhelp import blink
from _layout_edit import D1_SHIFT, edit_blink
from _preserve_help import board_text

from fenolite.dsl import BOARD_ORIGIN, Design, module_moves, moves, net_moves, placements, to_model
from fenolite.lens import preserve
from fenolite.lens.altium_schematic import ISSUE_CODES as ALTIUM_ISSUE_CODES
from fenolite.lens.edits import EDIT_ISSUE_CODES, BaseRecord, read_base, read_edits
from fenolite.lens.moved import Aliases
from fenolite.lens.placements import SourcePlacement, write_placements
from fenolite.lens.preserve import ExistingProject
from fenolite.lens.sync import EVIDENCE, SYNC_ISSUE_CODES, SyncPlan, plan_sync

ROOT = Path(__file__).resolve().parents[3]
CODE = re.compile(r'"(sync\.[a-z0-9-]+)"')


def plan(
    design: Design,
    text: str,
    current: str | None = None,
    *,
    base: BaseRecord | None = None,
    legacy: str | None = None,
) -> SyncPlan:
    aliases = Aliases(moves(design), module_moves(design), net_moves(design))
    found = plan_sync(
        to_model(design),
        ExistingProject(board=text),
        name="blink",
        aliases=aliases,
        origin=BOARD_ORIGIN,
        edits_text=current,
        placements_text=legacy,
        base=base,
        requests=placements(design),
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


def fresh_base() -> BaseRecord:
    from _buildhelp import build

    out = build(blink(), 10, write_base=True)
    return read_base(out.files["fenolite-base.json"].decode("utf-8"), target="kicad")


@pytest.mark.parametrize("with_base", [True, False])
def test_edited_board_synced(with_base: bool) -> None:
    d = blink()
    found = plan(d, board_text(edit=edit_blink), base=fresh_base() if with_base else None)
    assert list(found.files) == ["edits.toml"] and found.issues == ()
    parts = read_edits(found.files["edits.toml"], origin=BOARD_ORIGIN).parts
    assert list(parts) == ["D1"]
    at = placements(d)["D1"].at
    assert parts["D1"].values == {"position": (at.x + D1_SHIFT, at.y)}
    assert parts["D1"].over == {"position": (at.x, at.y)}
    assert dict(found.result) == {
        "board": "blink.kicad_pcb",
        "placements": 1,
        "edits": ["D1#position"],
        "pending": [],
        "conflicts": [],
        "unplaced": [],
        "orphans": [],
        "board_only": [],
        "symbols": None,
        "files": ["edits.toml"],
    }


def test_nothing_to_write() -> None:
    text = board_text(edit=edit_blink)
    first = plan(blink(), text)
    again = plan(blink(), text, first.files["edits.toml"])
    assert dict(again.files) == {} and again.result["files"] == [] and again.result["placements"] == 1


def test_orphaned_complement_reported() -> None:
    found = plan(without_r1(), board_text(edit=edit_blink))
    by_code = {i.code: i for i in found.issues}
    assert set(by_code) == {"sync.orphan", "sync.net-dropped"}
    assert "R1" in by_code["sync.orphan"].message and by_code["sync.orphan"].where == "R1"
    dropped = by_code["sync.net-dropped"]
    assert dropped.where == "LED_A" and "2 tracks" in dropped.message and "1 vias" in dropped.message
    assert found.result["orphans"] == ["R1"] and found.result["placements"] == 1


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
    assert found.result["placements"] == 0 and '[part."R1"]' not in found.files["edits.toml"]


def test_evidence() -> None:
    assert EVIDENCE == preserve.EVIDENCE


def test_closed_set() -> None:
    assert dict(SYNC_ISSUE_CODES) == {
        "sync.would-change": "error",
        "sync.conflict": "error",
        "sync.orphan": "warning",
        "sync.net-dropped": "warning",
        "sync.value-differs": "warning",
        "sync.symbol-off-grid": "warning",
        "sync.placements-migrated": "info",
    }
    produced: set[str] = set()
    for path in (Path(__file__), ROOT / "tests" / "unit" / "cli" / "test_sync_cmd.py"):
        produced |= set(CODE.findall(path.read_text(encoding="utf-8")))
    assert produced == set(SYNC_ISSUE_CODES)
    source = (ROOT / "src" / "fenolite").rglob("*.py")
    used = {code for path in source for code in CODE.findall(path.read_text(encoding="utf-8"))}
    assert used == (
        set(SYNC_ISSUE_CODES)
        | {code for code in ALTIUM_ISSUE_CODES if code.startswith("sync.")}
        | {code for code in EDIT_ISSUE_CODES if code.startswith("sync.")}
    )


def test_symbol_placements_are_planned_with_the_sheets() -> None:
    """The schematic half: with the sheets the second file is planned, and not when its text is held."""
    from _buildhelp import build

    from fenolite.backends.kicad.sch import read_schematic
    from fenolite.lens.schplacements import read_placements as read_symbols
    from fenolite.lens.sync import SYMBOL_FILE_NAME

    files = build(blink(), 10).files
    sheet = read_schematic(files["blink.kicad_sch"].decode("utf-8"), file="blink.kicad_sch")

    def run(held: str | None) -> SyncPlan:
        return plan_sync(
            to_model(blink()),
            ExistingProject(board=files["blink.kicad_pcb"].decode("utf-8")),
            name="blink",
            aliases=Aliases({}, {}, {}),
            origin=BOARD_ORIGIN,
            placements_text=None,
            symbol_placements_text=held,
            sheets=[sheet],
        )

    first = run(None)
    assert SYMBOL_FILE_NAME == "schematic-placements.toml" and first.result["symbols"] == 3
    assert sorted(read_symbols(first.files[SYMBOL_FILE_NAME])) == ["D1", "R1", "U1"]
    assert SYMBOL_FILE_NAME not in run(first.files[SYMBOL_FILE_NAME]).files
    assert plan(blink(), files["blink.kicad_pcb"].decode("utf-8")).result["symbols"] is None


# --- the edits of change c0250 --------------------------------------------------------------------


def _value(text: str, ref: str, value: str) -> str:
    from _layout_edit import edit_properties

    edited, _ = edit_properties(text, None, {ref: {"value": value}})
    assert edited is not None
    return edited


def test_value_edited_in_kicad_with_a_base() -> None:
    found = plan(blink(), _value(board_text(), "R1", "4k7"), base=fresh_base())
    assert found.issues == ()
    parts = read_edits(found.files["edits.toml"], origin=BOARD_ORIGIN).parts
    assert parts["R1"].values == {"value": "4k7"} and parts["R1"].over == {"value": "330"}
    assert found.result["edits"] == ["R1#value"]


def test_value_edited_in_kicad_without_a_base() -> None:
    found = plan(blink(), _value(board_text(), "R1", "4k7"))
    (issue,) = found.issues
    assert (issue.code, issue.where) == ("sync.value-differs", "R1")
    assert all(word in issue.message for word in ("R1", "value", "4k7", "330"))
    assert "value" not in found.files["edits.toml"]


def test_conflict_blocks_the_sync() -> None:
    d = blink()
    d.parts["R1"].value = "470"
    found = plan(d, _value(board_text(), "R1", "4k7"), base=fresh_base())
    (conflict,) = [i for i in found.issues if i.code == "sync.conflict"]
    assert conflict.where == "R1#value" and all(v in conflict.message for v in ("'330'", "'470'", "'4k7'"))
    assert dict(found.files) == {} and found.result["conflicts"][0]["key"] == "R1#value"  # type: ignore[index]


def test_pending_code_change_is_not_captured() -> None:
    d = blink()
    d.parts["R1"].value = "470"
    found = plan(d, board_text(), base=fresh_base())
    assert found.result["pending"] == ["R1#value"] and "value" not in found.files["edits.toml"]


def test_legacy_placements_migrated() -> None:
    d = blink()
    text = board_text(edit=edit_blink)
    at = placements(d)["R1"].at
    legacy = write_placements(
        {
            "D1": SourcePlacement(placements(d)["D1"].at, 0, "bottom", False),
            "R2": SourcePlacement(at, 0, "top", False),
        },
        origin=BOARD_ORIGIN,
    )
    found = plan(d, text, legacy=legacy)
    assert list(found.files) == ["edits.toml"]
    (migrated,) = [i for i in found.issues if i.code == "sync.placements-migrated"]
    assert migrated.where == "placements.toml" and migrated.severity == "info"
    parts = read_edits(found.files["edits.toml"], origin=BOARD_ORIGIN).parts
    assert list(parts) == ["D1"]  # R2 is no part of the design, so its entry goes
