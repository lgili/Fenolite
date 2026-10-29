# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Critical routes on the reference boards (change c0244; capability net-roles, "Open reference variants",
"Critical copper is locked and fenced", "Critical route failures" and "Critical routes on both backends";
capability cli-contract, "Role route result"; ``docs/roles.md``, "Critical routes").

Each ``open`` variant (the ``bad`` placement and the faults that are not critical copper, without the
critical copper of ``bad``) is built, its inferred roles are confirmed with ``fenolite roles --accept-all``,
and ``fenolite route --router octilinear --roles critical`` runs on it as a user runs it.
"""

from __future__ import annotations

import dataclasses
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from _critical import cli, confirmed_copy, route, routed
from _roleboards import EXAMPLES, Built, build_script, fill_as_outline, read

from fenolite.backends.kicad.boarditems import is_item_uuid
from fenolite.backends.kicad.copper import is_copper_uuid
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.geometry import Location, point_in_ring
from fenolite.model.board import Keepout


def entries(env: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["group"]: entry for entry in env["result"]["roles"]}


def codes(env: Mapping[str, Any], prefix: str = "route.") -> list[str]:
    return sorted(issue["code"] for issue in env["issues"] if issue["code"].startswith(prefix))


@pytest.fixture(scope="module")
def opened(
    reference: Callable[..., Built], tmp_path_factory: pytest.TempPathFactory
) -> Callable[[str], Built]:
    """``opened(board)``: a confirmed copy of the board's ``open`` variant, made once per module."""
    made: dict[str, Built] = {}

    def get(board: str) -> Built:
        if board not in made:
            made[board] = confirmed_copy(reference(board, "open"), tmp_path_factory.mktemp(f"{board}_open"))
        return made[board]

    return get


def test_reply_of_an_open_buck(opened: Callable[[str], Built]) -> None:
    """Scenario "The reply of an open buck"."""
    code, env, err = route(opened("buck_shunt").board, "--dry-run")
    assert code == 0, err
    found = entries(env)
    assert {name: entry["status"] for name, entry in found.items()} == {
        "gate_Q1": "complete",
        "gate_Q2": "complete",
        "kelvin_R12": "routed",
    }
    kelvin = found["kelvin_R12"]
    assert [(c["net"], c["a"], c["b"], c["form"], c["layer"]) for c in kelvin["connections"]] == [
        ("VL", "R12-1", "U3-3", "pair", "F.Cu"),
        ("VOUT", "R12-2", "U3-4", "pair", "F.Cu"),
    ]
    assert kelvin["reason"] is None and kelvin["proposal"] is None and kelvin["findings_after"] == []
    assert kelvin["copper"] and len(kelvin["corridors"]) == 2
    assert "route.unrouted" not in codes(env) and not [c for c in codes(env) if c.startswith("route.role")]
    assert env["result"]["selected"] == ["VL", "VOUT"] and env["result"]["unrouted"] == []
    assert env["result"]["connections"] == {"before": 2, "after": 0}
    assert env["result"]["plan"][0]["path"].endswith("buck_shunt_open.kicad_pcb")
    assert env["evidence"]["level"] == "UNVERIFIED"


BLOCKED = """\
# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as a test board; no file, value, name or layout comes from any other project.
from bms_board import make

from fenolite.dsl import Design, Net, Part, connect, mm

design = make(Design("bms_blocked"), "open")
r9 = Part("R9", "Fenolite:Resistor", footprint="Fenolite:Chip_1206", value="1k")
design.add(r9)
connect(Net("BLK"), r9[1], r9[2])
r9.place(mm(60), mm(13), rot=90)  # across the path from the shunt's sense pads to the monitor
"""


def test_a_blocked_pair_is_reported(tmp_path: Path) -> None:
    """Scenario "A blocked pair is reported": a part across the path of the bms pair leaves it unrouted with
    reason ``no-room``, a ``free-corridor`` proposal that names the part and a ``render --region``
    command."""
    folder = tmp_path / "bms"
    shutil.copytree(EXAMPLES / "bms", folder)
    libs = (EXAMPLES.parents[1] / "tests" / "data" / "libs").as_posix()
    for table in ("sym-lib-table", "fp-lib-table"):
        text = (folder / table).read_text(encoding="utf-8")
        (folder / table).write_text(
            text.replace("${KIPRJMOD}/../../../tests/data/libs", libs), encoding="utf-8"
        )
    (folder / "blocked.py").write_text(BLOCKED, encoding="utf-8")
    built = confirmed_copy(build_script(folder / "blocked.py", tmp_path / "build"), tmp_path / "copy")
    code, env, err = route(built.board, "--dry-run")
    assert code == 0, err
    entry = entries(env)["kelvin_R1"]
    assert (entry["status"], entry["reason"]) == ("unrouted", "no-room")
    proposal = entry["proposal"]
    assert proposal["kind"] == "free-corridor" and "R9" in proposal["text"]
    assert proposal["command"].startswith(f"fenolite render {built.board.name} --out ")
    assert "--region " in proposal["command"] and proposal["region"]
    assert codes(env, "route.role") == ["route.role-unrouted"]
    assert not env["result"].get("plan")


