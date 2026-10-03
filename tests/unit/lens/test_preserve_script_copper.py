# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script copper in a merge (capability layout-lens, "Script copper in a merge"; change c0028): the routed
blink is built, its board edited as KiCad would (by token edit), and built again. No tool runs."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from _layout_edit import add_items, move_footprint, net_ref, pad_position
from _routed import Routed, codes, script_copper

from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.lens import preserve

MM = 1_000_000
USER_UUID = "5a0f7c1e-2b3d-4c5e-8f60-718293a4b5c6"


def _shift_segment(text: str, uuid: str, dy_mm: str) -> str:
    """The board text with the ``start`` of the segment ``uuid`` set 1 mm lower, its uuid kept."""
    root = parse(text)
    children: list[Node | Atom] = []
    found = 0
    for child in root.children:
        if isinstance(child, Node) and child.name == "segment" and uuid in dumps(child):
            start = child.find("start")
            assert start is not None
            x, y = (a.text for a in start.atoms())
            moved = parse(f"(start {x} {float(y) + float(dy_mm):.6f})")
            child = child.with_children([moved if c is start else c for c in child.children])
            found += 1
        children.append(child)
    assert found == 1
    return dumps(root.with_children(children), style="kicad")


def test_copper_follows_a_moved_footprint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch)
    before_tracks, before_vias = script_copper(project.read())
    project.edit_board(lambda text: move_footprint(text, "D1", 4 * MM, 0))
    moved_pad = pad_position(project.board.read_text(encoding="utf-8"), "D1", "2")
    code, env, _ = project.build("--confirm")
    assert code == 0
    tracks, vias = script_copper(project.read())
    by_uuid = {t.native_ids["kicad"]: t for t in tracks}
    led_a = by_uuid[copper_uuid("led_a", "seg[2]")]
    assert led_a.end == moved_pad
    assert [t.native_ids["kicad"] for t in tracks] == [t.native_ids["kicad"] for t in before_tracks]
    assert [v.native_ids["kicad"] for v in vias] == [v.native_ids["kicad"] for v in before_vias]
    found = codes(env)
    # two tracks end at D1: led_a seg[2] at pad 2 and gnd seg[3] at pad 1
    assert found.count("kicad.copper.regenerated") == 2 and "kicad.copper.stale" not in found
    regenerated = {i["where"] for i in env["issues"] if i["code"] == "kicad.copper.regenerated"}
    assert regenerated == {copper_uuid("led_a", "seg[2]"), copper_uuid("gnd", "seg[3]")}
    assert env["result"]["copper"] == {
        "intents": 4, "tracks": 11, "vias": 7, "regenerated": 2, "stale": 0, "duplicates": 0,
    }  # fmt: skip
    assert "D1" in env["result"]["preserved"]["kept"]
    again = project.files()
    code, env, _ = project.build("--confirm")
    assert code == 0 and project.files() == again and "kicad.copper.regenerated" not in codes(env)


def test_removed_intent_removed_copper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch)
    text = project.script.read_text(encoding="utf-8")
    start = text.index("design.stitch(")
    project.script.write_text(text[:start], encoding="utf-8")
    ast.parse(project.script.read_text(encoding="utf-8"))
    code, env, _ = project.build("--confirm")
    assert code == 0
    tracks, vias = script_copper(project.read())
    assert len(tracks) == 11 and len(vias) == 2  # the two via steps stay; the five stitch vias are gone
    stale = [i for i in env["issues"] if i["code"] == "kicad.copper.stale"]
    assert len(stale) == 5 and all(i["severity"] == "warning" for i in stale)
    assert {i["where"] for i in stale} == {copper_uuid("gnd_fence", f"via[{k}]") for k in range(5)}
    assert env["result"]["copper"]["stale"] == 5 and env["result"]["copper"]["intents"] == 3


def test_kicad_edit_of_script_copper_is_replaced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch)
    before = project.files()
    uuid = copper_uuid("led_drv", "seg[0]")
    project.edit_board(lambda text: _shift_segment(text, uuid, "1"))
    assert project.files() != before
    code, env, _ = project.build("--confirm")
    assert code == 0
    regenerated = [i for i in env["issues"] if i["code"] == "kicad.copper.regenerated"]
    assert (
        len(regenerated) == 1 and uuid in regenerated[0]["message"] and regenerated[0]["severity"] == "info"
    )
    assert project.files() == before  # the segment is back at its pad, byte for byte


def test_copper_drawn_in_kicad_is_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch)
    text = project.board.read_text(encoding="utf-8")
    segment = (
        f'(segment (start 105 128) (end 110 128) (width 0.5) (layer "F.Cu") {net_ref(text, "GND")}'
        f' (uuid "{USER_UUID}"))'
    )
    project.edit_board(lambda board: add_items(board, segment))
    code, env, _ = project.build("--confirm")
    assert code == 0 and not [c for c in codes(env) if c.startswith("kicad.copper.")]
    design = project.read()
    assert design.board is not None
    uuids = [t.native_ids["kicad"] for t in design.board.tracks]
    assert uuids[0] == USER_UUID and len(uuids) == 12  # board copper first, then the script's
    first = project.files()
    code, _, _ = project.build("--confirm")
    assert code == 0 and project.files() == first


def test_duplicate_of_script_copper_is_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch)
    before = project.files()
    text = project.board.read_text(encoding="utf-8")
    script_uuid = copper_uuid("led_drv", "seg[1]")
    (node,) = [
        c
        for c in parse(text).children
        if isinstance(c, Node) and c.name == "segment" and script_uuid in dumps(c)
    ]
    copy = dumps(node, style="compact").replace(script_uuid, USER_UUID)
    project.edit_board(lambda board: add_items(board, copy))
    code, env, _ = project.build("--confirm")
    assert code == 0 and codes(env).count("kicad.copper.duplicate") == 1
    assert env["result"]["copper"]["duplicates"] == 1 and project.files() == before


def test_merge_module_stays_free_of_geometry() -> None:
    tree = ast.parse(Path(preserve.__file__).read_text(encoding="utf-8"))
    modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not [m for m in modules if m.startswith("fenolite.geometry")]
