# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Existing adapters and source choices (c0264, import sources and unsupported sources)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from _library_import import DATA, fixtures

from fenolite.core.errors import FormatError
from fenolite.library.importer.sources import ImportUsageError, read_sources


def test_authored_fixtures_are_reproducible() -> None:
    assert {path.name: path.read_bytes() for path in DATA.iterdir()} == fixtures()


def test_authored_archives_ignore_windows_creator_default(monkeypatch: pytest.MonkeyPatch) -> None:
    class WindowsZipInfo(zipfile.ZipInfo):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.create_system = 0

    monkeypatch.setattr(zipfile, "ZipInfo", WindowsZipInfo)
    # Compare the complete ZIP container, not only extracted members or a normalized projection.
    assert {path.name: path.read_bytes() for path in DATA.iterdir()} == fixtures()


def test_kicad_and_zip_sources_keep_pins_and_pads() -> None:
    got = read_sources([DATA / "exb6202.zip"])
    assert got.symbol.name == "EXB6202" and len(got.symbol.pins) == len(got.footprint.pads) == 8
    assert got.steps[0].data == (DATA / "exb6202.step").read_bytes()
    assert len(got.sources) == 4 and got.skipped[0].reason == "unsupported format"
    assert all("/" not in source.file for source in got.sources)


def test_altium_symbol_is_drawn_from_pin_table() -> None:
    got = read_sources([DATA / "exb6202.SchLib", DATA / "exb6202.PcbLib"])
    assert got.altium_symbol and len(got.symbol.pins) == 8 and got.symbol.graphics
    assert [(p.number, p.name, p.etype) for p in got.symbol.pins] == [
        (str(n), f"IO{n}", "passive") for n in range(1, 9)
    ]
    assert "library.import-symbol-regenerated" in {issue.code for issue in got.issues}


def test_preference_selects_tool_and_keeps_other_footprint() -> None:
    paths = [
        DATA / name for name in ("exb6202.kicad_sym", "exb6202.kicad_mod", "exb6202.SchLib", "exb6202.PcbLib")
    ]
    for prefer in ("kicad", "altium"):
        got = read_sources(paths, prefer=prefer)
        assert got.altium_symbol == (prefer == "altium") and len(got.alternatives) == 1


def test_intlib_refused_even_before_read(tmp_path: Path) -> None:
    with pytest.raises(ImportUsageError, match="IntLib") as error:
        read_sources([tmp_path / "part.IntLib"])
    assert ".SchLib and .PcbLib" in error.value.hint


def test_two_footprints_need_selection(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.kicad_sym", (DATA / "exb6202.kicad_sym").read_bytes())
        body = (DATA / "exb6202.kicad_mod").read_text()
        archive.writestr("a.kicad_mod", body.replace("EXB6202", "A"))
        archive.writestr("b.kicad_mod", body.replace("EXB6202", "B"))
    path = tmp_path / "two.zip"
    path.write_bytes(buffer.getvalue())
    with pytest.raises(ImportUsageError) as error:
        read_sources([path])
    assert "available: A, B" in error.value.hint
    assert read_sources([path], footprint="B").footprint.name == "B"


def test_not_a_step_file(tmp_path: Path) -> None:
    bad = tmp_path / "body.step"
    bad.write_bytes(b"Authored for Fenolite; not STEP")
    with pytest.raises(FormatError, match="STEP") as error:
        read_sources([DATA / "exb6202.kicad_sym", DATA / "exb6202.kicad_mod", bad])
    assert error.value.file == "body.step"
