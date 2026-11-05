# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of Part H of the maintainer's check (``docs/evidence/altium-pcb.md``, "Part H: a slot shorter
than its hole"; change c0416, task 3.1; ``H-A-SLOT-SHORT``).

``part_h(folder)`` writes the kit into ``folder``:

- ``holes.PcbDoc``: the board of ``_altium_slotcases`` with the six slot pads of ``SLOT_PADS`` as free
  plated pads ``P1`` to ``P6`` (cases H1 to H4);
- ``slots.PcbLib``: the footprint ``SL`` with the same six pads (``slot_library``; cases H5 and H6);
- ``expected.md``: the fields of every pad, read back from the written files with Fenolite's own reader,
  and the axis that KiCad 10.0.6 gives each slot; ``README.md``, the steps; ``SHA256SUMS``.

With ``FENOLITE_ALTIUM_PART_H=<folder outside the repository>`` the kit is written there:
``FENOLITE_ALTIUM_PART_H=~/fenolite-altium-checks/H-short-slots uv run pytest
tests/unit/backends/altium/test_part_h.py``. Without it the kit is written under the test's own folder. No
file that Altium wrote is in the repository.
"""

from __future__ import annotations

import hashlib
import os
from fractions import Fraction
from pathlib import Path

import _altium_slotcases as cases
import pytest

from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.pcbprims import PadRecord

ROOT = Path(__file__).resolve().parents[4]
HANDOVER = os.environ.get("FENOLITE_ALTIUM_PART_H")
SAVED_BOARD = os.environ.get("FENOLITE_ALTIUM_H4")
"""Kit case H4: the path of ``holes.PcbDoc`` saved by Altium Designer (``File » Save As``)."""
SAVED_LIBRARY = os.environ.get("FENOLITE_ALTIUM_H6")
"""Kit case H6: the path of ``slots.PcbLib`` saved by Altium Designer (``File » Save As``)."""
KICAD_AXES = {"1": "0°", "2": "90°", "3": "lost", "4": "lost", "5": "135°", "6": "120°"}
"""The axis of each slot, in degrees from the X axis, in KiCad 10.0.6's import of both files (change c0416,
``pcb-records.md``): the long side of the hole, ``lost`` where KiCad drops the slot."""

Fields = tuple[str, int, int, float, float]


def _mm(units: int) -> str:
    return f"{float(Fraction(units) * Fraction(254, 100) / 1_000_000):.3f}"


def pad_fields(pads: tuple[PadRecord, ...]) -> list[Fields]:
    """Name, hole size, slot length (units of 1/10 000 mil), slot rotation and pad rotation (degrees) of
    every slot pad, sorted by name."""
    return sorted(
        (p.name, p.hole, p.slot_length or 0, p.slot_rotation or 0.0, p.rotation)
        for p in pads
        if p.hole_shape == 2
    )


def _board_pads(data: bytes) -> tuple[PadRecord, ...]:
    return tuple(p for p in read_pcbdoc(data).pads if isinstance(p, PadRecord))


def _library_pads(data: bytes) -> tuple[PadRecord, ...]:
    (footprint,) = read_pcblib(data).footprints
    return footprint.pads


def _table(fields: list[Fields], prefix: str) -> list[str]:
    lines = [
        "| pad | Hole Size (mm) | Length (mm) | hole Rotation | pad Rotation | KiCad 10.0.6 axis |",
        "|---|---|---|---|---|---|",
    ]
    for name, hole, length, slot, turn in fields:
        axis = KICAD_AXES[name.removeprefix(prefix)]
        lines.append(f"| {name} | {_mm(hole)} | {_mm(length)} | {slot:g}° | {turn:g}° | {axis} |")
    return lines


def part_h(folder: Path) -> dict[str, str]:
    """Write the kit into ``folder``; the SHA-256 of every file by its path relative to ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    board, library = cases.short_slot_document(), cases.slot_library()
    (folder / "holes.PcbDoc").write_bytes(board)
    (folder / "slots.PcbLib").write_bytes(library)
    expected = [
        "# Part H: expected values",
        "",
        "## `holes.PcbDoc`: free pads at X 10, 18, 26, 34, 42 and 50 mm, Y 20 mm from the board's lower-left",
        "",
        *_table(pad_fields(_board_pads(board)), "P"),
        "",
        "## `slots.PcbLib`, footprint `SL`: pads 6 mm apart along X from the origin",
        "",
        *_table(pad_fields(_library_pads(library)), ""),
        "",
    ]
    (folder / "expected.md").write_text("\n".join(expected), encoding="utf-8")
    readme = (ROOT / "docs" / "evidence" / "altium-pcb.md").read_text(encoding="utf-8")
    start = readme.index("## Part H: a slot shorter than its hole")
    end = readme.index("\n## ", start + 3)
    (folder / "README.md").write_text(readme[start:end].rstrip() + "\n", encoding="utf-8")
    sums: dict[str, str] = {}
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        sums[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (folder / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sums.items()), encoding="utf-8"
    )
    return sums


