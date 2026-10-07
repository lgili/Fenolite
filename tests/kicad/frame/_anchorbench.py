# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Benches and probes of copper given in a part's frame (change c0111; capability kicad-oracle, "Anchored
copper passes the oracle"; ``H-G-FRAME-ANCHOR``, ``H-K-VIA-IN-PAD``).

Every bench is a design script, written to a temporary folder and built by ``fenolite build`` for the
running major from the authored footprint ``Frame:Frame_Anchor`` and a symbol of four pins that the script
authors. Nothing is committed: the script, its library table and the built project live in that folder.

**Frame.** ``Frame_Anchor`` at 0° and at 90° on the top and at 30° on the bottom. Each part has its four
pads on four nets of its own, and vias of a marker net, which holds no pad, anchored where a pad is: by
``part.at`` at the library positions of pads ``1`` and ``3``, by ``pad.at`` at an offset inside pad ``4``,
and by ``pad.at`` on a 3 × 3 grid of 1 mm in pad ``4``. KiCad gives a via the net of the pad it touches
(``H-K-VIA-RENET``), so the DRC report says, via by via, which pad KiCad sees under each anchor. The
control gives the offsets of the bottom part as board points computed without the mirror: its vias for
pads ``1`` and ``3`` must be named with each other's nets, which shows that the probe can fail.

**Thermal array.** One part with pad ``4`` on a net of its own and a stitch whose region is that pad;
joined, a track of the net runs through the via centres on the other outer layer.

**Moved part.** The joined thermal bench, built, its part moved and turned by ``fenolite place --move``,
and built again. The control gives the same array and track as board points.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import tempfile
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import fenolite.cli.main as cli_main
from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.core.coords import Point
from fenolite.geometry import Transform

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
LIBS = Path(__file__).resolve().parents[2] / "data" / "libs"
NAME = "anchor"
BOARD = f"{NAME}.kicad_pcb"
MM = 1_000_000
MARK = "MARK"
"""The net of the marker vias: it holds no pad."""
PAD_AT: Mapping[str, tuple[float, float]] = {"1": (-4, -2), "2": (-4, 0), "3": (-4, 2), "4": (1, 0)}
"""Where ``Frame_Anchor`` draws its pads, in millimetres."""
INSIDE = (0.5, -0.5)
"""The offset of the marker that ``pad.at`` puts inside pad ``4``, off its centre and off the grid."""
GRID = tuple((i, j) for j in (-1, 0, 1) for i in (-1, 0, 1))
PARTS: Mapping[str, tuple[float, float, int, str]] = {
    "UA": (12, 12, 0, "top"),
    "UB": (30, 12, 90, "top"),
    "UC": (48, 26, 30, "bottom"),
}
"""The parts of the frame bench: reference → x, y (mm, frame of ``place()``), degrees, side."""
THERMAL_AT = (20.0, 20.0)
MOVE = (40.0, 24.0, 90)
"""Where ``fenolite place --move`` puts the part of the moved bench: x, y (mm) and degrees."""
SNAKE = ((-1, -1), (0, -1), (1, -1), (1, 0), (0, 0), (-1, 0), (-1, 1), (0, 1), (1, 1))
"""The via centres of the 3 × 3 array in the order the joining track visits them."""
_NET = re.compile(r"\[([^\]]*)\]")

HEAD = '''"""A bench script of Fenolite's oracle tests (change c0111), authored for Fenolite."""

from fenolite.dsl import Design, Net, Part, Symbol, connect, mm, nm

design = Design("anchor")
design.board(mm(60), mm(40))
quad = Symbol("Bench", "Quad", reference="U", footprint="Frame:Frame_Anchor")
for number, y in (("1", 2.54), ("2", 0), ("3", -2.54)):
    quad.pin(number, f"P{number}", at=(mm(-5.08), mm(y)), length=mm(2.54), rotation=180)
quad.pin("4", "P4", at=(mm(5.08), mm(0)), length=mm(2.54))
quad.rect((mm(-2.54), mm(-5.08)), (mm(2.54), mm(5.08)))
design.add(quad)
SIZES = {"diameter": mm(0.6), "drill": mm(0.3)}
'''
ROW = '\t(lib (name "Frame") (type "KiCad") (uri "{}") (options "") (descr ""))\n'
TABLE = "(fp_lib_table\n\t(version 7)\n" + ROW + ")\n"


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def running_target() -> int:
    return runner().major()


