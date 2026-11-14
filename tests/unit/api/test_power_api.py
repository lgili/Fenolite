# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.analyze_power`` and ``analyze_split`` on a board, a path and an Altium edit session
(change c0503; capability python-api, "Power analysis in the API")."""

from __future__ import annotations

from pathlib import Path

from _power import strip

from fenolite.analysis import analyze_power as power_of_design
from fenolite.api import Board, analyze_power, analyze_split, read_board
from fenolite.core.evidence import Evidence, Level

RHO = 20_000
"""An illustrative resistivity in picoohm-metres; Fenolite ships none."""
PATHS = ((("J1-1",), ("U1-1",)),)


def test_a_board_gives_the_analysis() -> None:
    """A ``Board`` gives the rows of the analysis of its design, and the split solves them."""
    design, pads = strip()
    board = Board("strip", "0" * 64, "model", design, pads, (), Evidence(Level.INFERRED))
    kwargs = {"copper_thickness": {"*": 50_000}, "resistivity_pohm_m": RHO}
    power = analyze_power(board, paths=PATHS, **kwargs)  # type: ignore[arg-type]
    assert power == power_of_design(design, pads=pads, paths=PATHS, **kwargs)  # type: ignore[arg-type]
    split = analyze_split(board, power=power, grid=250_000, deadline=60, **kwargs)  # type: ignore[arg-type]
    (row,) = split.rows
    assert row.complete and row.cell_nm == 250_000 and row.within is True


def test_a_fix_checked_on_a_session_before_it_is_committed(tmp_path: Path) -> None:
    """Scenario "A fix checked before it is committed": a queued clone of the ``VIN`` track, 1 mm wide, on
    the Part J kit board (authored for Fenolite) lowers the high end of the path's resistance; the
    document is unchanged."""
    from fenolite.backends.altium import edit
    from tests.unit.backends.altium.test_part_j import build_board

    build_board(tmp_path)
    path = tmp_path / "edit.PcbDoc"
    before = path.read_bytes()
    on_disk = read_board(path)
    assert on_disk.design.board is not None
    nets = {net.id: net.name for net in on_disk.design.circuit.nets}
    tracks = on_disk.design.board.tracks
    # the probe track runs from (10, 5) mm in the document's frame (Y up): it gives the offset of the frames
    probe = next(t for t in tracks if nets.get(t.net_id or "") == "GND" and t.end.x - t.start.x > 9_000_000)
    dx, dy = probe.start.x - 10_000_000, -probe.start.y - 5_000_000
    track = next(t for t in tracks if nets.get(t.net_id or "") == "VIN" and t.start.y - t.end.y < -7_000_000)
    paths = ((("R1-1",), ("R2-1",)),)
    kwargs = {"paths": paths, "copper_thickness": {"*": 35_000}, "resistivity_pohm_m": RHO}
    filed = analyze_power(path, **kwargs)  # type: ignore[arg-type]
    session = edit.open(path, gates={"clone": True})
    assert isinstance(session, edit.Session)
    ends = ((track.start.x - dx, -track.start.y - dy), (track.end.x - dx, -track.end.y - dy))
    session.clone(edit.Track(*ends, "VIN"), width=1_000_000)
    pending = analyze_power(session, **kwargs)  # type: ignore[arg-type]
    (old,), (new,) = filed.rows, pending.rows
    assert old.resistance_uohm is not None and new.resistance_uohm is not None
    assert old.resistance_uohm.high is not None and new.resistance_uohm.high is not None
    assert new.resistance_uohm.high < old.resistance_uohm.high
    # the document holds 1/10 000 mil: the width reads back within a nanometre
    wide = [e for e in new.elements if e.kind == "track" and (e.area_nm2 or 0) > 999_000 * 35_000]
    assert wide and path.read_bytes() == before
