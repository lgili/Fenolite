# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper and fills follow a renamed net (capability layout-lens, "Copper items follow their nets" and "Zone
fills and the staleness digest"; change c0069). Each test builds the blink, edits the board by token edit,
renames a net in the script and builds again."""

from __future__ import annotations

from pathlib import Path

import pytest
from _board_only import add_h1
from _layout_edit import EDIT_UUIDS, ZONE_UUID, add_filled_zone, edit_blink
from _project import COPPER_WARN, Project, codes, footprint

from fenolite.model.design import Design


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def rename_net(p: Project, old: str, new: str, *, alias: bool = True) -> None:
    p.edit_script(f'Net("{old}")', f'Net("{new}")')
    if alias:
        p.edit_script("design.add(u1, r1, d1)", f'design.add(u1, r1, d1)\ndesign.moved_net("{old}", "{new}")')


def copper(design: Design) -> dict[str, tuple[str, str | None]]:
    """KiCad uuid → (kind, net name) of every track and via."""
    assert design.board is not None
    names = {n.id: n.name for n in design.circuit.nets}
    found: dict[str, tuple[str, str | None]] = {}
    for kind, items in (("track", design.board.tracks), ("via", design.board.vias)):
        for item in items:
            found[item.native_ids["kicad"]] = (kind, names.get(item.net_id or ""))
    return found


def of(env: dict[str, object], code: str) -> list[dict[str, str]]:
    return [i for i in env["issues"] if i["code"] == code]  # type: ignore[union-attr,index]


@pytest.mark.parametrize("target", [9, 10])
def test_renamed_net_keeps_its_routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int) -> None:
    p = Project(tmp_path, monkeypatch, target)
    p.edit_board(edit_blink)
    before = p.read()
    rename_net(p, "LED_A", "LED_ANODE")
    code, env, err = p.build("--confirm")
    assert code == 0, err
    after = p.read()
    seg_f, seg_b, via = EDIT_UUIDS
    assert copper(after) == {
        seg_f: ("track", "LED_ANODE"),
        seg_b: ("track", "LED_ANODE"),
        via: ("via", "LED_ANODE"),
    }
    assert before.board is not None and after.board is not None
    ends = lambda d: sorted((t.start, t.end, t.width, t.layer) for t in d.board.tracks)  # noqa: E731
    assert ends(after) == ends(before)
    (used,) = of(env, "layout.net-alias-used")
    assert "LED_A" in used["message"] and "LED_ANODE" in used["message"]
    assert "2 tracks" in used["message"] and "1 vias" in used["message"] and used["where"] == "LED_ANODE"
    assert "layout.net-removed" not in codes(env)
    assert env["result"]["preserved"]["net_aliases"] == {"LED_ANODE": "LED_A"}  # type: ignore[index]
    assert "LED_A" not in {n.name for n in after.circuit.nets}
    # the alias is needed for one build only
    p.edit_script('design.moved_net("LED_A", "LED_ANODE")', "")
    first = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 0 and p.files() == first and "layout.net-alias-unused" not in codes(env)


def test_rename_without_an_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    rename_net(p, "LED_A", "LED_ANODE", alias=False)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert copper(p.read()) == {}
    (removed,) = of(env, "layout.net-removed")
    assert removed["where"] == "LED_A" and "layout.net-alias-used" not in codes(env)


def test_alias_left_in_the_script_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    rename_net(p, "LED_A", "LED_ANODE")
    assert p.build("--confirm")[0] == 0
    code, env, _ = p.build("--confirm")
    (unused,) = of(env, "layout.net-alias-unused")
    assert code == 0 and unused["severity"] == "warning"
    assert "LED_A" in unused["message"] and "LED_ANODE" in unused["message"]


def test_board_only_pad_follows_the_net(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(add_h1())
    rename_net(p, "GND", "GND0")
    code, env, err = p.build("--confirm")
    assert code == 0, err
    design = p.read()
    h1, _ = footprint(design, "H1")
    names = {n.id: n.name for n in design.circuit.nets}
    assert {p.number: names.get(p.net_id or "") for p in h1.pads}["1"] == "GND0"  # type: ignore[attr-defined]
    (used,) = of(env, "layout.net-alias-used")
    assert "1 board-only pads" in used["message"] and "layout.net-removed" not in codes(env)


def test_a_renamed_net_keeps_its_fills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: add_filled_zone(t, net="GND", layer="B.Cu"))
    assert p.build(*COPPER_WARN, "--confirm")[0] == 0
    rename_net(p, "GND", "GND0")
    code, env, err = p.build(*COPPER_WARN, "--confirm")
    assert code == 0, err
    design = p.read()
    assert design.board is not None
    (zone,) = [z for z in design.board.zones if z.native_ids["kicad"] == ZONE_UUID]
    names = {n.id: n.name for n in design.circuit.nets}
    assert names[zone.net_id or ""] == "GND0" and len(zone.fills) == 2
    assert "zone.fill-stale" not in codes(env)
    assert env["result"]["preserved"]["fills"] == {"kept": 1, "dropped": 0}  # type: ignore[index]


def test_a_rename_that_moves_a_pin_drops_the_fills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: add_filled_zone(t, net="GND", layer="B.Cu"))
    assert p.build(*COPPER_WARN, "--confirm")[0] == 0
    rename_net(p, "GND", "GND0")
    p.edit_script("if pin not in (1, 9, 10)", "if pin not in (1, 9, 10, 11)")  # pin 11 is no longer marked
    p.edit_script("connect(gnd, u1[10], d1[1])", "connect(gnd, u1[10], u1[11], d1[1])")
    code, env, err = p.build(*COPPER_WARN, "--confirm")
    assert code == 0, err
    assert "zone.fill-stale" in codes(env)
