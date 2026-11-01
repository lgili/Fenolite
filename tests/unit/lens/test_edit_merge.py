# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The three-way merge of change c0250 (capability edit-merge): keys, the rule, takes and CAD sides."""

from __future__ import annotations

import ast
import itertools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _edit_help import base_of as _base
from _edit_help import edit as _edit
from _edit_help import issues as _issues
from _edit_help import value as _value
from _layout_edit import D1_SHIFT, add_to_footprint, edit_blink, edit_properties, move_footprint
from _project import Project, codes, footprint

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sch import read_schematic
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point
from fenolite.lens import edits as edits_mod
from fenolite.lens.edits import (
    PROPERTIES,
    BaseEntry,
    Edit,
    PropertyKey,
    Take,
    merge_property,
    parse_takes,
)

ROOT = Path(__file__).resolve().parents[3]
KEY = PropertyKey("R1", "value")
BASE = BaseEntry("330", "330")
NAMES = [
    "EDITS_SCHEMA", "EDITS_FILE", "BASE_SCHEMA", "BASE_FILE", "PROPERTIES", "PropertyKey", "BaseEntry",
    "BaseRecord", "read_base", "write_base", "PartEdits", "EditsFile", "read_edits", "write_edits",
    "Decision", "Conflict", "Take", "parse_takes", "merge_property", "merge_properties", "PropertyMerge",
    "capture_edits", "EDIT_ISSUE_CODES", "EVIDENCE",
]  # fmt: skip


def test_names() -> None:
    assert sorted(edits_mod.__all__) == sorted(NAMES)


def test_import_edges() -> None:
    tree = ast.parse((ROOT / "src/fenolite/lens/edits.py").read_text(encoding="utf-8"))
    imported = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    for banned in ("fenolite.geometry", "fenolite.dsl", "fenolite.lens.build", "fenolite.lens.preserve"):
        assert not any(name == banned or name.startswith(banned + ".") for name in imported), banned
    allowed = ("fenolite.core", "fenolite.model", "fenolite.backends", "fenolite.lens.placements")
    assert all(not name.startswith("fenolite") or name.startswith(allowed) for name in imported)


# --- keys -----------------------------------------------------------------------------------------


def test_key_text() -> None:
    assert str(PropertyKey("buck1/L", "property:Part number")) == "buck1/L#property:Part number"


def test_unknown_property_name_refused() -> None:
    with pytest.raises(ValueError) as raised:
        PropertyKey("R1", "colour")
    assert "colour" in str(raised.value) and all(name in str(raised.value) for name in PROPERTIES)


def test_key_order() -> None:
    keys = [
        PropertyKey("R1", "property:b"),
        PropertyKey("R1", "value"),
        PropertyKey("D1", "footprint"),
        PropertyKey("R1", "position"),
        PropertyKey("R1", "property:A"),
    ]
    assert [str(k) for k in sorted(keys, key=PropertyKey.sort_key)] == [
        "D1#footprint", "R1#position", "R1#value", "R1#property:A", "R1#property:b",
    ]  # fmt: skip


# --- the rule -------------------------------------------------------------------------------------


def test_cad_edit_kept() -> None:
    decision = merge_property(KEY, base=BASE, code="330", cad={"board": "4k7"})
    assert (decision.value, decision.source, decision.conflict) == ("4k7", "cad", None)
    assert decision.unrecorded


def test_code_change_written() -> None:
    decision = merge_property(KEY, base=BASE, code="470", cad={"board": "330"})
    assert (decision.value, decision.source, decision.wins) == ("470", "code", True)


def test_both_changed_to_different_values() -> None:
    decision = merge_property(KEY, base=BASE, code="470", cad={"board": "4k7"})
    assert decision.conflict is not None and decision.value == "4k7"
    conflict = decision.conflict
    assert (conflict.base, conflict.code, dict(conflict.cad), conflict.reason) == (
        "330",
        "470",
        {"board": "4k7"},
        "both-changed",
    )
    finding = conflict.finding()
    assert finding.code == "sync.conflict" and finding.severity == "error" and finding.where == "R1#value"
    assert "--take code:R1#value" in finding.hint and "--take cad:R1#value" in finding.hint


def test_record_of_a_conflict() -> None:
    conflict = merge_property(KEY, base=BASE, code="470", cad={"board": "4k7"}).conflict
    assert conflict is not None and conflict.cad == {"board": "4k7"} and conflict.reason == "both-changed"
    assert conflict.record() == {
        "key": "R1#value", "reason": "both-changed", "base": "330", "code": "470", "cad": {"board": "4k7"},
    }  # fmt: skip


def test_source_of_a_kept_edit() -> None:
    decision = merge_property(KEY, base=BASE, code="330", cad={"board": "330", "schematic": "4k7"})
    assert (decision.value, decision.source) == ("4k7", "schematic")


