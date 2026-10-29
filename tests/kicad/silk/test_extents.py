# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ink of stroke texts measured with the running ``kicad-cli`` (change c0212; capability
silkscreen-layout, "Text ink extents"; hypotheses ``H-K-SILK-INK`` and ``H-K-SILK-ESTIMATE``;
``docs/formats/kicad/text.md``)."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from _probes import major, runner

from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.textink import board_texts, measure_ink
from fenolite.core.coords import Point, Size
from fenolite.core.evidence import Level
from fenolite.model.board import Outline, Text
from fenolite.model.design import Design
from fenolite.silk.extents import InkBox, InkCache, TextKey, estimate, glyph_table, ink_box

pytestmark = pytest.mark.needs_kicad
MM = 1_000_000
CLOSE = 10_000
"""10 µm: what the scenario allows between the estimate and a render."""
DESIGNATORS = ("R12", "C100", "U7", "IC3", "J1", "TP14", "D2", "Q10", "SW3", "FB1", "LED5", "R_1", "X1.2")
ROOT = Path(__file__).resolve().parents[3]


class _Counted:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, keys: Sequence[TextKey]) -> Mapping[TextKey, InkBox | None]:
        self.calls += 1
        requests = {(k.text, k.width, k.height, k.stroke, k.h_justify, k.v_justify): k for k in keys}
        boxes = measure_ink(runner(), list(requests), major=major())
        return {key: None if boxes[r] is None else InkBox(*boxes[r]) for r, key in requests.items()}  # type: ignore[misc]


def _board_text(tmp_path: Path, text: str, at: Point) -> Path:
    """A board that holds one ``gr_text`` on ``F.SilkS``, written for the tool's major."""
    base = Design.new("ink", seed=0)
    assert base.board is not None
    board = dataclasses.replace(
        base.board,
        outline=Outline(
            id="out_1", points=(Point(0, 0), Point(40 * MM, 0), Point(40 * MM, 30 * MM), Point(0, 30 * MM))
        ),
        layers=created_layers(2),
        texts=(
            Text(id="txt_1", text=text, position=at, layer="F.SilkS", size=Size(MM, MM), thickness=150_000),
        ),
    )
    path = tmp_path / "ink.kicad_pcb"
    path.write_text(
        write_board(dataclasses.replace(base, board=board), target=major()).text, encoding="utf-8"
    )
    return path


def test_r12(tmp_path: Path) -> None:
    """Scenario "Extent of a designator": ``R12`` at 1 mm with a 0.15 mm stroke equals the ink of the same
    text drawn on a board within 10 µm, the estimate agrees within 10 µm, and a second call reads the
    cache."""
    tool = _Counted()
    version = f"kicad-cli {runner().version()}"
    cache = InkCache(tmp_path / "cache")
    first = ink_box("R12", size=(MM, MM), stroke=150_000, measure=tool, tool=version, cache=cache)
    assert first.level is Level.KICAD_VERIFIED and first.box is not None and tool.calls == 1
    at = Point(20 * MM, 15 * MM)
    (drawn,) = board_texts(runner(), _board_text(tmp_path, "R12", at), ["F.SilkS"])
    x0, y0, x1, y1 = drawn.ink
    seen = (x0 - at.x, y0 - at.y, x1 - at.x, y1 - at.y)
    box = first.box
    assert all(abs(a - b) <= CLOSE for a, b in zip((box.x0, box.y0, box.x1, box.y1), seen, strict=True))
    guess = estimate(TextKey("R12", MM, MM, 150_000))
    assert guess is not None
    assert all(
        abs(a - b) <= CLOSE for a, b in zip((guess.x0, guess.y0, guess.x1, guess.y1), seen, strict=True)
    )
    again = ink_box(
        "R12", size=(MM, MM), stroke=150_000, measure=tool, tool=version, cache=InkCache(tmp_path / "cache")
    )
    assert again.source == "cache" and again.box == first.box and tool.calls == 1


@pytest.mark.parametrize("width", [600_000, 1_000_000, 1_270_000])
@pytest.mark.parametrize(
    ("stroke", "justify"),
    [(100_000, ("center", "center")), (150_000, ("left", "top")), (300_000, ("right", "bottom"))],
)
def test_the_estimate_holds_the_render(width: int, stroke: int, justify: tuple[str, str]) -> None:
    """For usual designators, at three widths, strokes and justifications, the estimate holds the rendered
    ink and is within 10 µm of it (``H-K-SILK-ESTIMATE``)."""
    keys = [TextKey(text, width, MM, stroke, *justify) for text in DESIGNATORS]  # type: ignore[arg-type]
    requests = [(k.text, k.width, k.height, k.stroke, k.h_justify, k.v_justify) for k in keys]
    boxes = measure_ink(runner(), requests, major=major())  # type: ignore[arg-type]
    for key, request in zip(keys, requests, strict=True):
        seen = boxes[request]  # type: ignore[index]
        guess = estimate(key)
        assert seen is not None and guess is not None
        assert guess.x0 <= seen[0] and guess.y0 <= seen[1] and guess.x1 >= seen[2] and guess.y1 >= seen[3], (
            key
        )
        assert max(seen[0] - guess.x0, seen[1] - guess.y0, guess.x1 - seen[2], guess.y1 - seen[3]) <= CLOSE, (
            key
        )


@pytest.mark.kicad_min_major(10)
def test_the_glyph_table_is_fresh() -> None:
    """``tools/measure_glyphs.py`` measures the table again with the running tool: every row and constant
    is the one shipped (the table was measured with a 10.0 release)."""
    spec = importlib.util.spec_from_file_location("measure_glyphs", ROOT / "tools" / "measure_glyphs.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_glyphs"] = module
    spec.loader.exec_module(module)
    fresh = module.measure(str(runner().path))
    held = (ROOT / "src" / "fenolite" / "silk" / "data" / "glyphs.toml").read_text(encoding="utf-8")
    assert module._body(fresh) == module._body(held)
    assert glyph_table().glyphs
