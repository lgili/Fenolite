# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The finished projects of the v0.1 acceptance loop, judged on the running ``kicad-cli`` (capability
release-gate, "Finished boards pass on both majors"; change c0025).

``tests/data/acceptance/<example>_t<major>/`` holds what ``tests/routing/test_acceptance_loop.py``
recorded. A project for KiCad 10 is skipped on ``kicad-cli`` 9.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from _checkrun import check, cli_path, stage
from _probes import major

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad

ROOT = Path(__file__).resolve().parents[3]
RECORDED = ROOT / "tests" / "data" / "acceptance"
PROJECTS = sorted(path.name for path in RECORDED.iterdir() if path.is_dir()) if RECORDED.is_dir() else []
SEED = ("--seed", "250025", "--timestamp", "2026-10-04T00:00:00Z")
JUDGED = ("model.validate", "erc.lite", "drc.kicad", "netlist.assignment_compare", "roundtrip")
COPPER = ("(segment", "(arc", "(via", "(zone")
NET = re.compile(r'\(net (?:\d+ )?"[^"]*"\)')


def _split(name: str) -> tuple[str, int]:
    example, _, target = name.rpartition("_t")
    return example, int(target)


def _copy(name: str, tmp_path: Path) -> tuple[Path, Path, str, int]:
    """A copy of the recorded project: its folder, its board, the example and the KiCad major."""
    example, target = _split(name)
    if target > major():
        pytest.skip(f"target {target} on kicad-cli {major()}")
    folder = tmp_path / name
    shutil.copytree(RECORDED / name, folder)
    board = next(folder.glob("*.kicad_pcb"))
    return folder, board, example, target