@pytest.mark.parametrize("take", [None, "code", "cad"])
@pytest.mark.parametrize("with_base", [True, False])
@pytest.mark.parametrize("code_changed", [True, False])
@pytest.mark.parametrize("cad_changed", [True, False])
@pytest.mark.parametrize("kind", ["value", "position"])
def test_table(take: str | None, with_base: bool, code_changed: bool, cad_changed: bool, kind: str) -> None:
    """Every combination of the table of "Three-way property merge", with and without a base and a take."""
    a, b, c = ("330", "470", "4k7") if kind == "value" else ((1, 1), (2, 2), (3, 3))
    key = PropertyKey("R1", kind)
    code = b if code_changed else a
    cad = c if cad_changed else a
    takes = parse_takes([f"{take}:R1"]) if take else ()
    decision = merge_property(
        key, base=BaseEntry(a, a) if with_base else None, code=code, cad={"board": cad}, takes=takes
    )
    if not with_base:
        expected = cad if kind == "position" else code
        assert (decision.value, decision.conflict) == (expected, None)
        assert decision.take is None
        return
    if code_changed and cad_changed:
        if take is None:
            assert decision.conflict is not None and decision.conflict.reason == "both-changed"
        else:
            assert decision.conflict is None and decision.source == "take"
            assert decision.value == (code if take == "code" else cad)
        return
    assert decision.conflict is None and decision.take is None
    assert decision.value == (code if code_changed else cad)


def test_shared_change_is_no_conflict() -> None:
    decision = merge_property(KEY, base=BASE, code="4k7", cad={"board": "4k7"})
    assert (decision.value, decision.conflict) == ("4k7", None)


def test_removed_request_keeps_the_cad_value() -> None:
    key = PropertyKey("R1", "position")
    decision = merge_property(key, base=BaseEntry((1, 1), (1, 1)), code=None, cad={"board": (5, 5)})
    assert decision.value == (5, 5) and decision.conflict is None
    decision = merge_property(key, base=BaseEntry((1, 1), (1, 1)), code=None, cad={"board": (1, 1)})
    assert decision.value == (1, 1)


def test_locked_request_wins() -> None:
    key = PropertyKey("U1", "position")
    decision = merge_property(
        key, base=BaseEntry((1, 1), (1, 1)), code=(1, 1), cad={"board": (2, 2)}, locked=True
    )
    assert (decision.value, decision.source, decision.conflict) == ((1, 1), "code", None)


def test_footprint_locked_in_kicad_is_not_moved_silently() -> None:
    key = PropertyKey("R1", "position")
    decision = merge_property(
        key, base=BaseEntry((1, 1), (1, 1)), code=(2, 2), cad={"board": (1, 1)}, cad_locked=True
    )
    assert decision.conflict is not None and decision.conflict.reason == "cad-locked"
    taken = merge_property(
        key,
        base=BaseEntry((1, 1), (1, 1)),
        code=(2, 2),
        cad={"board": (1, 1)},
        cad_locked=True,
        takes=parse_takes(["code"]),
    )
    assert taken.value == (2, 2) and taken.conflict is None


def test_without_cad_side_the_code_wins() -> None:
    decision = merge_property(KEY, base=BASE, code="470", cad={})
    assert (decision.value, decision.source) == ("470", "code")


def test_stale_edit() -> None:
    edit = Edit("4k7", "330")
    decision = merge_property(KEY, base=BaseEntry("4k7", "4k7"), code="470", cad={"board": "4k7"}, edit=edit)
    assert decision.conflict is not None and decision.conflict.reason == "stale-edit"
    assert decision.conflict.code == "470" and decision.conflict.cad == {"edits": "4k7"}
    finding = decision.conflict.finding()
    assert "edits.toml '4k7'" in finding.message and "stale-edit" in finding.message
    code = merge_property(
        KEY,
        base=BaseEntry("4k7", "4k7"),
        code="470",
        cad={"board": "4k7"},
        edit=edit,
        takes=parse_takes(["code:R1#value"]),
    )
    assert (code.value, code.source, code.conflict) == ("470", "code", None)
    cad = merge_property(
        KEY,
        base=BaseEntry("4k7", "4k7"),
        code="470",
        cad={"board": "4k7"},
        edit=edit,
        takes=parse_takes(["cad"]),
    )
    assert (cad.value, cad.conflict) == ("4k7", None)


def test_redundant_and_current_edits_apply() -> None:
    current = merge_property(KEY, base=None, code="330", cad={}, edit=Edit("4k7", "330"))
    assert (current.value, current.code, current.edited) == ("4k7", "4k7", True)
    redundant = merge_property(KEY, base=None, code="4k7", cad={}, edit=Edit("4k7", "330"))
    assert (redundant.value, redundant.conflict) == ("4k7", None)
    legacy = merge_property(
        PropertyKey("R1", "position"), base=None, code=(1, 1), cad={}, edit=Edit((2, 2), None, legacy=True)
    )
    assert legacy.value == (2, 2)


def test_recorded_edit_is_not_unrecorded() -> None:
    decision = merge_property(
        KEY, base=BaseEntry("330", "330"), code="330", cad={"board": "4k7"}, edit=Edit("4k7", "330")
    )
    assert decision.value == "4k7" and not decision.unrecorded and decision.conflict is None