# --- scripts ----------------------------------------------------------------------------------------


def _part(ref: str, x: float, y: float, degrees: int, side: str, nets: Mapping[str, str]) -> str:
    """The lines that add ``ref``, connect its pads to ``nets`` and place it, unlocked."""
    name = ref.lower()
    lines = [f'{name} = Part("{ref}", quad.lib_id)', f"design.add({name})"]
    lines += [f'connect(Net("{net}"), {name}["{number}"])' for number, net in nets.items()]
    lines.append(f'{name}.place(mm({x}), mm({y}), {degrees}, "{side}")')
    return "\n".join(lines) + "\n"


def board_point(ref: str, offset: tuple[float, float], *, mirror: bool | None = None) -> tuple[int, int]:
    """Where the offset (mm, library frame) of the part ``ref`` of the frame bench lies in the frame of
    ``place()``, in nanometres, computed by the test with ``Transform.placement``; ``mirror`` overrides
    the mirror of the part's side, for the control."""
    x, y, degrees, side = PARTS[ref]
    flip = side == "bottom" if mirror is None else mirror
    move = Transform.placement(Point(round(x * MM), round(y * MM)), degrees * MM, mirror=flip)
    point = move.apply(Point(round(offset[0] * MM), round(offset[1] * MM)))
    return point.x, point.y


def markers(ref: str) -> dict[str, tuple[str, str | None, tuple[float, float]]]:
    """The marker vias of one part: key → the pad whose net KiCad must give it, the pad the anchor is
    measured from (``None``: the footprint's origin) and the offset in millimetres."""
    found: dict[str, tuple[str, str | None, tuple[float, float]]] = {
        f"{ref}_p1": ("1", None, PAD_AT["1"]),
        f"{ref}_p3": ("3", None, PAD_AT["3"]),
        f"{ref}_in": ("4", "4", INSIDE),
    }
    for i, j in GRID:
        found[f"{ref}_g{i + 1}{j + 1}"] = ("4", "4", (i, j))
    return found


def _spot(ref: str, base: str | None, offset: tuple[float, float], computed: bool) -> str:
    """The point argument of a marker: an anchor of the script, or a board point computed here."""
    if computed:
        origin = PAD_AT[base] if base is not None else (0, 0)
        x, y = board_point(ref, (origin[0] + offset[0], origin[1] + offset[1]))
        return f"(nm({x}), nm({y}))"
    start = ref.lower() if base is None else f'{ref.lower()}.pad("{base}")'
    return f"{start}.at(mm({offset[0]}), mm({offset[1]}))"


def frame_script(*, computed: bool = False) -> str:
    """The frame bench. ``computed`` gives every marker as a board point computed by the test instead of
    an anchor: the form of the first measurement, before the anchors existed."""
    text = HEAD + f'mark = Net("{MARK}")\ndesign.add(mark)\n'
    for ref, (x, y, degrees, side) in PARTS.items():
        text += _part(ref, x, y, degrees, side, {n: f"{ref}_{n}" for n in PAD_AT})
        for key, (_, base, offset) in markers(ref).items():
            text += f'design.via("{key}", {_spot(ref, base, offset, computed)}, net=mark, **SIZES)\n'
    return text


def control_script() -> str:
    """The bottom part alone, its markers for pads ``1`` and ``3`` given as board points computed without
    the mirror."""
    ref = "UC"
    x, y, degrees, side = PARTS[ref]
    text = HEAD + f'mark = Net("{MARK}")\ndesign.add(mark)\n'
    text += _part(ref, x, y, degrees, side, {n: f"{ref}_{n}" for n in PAD_AT})
    for number in ("1", "3"):
        px, py = board_point(ref, PAD_AT[number], mirror=False)
        text += f'design.via("{ref}_p{number}", (nm({px}), nm({py})), net=mark, **SIZES)\n'
    return text


