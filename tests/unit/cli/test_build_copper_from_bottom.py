# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A copper source whose footprint is on the bottom side with pads off its X axis (change c0142;
capability altium-build, "Bottom-side footprints of a copper source").

A KiCad board stores the pads of a bottom footprint mirrored about local X (``docs/formats/kicad/board.md``,
``H-G-BOTTOM-STORE``, ``KICAD-VERIFIED``). The check of a copper source compared those stored positions
with the library definition as they are, so a board whose bottom footprint has a pad off its X axis was
refused, with or without a pin-to-pad map; the blink's bottom LED has both pads on the axis. Here the
blink's controller, a QFP-32 of the authored mini library, is put on the bottom at 0 and 90 degrees, its
KiCad board is written by Fenolite's own build and handed to ``--copper-from``.
"""

from __future__ import annotations

import dataclasses
import io
import json
import sys
from pathlib import Path

import pytest
from _buildhelp import blink_variant

import fenolite.cli.main as cli_main
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.lens.altium_copper import library_pad_positions
from fenolite.model.design import Design

U1 = 'u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")'
MAPPED = U1.replace(")", ', pad_map={"1": "2", "2": "1"})')
"""The controller with pin 1 (``LED_DRV``) on pad 2 and pin 2 (marked open) on pad 1."""
PLACE = "u1.place(mm(14), mm(15), locked=True)"
MISMATCH = "altium.copper-board-mismatch"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def script(folder: Path, rot: int, *, mapped: bool, append: str = "") -> Path:
    """The blink under ``folder`` with ``U1`` on the bottom at ``rot`` degrees, mapped or not."""
    path = blink_variant(folder, PLACE, f'u1.place(mm(14), mm(15), rot={rot}, side="bottom", locked=True)')
    text = path.read_text(encoding="utf-8")
    if mapped:
        assert U1 in text
        text = text.replace(U1, MAPPED)
    path.write_text(text + append, encoding="utf-8")
    return path


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, list[dict[str, str]]]:
    out = io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", io.StringIO())
        code = cli_main.main(["build", *args, "--confirm", "--json"])
    issues = json.loads(out.getvalue())["issues"] if out.getvalue() else []
    return code, [i for i in issues if i["severity"] == "error"]


def kicad_board(monkeypatch: pytest.MonkeyPatch, folder: Path, rot: int, *, mapped: bool) -> Path:
    """The KiCad board of the variant, written by ``fenolite build`` into ``folder / "k"``."""
    source = script(folder / "board-script", rot, mapped=mapped)
    assert run(monkeypatch, str(source), "--out", str(folder / "k")) == (0, [])
    (board,) = (folder / "k").glob("*.kicad_pcb")
    return board


def controller(design: Design) -> object:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    (found,) = [f for f in design.board.footprints if refs[f.component_id] == "U1"]
    return found


def pad_centres(design: Design, backend: object) -> dict[tuple[str, str], Point]:
    return {(p.ref, p.number): p.position for p in backend.board_pads(design)}  # type: ignore[attr-defined]


def assert_pads_where_kicad_has_them(board: Path, out: Path) -> None:
    """Every pad of the written PCB document is where the KiCad board has it, up to one common shift of
    the frame, within 2 nm (the document holds 1/10 000 mil)."""
    kicad = pad_centres(read_board(board.read_text(encoding="utf-8"), file=board.name), KicadBackend())
    (document,) = out.glob("*.PcbDoc")
    backend = AltiumBackend()
    altium = pad_centres(backend.board_from_bytes(document.read_bytes(), file=document.name).design, backend)
    assert sorted(kicad) == sorted(altium) and ("U1", "32") in kicad
    anchor = ("D1", "1")
    dx, dy = kicad[anchor].x - altium[anchor].x, kicad[anchor].y - altium[anchor].y
    for key, at in kicad.items():
        assert abs(at.x - altium[key].x - dx) <= 2 and abs(at.y - altium[key].y - dy) <= 2, key


@pytest.mark.parametrize("rot", [0, 90])
@pytest.mark.parametrize("mapped", [False, True], ids=["no-map", "map"])
def test_bottom_footprint_with_pads_off_its_axis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rot: int, mapped: bool
) -> None:
    """The board of the same script is accepted, and every pad of the document is where KiCad has it."""
    board = kicad_board(monkeypatch, tmp_path, rot, mapped=mapped)
    stored = controller(read_board(board.read_text(encoding="utf-8"), file=board.name))
    assert stored.side == "bottom" and stored.rotation == rot * 1_000_000  # type: ignore[attr-defined]
    raw = sorted((p.number, p.position.x, p.position.y) for p in stored.pads)  # type: ignore[attr-defined]
    assert raw != sorted(library_pad_positions(stored))  # type: ignore[arg-type]
    out = tmp_path / "a"
    design = script(tmp_path / "script", rot, mapped=mapped)
    code, errors = run(
        monkeypatch, str(design), "--out", str(out), "--target", "altium", "--copper-from", str(board)
    )
    assert (code, errors) == (0, [])
    assert_pads_where_kicad_has_them(board, out)


@pytest.mark.parametrize(
    ("design_mapped", "board_mapped"),
    [(True, False), (False, True)],
    ids=["board-without-the-map", "board-with-a-map-the-script-lacks"],
)
def test_a_board_of_the_other_map_is_refused_by_its_nets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, design_mapped: bool, board_mapped: bool
) -> None:
    """A bottom board of the other assignment is refused for the nets of pads 1 and 2, not for the pad
    positions: the land is the same."""
    board = kicad_board(monkeypatch, tmp_path, 90, mapped=board_mapped)
    design = script(tmp_path / "script", 90, mapped=design_mapped)
    out = tmp_path / "a"
    code, errors = run(
        monkeypatch, str(design), "--out", str(out), "--target", "altium", "--copper-from", str(board)
    )
    assert code == 5 and not out.exists()
    assert {(i["code"], i["where"]) for i in errors} == {(MISMATCH, "U1.1"), (MISMATCH, "U1.2")}
    assert not [i for i in errors if "the pads of" in i["message"]]


@pytest.mark.parametrize("rot", [0, 90])
def test_a_bottom_footprint_stored_unmirrored_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rot: int
) -> None:
    """Negative control: the same board with the bottom controller's pads stored as the library has them
    (not mirrored about local X) is refused for its pads."""
    board = kicad_board(monkeypatch, tmp_path, rot, mapped=False)
    design = read_board(board.read_text(encoding="utf-8"), file=board.name)
    stored = controller(design)

    def unmirror(pad: object) -> object:
        at = pad.position  # type: ignore[attr-defined]
        return dataclasses.replace(pad, position=dataclasses.replace(at, y=-at.y))  # type: ignore[type-var]

    flipped = dataclasses.replace(stored, pads=tuple(unmirror(p) for p in stored.pads))  # type: ignore[type-var,attr-defined]
    assert design.board is not None
    footprints = tuple(flipped if f is stored else f for f in design.board.footprints)
    edited = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=footprints))
    board.write_text(write_board(edited).text, encoding="utf-8")
    assert controller(read_board(board.read_text(encoding="utf-8"), file=board.name)) != stored
    out = tmp_path / "a"
    source = script(tmp_path / "script", rot, mapped=False)
    code, errors = run(
        monkeypatch, str(source), "--out", str(out), "--target", "altium", "--copper-from", str(board)
    )
    assert code == 5 and not out.exists()
    (found,) = errors
    assert (found["code"], found["where"]) == (MISMATCH, "U1")
    assert (
        "the pads of Mini:Mini_QFP-32_7x7mm_P0.8mm differ from the footprint the design resolves"
        in (found["message"])
    )


TRACK = """
from fenolite.dsl import via_step

