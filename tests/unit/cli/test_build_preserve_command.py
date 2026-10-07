# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout preservation through ``fenolite build`` (capability layout-lens, command-level scenarios, and the
c0019 scenarios of design-dsl; change c0019). Each test builds the blink into ``tmp_path``, edits the
result as KiCad would (by token edit), and builds again in-process."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest
from _board_only import add_h1
from _layout_edit import (
    D1_SHIFT,
    EDIT_UUIDS,
    ZONE_UUID,
    add_filled_zone,
    edit_blink,
    move_footprint,
)
from _project import COPPER_WARN, Project, codes, footprint, node_of, prop_node

import fenolite.cli.main as cli_main
from fenolite.backends.kicad import _json
from fenolite.backends.kicad.dru import read_rules
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.lens.preserve import footprint_uuid
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
MM = 1_000_000


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


# --- Existing project files ------------------------------------------------------------------------


def test_discarding_the_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    fresh = p.board.read_bytes()
    p.edit_board(edit_blink)
    edited = p.board.read_bytes()
    code, _, _ = p.build("--discard-layout", "--confirm")
    assert code == 0 and p.board.read_bytes() == fresh
    assert (p.out / "blink.kicad_pcb.bak").read_bytes() == edited


def test_board_of_major_10_built_for_target_9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    before = p.files()
    p.target = 9
    code, _, err = p.build("--dry-run")
    assert code == 7 and json.loads(err)["code"] == "FEN-7002" and p.files() == before


def test_broken_rules_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    rules = p.out / "blink.kicad_dru"
    lines = rules.read_text(encoding="utf-8").split("\n")
    lines.insert(2, "(rule 'big one' (constraint clearance (min 1mm)))")
    rules.write_text("\n".join(lines), encoding="utf-8")
    code, _, err = p.build("--dry-run")
    error = json.loads(err)
    assert code == 3 and error["code"] == "FEN-3004"
    assert "blink.kicad_dru" in error["where"] and "3" in error["where"]


# --- Placement precedence --------------------------------------------------------------------------


def test_the_board_wins_over_place(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    placed, _ = footprint(p.read(), "D1")
    p.edit_board(edit_blink)
    code, env, _ = p.build("--confirm")
    moved, _ = footprint(p.read(), "D1")
    assert code == 0 and moved.position.x == placed.position.x + D1_SHIFT  # type: ignore[attr-defined]
    assert [i["where"] for i in env["issues"] if i["code"] == "layout.place-overridden"] == ["D1"]  # type: ignore[index, union-attr]


def test_a_locked_place_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    placed, _ = footprint(p.read(), "U1")
    p.edit_board(lambda t: move_footprint(t, "U1", 0, 2 * MM))
    code, env, _ = p.build("--confirm")
    back, _ = footprint(p.read(), "U1")
    assert code == 0 and back.position == placed.position and back.locked  # type: ignore[attr-defined]
    assert "layout.place-forced" in codes(env)


def test_a_staged_part_placed_by_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project.__new__(Project)
    p.monkeypatch, p.target = monkeypatch, 10
    root = tmp_path / "repo"
    shutil.copytree(BLINK_DIR, root / "examples" / "blink_2layer")
    shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
    p.script, p.out = root / "examples" / "blink_2layer" / "design.py", tmp_path / "B"
    p.edit_script("r1.place(mm(32), mm(9))\n", "")
    assert p.build("--confirm")[0] == 0
    staged = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 0 and p.files() == staged and codes(env).count("layout.unplaced") == 1
    p.edit_script("d1.place(", "r1.place(mm(20), mm(10))\nd1.place(")
    code, env, _ = p.build("--confirm")
    r1, _ = footprint(p.read(), "R1")
    assert code == 0 and (r1.position.x, r1.position.y) == (120 * MM, 110 * MM)  # type: ignore[attr-defined]
    assert "layout.unplaced" not in codes(env)


# --- Kept and re-placed footprints -----------------------------------------------------------------


def _move_reference(text: str) -> str:
    """``R1``'s Reference property moved 1 mm by token edit."""
    root = parse(text)
    out = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "footprint" and '"Reference" "R1"' in dumps(child):
            kids = []
            for kid in child.children:
                if isinstance(kid, Node) and kid.name == "property" and kid.atoms()[0].value == "Reference":
                    kid = kid.with_children(
                        [
                            parse(f"(at {c.atoms()[0].value} {float(c.atoms()[1].value) + 1:g})")
                            if isinstance(c, Node) and c.name == "at"
                            else c
                            for c in kid.children
                        ]
                    )
                kids.append(kid)
            child = child.with_children(kids)
        out.append(child)
    return dumps(root.with_children(out), style="kicad")


def test_silkscreen_edit_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: _move_reference(edit_blink(t)))
    edited = prop_node(p.board.read_text(encoding="utf-8"), "R1", "Reference")
    code, env, _ = p.build("--confirm")
    assert code == 0 and prop_node(p.board.read_text(encoding="utf-8"), "R1", "Reference") == edited
    assert "R1" in env["result"]["preserved"]["kept"]  # type: ignore[index]


