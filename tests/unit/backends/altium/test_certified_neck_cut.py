# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scoped final cut applies the real policy and refuses without a fallback (c0332)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from fenolite.api import run
from fenolite.backends.altium.pour import _certified_neck_cut
from fenolite.geometry.boolean._exact_realization import Projection
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.vector import Point


def rectangle(x0: int, y0: int, x1: int, y1: int) -> Polygon:
    return Polygon((Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)))


def test_actual_caller_tests_whole_piece_before_hole() -> None:
    assert _certified_neck_cut((rectangle(0, 0, 3, 3),), (rectangle(1, 1, 2, 2),), 3) == ()
    result = _certified_neck_cut((rectangle(0, 0, 10, 10),), (rectangle(2, 2, 8, 8),), 1)
    assert len(result) == 1 and len(result[0].holes) == 1 and result[0].area2 == 128


def test_input_limit_refuses_before_large_exact_arrangement() -> None:
    with pytest.raises(GeometryError, match="input-edge budget"):
        _certified_neck_cut((rectangle(0, 0, 10, 10),) * 2501, (), 1)


def test_real_unrepresentable_corner_refuses_without_fallback() -> None:
    subject = Polygon((Point(-4, 1), Point(0, 0), Point(4, 0), Point(4, 2), Point(-4, 2)))
    with pytest.raises(GeometryError, match="protected source vertex missing"):
        _certified_neck_cut((subject,), (rectangle(-5, -5, -1, 5), rectangle(1, -5, 5, 5)), 1)


@pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")
def test_certificate_refusal_is_cli_bad_input_and_stages_no_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise GeometryError("planted final neck certificate refusal")

    monkeypatch.setattr(Projection, "certify", refuse)
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
    assert reply.exit_code == 3
    assert reply.error is not None and reply.error["code"] == "FEN-3005"
    assert "planted final neck certificate refusal" in reply.error["message"]
    assert not reply.result.get("plan")
    assert not output.exists() and script.read_bytes() == before