def _fill(board: Path) -> None:
    board.write_text(fill_as_outline(board.read_text(encoding="utf-8")), encoding="utf-8")


def _check(board: Path, folder: str) -> dict[str, Any]:
    args = ["roles", str(board), "--check"]
    requirements = EXAMPLES / folder / "requirements.toml"
    if requirements.is_file():
        args += ["--requirements", str(requirements)]
    code, env, err = cli(*args)
    assert code in (0, 5), err
    return env


def test_corridors_and_locks_after_a_fill(opened: Callable[[str], Built], tmp_path: Path) -> None:
    """Scenario "The fill leaves the sense branch alone": on the routed open buck, both sense branches are
    locked and lie inside their corridors, and after a fill ``roles --check`` finds no
    ``roles.kelvin-shared``.
    The corridors' and tracks' KiCad uuids carry neither the build's item marker nor its copper marker, so a
    rebuild keeps them as items drawn on the board."""
    built = confirmed_copy(opened("buck_shunt"), tmp_path)
    routed(built.board)
    text = built.board.read_text(encoding="utf-8")
    design, _ = read(built)
    assert design.board is not None
    nets = {net.id: net.name for net in design.circuit.nets}
    areas = {area.name: area for area in design.board.keepouts if area.name.startswith("role.corridor.")}
    assert sorted(areas) == ["role.corridor.kelvin_R12.VL", "role.corridor.kelvin_R12.VOUT"]
    for area in areas.values():
        assert area.no_copper_pour and not (
            area.no_tracks or area.no_vias or area.no_pads or area.no_footprints
        )
        assert area.layers == ("F.Cu",) and not is_item_uuid(area.native_ids["kicad"])
    locked = [track for track in design.board.tracks if track.locked]
    assert {nets[track.net_id or ""] for track in locked} == {"VL", "VOUT"}
    for track in locked:
        ring = areas[f"role.corridor.kelvin_R12.{nets[track.net_id or '']}"].outline
        assert point_in_ring(track.start, ring) is not Location.OUTSIDE
        assert point_in_ring(track.end, ring) is not Location.OUTSIDE
        assert not is_copper_uuid(track.native_ids["kicad"])
    assert text.count("(locked yes)") >= len(locked)
    _fill(built.board)
    env = _check(built.board, "buck_shunt")
    assert not [i for i in env["issues"] if i["code"] in ("roles.kelvin-shared", "roles.kelvin-outer")]


def test_a_corridor_replaces_one_of_its_name(opened: Callable[[str], Built], tmp_path: Path) -> None:
    """A rule area named as a corridor (a provisional corridor of phase 1) is replaced along the route, and
    another rule area is kept."""
    built = confirmed_copy(opened("buck_shunt"), tmp_path)
    design = read_board(built.board.read_text(encoding="utf-8"), file=built.board.name)
    assert design.board is not None
    ring = (Point(140_000_000, 101_000_000), Point(141_000_000, 101_000_000), Point(141_000_000, 102_000_000))
    old = Keepout(
        id="rul_old", outline=ring, layers=("F.Cu",), no_copper_pour=True, name="role.corridor.kelvin_R12.VL"
    )
    other = Keepout(id="rul_other", outline=ring, layers=("F.Cu",), no_tracks=True, name="mine")
    board = dataclasses.replace(design.board, keepouts=(*design.board.keepouts, old, other))
    built.board.write_text(write_board(dataclasses.replace(design, board=board)).text, encoding="utf-8")
    routed(built.board)
    after = read_board(built.board.read_text(encoding="utf-8"), file=built.board.name)
    assert after.board is not None
    named = [area for area in after.board.keepouts if area.name == "role.corridor.kelvin_R12.VL"]
    assert len(named) == 1 and named[0].outline != ring
    assert [area.name for area in after.board.keepouts if area.name == "mine"] == ["mine"]