def test_no_floats_and_hash_seed_independent() -> None:
    script = (
        "from fenolite.lens.edits import *\n"
        "from fenolite.lens.edits import Edit\n"
        "k = PropertyKey('R1', 'position')\n"
        "d = [merge_property(k, base=BaseEntry((1, 2), (1, 2)), code=c, cad={'board': b, 'schematic': b})"
        " for c, b in [((1, 2), (3, 4)), ((5, 6), (1, 2)), ((5, 6), (7, 8))]]\n"
        "print(repr(d))\n"
    )
    outputs = set()
    for seed in ("0", "1"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        run = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, env=env, check=True
        )
        assert "." not in run.stdout.replace("...", "")
        outputs.add(run.stdout)
    assert len(outputs) == 1


# --- takes ----------------------------------------------------------------------------------------


def test_take_grammar() -> None:
    assert parse_takes(["code", "cad:R1#value", "board:buck1/L", "cad:R1#value"]) == (
        Take("", "code"),
        Take("R1#value", "cad"),
        Take("buck1/L", "board"),
    )
    assert str(Take("R1#value", "cad")) == "cad:R1#value" and str(Take("", "code")) == "code"


@pytest.mark.parametrize("value", ["mine:R1", "code:", "code:R 1", "cad:R1#colour", "", "CODE"])
def test_malformed_take(value: str) -> None:
    with pytest.raises(ValueError) as raised:
        parse_takes([value])
    assert repr(value) in str(raised.value)


def test_contradictory_takes() -> None:
    with pytest.raises(ValueError, match="contradict"):
        parse_takes(["code:R1", "cad:R1"])


def test_take_specificity() -> None:
    takes = parse_takes(["code", "cad:R1", "code:R1#value"])
    value = merge_property(KEY, base=BASE, code="470", cad={"board": "4k7"}, takes=takes)
    assert value.value == "470" and value.take == Take("R1#value", "code")
    footprint = merge_property(
        PropertyKey("R1", "footprint"), base=BaseEntry("A", "A"), code="B", cad={"board": "C"}, takes=takes
    )
    assert footprint.value == "C" and footprint.take == Take("R1", "cad")
    other = merge_property(
        PropertyKey("D1", "value"), base=BaseEntry("A", "A"), code="B", cad={"board": "C"}, takes=takes
    )
    assert other.value == "B" and other.take == Take("", "code")


def test_a_take_never_changes_a_property_not_in_conflict() -> None:
    decision = merge_property(KEY, base=BASE, code="330", cad={"board": "4k7"}, takes=parse_takes(["code"]))
    assert decision.value == "4k7" and decision.take is None


# --- CAD sides ------------------------------------------------------------------------------------


def test_sides_agree() -> None:
    decision = merge_property(KEY, base=BASE, code="330", cad={"board": "4k7", "schematic": "4k7"})
    assert (decision.value, decision.conflict) == ("4k7", None)


def test_sides_disagree() -> None:
    decision = merge_property(KEY, base=BASE, code="330", cad={"board": "1k", "schematic": "4k7"})
    conflict = decision.conflict
    assert conflict is not None and conflict.reason == "sides-disagree"
    assert dict(conflict.cad) == {"board": "1k", "schematic": "4k7"}
    assert "--take board:R1#value" in conflict.finding().hint
    unresolved = merge_property(
        KEY, base=BASE, code="330", cad={"board": "1k", "schematic": "4k7"}, takes=parse_takes(["cad"])
    )
    assert unresolved.conflict is not None
    for side, value in (("board", "1k"), ("schematic", "4k7")):
        taken = merge_property(
            KEY, base=BASE, code="330", cad={"board": "1k", "schematic": "4k7"}, takes=parse_takes([side])
        )
        assert (taken.value, taken.conflict, taken.source) == (value, None, "take")


def test_only_the_schematic_changed() -> None:
    combos = list(itertools.product(["330", "4k7"], repeat=2))
    for board, schematic in combos:
        decision = merge_property(KEY, base=BASE, code="330", cad={"board": board, "schematic": schematic})
        if board != schematic:
            assert decision.value == "4k7" and decision.conflict is None


# --- builds (command level) -----------------------------------------------------------------------

MM = 1_000_000


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_build_writes_the_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    base = _base(p)
    assert base["R1"]["value"] == {"code": "330", "out": "330"}
    assert base["R1"]["position"] == {"code": [132 * MM, 109 * MM], "out": [132 * MM, 109 * MM]}
    assert base["D1"]["rotation"] == {"code": [0, "bottom"], "out": [0, "bottom"]}
    before = (p.out / "fenolite-base.json").read_bytes()
    code, env, _ = p.build("--confirm")
    assert code == 0 and (p.out / "fenolite-base.json").read_bytes() == before
    edits = env["result"]["preserved"]["edits"]  # type: ignore[index]
    assert edits == {"kept": [], "code": [], "taken": [], "unrecorded": [], "conflicts": []}
    assert "H-K-EDIT-SCH-VALUE" in env["evidence"]["hypotheses"]  # type: ignore[index]
    record = json.loads((p.out / ".fenolite/build.json").read_text(encoding="utf-8"))
    assert "fenolite-base.json" in record["files"]


