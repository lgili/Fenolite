# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper tables in a build (capability design-dsl, "Copper tables in a build"; change c0275). No tool
runs."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fenolite.api import run
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.pcb import read_board

SCRIPT = """\
from fenolite.dsl import Design, Net, mm

design = Design("tables")
design.board(mm(50), mm(30))
gnd = Net("GND")
design.track_table(
    "GND/F.Cu/1",
    net=gnd,
    layer="F.Cu",
    width=mm("0.25"),
    rows_nm=(
        (10_000_000, 10_000_000, 15_000_000, 10_000_000),
        (15_000_000, 10_000_000, 15_000_000, 15_000_000),
        (15_000_000, 15_000_000, 19_000_000, 15_000_000),
    ),
)
design.via_table(
    "GND/via/1",
    net=gnd,
    diameter=mm("0.6"),
    drill=mm("0.3"),
    rows_nm=((10_000_000, 10_000_000), (19_000_000, 15_000_000)),
)
"""
STAMP = "2026-10-29T00:00:00Z"


def _digests(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p.suffix != ".bak"
    }


def test_rebuild_keeps_table_copper(tmp_path: Path) -> None:
    (tmp_path / "design.py").write_text(SCRIPT, encoding="utf-8")
    dry = run("build", "design.py", "--out", "out", "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert dry.exit_code == 0, dry.error
    assert dry.result["copper"]["tracks"] == 3
    assert dry.result["copper"]["vias"] == 2
    first = run("build", "design.py", "--out", "out", "--confirm", cwd=tmp_path, timestamp=STAMP)
    assert first.exit_code == 0, first.error
    before = _digests(tmp_path / "out")
    board = read_board((tmp_path / "out" / "tables.kicad_pcb").read_text(encoding="utf-8")).board
    assert board is not None
    tracks = sorted(board.tracks, key=lambda t: t.native_ids["kicad"])
    assert [t.native_ids["kicad"] for t in tracks] == sorted(
        copper_uuid("GND/F.Cu/1", f"seg[{i}]") for i in range(3)
    )
    first_track = next(
        t for t in board.tracks if t.native_ids["kicad"] == copper_uuid("GND/F.Cu/1", "seg[0]")
    )
    assert (first_track.start.x, first_track.start.y, first_track.end.x, first_track.end.y) == (
        110_000_000, 110_000_000, 115_000_000, 110_000_000,
    )  # fmt: skip
    assert first_track.width == 250_000 and first_track.layer == "F.Cu"
    assert {v.native_ids["kicad"] for v in board.vias} == {
        copper_uuid("GND/via/1", f"via[{i}]") for i in range(2)
    }
    again = run("build", "design.py", "--out", "out", "--confirm", cwd=tmp_path, timestamp=STAMP)
    assert again.exit_code == 0, again.error
    assert not [i for i in (again.envelope or {})["issues"] if i["code"].startswith("kicad.copper.")]
    assert _digests(tmp_path / "out") == before
