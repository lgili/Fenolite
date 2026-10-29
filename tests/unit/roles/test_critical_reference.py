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
from collections import Counter
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from _critical import cli, confirmed_copy, route, routed
from _roleboards import EXAMPLES, Built, build_script, fill_as_outline, read
from _rolecheck import checked, findings

from fenolite.backends import registry
from fenolite.backends.altium.adapter.copper import region_points
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.base import BoardFrame
from fenolite.backends.kicad.boarditems import is_item_uuid
from fenolite.backends.kicad.copper import is_copper_uuid
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.geometry import Location, point_in_ring
from fenolite.model.board import Keepout
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design
from fenolite.roles.judge import split_roles
from fenolite.roles.store import dumps_document, merged


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


# --- the acceptance gate (tasks 4.1 to 4.5) -------------------------------------------------------------

OPEN_BEFORE: Mapping[str, set[tuple[str, str, str]]] = {
    "buck_shunt": {
        ("roles.loop-area", "warning", "hot_SW"),
        ("roles.loop-open", "warning", "kelvin_R12"),
        ("roles.loop-open", "warning", "kelvin_R12:R12-1"),
        ("roles.loop-open", "warning", "kelvin_R12:R12-2"),
        ("roles.width-current", "warning", "/kicad_pcb/segment[55]"),
    },
    "half_bridge": {
        ("roles.loop-open", "warning", "gate_Q1"),
        ("roles.loop-open", "warning", "gate_Q2"),
        ("roles.loop-open", "warning", "kelvin_R1"),
        ("roles.loop-open", "warning", "kelvin_R1:R1-1"),
        ("roles.loop-open", "warning", "kelvin_R1:R1-2"),
        ("roles.via-current", "error", "/kicad_pcb/via[7]"),
    },
    "bms": {
        ("roles.loop-open", "warning", "kelvin_R1"),
        ("roles.loop-open", "warning", "kelvin_R1:R1-2"),
        ("roles.loop-open", "warning", "kelvin_R1:R1-3"),
        ("roles.return-gap", "warning", "TAP0@/kicad_pcb/segment[23]"),
        ("roles.width-current", "warning", "/kicad_pcb/segment[21]"),
    },
}
"""The findings of warning or above of each ``open`` variant before routing: phase 1's faults, and the open
critical connections."""
OPEN_AFTER: Mapping[str, set[tuple[str, str, str]]] = {
    "buck_shunt": {
        ("roles.loop-area", "warning", "hot_SW"),
        ("roles.width-current", "warning", "/kicad_pcb/segment[55]"),
    },
    "half_bridge": {
        ("roles.loop-open", "warning", "kelvin_R1"),
        ("roles.loop-open", "warning", "kelvin_R1:R1-1"),
        ("roles.loop-open", "warning", "kelvin_R1:R1-2"),
        ("roles.via-current", "error", "/kicad_pcb/via[7]"),
    },
    "bms": {
        ("roles.return-gap", "warning", "TAP0@/kicad_pcb/segment[23]"),
        ("roles.width-current", "warning", "/kicad_pcb/segment[21]"),
    },
}
"""The findings after ``route --roles critical`` and a fill: exactly phase 1's faults, and on the half-bridge
the pair that its switch-node pour ``SW_UNDER`` blocks (design decision 17)."""
STATUSES = {
    "buck_shunt": {"gate_Q1": "complete", "gate_Q2": "complete", "kelvin_R12": "routed"},
    "half_bridge": {"gate_Q1": "routed", "gate_Q2": "routed", "kelvin_R1": "unrouted"},
    "bms": {"gate_Q1": "complete", "gate_Q2": "complete", "kelvin_R1": "routed"},
}
BOARDS_OPEN = sorted(OPEN_BEFORE)


@dataclasses.dataclass(frozen=True)
class Routed:
    """A routed ``open`` variant: the copy, the dry run's envelope, and the role check after a fill."""

    built: Built
    reply: dict[str, Any]
    check: dict[str, Any]


