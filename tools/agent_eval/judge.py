# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The judge of the agent evaluation: a verdict from the files of a work folder (change c0081).

``judge(workdir, task, fenolite)`` runs five checks, all of them, and never stops at a failure:

- ``project``: the expected folder holds one board file and a ``.fenolite/`` model;
- ``check``: ``fenolite check <project> --json`` exits 0;
- ``nets``: the nets of the model, as groups of ``REF-PIN``, are the expected groups (names ignored);
- ``board``: the outline fits the size and the copper layer count is the expected one;
- ``outputs``: every expected file pattern matches a file.

The verdict is ``passed`` only when all five passed. When ``check`` could not run KiCad's stages because
no ``kicad-cli`` was found and the other four passed, it is ``unjudged``, never ``passed``. The judge
reads the work folder and writes nothing in it; it runs the ``fenolite`` it is given, not the call log.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from fenolite.backends.kicad.pcb import read_board
from fenolite.model import canonical
from fenolite.model.design import Design

from .tasks import Expect, Task, split_ref_pin

Status = Literal["passed", "failed", "unjudged"]
Fenolite = str | os.PathLike[str] | Sequence[str]
"""The executable to run: a path, or the first words of its command line."""

CHECKS = ("project", "check", "nets", "board", "outputs")
EXIT_TOOL_MISSING = 6
CHECK_TIMEOUT_S = 900
EDGE_LAYER = "Edge.Cuts"
COPPER_KIND = "copper"
MODEL_DIR = ".fenolite"
BOARD_SUFFIX = ".kicad_pcb"


@dataclass(frozen=True)
class Check:
    """One check of the judge."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Verdict:
    """What the judge decided."""

    status: Status
    checks: tuple[Check, ...]
    evidence_level: str | None
    """``evidence.level`` of the envelope of ``fenolite check``; ``None`` when it printed none."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence_level": self.evidence_level,
            "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks],
        }


@dataclass(frozen=True)
class Completed:
    """A finished command."""

    code: int
    stdout: str
    stderr: str


def command(fenolite: Fenolite) -> list[str]:
    """The first words of the command line that ``fenolite`` names."""
    if isinstance(fenolite, (str, os.PathLike)):
        return [os.fspath(fenolite)]
    return [os.fspath(word) for word in fenolite]


def run_command(argv: Sequence[str], cwd: Path) -> Completed:
    """Run one command and wait for it. The tests replace this function to stay in one process."""
    done = subprocess.run(
        list(argv),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=CHECK_TIMEOUT_S,
        check=False,
    )
    return Completed(done.returncode, done.stdout, done.stderr)


def _not_run(name: str, blocker: str) -> Check:
    return Check(name, False, f"not run: the check '{blocker}' did not pass")


def find_board(project: Path) -> Path | None:
    """The one board file of a project folder, or ``None`` when it holds none or several."""
    boards = sorted(path for path in project.glob(f"*{BOARD_SUFFIX}") if path.is_file())
    return boards[0] if len(boards) == 1 else None


def check_project(workdir: Path, expect: Expect) -> Check:
    project = workdir / expect.project
    if not project.is_dir():
        return Check("project", False, f"the folder {expect.project} does not exist")
    boards = sorted(path.name for path in project.glob(f"*{BOARD_SUFFIX}") if path.is_file())
    if len(boards) != 1:
        found = ", ".join(boards) if boards else "none"
        return Check("project", False, f"{expect.project} must hold exactly one board file, found: {found}")
    if not (project / MODEL_DIR).is_dir():
        return Check("project", False, f"{expect.project} holds no {MODEL_DIR} folder: it was not built")
    return Check("project", True, f"{expect.project}/{boards[0]}")


