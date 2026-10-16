# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The slot fixture converted to Altium and back to KiCad (capability design-conversion, "Slots and
cut-outs in a conversion"; hypothesis H-K-CONV-SLOTS; change c0170).

The source is ``tests/data/slots/convert.py`` built for the running major, committed as
``tests/data/slots/slots_convert_t<major>.kicad_pcb`` (the build merges the L of ``S2`` and ``S3``, which
needs the ``geo`` extra that the oracle jobs do not install; ``tests/unit/convert/test_convert_slots.py``
keeps the boards equal to a fresh build). It is converted to Altium with the cut-out regions written
(``pcbdoc.CUTOUT_REGIONS`` set for the run: the region form is c0168's, measured against KiCad's importer),
and the document is converted back to KiCad for the running major. No ring overlaps on either side, so
neither conversion needs the ``geo`` extra.

- ``convert-slots-drc``: ``absent`` when ``pcb drc`` of the board that comes back reports no
  ``invalid_outline``.
- ``convert-slots-drill``: ``equal`` when the drill files of the board that comes back hold what those of
  the source hold, the hits taken relative to the round hole ``H1``: in the NPTH file ``H1`` and the
  drilled slot ``D1`` (a ``G85`` route), and nothing else in any file, so neither a milled slot nor the
  cut-out reaches a drill file.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from functools import cache
from pathlib import Path

import _lenscases as lc
from _outlinebench import PROJECT, drc, drill_hits, types

from fenolite.backends.altium import pcbdoc
from fenolite.convert import Conversion, convert_project

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "data" / "slots" / "convert.py"
BOARD = "slots.kicad_pcb"
TOLERANCE_MM = 0.002
"""How far a converted hit may lie from the source's, per coordinate: the Altium unit is 2.54 nm and an
Excellon coordinate is written to the micrometre or finer."""
Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]


def major() -> int:
    return 10 if lc.runner().major() >= 10 else 9


def source_board(target: int) -> Path:
    """The committed board of the fixture built for ``target``."""
    return FIXTURE.parent / f"slots_convert_t{target}.kicad_pcb"


@contextmanager
def regions() -> Iterator[None]:
    """``pcbdoc.CUTOUT_REGIONS`` set while a conversion writes the Altium document."""
    before = pcbdoc.CUTOUT_REGIONS
    pcbdoc.CUTOUT_REGIONS = True  # type: ignore[misc]
    try:
        yield
    finally:
        pcbdoc.CUTOUT_REGIONS = before  # type: ignore[misc]


def _written(conversion: Conversion, folder: Path) -> Path:
    for name, data in conversion.files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder / conversion.read_back


@cache
def round_trip(target: int) -> tuple[Conversion, Conversion]:
    """The conversion of the fixture to Altium and that of its document back to KiCad ``target``."""
    with tempfile.TemporaryDirectory(prefix="fenolite-slots-") as temp:
        folder = Path(temp)
        source = folder / "kicad"
        source.mkdir()
        (source / BOARD).write_text(source_board(target).read_text(encoding="utf-8"), encoding="utf-8")
        (source / "slots.kicad_pro").write_text(PROJECT, encoding="utf-8")
        with regions():
            altium = convert_project(source / BOARD, to="altium", allow_lossy=True)
        document = _written(altium, folder / "altium")
        back = convert_project(document, to="kicad", kicad_version=target, allow_lossy=True)
    return altium, back


def returned_files(target: int) -> dict[str, bytes]:
    return dict(round_trip(target)[1].files)


def source_files(target: int) -> dict[str, str | bytes]:
    return {BOARD: source_board(target).read_text(encoding="utf-8"), "slots.kicad_pro": PROJECT}


@cache
def returned_types() -> tuple[str, ...] | None:
    back = round_trip(major())[1]
    report = drc(dict(back.files), back.read_back)
    return None if report is None else tuple(types(report))


def slots_drc() -> str:
    """``absent`` when the board that comes back has no ``invalid_outline``."""
    found = returned_types()
    if found is None:
        return "inconclusive"
    return "present" if "invalid_outline" in found else "absent"


_NUMBER = re.compile(r"[XY](-?\d+(?:\.\d+)?)")


def _hits(hits: Mapping[str, list[str]]) -> dict[str, list[tuple[bool, tuple[float, ...]]]]:
    """Per kind of file (``NPTH`` or ``PTH``), each hit as (is a route, its numbers relative to the first
    round hit of the NPTH file), sorted."""
    files = {("NPTH" if "NPTH" in name else "PTH"): lines for name, lines in hits.items()}
    npth = files.get("NPTH", [])
    origin = next(
        ([float(v) for v in _NUMBER.findall(line)] for line in npth if "G85" not in line),
        [0.0, 0.0],
    )
    found: dict[str, list[tuple[bool, tuple[float, ...]]]] = {}
    for kind, lines in files.items():
        rows = []
        for line in lines:
            values = [float(v) for v in _NUMBER.findall(line)]
            relative = tuple(v - origin[k % 2] for k, v in enumerate(values))
            rows.append(("G85" in line, relative))
        found[kind] = sorted(rows)
    return found


@cache
def drill_pair() -> tuple[dict[str, list[str]] | None, dict[str, list[str]] | None]:
    back = round_trip(major())[1]
    return drill_hits(source_files(major()), BOARD), drill_hits(dict(back.files), back.read_back)


def slots_drill() -> str:
    """``equal`` when the drill files of the board that comes back hold the source's hits, relative to
    ``H1``: ``H1`` and the route of ``D1`` in the NPTH file, nothing else."""
    source, back = drill_pair()
    if source is None or back is None:
        return "inconclusive"
    a, b = _hits(source), _hits(back)
    npth = a.get("NPTH", [])
    if [route for route, _ in npth] != [False, True] or any(a.get("PTH", [])):
        return "inconclusive"  # the source does not hold what the fixture declares
    if {k: len(v) for k, v in a.items() if v} != {k: len(v) for k, v in b.items() if v}:
        return "different"
    for kind, rows in a.items():
        for (route, values), (other_route, other) in zip(rows, b.get(kind, []), strict=False):
            if route != other_route or len(values) != len(other):
                return "different"
            if any(abs(x - y) > TOLERANCE_MM for x, y in zip(values, other, strict=True)):
                return "different"
    return "equal"


def conv_slot_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    return {"convert-slots-drc": (slots_drc, both), "convert-slots-drill": (slots_drill, both)}
