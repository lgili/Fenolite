# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite net PATH NAME --islands [--without ...]`` (change c0500, design D4), on the Part J kit board (an
authored ``.PcbDoc``) and on ``two_layer.kicad_pcb``. ``islands`` stays the count; the list is
``island_list``."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fenolite.cli.main import main
from tests.unit.backends.altium.test_part_j import build_board

ROOT = Path(__file__).resolve().parents[3]
KICAD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


@pytest.fixture(scope="module")
def doc(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("kit") / "board"
    build_board(folder)
    return folder / "edit.PcbDoc"


def _net(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict]:
    code = main(["net", *argv, "--json"])
    out, err = capsys.readouterr()
    if code == 0:
        return code, json.loads(out)
    return code, json.loads(err.strip().splitlines()[-1])


def test_islands_of_an_altium_net(doc: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "Islands of an Altium net": one entry per counted island, each member named by a locator
    of the document or ``REF-PIN``; the count stays where it was."""
    code, reply = _net(capsys, str(doc), "GND", "--islands")
    net = reply["result"]["net"]
    assert code == 0 and len(net["island_list"]) == net["islands"] > 1
    wheres = [m["where"] for island in net["island_list"] for m in island["members"]]
    assert wheres and all(re.fullmatch(r"[A-Za-z0-9]+/Data#\d+|[A-Z]+\d+-\w+", w) for w in wheres), wheres


def test_cutting_a_track_splits_the_net(doc: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "Cutting a track": MID runs R1-2, two tracks, D1-2; without the first track it is two."""
    code, reply = _net(capsys, str(doc), "MID", "--without", "Tracks6/Data#27")
    cut = reply["result"]["net"]["cut"]
    assert code == 0 and cut["removed"] == ["Tracks6/Data#27"]
    assert (cut["islands_before"], cut["islands_after"], cut["split"]) == (1, 2, True) and "note" not in cut


def test_a_cut_on_a_zoned_net_says_fills_are_not_repoured(capsys: pytest.CaptureFixture[str]) -> None:
    code, reply = _net(capsys, str(KICAD), "GND", "--without", "/kicad_pcb/segment[2]")
    cut = reply["result"]["net"]["cut"]
    assert code == 0 and cut["note"] == "saved fills are not repoured" and cut["split"] is False


def test_a_name_that_is_not_on_the_board(doc: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "A name that is not on the board": exit 2, ``FEN-2001``, the hint names close locators."""
    code, error = _net(capsys, str(doc), "MID", "--without", "Tracks6/Data#99")
    assert code == 2 and error["code"] == "FEN-2001" and "Tracks6/Data#" in error["hint"]
    code, error = _net(capsys, str(doc), "--islands")
    assert code == 2 and error["code"] == "FEN-2001"


def test_without_the_options_the_reply_is_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    _, reply = _net(capsys, str(KICAD), "GND")
    assert not {"island_list", "cut"} & set(reply["result"]["net"])
