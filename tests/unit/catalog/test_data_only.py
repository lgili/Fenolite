# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog holds no geometry in Python (change c0259; capability fenolite-component-catalog, "Catalog
definitions are data files")."""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.catalog import ANODE_FIRST_SYMBOLS, CATHODE_FIRST_LANDS, ENTRIES, default_pad_map

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "src" / "fenolite" / "catalog"


def test_no_geometry_in_code() -> None:
    assert not (CATALOG / "_symbol_expansion.py").exists()
    for path in sorted(CATALOG.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"_(LANDS|BODIES)_UM\b|_SPECS\b|SYMBOL_SPECS", text), path.name
        assert not re.search(r"Point\(\s*-?\d", text), path.name
    for entry in ENTRIES:
        folder = "pins" if entry.kind == "symbol" else "packages"
        assert (CATALOG / "data" / folder / f"{entry.lib_id.split(':', 1)[1]}.toml").is_file(), entry.lib_id
    assert len(ENTRIES) == 149


def test_pad_map_from_the_records() -> None:
    assert default_pad_map("Fenolite:LED", "Fenolite:LED0603_Kingbright_APT1608SURCK") == (
        ("1", "2"),
        ("2", "1"),
    )
    assert default_pad_map("Fenolite:Resistor", "Fenolite:Chip_0603") == ()
    assert "Fenolite:LED" in ANODE_FIRST_SYMBOLS and "Fenolite:SOD128_Nexperia_CFP5" in CATHODE_FIRST_LANDS


def test_entries_carry_version_licence_and_uid() -> None:
    from fenolite.catalog.records import record_uid

    resistor = next(entry for entry in ENTRIES if entry.lib_id == "Fenolite:Resistor")
    assert (resistor.version, resistor.licence) == ("1.0.1", "CC0-1.0")
    assert resistor.uid == record_uid("pins", "Fenolite:Resistor")
    assert (resistor.kind, resistor.category, resistor.evidence) == ("symbol", "Passive", "INFERRED")


def test_every_shipped_record_is_cc0() -> None:
    """The maintainer decided on 2026-10-29 that the shipped records are CC0-1.0 (c0259, open question 1)."""
    from fenolite.catalog.records import shipped_tree

    records = shipped_tree().records
    assert len(records) == 159 and {r.header.licence for r in records} == {"CC0-1.0"}
    for path in sorted((CATALOG / "data").rglob("*.toml")):
        assert "Apache-2.0" not in path.read_text(encoding="utf-8"), path.name
