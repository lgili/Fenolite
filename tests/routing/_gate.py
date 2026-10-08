# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the feasibility gate of change c0110 shares (design of c0110, Decision 1): building a bench into a
folder, running a script of the pinned KiCadRoutingTools checkout or the pinned Freerouting jar on a copy of
it, merging the copper the tool added on the selected nets, judging the merged board with the ``kicad-cli``
of its major, and recording an outcome.

The gate uses ``fenolite build`` (and ``fenolite route --router direct`` for c0107's plane fan-out, which the
QFN and BGA benches carry), ``read_board``, ``write_board``, ``write_dsn``, ``read_session``,
``routing.merge.apply``, ``subprocess`` and ``kicad-cli``; no code of the router plugins. Each tool run is
bounded by ``FENOLITE_GATE_SECONDS`` (900 by default, the gate's limit per run). An outcome is printed, so
the ``-rA`` log of the ``routing`` job shows it, and with ``FENOLITE_ROUTING_EVIDENCE=1`` it is also
appended to ``docs/evidence/routing.md`` and written to the tool's results file under
``docs/evidence/routing/``.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import _planebench as pb
from _resources import kicad_cli

from fenolite.backends.base import BoardPad, DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.specctra.dsn import DsnResult
from fenolite.backends.specctra.ses import read_session, to_copper
from fenolite.core.coords import Point
from fenolite.model.board import Arc, Track, Via
from fenolite.model.design import Design
from fenolite.routing.merge import apply
from fenolite.routing.protocol import RoutingResult

ROOT = Path(__file__).resolve().parents[2]
KRT_TAG = "v0.22.1"
GATE_SECONDS = int(os.environ.get("FENOLITE_GATE_SECONDS", "900"))
"""The limit of one tool run of the gate (Decision 1: at most 900 s per run)."""
EVIDENCE_PAGE = ROOT / "docs" / "evidence" / "routing.md"
RESULTS = ROOT / "docs" / "evidence" / "routing"
WRITE = "FENOLITE_ROUTING_EVIDENCE"
PAIR_TYPES = frozenset({"diff_pair_gap_out_of_range", "diff_pair_uncoupled_length_too_long"})
_NET = re.compile(r"\[([^\]]+)\]")


def build(module: str, function: str, folder: Path, target: int, **arguments: object) -> Path:
    """The design that ``module.function(**arguments)`` returns, built by ``fenolite build`` into
    ``folder / "out"`` for ``target``; returns its board file. ``tests/routing`` is on the import path of the
    suites, so the script imports the bench module by name."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "design.py"
    call = ", ".join(f"{key}={value!r}" for key, value in sorted(arguments.items()))
    script.write_text(f"from {module} import {function}\n\ndesign = {function}({call})\n", encoding="utf-8")
    out = folder / "out"
    code, env, err = pb.run_cli(
        "--kicad-version", str(target), "build", str(script), "--out", str(out), "--confirm"
    )
    errors = [i for i in env.get("issues", ()) if i["severity"] == "error"]  # type: ignore[union-attr, index]
    assert code == 0, (err, errors)
    boards = sorted(out.glob("*.kicad_pcb"))
    assert len(boards) == 1, boards
    return boards[0]


def fan_out_planes(board: Path) -> dict[str, object]:
    """c0107's plane fan-out written into ``board`` by ``fenolite route --router direct`` on the two plane
    nets (``GND``, ``VCC``), which the router never traces; returns ``result.plane_fanout``."""
    code, env, err = pb.run_cli(
        "route",
        str(board),
        "--router",
        "direct",
        "--nets",
        "GND",
        "--nets",
        "VCC",
        "--confirm",
        "--no-backup",
    )
    assert code == 0, err
    made = env["result"]["plane_fanout"]  # type: ignore[index]
    assert isinstance(made, dict), env
    return made


def copy_project(board: Path, folder: Path) -> Path:
    """A copy of the folder of ``board`` (project, rules, library tables, project library) in ``folder``;
    returns the copied board."""
    shutil.copytree(board.parent, folder)
    return folder / board.name


def krt_checkout() -> tuple[Path, Path]:
    """The pinned KiCadRoutingTools checkout (``FENOLITE_KRT``) and the interpreter that runs it."""
    checkout = Path(os.environ["FENOLITE_KRT"])
    interpreter = Path(os.environ.get("FENOLITE_KRT_PYTHON", sys.executable))
    assert (checkout / "py_router" / "route.py").is_file(), checkout
    return checkout, interpreter


@dataclass(frozen=True)
class ToolRun:
    """One run of a tool: its exit code (``None`` when it was stopped at the limit), seconds, output tail."""

    code: int | None
    seconds: float
    tail: str

    @property
    def done(self) -> bool:
        return self.code == 0


def run_tool(command: Sequence[str], folder: Path, *, env: dict[str, str] | None = None) -> ToolRun:
    """Run ``command`` in ``folder`` within ``GATE_SECONDS``."""
    start = time.monotonic()
    try:
        done = subprocess.run(
            list(command),
            cwd=folder,
            env={**os.environ, "LANG": "C", "LC_ALL": "C", **(env or {})},
            capture_output=True,
            text=True,
            timeout=GATE_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as stopped:
        output = stopped.stdout if isinstance(stopped.stdout, str) else (stopped.stdout or b"").decode()
        return ToolRun(None, round(time.monotonic() - start, 1), "\n".join(output.splitlines()[-15:]))
    output = done.stdout + done.stderr
    return ToolRun(done.returncode, round(time.monotonic() - start, 1), "\n".join(output.splitlines()[-15:]))


def krt(script: str, *arguments: str, folder: Path) -> ToolRun:
    """``py_router/<script>`` of the checkout with ``arguments``, in ``folder``."""
    checkout, interpreter = krt_checkout()
    return run_tool([str(interpreter), str(checkout / "py_router" / script), *arguments], folder)


def mm(value: int) -> str:
    """Nanometres as the tools' millimetre argument."""
    whole, rest = divmod(value, 1_000_000)
    return f"{whole}.{rest:06d}".rstrip("0").rstrip(".")


def added_copper(before: Design, after: Design, nets: Iterable[str]) -> RoutingResult:
    """The tracks, arcs and vias of ``after`` whose id ``before`` lacks, on the nets named, with the net ids
    of ``before``."""
    assert before.board is not None and after.board is not None
    wanted = set(nets)
    ids_before = {net.name: net.id for net in before.circuit.nets}
    names_after = {net.id: net.name for net in after.circuit.nets}
    known = {item.id for item in (*before.board.tracks, *before.board.arcs, *before.board.vias)}

    def keep(item: Track | Arc | Via) -> bool:
        return item.id not in known and names_after.get(item.net_id or "") in wanted

    def renet(item: Track | Arc | Via) -> Track | Arc | Via:
        return dataclasses.replace(item, net_id=ids_before[names_after[item.net_id or ""]])

    tracks = tuple(renet(item) for item in after.board.tracks if keep(item))
    arcs = tuple(renet(item) for item in after.board.arcs if keep(item))
    vias = tuple(renet(item) for item in after.board.vias if keep(item))
    return RoutingResult(tracks=tracks, arcs=arcs, vias=vias)  # type: ignore[arg-type]


def merged_board(
    board: Path, routed: Path, nets: Iterable[str], target: int, name: str
) -> tuple[Path, Design]:
    """``board`` with the copper ``routed`` added on ``nets``, written beside ``board`` as ``name`` with the
    project and rules files under the same stem; returns the file and its design."""
    before = read_board(board.read_text(encoding="utf-8"))
    after = read_board(routed.read_text(encoding="utf-8"))
    design = apply(before, added_copper(before, after, nets))
    out = board.with_name(f"{name}.kicad_pcb")
    out.write_text(write_board(design, target=target).text, encoding="utf-8")
    for suffix in (".kicad_pro", ".kicad_dru"):
        beside = board.with_suffix(suffix)
        if beside.is_file():
            shutil.copy2(beside, out.with_suffix(suffix))
    return out, design


def runner() -> KicadCli:
    binary = kicad_cli()
    assert binary is not None
    return KicadCli(Path(binary), timeout=600)


def drc(board: Path) -> DrcReport:
    """KiCad's DRC report of ``board`` with its project and rules files (``kicad-cli`` of this machine)."""
    files = {
        beside.name: beside
        for beside in (board.with_suffix(".kicad_pro"), board.with_suffix(".kicad_dru"))
        if beside.is_file()
    }
    done = runner().drc(board, files=files)
    assert done.report is not None, done.run.stderr or done.run.stdout
    return done.report


def error_types(report: DrcReport) -> set[str]:
    return {
        v.type
        for v in (*report.violations, *report.unconnected_items)
        if v.severity == "error" and not v.excluded
    }


def open_on(report: DrcReport, nets: Iterable[str]) -> int:
    """The unconnected items of ``report`` that name one of ``nets``."""
    wanted = set(nets)
    return sum(
        1
        for item in report.unconnected_items
        if any(found in wanted for entry in item.items for found in _NET.findall(entry.description))
    )


def findings_of(report: DrcReport, types: Iterable[str]) -> list[str]:
    """The descriptions of the violations of ``types``."""
    wanted = set(types)
    return [v.description for v in report.violations if v.type in wanted and not v.excluded]


def _inside(point: Point, pad: BoardPad) -> bool:
    """Whether ``point`` lies in the copper of ``pad`` on one of its layers (integer arithmetic)."""
    for copper in pad.copper:
        half = copper.width // 2
        core = copper.core
        if copper.filled and len(core) >= 3 and _in_ring(point, core):
            return True
        pairs = [(core[0], core[0])] if len(core) == 1 else list(zip(core, core[1:], strict=False))
        if any(_near(point, a, b, half) for a, b in pairs):
            return True
    return False


def _near(p: Point, a: Point, b: Point, half: int) -> bool:
    dx, dy = b.x - a.x, b.y - a.y
    length = dx * dx + dy * dy
    if length == 0:
        cx, cy = a.x, a.y
        return (p.x - cx) ** 2 + (p.y - cy) ** 2 <= half * half
    t_num = (p.x - a.x) * dx + (p.y - a.y) * dy
    t_num = max(0, min(length, t_num))
    # the squared distance to the closest point, scaled by ``length`` squared to stay in integers
    ex = (p.x - a.x) * length - t_num * dx
    ey = (p.y - a.y) * length - t_num * dy
    return ex * ex + ey * ey <= (half * length) ** 2


def _in_ring(p: Point, ring: Sequence[Point]) -> bool:
    inside = False
    for a, b in zip(ring, (*ring[1:], ring[0]), strict=True):
        if (a.y > p.y) != (b.y > p.y):
            # x of the crossing compared without division: sign of (p.x - x_cross) * (b.y - a.y)
            lhs = (p.x - a.x) * (b.y - a.y)
            rhs = (b.x - a.x) * (p.y - a.y)
            if (lhs < rhs) == (b.y > a.y):
                inside = not inside
    return inside


def vias_in_pads(design: Design, vias: Iterable[Via]) -> int:
    """How many of ``vias`` have their centre inside the copper of a surface pad."""
    pads = [pad for pad in board_pads(design) if pad.kind == "smd"]
    return sum(1 for via in vias if any(_inside(via.position, pad) for pad in pads))


def narrow(design: Design, nets: Iterable[str], width: int) -> list[int]:
    """The widths, sorted, of the tracks and arcs on ``nets`` narrower than ``width``."""
    assert design.board is not None
    wanted = set(nets)
    names = {net.id: net.name for net in design.circuit.nets}
    copper = (*design.board.tracks, *design.board.arcs)
    return sorted(
        item.width for item in copper if names.get(item.net_id or "") in wanted and item.width < width
    )


def record(tool: str, probe: str, value: str, detail: str) -> None:
    """Print one outcome; with ``FENOLITE_ROUTING_EVIDENCE=1`` also append it to the evidence page and write
    it to the results file of ``tool`` (``krt-v0.22.1`` or ``freerouting-2.4.1``)."""
    print(f"{probe}: {value}; {detail}")
    if os.environ.get(WRITE) != "1":
        return
    with EVIDENCE_PAGE.open("a", encoding="utf-8") as stream:
        stream.write(f"- `{probe}`: `{value}` ({detail}).\n")
    path = RESULTS / f"{tool}.json"
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    outcomes = data.get("outcomes")
    merged: dict[str, object] = dict(outcomes) if isinstance(outcomes, dict) else {}
    merged[probe] = {"value": value, "detail": detail}
    data["outcomes"] = dict(sorted(merged.items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


FREEROUTING_BASE = (
    "-mp", "20", "-mt", "1", "-da", "--gui.enabled=false", "--router.optimizer.enabled=false",
    "--router.automatic_neckdown=false",
)  # fmt: skip
"""What every Freerouting run of the gate passes: the plugin's passes, one thread, no analytics, no window,
and the two settings the plugin always passes since c0109 and c0110 (no optimizer, no automatic neck-down)."""


def freerouting(written: DsnResult, folder: Path, *settings: str) -> tuple[ToolRun, str | None]:
    """The pinned jar (``FENOLITE_FREEROUTING_JAR``, Java from ``FENOLITE_JAVA`` or ``PATH``) on the design
    file ``written`` in ``folder``, which is also its ``HOME``, with ``settings`` after the gate's own; the
    run and the session text (``None`` without one)."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "board.dsn").write_text(written.text, encoding="utf-8")
    java = os.environ.get("FENOLITE_JAVA") or shutil.which("java") or "java"
    jar = os.environ["FENOLITE_FREEROUTING_JAR"]
    command = [java, "-jar", jar, "-de", "board.dsn", "-do", "board.ses", *FREEROUTING_BASE, *settings]
    done = run_tool(command, folder, env={"HOME": str(folder)})
    session = folder / "board.ses"
    return done, session.read_text(encoding="utf-8") if session.is_file() else None


def session_board(
    board: Path, written: DsnResult, session: str, nets: Iterable[str], target: int, name: str
) -> tuple[Path, Design]:
    """``board`` with the session's copper on ``nets`` merged by ``routing.merge.apply``, written beside it
    as ``name`` with its project and rules files; returns the file and its design."""
    before = read_board(board.read_text(encoding="utf-8"))
    tracks, vias, issues = to_copper(
        read_session(session, file="board.ses"), written.names, selected=tuple(nets)
    )
    assert not [issue for issue in issues if issue.severity == "error"], issues
    design = apply(before, RoutingResult(tracks=tracks, vias=vias))
    out = board.with_name(f"{name}.kicad_pcb")
    out.write_text(write_board(design, target=target).text, encoding="utf-8")
    for suffix in (".kicad_pro", ".kicad_dru"):
        beside = board.with_suffix(suffix)
        if beside.is_file():
            shutil.copy2(beside, out.with_suffix(suffix))
    return out, design


def running_major() -> int:
    return runner().major()


__all__ = [
    "GATE_SECONDS",
    "KRT_TAG",
    "PAIR_TYPES",
    "ToolRun",
    "added_copper",
    "build",
    "copy_project",
    "drc",
    "error_types",
    "fan_out_planes",
    "findings_of",
    "freerouting",
    "krt",
    "krt_checkout",
    "merged_board",
    "mm",
    "narrow",
    "open_on",
    "record",
    "run_tool",
    "running_major",
    "session_board",
    "vias_in_pads",
]