def test_value_changed_in_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: _move_reference(edit_blink(t)))
    edited = prop_node(p.board.read_text(encoding="utf-8"), "R1", "Value")
    p.edit_script('value="330"', 'value="4k7"')
    assert p.build("--confirm")[0] == 0
    value = prop_node(p.board.read_text(encoding="utf-8"), "R1", "Value")
    assert value.atoms()[1].value == "4k7"
    assert value.children[2:] == edited.children[2:]


def test_user_property_changed_in_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project.__new__(Project)
    p.monkeypatch, p.target = monkeypatch, 10
    root = tmp_path / "repo"
    shutil.copytree(BLINK_DIR, root / "examples" / "blink_2layer")
    shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
    p.script, p.out = root / "examples" / "blink_2layer" / "design.py", tmp_path / "B"
    p.edit_script('value="330")', 'value="330", properties={"Part number": "PN-330"})')
    assert p.build("--confirm")[0] == 0
    p.edit_board(_move_reference)
    text = p.board.read_text(encoding="utf-8")
    edited_ref, old_pn = prop_node(text, "R1", "Reference"), prop_node(text, "R1", "Part number")
    p.edit_script('{"Part number": "PN-330"}', '{"Part number": "PN-470", "Supplier code": "S-1"}')
    code, env, _ = p.build("--confirm")
    text = p.board.read_text(encoding="utf-8")
    assert code == 0 and "R1" in env["result"]["preserved"]["kept"]  # type: ignore[index]
    assert prop_node(text, "R1", "Reference") == edited_ref
    pn = prop_node(text, "R1", "Part number")
    assert (
        pn.atoms()[1].value == "PN-470"
        and pn.find("uuid") == old_pn.find("uuid")
        and pn.find("at") == old_pn.find("at")
    )
    names = [n.atoms()[0].value for n in node_of(text, "R1").nodes("property")]
    assert names.index("Supplier code") == names.index("Part number") + 1
    _, r1 = footprint(p.read(), "R1")
    assert r1.properties["Part number"] == "PN-470" and r1.properties["Supplier code"] == "S-1"  # type: ignore[attr-defined]


def _add_note(text: str) -> str:
    root = parse(text)
    out = []
    note = parse(
        '(property "Note" "hand" (at 0 0 0) (layer "F.Fab") (hide yes) '
        '(uuid "00000000-0000-4000-8000-00000000a0e1") (effects (font (size 1 1) (thickness 0.15))))'
    )
    for child in root.children:
        if isinstance(child, Node) and child.name == "footprint" and '"Reference" "R1"' in dumps(child):
            kids = list(child.children)
            last = max(i for i, c in enumerate(kids) if isinstance(c, Node) and c.name == "property")
            kids.insert(last + 1, note)
            child = child.with_children(kids)
        out.append(child)
    return dumps(root.with_children(out), style="kicad")


def test_property_added_in_kicad_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(_add_note)
    assert p.build("--confirm")[0] == 0
    first = p.files()
    assert p.build("--confirm")[0] == 0
    assert prop_node(p.board.read_text(encoding="utf-8"), "R1", "Note") is not None and p.files() == first


