# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite silk --clip`` (change c0226; capability silkscreen-layout, "Silkscreen clipping", "Clipped
strokes checked", "Clipped footprints and their library" and "Clip options"), on the authored benches of
``tests/_silkbench.py``. Hermetic: no subprocess may start.

The pads the assertions measure against are written here again, apart from ``fenolite.silk``: the two
pads of ``BOXED`` at 0 degrees, and distances from sampled points of each stroke to their rectangles."""

from __future__ import annotations

import io
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _silkbench import BOXED, SilkBoard, clipped, row
from _ties import MM

import fenolite.silk.clip as silk_clip
from fenolite.backends.kicad.fpitems import footprint_items
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.cli import main as cli_main
from fenolite.core.coords import Point
from fenolite.library import derive_library, drift
from fenolite.model.board import Graphic
from fenolite.model.design import Design
from fenolite.silk.cut import Cut, Piece

UM = 1_000
Box = tuple[int, int, int, int]
RULE = '(version 1)\n(rule "silk" (constraint silk_clearance (min 0.1mm)))\n'


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _write(folder: Path, design: Design, name: str = "silk", *, rule: bool = False) -> Path:
    board = folder / f"{name}.kicad_pcb"
    board.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    project = synthesize_project(design, target=10, board_name=name)
    board.with_suffix(".kicad_pro").write_text(project, encoding="utf-8", newline="\n")
    if rule:
        board.with_suffix(".kicad_dru").write_text(RULE, encoding="utf-8", newline="\n")
    return board


def silk(
    monkeypatch: pytest.MonkeyPatch, folder: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    monkeypatch.chdir(folder)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["silk", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")


def one_boxed() -> Design:
    bench = SilkBoard(width=20 * MM, height=20 * MM)
    bench.place("U1", Point(10 * MM, 10 * MM), defn=BOXED, ref_at=Point(10 * MM, 13 * MM))
    return bench.build()


def _pads_at(at: Point) -> list[Box]:
    """The two pads of ``BOXED`` at 0 degrees: 0.9 mm x 1 mm at x = -0.8 mm and +0.8 mm."""
    return [
        (at.x + d - 450 * UM, at.y - 500 * UM, at.x + d + 450 * UM, at.y + 500 * UM)
        for d in (-800 * UM, 800 * UM)
    ]


def _samples(graphic: Graphic, at: Point) -> list[tuple[float, float]]:
    """Points every 10 µm or less along a line or an arc of a footprint at ``at`` turned by 0 degrees."""
    pts = [(at.x + p.x, at.y + p.y) for p in graphic.points]
    if graphic.kind == "line":
        (ax, ay), (bx, by) = pts
        n = max(2, int(math.hypot(bx - ax, by - ay) / (10 * UM)) + 1)
        return [(ax + (bx - ax) * k / n, ay + (by - ay) * k / n) for k in range(n + 1)]
    assert graphic.kind == "arc", graphic.kind
    (sx, sy), (mx, my), (ex, ey) = pts
    d = 2 * (sx * (my - ey) + mx * (ey - sy) + ex * (sy - my))
    cx = ((sx**2 + sy**2) * (my - ey) + (mx**2 + my**2) * (ey - sy) + (ex**2 + ey**2) * (sy - my)) / d
    cy = ((sx**2 + sy**2) * (ex - mx) + (mx**2 + my**2) * (sx - ex) + (ex**2 + ey**2) * (mx - sx)) / d
    r = math.hypot(sx - cx, sy - cy)
    a0, am, a1 = (math.atan2(y - cy, x - cx) for x, y in ((sx, sy), (mx, my), (ex, ey)))

    def ccw(a: float, b: float) -> float:
        return (b - a) % (2 * math.pi)

    span = ccw(a0, a1)
    sign = 1.0 if ccw(a0, am) < span else -1.0
    sweep = span if sign > 0 else 2 * math.pi - span
    n = max(2, int(sweep * r / (10 * UM)) + 1)
    return [
        (cx + r * math.cos(a0 + sign * sweep * k / n), cy + r * math.sin(a0 + sign * sweep * k / n))
        for k in range(n + 1)
    ]


def _gap(x: float, y: float, box: Box) -> float:
    dx = max(box[0] - x, 0.0, x - box[2])
    dy = max(box[1] - y, 0.0, y - box[3])
    return math.hypot(dx, dy)


def test_outline_over_a_pad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Outline over a pad": no stroke's ink comes into a pad, and one footprint is reported."""
    board = _write(tmp_path, one_boxed())
    code, env, err = silk(monkeypatch, tmp_path, board.name, "--clip", "--confirm")
    assert code == 0, err
    result = env["result"]
    assert result["changed"] is True and result["clip"]["margin"] == 0
    assert result["clip"]["items"] == 3 and result["clip"]["cuts"][0]["by"] == ["own"]
    assert [found["code"] for found in env["issues"]] == ["silk.footprint-changed"]
    assert result["library"]["changed"] == ["Silk:BOXED"]
    assert env["evidence"]["level"] == "INFERRED"
    assert env["evidence"]["hypotheses"] == ["H-K-SILK-CLIP", "H-K-SILK-MASK"]
    written = read_board(board.read_text(encoding="utf-8"), file=board.name)
    assert written.board is not None
    footprint = written.board.footprints[0]
    strokes = [g for g in footprint_items(footprint).graphics if g.layer == "F.SilkS"]
    assert len(strokes) == result["clip"]["pieces"] >= 4
    assert {g.kind for g in strokes} == {"line", "arc"}
    for graphic in strokes:
        half = graphic.width / 2
        for x, y in _samples(graphic, footprint.position):
            assert all(_gap(x, y, box) >= half - 1 for box in _pads_at(footprint.position)), (graphic, x, y)
    # a second run finds nothing to cut
    code, env, err = silk(monkeypatch, tmp_path, board.name, "--clip", "--dry-run")
    assert code == 0, err
    assert env["result"]["clip"]["items"] == 0 and env["result"]["changed"] is False and env["issues"] == []


