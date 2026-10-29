# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement in code through ``fenolite build`` (change c0255; capability placement-in-code, "Recorded
resolutions", "Resolution order", "Unresolved references", "Rigid block moves" and "Strategy groups without a
pose"; capability layout-lens, "Placement precedence")."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from _layout_edit import add_items, move_footprint, net_ref, pad_position

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.dsl.convert import BOARD_ORIGIN
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
PADS = ROOT / "examples" / "relative" / "pads.py"
MM = 1_000_000


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


class Bench:
    """A design script in a folder of its own, built into ``out`` in-process."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, name: str) -> None:
        self.monkeypatch = monkeypatch
        self.folder = tmp_path / "src"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.script = self.folder / "design.py"
        self.script.write_text(text, encoding="utf-8")
        self.out = tmp_path / "out"
        self.name = name

    def build(self, *flags: str, out: Path | None = None) -> tuple[int, dict[str, Any], str]:
        stdout, err = io.StringIO(), io.StringIO()
        self.monkeypatch.setattr("sys.stdout", stdout)
        self.monkeypatch.setattr("sys.stderr", err)
        args = ["build", str(self.script), "--out", str(out or self.out), *flags, "--json"]
        code = cli_main.main(args)
        return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, err.getvalue()

    @property
    def board(self) -> Path:
        return self.out / f"{self.name}.kicad_pcb"

    def read(self) -> Design:
        return read_board(self.board.read_text(encoding="utf-8"))

    def positions(self) -> dict[str, tuple[Point, int, str]]:
        design = self.read()
        assert design.board is not None
        refs = {c.id: c.ref for c in design.circuit.components}
        return {refs[fp.component_id]: (fp.position, fp.rotation, fp.side) for fp in design.board.footprints}

    def edit_script(self, old: str, new: str) -> None:
        text = self.script.read_text(encoding="utf-8")
        assert old in text, old
        self.script.write_text(text.replace(old, new), encoding="utf-8")

    def files(self) -> dict[str, bytes]:
        return {
            str(p.relative_to(self.out)): p.read_bytes()
            for p in sorted(self.out.rglob("*"))
            if p.is_file() and not p.name.endswith(".bak")
        }


def _codes(env: dict[str, Any]) -> list[str]:
    return [found["code"] for found in env["issues"]]


HEAD = """from fenolite.dsl import Design, Net, block, connect, mm, row

design = Design("rel")
board = design.board(mm(40), mm(30))


def cap(container, ref):
    return container.part(ref, "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")


"""


def test_pads_example_is_recorded_and_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = Bench(tmp_path, monkeypatch, PADS.read_text(encoding="utf-8"), "relative_pads")
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    placement = env["result"]["placement"]
    records = {record["path"]: record for record in placement["relative"]}
    assert sorted(records) == ["C1", "C2", "D1", "J1", "R1"]
    assert records["C2"]["request"] == "right_of=U1 gap=1mm"
    positions = bench.positions()
    for path, record in records.items():
        at = Point(BOARD_ORIGIN.x + record["at"][0], BOARD_ORIGIN.y + record["at"][1])
        assert positions[path] == (at, record["rotation"], record["side"]), path
    assert len(placement["digest"]) == 64 and placement["blocks"] == []
    assert "H-G-REL-RESOLVE" in env["evidence"]["hypotheses"]
    record = json.loads((bench.out / ".fenolite" / "build.json").read_text(encoding="utf-8"))
    assert record["layout"] == {"digest": placement["digest"], "poses": {}}


def test_byte_identical_rebuilds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = Bench(tmp_path, monkeypatch, PADS.read_text(encoding="utf-8"), "relative_pads")
    assert bench.build("--confirm")[0] == 0
    first = bench.files()
    other = tmp_path / "other"
    assert bench.build("--confirm", out=other)[0] == 0
    assert {k: v for k, v in first.items()} == {
        str(p.relative_to(other)): p.read_bytes() for p in sorted(other.rglob("*")) if p.is_file()
    }
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert bench.files() == first
    assert "layout.place-overridden" not in _codes(env)


def test_a_cycle_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = HEAD + "a, b = cap(design, 'A'), cap(design, 'B')\na.place(right_of=b)\nb.place(right_of=a)\n"
    bench = Bench(tmp_path, monkeypatch, text, "rel")
    code, env, _ = bench.build("--confirm")
    assert code == 5
    found = [i for i in env["issues"] if i["code"] == "layout.relative-cycle"]
    assert len(found) == 1 and found[0]["where"] == "A, B" and found[0]["severity"] == "error"
    assert not bench.out.exists() or not list(bench.out.rglob("*.kicad_pcb"))


def test_reference_left_in_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = HEAD + "u1, c5 = cap(design, 'U1'), cap(design, 'C5')\nc5.place(right_of=u1)\n"
    bench = Bench(tmp_path, monkeypatch, text, "rel")
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    unresolved = [i for i in env["issues"] if i["code"] == "layout.relative-unresolved"]
    assert len(unresolved) == 1 and "C5" in unresolved[0]["where"] and "U1" in unresolved[0]["where"]
    assert _codes(env).count("layout.unplaced") == 2


def test_the_board_wins_over_a_relative_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = HEAD + (
        "u1, c5 = cap(design, 'U1'), cap(design, 'C5')\n"
        "u1.place(mm(14), mm(15))\nc5.place(right_of=u1, gap=mm(1))\n"
    )
    bench = Bench(tmp_path, monkeypatch, text, "rel")
    assert bench.build("--confirm")[0] == 0
    before = bench.positions()["C5"][0]
    bench.board.write_text(
        move_footprint(bench.board.read_text(encoding="utf-8"), "C5", 0, 3 * MM), encoding="utf-8"
    )
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert bench.positions()["C5"][0] == Point(before.x, before.y + 3 * MM)
    (found,) = [i for i in env["issues"] if i["code"] == "layout.place-overridden"]
    assert found["where"] == "C5" and "right_of=U1 gap=1mm" in found["message"]


def test_a_follower_follows_its_moved_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = HEAD + (
        "u1, c5 = cap(design, 'U1'), cap(design, 'C5')\n"
        "u1.place(mm(14), mm(15))\nc5.place(right_of=u1, gap=mm(1))\n"
    )
    bench = Bench(tmp_path, monkeypatch, text, "rel")
    assert bench.build("--confirm")[0] == 0
    before = bench.positions()
    bench.board.write_text(
        move_footprint(bench.board.read_text(encoding="utf-8"), "U1", 0, 4 * MM), encoding="utf-8"
    )
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    after = bench.positions()
    # the base record holds C5's code position: the code moved with U1 and the board did not, so C5 follows
    assert after["U1"][0] == Point(before["U1"][0].x, before["U1"][0].y + 4 * MM)
    assert after["C5"][0] == Point(before["C5"][0].x, before["C5"][0].y + 4 * MM)


BLOCK = (
    HEAD
    + """
