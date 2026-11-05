# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where Altium Designer puts the copies of an Embedded Board Array, measured from its own NC drill outputs
(change c0386, tasks 1.2 and 1.3; ``docs/formats/altium/pcb-document.md``, "Embedded board arrays";
``H-A-PANEL-RECORD``).

Each drilled hole of the referenced board is placed by the array record and compared with the hits of the
drill file that Altium wrote for the panel. The rule measured: the copy in column ``c`` and row ``r`` takes
a point ``p`` of the board to ``(X, Y) + M(R((c · COLSPACING, r · ROWSPACING) + p − o))``, where ``o`` is the
board's origin, ``R`` the turn by ``ROTATION`` counter-clockwise about ``(X, Y)`` and ``M`` the mirror of X
about ``X`` when ``MIRROR`` is set. The whole array turns or mirrors as one, not each copy in place.

With ``FENOLITE_ALTIUM_PANEL_OUTPUTS=<folder>`` the test reads, from a folder outside the repository,
``board.PcbDoc``, each saved ``panel-<variant>.PcbDoc`` and its drill file ``panel-<variant>.TXT`` (or
``panel-<variant>-Plated.TXT`` when the plated holes were written apart). No file that Altium wrote is in
the repository.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

from fenolite.backends.altium.read.arrays import BoardArray, board_arrays
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord, ViaRecord

OUTPUTS = os.environ.get("FENOLITE_ALTIUM_PANEL_OUTPUTS")
UNIT_MM = Fraction(254, 100_000_000)
"""One document unit (1/10 000 mil) in millimetres."""
VARIANTS = ("a", "rot90", "mirror", "link")
_COORD = re.compile(r"([XY])(-?\d+)")


def _excellon_number(text: str, integers: int) -> Fraction:
    """An Excellon number with leading zeros kept (``LZ``) and trailing zeros dropped: the first
    ``integers`` digits, padded with zeros on the right, are the whole part, the rest the fraction (with 4
    integer digits ``003254`` is 32.54 and ``002`` is 20)."""
    sign = -1 if text.startswith("-") else 1
    digits = text.lstrip("-").ljust(integers, "0")
    whole, part = digits[:integers], digits[integers:]
    return sign * (Fraction(int(whole or "0")) + (Fraction(int(part), 10 ** len(part)) if part else 0))


def drill_hits(text: str) -> Counter[tuple[str, Fraction, Fraction]]:
    """The hits of an Altium Excellon file as (tool diameter text, X mm, Y mm), counted. Only the form
    Altium Designer writes is read: ``METRIC,LZ``, ``;FILE_FORMAT=<i>:<d>``, modal coordinates."""
    integers = 4
    tools: dict[str, str] = {}
    tool = ""
    x = y = Fraction(0)
    hits: Counter[tuple[str, Fraction, Fraction]] = Counter()
    body = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "M30":
            break
        if line.startswith(";FILE_FORMAT="):
            integers = int(line.split("=", 1)[1].split(":")[0])
        elif line in ("METRIC,LZ", "M48", "") or line.startswith(";"):
            continue
        elif line == "%":
            body = True
        elif not body and (match := re.fullmatch(r"(T\d+)\S*C([\d.]+)", line)):
            tools[match.group(1)] = match.group(2)
        elif body and re.fullmatch(r"T\d+", line):
            tool = tools[line]
        elif body and line[0] in "XY":
            for axis, number in _COORD.findall(line):
                value = _excellon_number(number, integers)
                if axis == "X":
                    x = value
                else:
                    y = value
            hits[(tool, x, y)] += 1
        else:
            raise ValueError(f"unread drill line {line!r}")
    return hits


def placed(
    array: BoardArray, point: tuple[Fraction, Fraction], origin: tuple[Fraction, Fraction], col: int, row: int
) -> tuple[Fraction, Fraction]:
    """Where copy (``col``, ``row``) of ``array`` puts ``point`` of the board, in mm (both in units)."""
    turns = {0.0: (1, 0), 90.0: (0, 1), 180.0: (-1, 0), 270.0: (0, -1)}
    cos, sin = turns[array.rotation % 360]
    dx = col * array.col_pitch + point[0] - origin[0]
    dy = row * array.row_pitch + point[1] - origin[1]
    tx, ty = cos * dx - sin * dy, sin * dx + cos * dy
    if array.mirrored:
        tx = -tx
    return (array.x + tx) * UNIT_MM, (array.y + ty) * UNIT_MM