def _thermal_point(offset: tuple[float, float]) -> str:
    """A point of pad ``4`` of the thermal part as a board point: the part sits at 0° on the top."""
    x = THERMAL_AT[0] + PAD_AT["4"][0] + offset[0]
    y = THERMAL_AT[1] + PAD_AT["4"][1] + offset[1]
    return f"(mm({x}), mm({y}))"


def thermal_script(*, joined: bool, computed: bool = False) -> str:
    """The thermal bench: a stitch whose region is pad ``4`` and, ``joined``, a ``B.Cu`` track through the
    via centres, its points anchored with ``pad.at``. ``computed`` gives the array as nine vias at board
    points and the track through board points: the control of the moved bench."""
    nets = {"1": "P1", "2": "P2", "3": "P3", "4": "EP"}
    text = HEAD + _part("U1", THERMAL_AT[0], THERMAL_AT[1], 0, "top", nets)
    text += 'ep = design.nets["EP"]\n'
    if computed:
        for i, j in GRID:
            text += f'design.via("c{i + 1}{j + 1}", {_thermal_point((i, j))}, net=ep, **SIZES)\n'
    else:
        text += (
            'design.stitch("ep", net=ep, pitch=mm(1), region=u1.pad("4"), margin=mm(0.1), '
            "clearance=mm(0.2), **SIZES)\n"
        )
    if joined:
        points = [_thermal_point(p) if computed else f'u1.pad("4").at(mm({p[0]}), mm({p[1]}))' for p in SNAKE]
        text += f'design.track("join", {", ".join(points)}, layer="B.Cu", net=ep, width=mm(0.3))\n'
    return text


def array_uuids(*, computed: bool = False) -> tuple[frozenset[str], frozenset[str]]:
    """The uuids of the nine vias and of the eight segments of the joining track."""
    if computed:
        vias = frozenset(copper_uuid(f"c{i + 1}{j + 1}", "via") for i, j in GRID)
    else:
        vias = frozenset(copper_uuid("ep", f"via[{i},{j}]") for i, j in GRID)
    return vias, frozenset(copper_uuid("join", f"seg[{k}]") for k in range(len(SNAKE) - 1))


# --- builds -----------------------------------------------------------------------------------------


@contextlib.contextmanager
def _isolated(config: Path) -> Iterator[None]:
    """No library table and no library variable of the machine reaches the build."""
    names = ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR")
    saved = {name: os.environ.get(name) for name in ("KICAD_CONFIG_HOME", *names)}
    os.environ["KICAD_CONFIG_HOME"] = str(config)
    for name in names:
        os.environ.pop(name, None)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _fenolite(*args: str) -> tuple[int, dict[str, Any]]:
    """``fenolite`` in this process: the exit code and the JSON envelope."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {"issues": [], "stderr": err.getvalue()}


@dataclass(frozen=True)
class Built:
    """What a bench gave: the DRC report of its last build, and the issues of each ``fenolite`` run."""

    report: DrcReport | None
    issues: tuple[tuple[dict[str, Any], ...], ...]

    def codes(self, run: int = -1) -> list[str]:
        return [str(issue["code"]) for issue in self.issues[run]]


def _run(script: str, target: int, *, guard: bool, move: tuple[float, float, int] | None = None) -> Built:
    """Build ``script`` for ``target`` in a temporary folder and run KiCad's DRC on the board. Without
    ``guard`` the build passes ``--copper-check warn``. With ``move`` the part ``U1`` is then moved by
    ``fenolite place --move``, the script built again over the board, and the DRC run on that."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        project, out = folder / "project", folder / "out"
        project.mkdir()
        (project / "design.py").write_text(script, encoding="utf-8", newline="\n")
        table = TABLE.format((LIBS / "Frame.pretty").as_posix())
        (project / "fp-lib-table").write_text(table, encoding="utf-8", newline="\n")
        version = ["--kicad-version", str(target)]
        build = [*version, "build", str(project / "design.py"), "--out", str(out), "--confirm"]
        if not guard:
            build += ["--copper-check", "warn"]
        runs: list[tuple[dict[str, Any], ...]] = []
        with _isolated(folder / "config"):
            code, envelope = _fenolite(*build)
            runs.append(tuple(envelope["issues"]))
            assert (out / BOARD).is_file(), (
                code,
                [i for i in envelope["issues"] if i["severity"] == "error"],
            )
            if move is not None:
                spot = f"U1={move[0]}mm,{move[1]}mm,{move[2]}"
                code, envelope = _fenolite(*version, "place", str(out / BOARD), "--move", spot, "--confirm")
                runs.append(tuple(envelope["issues"]))
                assert code == 0, envelope["issues"]
                code, envelope = _fenolite(*build)
                runs.append(tuple(envelope["issues"]))
                assert code == 0, [i for i in envelope["issues"] if i["severity"] == "error"]
        tops = {p.name: p for p in sorted(out.iterdir()) if p.name != BOARD and not p.name.endswith(".bak")}
        report = runner().drc(out / BOARD, files=tops).report
    return Built(report, tuple(runs))


