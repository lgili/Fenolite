# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A design that names only catalog lib ids builds into a project that ``check`` accepts, with no KiCad
library and no external tool (capabilities fenolite-component-catalog, "Catalog-only design passes
check", and layout-lens, "Kept footprints gain missing mandatory fields"; change c0077)."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from _catalog_design import FOOTPRINTS, NAME, REFS, VALUES, catalog_blink, write_script

import fenolite.cli.main as cli_main
from fenolite.backends.kicad import embed
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.checks.assignment_compare import PairResult, board_netlist, compare, model_netlist
from fenolite.dsl import Design as DslDesign
from fenolite.model import canonical
from fenolite.model.board import FootprintField, FootprintInstance
from fenolite.model.design import Design

MANDATORY = ("Reference", "Value")
Envelope = dict[str, object]


@pytest.fixture(autouse=True)
def hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No library table, no KiCad library and no child process: the catalog needs none of them."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a child process was started: {args!r}")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, Envelope, Envelope]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        code = cli_main.main([*args, "--json"])
    return code, json.loads(stdout.getvalue() or "{}"), json.loads(stderr.getvalue() or "{}")


def build(
    monkeypatch: pytest.MonkeyPatch, script: Path, out: Path, *flags: str, target: int = 10
) -> tuple[int, Envelope, Envelope]:
    return run(monkeypatch, "--kicad-version", str(target), "build", str(script), "--out", str(out), *flags)


def confirm(monkeypatch: pytest.MonkeyPatch, script: Path, out: Path, target: int = 10) -> Envelope:
    code, env, err = build(monkeypatch, script, out, "--confirm", target=target)
    assert code == 0, err
    return env


def codes(env: Envelope) -> list[str]:
    return sorted(i["code"] for i in env["issues"])  # type: ignore[union-attr, index]


def board_path(out: Path) -> Path:
    return out / f"{NAME}.kicad_pcb"


def footprints(design: Design) -> dict[str, FootprintInstance]:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    return {refs[fp.component_id]: fp for fp in design.board.footprints}


def field(fp: FootprintInstance, name: str) -> FootprintField:
    (found,) = [f for f in fp.fields if f.name == name]
    return found


def netlists(out: Path) -> tuple[PairResult, Design]:
    """The comparison of the model the build recorded with the board read back, and that board."""
    model = canonical.load_dir(out / ".fenolite")
    board = read_board(board_path(out))
    return compare(model_netlist(model), board_netlist(board)[0]), board


def changed(env: Envelope, out: Path) -> list[str]:
    """The planned files whose bytes differ from the file under ``out`` (or that ``out`` lacks)."""
    plan = env["result"]["plan"]  # type: ignore[index]
    assert plan
    return [
        Path(p["path"]).relative_to(out).as_posix()
        for p in plan
        if not Path(p["path"]).is_file()
        or hashlib.sha256(Path(p["path"]).read_bytes()).hexdigest() != p["sha256"]
    ]


def edit_footprints(out: Path, change: Callable[[str, Node], Node | None]) -> int:
    """A token edit of the board: ``change(path, property)`` gives the property to write, or ``None`` to
    remove it; ``path`` is the footprint's ``fenolite.path``. Returns the number of properties changed."""
    root = parse(board_path(out).read_text(encoding="utf-8"))
    done = 0
    children: list[Node | Atom] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "footprint":
            (path,) = [
                p.atoms()[1].value for p in child.nodes("property") if p.atoms()[0].value == "fenolite.path"
            ]
            parts: list[Node | Atom] = []
            for part in child.children:
                if isinstance(part, Node) and part.name == "property":
                    new = change(path, part)
                    done += new is not part
                    if new is None:
                        continue
                    part = new
                parts.append(part)
            child = child.with_children(parts)
        children.append(child)
    board_path(out).write_text(dumps(root.with_children(children), style="kicad"), encoding="utf-8")
    return done


