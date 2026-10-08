# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Counts-only corpus check of the public Altium-written compound containers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _boards import census
from _cfb_read import read_compound as independent_read
from _corpus import CorpusItem, manifest_items, require
from _kicad import oracle_env
from _resources import kicad_cli, kicad_cli_major

from fenolite.backends.altium.read.cfb import CompoundFile, read_compound

pytestmark = pytest.mark.needs_corpus
ITEMS = manifest_items("cfb")


def _entry_counts(path: Path, compound: CompoundFile) -> tuple[int, int, int]:
    data = path.read_bytes()
    sector_size = compound.header.sector_size
    directory_sectors = [sid for sid, owner in compound._sector_owners.items() if owner == "directory"]
    directory = b"".join(data[(sid + 1) * sector_size : (sid + 2) * sector_size] for sid in directory_sectors)
    red = clsid = timed = 0
    for start in range(0, len(directory), 128):
        row = directory[start : start + 128]
        if len(row) != 128 or row[66] == 0:
            continue
        red += row[67] == 0
        clsid += any(row[80:96])
        timed += any(row[100:116])
    return red, clsid, timed


@pytest.mark.parametrize("item", ITEMS, ids=lambda item: item.id)
def test_public_compound_rows(item: CorpusItem) -> None:
    path = require(item)
    compound = read_compound(path)
    assert compound.notes == ()
    allocated = {sector for sector, value in enumerate(compound._fat_values) if value != 0xFFFFFFFF}
    assert allocated == set(compound._sector_owners)
    if compound.header.difat_sectors == 0:
        assert compound.as_dict() == independent_read(path.read_bytes())
    if item.id == "altium-third-party-pcbdoc-01":
        assert compound.header.fat_sectors == 154
        assert compound.header.difat_sectors == 1
    red, clsid, timed = _entry_counts(path, compound)
    census(
        "altium_cfb",
        item.id,
        {
            "major": compound.header.major,
            "sectors": compound.header.sector_count,
            "fat_sectors": compound.header.fat_sectors,
            "difat_sectors": compound.header.difat_sectors,
            "storages": len(compound.storages()),
            "streams": len(compound.streams()),
            "red_entries": red,
            "entries_with_clsid": clsid,
            "entries_with_time": timed,
            "notes": [issue.code for issue in compound.notes],
        },
    )


@pytest.mark.needs_kicad
@pytest.mark.kicad_min_major(10)
def test_difat_container_imports_in_kicad_10(tmp_path: Path) -> None:
    item = next(item for item in ITEMS if item.id == "altium-third-party-pcbdoc-01")
    source = require(item)
    cli = kicad_cli()
    assert cli is not None and kicad_cli_major() == 10
    target = tmp_path / "imported.kicad_pcb"
    env = oracle_env(tmp_path / "config")
    result = subprocess.run(
        [cli, "pcb", "import", "--format", "altium", "-o", str(target), str(source)],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        check=False,
    )
    census("altium_cfb_support", item.id, {"kicad_cli_exit": result.returncode})
    assert result.returncode == 0