def _written(name: str, drill: int, length: int, axis: int, turn: int) -> Fields:
    from fenolite.backends.altium import pcbrecords as rec

    return (name, rec.to_units(drill), rec.to_units(length), rec.degrees_of(axis), rec.degrees_of(turn))


def test_part_h_kit(tmp_path: Path) -> None:
    """The kit holds both files, and each holds the six slots of ``SLOT_PADS`` as written: three with the
    slot length below the hole size."""
    folder = Path(HANDOVER).expanduser() if HANDOVER else tmp_path / "H-short-slots"
    if HANDOVER:
        assert ROOT not in folder.resolve().parents, "the kit is written outside the repository"
    sums = part_h(folder)
    assert set(sums) == {"README.md", "expected.md", "holes.PcbDoc", "slots.PcbLib"}
    board = pad_fields(_board_pads((folder / "holes.PcbDoc").read_bytes()))
    library = pad_fields(_library_pads((folder / "slots.PcbLib").read_bytes()))
    assert board == [_written(f"P{n}", *rest) for n, *rest in cases.SLOT_PADS]
    assert library == [_written(n, *rest) for n, *rest in cases.SLOT_PADS]
    assert [name for name, hole, length, *_ in board if length < hole] == ["P2", "P4", "P6"]
    text = (folder / "README.md").read_text(encoding="utf-8")
    for case in range(1, 7):
        assert f"**H{case}**" in text


def _same(written: list[Fields], saved: list[Fields]) -> list[str]:
    """What Altium changed, one line per field: lengths within 1 unit, angles within 0.001° modulo 360°."""
    changed: list[str] = []
    if [f[0] for f in written] != [f[0] for f in saved]:
        return [f"pads {[f[0] for f in written]} became {[f[0] for f in saved]}"]
    for a, b in zip(written, saved, strict=True):
        for label, x, y in (("hole size", a[1], b[1]), ("slot length", a[2], b[2])):
            if abs(x - y) > 1:
                changed.append(f"{a[0]} {label} {_mm(x)} mm became {_mm(y)} mm")
        for label, x, y in (("slot rotation", a[3], b[3]), ("pad rotation", a[4], b[4])):
            d = (x - y) % 360
            if min(d, 360 - d) > 0.001:
                changed.append(f"{a[0]} {label} {x:g}° became {y:g}°")
    return changed


def test_h4_saved_board_reads_back() -> None:
    """Kit case H4: the board Altium saved holds the six slot pads of the one Fenolite wrote, each with its
    hole size, slot length and both rotations; a failure names every field Altium changed."""
    if not SAVED_BOARD:
        pytest.skip("set FENOLITE_ALTIUM_H4 to the path of the board Altium saved (kit case H4)")
    written = pad_fields(_board_pads(cases.short_slot_document()))
    saved = pad_fields(_board_pads(Path(SAVED_BOARD).expanduser().read_bytes()))
    assert _same(written, saved) == []


def test_h6_saved_library_reads_back() -> None:
    """Kit case H6: the library Altium saved holds footprint ``SL`` with the six slot pads as written."""
    if not SAVED_LIBRARY:
        pytest.skip("set FENOLITE_ALTIUM_H6 to the path of the library Altium saved (kit case H6)")
    written = pad_fields(_library_pads(cases.slot_library()))
    saved = pad_fields(_library_pads(Path(SAVED_LIBRARY).expanduser().read_bytes()))
    assert _same(written, saved) == []


def test_readback_names_a_swapped_slot() -> None:
    """The comparison of H4 and H6 names a field Altium would have changed: a slot whose two numbers were
    swapped and turned a quarter, as KiCad holds it, is three changed fields."""
    written = pad_fields(_board_pads(cases.short_slot_document()))
    name, hole, length, slot, turn = written[1]
    swapped = [*written[:1], (name, length, hole, (slot + 90) % 360, turn), *written[2:]]
    assert _same(written, swapped) == [
        "P2 hole size 2.150 mm became 1.000 mm",
        "P2 slot length 1.000 mm became 2.150 mm",
        "P2 slot rotation 0° became 90°",
    ]
