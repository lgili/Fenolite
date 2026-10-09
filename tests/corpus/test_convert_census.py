# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad 10.0.6 demo boards converted to Altium and read back (change c0159, ``H-G-CONV-LEDGER``).

Each board of the corpus is read with the KiCad backend (the corpus holds the boards without their project
files), written as an Altium project with ``lens.altium.write_model(design, allow_lossy=True)``, and its
PCB document read back with the Altium backend and compared with the board through ``compare_designs`` at
the highest level both hold, in the relative frame, within 10 nm and 20 ppm (the measurement of the
design, "Context"). The test records, per board, the items the write leaves out per kind and the
differences per kind, and the largest per-coordinate difference of a placement, a pad position, a pad size
or a drill without tolerance, which sets ``tolerance_nm`` of the conversion profile.
"""

from __future__ import annotations

import re
import tempfile
from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.backends import registry
from fenolite.backends.altium.cfb import CompoundTooLarge
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.equivalence import EquivalenceReport, Tolerances, compare_designs, max_level
from fenolite.lens.altium import write_model
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
PREFIX = "kicad-demo-10-0-6-pcb-"
TOO_LARGE = {"06": 119, "18": 180}
"""The boards the write refuses (``CompoundTooLarge``), with the FAT sectors their document needs."""
NOT_WRITTEN: dict[str, dict[str, int]] = {
    "01": {
        "footprint-graphic": 33, "graphic": 31, "outline": 1, "pad": 30, "stackup": 1, "text": 149,
        "zone-fill": 13,
    },
    "02": {"stackup": 1, "text": 2, "zone-fill": 1},
    "03": {"footprint-graphic": 4, "stackup": 1, "zone-fill": 1},
    "04": {"footprint-graphic": 4, "pad": 10, "stackup": 1, "zone-fill": 1},
    "05": {"dimension": 2, "pad": 62, "stackup": 1, "text": 6, "zone-fill": 1},
    "07": {"pad": 5, "stackup": 1, "text": 5, "zone-fill": 3},
    "08": {"footprint-copper": 4, "graphic": 3},
    "09": {"footprint-graphic": 32, "keep-out": 4, "pad": 35, "text": 2, "zone-fill": 1},
    "10": {"footprint-graphic": 32, "keep-out": 4, "pad": 35, "text": 2, "zone-fill": 2},
    "11": {
        "copper-shape": 2, "footprint-copper": 3, "footprint-graphic": 29, "graphic": 2, "net-tie": 2,
        "outline": 20, "pad": 23, "stackup": 1, "text": 25, "zone-fill": 34,
    },
    "12": {"footprint-graphic": 6, "pad": 11, "stackup": 1, "text": 19, "zone-fill": 1},
    "13": {
        "footprint-copper": 1, "footprint-graphic": 4, "footprint-text": 2, "net-tie": 1, "outline": 4,
        "pad": 67, "stackup": 1, "text": 1, "zone": 2, "zone-fill": 2,
    },
    "14": {"copper-shape": 4, "footprint-graphic": 11, "outline": 1},
    "15": {
        "dimension": 1, "footprint-graphic": 2, "footprint-text": 2, "stackup": 1, "text": 8, "zone-fill": 1,
    },
    "16": {
        "dimension": 6, "footprint-copper": 25, "footprint-graphic": 19, "footprint-text": 1, "graphic": 2,
        "net-tie": 9, "outline": 1, "pad": 27, "stackup": 1, "text": 224, "zone-fill": 2,
    },
    "17": {"dimension": 2, "graphic": 14, "pad": 144, "stackup": 1, "text": 1, "zone-fill": 2},
}  # fmt: skip
"""Per board, the model items ``write_model`` leaves out, per kind (measured on 2026-10-09)."""
DIFFERENCES: dict[str, tuple[int, dict[str, int]]] = {
    "01": (5, {"dnp": 2, "pad-missing": 15, "pin-missing": 6}),
    "02": (5, {}),
    "03": (5, {}),
    "04": (5, {"pad-missing": 10, "pin-missing": 9}),
    "05": (5, {"pad-missing": 62, "pin-missing": 62}),
    "07": (5, {"pad-missing": 5, "pin-missing": 3}),
    "08": (4, {"ref-ambiguous": 1}),
    "09": (5, {"pad-missing": 19, "pin-missing": 19}),
    "10": (5, {"pad-missing": 19, "pin-missing": 19}),
    "11": (5, {"dnp": 11, "pad-missing": 20, "pin-missing": 17, "ref-ambiguous": 1}),
    "12": (5, {"pad-missing": 10, "pin-missing": 2}),
    "13": (5, {"dnp": 22, "pad-missing": 35, "pin-missing": 25, "route-connectivity": 2}),
    "14": (5, {}),
    "15": (5, {}),
    "16": (5, {"dnp": 11, "pad-missing": 24, "pin-missing": 4, "ref-ambiguous": 4, "route-connectivity": 1}),
    "17": (5, {"pad-missing": 128, "pin-missing": 120}),
}
"""Per board, the level compared and the differences per kind, within 10 nm and 20 ppm (2026-10-09)."""
LARGEST_NM = 2
"""The largest per-coordinate difference without tolerance over every written board (2026-10-09): the
written unit is 2.54 nm and the reader rounds it to the nanometre."""
ITEMS = {item.id.removeprefix(PREFIX): item for item in manifest_items("rt0") if item.id.startswith(PREFIX)}
_NUMBER = re.compile(r"-?\d+")


@cache
def _sides(key: str) -> tuple[Design, Design]:
    path = require(ITEMS[key])
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    written = write_model(design, allow_lossy=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in written.files.items():
            (Path(tmp) / name).write_bytes(data)
        document = next(Path(tmp) / name for name in written.files if name.lower().endswith(".pcbdoc"))
        backend = registry.for_path(document)
        assert backend is not None
        back = backend.read(document).content
    assert isinstance(back, Design)
    return design, back


@cache
def _not_written(key: str) -> dict[str, int]:
    path = require(ITEMS[key])
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    return dict(sorted(write_model(design, allow_lossy=True).inputs.counts().items()))


def _largest(report: EquivalenceReport) -> int:
    """The largest per-coordinate difference of a placement (after the frame's translation), a pad
    position, a pad size or a drill."""
    largest = 0
    shift = report.translation
    for difference in report.differences:
        a = [int(value) for value in _NUMBER.findall(difference.a)]
        b = [int(value) for value in _NUMBER.findall(difference.b)]
        if difference.kind == "position" and len(a) == len(b) == 2:
            b = [b[0] - shift.x, b[1] - shift.y]
        elif difference.kind not in ("pad-position", "pad-size", "pad-drill") or len(a) != len(b):
            continue
        largest = max(largest, *(abs(x - y) for x, y in zip(a, b, strict=True)))
    return largest


@pytest.mark.parametrize("key", sorted(TOO_LARGE))
def test_too_large_boards(key: str) -> None:
    path = require(ITEMS[key])
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    with pytest.raises(CompoundTooLarge, match=f"needs {TOO_LARGE[key]} FAT sectors"):
        write_model(design, allow_lossy=True)


@pytest.mark.parametrize("key", sorted(NOT_WRITTEN))
def test_not_written_per_kind(key: str) -> None:
    found = _not_written(key)
    print(f"{ITEMS[key].path.stem}: {found}")
    assert found == NOT_WRITTEN[key]


@pytest.mark.parametrize("key", sorted(DIFFERENCES))
def test_differences_per_kind(key: str) -> None:
    a, b = _sides(key)
    level = max_level(a, b)
    report = compare_designs(a, b, level=level, tolerances=Tolerances(10, 0, 20), frame="relative")
    found = dict(sorted(Counter(d.kind for d in report.differences).items()))
    exact = compare_designs(a, b, level=min(level, 4), frame="relative")
    print(f"{ITEMS[key].path.stem}: level {level}, {found}, largest {_largest(exact)} nm")
    assert (level, found) == DIFFERENCES[key]
    assert _largest(exact) <= LARGEST_NM