def test_build_receipt_lists_the_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, env, _ = p.run("build", "--confirm", out=tmp_path / "C")
    assert code == 0
    written = [w["path"] for w in env["receipt"]["written"]]  # type: ignore[index, union-attr]
    assert str(tmp_path / "C" / "fenolite-base.json") in written


def test_build_staged_part_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_script("r1.place(mm(32), mm(9))\n", "")
    code, _, err = p.build("--confirm", "--discard-layout")
    assert code == 0, err
    position = _base(p)["R1"]["position"]
    assert position["code"] is None and position["out"] is not None


def test_build_value_kept_from_the_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"value": "4k7"}})
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert _value(p, "R1") == ("4k7", "4k7")
    circuit = json.loads((p.out / ".fenolite/circuit.json").read_text(encoding="utf-8"))
    assert any(c.get("value") == "4k7" for c in circuit["components"])
    assert [i["where"] for i in _issues(env, "edit.unrecorded")] == ["R1#value"]
    assert _base(p)["R1"]["value"] == {"code": "330", "out": "4k7"}
    edits = env["result"]["preserved"]["edits"]  # type: ignore[index]
    assert edits["kept"] == ["R1#value"] and edits["unrecorded"] == ["R1#value"]  # type: ignore[index]
    # rebuild is stable, and the edit is still reported as unrecorded
    before = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 0 and [i["where"] for i in _issues(env, "edit.unrecorded")] == ["R1#value"]
    after = p.files()
    assert {k: v for k, v in after.items() if not k.startswith(".fenolite")} == {
        k: v for k, v in before.items() if not k.startswith(".fenolite")
    }


def test_build_value_edited_in_the_schematic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"value": "4k7"}}, board=False, schematic=True)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert _value(p, "R1") == ("4k7", "4k7")
    assert [i["where"] for i in _issues(env, "edit.unrecorded")] == ["R1#value"]


def test_build_board_updated_from_the_schematic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"value": "4k7"}}, board=True, schematic=True)
    code, env, _ = p.build("--confirm")
    assert code == 0 and _value(p, "R1") == ("4k7", "4k7") and not _issues(env, "sync.conflict")


def test_build_sides_disagree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"value": "4k7"}}, board=False, schematic=True)
    _edit(p, {"R1": {"value": "1k"}})
    code, env, _ = p.build("--dry-run")
    (conflict,) = _issues(env, "sync.conflict")
    assert code == 5 and conflict["where"] == "R1#value" and "sides-disagree" in conflict["message"]
    assert "'1k'" in conflict["message"] and "'4k7'" in conflict["message"]
    code, env, _ = p.build("--take", "schematic:R1#value", "--confirm")
    assert code == 0 and _value(p, "R1") == ("4k7", "4k7")


def test_build_without_schematic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    out = tmp_path / "S"
    assert p.run("build", "--schematic", "skip", "--confirm", out=out)[0] == 0
    board = out / "blink.kicad_pcb"
    text, _ = edit_properties(board.read_text(encoding="utf-8"), None, {"R1": {"value": "4k7"}})
    assert text is not None
    board.write_text(text, encoding="utf-8")
    code, _, err = p.run("build", "--schematic", "skip", "--confirm", out=out)
    assert code == 0, err
    _, component = footprint(read_board(board.read_text(encoding="utf-8")), "R1")
    assert component.value == "4k7"  # type: ignore[attr-defined]
    assert not (out / "blink.kicad_sch").exists()


def test_build_without_a_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    (p.out / "fenolite-base.json").unlink()
    _edit(p, {"R1": {"value": "4k7"}})
    p.edit_board(edit_blink)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    fp, component = footprint(p.read(), "R1")
    assert component.value == "330"  # type: ignore[attr-defined]
    d1, _ = footprint(p.read(), "D1")
    assert d1.position.x == 138 * MM + D1_SHIFT  # type: ignore[attr-defined]
    assert len(_issues(env, "edit.base-missing")) == 1 and (p.out / "fenolite-base.json").is_file()
    assert not _issues(env, "edit.unrecorded")


def test_build_same_result_without_the_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"value": "4k7"}})
    clone = tmp_path / "clone"
    shutil.copytree(p.out, clone)
    shutil.rmtree(clone / ".fenolite")
    first = p.build("--dry-run")
    second = p.run("build", "--dry-run", out=clone)
    assert first[0] == second[0] == 0
    plans = [
        {
            Path(w["path"]).relative_to(folder).as_posix(): w["sha256"]
            for w in env["result"]["plan"]  # type: ignore[index, union-attr]
            if ".fenolite" not in Path(w["path"]).parts
        }
        for (_, env, _), folder in ((first, p.out), (second, clone))
    ]
    assert plans[0] == plans[1] and "fenolite-base.json" in plans[0]
    assert first[1]["result"]["preserved"]["edits"] == second[1]["result"]["preserved"]["edits"]  # type: ignore[index]


