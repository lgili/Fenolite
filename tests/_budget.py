# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The frame-budget measurement of the viewer page (change c0245, decision 7): a script run in the page of
the stress board by the harness, and its reply's summary.

Each frame is the page's own ``draw()`` followed by a one-pixel ``getImageData``, which makes Chromium
rasterise the canvas before the clock stops. Pan and zoom alternate over 120 frames. Pointer moves are 200
``mousemove`` events over the canvas; the board layers painted during them are counted through
``paintCache``. The open time is ``performance.now()`` when the harness sees the scene loaded, an upper
bound of the first full draw.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

SCRIPT = (Path(__file__).resolve().parent / "visual" / "budget.js").read_text(encoding="utf-8")


def summary(result: dict[str, Any]) -> str:
    """One line for the log."""
    return (
        f"open {result['open_ms']:.0f} ms; frame p95 {result['frame_p95_ms']:.1f} ms "
        f"(median {result['frame_median_ms']:.1f}); cursor p95 {result['cursor_p95_ms']:.2f} ms "
        f"(median {result['cursor_median_ms']:.2f}); board paints during 200 moves "
        f"{result['board_paints_during_moves']}; {result['prims']} primitives on "
        f"{result['width']:.0f} x {result['height']:.0f} px"
    )


__all__ = ["SCRIPT", "summary"]
