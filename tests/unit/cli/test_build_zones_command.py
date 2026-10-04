# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script zones through ``fenolite build`` (capability layout-lens, "Zones declared in the script" and the
new scenarios of "Zone fills and the staleness digest"; design-dsl, "Zones in a build"; change c0031).
Each test builds the blink pour variant into ``tmp_path``, edits the result as KiCad would (by token
edit), and builds again in-process."""

from __future__ import annotations

import io
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from _buildhelp import POUR

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import kicad_uuid, read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, tree_equal
from fenolite.core.ids import derived_id
from fenolite.model.board import Zone

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
DRAWN_UUID = "00000000-0000-4000-8000-0000000000a1"
VIN_TOP = 'design.zone(vin, layers=("F.Cu",), name="VIN_TOP")\n'
LOCKED = POUR.replace('connection="solid"', 'connection="solid", locked=True')
FILLS = (
    '(filled_polygon (layer "B.Cu") (pts (xy 101.5 101.5) (xy 148.5 101.5) (xy 148.5 128.5)'
    " (xy 101.5 128.5)))",
    '(filled_polygon (layer "B.Cu") (pts (xy 120 120) (xy 122 120) (xy 122 122) (xy 120 122)))',
)
REMOVE_R1 = (
    ('r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")\n', ""),
    ("design.add(u1, r1, d1)", "design.add(u1, d1)"),
    ("connect(led_drv, u1[1], r1[1])", "connect(led_drv, u1[1])"),
    ("connect(led_a, r1[2], d1[2])", "connect(led_a, d1[2])"),
    ("r1.place(mm(32), mm(9))\n", ""),
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


class Project:
    """A copy of the blink whose script declares zones (``pour``), built into ``out`` with ``--confirm``."""

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        target: int = 10,
        pour: str = POUR,
        out: str = "B",
    ) -> None:
        self.monkeypatch = monkeypatch
        self.target = target
        root = tmp_path / f"repo-{out}"
        shutil.copytree(BLINK_DIR, root / "examples" / "blink_2layer")
        shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
        self.script = root / "examples" / "blink_2layer" / "design.py"
        self.script.write_text(self.script.read_text(encoding="utf-8") + pour, encoding="utf-8")
        self.out = tmp_path / out
        code, env, err = self.build("--confirm")
        assert code == 0, err
        self.first = env

    def build(self, *flags: str) -> tuple[int, dict[str, object], str]:
        out, err = io.StringIO(), io.StringIO()
        self.monkeypatch.setattr("sys.stdout", out)
        self.monkeypatch.setattr("sys.stderr", err)
        args = ["--kicad-version", str(self.target), "build", str(self.script), "--out", str(self.out)]
        code = cli_main.main([*args, *flags, "--json"])
        return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()

    @property
    def board(self) -> Path:
        return self.out / "blink.kicad_pcb"

    @property
    def text(self) -> str:
        return self.board.read_text(encoding="utf-8")

    def edit_board(self, change: Callable[[str], str]) -> None:
        self.board.write_text(change(self.text), encoding="utf-8")

    def edit_script(self, old: str, new: str) -> None:
        text = self.script.read_text(encoding="utf-8")
        assert old in text, old
        self.script.write_text(text.replace(old, new), encoding="utf-8")

    def zones(self) -> tuple[Zone, ...]:
        design = read_board(self.text)
        assert design.board is not None
        return design.board.zones

    def files(self) -> dict[str, bytes]:
        return {
            str(p.relative_to(self.out)): p.read_bytes()
            for p in sorted(self.out.rglob("*"))
            if p.is_file() and not p.name.endswith(".bak")
        }


def issues(env: dict[str, object], prefix: str = "kicad.zone.") -> list[dict[str, str]]:
    return [i for i in env["issues"] if i["code"].startswith(prefix)]  # type: ignore[union-attr, index]


def codes(env: dict[str, object]) -> list[str]:
    return [i["code"] for i in env["issues"]]  # type: ignore[union-attr, index]


def zone_node(text: str, name: str = "GND", index: int = 0) -> Node:
    wanted = parse(f'(name "{name}")')
    return [z for z in parse(text).nodes("zone") if z.find("name") == wanted][index]


def replace_zone(text: str, old: Node, *new: Node) -> str:
    root = parse(text)
    children: list[object] = []
    for child in root.children:
        children += list(new) if child == old else [child]
    return dumps(root.with_children(children))  # type: ignore[arg-type]


def edit_zone(text: str, old: str, new: str, name: str = "GND") -> str:
    target = zone_node(text, name)
    compact = dumps(target, style="compact")
    assert old in compact, old
    return replace_zone(text, target, parse(compact.replace(old, new, 1)))


def clearance(value: str) -> Callable[[str], str]:
    return lambda text: edit_zone(text, "(clearance 0.3)", f"(clearance {value})")


def filled(text: str) -> str:
    """The zone ``GND`` as KiCad leaves it after a fill: ``(fill yes …)`` and two fill polygons."""
    flagged = edit_zone(text, "(fill (", "(fill yes (")
    node = zone_node(flagged)
    return replace_zone(flagged, node, node.with_children([*node.children, *(parse(f) for f in FILLS)]))


# --- Zones in a build (design-dsl) -----------------------------------------------------------------


@pytest.mark.parametrize("target", [9, 10])
def test_blink_with_a_pour_on_both_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
) -> None:
    p = Project(tmp_path, monkeypatch, target)
    (zone,) = p.zones()
    assert (zone.name, zone.layers) == ("GND", ("B.Cu",))
    assert zone.settings.clearance == 300_000 and zone.settings.connection == "solid"
    assert ("(filled_areas_thickness no)" in " ".join(p.text.split())) == (target == 9)
    assert issues(p.first) == []  # fresh builds report no zone code


def test_zone_uuid_from_the_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a = Project(tmp_path, monkeypatch, out="A")
    b = Project(tmp_path, monkeypatch, out="B")
    assert a.text == b.text
    wanted = kicad_uuid(Zone(id=derived_id("zon", "dsl", "zone:GND"), outline=()))
    assert a.zones()[0].native_ids == {"kicad": wanted}


def test_unchanged_rebuild_is_a_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    before = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 0 and issues(env) == [] and p.files() == before


# --- Zones declared in the script (layout-lens) ------------------------------------------------------


def test_clearance_edited_in_kicad_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(clearance("0.5"))
    edited = zone_node(p.text)
    code, env, _ = p.build("--confirm")
    assert code == 0 and tree_equal(zone_node(p.text), edited)
    (issue,) = issues(env)
    assert issue["code"] == "kicad.zone.overridden" and issue["severity"] == "info"
    assert "GND" in issue["message"] and "settings" in issue["message"]
    assert "--discard-layout" in issue["hint"]


def test_a_locked_zone_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(clearance("0.5"))
    p.edit_script(POUR, LOCKED)
    code, env, _ = p.build("--confirm")
    assert code == 0
    (issue,) = issues(env)
    assert (
        issue["code"] == "kicad.zone.forced" and issue["severity"] == "warning" and "GND" in issue["message"]
    )
    node = zone_node(p.text)
    assert node.find("connect_pads") == parse("(connect_pads yes (clearance 0.3))")
    assert node.find("locked") == parse("(locked yes)")
    (zone,) = p.zones()
    assert zone.settings.clearance == 300_000 and zone.locked is True


def test_zone_added_to_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_script(POUR, POUR + VIN_TOP)
    code, env, _ = p.build("--confirm")
    assert code == 0 and issues(env) == []
    assert [z.name for z in p.zones()] == ["GND", "VIN_TOP"]


def test_zone_removed_from_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch, pour=POUR + VIN_TOP)
    assert [z.name for z in p.zones()] == ["GND", "VIN_TOP"]
    p.edit_script(VIN_TOP, "")
    code, env, _ = p.build("--confirm")
    assert code == 0 and [z.name for z in p.zones()] == ["GND"]
    (issue,) = issues(env)
    assert issue["code"] == "kicad.zone.orphan" and "VIN_TOP" in issue["message"]


def test_zone_drawn_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    node = zone_node(p.text)
    uuid = dumps(node.find("uuid"), style="compact")  # type: ignore[arg-type]
    drawn = parse(dumps(node, style="compact").replace(uuid, f'(uuid "{DRAWN_UUID}")'))
    p.edit_board(lambda text: replace_zone(text, node, node, drawn))
    code, env, _ = p.build("--confirm")
    assert code == 0 and issues(env) == []
    assert [z.name for z in p.zones()] == ["GND", "GND"]
    assert DRAWN_UUID in {z.native_ids["kicad"] for z in p.zones()}
    # and the build after that writes the same bytes
    before = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 0 and issues(env) == [] and p.files() == before


def test_zone_kept_across_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch, target=9)
    p.edit_board(clearance("0.5"))
    p.target = 10
    code, env, _ = p.build("--confirm")
    assert code == 0 and [i["code"] for i in issues(env)] == ["kicad.zone.overridden"]
    (zone,) = p.zones()
    assert zone.settings.clearance == 500_000
    assert "filled_areas_thickness" not in p.text


# --- Zone fills and the staleness digest -------------------------------------------------------------


def test_unchanged_rebuild_keeps_the_fills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(filled)
    code, env, _ = p.build("--confirm")
    (zone,) = p.zones()
    assert code == 0 and len(zone.fills) == 2 and zone.filled is True
    assert "zone.fill-stale" not in codes(env) and issues(env) == []


def test_a_removed_part_drops_fills_and_the_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(filled)
    for old, new in REMOVE_R1:
        p.edit_script(old, new)
    code, env, _ = p.build("--confirm")
    (zone,) = p.zones()
    assert code == 0 and zone.fills == () and zone.filled is False
    stale = [i for i in env["issues"] if i["code"] == "zone.fill-stale"]  # type: ignore[union-attr, index]
    assert len(stale) == 1 and "GND" in stale[0]["message"]


def test_a_zone_setting_change_drops_fills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch, pour=LOCKED)
    p.edit_board(filled)
    p.edit_script("clearance=mm(0.3), connection", "clearance=mm(0.4), connection")
    code, env, _ = p.build("--confirm")
    assert code == 0
    assert "zone.fill-stale" in codes(env) and "kicad.zone.forced" in codes(env)
    node = zone_node(p.text)
    assert node.find("connect_pads") == parse("(connect_pads yes (clearance 0.4))")
    assert node.nodes("filled_polygon") == ()
    fill = node.find("fill")
    assert fill is not None and fill.atoms() == ()


def test_an_unlocked_setting_change_keeps_the_board_and_its_fills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(filled)
    p.edit_script("clearance=mm(0.3), connection", "clearance=mm(0.4), connection")
    code, env, _ = p.build("--confirm")
    (zone,) = p.zones()
    assert code == 0 and zone.settings.clearance == 300_000 and len(zone.fills) == 2
    assert [i["code"] for i in issues(env)] == ["kicad.zone.overridden"] and "zone.fill-stale" not in codes(
        env
    )


# --- the Altium target ------------------------------------------------------------------------------


def _altium(
    monkeypatch: pytest.MonkeyPatch, script: Path, out: Path, *more: str
) -> tuple[int, dict[str, object]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    args = ["build", str(script), "--out", str(out), "--target", "altium", *more, "--confirm", "--json"]
    code = cli_main.main(args)
    assert code == 0, stderr.getvalue()
    return code, json.loads(stdout.getvalue())


def test_altium_build_writes_script_zones_as_polygons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = Project(tmp_path, monkeypatch)
    _, env = _altium(monkeypatch, p.script, tmp_path / "A")
    copper = env["result"]["copper"]  # type: ignore[index]
    assert (copper["source"], copper["zones"]) == ("model", 1)
    assert "altium.zones-unpoured" in codes(env)


def test_altium_build_with_copper_from_takes_the_boards_zones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = Project(tmp_path, monkeypatch)
    _, env = _altium(monkeypatch, p.script, tmp_path / "A", "--copper-from", str(p.board))
    copper = env["result"]["copper"]  # type: ignore[index]
    assert (copper["source"], copper["zones"]) == ("board", 1)