def test_build_base_edited_by_hand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    base = p.out / "fenolite-base.json"
    base.write_text(base.read_text(encoding="utf-8").replace('"330"', '"331"'), encoding="utf-8")
    code, env, err = p.build("--dry-run")
    assert code == 7
    assert "fenolite-base.json" in err


def test_build_changed_place_moves_an_unedited_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_script("r1.place(mm(32), mm(9))", "r1.place(mm(35), mm(9))")
    code, env, err = p.build("--confirm")
    assert code == 0, err
    fp, _ = footprint(p.read(), "R1")
    assert fp.position.x == 135 * MM  # type: ignore[attr-defined]
    assert [i["where"] for i in _issues(env, "edit.code-wins")] == ["R1#position"]
    assert not _issues(env, "layout.place-overridden")


def test_build_hand_move_and_script_move_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: move_footprint(t, "R1", 0, 2 * MM))
    p.edit_script("r1.place(mm(32), mm(9))", "r1.place(mm(35), mm(9))")
    before = p.files()
    code, env, _ = p.build("--confirm")
    (conflict,) = _issues(env, "sync.conflict")
    assert code == 5 and conflict["where"] == "R1#position" and p.files() == before


def test_build_rotation_in_the_script_merges_with_a_hand_move(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: move_footprint(t, "R1", 0, 2 * MM))
    p.edit_script("r1.place(mm(32), mm(9))", "r1.place(mm(32), mm(9), rot=90)")
    code, env, err = p.build("--confirm")
    assert code == 0, err
    fp, _ = footprint(p.read(), "R1")
    assert (fp.position.y, fp.rotation) == (111 * MM, 90_000_000) and not _issues(env, "sync.conflict")  # type: ignore[attr-defined]


def test_build_footprint_locked_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"locked": True}})
    p.edit_script("r1.place(mm(32), mm(9))", "r1.place(mm(35), mm(9))")
    code, env, _ = p.build("--dry-run")
    (conflict,) = _issues(env, "sync.conflict")
    assert code == 5 and conflict["where"] == "R1#position" and "cad-locked" in conflict["message"]


def test_build_place_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: move_footprint(t, "R1", 0, 2 * MM))
    p.edit_script("r1.place(mm(32), mm(9))\n", "")
    code, env, err = p.build("--confirm")
    assert code == 0, err
    fp, _ = footprint(p.read(), "R1")
    assert fp.position == Point(132 * MM, 111 * MM)  # type: ignore[attr-defined]
    assert not _issues(env, "layout.unplaced")


def test_build_footprint_changed_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"footprint": "Mini:Mini_LED_THT_3mm"}})
    code, env, err = p.build("--confirm", "--copper-check", "warn")
    assert code == 0, err
    fp, _ = footprint(p.read(), "R1")
    assert fp.lib_ref == "Mini:Mini_LED_THT_3mm"  # type: ignore[attr-defined]
    assert "R1" in env["result"]["preserved"]["kept"]  # type: ignore[index]
    assert not _issues(env, "layout.footprint-replaced")
    assert [i["where"] for i in _issues(env, "edit.unrecorded")] == ["R1#footprint"]


def test_build_unedited_rebuild_lists_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, env, _ = p.build("--dry-run")
    assert code == 0
    assert all(v == [] for v in env["result"]["preserved"]["edits"].values())  # type: ignore[index, union-attr]
    assert not [c for c in codes(env) if c.startswith(("edit.", "sync."))]


def test_build_renamed_part_keeps_its_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"value": "4k7"}})
    p.edit_script('r1 = Part("R1"', 'r1 = Part("R7"')
    p.edit_script("design.board(mm(50), mm(30))", 'design.board(mm(50), mm(30))\ndesign.moved("R1", "R7")')
    code, env, err = p.build("--confirm")
    assert code == 0, err
    _, component = footprint(p.read(), "R7")
    assert component.value == "4k7"  # type: ignore[attr-defined]
    assert not _issues(env, "sync.conflict") and not _issues(env, "edit.base-missing")


# --- merge_properties and the closed set ----------------------------------------------------------


def _fresh_with_base() -> tuple[str, str, edits_mod.BaseRecord]:
    from _buildhelp import blink, build

    out = build(blink(), 10, write_base=True)
    base = edits_mod.read_base(out.files["fenolite-base.json"].decode("utf-8"), target="kicad")
    return out.files["blink.kicad_pcb"].decode("utf-8"), out.files["blink.kicad_sch"].decode("utf-8"), base