design.track(
    "u1_out",
    u1.pad(1), via_step(mm(16.8), mm(21.5), to="F.Cu", diameter=mm(0.6), drill=mm(0.3)), r1.pad(1),
    layer="B.Cu", width=mm(0.3),
)
"""
"""Script copper on the bottom controller at 90 degrees: from its pad 1 (at 2.8, 4.15 mm from its
origin, on the bottom row) down to a via, then on the top to ``R1``'s pad 1."""


def test_script_copper_on_a_bottom_footprint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The script source (origin ``script``) holds the stored, mirrored pads too, and is accepted; the
    same script's KiCad board is accepted as ``--copper-from``, and both documents have equal bytes."""
    source = script(tmp_path / "s", 90, mapped=False, append=TRACK)
    assert run(monkeypatch, str(source), "--out", str(tmp_path / "k")) == (0, [])
    (board,) = (tmp_path / "k").glob("*.kicad_pcb")
    assert "(segment" in board.read_text(encoding="utf-8") and "(via" in board.read_text(encoding="utf-8")
    assert run(monkeypatch, str(source), "--out", str(tmp_path / "a"), "--target", "altium") == (0, [])
    assert_pads_where_kicad_has_them(board, tmp_path / "a")
    code, errors = run(
        monkeypatch,
        str(source),
        "--out",
        str(tmp_path / "b"),
        "--target",
        "altium",
        "--copper-from",
        str(board),
    )
    assert (code, errors) == (0, [])
    (script_doc,) = (tmp_path / "a").glob("*.PcbDoc")
    (board_doc,) = (tmp_path / "b").glob("*.PcbDoc")
    assert script_doc.read_bytes() == board_doc.read_bytes()