def test_footprint_changed_in_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    before, _ = footprint(p.read(), "R1")
    p.edit_script('footprint="Mini:Mini_R_0603"', 'footprint="Mini:Mini_LED_THT_3mm"')
    code, env, _ = p.build(*COPPER_WARN, "--confirm")
    after, _ = footprint(p.read(), "R1")
    assert code == 0 and after.lib_ref == "Mini:Mini_LED_THT_3mm"  # type: ignore[attr-defined]
    assert (after.position, after.rotation, after.side) == (before.position, before.rotation, before.side)  # type: ignore[attr-defined]
    assert [i["where"] for i in env["issues"] if i["code"] == "layout.footprint-replaced"] == ["R1"]  # type: ignore[index, union-attr]


def test_rename_through_an_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    old, _ = footprint(p.read(), "R1")
    p.edit_script('Part("R1"', 'Part("R7"')
    p.edit_script("design.add(u1, r1, d1)", 'design.add(u1, r1, d1)\ndesign.moved("R1", "R7")')
    code, env, _ = p.build("--confirm")
    new, comp = footprint(p.read(), "R7")
    assert code == 0 and "layout.alias-used" in codes(env)
    assert new.position == old.position and new.native_ids["kicad"] == footprint_uuid("R7")  # type: ignore[attr-defined]
    assert comp.properties["fenolite.path"] == "R7"  # type: ignore[attr-defined]
    p.edit_script('design.moved("R1", "R7")', "")
    first = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 0 and p.files() == first and "layout.alias-unused" not in codes(env)


def test_unknown_new_path_at_build_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_script("design.add(u1, r1, d1)", 'design.add(u1, r1, d1)\ndesign.moved("R0", "R9")')
    code, _, err = p.build("--dry-run")
    error = json.loads(err)
    assert code == 3 and error["code"] == "FEN-3004" and "R9" in error["message"]


# --- Orphan and board-only footprints --------------------------------------------------------------

REMOVE_R1 = (
    ('r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")\n', ""),
    ("design.add(u1, r1, d1)", "design.add(u1, d1)"),
    ("connect(led_drv, u1[1], r1[1])", "connect(led_drv, u1[1])"),
    ("connect(led_a, r1[2], d1[2])", "connect(led_a, d1[2])"),
    ("r1.place(mm(32), mm(9))\n", ""),
)


def test_removed_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    for old, new in REMOVE_R1:
        p.edit_script(old, new)
    code, env, _ = p.build("--confirm")
    design = p.read()
    assert code == 0 and "R1" not in {c.ref for c in design.circuit.components}
    assert [i["where"] for i in env["issues"] if i["code"] == "layout.orphan"] == ["R1"]  # type: ignore[index, union-attr]


def test_footprint_added_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: add_h1()(edit_blink(t)))
    code, env, err = p.build("--confirm")
    assert code == 0, err
    first = p.files()
    design = p.read()
    fp, comp = footprint(design, "H1")
    nets = {n.id: n.name for n in design.circuit.nets}
    pads = {pad.number: nets.get(pad.net_id or "") for pad in fp.pads}  # type: ignore[attr-defined]
    assert pads == {"1": "GND", "2": None} and "layout.board-only" in codes(env)
    cache = json.loads((p.out / ".fenolite" / "circuit.json").read_text())
    (gnd,) = [n for n in cache["nets"] if n["name"] == "GND"]
    assert {"component_id": comp.id, "pin": "1"} in gnd["members"]  # type: ignore[attr-defined]
    assert not any({"component_id": comp.id, "pin": "2"} in n["members"] for n in cache["nets"])  # type: ignore[attr-defined]
    assert p.build("--confirm")[0] == 0 and p.files() == first


def test_board_only_reference_collides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: add_h1("R1")(edit_blink(t)))
    before = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 5 and "model.duplicate-ref" in codes(env) and p.files() == before


# --- Copper items follow their nets ----------------------------------------------------------------


def test_tracks_intact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch, target=9)
    p.edit_board(edit_blink)
    edited = p.read()
    assert p.build("--confirm")[0] == 0
    rebuilt = p.read()

    def items(design: Design) -> set[tuple[object, ...]]:
        assert design.board is not None
        nets = {n.id: n.name for n in design.circuit.nets}
        return {
            (t.native_ids["kicad"], t.start, t.end, t.width, t.layer, nets[t.net_id or ""])
            for t in design.board.tracks
        } | {(v.native_ids["kicad"], v.position, v.diameter, nets[v.net_id or ""]) for v in design.board.vias}

    assert items(rebuilt) == items(edited) and {i[0] for i in items(rebuilt)} == set(EDIT_UUIDS)