def test_result_of_a_build() -> None:
    from _buildhelp import blink

    from fenolite.dsl import module_moves, moves, net_moves, placements, to_model
    from fenolite.lens.preserve import ExistingProject, prepare

    board, _, base = _fresh_with_base()
    board, _ = edit_properties(board, None, {"R1": {"value": "4k7"}})
    d = blink()
    d.parts["D1"].request = None
    d.parts["D1"].place("40mm", "20mm", side="bottom")
    ready = prepare(
        to_model(d), placements(d), ExistingProject(board=board), name="blink", moves=moves(d),
        module_moves=module_moves(d), net_moves=net_moves(d), edits={}, base=base,
    )  # fmt: skip
    sources = {str(decision.key): decision.source for decision in ready.decisions}
    assert sources["R1#value"] == "cad" and sources["D1#position"] == "code"
    assert ready.design is not None
    (r1,) = [c for c in ready.design.circuit.components if c.ref == "R1"]
    assert r1.value == "4k7"


def test_units_of_a_symbol_disagree() -> None:
    import dataclasses

    from _buildhelp import blink

    from fenolite.dsl import to_model
    from fenolite.lens.preserve import match_footprints

    board_text, sheet_text, base = _fresh_with_base()
    sheet = read_schematic(sheet_text, file="blink.kicad_sch")
    (u1,) = [s for s in sheet.symbols if s.ref == "U1"]
    second = dataclasses.replace(
        u1, id=u1.id + "-2", unit=2, value="X", properties={**u1.properties, "Value": "X"}
    )
    sheet = dataclasses.replace(sheet, symbols=(*sheet.symbols, second))
    model = to_model(blink())
    board = read_board(board_text)
    match = match_footprints(model, board)
    merged = edits_mod.merge_properties(
        model,
        board=board,
        sheets=[sheet],
        match={path: m.footprint for path, m in match.matches.items()},
        base=base,
        edits={},
    )
    (conflict,) = [i for i in merged.issues if i.code == "sync.conflict"]
    assert conflict.where == "U1#value" and "sides-disagree" in conflict.message


def test_evidence() -> None:
    from fenolite.core.evidence import Level

    assert edits_mod.EVIDENCE.level is Level.INFERRED
    assert edits_mod.EVIDENCE.hypotheses == ("H-K-LENS-KEEP", "H-K-SCH-UPDATE", "H-K-EDIT-SCH-VALUE")


def test_closed_set() -> None:
    import re

    table = {
        "sync.conflict": "error", "edit.take-unused": "warning", "edit.legacy-file": "warning",
        "edit.base-invalid": "warning", "edit.unrecorded": "info", "edit.code-wins": "info",
        "edit.base-missing": "info",
    }  # fmt: skip
    assert dict(edits_mod.EDIT_ISSUE_CODES) == table
    tests = [
        Path(__file__),
        ROOT / "tests/unit/lens/test_base_record.py",
        ROOT / "tests/unit/lens/test_preserve_place.py",
        ROOT / "tests/unit/cli/test_build_command.py",
        ROOT / "tests/unit/cli/test_build_take.py",
    ]
    produced: set[str] = set()
    for path in tests:
        produced |= set(re.findall(r'"((?:edit\.[a-z-]+)|sync\.conflict)"', path.read_text(encoding="utf-8")))
    assert produced == set(table)


# --- capture (sync) -------------------------------------------------------------------------------


def _capture(
    board_text: str,
    base: edits_mod.BaseRecord | None,
    held: dict[str, edits_mod.PartEdits] | None = None,
    design: object = None,
) -> edits_mod.EditsFile:
    from _buildhelp import blink

    from fenolite.dsl import BOARD_ORIGIN, placements, to_model
    from fenolite.lens.extract import extract_placements
    from fenolite.lens.preserve import match_footprints

    d = design or blink()
    model = to_model(d)  # type: ignore[arg-type]
    board = read_board(board_text)
    match = match_footprints(model, board)
    extracted = extract_placements(board, match, design=model)
    return edits_mod.capture_edits(
        model,
        board=board,
        sheets=None,
        match={path: m.footprint for path, m in match.matches.items()},
        base=base,
        edits=held or {},
        origin=BOARD_ORIGIN,
        requests=placements(d),  # type: ignore[arg-type]
        off_board=frozenset(extracted.unplaced),
    )


def test_capture_only_differences() -> None:
    board, _, base = _fresh_with_base()
    found = _capture(edit_blink(board), base)
    assert list(found.parts) == ["D1"] and found.captured == ("D1#position",)
    assert set(found.parts["D1"].values) == {"position"}
    assert found.parts["D1"].over == {"position": (138 * MM, 120 * MM)}