@pytest.fixture(scope="module")
def routed_open(
    opened: Callable[[str], Built], tmp_path_factory: pytest.TempPathFactory
) -> Callable[[str], Routed]:
    made: dict[str, Routed] = {}

    def get(board: str) -> Routed:
        if board not in made:
            built = confirmed_copy(opened(board), tmp_path_factory.mktemp(f"{board}_routed"))
            reply = routed(built.board)
            filled = tmp_path_factory.mktemp(f"{board}_filled") / "out"
            shutil.copytree(built.out, filled)
            board_file = filled / built.board.name
            _fill(board_file)
            made[board] = Routed(built, reply, _check(board_file, board))
        return made[board]

    return get


def _findings(env: Mapping[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (i["code"], i["severity"], i["where"]) for i in env["issues"] if i["severity"] in ("warning", "error")
    }


def _measures(env: Mapping[str, Any], kind: str) -> list[dict[str, Any]]:
    return [m for m in env["result"]["measures"] if m["kind"] == kind]


@pytest.mark.parametrize("board", BOARDS_OPEN)
def test_open_variant_builds(reference: Callable[..., Built], board: str) -> None:
    """Task 4.1: each ``open`` variant builds, and before routing it gives phase 1's faults and its open
    critical connections only (``checked`` confirms its groups as the reference tests do)."""
    assert findings(checked(reference, board, "open")) == OPEN_BEFORE[board]


@pytest.mark.parametrize("board", BOARDS_OPEN)
def test_critical_findings_cleared(routed_open: Callable[[str], Routed], board: str) -> None:
    """Scenario "Critical findings cleared": the routed and filled ``open`` variant keeps exactly its listed
    findings, and each group ends with its status."""
    done = routed_open(board)
    assert {e["group"]: e["status"] for e in done.reply["result"]["roles"]} == STATUSES[board]
    assert _findings(done.check) == OPEN_AFTER[board]


@pytest.mark.parametrize("board", ["buck_shunt", "bms"])
def test_kelvin_pairs_routed_clean(routed_open: Callable[[str], Routed], board: str) -> None:
    """``H-G-CRIT-KELVIN``: no Kelvin finding after routing and a fill, every entry offset ``t > 0``, the
    pair coupled (at or under 2000 per-mille)."""
    done = routed_open(board)
    assert not [i for i in done.check["issues"] if i["code"].startswith("roles.kelvin")]
    attachments = _measures(done.check, "attachment")
    assert len(attachments) == 2 and all(
        a["values"]["offsets"] and min(a["values"]["offsets"]) > 0 for a in attachments
    )
    (pair,) = [m for m in _measures(done.check, "loop") if m["values"]["group"] == "kelvin"]
    assert pair["values"]["ratio_permille"] <= 2000


def test_gate_loops_of_the_half_bridge(routed_open: Callable[[str], Routed]) -> None:
    """``H-G-CRIT-GATE``: both gate loops at or under 2000 per-mille, no ``roles.gate-return-shared``, the
    high side's return beside its drive from the Kelvin-source pad."""
    done = routed_open("half_bridge")
    loops = {
        m["subject"]: m["values"] for m in _measures(done.check, "loop") if m["values"]["group"] == "gate"
    }
    assert set(loops) == {"gate_Q1", "gate_Q2"} and all(v["ratio_permille"] <= 2000 for v in loops.values())
    assert not [
        i for i in done.check["issues"] if i["code"] in ("roles.gate-return-shared", "roles.gate-loop")
    ]
    found = entries(done.reply)
    (ret,) = found["gate_Q1"]["connections"]
    assert (ret["a"], ret["b"], ret["form"], ret["vias"]) == ("Q1-2", "U2-6", "side-by-side", 0)


def test_half_bridge_pair_waits_for_its_switch_node(
    routed_open: Callable[[str], Routed], tmp_path: Path
) -> None:
    """``H-G-CRIT-KEEPAWAY`` on the half-bridge: every shape of the pair runs over ``SW_UNDER`` on ``In1.Cu``,
    so the pair is refused with ``near-switching`` naming that pour and no ``roles.near-switching`` is
    written. Once the switch-node pour is gone (phase 1's copper), a second run routes the pair clean, and
    the gate loops stay ``complete``."""
    done = routed_open("half_bridge")
    entry = entries(done.reply)["kelvin_R1"]
    assert (entry["reason"], entry["proposal"]["kind"]) == ("near-switching", "free-corridor")
    assert "SW_UNDER" in entry["proposal"]["text"]
    assert not [i for i in done.check["issues"] if i["code"] == "roles.near-switching"]
    copy = tmp_path / "out"
    shutil.copytree(done.built.out, copy)
    board = copy / done.built.board.name
    design = read_board(board.read_text(encoding="utf-8"), file=board.name)
    assert design.board is not None
    sw = next(net.id for net in design.circuit.nets if net.name == "SW")
    trimmed = dataclasses.replace(
        design.board,
        zones=tuple(zone for zone in design.board.zones if zone.name != "SW_UNDER"),
        vias=tuple(v for v in design.board.vias if not (v.net_id == sw and v.layers == ("F.Cu", "In1.Cu"))),
    )
    board.write_text(write_board(dataclasses.replace(design, board=trimmed)).text, encoding="utf-8")
    again = routed(board)
    assert {e["group"]: e["status"] for e in again["result"]["roles"]} == {
        "gate_Q1": "complete",
        "gate_Q2": "complete",
        "kelvin_R1": "routed",
    }
    _fill(board)
    check = _check(board, "half_bridge")
    assert _findings(check) == {("roles.via-current", "error", "/kicad_pcb/via[6]")}
    attachments = _measures(check, "attachment")
    assert all(min(a["values"]["offsets"]) > 0 for a in attachments)


@pytest.mark.parametrize("board", BOARDS_OPEN)
def test_good_variants_plan_no_write(reference: Callable[..., Built], tmp_path: Path, board: str) -> None:
    """On each ``good`` variant the command plans no write: every group is ``complete``, and no
    ``route.role-*`` warning is given."""
    built = confirmed_copy(reference(board, "good"), tmp_path)
    code, env, err = route(built.board, "--dry-run")
    assert code == 0, err
    assert {e["status"] for e in env["result"]["roles"]} == {"complete"}
    assert not env["result"].get("plan")
    assert not [i for i in env["issues"] if i["code"].startswith("route.role") and i["severity"] != "info"]


def _role_items(board: Path) -> tuple[set[tuple[object, ...]], set[tuple[object, ...]]]:
    design = read_board(board.read_text(encoding="utf-8"), file=board.name)
    assert design.board is not None
    tracks = {(t.layer, t.start, t.end, t.width) for t in design.board.tracks if t.locked}
    tracks |= {("via", v.position, v.diameter) for v in design.board.vias if v.locked}
    areas = {
        (a.name, a.outline, a.layers) for a in design.board.keepouts if a.name.startswith("role.corridor.")
    }
    return tracks, areas


@pytest.mark.parametrize("board", BOARDS_OPEN)
def test_again_a_fixed_point(routed_open: Callable[[str], Routed], tmp_path: Path, board: str) -> None:
    """``H-G-CRIT-IDEMPOTENT``: a second run on a routed ``open`` board writes nothing and finds every routed
    group ``complete``; two rebuilds of the routed project keep the role copper and the corridors, and the
    second rebuild writes the bytes of the first."""
    done = routed_open(board)
    copy = tmp_path / "out"
    shutil.copytree(done.built.out, copy)
    board_file = copy / done.built.board.name
    code, env, err = route(board_file, "--dry-run")
    assert code == 0, err
    assert not env["result"].get("plan")
    before = {e["group"]: e["status"] for e in done.reply["result"]["roles"]}
    expected = {name: ("complete" if status == "routed" else status) for name, status in before.items()}
    assert {e["group"]: e["status"] for e in env["result"]["roles"]} == expected
    held = _role_items(board_file)
    assert held[0] and held[1]
    script = EXAMPLES / board / "open.py"
    build_script(script, copy, fill=False)
    first = board_file.read_bytes()
    assert _role_items(board_file) == held
    build_script(script, copy, fill=False)
    assert board_file.read_bytes() == first


def _converted(built: Built, into: Path) -> Path:
    """The Altium PCB document of ``fenolite convert`` of a KiCad project, with the project's stored roles
    (confirmed and declared) in its role document, as the Altium board's user keeps them."""
    code, _, err = cli("convert", str(built.board), "--to", "altium", "--out", str(into), "--confirm")
    assert code == 0, err
    (document,) = sorted(into.glob("*.PcbDoc"))
    model = load_dir(built.out / ".fenolite")
    declared, confirmed = split_roles(model.rules.roles if model.rules is not None else None)
    document.with_name(document.stem + ".roles.json").write_bytes(dumps_document(merged(declared, confirmed)))
    return document


def _judged(board: Path) -> Counter[tuple[str, str, str]]:
    """The role findings of warning or above of a reading: a group's by its subject, any other by its code
    and severity (its locator differs between the backends)."""
    code, env, err = cli("roles", str(board), "--check")
    assert code in (0, 5), err
    groups = ("hot_", "gate_", "kelvin_")
    return Counter(
        (i["code"], i["severity"], i["where"] if i["where"].startswith(groups) else "")
        for i in env["issues"]
        if i["code"].startswith("roles.") and i["severity"] in ("warning", "error")
    )


@pytest.mark.parametrize("board", BOARDS_OPEN)
def test_altium_readback(
    opened: Callable[[str], Built], routed_open: Callable[[str], Routed], tmp_path: Path, board: str
) -> None:
    """Scenario "Same critical copper in Altium", ``H-A-CRIT-READBACK``: the convert of a routed ``open``
    variant reads back with every role track and via at its place and width, locked, and every corridor as a
    pour keep-out region on its layer; and the role copper changes the role findings of the Altium reading
    exactly as it changes those of the KiCad reading (the readings of a converted project differ before
    routing already, since a board that Fenolite did not build has no pin names to classify its parts)."""
    done = routed_open(board)
    routed_doc = _converted(done.built, tmp_path / "routed")
    open_doc = _converted(opened(board), tmp_path / "open")
    kicad, _ = read(done.built)
    backend = registry.for_path(routed_doc)
    assert backend is not None
    altium = backend.read(routed_doc).content
    assert isinstance(altium, Design) and altium.board is not None and kicad.board is not None
    pads_k = {f"{p.ref}-{p.number}": p.position for p in read(done.built)[1]}
    assert isinstance(backend, BoardFrame)
    pads_a = {f"{p.ref}-{p.number}": p.position for p in backend.board_pads(altium, issues=[])}
    anchor = sorted(pads_k)[0]
    dx, dy = pads_a[anchor].x - pads_k[anchor].x, pads_a[anchor].y - pads_k[anchor].y

    def moved(point: Point) -> tuple[int, int]:
        return (round((point.x + dx) / 1_000), round((point.y + dy) / 1_000))

    def copper(design: Design, shift: bool) -> set[tuple[object, ...]]:
        assert design.board is not None
        at = moved if shift else (lambda p: (round(p.x / 1_000), round(p.y / 1_000)))
        found: set[tuple[object, ...]] = {
            (t.layer, at(t.start), at(t.end), t.width) for t in design.board.tracks if t.locked
        }
        return found | {("via", at(v.position), v.diameter) for v in design.board.vias if v.locked}

    assert copper(kicad, True) and copper(altium, False) == copper(kicad, True)
    document = read_pcbdoc(routed_doc.read_bytes(), file=routed_doc.name, strict=True)
    regions = sorted(
        tuple((round(p.x / 1_000), round(p.y / 1_000)) for p in region_points(r.outline))
        for r in document.regions
        if r.prefix.flags2 == 2
        and r.properties.get("KEEPOUTRESTRICTIONS") == "4"
        and r.properties.get("V7_LAYER") == "TOP"
    )
    corridors = sorted(
        tuple(moved(p) for p in area.outline)
        for area in kicad.board.keepouts
        if area.name.startswith("role.corridor.") and area.layers == ("F.Cu",)
    )
    assert corridors and len(regions) == len(corridors)
    for mine, theirs in zip(sorted(map(sorted, regions)), sorted(map(sorted, corridors)), strict=True):
        assert all(abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1 for a, b in zip(mine, theirs, strict=True))
    kicad_open = tmp_path / "kicad_open"
    shutil.copytree(opened(board).out, kicad_open)
    _fill(kicad_open / opened(board).board.name)
    kicad_routed = tmp_path / "kicad_routed"
    shutil.copytree(done.built.out, kicad_routed)
    _fill(kicad_routed / done.built.board.name)
    before_k, after_k = (
        _judged(kicad_open / opened(board).board.name),
        _judged(kicad_routed / done.built.board.name),
    )
    before_a, after_a = _judged(open_doc), _judged(routed_doc)
    assert after_k - before_k == Counter() and after_a - before_a == Counter()
    assert before_a - after_a == before_k - after_k
