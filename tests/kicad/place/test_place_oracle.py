# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement against the oracle (capability kicad-oracle, "Moved footprints pass the oracle"; change c0022):
the legality check names exactly the pairs that KiCad's ``courtyards_overlap`` names on a bench, and a blink
whose staged parts ``fenolite place`` put on the board keeps them through a rebuild."""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import _framebench
import _lenscases as lc
import _placecases as pc
import pytest
from _boards import mm
from _buildhelp import blink_variant

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.core.coords import Point
from fenolite.geometry import BBox
from fenolite.model.board import FootprintInstance, Side
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.placement import check

pytestmark = pytest.mark.needs_kicad
MM = 1_000_000
WIDTH = pc.WIDTH
BENCH: tuple[tuple[str, str, str, Side, int, float, float], ...] = (
    # reference, footprint, library, side, angle, x and y in mm
    ("T1", "Frame_Shapes", "Frame", "top", 0, 20, 20),
    ("T2", "Frame_Shapes", "Frame", "top", 0, 25.98, 20),  # overlaps T1 by 20 µm
    ("T3", "Frame_Shapes", "Frame", "top", 0, 31.98, 20),  # shares an edge with T2: clear
    ("B1", "Frame_Shapes", "Frame", "bottom", 0, 20, 20),  # under T1, on the other face: clear
    ("B2", "Frame_Loop", "Frame", "bottom", 30, 60, 20),
    ("B3", "Frame_Loop", "Frame", "bottom", 30, 61, 21),  # overlaps B2 widely
)
EXPECTED = {frozenset({"T1", "T2"}), frozenset({"B2", "B3"})}


def bench(target: int) -> Design:
    placed: list[tuple[Component, FootprintInstance]] = []
    for n, (ref, name, lib, side, angle, x, y) in enumerate(BENCH, start=1):
        at = mm(0, 0)
        component, footprint = _framebench._place(target, ref, name, lib, at, angle, side, n)  # pyright: ignore[reportPrivateUsage]
        position = Point(round(x * MM), round(y * MM))
        placed.append((component, dataclasses.replace(footprint, position=position)))
    return _framebench._design(placed, 90, 45)  # pyright: ignore[reportPrivateUsage]


def test_legality_matches_drc() -> None:
    target = pc.major()
    design = bench(target)
    assert design.board is not None
    names = {fp.id: footprint_ref(design, fp) for fp in design.board.footprints}
    outline = board_outline(design)
    assert outline.source == "model"
    issues = check(KicadBackend().placed_extents(design), outline.rings, names=names)
    assert {i.code for i in issues} == {"place.courtyard-overlap"}
    ours = {frozenset(i.where.split(",")) for i in issues}
    with tempfile.TemporaryDirectory() as tmp:
        report = _framebench.drc(pc.runner(), design, target, Path(tmp))
    assert report is not None
    refs = {fp.native_ids["kicad"]: names[fp.id] for fp in design.board.footprints}
    theirs = {
        frozenset(refs[item.uuid] for item in violation.items)
        for violation in report.violations
        if violation.type == "courtyards_overlap"
    }
    assert ours == theirs == EXPECTED
    assert len(report.of_type("courtyards_overlap")) == len(EXPECTED)


# --- placed, then rebuilt -----------------------------------------------------------------------------


def fenolite(cwd: Path, *args: str) -> tuple[int, dict[str, Any]]:
    """``(exit code, envelope)`` of ``fenolite … --json`` run in ``cwd``."""
    command = [sys.executable, "-m", "fenolite", *args, "--json"]
    run = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=600, check=False)
    return run.returncode, json.loads(run.stdout) if run.stdout.strip() else {}


def project_files(folder: Path) -> dict[str, str | bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and ".fenolite" not in path.relative_to(folder).parts
    }


def all_files(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and not path.name.endswith(".bak")
    }


def test_placed_then_rebuilt(tmp_path: Path) -> None:
    target = str(pc.major())
    script = blink_variant(tmp_path / "src")
    text = script.read_text(encoding="utf-8")
    for line in ("r1.place(mm(32), mm(9))\n", 'd1.place(mm(38), mm(20), side="bottom")\n'):
        assert line in text
        text = text.replace(line, "")
    script.write_text(text, encoding="utf-8")
    out = tmp_path / "out"
    build = ("build", str(script), "--out", str(out), "--kicad-version", target, "--confirm")
    code, env = fenolite(tmp_path, *build)
    assert code == 0, env.get("issues")
    assert sorted(env["result"]["staged"]) == ["D1", "R1"]

    code, env = fenolite(tmp_path, "place", str(out), "--strategy", "grid", "--confirm")
    assert code == 0, env.get("issues")
    assert [row["ref"] for row in env["result"]["moved"]] == ["D1", "R1"] and env["result"]["unplaced"] == []
    assert env["result"]["legality"] == {}
    placed = lc.positions((out / lc.BOARD).read_text(encoding="utf-8"))
    design = read_board(out / lc.BOARD)
    region = BBox.of_points(board_outline(design).rings[0])
    assert all(region.contains_point(placed[ref][0]) for ref in ("D1", "R1"))  # type: ignore[index]

    code, env = fenolite(tmp_path, *build)
    assert code == 0, env.get("issues")
    assert not [i for i in env["issues"] if i["code"] == "layout.unplaced"]
    assert env["result"]["staged"] == []
    no_rule = {"near": {"judged": 0, "failed": 0, "skipped": 0}}  # the guard also counts the rules (c0113)
    assert env["result"]["placement"] == {"ran": True, "counts": {}, "rules": no_rule}
    rebuilt = lc.positions((out / lc.BOARD).read_text(encoding="utf-8"))
    assert rebuilt == placed
    first = all_files(out)

    code, env = fenolite(tmp_path, *build)
    assert code == 0, env.get("issues")
    assert all_files(out) == first

    # the oracle reads the parts where the placer put them, and its own courtyard check is silent
    rows = lc.pos_rows(project_files(out))
    for ref in ("D1", "R1", "U1"):
        at, rotation, side = placed[ref]  # type: ignore[misc]
        row = rows[ref]
        assert (row.position, row.rotation, row.side) == (at, rotation, side)  # type: ignore[attr-defined]
    report = lc.drc(project_files(out))
    assert report is not None and not report.of_type("courtyards_overlap")
