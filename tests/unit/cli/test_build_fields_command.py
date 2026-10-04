# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Field placements through ``fenolite build`` (capabilities design-dsl, "Field placements in a build", and
layout-lens, "Footprint fields across rebuilds"; change c0030). Each test builds a blink variant into
``tmp_path``, edits the result as KiCad would (by token edit), and builds again in-process."""

from __future__ import annotations

import io
import json
import shutil
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.embed import placement_uuid
from fenolite.backends.kicad.fields import field_angle, place_outside
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.model.board import FootprintField, FootprintInstance
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
LIBS = ROOT / "tests" / "data" / "libs"
MM = 1_000_000
ABOVE = '\nr1.field("Reference", outside="top")\n'


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


class Project:
    """A blink copy with its libraries and ``append`` added to its script; ``build`` runs the command."""

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        target: int = 10,
        *,
        append: str = "",
        out: str = "B",
    ) -> None:
        self.monkeypatch = monkeypatch
        self.target = target
        root = tmp_path / "repo"
        if not root.is_dir():
            shutil.copytree(BLINK_DIR, root / "examples" / "blink_2layer")
            shutil.copytree(LIBS, root / "tests" / "data" / "libs")
        self.folder = root / "examples" / "blink_2layer"
        self.script = self.folder / "design.py"
        if append:
            self.script.write_text(self.script.read_text(encoding="utf-8") + append, encoding="utf-8")
        self.out = tmp_path / out

    def build(self, *flags: str) -> tuple[int, dict[str, object], dict[str, object]]:
        out, err = io.StringIO(), io.StringIO()
        self.monkeypatch.setattr("sys.stdout", out)
        self.monkeypatch.setattr("sys.stderr", err)
        args = ["--kicad-version", str(self.target), "build", str(self.script), "--out", str(self.out)]
        code = cli_main.main([*args, *flags, "--json"])
        return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")

    def confirm(self) -> dict[str, object]:
        code, env, err = self.build("--confirm")
        assert code == 0, err
        return env

    @property
    def board(self) -> Path:
        return self.out / "blink.kicad_pcb"

    def edit_board(self, change: Callable[[str], str]) -> None:
        self.board.write_text(change(self.board.read_text(encoding="utf-8")), encoding="utf-8")

    def edit_script(self, old: str, new: str) -> None:
        text = self.script.read_text(encoding="utf-8")
        assert old in text, old
        self.script.write_text(text.replace(old, new), encoding="utf-8")

    def read(self) -> Design:
        return read_board(self.board)

    def files(self) -> dict[str, bytes]:
        return {
            str(p.relative_to(self.out)): p.read_bytes()
            for p in sorted(self.out.rglob("*"))
            if p.is_file() and p.suffix != ".bak"
        }


def footprint(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    target = design.by_ref[ref].id
    return next(fp for fp in design.board.footprints if fp.component_id == target)


def field(fp: FootprintInstance, name: str) -> FootprintField:
    return next(f for f in fp.fields if f.name == name)


def edit_property(text: str, ref: str, name: str, change: Callable[[Node], Node]) -> str:
    """The board text with the property ``name`` of footprint ``ref`` replaced by ``change(node)``."""
    root = parse(text)
    done = 0
    children: list[Node | object] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "footprint":
            props = child.nodes("property")
            if any(p.atoms()[0].value == "Reference" and p.atoms()[1].value == ref for p in props):
                parts: list[object] = []
                for part in child.children:
                    if isinstance(part, Node) and part.name == "property" and part.atoms()[0].value == name:
                        part = change(part)
                        done += 1
                    parts.append(part)
                child = child.with_children(parts)  # type: ignore[arg-type]
        children.append(child)
    assert done == 1, (ref, name, done)
    return dumps(root.with_children(children), style="kicad")  # type: ignore[arg-type]


def move_at(dx_mm: int) -> Callable[[Node], Node]:
    """A token edit of a property's ``at``: X moved by a whole number of millimetres."""

    def change(node: Node) -> Node:
        at = node.find("at")
        assert at is not None
        x, y, angle = (a.text for a in at.atoms())
        moved = parse(f"(at {format(Decimal(x) + dx_mm, 'f')} {y} {angle})")
        return node.with_children([moved if c is at else c for c in node.children])

    return change


def without_hide(node: Node) -> Node:
    return node.with_children([c for c in node.children if not (isinstance(c, Node) and c.name == "hide")])


def property_node(text: str, ref: str, name: str) -> Node:
    found: list[Node] = []
    edit_property(text, ref, name, lambda node: (found.append(node), node)[1])
    return found[0]


# --- task 8.1: "Field placements in a build" ------------------------------------------------------


