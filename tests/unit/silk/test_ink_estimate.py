# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ink of a stroke text: the estimate from the glyph table, the cache and the choice between them
(change c0212; capability silkscreen-layout, "Text ink extents"; hypothesis ``H-K-SILK-ESTIMATE``).

The reference boxes are the ones ``kicad-cli`` 10.0.7 drew for c0212, as ``docs/formats/kicad/text.md``
records them; the tests need no tool."""

from __future__ import annotations

import string
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from fenolite.core.evidence import Level
from fenolite.silk.extents import (
    ESTIMATE_MARGIN,
    InkBox,
    InkCache,
    TextKey,
    cache_folder,
    effective_stroke,
    estimate,
    glyph_table,
    ink_box,
    ink_boxes,
)

MM = 1_000_000
CLOSE = 2_000
"""How far an estimate may sit from a recorded render: the margin and a little rounding."""


def _near(box: InkBox | None, want: tuple[int, int, int, int]) -> bool:
    assert box is not None
    return all(
        abs(got - expected) <= CLOSE
        for got, expected in zip((box.x0, box.y0, box.x1, box.y1), want, strict=True)
    )


def test_r12_as_recorded() -> None:
    """``R12`` at 1 mm and a 0.15 mm stroke, centred: KiCad drew its skeleton from (-1.2143, -0.5452) to
    (1.2619, 0.4548) mm; the ink adds 0.075 mm on each side."""
    box = estimate(TextKey("R12", MM, MM, 150_000))
    assert _near(box, (-1_289_300, -620_200, 1_336_900, 529_800))
    assert box is not None and box.x0 <= -1_289_300 and box.x1 >= 1_336_900  # never smaller


@pytest.mark.parametrize(
    ("text", "width", "skeleton"),
    [
        ("C100", 600_000, (-1_042_900, -545_200, 1_042_900, 454_800)),
        ("TP14", 800_000, (-1_390_500, -592_800, 1_352_400, 454_800)),
        ("Q10", 1_270_000, (-1_632_900, -545_200, 1_632_900, 550_100)),
        ("X1.2", 1_500_000, (-2_285_700, -545_200, 2_214_300, 454_800)),
    ],
)
def test_other_designators_as_recorded(text: str, width: int, skeleton: tuple[int, int, int, int]) -> None:
    """Recorded renders at a height of 1 mm and a stroke of 0.15 mm, at four glyph widths."""
    x0, y0, x1, y1 = skeleton
    assert _near(
        estimate(TextKey(text, width, MM, 150_000)), (x0 - 75_000, y0 - 75_000, x1 + 75_000, y1 + 75_000)
    )


def test_the_stroke_is_held_to_a_quarter_of_the_size() -> None:
    """A stroke above a quarter of the smaller of width and height is drawn at a quarter."""
    key = TextKey("H", MM // 2, MM // 2, 300_000)
    assert effective_stroke(key) == 125_000
    box = estimate(key)
    assert box is not None
    h = glyph_table().glyphs["H"]
    assert box.width == (h.right - h.left) // 2 + 125_000 + 2 * ESTIMATE_MARGIN


def test_justification_moves_the_box() -> None:
    """``H`` at 1 mm and 0.15 mm: left moves it by 0.6225 mm, top by 0.585 mm, as recorded."""
    centre = estimate(TextKey("H", MM, MM, 150_000))
    moved = estimate(TextKey("H", MM, MM, 150_000, "left", "top"))
    back = estimate(TextKey("H", MM, MM, 150_000, "right", "bottom"))
    assert centre is not None and moved is not None and back is not None
    assert abs((moved.x0 - centre.x0) - 622_500) <= 1 and abs((moved.y0 - centre.y0) - 585_000) <= 1
    assert abs((centre.x0 - back.x0) - 622_500) <= 1 and abs((centre.y0 - back.y0) - 585_000) <= 1


@pytest.mark.parametrize("justify", ["left", "center", "right"])
def test_an_unknown_glyph_only_grows_the_box(justify: str) -> None:
    """``R?1`` holds every ``R<g>1`` that the table can draw, whatever the justification."""
    unknown = estimate(TextKey("R?1", MM, MM, 150_000, justify))  # type: ignore[arg-type]
    assert unknown is not None
    for glyph in glyph_table().glyphs:
        known = estimate(TextKey(f"R{glyph}1", MM, MM, 150_000, justify))  # type: ignore[arg-type]
        assert known is not None
        assert unknown.x0 <= known.x0 and unknown.x1 >= known.x1, glyph
        assert unknown.y0 <= known.y0 and unknown.y1 >= known.y1, glyph


def test_lines_and_blanks() -> None:
    """A second line grows the box up and down by 1.61 x the height; a blank text has no ink."""
    one = estimate(TextKey("R1", MM, MM, 150_000))
    two = estimate(TextKey("R1\nR2", MM, MM, 150_000))
    assert one is not None and two is not None
    assert two.y0 <= one.y0 - 1_610_000 and two.y1 >= one.y1 + 1_610_000
    assert estimate(TextKey("  ", MM, MM, 150_000)) is None


def test_the_table() -> None:
    """The shipped table: every letter and digit, from one tool version, with its layout constants."""
    table = glyph_table()
    assert set(string.ascii_letters + string.digits) <= set(table.glyphs)
    assert table.tool.startswith("kicad-cli ") and table.v_shift == 585_000
    assert all(g.left <= g.right and g.top <= g.bottom for g in table.glyphs.values())


def test_a_key_needs_a_size() -> None:
    with pytest.raises(ValueError):
        TextKey("R1", 0, MM, 150_000)
    with pytest.raises(ValueError):
        ink_box("R1", size=(MM, MM), stroke=150_000, font="Arial")


class _Tool:
    """A stand-in for a render: every text gets the box (-1, -1, 1, 1) mm; it counts its calls."""

    def __init__(self) -> None:
        self.calls: list[list[TextKey]] = []

    def __call__(self, keys: Sequence[TextKey]) -> Mapping[TextKey, InkBox | None]:
        self.calls.append(list(keys))
        return {key: InkBox(-MM, -MM, MM, MM) if key.text.strip() else None for key in keys}


def test_measured_once_then_read_from_the_cache(tmp_path: Path) -> None:
    """A render is ``KICAD-VERIFIED``; a second call reads the cache and renders nothing."""
    tool = _Tool()
    cache = InkCache(tmp_path / "silk")
    first = ink_box("R12", size=(MM, MM), stroke=150_000, measure=tool, tool="kicad-cli 10.0.7", cache=cache)
    assert first.level is Level.KICAD_VERIFIED and first.source == "kicad-cli 10.0.7"
    assert first.box == InkBox(-MM, -MM, MM, MM)
    again = InkCache(tmp_path / "silk")
    second = ink_box("R12", size=(MM, MM), stroke=150_000, measure=tool, tool="kicad-cli 10.0.7", cache=again)
    assert second.source == "cache" and second.box == first.box and len(tool.calls) == 1 and again.hits == 1
    other = ink_box("R12", size=(MM, MM), stroke=150_000, measure=tool, tool="kicad-cli 9.0.9", cache=again)
    assert other.source == "kicad-cli 9.0.9" and len(tool.calls) == 2  # another tool, another entry


def test_one_render_for_all_missing_keys(tmp_path: Path) -> None:
    tool = _Tool()
    keys = [TextKey(text, MM, MM, 150_000) for text in ("R1", "R2", "R1", " ")]
    found = ink_boxes(keys, measure=tool, tool="kicad-cli 10.0.7", cache=InkCache(tmp_path))
    assert len(tool.calls) == 1 and len(tool.calls[0]) == 3
    assert found[TextKey(" ", MM, MM, 150_000)].box is None


def test_without_a_tool_everything_is_estimated() -> None:
    found = ink_boxes([TextKey("R1", MM, MM, 150_000)])
    (ink,) = found.values()
    assert ink.level is Level.INFERRED and ink.source == "estimate" and ink.box is not None


def test_a_broken_cache_entry_is_a_miss(tmp_path: Path) -> None:
    cache = InkCache(tmp_path)
    key = TextKey("R1", MM, MM, 150_000)
    cache.put("t", key, InkBox(1, 2, 3, 4))
    assert cache.get("t", key) == (True, InkBox(1, 2, 3, 4))
    for entry in tmp_path.glob("*.json"):
        entry.write_text("{", encoding="utf-8")
    assert cache.get("t", key) == (False, None)
    assert InkCache(None).get("t", key) == (False, None)


def test_the_cache_folder() -> None:
    assert cache_folder({"FENOLITE_CACHE_DIR": "/c"}) == Path("/c/silk")
    assert cache_folder({"XDG_CACHE_HOME": "/x"}) == Path("/x/fenolite/silk")