def test_capture_removed_edit() -> None:
    from types import MappingProxyType

    from _buildhelp import BLINK_DIR, blink, resolver

    from fenolite.dsl import placements, to_model
    from fenolite.lens.build import build_design
    from fenolite.lens.preserve import ExistingProject, prepare

    held = {"R1": edits_mod.PartEdits(MappingProxyType({"value": "4k7"}), MappingProxyType({"value": "330"}))}
    d = blink()
    ready = prepare(to_model(d), placements(d), ExistingProject(), name="blink", edits=held)
    assert ready.design is not None
    out = build_design(
        ready.design, ready.placements, name="blink", copper=2, resolver=resolver(10, BLINK_DIR, None, None),
        prepared=ready, write_base=True,
    )  # fmt: skip
    base = edits_mod.read_base(out.files["fenolite-base.json"].decode("utf-8"), target="kicad")
    assert base.parts["R1"]["value"] == edits_mod.BaseEntry("4k7", "4k7")
    text = out.files["blink.kicad_pcb"].decode("utf-8")
    back, _ = edit_properties(text, None, {"R1": {"value": "330"}})
    assert back is not None
    found = _capture(back, base, held)
    assert "R1" not in found.parts


def test_capture_staged_part() -> None:
    from _buildhelp import blink, build

    d = blink()
    d.parts["R1"].request = None
    out = build(d, 10, write_base=True)
    base = edits_mod.read_base(out.files["fenolite-base.json"].decode("utf-8"), target="kicad")
    found = _capture(out.files["blink.kicad_pcb"].decode("utf-8"), base, design=d)
    assert "R1" not in found.parts


def test_capture_without_a_base() -> None:
    board, _, _ = _fresh_with_base()
    edited, _ = edit_properties(edit_blink(board), None, {"R1": {"value": "4k7"}})
    assert edited is not None
    found = _capture(edited, None)
    assert list(found.parts) == ["D1"] and "R1" in found.no_base and found.issues == ()


def test_capture_keeps_edits_of_parts_not_on_the_board() -> None:
    from types import MappingProxyType

    from _buildhelp import blink

    from fenolite.dsl import Part

    board, _, base = _fresh_with_base()
    d = blink()
    d.add(Part("R9", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k"))
    held = {"R9": edits_mod.PartEdits(MappingProxyType({"value": "2k"}), MappingProxyType({"value": "1k"}))}
    found = _capture(board, base, held, design=d)
    assert found.parts["R9"] == held["R9"]


def test_capture_conflict_gives_no_edit() -> None:
    from _buildhelp import blink

    board, _, base = _fresh_with_base()
    edited, _ = edit_properties(edit_blink(board), None, {"R1": {"value": "4k7"}})
    assert edited is not None
    d = blink()
    d.parts["R1"].value = "470"
    found = _capture(edited, base, design=d)
    assert found.parts == {} and [i.code for i in found.issues] == ["sync.conflict"]


def test_docs() -> None:
    page = (ROOT / "docs/lens.md").read_text(encoding="utf-8")
    for heading in ("Three-way merge", "The base record", "edits.toml", "Conflicts and --take"):
        assert f"\n## {heading}\n" in page, heading
    assert "\n## From placements.toml to edits.toml\n" in page
    assert "There is no stored base" not in page
    assert "committed with the output folder" in page and "| changed | changed, different |" in page
    contract = (ROOT / "docs/cli-contract.md").read_text(encoding="utf-8")
    assert "--take" in contract and "edits.toml" in contract


# --- references and user properties (phase 2) ----------------------------------------------------


def _edits_text(p: Project) -> str:
    return (p.script.parent / "edits.toml").read_text(encoding="utf-8")


def _stable(p: Project) -> None:
    """A rebuild writes every file with the bytes of the build before it."""
    before = p.files()
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert not _issues(env, "sync.conflict") and p.files() == before


def test_reference_reannotated_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"reference": "R7"}}, schematic=True)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    fp, component = footprint(p.read(), "R7")
    assert component.properties["fenolite.path"] == "R1"  # type: ignore[attr-defined]
    sheet = read_schematic(p.out / "blink.kicad_sch")
    assert [
        s.properties["Reference"] for s in sheet.symbols if s.properties.get("fenolite.path") == "R1"
    ] == ["R7"]
    assert [i["where"] for i in _issues(env, "edit.unrecorded")] == ["R1#reference"]
    assert _base(p)["R1"]["reference"] == {"code": "R1", "out": "R7"}
    code, env, err = p.run("sync", "--to-source", "--confirm")
    assert code == 0, err
    text = _edits_text(p)
    assert '[part."R1"]\nreference = "R7"\n' in text and '[part."R1".over]\nreference = "R1"\n' in text
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert footprint(p.read(), "R7") and not _issues(env, "edit.unrecorded")
    _stable(p)


def test_reference_edit_given_in_the_edits_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    (p.script.parent / "edits.toml").write_text(
        '# Written by fenolite sync --to-source.\nschema = "fenolite.edits.v0"\n\n'
        '[part."R1"]\nreference = "R9"\n\n[part."R1".over]\nreference = "R1"\n',
        encoding="utf-8",
    )
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert footprint(p.read(), "R9") and _base(p)["R1"]["reference"] == {"code": "R9", "out": "R9"}
    # the script changes the ref under the edit, the path staying R1: a stale edit
    p.edit_script('Part("R1", "Mini:Mini_R"', 'Part("R2", "Mini:Mini_R", name="R1"')
    code, env, _ = p.build("--dry-run")
    (conflict,) = _issues(env, "sync.conflict")
    assert code == 5 and conflict["where"] == "R1#reference" and "stale-edit" in conflict["message"]
    code, _, err = p.build("--take", "code:R1#reference", "--confirm")
    assert code == 0, err
    assert footprint(p.read(), "R2")


