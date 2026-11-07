# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent export/ ERC of generated schematics (c0161 task 4.3)."""

from __future__ import annotations

import _a2kcases
import pytest
from _altium_sets import SETS, lay_out
from _probes import runner

pytestmark = pytest.mark.needs_kicad


def test_sample_schematic() -> None:
    assert not _a2kcases.schematic(_a2kcases.SAMPLE, runner())


@pytest.mark.needs_corpus
@pytest.mark.slow
@pytest.mark.parametrize("name", list(SETS))
def test_public_schematic(name, tmp_path) -> None:
    folder = lay_out(SETS[name], tmp_path / name)
    project = next(folder.rglob("*.PrjPcb"))
    assert not _a2kcases.schematic(project, runner())


@pytest.mark.parametrize("variant", ["sheets", "pages"])
def test_source_sheets_and_pages_load(variant, monkeypatch) -> None:
    """change c0372 task 2.2: the KiCad sheets of a flat project of two sheets, and the pages of a circuit
    too large for one, load in KiCad: ERC reads every page and the exported netlist is the circuit's."""
    from _erc import run_erc
    from _gensheets import BLINK, refusing_more_than, two_sheets

    from fenolite.convert import convert_project
    from fenolite.convert.sources import read_source

    if variant == "pages":
        refusing_more_than(monkeypatch, 2)
        source = read_source(BLINK)
    else:
        source = two_sheets()
    cli = runner()
    assert not _a2kcases.schematic(source, cli)
    conversion = convert_project(source, to="kicad", kicad_version=cli.major(), allow_lossy=True)
    pages = [name for name in conversion.files if name.endswith(".kicad_sch")]
    assert len(pages) == 3
    report = run_erc(cli, "blink.kicad_sch", dict(conversion.files))
    assert report.data is not None, report.stderr
    assert len(report.data["sheets"]) == 3
