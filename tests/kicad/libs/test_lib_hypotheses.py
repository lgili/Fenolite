# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of H-K-LIB-NAME-STEM and H-K-LIB-SYMDIR (docs/hypotheses.md), major-aware and isolated."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import pytest
from _kicad import cli, major
from _libs import MINI, isolated_kicad_env, kicad, make_symdir

from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.model.library import SymbolDef

pytestmark = pytest.mark.needs_kicad


def _fixture(running: int, ten: str, nine: str) -> Path:
    return MINI / (ten if running >= 10 else nine)


def test_name_stem(tmp_path: Path) -> None:
    """H-K-LIB-NAME-STEM: a footprint is named after its file stem, not its header name."""
    running = major()
    library = tmp_path / "Lib.pretty"
    library.mkdir()
    shutil.copyfile(
        _fixture(running, "Mini.pretty", "Mini_v9.pretty") / "Mini_R_0603.kicad_mod",
        library / "Other.kicad_mod",
    )
    out = tmp_path / "svg"
    out.mkdir()
    result = kicad(cli(), isolated_kicad_env(tmp_path), "fp", "export", "svg", library, "-o", out)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(p.name for p in out.glob("*.svg")) == ["Other.svg"]


def _flat(symbols: tuple[SymbolDef, ...]) -> dict[str, SymbolDef]:
    return {s.name: dataclasses.replace(s, provenance=None, ext={}) for s in resolve_extends(symbols)}


def test_symdir(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """H-K-LIB-SYMDIR: kicad-cli reads a symbol folder as one library, ``extends`` across its files."""
    running = major()
    if running < 10:
        request.applymarker(pytest.mark.xfail(strict=False, reason="symbol folders are new in KiCad 10"))
    folder = make_symdir(
        _fixture(running, "Mini.kicad_sym", "Mini_v9.kicad_sym"), tmp_path / "Mini.kicad_symdir"
    )
    env = isolated_kicad_env(tmp_path)
    out = tmp_path / "svg"
    out.mkdir()
    result = kicad(cli(), env, "sym", "export", "svg", folder, "-o", out)
    assert result.returncode == 0, result.stdout + result.stderr
    names = {p.stem for p in folder.glob("*.kicad_sym")}
    assert {p.stem.split("_unit")[0] for p in out.glob("*.svg")} == names
    packed = tmp_path / "packed.kicad_sym"
    result = kicad(cli(), env, "sym", "upgrade", "--force", folder, "-o", packed)
    assert result.returncode == 0 and packed.is_file(), result.stdout + result.stderr
    assert _flat(read_symbol_library(packed, library="Mini")) == _flat(
        read_symbol_library(folder, library="Mini")
    )