def test_reference_duplicate_is_the_build_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    (p.script.parent / "edits.toml").write_text(
        '# Written by fenolite sync --to-source.\nschema = "fenolite.edits.v0"\n\n'
        '[part."R1"]\nreference = "D1"\n\n[part."R1".over]\nreference = "R1"\n',
        encoding="utf-8",
    )
    before = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 5 and "model.duplicate-ref" in codes(env) and p.files() == before


def test_reference_edit_is_a_hand_ref_of_the_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch, folder="examples/lock", name="lock_demo")
    lock = p.script.with_suffix(".lock")
    # the board only: the symbols of the modules are in child sheets, which KiCad updates from the board
    board_text, _ = edit_properties(p.board.read_text(encoding="utf-8"), None, {"R1": {"reference": "R7"}})
    p.board.write_text(board_text or "", encoding="utf-8")
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert [i["where"] for i in _issues(env, "edit.unrecorded")] == ["led/R#reference"]
    assert '"led/R" = "R1"' in lock.read_text(encoding="utf-8")
    code, _, err = p.run("sync", "--to-source", "--confirm")
    assert code == 0, err
    assert 'reference = "R7"' in _edits_text(p)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert '"led/R" = "R7"' in lock.read_text(encoding="utf-8") and footprint(p.read(), "R7")
    # the lock now holds the ref, so the next sync drops the edit and the build keeps it
    code, _, err = p.run("sync", "--to-source", "--confirm")
    assert code == 0, err
    assert "reference" not in _edits_text(p)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert footprint(p.read(), "R7") and not _issues(env, "edit.unrecorded")
    _stable(p)


PN = 'value="330", properties={"Part number": "PN-330"}'


def _with_property(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    p = Project(tmp_path, monkeypatch)
    p.edit_script('value="330"', PN)
    code, _, err = p.build("--confirm")
    assert code == 0, err
    assert _base(p)["R1"]["property:Part number"] == {"code": "PN-330", "out": "PN-330"}
    return p


def _board_property(p: Project, ref: str, name: str) -> str | None:
    _, component = footprint(p.read(), ref)
    return component.properties.get(name)  # type: ignore[attr-defined, no-any-return]


def test_user_property_edited_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _with_property(tmp_path, monkeypatch)
    _edit(p, {"R1": {"properties": {"Part number": "PN-470"}}})
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert _board_property(p, "R1", "Part number") == "PN-470"
    assert [i["where"] for i in _issues(env, "edit.unrecorded")] == ["R1#property:Part number"]
    code, _, err = p.run("sync", "--to-source", "--confirm")
    assert code == 0, err
    assert 'properties = { "Part number" = "PN-470" }' in _edits_text(p)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert _board_property(p, "R1", "Part number") == "PN-470" and not _issues(env, "edit.unrecorded")
    _stable(p)


def test_user_property_changed_on_both_sides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _with_property(tmp_path, monkeypatch)
    _edit(p, {"R1": {"properties": {"Part number": "PN-470"}}})
    p.edit_script("PN-330", "PN-1K")
    code, env, _ = p.build("--dry-run")
    (conflict,) = _issues(env, "sync.conflict")
    assert code == 5 and conflict["where"] == "R1#property:Part number"
    code, _, err = p.build("--take", "code:R1#property:Part number", "--confirm")
    assert code == 0, err
    assert _board_property(p, "R1", "Part number") == "PN-1K"


def test_user_property_removed_in_kicad_counts_as_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _with_property(tmp_path, monkeypatch)
    root = parse(p.board.read_text(encoding="utf-8"))
    children: list[Node | Atom] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "footprint" and '"Part number"' in dumps(child):
            child = child.with_children(
                [
                    c
                    for c in child.children
                    if not (
                        isinstance(c, Node) and c.name == "property" and c.atoms()[0].value == "Part number"
                    )
                ]
            )
        children.append(child)
    p.board.write_text(dumps(root.with_children(children), style="kicad"), encoding="utf-8")
    code, env, err = p.build("--confirm", "--schematic", "skip")
    assert code == 0, err
    assert _board_property(p, "R1", "Part number") in (None, "")
    assert [i["where"] for i in _issues(env, "edit.unrecorded")] == ["R1#property:Part number"]
    assert _base(p)["R1"]["property:Part number"]["out"] == ""


def test_user_property_added_in_kicad_stays_opaque(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(
        lambda text: add_to_footprint(
            text, "R1", '(property "Supplier" "ACME" (at 0 0 0) (layer "F.Fab") (hide yes))'
        )
    )
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert _board_property(p, "R1", "Supplier") == "ACME"
    assert "property:Supplier" not in _base(p)["R1"] and not _issues(env, "edit.unrecorded")
