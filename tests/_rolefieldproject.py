# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored saved-reference search project; no third-party circuit data."""

from dataclasses import replace
from pathlib import Path

from _search_project import cli, project

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point


def role_project(folder: Path, layers: int = 2, *, state: str = "valid", major: int = 10):
    reference = "B.Cu" if layers == 2 else "In1.Cu"
    extra = f'''
gnd=Net("GND")
design.zone(gnd,layers=("{reference}",),outline=((mm(1),mm(1)),(mm(23),mm(1)),
            (mm(23),mm(19)),(mm(1),mm(19))),clearance=mm("0.2"),islands="never")
design.net_role(sig,"signal",sensitive=True)
design.net_role(fence,"switch_node")
design.net_role(gnd,"ground")
'''
    if state == "missing-limit":
        extra = extra.replace('design.net_role(fence,"switch_node")', 'design.net_role(fence,"high_voltage")')
    built = project(folder, layers, extra=extra)
    if major != 10:
        out = folder / "oracle"
        code, _, err = cli(
            "build",
            str(folder / "search_maze.py"),
            "--out",
            str(out),
            "--kicad-version",
            str(major),
            "--confirm",
        )
        assert code == 0, err
        built = replace(built, out=out, board=out / built.board.name)
        # The writer intentionally produces empty fills; author the saved-fill bench explicitly.
        from _roleboards import fill_as_outline

        built.board.write_text(fill_as_outline(built.board.read_text()))
    if state == "stale":
        design = read_board(built.board.read_text())
        zone = design.board.zones[0]
        fill = zone.fills[0]
        stale = replace(fill, polygon=(Point(-1_000_000, 1_000_000), *fill.polygon[1:]))
        changed = replace(design, board=replace(design.board, zones=(replace(zone, fills=(stale,)),)))
        built.board.write_text(write_board(changed, target=major).text)
    return built