def layout(design: Design) -> dict[str, object]:
    """What a rebuild must keep: each footprint's place and pad nets, and every track."""
    assert design.board is not None
    nets = {n.id: n.name for n in design.circuit.nets}
    found: dict[str, object] = {
        ref: (
            fp.position,
            fp.rotation,
            fp.side,
            tuple((p.number, nets.get(p.net_id or "", "")) for p in fp.pads),
        )
        for ref, fp in footprints(design).items()
    }
    found["tracks"] = sorted(
        (t.start.x, t.start.y, t.end.x, t.end.y, t.width, t.layer, nets.get(t.net_id or "", ""))
        for t in design.board.tracks
    )
    return found


# --- the fixture ------------------------------------------------------------------------------------


def test_the_catalog_blink_names_only_catalog_ids() -> None:
    design = catalog_blink()
    assert isinstance(design, DslDesign) and design.name == NAME
    parts = {part.ref: part for part in design.parts.values()}
    assert tuple(sorted(parts)) == REFS
    assert {ref: part.footprint for ref, part in parts.items()} == FOOTPRINTS
    assert all(part.lib_id.startswith("Fenolite:") for part in parts.values())
    assert sorted(design.nets) == ["GND", "LED_A", "VIN"]


# --- acceptance: the nets of the script equal the nets of the board ---------------------------------


@pytest.mark.parametrize("target", [9, 10])
def test_nets_of_the_script_and_of_the_board_agree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
) -> None:
    script = write_script(tmp_path / "P")
    assert not (tmp_path / "P" / "fp-lib-table").exists()
    out = tmp_path / "out"
    env = confirm(monkeypatch, script, out, target)
    libraries = env["result"]["libraries"]  # type: ignore[index]
    assert set(libraries.values()) == {"builtin"} and len(libraries) == 6
    assert "build.field-added" not in codes(env) and "layout.unplaced" not in codes(env)
    code, checked, err = run(
        monkeypatch, "check", str(out), "--stages", "model.validate,copper.clearance"
    )  # fmt: skip
    assert code == 0, (err, checked.get("issues"))
    stages = {s["name"]: s["status"] for s in checked["result"]["stages"]}  # type: ignore[index]
    assert stages["model.validate"] == "ok" and stages["copper.clearance"] == "ok"
    pair, board = netlists(out)
    assert (pair.common, pair.only_a, pair.only_b, pair.differences) == (6, (), (), ())
    assert tuple(sorted(c.ref for c in board.circuit.components)) == REFS
    assert {c.ref: c.value for c in board.circuit.components} == VALUES
    for ref, fp in footprints(board).items():
        assert [f.name for f in fp.fields][:2] == list(MANDATORY), ref
    for footprint in FOOTPRINTS.values():
        name = footprint.split(":")[1]
        text = (out / "lib" / "Fenolite.pretty" / f"{name}.kicad_mod").read_text(encoding="utf-8")
        assert '(property "Reference" "REF**"' in text and f'(property "Value" "{name}"' in text


def test_a_regression_is_caught(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = write_script(tmp_path / "P")
    out = tmp_path / "out"
    with monkeypatch.context() as patch:
        # prepared definitions get no field, and a placement adds none: the state before c0077
        patch.setattr(embed, "default_fields", lambda defn: ())
        confirm(monkeypatch, script, out)
    pair, board = netlists(out)
    assert [c.ref for c in board.circuit.components] == ["", "", ""]
    assert pair.differences or pair.only_a or pair.only_b
    assert pair.common < 6


# --- the second backend ------------------------------------------------------------------------------


def test_altium_documents_are_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = write_script(tmp_path / "P")
    out = tmp_path / "A"

    def plan() -> tuple[list[tuple[str, str]], list[str]]:
        code, env, err = run(
            monkeypatch, "build", str(script), "--out", str(out), "--target", "altium", "--dry-run"
        )
        assert code == 0, err
        return [(p["path"], p["sha256"]) for p in env["result"]["plan"]], codes(env)  # type: ignore[index]

    as_it_is = plan()
    with monkeypatch.context() as patch:
        patch.setattr(embed, "default_fields", lambda defn: ())
        without = plan()
    assert as_it_is[0] and as_it_is == without
    assert any(path.endswith(".PcbDoc") for path, _ in as_it_is[0])


# --- a rebuild repairs an older board ----------------------------------------------------------------


def older_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Design]:
    """The catalog blink built, then every ``Reference`` and ``Value`` property removed from the board.
    The board as it was built is kept beside it as ``built.kicad_pcb``."""
    script = write_script(tmp_path / "P")
    out = tmp_path / "out"
    confirm(monkeypatch, script, out)
    before = read_board(board_path(out))
    (tmp_path / "built.kicad_pcb").write_bytes(board_path(out).read_bytes())
    removed = edit_footprints(out, lambda path, p: None if p.atoms()[0].value in MANDATORY else p)
    assert removed == 6
    stripped = read_board(board_path(out))
    for fp in footprints_by_path(stripped).values():
        assert [f.name for f in fp.fields] == ["fenolite.path"]
    return script, out, before


