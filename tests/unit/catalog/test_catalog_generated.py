# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog footprints after the footprint generators (change c0260, requirement "Catalog footprints
come from the generators"): every catalog ``.kicad_mod`` keeps the bytes captured before the change, for
both writer targets, and no private land helper or land tuple remains in ``fenolite.catalog``. That
``drawing/0`` draws the family-shaped entries equal to their records is
``tests/unit/catalog/footprints/test_drawing.py::test_drawing_0_reproduces_the_0_6_catalog``."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fenolite.backends.kicad.mod import prepare_authored_definition, write_pretty
from fenolite.catalog import get_footprint, list_entries

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests" / "data" / "catalog" / "footprints.sha256"
CATALOG = ROOT / "src" / "fenolite" / "catalog"
HELPERS = (
    "_chip_footprint",
    "_two_terminal_footprint",
    "_row_pads",
    "_quad_pads",
    "_paste_grid",
    "_thermal_paste",
    "_pin1_index",
    "_make_footprint",
)


def test_golden_footprint_bytes_unchanged() -> None:
    golden = dict(
        reversed(line.split("  ", 1)) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line
    )
    defs = [prepare_authored_definition(get_footprint(e.lib_id)) for e in list_entries(kind="footprint")]
    assert len(defs) == 100
    found: dict[str, str] = {}
    for target in (9, 10):
        for name, text in write_pretty(defs, target=target).items():
            found[f"kicad{target}/{name}"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert found == golden


def test_no_private_land_helpers_remain() -> None:
    for path in sorted(CATALOG.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name in HELPERS:
            assert not re.search(rf"\bdef {name}\b", text), (path.name, name)
        assert not re.search(r"^_[A-Z0-9_]*_LANDS_UM\b", text, re.MULTILINE), path.name
