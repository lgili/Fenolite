# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The final cut is exact, realized by selective snap rounding, and refuses without a fallback (c0332)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from fenolite.api import run
from fenolite.backends.altium.pour import _certified_neck_cut
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.vector import Point


def rectangle(x0: int, y0: int, x1: int, y1: int) -> Polygon:
    return Polygon((Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)))


def test_actual_caller_tests_whole_piece_before_hole() -> None:
    assert _certified_neck_cut((rectangle(0, 0, 3, 3),), (rectangle(1, 1, 2, 2),), 3) == ()
    result = _certified_neck_cut((rectangle(0, 0, 10, 10),), (rectangle(2, 2, 8, 8),), 1)
    assert len(result) == 1 and len(result[0].holes) == 1 and result[0].area2 == 128


def test_input_limit_refuses_when_no_seam_can_split_the_arrangement() -> None:
    # one cut piece spans every subject vertex: no strip seam exists, so the cap still refuses
    with pytest.raises(GeometryError, match="input-edge budget"):
        _certified_neck_cut((rectangle(0, 0, 10, 10),) * 25_001, (rectangle(-1, -1, 11, 11),), 1)


def test_sub_nanometre_source_turn_is_flattened_not_refused() -> None:
    # The exact boundary turns at the source vertex (0, 0) by a quarter nanometre over one: its neighbour
    # (-1, 1/4) rounds to (-1, 0). The vertex keeps its coordinate on a straight realized edge.
    subject = Polygon((Point(-4, 1), Point(0, 0), Point(4, 0), Point(4, 2), Point(-4, 2)))
    result = _certified_neck_cut((subject,), (rectangle(-5, -5, -1, 5), rectangle(1, -5, 5, 5)), 1)
    assert result == (rectangle(-1, 0, 1, 2),)


@pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")
def test_build_calls_the_exact_cut_and_refuses_without_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fenolite.geometry.boolean import _exact_cut

    def refuse(*args: object, **kwargs: object) -> None:
        raise GeometryError("planted exact final neck cut refusal")

    monkeypatch.setattr(_exact_cut, "exact_difference", refuse)
    output = tmp_path / "output"
    script = Path(__file__).resolve().parents[4] / "examples/board_40parts/design.py"
    before = script.read_bytes()
    reply = run(
        "build",
        str(script),
        "--out",
        str(output),
        "--target",
        "altium",
        "--dry-run",
        cwd=tmp_path,
        seed=1,
        timestamp="2026-01-01T00:00:00Z",
    )
    # Reconnected by the c0332 redesign: the refusal reaches the build, which writes and plans nothing.
    assert reply.exit_code != 0
    assert "planted exact final neck cut refusal" in str(reply.error)
    assert not output.exists() and script.read_bytes() == before