def footprints_by_path(design: Design) -> dict[str, FootprintInstance]:
    assert design.board is not None
    paths = {c.id: c.properties.get("fenolite.path", "") for c in design.circuit.components}
    return {paths[fp.component_id]: fp for fp in design.board.footprints}


def test_older_board_gains_the_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, out, before = older_board(tmp_path, monkeypatch)
    env = confirm(monkeypatch, script, out)
    assert sorted(env["result"]["preserved"]["kept"]) == list(REFS)  # type: ignore[index]
    assert "build.field-added" not in codes(env)
    after = read_board(board_path(out))
    assert {c.ref: c.value for c in after.circuit.components} == VALUES
    assert layout(after) == layout(before)
    for ref, fp in footprints(after).items():
        old = footprints(before)[ref]
        assert [f.name for f in fp.fields] == [f.name for f in old.fields], ref
        for name in MANDATORY:
            assert field(fp, name) == field(old, name), (ref, name)
    # the repaired board is the board a first build writes: the fields sit before the first field
    assert board_path(out).read_bytes() == (tmp_path / "built.kicad_pcb").read_bytes()
    pair, _ = netlists(out)
    assert (pair.common, pair.differences) == (6, ())


def test_older_board_takes_a_field_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, out, _ = older_board(tmp_path, monkeypatch)
    lines = "\ndesign.parts['R1'].field('Value', visible=False)\n"
    script.write_text(script.read_text(encoding="utf-8") + lines, encoding="utf-8")
    confirm(monkeypatch, script, out)
    after = footprints(read_board(board_path(out)))
    assert field(after["R1"], "Value").visible is False
    assert field(after["D1"], "Value").visible is True


def test_a_field_edited_in_kicad_stays(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = write_script(tmp_path / "P")
    out = tmp_path / "out"
    confirm(monkeypatch, script, out)
    before = field(footprints(read_board(board_path(out)))["R1"], "Reference")

    def move(path: str, prop: Node) -> Node:
        if path != "R1" or prop.atoms()[0].value != "Reference":
            return prop
        at = prop.find("at")
        assert at is not None
        x, y = at.atoms()[:2]
        moved = at.with_children([Atom.from_nm(x.to_nm() + 2_000_000), y, *at.atoms()[2:]])
        return prop.with_children([moved if c is at else c for c in prop.children])

    assert edit_footprints(out, move) == 1
    edited = field(footprints(read_board(board_path(out)))["R1"], "Reference")
    assert edited.position.x == before.position.x + 2_000_000
    confirm(monkeypatch, script, out)
    after = field(footprints(read_board(board_path(out)))["R1"], "Reference")
    assert after.position == edited.position and after.native_ids == before.native_ids


def test_a_second_rebuild_changes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, out, _ = older_board(tmp_path, monkeypatch)
    confirm(monkeypatch, script, out)
    code, env, err = build(monkeypatch, script, out, "--dry-run")
    assert code == 0, err
    assert changed(env, out) == []
