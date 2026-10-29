# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The frame-budget measurement of the viewer page (change c0245, decision 7): a script run in the page of
the stress board by the harness, and its reply's summary.

Each frame is the page's own ``draw()``, or a mouse event, followed by a one-pixel ``getImageData``, which
makes Chromium rasterise the canvas before the clock stops; ``tests/visual/budget.js`` says what each figure
measures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

SCRIPT = (Path(__file__).resolve().parent / "visual" / "budget.js").read_text(encoding="utf-8")


def summary(result: dict[str, Any]) -> str:
    """One line for the log."""
    message = result.get("message_ms")
    return (
        f"open {result['open_ms']:.0f} ms; pan/zoom event p95 {result['frame_p95_ms']:.1f} ms "
        f"(median {result['frame_median_ms']:.1f}, {result['interactive_board_paints']} board paints); "
        f"full draw p95 {result['full_p95_ms']:.1f} ms (median {result['full_median_ms']:.1f}); "
        f"cursor p95 {result['cursor_p95_ms']:.2f} ms ({result['board_paints_during_moves']} board paints); "
        + (f"message click {message:.1f} ms; " if message is not None else "")
        + f"{result['prims']} primitives on {result['width']:.0f} x {result['height']:.0f} px"
    )


__all__ = ["SCRIPT", "summary"]
