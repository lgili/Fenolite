# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact numbers, ids and the closed issue-code set of board reads (kicad-file-backend, c0009)."""

from __future__ import annotations

from _boards import FIXTURE, SCENARIOS, uid

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.pcb import ISSUE_CODES, read_board
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.base import Opaque


def _root_opaque(text: str) -> list[str]:
    design = read_board(text)
    assert design.board is not None
    return [s.fragment for s in slotlib.from_ext(design.board.ext["kicad"]) if isinstance(s, Opaque)]


def test_sub_nanometre_track() -> None:
    issues: list[Issue] = []
    design = read_board(SCENARIOS["sub-nm"], issues=issues)
    assert design.board is not None and design.board.tracks == ()
    assert any(f.startswith("(segment (start 0.0000001 0)") for f in _root_opaque(SCENARIOS["sub-nm"]))
    assert [(i.code, i.severity) for i in issues] == [("kicad.board.inexact-length", "info")]


def test_unrepresentable_footprint_angle() -> None:
    issues: list[Issue] = []
    design = read_board(SCENARIOS["fp-angle"], issues=issues)
    assert design.board is not None and design.board.footprints == () and design.circuit.components == ()
    assert any(f.startswith('(footprint "Lib:FP"') for f in _root_opaque(SCENARIOS["fp-angle"]))
    assert [(i.code, i.severity) for i in issues] == [("kicad.board.inexact-angle", "info")]


def test_repeated_uuid() -> None:
    issues: list[Issue] = []
    design = read_board(SCENARIOS["repeat-uuid"], issues=issues)
    assert design.board is not None
    u = uid(9)
    assert [t.id for t in design.board.tracks] == [
        derived_id("trk", "kicad", u),
        derived_id("trk", "kicad", f"{u}:1"),
    ]
    assert [t.native_ids["kicad"] for t in design.board.tracks] == [u, u]
    assert [(i.code, i.severity) for i in issues] == [("kicad.board.duplicate-uuid", "warning")]


def test_oval_drill_on_a_board_pad() -> None:
    issues: list[Issue] = []
    design = read_board(SCENARIOS["oval-drill"], issues=issues)
    assert design.board is not None
    assert design.board.footprints[0].pads[0].drill is None
    assert [i.code for i in issues] == ["kicad.board.kept-opaque"]
    assert not [i for i in issues if i.code.startswith("kicad.lib.")]


def test_ids_of_board_items() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    track = design.board.tracks[0]
    assert track.id == derived_id("trk", "kicad", track.native_ids["kicad"])
    fp = design.board.footprints[0]
    pad = fp.pads[0]
    assert pad.id == derived_id("pad", "kicad", f"{fp.native_ids['kicad']}:{pad.native_ids['kicad']}")
    assert design.board.id == derived_id("brd", "kicad", "kicad_pcb")
    assert design.header.id == derived_id("dsn", "kicad", "kicad_pcb")
    gnd = design.nets_by_name["GND"]
    assert gnd.id == derived_id("net", "kicad", "net:GND")
    f_cu = design.board.layers[0]
    assert f_cu.id == derived_id("lay", "kicad", "layer:F.Cu")
    component = design.by_ref["R1"]
    assert component.id == derived_id("cmp", "kicad", f"fp:{fp.native_ids['kicad']}")
    assert component.pins[0].id == derived_id("pin", "kicad", f"{fp.native_ids['kicad']}:pin:1")


def test_closed_set() -> None:
    """Every code produced by the board scenarios is in ``ISSUE_CODES`` with its severity."""
    seen: dict[str, str] = {}
    for text in [FIXTURE.read_text(encoding="utf-8"), *SCENARIOS.values()]:
        issues: list[Issue] = []
        read_board(text, issues=issues)
        seen.update({i.code: i.severity for i in issues})
    assert not [c for c in seen if c.startswith("model.")], "model findings come from Design.validate()"
    board_codes = {c: s for c, s in seen.items() if not c.startswith("kicad.version.")}
    assert board_codes and all(ISSUE_CODES.get(c) == s for c, s in board_codes.items()), board_codes
    assert set(board_codes) == set(ISSUE_CODES)
