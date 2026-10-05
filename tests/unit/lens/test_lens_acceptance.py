# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The lens acceptance (capability layout-lens, "Lens acceptance fixture"; change c0069): five footprints
moved and three tracks routed "in KiCad", then a part added and a module renamed with ``moved()``, and
everything is preserved. The stand-in for *Update PCB from Schematic* joins when the schematic writer
(c0061) exists."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest
from _layout_edit import MM, footprint_node, group_members, node_uuid
from _lensfix import (
    FIELD_REF,
    FOLDER,
    GROUP,
    GROUPED,
    MOVES,
    NAME,
    PATHS,
    TRACKS,
    drop_alias,
    edit_board,
    edit_script,
    renamed,
)
from _project import Project, codes

from fenolite.backends.kicad.embed import placement_uuid
from fenolite.backends.kicad.sexpr import Node, first_difference
from fenolite.core.coords import Point
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import Module
from fenolite.lens.preserve import footprint_uuid
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
LOST = {"layout.orphan", "layout.net-removed", "layout.footprint-replaced", "zone.fill-stale"}


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def placement(design: Design, ref: str) -> tuple[Point, int, str, bool]:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    (fp,) = [f for f in design.board.footprints if refs[f.component_id] == ref]
    return fp.position, fp.rotation, fp.side, fp.locked


def tracks(design: Design) -> dict[str, tuple[Point, Point, int, str, str | None]]:
    assert design.board is not None
    names = {n.id: n.name for n in design.circuit.nets}
    return {
        t.native_ids["kicad"]: (t.start, t.end, t.width, t.layer, names.get(t.net_id or ""))
        for t in design.board.tracks
    }


def reference_node(text: str, ref: str) -> tuple[int, Node]:
    props = footprint_node(text, ref).nodes("property")
    return next((i, n) for i, n in enumerate(props) if n.atoms()[0].value == "Reference")


def without_uuid(node: Node) -> Node:
    return node.with_children([c for c in node.children if not (isinstance(c, Node) and c.name == "uuid")])


def test_fixture_shape() -> None:
    d = runpy.run_path(str(ROOT / FOLDER / "design.py"))["design"]
    assert isinstance(d, DslDesign) and d.name == NAME
    assert sorted(d.parts) == sorted(PATHS.values()) and all(p.request is not None for p in d.parts.values())
    assert {m.path for m in d.modules.values() if isinstance(m, Module)} == {"power", "io"}
    for module in ("power", "io"):
        assert sum(1 for path in d.parts if path.startswith(f"{module}/")) >= 3
    assert {"power/FB", "power/LED_A", "io/LED_A", "io/SENSE", "VIN", "GND", "DRV"} == set(d.nets)
    assert sum(1 for ref in MOVES if PATHS[ref].startswith("power/")) == 3 and len(set(MOVES.values())) == 5


