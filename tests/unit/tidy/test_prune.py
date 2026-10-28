# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.tidy.prune`` (change c0208; capability copper-tidy, "Prune dangling copper"), on the authored
bench of ``tests/_tidybench.py``. Hermetic."""

from __future__ import annotations

import dataclasses

from _groundties import _p
from _tidybench import bench

from fenolite.analysis.connectivity import connectivity
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.frame import board_pads
from fenolite.model.design import Design
from fenolite.tidy import prune
from fenolite.tidy.graph import keeps_groups, net_pieces


def _groups(design: Design) -> dict[str, tuple[tuple[str, ...], ...]]:
    report = connectivity(design, pads=board_pads(design))
    return {row.name: row.pads for row in report.nets}


def _ends(design: Design) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    assert design.board is not None
    return {((t.start.x, t.start.y), (t.end.x, t.end.y)) for t in design.board.tracks}


def test_a_stub_after_routing() -> None:
    """Scenario "A stub after routing": the stub, the lead and its via go; every net keeps its groups."""
    design = bench()
    result = prune(design, pads=board_pads(design))
    board = result.design.board
    assert board is not None
    assert _ends(result.design) == {
        ((10_000_000, 10_000_000), (30_000_000, 10_000_000)),
        ((30_000_000, 10_000_000), (30_000_000, 20_000_000)),
        ((10_000_000, 30_000_000), (25_000_000, 30_000_000)),
        ((18_000_000, 36_000_000), (18_000_000, 30_000_000)),
    }
    assert board.vias == ()
    assert [(edit.step, edit.reason, edit.net) for edit in result.edits] == [
        ("prune", "free-end", "SIG"),
        ("prune", "via-under-two-layers", "SIG"),
        ("prune", "free-end", "SIG"),
    ]
    assert result.edits[0].at == _p(20, 12) and result.edits[1].at == _p(15, 14)
    assert _groups(result.design) == _groups(design)


def test_a_bridge_with_a_free_end_stays() -> None:
    """``k`` has a free end but is the only way from ``U3-1`` to ``U4-1``: it stays, with ``tidy.kept``."""
    design = bench(stub=False, lead=False)
    result = prune(design, pads=board_pads(design))
    assert result.edits == () and result.design == design
    assert [(found.code, found.severity, found.where) for found in result.issues] == [
        ("tidy.kept", "info", "trk_00000000-0000-4000-8000-000000000003")
    ]


def test_locked_and_kept_copper_stays() -> None:
    design = bench(lead=False, bus=False, locked_stub=True)
    pads = board_pads(design)
    result = prune(design, pads=pads)
    assert [edit.removed for edit in result.edits] == [("trk_00000000-0000-4000-8000-000000000003",)]
    assert _p(25, 8) in {t.end for t in (result.design.board.tracks if result.design.board else ())}
    stub = "trk_00000000-0000-4000-8000-000000000003"
    assert prune(design, pads=pads, keep={stub}).edits == ()


def test_script_copper_is_kept_by_the_caller() -> None:
    """The CLI keeps script copper by passing its ids; a track with a copper uuid is only kept so."""
    design = bench(lead=False, bus=False)
    assert design.board is not None
    tracks = tuple(
        dataclasses.replace(t, native_ids={"kicad": copper_uuid("s", "seg[0]")}) for t in design.board.tracks
    )
    marked = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=tracks))
    keep = {t.id for t in tracks}
    assert prune(marked, pads=board_pads(marked), keep=keep).edits == ()


def test_nets_select() -> None:
    design = bench()
    assert prune(design, pads=board_pads(design), nets={"BUS"}).edits == ()
    assert len(prune(design, pads=board_pads(design), nets={"SIG"}).edits) == 3


def test_a_via_in_a_zone_outline_stays() -> None:
    """A via whose second layer lies inside an outline of a zone of its net counts as joined there, also
    without a fill."""
    from _groundties import _box, _zone

    design = bench(stub=False, bus=False)
    assert design.board is not None
    sig = next(net.id for net in design.circuit.nets if net.name == "SIG")
    zone = dataclasses.replace(_zone(1, sig, _box(12, 12, 18, 16), fill=False), layers=("B.Cu",))
    zoned = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(zone,)))
    assert prune(zoned, pads=board_pads(zoned)).edits == ()


def test_unshaped_copper_skips_the_net() -> None:
    design = bench(bus=False)
    assert design.board is not None
    broken = dataclasses.replace(design.board.tracks[0], width=-1)
    tracks = (broken, *design.board.tracks[1:])
    bad = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=tracks))
    result = prune(bad, pads=board_pads(bad))
    assert result.edits == () and [found.code for found in result.issues] == ["tidy.net-skipped"]


def test_keeps_groups() -> None:
    design = bench(stub=False, lead=False)
    pieces = net_pieces(design, board_pads(design)).pieces
    bus = next(net.id for net in design.circuit.nets if net.name == "BUS")
    held = list(pieces[bus])
    bridge = "trk_00000000-0000-4000-8000-000000000003"
    assert keeps_groups(held, held)
    assert not keeps_groups(held, [p for p in held if p.ident != bridge], removed=(bridge,))
    assert not keeps_groups(held, [p for p in held if p.ident != bridge])