@cache
def frame_built(target: int, computed: bool = False) -> Built:
    return _run(frame_script(computed=computed), target, guard=False)


@cache
def control_built(target: int) -> Built:
    return _run(control_script(), target, guard=False)


@cache
def thermal_built(target: int, joined: bool, computed: bool = False) -> Built:
    return _run(thermal_script(joined=joined, computed=computed), target, guard=True)


@cache
def moved_built(target: int, computed: bool) -> Built:
    return _run(thermal_script(joined=True, computed=computed), target, guard=True, move=MOVE)


# --- reading the report -----------------------------------------------------------------------------


def _entries(report: DrcReport) -> tuple[DrcViolation, ...]:
    return (*report.violations, *report.unconnected_items)


def named_nets(report: DrcReport, uuids: Mapping[str, str]) -> dict[str, set[str]]:
    """Label → the net names in square brackets of the report's descriptions of that item (``Via [UA_4]
    on F.Cu - B.Cu``): the net the item has once KiCad loaded the board."""
    found: dict[str, set[str]] = {label: set() for label in uuids.values()}
    for entry in _entries(report):
        for item in entry.items:
            match = _NET.search(item.description)
            if item.uuid in uuids and match is not None:
                found[uuids[item.uuid]].add(match.group(1))
    return found


def naming(report: DrcReport, uuids: frozenset[str]) -> dict[str, list[str]]:
    """Uuid → the types of the violations and unconnected items that name it."""
    found: dict[str, list[str]] = {uuid: [] for uuid in uuids}
    for entry in _entries(report):
        for item in entry.items:
            if item.uuid in found:
                found[item.uuid].append(entry.type)
    return found


def frame_problems(target: int, *, computed: bool = False) -> list[str]:
    """What keeps the frame bench from ``equal``: a marker KiCad names with another net than that of the
    pad its anchor names, a marker the report does not name, or a ``shorting_items`` naming a marker."""
    report = frame_built(target, computed).report
    if report is None:
        return ["no DRC report"]
    wanted = {key: f"{ref}_{pad}" for ref in PARTS for key, (pad, _, _) in markers(ref).items()}
    uuids = {copper_uuid(key, "via"): key for key in wanted}
    nets = named_nets(report, uuids)
    problems = [
        f"{key}: named {sorted(nets[key])}, wanted {net}" for key, net in wanted.items() if nets[key] != {net}
    ]
    shorts = naming(report, frozenset(uuids))
    problems += [f"{uuids[u]}: shorting_items" for u, types in shorts.items() if "shorting_items" in types]
    return problems


def frame_outcome(target: int) -> str:
    return "equal" if not frame_problems(target) else "different"


