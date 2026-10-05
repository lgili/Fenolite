# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Format version constants written by kicad-cli (H-K-TOK-CONSTANTS, H-K-TOK-DEV)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from _corpus import manifest_items
from _kicad import cli, loads, major, run

from fenolite.backends.kicad import load
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind, detect_version

pytestmark = pytest.mark.needs_kicad
TOKENS = Path(__file__).resolve().parents[1] / "data" / "kicad" / "tokens"
OLD = TOKENS / "old"


def _check(kind: FileKind, written: Path) -> None:
    version = detect_version(load(written))
    constant = FORMAT_VERSIONS[kind][major()]
    assert version == constant, (
        f"{kind.value} on KiCad {major()}: constant {constant}, kicad-cli wrote {version}"
    )


def test_footprint_constant(tmp_path: Path) -> None:
    (tmp_path / "in.pretty").mkdir()
    shutil.copy(OLD / "old.kicad_mod", tmp_path / "in.pretty" / "old.kicad_mod")
    run("fp", "upgrade", "--force", "-o", tmp_path / "out.pretty", tmp_path / "in.pretty")
    _check(FileKind.FOOTPRINT, tmp_path / "out.pretty" / "old.kicad_mod")


def test_symbol_library_constant(tmp_path: Path) -> None:
    target = tmp_path / "old.kicad_sym"
    shutil.copy(OLD / "old.kicad_sym", target)
    run("sym", "upgrade", "--force", target)
    _check(FileKind.SYMBOL_LIB, target)


@pytest.mark.kicad_min_major(10)
def test_board_constant(tmp_path: Path) -> None:
    target = tmp_path / "old.kicad_pcb"
    shutil.copy(OLD / "old.kicad_pcb", target)
    run("pcb", "upgrade", "--force", target)
    _check(FileKind.BOARD, target)


@pytest.mark.kicad_min_major(10)
def test_schematic_constant(tmp_path: Path) -> None:
    target = tmp_path / "old.kicad_sch"
    shutil.copy(OLD / "old.kicad_sch", target)
    run("sch", "upgrade", "--force", target)
    _check(FileKind.SCHEMATIC, target)


def _sheet_errors(tmp_path: Path, version: int) -> str:
    sheet = tmp_path / f"w{version}.kicad_wks"
    text = (TOKENS / "skeleton.kicad_wks").read_text(encoding="utf-8")
    sheet.write_text(re.sub(r"\(version \d+\)", f"(version {version})", text, count=1), encoding="utf-8")
    # KiCad also uses home/cache/data and the OS temp directory (including instance locks).
    # KICAD_CONFIG_HOME alone does not isolate those paths between parallel oracle processes.
    home = tmp_path / f"home-{version}"
    temporary = home / "tmp"
    temporary.mkdir(parents=True)
    result = KicadCli(Path(cli()), timeout=600).run(
        [
            "pcb",
            "export",
            "svg",
            "board.kicad_pcb",
            "--drawing-sheet",
            "sheet.kicad_wks",
            "-l",
            "Edge.Cuts",
            "--mode-single",
            "-o",
            "out.svg",
        ],
        files={"board.kicad_pcb": TOKENS / "skeleton.kicad_pcb", "sheet.kicad_wks": sheet},
        env={
            "HOME": str(home),
            "XDG_CACHE_HOME": str(home / "cache"),
            "XDG_DATA_HOME": str(home / "data"),
            "TMPDIR": str(temporary),
            "TMP": str(temporary),
            "TEMP": str(temporary),
        },
    )
    assert result.ok, result.stdout + result.stderr
    assert "out.svg" in result.outputs, result.stdout + result.stderr
    return result.stdout + result.stderr


def test_worksheet_boundary(tmp_path: Path) -> None:
    constant = FORMAT_VERSIONS[FileKind.WORKSHEET][major()]
    assert "Error loading drawing sheet" not in _sheet_errors(tmp_path, constant)
    newer = _sheet_errors(tmp_path, constant + 1)
    assert "Error loading drawing sheet" in newer and "more recent version" in newer


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("version", [20250513, 20250907])
def test_dev_versions_load_on_10(tmp_path: Path, version: int) -> None:
    """H-K-TOK-DEV: development versions of the 10.0 cycle load in 10.0 (authored board)."""
    board = tmp_path / "dev.kicad_pcb"
    text = (TOKENS / "future.kicad_pcb").read_text(encoding="utf-8")
    board.write_text(text.replace("(version 20260206)", f"(version {version})"), encoding="utf-8")
    assert loads(board)


@pytest.mark.needs_corpus
@pytest.mark.kicad_min_major(10)
def test_dev_demos(tmp_path: Path) -> None:
    """H-K-TOK-DEV on KiCad-written demo boards: every cached rt0 board with a dev version loads in 10.0."""
    released = set(FORMAT_VERSIONS[FileKind.BOARD].values())
    checked = 0
    for item in manifest_items("oracle"):
        if not item.path.is_file() or item.heavy or "rt0" not in item.uses:
            continue
        version = detect_version(load(item.path))
        if version in released or version < min(released):
            continue
        board = tmp_path / f"{item.id}.kicad_pcb"
        shutil.copy(item.path, board)
        assert loads(board), f"{item.id} (version {version}) does not load"
        checked += 1
    if not checked:
        pytest.skip("no cached development-version demo board")