def test_reference_above_a_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, 10, append=ABOVE)
    env = project.confirm()
    assert not [i for i in env["issues"] if i["severity"] == "error"]  # type: ignore[index, union-attr]
    r1 = footprint(project.read(), "R1")
    reference = field(r1, "Reference")
    assert field_angle(r1, reference) == 0
    assert (reference.h_justify, reference.v_justify) == ("center", "bottom")
    assert place_outside(r1, "Reference", side="top") == r1


def test_hidden_value_of_a_bottom_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, 9, append='\nd1.field("Value", visible=False, layer="silk")\n')
    project.confirm()
    value = field(footprint(project.read(), "D1"), "Value")
    assert (value.visible, value.layer, value.mirrored) == (False, "B.SilkS", True)


def test_library_without_the_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, 10)
    variant = tmp_path / "V"
    library = variant / "NoValue.pretty"
    library.mkdir(parents=True)
    source = parse((LIBS / "Mini_v9.pretty" / "Mini_R_0603.kicad_mod").read_text(encoding="utf-8"))
    kept = [
        c
        for c in source.children
        if not (isinstance(c, Node) and c.name == "property" and c.atoms()[0].value == "Value")
    ]
    assert len(kept) == len(source.children) - 1
    (library / "NoValue_R.kicad_mod").write_text(
        dumps(source.with_children(kept), style="kicad").replace('"Mini_R_0603"', '"NoValue_R"', 1), "utf-8"
    )
    row = '\t(lib (name "{}") (type "KiCad") (uri "{}") (options "") (descr ""))\n'
    tables = {
        "fp-lib-table": ("fp_lib_table", {"Mini": LIBS / "Mini_v9.pretty", "NoValue": library}),
        "sym-lib-table": ("sym_lib_table", {"Mini": LIBS / "Mini_v9.kicad_sym"}),
    }
    for name, (head, rows) in tables.items():
        body = "".join(row.format(nick, path.as_posix()) for nick, path in rows.items())
        (variant / name).write_text(f"({head}\n\t(version 7)\n{body})\n", encoding="utf-8")
    text = project.script.read_text(encoding="utf-8")
    old = 'footprint="Mini:Mini_R_0603"'
    assert old in text
    script = variant / "design.py"
    script.write_text(
        text.replace(old, 'footprint="NoValue:NoValue_R"') + '\nr1.field("Value", visible=False)\n', "utf-8"
    )
    project.script = script
    code, _, err = project.build("--dry-run")
    assert code == 3 and err["code"] == "FEN-3004"
    assert "NoValue:NoValue_R" in str(err["message"]) and "Value" in str(err["message"])
    assert not project.out.exists()
    # the same script without the request builds: only the request needs the field
    script.write_text(
        script.read_text(encoding="utf-8").replace('r1.field("Value", visible=False)', ""), "utf-8"
    )
    code, _, err = project.build("--dry-run")
    assert code == 0, err


def test_bad_request_is_a_script_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, 10, append='\nr1.field("MPN", visible=False)\n')
    code, _, err = project.build("--dry-run")
    assert code == 3 and err["code"] == "FEN-3004" and "MPN" in str(err["message"])


def test_reproducible_field_placement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = Project(tmp_path, monkeypatch, 10, append=ABOVE, out="B1")
    first.confirm()
    second = Project(tmp_path, monkeypatch, 10, out="B2")
    second.confirm()
    assert first.files() == second.files() and first.files()


# --- task 9.1: "Footprint fields across rebuilds" -------------------------------------------------

EMPTY = {"kept": [], "forced": [], "carried": []}


def outcome(env: dict[str, object]) -> dict[str, list[str]]:
    return env["result"]["preserved"]["fields"]  # type: ignore[index, return-value]


def edited_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int = 10) -> tuple[Project, Node]:
    """A confirmed build with the unlocked request, whose ``R1`` Reference is then moved 1 mm in the board."""
    project = Project(tmp_path, monkeypatch, target, append=ABOVE)
    assert outcome(project.confirm()) == EMPTY
    project.edit_board(lambda text: edit_property(text, "R1", "Reference", move_at(1)))
    return project, property_node(project.board.read_text(encoding="utf-8"), "R1", "Reference")


def test_fresh_build_reports_empty_lists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, 10, append=ABOVE)
    code, env, _ = project.build("--dry-run")
    assert code == 0 and outcome(env) == EMPTY
    assert env["result"]["preserved"]["board"] is False  # type: ignore[index]


def test_a_gui_edit_wins_over_an_unlocked_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, edited = edited_project(tmp_path, monkeypatch)
    env = project.confirm()
    text = project.board.read_text(encoding="utf-8")
    assert property_node(text, "R1", "Reference") == edited
    assert outcome(env) == {"kept": ["R1:Reference"], "forced": [], "carried": []}
    assert "R1" in env["result"]["preserved"]["kept"]  # type: ignore[index]
    # the next rebuild says the same and writes the same bytes
    first = project.files()
    assert outcome(project.confirm()) == {"kept": ["R1:Reference"], "forced": [], "carried": []}
    assert project.files() == first


