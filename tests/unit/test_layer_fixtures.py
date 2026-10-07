# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The filled six- and eight-layer fixtures follow the build (capability kicad-oracle, "Builds of four,
six and eight copper layers pass the oracle", scenario "Fixtures follow the build"; change c0100).

``tests/data/kicad/layers/l<n>_t9_filled.kicad_pcb`` is the target-9 build of the variant of
``tests/kicad/build/_layercases.py`` filled by KiCad 10.0.6, which KiCad 9.0.9 judges because it cannot
refill zones. Each fixture must equal the target-9 build of its count except for the fills and the
``filled`` flag of its zones, so a change of the build cannot leave a stale fixture. No ``kicad-cli`` runs.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board, write_board

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kicad" / "build"))

import _layercases as lc  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def built_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, copper: int) -> str:
    """The board of the target-9 build of the variant, with the arguments of the oracle run."""
    script = lc.write_script(tmp_path / f"src{copper}", copper)
    out = tmp_path / f"out{copper}"
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    args = ["build", str(script), "--out", str(out), "--kicad-version", "9", *lc.SEED, "--no-backup"]
    assert cli_main.main([*args, "--confirm", "--json"]) == 0
    return (out / "blink.kicad_pcb").read_text(encoding="utf-8")


def unfilled_text(path: Path) -> str:
    """The fixture written again for target 9 without its fills."""
    fixture = read_board(path.read_text(encoding="utf-8"))
    assert fixture.board is not None
    assert all(zone.filled and len(zone.fills) == 1 for zone in fixture.board.zones)
    return write_board(lc.without_fills(fixture), target=9).text


@pytest.mark.parametrize("copper", lc.FIXTURE_COUNTS)
def test_fixtures_follow_the_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, copper: int) -> None:
    path = lc.fixture(copper)
    assert path.is_file(), f"{path.name} is missing: run tests/kicad/build/test_layer_builds.py on KiCad 10"
    fixture = read_board(path.read_text(encoding="utf-8"))
    assert fixture.board is not None
    names = tuple(layer.name for layer in fixture.board.layers if layer.kind == "copper")
    assert names == lc.copper_names(copper) and len(fixture.board.zones) == copper - 2
    assert unfilled_text(path) == built_board(tmp_path, monkeypatch, copper), (
        f"{path.name} differs from the target-9 build of {copper} layers: write it again with "
        "FENOLITE_PROBES_WRITE=1 on KiCad 10 (tests/kicad/build/test_layer_builds.py)"
    )


def test_a_changed_build_is_noticed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The comparison fails, naming the fixture's rule, when the build gives another board: here the
    six-layer fixture against the build of the eight-layer variant."""
    assert unfilled_text(lc.fixture(6)) != built_board(tmp_path, monkeypatch, 8)
    assert unfilled_text(lc.fixture(6)) != lc.fixture(6).read_text(encoding="utf-8")  # the fills are left out