def test_net_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    p.edit_script("connect(led_a, r1[2], d1[2])", "")
    code, env, _ = p.build("--confirm")
    design = p.read()
    assert code == 0 and design.board is not None and not design.board.tracks and not design.board.vias
    (found,) = [i for i in env["issues"] if i["code"] == "layout.net-removed"]  # type: ignore[union-attr]
    assert "LED_A" in found["message"] and "2 tracks" in found["message"] and "1 vias" in found["message"]


# --- Board content outside the design is kept ------------------------------------------------------


def test_board_setup_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    text = p.board.read_text(encoding="utf-8")
    assert "(pad_to_mask_clearance 0)" in text
    p.board.write_text(
        text.replace("(pad_to_mask_clearance 0)", "(pad_to_mask_clearance 0.05)"), encoding="utf-8"
    )
    edited = [c for c in parse(p.board.read_text()).children if isinstance(c, Node) and c.name == "setup"]
    assert p.build("--confirm")[0] == 0
    assert [
        c for c in parse(p.board.read_text()).children if isinstance(c, Node) and c.name == "setup"
    ] == edited


def test_outline_edited_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    text = p.board.read_text(encoding="utf-8")
    edited = (
        text.replace("(start 150 100)\n\t\t(end 150 130)", "(start 155 100)\n\t\t(end 155 130)")
        .replace("(start 100 100)\n\t\t(end 150 100)", "(start 100 100)\n\t\t(end 155 100)")
        .replace("(start 150 130)\n\t\t(end 100 130)", "(start 155 130)\n\t\t(end 100 130)")
    )
    assert edited.count("155") == 4, "the edge lines changed form"
    p.board.write_text(edited, encoding="utf-8")
    code, env, _ = p.build("--confirm")
    edges = [c for c in parse(p.board.read_text()).children if isinstance(c, Node) and c.name == "gr_line"]
    assert code == 0 and "layout.outline-kept" in codes(env) and sum("155" in dumps(e) for e in edges) == 3


def test_copper_count_changed_in_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    before = p.files()
    p.edit_script("design.board(mm(50), mm(30))", "design.board(mm(50), mm(30), copper=4)")
    code, env, _ = p.build("--confirm")
    assert code == 5 and "layout.copper-mismatch" in codes(env) and p.files() == before


# --- Zone fills and the staleness digest -----------------------------------------------------------


def _filled(p: Project) -> None:
    p.edit_board(lambda t: add_filled_zone(t, net="GND", layer="B.Cu"))


def _fills(p: Project) -> int:
    design = p.read()
    assert design.board is not None
    (zone,) = [z for z in design.board.zones if z.native_ids["kicad"] == ZONE_UUID]
    return len(zone.fills)


def test_unchanged_rebuild_keeps_fills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _filled(p)
    code, env, _ = p.build(*COPPER_WARN, "--confirm")
    assert code == 0 and _fills(p) == 2 and "zone.fill-stale" not in codes(env)


def test_a_removed_part_drops_fills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _filled(p)
    for old, new in REMOVE_R1:
        p.edit_script(old, new)
    code, env, _ = p.build("--confirm")
    assert code == 0 and _fills(p) == 0 and "zone.fill-stale" in codes(env)


def test_a_class_change_drops_fills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _filled(p)
    p.edit_script("clearance=mm(0.2)", "clearance=mm(0.3)")
    code, env, _ = p.build(*COPPER_WARN, "--confirm")
    assert code == 0 and _fills(p) == 0 and "zone.fill-stale" in codes(env)


# --- Project and rules files are merged ------------------------------------------------------------


def test_user_rule_kept_after_fenolites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    rules = p.out / "blink.kicad_dru"
    lines = rules.read_text(encoding="utf-8").split("\n")
    lines[1:1] = ["# kept by hand", "(rule user_gap (constraint clearance (min 0.3mm)))"]
    rules.write_text("\n".join(lines), encoding="utf-8")
    assert p.build(*COPPER_WARN, "--confirm")[0] == 0
    first = rules.read_text(encoding="utf-8")
    assert p.build(*COPPER_WARN, "--confirm")[0] == 0 and rules.read_text(encoding="utf-8") == first
    assert first.startswith("(version 1)\n") and first.index("# kept by hand") < first.index("user_gap")
    (user,) = [r for r in read_rules(first).rules if r.name == "user_gap"]
    assert user.priority == 1