@block
def buck(b):
    vin = b.port("VIN")
    u = cap(b, "U")
    u.place(mm(0), mm(0))
    ind = cap(b, "L")
    ind.place(right_of=u, gap=mm(1))
    sw = b.net("SW")
    connect(sw, u["B"], ind["A"])
    connect(vin, u["A"], ind["B"])


j1 = cap(design, "J1")
j1.place(mm(3), mm(3))
vin = Net("VIN")
connect(vin, j1["A"])
p1 = design.use(buck, "buck1")
connect(vin, p1.VIN)
p1.place(mm(10), mm(8))
"""
)


def test_block_moved_with_its_copper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = Bench(tmp_path, monkeypatch, BLOCK, "rel")
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert env["result"]["placement"]["blocks"][0]["at"] == [10 * MM, 8 * MM]
    text = bench.board.read_text(encoding="utf-8")
    refs = {c.properties.get("fenolite.path"): c.ref for c in read_board(text).circuit.components}
    u, ind = refs["buck1/U"], refs["buck1/L"]
    text = move_footprint(text, ind, 0, MM)
    start, end = pad_position(text, u, "2"), pad_position(text, ind, "1")
    net = net_ref(text, "buck1/SW")
    track = (
        f"(segment (start {start.x / MM} {start.y / MM}) (end {end.x / MM} {end.y / MM}) (width 0.25) "
        f'(layer "F.Cu") {net} (uuid "0e5f2b9c-55aa-4c3e-9b1d-2550c0255001"))'
    )
    bench.board.write_text(add_items(text, track), encoding="utf-8")
    before = bench.positions()
    bench.edit_script("p1.place(mm(10), mm(8))", "p1.place(mm(20), mm(8))")
    code, env, err = bench.build("--confirm")
    assert code == 0, [i for i in env["issues"] if i["severity"] == "error"]
    after = bench.positions()
    for ref in (u, ind):
        assert after[ref][0] == Point(before[ref][0].x + 10 * MM, before[ref][0].y), ref
    assert after["J1"] == before["J1"]
    moved = [i for i in env["issues"] if i["code"] == "layout.block-moved"]
    assert len(moved) == 1 and moved[0]["where"] == "buck1" and moved[0]["severity"] == "info"
    board = bench.read().board
    assert board is not None
    (kept,) = [
        t for t in board.tracks if str(t.native_ids.get("kicad")) == "0e5f2b9c-55aa-4c3e-9b1d-2550c0255001"
    ]
    assert kept.start == Point(start.x + 10 * MM, start.y) and kept.end == Point(end.x + 10 * MM, end.y)
    record = json.loads((bench.out / ".fenolite" / "build.json").read_text(encoding="utf-8"))
    assert record["layout"]["poses"]["buck1"] == [BOARD_ORIGIN.x + 20 * MM, BOARD_ORIGIN.y + 8 * MM, 0]


def test_a_group_stays_together(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = (
        HEAD
        + """
@block
def trio(b):
    for name in ("R1", "R2", "R3"):
        cap(b, name)
    b.layout(row())


design.use(trio, "g")
cap(design, "J9")
"""
    )
    bench = Bench(tmp_path, monkeypatch, text, "rel")
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert _codes(env).count("layout.unplaced") == 4
    positions = bench.positions()
    design = bench.read()
    refs = {c.properties.get("fenolite.path"): c.ref for c in design.circuit.components}
    xs = [positions[refs[f"g/R{i}"]][0].x for i in (1, 2, 3)]
    ys = {positions[refs[f"g/R{i}"]][0].y for i in (1, 2, 3)}
    assert xs == sorted(xs) and len(ys) == 1
    assert positions["J9"][0].x > xs[-1]
    (held,) = env["result"]["placement"]["blocks"]
    assert held["staged"] is True and held["layout"] == "row()"


def test_a_build_without_placement_in_code_has_no_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copy(ROOT / "examples" / "blocks" / "design.py", tmp_path / "design.py")
    bench = Bench(tmp_path, monkeypatch, (tmp_path / "design.py").read_text(encoding="utf-8"), "blocks_demo")
    code, env, err = bench.build("--dry-run")
    assert code == 0, err
    assert "relative" not in env["result"]["placement"]
