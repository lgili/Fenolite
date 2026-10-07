# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper of an Altium build whose pins have several pads (capability altium-build, "Pin maps in an Altium
build"; change c0123): the check of a copper source reads the nets by pad through the map, every pad of a
pin carrying the pin's net. The cases of a map of one pad per pin are those of the fix c0135, in
``test_altium_pad_map_copper.py``."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from _altium_padmap import D1, pad_nets
from _buildhelp import POUR, blink_variant

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, list[dict[str, str]]]:
    out = io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", io.StringIO())
        code = cli_main.main(["build", *args, "--confirm", "--json"])
    issues = json.loads(out.getvalue())["issues"] if out.getvalue() else []
    return code, [i for i in issues if i["severity"] == "error"]


def kicad_pads(folder: Path) -> dict[tuple[str, str], str]:
    (file,) = folder.glob("*.kicad_pcb")
    design = read_board(file.read_text(encoding="utf-8"), file=file.name)
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    names = {net.id: net.name for net in design.circuit.nets}
    return {
        (refs[fp.component_id], pad.number): names.get(pad.net_id or "", "")
        for fp in design.board.footprints
        for pad in fp.pads
        if pad.number
    }


BONDED_D1 = D1.replace('"Mini:Mini_LED_THT_3mm"', '"Mini:Mini_QFP-32_7x7mm_P0.8mm"').replace(
    ")", ', pad_map={"1": ("1", "5"), "2": ("2", "6")})'
)
"""The LED on a 32-pad footprint, each pin bonded to two pads (change c0123)."""


def bonded_script(folder: Path, *, bonded: bool) -> Path:
    """The blink with a ``GND`` pour, its LED on the 32-pad footprint and on the top side; with ``bonded``
    each pin of the LED is bonded to two pads. (On the bottom side a footprint whose pads are off its x
    axis is refused as copper source with or without a map, which is reported apart from this change.)"""
    plain = BONDED_D1[: BONDED_D1.index(", pad_map=")] + ")"
    script = blink_variant(folder, D1, BONDED_D1 if bonded else plain, append=POUR)
    text = script.read_text(encoding="utf-8")
    assert BOTTOM in text
    script.write_text(text.replace(BOTTOM, BOTTOM.replace(', side="bottom"', "")), encoding="utf-8")
    return script


BOTTOM = 'd1.place(mm(38), mm(20), side="bottom")'


@pytest.mark.parametrize("board_bonded", [True, False], ids=["same-map", "board-without-the-map"])
def test_copper_from_a_board_whose_pins_have_several_pads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board_bonded: bool
) -> None:
    """A pin bonded to several pads: every pad of the pin carries its net in the check of a copper source,
    so the KiCad board of the same script is accepted and the PCB document has the nets of that board. The
    board of the script without the map leaves the second pad of each pin on no net, and is refused."""
    board_script = bonded_script(tmp_path / "board-script", bonded=board_bonded)
    assert run(monkeypatch, str(board_script), "--out", str(tmp_path / "k")) == (0, [])
    (board,) = (tmp_path / "k").glob("*.kicad_pcb")
    script = bonded_script(tmp_path / "script", bonded=True)
    out = tmp_path / "a"
    args = (str(script), "--out", str(out), "--target", "altium", "--copper-from", str(board))
    code, errors = run(monkeypatch, *args)
    if not board_bonded:
        assert code == 5 and not out.exists()
        assert {i["code"] for i in errors} == {"altium.copper-board-mismatch"}
        assert sorted(i["message"].split(": ", 1)[1] for i in errors) == [
            "pad 5 of D1 is on no net there, the design puts it on GND",
            "pad 6 of D1 is on no net there, the design puts it on LED_A",
        ]
        return
    assert (code, errors) == (0, [])
    kicad, altium = kicad_pads(tmp_path / "k"), pad_nets(out)
    for number, net in {"1": "GND", "5": "GND", "2": "LED_A", "6": "LED_A"}.items():
        assert kicad[("D1", number)] == altium[("D1", number)] == net