def control_outcome(target: int) -> str:
    """``different`` when the unmirrored vias of pads ``1`` and ``3`` are named with each other's nets;
    ``equal`` when each has the net of its own pad; ``inconclusive`` otherwise."""
    report = control_built(target).report
    if report is None:
        return "reject"
    uuids = {copper_uuid(f"UC_p{number}", "via"): number for number in ("1", "3")}
    nets = named_nets(report, uuids)
    if nets == {"1": {"UC_3"}, "3": {"UC_1"}}:
        return "different"
    return "equal" if nets == {"1": {"UC_1"}, "3": {"UC_3"}} else "inconclusive"


def thermal_outcome(target: int) -> str:
    """``absent`` when no violation and no unconnected item names a via of the array or its track."""
    report = thermal_built(target, True).report
    if report is None:
        return "reject"
    vias, track = array_uuids()
    return "absent" if not any(naming(report, vias | track).values()) else "present"


def alone_outcome(target: int) -> str:
    """``present`` when each via of the array gives exactly one ``via_dangling`` and nothing else names
    it; ``absent`` when nothing names any; ``different`` otherwise."""
    report = thermal_built(target, False).report
    if report is None:
        return "reject"
    found = naming(report, array_uuids()[0])
    if all(types == ["via_dangling"] for types in found.values()):
        return "present"
    return "absent" if not any(found.values()) else "different"


def regenerated(built: Built) -> set[str]:
    """The uuids the rebuild of a moved bench reports as ``kicad.copper.regenerated``."""
    return {str(i["where"]) for i in built.issues[-1] if i["code"] == "kicad.copper.regenerated"}


def moved_outcome(target: int) -> str:
    """``absent`` when, after the move and the rebuild, no ``via_dangling`` and no unconnected item names
    the array or its track; ``different`` when the rebuild did not regenerate each of them."""
    built = moved_built(target, False)
    if built.report is None:
        return "reject"
    vias, track = array_uuids()
    if not (vias | track) <= regenerated(built):
        return "different"
    found = naming(built.report, vias | track)
    loose = {
        u for entry in built.report.unconnected_items for item in entry.items if (u := item.uuid) in found
    }
    dangling = [u for u, types in found.items() if "via_dangling" in types]
    return "absent" if not dangling and not loose else "present"


def moved_control_outcome(target: int) -> str:
    """``present`` when every via of the array given as board points is ``via_dangling`` after the same
    move and rebuild; ``absent`` when none is; ``different`` otherwise."""
    built = moved_built(target, True)
    if built.report is None:
        return "reject"
    found = naming(built.report, array_uuids(computed=True)[0])
    dangling = [u for u, types in found.items() if "via_dangling" in types]
    if len(dangling) == len(found):
        return "present"
    return "absent" if not dangling else "different"


def guard_findings(built: Built) -> list[str]:
    """The codes of the copper guard in the issues of every build of a bench."""
    return [
        code for run in range(len(built.issues)) for code in built.codes(run) if code.startswith("copper.")
    ]


def anchor_probes() -> Probes:
    both = (9, 10)
    target = running_target
    return {
        "copper-anchor-frame": (lambda: frame_outcome(target()), both),
        "copper-anchor-frame-control": (lambda: control_outcome(target()), both),
        "copper-anchor-thermal": (lambda: thermal_outcome(target()), both),
        "copper-anchor-thermal-alone": (lambda: alone_outcome(target()), both),
        "copper-anchor-moved": (lambda: moved_outcome(target()), both),
        "copper-anchor-moved-control": (lambda: moved_control_outcome(target()), both),
    }


__all__ = [
    "GRID",
    "MOVE",
    "PARTS",
    "Built",
    "alone_outcome",
    "anchor_probes",
    "array_uuids",
    "board_point",
    "control_built",
    "control_outcome",
    "control_script",
    "frame_built",
    "frame_outcome",
    "frame_problems",
    "frame_script",
    "guard_findings",
    "markers",
    "moved_built",
    "moved_control_outcome",
    "moved_outcome",
    "named_nets",
    "naming",
    "regenerated",
    "thermal_built",
    "thermal_outcome",
    "thermal_script",
]