def test_ten_only_user_rule_for_target_9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch, target=9)
    rules = p.out / "blink.kicad_dru"
    rules.write_text(
        rules.read_text(encoding="utf-8") + "(rule mask (constraint bridged_mask))\n", encoding="utf-8"
    )
    code, env, err = p.build("--confirm")
    assert code == 7 and json.loads(err)["code"] == "FEN-7001" and "kicad.token.too-new" in codes(env)
    code, env, _ = p.build("--allow-lossy", "--confirm")
    assert code == 0 and "rules.dropped-for-target" in codes(env) and "bridged_mask" not in rules.read_text()


def test_user_class_kept_in_the_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    project = p.out / "blink.kicad_pro"
    data = _json.loads(project.read_text(encoding="utf-8"))
    classes = data["net_settings"]["classes"]
    user = dict(classes[0])
    user["name"] = "USER"
    classes.append(user)
    project.write_text(_json.dumps(data), encoding="utf-8")
    assert p.build("--confirm")[0] == 0
    written = _json.loads(project.read_text(encoding="utf-8"))
    names = {c["name"]: c for c in written["net_settings"]["classes"]}
    assert "USER" in names and names["PWR"]["clearance"] == _json.JsonNumber("0.2")


# --- Issue codes, evidence -------------------------------------------------------------------------


def test_warnings_do_not_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    for old, new in REMOVE_R1:
        p.edit_script(old, new)
    code, env, _ = p.build("--confirm")
    assert code == 0 and "layout.orphan" in codes(env)


def test_envelope_over_an_existing_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, env, _ = p.build("--dry-run")
    evidence, preserved = env["evidence"], env["result"]["preserved"]  # type: ignore[index]
    assert code == 0 and evidence["level"] == "INFERRED" and "H-K-LENS-KEEP" in evidence["hypotheses"]  # type: ignore[index]
    assert "H-K-PCB-READ" in evidence["hypotheses"] and preserved["board"] is True  # type: ignore[index]
    assert set(preserved) == {  # type: ignore[arg-type]
        "board", "kept", "replaced", "added", "orphans", "board_only", "dropped", "fills", "aliases",
        "reader_infos", "fields", "pad_zones", "module_aliases", "net_aliases", "source",
    }  # fmt: skip
    assert preserved["source"] == {"file": None, "used": [], "stale": [], "unknown": []}  # type: ignore[index]  # c0069
    assert preserved["module_aliases"] == {} and preserved["net_aliases"] == {}  # type: ignore[index]
    assert preserved["fields"] == {"kept": [], "forced": [], "carried": []}  # type: ignore[index]  # c0030
    assert preserved["pad_zones"] == {"kept": [], "forced": []}  # type: ignore[index]  # c0068


def test_fresh_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    shutil.rmtree(p.out)
    code, env, _ = p.build("--dry-run")
    assert code == 0 and "H-K-LENS-KEEP" not in env["evidence"]["hypotheses"]  # type: ignore[index]
    assert env["result"]["preserved"]["board"] is False  # type: ignore[index]


def test_rules_merge_adds_dru_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, env, _ = p.build("--dry-run")
    assert code == 0 and "H-K-DRU-DIALECT" in env["evidence"]["hypotheses"]  # type: ignore[index]


def test_rebuilt_blink_with_a_mounting_hole_added_in_kicad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """verification-loop, MODIFIED "Model validation stage": ``check`` asks a board-only footprint for no
    symbol."""
    p = Project(tmp_path, monkeypatch)
    p.edit_board(add_h1())
    assert p.build("--confirm")[0] == 0
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    stages = "model.validate,roundtrip"
    code = cli_main.main(["check", str(p.out), "--stages", stages, "--json"])
    env = json.loads(out.getvalue())
    assert code == 0, err.getvalue()
    assert not [i for i in env["issues"] if i["severity"] == "error"]
    assert "check.symbol-unresolved" not in codes(env)


# --- Layer count across rebuilds (change c0100, layout-lens "Layer count across rebuilds") -----------

