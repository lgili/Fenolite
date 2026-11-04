# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper on no net, arcs on one line and repeated zone names in the Python import (capability
board-to-code, "Copper on no net and arcs on one line" and "Exact zone names"; change c0375). Authored
variants of the two-sheet board alone."""

from __future__ import annotations

from pathlib import Path

import pytest
from _importcode import BOARD, build, built_board, imported

from fenolite.api import read_board
from fenolite.dsl import Design, Net, mm
from fenolite.dsl.errors import DslError

EXTRA = """
\t(segment (start 120 140) (end 125 140) (width 0.3) (layer "F.Cu")
\t\t(uuid "66656e6f-6c69-0375-0000-000000000001"))
\t(arc (start 120 145) (mid 122.5 143) (end 125 145) (width 0.3) (layer "F.Cu")
\t\t(uuid "66656e6f-6c69-0375-0000-000000000002"))
\t(arc (start 120 150) (mid 122.5 150) (end 125 150) (width 0.3) (layer "B.Cu") (net "GND")
\t\t(uuid "66656e6f-6c69-0375-0000-000000000003"))
"""

ZONE = """
\t(zone (net "GND") (layer "F.Cu") (uuid "66656e6f-6c69-0375-0000-00000000001{n}") (name "{name}")
\t\t(hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25)
\t\t(fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))
\t\t(polygon (pts (xy {x} 112) (xy {x2} 112) (xy {x2} 116) (xy {x} 116))))
"""


def _variant(tmp: Path, name: str, extra: str) -> Path:
    text = BOARD.read_text(encoding="utf-8").rstrip()
    assert text.endswith(")")
    folder = tmp / name
    folder.mkdir()
    target = folder / f"{name}.kicad_pcb"
    target.write_text(text[:-1] + extra + ")\n", encoding="utf-8")
    return target


def _where(design, kind: str, y: int) -> list[tuple[object, ...]]:  # type: ignore[no-untyped-def]
    names = {net.id: net.name for net in design.circuit.nets}
    items = design.board.tracks if kind == "track" else design.board.arcs
    return [(i.start, i.end, i.layer, names.get(i.net_id or "")) for i in items if i.start.y == y]


def test_netless_copper_and_line_arcs_are_written(tmp_path: Path) -> None:
    source = _variant(tmp_path, "netless", EXTRA)
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    unexpressed = {row["kind"]: row["count"] for row in reply.result["unexpressed"]}
    assert not {"copper-without-net", "degenerate-arc", "arc-as-track"} & unexpressed.keys()
    (said,) = [i for i in reply.envelope["issues"] if i["code"] == "import.arc-as-track"]
    assert said["severity"] == "info" and said["message"].startswith("1 arc(s)")
    assert reply.result["equivalence"]["equivalent"]
    text = (tmp_path / "out" / "copper.py").read_text(encoding="utf-8")
    assert 'design.track_table(\n        "_/F.Cu/1",\n        layer=' in text
    assert build(tmp_path / "out").exit_code == 0
    built = built_board(tmp_path / "out", "netless").design
    original = read_board(source).design
    y = 140_000_000
    assert _where(built, "track", y) == _where(original, "track", y)
    assert _where(built, "track", y)[0][3] is None
    y = 145_000_000
    assert _where(built, "arc", y) == _where(original, "arc", y)
    assert _where(built, "arc", y)[0][3] is None
    # the arc whose three points lie on one line is the track it draws
    y = 150_000_000
    assert _where(original, "arc", y) and not _where(built, "arc", y)
    assert [row[:2] for row in _where(built, "track", y)] == [row[:2] for row in _where(original, "arc", y)]


def test_a_via_table_still_names_its_net() -> None:
    design = Design("t")
    with pytest.raises(DslError, match="net must be a Net"):
        design.via_table("v", net=None, diameter=mm(0.6), drill=mm(0.3), rows_nm=((0, 0),))  # type: ignore[arg-type]
    design.track_table("t", layer="F.Cu", width=mm(0.2), rows_nm=((0, 0, 1000, 0),))
    design.arc_table("a", layer="F.Cu", width=mm(0.2), rows_nm=((0, 0, 500, 500, 1000, 0),), net=Net("N"))


def test_repeated_and_padded_zone_names_are_kept(tmp_path: Path) -> None:
    zones = "".join(
        ZONE.format(n=n, name=name, x=100 + 5 * n, x2=103 + 5 * n)
        for n, name in enumerate(("Plane", "Plane", " Pour "))
    )
    source = _variant(tmp_path, "named", zones)
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert "zone-name" not in {row["kind"] for row in reply.result["unexpressed"]}
    assert build(tmp_path / "out").exit_code == 0
    names = sorted(zone.name for zone in built_board(tmp_path / "out", "named").design.board.zones)
    assert names == sorted(zone.name for zone in read_board(source).design.board.zones)
    assert names.count("Plane") == 2 and " Pour " in names


def test_a_zone_name_without_a_key_stays_unique_and_trimmed() -> None:
    design = Design("t")
    design.board(width=mm(20), height=mm(20))
    design.zone(None, layers=("F.Cu",), name="Plane")
    with pytest.raises(DslError, match="already used"):
        design.zone(None, layers=("F.Cu",), name="Plane")
    with pytest.raises(DslError, match="surrounding spaces"):
        design.zone(None, layers=("F.Cu",), name=" Pour ")
    design.zone(None, layers=("F.Cu",), name="Plane", key="zone/2")
    design.zone(None, layers=("F.Cu",), name=" Pour ", key="zone/3")
    with pytest.raises(DslError, match="not a space"):
        design.zone(None, layers=("F.Cu",), name="  ", key="zone/4")