@pytest.mark.parametrize("target", [9, 10])
def test_rename_keeps_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int) -> None:
    p = Project(tmp_path, monkeypatch, target, folder=FOLDER, name=NAME)
    built = p.read()
    p.edit_board(edit_board)
    edited_text = p.board.read_text(encoding="utf-8")
    edited = p.read()
    for ref, (dx, dy) in MOVES.items():
        at = placement(built, ref)[0]
        assert placement(edited, ref)[0] == Point(at.x + dx, at.y + dy)
    assert set(tracks(edited)) == {uuid for uuid, *_ in TRACKS}
    # the script edits: a part added, a module renamed through moved()
    p.script.write_text(edit_script(p.script.read_text(encoding="utf-8")), encoding="utf-8")
    code, env, err = p.build("--confirm")
    assert code == 0, err
    text = p.board.read_text(encoding="utf-8")
    rebuilt = p.read()
    # every footprint is where the edited board had it
    for ref in PATHS:
        assert placement(rebuilt, ref) == placement(edited, ref), ref
    # the three tracks keep uuid, ends, width and layer, each on its net under the new name
    was, now = tracks(edited), tracks(rebuilt)
    assert set(now) == set(was)
    for uuid, net, _, _ in TRACKS:
        assert now[uuid][:4] == was[uuid][:4] and was[uuid][4] == net and now[uuid][4] == renamed(net)
    assert now[TRACKS[0][0]][4] == "supply/FB"
    # the moved Reference property is the edited node under the new identity
    index, kept = reference_node(text, FIELD_REF)
    _, moved = reference_node(edited_text, FIELD_REF)
    assert first_difference(without_uuid(kept), without_uuid(moved)) is None
    new_path = renamed(PATHS[FIELD_REF])
    assert node_uuid(kept) == placement_uuid(new_path, f"/footprint/property[{index}]")
    # the group lists the two renamed footprints by their new uuids
    assert group_members(text, GROUP) == [footprint_uuid(renamed(PATHS[ref])) for ref in GROUPED]
    assert group_members(edited_text, GROUP) == [footprint_uuid(PATHS[ref]) for ref in GROUPED]
    # the new part is staged, and nothing was lost
    assert [i["where"] for i in env["issues"] if i["code"] == "layout.unplaced"] == ["io/R9"]  # type: ignore[union-attr,index]
    assert not LOST & set(codes(env)), codes(env)
    preserved = env["result"]["preserved"]  # type: ignore[index]
    assert preserved["kept"] == sorted(renamed(path) for path in PATHS.values())  # type: ignore[index]
    assert preserved["replaced"] == [] and preserved["added"] == ["io/R9"]  # type: ignore[index]
    assert preserved["module_aliases"] == {"supply": "power"}  # type: ignore[index]
    assert preserved["net_aliases"] == {"supply/FB": "power/FB", "supply/LED_A": "power/LED_A"}  # type: ignore[index]
    assert preserved["dropped"] == {"tracks": 0, "arcs": 0, "vias": 0, "zones": 0}  # type: ignore[index]
    # normal form: without the moved() call the next build writes the same bytes
    p.script.write_text(drop_alias(p.script.read_text(encoding="utf-8")), encoding="utf-8")
    first = p.files()
    code, env, err = p.build("--confirm")
    assert code == 0 and p.files() == first, err
    assert not {"layout.alias-used", "layout.alias-unused", "layout.net-alias-used"} & set(codes(env))


@pytest.mark.parametrize("target", [9, 10])
def test_layout_restored_from_the_source_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
) -> None:
    p = Project(tmp_path, monkeypatch, target, folder=FOLDER, name=NAME)
    p.edit_board(edit_board)
    p.script.write_text(edit_script(p.script.read_text(encoding="utf-8")), encoding="utf-8")
    assert p.build("--confirm")[0] == 0
    rebuilt = p.read()
    code, env, err = p.run("sync", "--to-source", "--confirm")
    assert code == 0, err
    source = p.script.parent / "placements.toml"
    assert source.is_file() and env["result"]["placements"] == len(PATHS)  # type: ignore[index]
    assert env["result"]["unplaced"] == ["io/R9"]  # type: ignore[index]
    empty = tmp_path / "restored"
    code, env, err = p.run("build", "--discard-layout", "--confirm", out=empty)
    assert code == 0, err
    p.out = empty
    restored = p.read()
    for ref in PATHS:
        assert placement(restored, ref) == placement(rebuilt, ref), ref
    assert [i["where"] for i in env["issues"] if i["code"] == "layout.unplaced"] == ["io/R9"]  # type: ignore[union-attr,index]
    assert restored.board is not None and not restored.board.tracks
    used = env["result"]["preserved"]["source"]["used"]  # type: ignore[index]
    assert used == sorted(renamed(path) for path in PATHS.values() if path != "U1")


def test_offsets_are_distinct_and_small() -> None:
    assert all(abs(dx) <= 2 * MM and abs(dy) <= 2 * MM for dx, dy in MOVES.values())