def test_untouched_board_is_not_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _write(tmp_path, row(3))
    before = board.read_bytes()
    code, env, err = silk(monkeypatch, tmp_path, board.name, "--clip", "--confirm")
    assert code == 0, err
    assert env["result"]["changed"] is False and env["result"]["library"] is None
    assert board.read_bytes() == before


def test_library_one_footprint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "One footprint for the library": U1 to U3 (0, 90, 30 degrees) give one footprint, U4,
    crossed by TP1's pad, is cut by another part's opening and differs."""
    board = _write(tmp_path, clipped(("top",)))
    original = board.read_text(encoding="utf-8")
    code, env, err = silk(monkeypatch, tmp_path, board.name, "--clip", "--confirm")
    assert code == 0, err
    codes = [found["code"] for found in env["issues"]]
    assert codes.count("silk.footprint-changed") == 1 and codes.count("silk.cut-by-other") == 1
    other = next(found for found in env["issues"] if found["code"] == "silk.cut-by-other")
    assert other["where"] == "U4" and "TP1" in other["message"]
    rows = {row["owner"]: row["by"] for row in env["result"]["clip"]["cuts"]}
    assert rows == {"U1": ["own"], "U2": ["own"], "U3": ["own"], "U4": ["own", "other"]}
    derived = derive_library(board.read_text(encoding="utf-8"), library="lib", target=10)
    groups = {fp.refs for fp in derived.footprints if fp.source.endswith("BOXED")}
    assert groups == {("U1", "U2", "U3"), ("U4",)}, groups
    old = tmp_path / "old.pretty"
    old.mkdir()
    for name, body in derive_library(original, library="old", target=10).files().items():
        (old / name).write_text(body, encoding="utf-8", newline="\n")
    kinds = dict(drift(derived, old))
    clean = next(fp.name for fp in derived.footprints if fp.refs == ("U1", "U2", "U3"))
    assert "silkscreen" in kinds[clean]


def test_check_failed_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A piece that crosses a pad fails the check: exit 5, ``silk.check-failed``, the board unchanged."""
    board = _write(tmp_path, one_boxed())
    before = board.read_bytes()
    across = Piece((Point(9 * MM, 10 * MM), Point(11 * MM, 10 * MM)))  # through both pads

    def bad(*args: object, **kwargs: object) -> Cut:
        return Cut((across,))

    monkeypatch.setattr(silk_clip, "cut", bad)
    code, env, _ = silk(monkeypatch, tmp_path, board.name, "--clip", "--confirm")
    assert code == 5
    assert "silk.check-failed" in [found["code"] for found in env["issues"]]
    assert board.read_bytes() == before


def test_margin_rule_option_and_refusals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Margin and refusals"."""
    board = _write(tmp_path, one_boxed(), rule=True)
    code, env, err = silk(monkeypatch, tmp_path, board.name, "--clip", "--dry-run")
    assert code == 0, err
    assert env["result"]["clip"]["margin"] == 100 * UM and env["result"]["clip"]["margin_source"] == "rule"
    code, env, err = silk(monkeypatch, tmp_path, board.name, "--clip", "--margin", "0.2mm", "--dry-run")
    assert code == 0, err
    assert env["result"]["clip"]["margin"] == 200 * UM and env["result"]["clip"]["margin_source"] == "option"
    for args in (("--clip", "--margin", "-1mm"), ("--margin", "0.1mm", "--designators"), ()):
        code, _, err = silk(monkeypatch, tmp_path, board.name, *args, "--dry-run")
        assert code == 2, (args, err)


def test_both_clip_then_designators(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Margin and refusals": both options together, the clip first."""
    board = _write(tmp_path, clipped(("top",)))
    code, env, err = silk(
        monkeypatch, tmp_path, board.name, "--clip", "--designators", "--measure", "estimate", "--confirm"
    )
    assert code == 0, err
    result = env["result"]
    assert result["clip"]["items"] > 0 and result["changed"] is True
    # TP1 lies inside U4's courtyard, so its designator has no free place (silk.no-place)
    statuses = {row["ref"]: row["status"] for row in result["placements"]}
    assert statuses == {"U1": "placed", "U2": "placed", "U3": "placed", "U4": "placed", "TP1": "unplaced"}
    assert env["evidence"]["hypotheses"] == [
        "H-K-SILK-CLIP",
        "H-K-SILK-MASK",
        "H-K-SILK-DRC",
        "H-K-SILK-ESTIMATE",
    ]