BOARD_LINE = "design.board(mm(50), mm(30))"


def _layers_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, copper: int, extra: str = "") -> Project:
    """The blink built on ``copper`` layers: the script is changed and the board created on the new count."""
    p = Project(tmp_path, monkeypatch)
    p.edit_script(BOARD_LINE, f"design.board(mm(50), mm(30), copper={copper})")
    if extra:
        p.script.write_text(p.script.read_text(encoding="utf-8") + extra, encoding="utf-8")
    code, _, err = p.build("--discard-layout", "--no-backup", "--confirm")
    assert code == 0, err
    return p


def _add_layers(p: Project, after: str, *rows: str) -> None:
    """Rows added to the layer table right after the row ``after``, as KiCad's board setup adds layers."""
    text = p.board.read_text(encoding="utf-8")
    anchor = f"\t\t{after}\n"
    assert text.count(anchor) == 1, after
    added = "".join(f"\t\t{row}\n" for row in rows)
    p.board.write_text(text.replace(anchor, anchor + added), encoding="utf-8")


def _copper(p: Project) -> list[str]:
    board = p.read().board
    assert board is not None
    return [layer.name for layer in board.layers if layer.kind == "copper"]


def _mismatch(env: dict[str, object]) -> dict[str, str]:
    (found,) = [i for i in env["issues"] if i["code"] == "layout.copper-mismatch"]  # type: ignore[union-attr, index]
    return found  # type: ignore[return-value]


def test_six_layers_rebuilt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Six layers rebuilt"."""
    p = _layers_project(tmp_path, monkeypatch, 6, '\ndesign.zone(gnd, layers=("In4.Cu",))\n')
    assert _copper(p) == ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]
    before = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 0 and env["result"]["preserved"]["board"] is True  # type: ignore[index]
    assert p.files() == before


def test_layers_added_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Layers added in KiCad": the six-layer script keeps the layout of the edited board."""
    p = _layers_project(tmp_path, monkeypatch, 4)
    _add_layers(p, '(6 "In2.Cu" signal)', '(8 "In3.Cu" signal)', '(10 "In4.Cu" signal)')
    p.edit_script("copper=4", "copper=6")
    code, env, _ = p.build("--confirm")
    assert code == 0
    assert {"D1", "R1", "U1"} <= set(env["result"]["preserved"]["kept"])  # type: ignore[index]
    assert _copper(p) == ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]


def test_mismatch_names_the_boards_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Mismatch names the board's count"."""
    p = _layers_project(tmp_path, monkeypatch, 4)
    _add_layers(p, '(6 "In2.Cu" signal)', '(8 "In3.Cu" signal)', '(10 "In4.Cu" signal)')
    before = p.files()
    code, env, _ = p.build("--confirm")
    found = _mismatch(env)
    assert code == 5 and found["severity"] == "error" and p.files() == before
    assert "has 6 copper layers" in found["message"] and "declares 4" in found["message"]
    assert "In4.Cu" in found["message"]
    assert "copper=6" in found["hint"] and "--discard-layout" in found["hint"]


def test_table_that_fenolite_does_not_create(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Table that Fenolite does not create": ten layers have no ``copper=`` to name."""
    p = _layers_project(tmp_path, monkeypatch, 8)
    _add_layers(p, '(14 "In6.Cu" signal)', '(16 "In7.Cu" signal)', '(18 "In8.Cu" signal)')
    before = p.files()
    code, env, _ = p.build("--confirm")
    found = _mismatch(env)
    assert code == 5 and p.files() == before
    assert "has 10 copper layers" in found["message"] and "declares 8" in found["message"]
    assert "--discard-layout" in found["hint"] and "copper=" not in found["hint"]


def test_fewer_layers_on_the_board_names_both_ways(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A two-layer board and a four-layer script: the hint names the board's count and the flag."""
    p = Project(tmp_path, monkeypatch)
    p.edit_script(BOARD_LINE, "design.board(mm(50), mm(30), copper=4)")
    code, env, _ = p.build("--confirm")
    found = _mismatch(env)
    assert code == 5 and "has 2 copper layers" in found["message"] and "declares 4" in found["message"]
    assert "copper=2" in found["hint"] and "--discard-layout" in found["hint"]
