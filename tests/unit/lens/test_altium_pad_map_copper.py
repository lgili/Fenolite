# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A ``pad_map`` and copper in an Altium build (capability altium-build, "Pin maps in an Altium build";
change c0135): the check of a copper source reads the nets by pad through the map, as the PCB document
does, so a routed script with a map builds, a routed KiCad board of the same script is accepted as copper
source, and a board that was routed without the map is refused with a true message."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from _altium_padmap import D1, SWAPPED, pad_nets
from _buildhelp import POUR, blink_variant

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board

ROOT = Path(__file__).resolve().parents[3]
ROUTED = (ROOT / "examples" / "blink_routed" / "design.py").read_text(encoding="utf-8")
"""The routed blink: three tracks, two of them ending on the pads of ``D1``, vias and a stitched fence."""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def routed_script(folder: Path, *, mapped: bool, append: str = "") -> Path:
    """The routed blink under ``folder``; with ``mapped`` the pins of ``D1`` are on the other pads and the
    two tracks that end on ``D1`` end on the pad of the same net as before."""
    assert D1 in ROUTED
    text = ROUTED
    if mapped:
        text = text.replace(D1, SWAPPED)
        text = text.replace("d1.pad(2)", "d1.pad(X)").replace("d1.pad(1)", "d1.pad(2)")
        text = text.replace("d1.pad(X)", "d1.pad(1)")
    script = blink_variant(folder, "", "")
    script.write_text(text + append, encoding="utf-8")
    return script


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


@pytest.mark.parametrize("mapped", [False, True], ids=["no-map", "map"])
def test_script_tracks_on_a_mapped_part(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mapped: bool
) -> None:
    """Tracks that end on the pads of the mapped part: the build is not refused, and the pads of the PCB
    document carry the nets the KiCad board of the same script carries."""
    script = routed_script(tmp_path / "script", mapped=mapped)
    assert run(monkeypatch, str(script), "--out", str(tmp_path / "k")) == (0, [])
    assert run(monkeypatch, str(script), "--out", str(tmp_path / "a"), "--target", "altium") == (0, [])
    kicad, altium = kicad_pads(tmp_path / "k"), pad_nets(tmp_path / "a")
    wanted = {"1": "LED_A", "2": "GND"} if mapped else {"1": "GND", "2": "LED_A"}
    for number, net in wanted.items():
        assert kicad[("D1", number)] == altium[("D1", number)] == net


@pytest.mark.parametrize("mapped", [False, True], ids=["no-map", "map"])
def test_a_zone_beside_a_mapped_part(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mapped: bool) -> None:
    script = routed_script(tmp_path / "script", mapped=mapped, append=POUR)
    assert run(monkeypatch, str(script), "--out", str(tmp_path / "a"), "--target", "altium") == (0, [])
    assert pad_nets(tmp_path / "a")[("D1", "2" if mapped else "1")] == "GND"


@pytest.mark.parametrize(
    ("design_mapped", "board_mapped"),
    [(False, False), (True, True), (True, False), (False, True)],
    ids=["no-map", "map-on-both", "board-without-the-map", "board-with-a-map-the-script-lacks"],
)
def test_copper_from_a_kicad_board(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, design_mapped: bool, board_mapped: bool
) -> None:
    """``--copper-from`` the KiCad board of the same script is accepted with and without a map. A board
    that was routed for the other assignment of the pads is refused, and the message names the net the
    design really puts on the pad: before, a design with a map was refused against its own board, and
    accepted against a board routed without the map, whose track then ended on a pad of another net."""
    board_script = routed_script(tmp_path / "board-script", mapped=board_mapped)
    assert run(monkeypatch, str(board_script), "--out", str(tmp_path / "k")) == (0, [])
    (board,) = (tmp_path / "k").glob("*.kicad_pcb")
    script = routed_script(tmp_path / "script", mapped=design_mapped)
    out = tmp_path / "a"
    code, errors = run(
        monkeypatch, str(script), "--out", str(out), "--target", "altium", "--copper-from", str(board)
    )
    if design_mapped == board_mapped:
        assert (code, errors) == (0, [])
        assert pad_nets(out)[("D1", "2" if design_mapped else "1")] == "GND"
        return
    assert code == 5 and not out.exists()
    assert {i["code"] for i in errors} == {"altium.copper-board-mismatch"}
    there, wanted = ("GND", "LED_A") if design_mapped else ("LED_A", "GND")
    (first,) = [i for i in errors if i["where"].endswith("D1.1") or "pad 1 of D1" in i["message"]]
    assert f"pad 1 of D1 is on {there} there, the design puts it on {wanted}" in first["message"]