def board_holes(data: bytes) -> tuple[tuple[Fraction, Fraction], list[tuple[Fraction, Fraction]]]:
    """The board's origin and the centre of every drilled pad and via, in units."""
    doc = read_pcbdoc(data)
    origin = doc.board.origin
    assert origin is not None
    holes = [(Fraction(p.x), Fraction(p.y)) for p in doc.pads if isinstance(p, PadRecord) and p.hole] + [
        (Fraction(v.x), Fraction(v.y)) for v in doc.vias if isinstance(v, ViaRecord)
    ]
    assert len(holes) == sum(1 for p in doc.pads if not isinstance(p, PadRecord) or p.hole) + len(doc.vias)
    return (Fraction(origin[0]), Fraction(origin[1])), holes


def test_drill_reader_reads_altium_lz_form() -> None:
    text = "\n".join(
        [
            "M48", ";FILE_FORMAT=4:4", "METRIC,LZ", ";TYPE=PLATED", "T01F00S00C0.3000", "T02F00S00C0.9000",
            "%", "T01", "X0023Y0011", "X0065", "Y0043", "T02", "X-003254Y002", "M30",
        ]
    )  # fmt: skip
    hits = drill_hits(text)
    assert hits == Counter(
        {
            ("0.3000", Fraction(23), Fraction(11)): 1,
            ("0.3000", Fraction(65), Fraction(11)): 1,
            ("0.3000", Fraction(65), Fraction(43)): 1,
            ("0.9000", Fraction(-3254, 100), Fraction(20)): 1,
        }
    )


def test_placement_turns_and_mirrors_the_whole_array() -> None:
    mm = Fraction(1) / UNIT_MM
    array = BoardArray("board.PcbDoc", 5 * mm, 5 * mm, 90.0, False, 2, 2, 32 * mm, 42 * mm, False)
    origin = (Fraction(0), Fraction(0))
    assert placed(array, (18 * mm, 6 * mm), origin, 1, 0) == (-1, 65)
    mirrored = BoardArray("board.PcbDoc", 5 * mm, 5 * mm, 0.0, True, 2, 2, 32 * mm, 42 * mm, False)
    assert placed(mirrored, (18 * mm, 6 * mm), origin, 1, 1) == (-55, 43)


def _drill_file(folder: Path, variant: str) -> Path | None:
    for name in (f"panel-{variant}.TXT", f"panel-{variant}-Plated.TXT"):
        if (folder / name).is_file():
            return folder / name
    return None


@pytest.mark.skipif(not OUTPUTS, reason="FENOLITE_ALTIUM_PANEL_OUTPUTS names no folder of Altium outputs")
@pytest.mark.parametrize("variant", VARIANTS)
def test_altium_drill_hits_match_the_array_record(variant: str) -> None:
    folder = Path(str(OUTPUTS)).expanduser()
    panel, drill = folder / f"panel-{variant}.PcbDoc", _drill_file(folder, variant)
    if not panel.is_file() or drill is None:
        pytest.skip(f"no saved panel or drill output for panel-{variant}")
    origin, holes = board_holes((folder / "board.PcbDoc").read_bytes())
    data = panel.read_bytes()
    arrays = board_arrays(data)
    assert len(arrays) == 1
    array = arrays[0]
    expected = Counter(
        placed(array, hole, origin, col, row)
        for hole in holes
        for col in range(array.cols)
        for row in range(array.rows)
    )
    hits = drill_hits(drill.read_text(encoding="ascii"))
    found = Counter((x, y) for (_, x, y), count in hits.items() for _ in range(count))
    tolerance = Fraction(1, 1000)

    def near(a: tuple[Fraction, Fraction], b: tuple[Fraction, Fraction]) -> bool:
        return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance

    left = list(found.elements())
    for point in expected.elements():
        match = next((hit for hit in left if near(hit, point)), None)
        assert match is not None, (variant, [float(c) for c in point])
        left.remove(match)
    assert not left, (variant, [[float(c) for c in hit] for hit in left])