def _fenolite(cwd: Path, *args: str) -> tuple[int, dict[str, Any], str]:
    run = subprocess.run(
        [sys.executable, "-m", "fenolite", *args, "--json"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    return run.returncode, json.loads(run.stdout) if run.stdout.strip() else {}, run.stderr


def _build(folder: Path, example: str, target: int, mode: str) -> tuple[int, dict[str, Any], str]:
    script = ROOT / "examples" / example / "design.py"
    return _fenolite(
        folder.parent, "build", str(script), "--out", str(folder), "--kicad-version", str(target),
        *SEED, mode, "--no-backup",
    )  # fmt: skip


def _files(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.suffix != ".kicad_prl" and ".fenolite" not in path.parts
    }


def _top_level(text: str, heads: tuple[str, ...]) -> list[str]:
    """The top-level lists of a board file that start with one of ``heads``, as written."""
    found: list[str] = []
    depth, start = 0, 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
            if depth == 2:
                start = index
        elif char == ")":
            if depth == 2 and text.startswith(heads, start):
                found.append(text[start : index + 1])
            depth -= 1
    return found


def _mm(value: int) -> str:
    return f"{value / 1_000_000:.6f}".rstrip("0").rstrip(".")


@pytest.mark.parametrize("name", PROJECTS)
def test_check(name: str, tmp_path: Path) -> None:
    """Item 1: no DRC violation, no unconnected item, no net-assignment difference, an equal round trip."""
    folder, _board, _example, _target = _copy(name, tmp_path)
    code, envelope, _out, error = check(folder)
    assert code == 0, error or envelope.get("issues")
    for judged in JUDGED:
        assert stage(envelope, judged)["status"] == "ok", stage(envelope, judged)
    drc = stage(envelope, "drc.kicad")["summary"]
    assert drc["violations"] == 0 and drc["unconnected"] == 0 and drc["canary"] == "fired", drc
    assert not [issue for issue in envelope["issues"] if issue["severity"] == "error"]


@pytest.mark.parametrize("name", PROJECTS)
def test_rebuild_is_the_identity(name: str, tmp_path: Path) -> None:
    """Item 1: a second build keeps the fills and the routes, byte for byte."""
    folder, _board, example, target = _copy(name, tmp_path)
    recorded = _files(folder)
    code, envelope, error = _build(folder, example, target, "--dry-run")
    assert code == 0, error
    plan = [write for write in envelope["result"]["plan"] if "/.fenolite/" not in write["path"]]
    assert plan, "a build lists the files of the project"
    changed = [
        Path(write["path"]).name
        for write in plan
        if not Path(write["path"]).is_file()
        or hashlib.sha256(Path(write["path"]).read_bytes()).hexdigest() != write["sha256"]
    ]
    assert not changed, f"the build plans new bytes for {changed}"
    for _ in range(2):
        code, envelope, error = _build(folder, example, target, "--confirm")
        assert code == 0, error
        assert _files(folder) == recorded


@pytest.mark.parametrize("name", PROJECTS)
def test_moved_footprint_survives_a_rebuild(name: str, tmp_path: Path) -> None:
    """Item 1: a footprint moved on the board keeps its position through a rebuild, and the copper is
    untouched."""
    folder, board, example, target = _copy(name, tmp_path)
    design = read_board(board.read_text(encoding="utf-8"), file=board.name)
    outline = board_outline(design)
    assert outline, "the built board has a closed outline"
    left = min(point.x for ring in outline for point in ring)
    top = min(point.y for ring in outline for point in ring)
    r1 = next(pad for pad in board_pads(design) if pad.ref == "R1" and pad.number == "1")
    assert design.board is not None
    footprint = next(fp for fp in design.board.footprints if fp.id == r1.footprint_id)
    wanted = (footprint.position.x - left + 1_000_000, footprint.position.y - top + 500_000)
    move = f"R1={_mm(wanted[0])}mm,{_mm(wanted[1])}mm"
    code, envelope, error = _fenolite(
        folder, "place", board.name, "--strategy", "manual", "--move", move, "--force", *SEED,
        "--confirm", "--no-backup",
    )  # fmt: skip
    assert code in (0, 5), error or envelope
    moved_text = board.read_text(encoding="utf-8")
    before = _top_level(moved_text, COPPER)
    assert before
    code, envelope, error = _build(folder, example, target, "--confirm")
    assert code == 0, error
    rebuilt_text = board.read_text(encoding="utf-8")
    assert _top_level(rebuilt_text, COPPER) == before
    rebuilt = read_board(rebuilt_text, file=board.name)
    assert rebuilt.board is not None
    again = next(fp for fp in rebuilt.board.footprints if fp.id == footprint.id)
    assert (again.position.x - left, again.position.y - top) == wanted


def _r1_pad_net(text: str, number: str) -> tuple[int, int]:
    """The span of the ``(net …)`` token of pad ``number`` of ``R1`` in a board file."""
    start = text.index('(property "Reference" "R1"')
    pad = text.index(f'(pad "{number}"', start)
    found = NET.search(text, pad)
    assert found is not None
    return found.start(), found.end()


@pytest.mark.parametrize("name", PROJECTS)
def test_renetted_pad_is_detected(name: str, tmp_path: Path) -> None:
    """Negative test: pad 1 of ``R1`` on the net ``GND`` makes ``check`` exit 5 and name ``R1``."""
    folder, board, _example, _target = _copy(name, tmp_path)
    text = board.read_text(encoding="utf-8")
    ground = re.search(r'\(net (?:\d+ )?"GND"\)', text)
    assert ground is not None
    begin, end = _r1_pad_net(text, "1")
    assert text[begin:end] != ground.group(0)
    board.write_text(text[:begin] + ground.group(0) + text[end:], encoding="utf-8")
    code, envelope, _out, error = check(folder)
    assert code == 5, error
    errors = [issue for issue in envelope["issues"] if issue["severity"] == "error"]
    assert any("R1" in issue["where"] for issue in errors), errors


@pytest.mark.parametrize("name", PROJECTS)
def test_track_between_two_nets_is_detected(name: str, tmp_path: Path) -> None:
    """Negative test: a track from pad 1 to pad 2 of ``R1`` makes ``check`` exit 5 and name ``R1``."""
    folder, board, _example, _target = _copy(name, tmp_path)
    text = board.read_text(encoding="utf-8")
    design = read_board(text, file=board.name)
    ends = {pad.number: pad.position for pad in board_pads(design) if pad.ref == "R1"}
    begin, end = _r1_pad_net(text, "1")
    template = _top_level(text, ("(segment",))[0]
    bridge = re.sub(r"\(start [^)]*\)", f"(start {_mm(ends['1'].x)} {_mm(ends['1'].y)})", template)
    bridge = re.sub(r"\(end [^)]*\)", f"(end {_mm(ends['2'].x)} {_mm(ends['2'].y)})", bridge)
    bridge = re.sub(r'\(layer "[^"]*"\)', '(layer "F.Cu")', bridge)
    bridge = NET.sub(text[begin:end], bridge)
    bridge = re.sub(r'\(uuid "[^"]*"\)', '(uuid "0c0025aa-0000-4000-8000-00000000c025")', bridge)
    where = text.index(template)
    board.write_text(text[:where] + bridge + "\n\t" + text[where:], encoding="utf-8")
    code, envelope, _out, error = check(folder)
    assert code == 5, error
    errors = [issue for issue in envelope["issues"] if issue["severity"] == "error"]
    assert any("R1" in issue["where"] for issue in errors), errors


@pytest.mark.parametrize("name", PROJECTS)
def test_exports_and_views_are_planned(name: str, tmp_path: Path) -> None:
    folder, board, _example, _target = _copy(name, tmp_path)
    out = tmp_path / "out"
    for args in (("export", "--all", "--manifest"), ("render", "--svg")):
        code, envelope, error = _fenolite(
            folder, args[0], board.name, "-o", str(out / args[0]), *args[1:], "--kicad-cli", cli_path(),
            "--dry-run",
        )  # fmt: skip
        assert code == 0, error
        assert envelope["result"]["plan"], args


def test_four_projects_are_recorded() -> None:
    assert PROJECTS == ["blink_2layer_t10", "blink_2layer_t9", "board_40parts_t10", "board_40parts_t9"]