def _table(value: object) -> dict[str, Any]:
    """``value`` when it is a JSON object, else an empty one."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _rows(value: object) -> list[dict[str, Any]]:
    """The JSON objects of ``value`` when it is a list, else none."""
    items = cast("list[object]", value) if isinstance(value, list) else []
    return [cast("dict[str, Any]", item) for item in items if isinstance(item, dict)]


def _envelope(text: str) -> dict[str, Any]:
    try:
        return _table(json.loads(text))
    except json.JSONDecodeError:
        return {}


def _stage(envelope: dict[str, Any], name: str) -> dict[str, Any]:
    for stage in _rows(_table(envelope.get("result")).get("stages")):
        if stage.get("name") == name:
            return stage
    return {}


def check_check(workdir: Path, expect: Expect, fenolite: Fenolite) -> tuple[Check, str | None, bool]:
    """The ``check`` check, the evidence level of its envelope, and whether KiCad was missing."""
    done = run_command([*command(fenolite), "check", expect.project, "--json"], workdir)
    envelope = _envelope(done.stdout)
    found = _table(envelope.get("evidence")).get("level")
    level = found if isinstance(found, str) else None
    drc = _stage(envelope, "drc.kicad")
    skipped = drc.get("status") == "skipped" and "kicad-cli" in str(drc.get("reason", ""))
    if done.code == 0 and not skipped:
        return Check("check", True, f"exit 0, evidence {level}"), level, False
    if done.code == EXIT_TOOL_MISSING or skipped:
        detail = f"exit {done.code}: kicad-cli was not found, KiCad's stages did not run"
        return Check("check", False, detail), level, True
    codes = sorted(
        {
            str(issue.get("code"))
            for issue in _rows(envelope.get("issues"))
            if issue.get("severity") == "error"
        }
    )
    last = done.stderr.strip().splitlines()[-1] if done.stderr.strip() else ""
    said = ", ".join(codes) if codes else str(_envelope(last).get("code", "no error object"))
    return Check("check", False, f"exit {done.code}: {said}"), level, False


def model_groups(design: Design) -> tuple[set[frozenset[str]], set[str]]:
    """The nets of a model as sets of ``REF-PIN``, and every ``REF-PIN`` the model has.

    A member names a pin of its component by number; a member that names pins by their name stands for
    every pin of that name. A pin bonded to several pads is one entry: pads are not read here.
    """
    by_id = {component.id: component for component in design.circuit.components}
    pins = {f"{c.ref}-{pin.number}" for c in design.circuit.components for pin in c.pins}
    groups: set[frozenset[str]] = set()
    for net in design.circuit.nets:
        members: set[str] = set()
        for member in net.members:
            component = by_id.get(member.component_id)
            if component is None:
                continue
            numbers = {pin.number for pin in component.pins}
            if member.pin in numbers:
                members.add(f"{component.ref}-{member.pin}")
            else:
                named = [pin.number for pin in component.pins if pin.name == member.pin]
                members.update(f"{component.ref}-{number}" for number in named or [member.pin])
        if members:
            groups.add(frozenset(members))
    return groups, pins


def compare_nets(groups: set[frozenset[str]], expect: Expect) -> Check:
    """Compare the groups of a model with the expected ones; the detail names the pins that differ."""
    expected = {frozenset(group) for group in expect.nets.values()}
    if groups == expected:
        return Check("nets", True, f"{len(expected)} nets as expected")

    def partners(sets: set[frozenset[str]]) -> dict[str, frozenset[str]]:
        return {pin: group for group in sets for pin in group}

    have, want = partners(groups), partners(expected)
    wrong = sorted(pin for pin in have.keys() | want.keys() if have.get(pin) != want.get(pin))
    shown = ", ".join(wrong[:12]) + (f" and {len(wrong) - 12} more" if len(wrong) > 12 else "")
    return Check("nets", False, f"the nets differ at {shown}")


def check_nets(workdir: Path, expect: Expect) -> Check:
    try:
        design = canonical.load_dir(workdir / expect.project / MODEL_DIR)
    except Exception as error:  # a model the judge cannot read is a failed check, never a crash
        return Check("nets", False, f"the model of {expect.project} cannot be read: {type(error).__name__}")
    groups, pins = model_groups(design)
    listed = {entry for group in expect.nets.values() for entry in group}
    refs = {split_ref_pin(entry)[0] for entry in listed}
    missing = sorted(ref for ref in refs if not any(pin.startswith(f"{ref}-") for pin in pins))
    if missing:
        return Check("nets", False, f"the model has no part {', '.join(missing)}")
    return compare_nets(groups, expect)


def _mm(value: int) -> str:
    text = f"{value / 1_000_000:.3f}".rstrip("0").rstrip(".")
    return f"{text} mm"


def outline_box(design: Design) -> tuple[int, int] | None:
    """Width and height, in nanometres, of the box around the board outline; ``None`` without one."""
    board = design.board
    if board is None:
        return None
    xs: list[int] = []
    ys: list[int] = []
    if board.outline is not None:
        for point in board.outline.points:
            xs.append(point.x)
            ys.append(point.y)
    for graphic in board.graphics:
        if graphic.layer != EDGE_LAYER or not graphic.points:
            continue
        if graphic.kind == "circle" and len(graphic.points) >= 2:
            centre, rim = graphic.points[0], graphic.points[1]
            radius = math.ceil(math.hypot(rim.x - centre.x, rim.y - centre.y))
            xs += [centre.x - radius, centre.x + radius]
            ys += [centre.y - radius, centre.y + radius]
            continue
        for point in graphic.points:
            xs.append(point.x)
            ys.append(point.y)
    if not xs:
        return None
    return max(xs) - min(xs), max(ys) - min(ys)


def check_board(workdir: Path, expect: Expect) -> Check:
    path = find_board(workdir / expect.project)
    if path is None:
        return _not_run("board", "project")
    try:
        design = read_board(path)
    except Exception as error:  # a board the judge cannot read is a failed check, never a crash
        return Check("board", False, f"the board file cannot be read: {type(error).__name__}")
    box = outline_box(design)
    if box is None:
        return Check("board", False, "the board has no outline")
    layers = sum(1 for layer in design.board.layers if layer.kind == COPPER_KIND) if design.board else 0
    width, height = box
    limit_w, limit_h = expect.max_size
    fits = (width <= limit_w and height <= limit_h) or (width <= limit_h and height <= limit_w)
    said = f"{_mm(width)} by {_mm(height)}"
    limit = f"{_mm(limit_w)} by {_mm(limit_h)}"
    problems: list[str] = []
    if not fits:
        problems.append(f"the board is {said}, larger than {limit}")
    if layers != expect.copper_layers:
        problems.append(f"the board has {layers} copper layers, not {expect.copper_layers}")
    if problems:
        return Check("board", False, "; ".join(problems))
    return Check("board", True, f"{said} within {limit}, {layers} copper layers")


def check_outputs(workdir: Path, expect: Expect) -> Check:
    missing = [
        pattern for pattern in expect.outputs if not any(path.is_file() for path in workdir.glob(pattern))
    ]
    if missing:
        return Check("outputs", False, f"no file matches {', '.join(missing)}")
    return Check("outputs", True, f"{len(expect.outputs)} patterns matched")


def decide(checks: Sequence[Check], no_kicad: bool) -> Status:
    """The status of a verdict from its checks."""
    if all(check.passed for check in checks):
        return "passed"
    others = all(check.passed for check in checks if check.name != "check")
    return "unjudged" if no_kicad and others else "failed"


def judge(workdir: str | os.PathLike[str], task: Task, fenolite: Fenolite) -> Verdict:
    """Decide a run from what its work folder holds."""
    folder = Path(workdir)
    expect = task.expect
    project = check_project(folder, expect)
    level: str | None = None
    no_kicad = False
    if project.passed:
        check, level, no_kicad = check_check(folder, expect, fenolite)
        nets = check_nets(folder, expect)
        board = check_board(folder, expect)
    else:
        check, nets, board = (_not_run(name, "project") for name in ("check", "nets", "board"))
    checks = (project, check, nets, board, check_outputs(folder, expect))
    return Verdict(decide(checks, no_kicad), checks, level)