def test_a_locked_request_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, edited = edited_project(tmp_path, monkeypatch)
    project.edit_script('outside="top")', 'outside="top", locked=True)')
    env = project.confirm()
    assert outcome(env) == {"kept": [], "forced": ["R1:Reference"], "carried": []}
    r1 = footprint(project.read(), "R1")
    assert place_outside(r1, "Reference", side="top") == r1
    node = property_node(project.board.read_text(encoding="utf-8"), "R1", "Reference")
    assert node != edited and node.find("uuid") == edited.find("uuid")
    # once forced, the board agrees with the request: the next rebuild is quiet and stable
    first = project.files()
    assert outcome(project.confirm()) == EMPTY and project.files() == first


def test_fields_follow_a_forced_move(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = edited_project(tmp_path, monkeypatch)
    before = footprint(project.read(), "R1")
    project.edit_script("r1.place(mm(32), mm(9))", "r1.place(mm(34), mm(9), locked=True)")
    env = project.confirm()
    assert "layout.place-forced" in [i["code"] for i in env["issues"]]  # type: ignore[index, union-attr]
    assert "R1" in env["result"]["preserved"]["replaced"]  # type: ignore[index]
    r1 = footprint(project.read(), "R1")
    assert r1.position.x == before.position.x + 2 * MM and r1.position.y == before.position.y
    old, new = field(before, "Reference"), field(r1, "Reference")
    assert (new.position, new.rotation) == (old.position, old.rotation)
    assert (new.h_justify, new.v_justify) == (old.h_justify, old.v_justify)
    assert outcome(env) == {"kept": ["R1:Reference"], "forced": [], "carried": ["R1:Reference"]}


def test_a_side_change_takes_the_library_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = edited_project(tmp_path, monkeypatch)
    project.edit_script("r1.place(mm(32), mm(9))", 'r1.place(mm(32), mm(9), side="bottom", locked=True)')
    env = project.confirm()
    r1 = footprint(project.read(), "R1")
    reference = field(r1, "Reference")
    assert r1.side == "bottom" and reference.layer == "B.SilkS" and reference.mirrored
    assert place_outside(r1, "Reference", side="top") == r1  # the built copy's field, request applied
    assert outcome(env)["carried"] == [] and outcome(env)["forced"] == []


@pytest.mark.parametrize("target", [9, 10])
def test_rebuilds_of_an_unedited_board_are_quiet_and_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
) -> None:
    project = Project(tmp_path, monkeypatch, target, append=ABOVE)
    project.confirm()
    first = project.files()
    for _ in range(2):
        assert outcome(project.confirm()) == EMPTY
        assert project.files() == first
    shutil.rmtree(project.out / ".fenolite")
    project.confirm()
    assert project.files() == first


def test_gui_edit_of_a_field_without_a_request_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = Project(tmp_path, monkeypatch, 10)
    project.confirm()
    project.edit_board(lambda text: edit_property(text, "D1", "Value", move_at(-2)))
    edited = property_node(project.board.read_text(encoding="utf-8"), "D1", "Value")
    env = project.confirm()
    assert property_node(project.board.read_text(encoding="utf-8"), "D1", "Value") == edited
    assert outcome(env) == EMPTY


# --- task 9.2: c0019's user-property rule on fields ------------------------------------------------


def test_user_property_on_a_kept_footprint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, 10)
    project.edit_script('value="330")', 'value="330", properties={"Part number": "PN-330"})')
    project.confirm()

    def edit(text: str) -> str:
        return edit_property(text, "R1", "Part number", lambda node: without_hide(move_at(1)(node)))

    project.edit_board(edit)
    before = footprint(project.read(), "R1")
    old = field(before, "Part number")
    assert old.visible and old.position.x == MM
    project.edit_script('{"Part number": "PN-330"}', '{"Part number": "PN-470", "Supplier code": "S-1"}')
    env = project.confirm()
    assert "R1" in env["result"]["preserved"]["kept"]  # type: ignore[index]
    assert outcome(env) == EMPTY
    design = project.read()
    r1 = footprint(design, "R1")
    part_number = field(r1, "Part number")
    assert (part_number.position, part_number.visible) == (old.position, True)
    assert part_number.native_ids == old.native_ids
    assert design.by_ref["R1"].properties["Part number"] == "PN-470"
    assert design.by_ref["R1"].properties["Supplier code"] == "S-1"
    supplier = r1.fields[-1]
    assert supplier.name == "Supplier code" and not supplier.visible
    assert supplier.native_ids == {"kicad": placement_uuid("R1", "/footprint/property:Supplier code")}
    assert [f.name for f in r1.fields[:-1]] == [f.name for f in before.fields]
    # the rebuild is the normal form: nothing changes again
    first = project.files()
    assert outcome(project.confirm()) == EMPTY and project.files() == first
