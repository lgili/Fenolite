# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A public PCB document converted to KiCad and back to Altium with the computed pour pours what the
computed pour of the source document pours, and refuses the rest (change c0457; capability
design-conversion, "The pour of the way back follows the source").

``altium-third-party-pcbdoc-04`` holds 9 polygons and a Clearance record at priority 1 whose scope the pour
does not read. The pour of the source refuses its 9 polygons (4 for that rule, 5 that depend on them, the
census of ``test_altium_pour_census.py``). On ``cac/lote-27`` the way back lost the record and poured the 9;
since change c0434 it writes the record back and refuses them as the source does (S-2160). Poured with
the record ignored, or with its gap taken as a bound, those polygons differ from the regions the document
saves by 3.5 to 7.4 times the M1 allowance (S-2160). The test reads counts and issue codes only.
"""

from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.api import convert

pytestmark = pytest.mark.needs_corpus
ITEM = next(item for item in manifest_items("altium-pcbdoc") if item.id.endswith("-pcbdoc-04"))


def _write(files: dict[str, bytes], folder: Path) -> None:
    for name, data in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def test_the_way_back_pours_what_the_source_pours(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyclipper") is None:
        pytest.skip("the pour needs the geo extra")
    from fenolite.backends.altium.pour import pour_reading, read_pour

    source = require(ITEM)
    own = pour_reading(read_pour(source.read_bytes(), file=source.name))
    refused = Counter(polygon.reason for polygon in own.polygons if not polygon.poured)
    assert (len(own.polygons), refused) == (9, Counter({"depends-on-refused": 5, "rule-scope": 4}))
    _write(dict(convert(source, to="kicad", allow_lossy=True).conversion.files), tmp_path / "k")
    (board,) = (tmp_path / "k").glob("*.kicad_pcb")
    back = convert(board, to="altium", allow_lossy=True).conversion
    codes = Counter(issue.code for issue in back.issues)
    assert codes["altium.zone-unpoured"] == sum(refused.values())
    assert codes["altium.zones-poured"] == 0
    rows = {row.kind: row for row in back.report.rows}
    assert (rows["zone"].source, rows["zone"].written, rows["zone"].lost) == (9, 9, 0)
    assert rows["rule"].lost == 0
