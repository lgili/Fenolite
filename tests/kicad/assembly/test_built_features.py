# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The features of change c0118 built from a script with the three calls (task 3.6; capability
kicad-oracle, "Assembly and test features pass the oracle", scenario "Built features on both majors").

The board is the blink with ``_asmfeatures.CALLS``: a global fiducial on each side (``FID1``, ``FID2``), a
test point on ``LED_A`` (``TP1``) and a tooling hole of 3 mm with a keep-out (``TH1``), built for the target
the running major loads best. The checks are those of the probes of task 1.3 on that board, and the two
probes the design adds: ``asm-tooling-drill`` (the not-plated drill file holds the hole's diameter at its
centre) and ``asm-features-pos`` (the position file lists the fiducials at their places, and no test point
or tooling hole). They are asserted here; every test of this file passed on 9.0.9 and on 10.0.6 in CI run
37803522539 (``kicad-9`` and ``kicad-10`` jobs). They are not registered as probes.
"""

from __future__ import annotations

import csv
import io
import re
import tempfile
from functools import cache
from pathlib import Path

import _featurebench as fb
import _lenscases as lc
import pytest
from _asmfeatures import calls_design
from _buildcases import _folder
from _outlinebench import drc, drill_hits, target
from _outlinehelp import build_script

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.dsl import BOARD_ORIGIN

pytestmark = pytest.mark.needs_kicad
BOARD = "blink.kicad_pcb"
MM = 1_000_000
PLACES = {"FID1": (3, 3), "FID2": (47, 27), "TP1": (30, 12), "TH1": (46, 4)}
"""Where ``CALLS`` puts each feature, in millimetres of the frame of ``place()``."""
SIDES = {"FID1": "top", "FID2": "bottom"}
DRILL_MM = 3.0
MASK_MM = 2


def _at(ref: str) -> Point:
    x, y = PLACES[ref]
    return Point(BOARD_ORIGIN.x + x * MM, BOARD_ORIGIN.y + y * MM)


@cache
def built_files() -> tuple[tuple[str, str | bytes], ...]:
    output = build_script(calls_design(), target())
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return tuple((k, v) for k, v in output.files.items() if not k.startswith(".fenolite/"))


def built_text() -> str:
    data = dict(built_files())[BOARD]
    return data.decode("utf-8") if isinstance(data, bytes) else data


def feature_uuids() -> dict[str, set[str]]:
    """Per feature reference: the KiCad uuids of its footprint and of its pads."""
    design = read_board(built_text())
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    found: dict[str, set[str]] = {}
    for fp in design.board.footprints:
        ref = refs.get(fp.component_id, "")
        if ref in PLACES:
            found[ref] = {v for e in (fp, *fp.pads) if (v := e.native_ids.get("kicad")) is not None}
    return found


def test_the_built_board_holds_the_features() -> None:
    """Not vacuous: the four features are on the board, each with its uuids."""
    found = feature_uuids()
    assert sorted(found) == sorted(PLACES) and all(found.values())


def test_built_features_drc() -> None:
    """``asm-fiducial-drc`` on the built board: no violation names a fiducial, the test point or the tooling
    hole (the open connections of the unrouted blink and the library checks aside)."""
    report = drc(dict(built_files()))
    assert report is not None
    wanted = set().union(*feature_uuids().values())
    named = [
        (v.type, v.description)
        for v in report.violations
        if v.type not in fb.LIBRARY_TYPES and any(item.uuid in wanted for item in v.items)
    ]
    assert named == []


def test_built_fiducial_mask() -> None:
    """``asm-fiducial-mask`` on the built board: the mask plot of each fiducial's side flashes a circle of
    its mask diameter at its centre."""
    runner = lc.runner()
    for ref, layer in (("FID1", "F.Mask"), ("FID2", "B.Mask")):
        found = fb.plot(runner, built_text(), layer)
        assert found is not None
        assert f"C,{MASK_MM}.000000" in {f[3] for f in fb.at(found, _at(ref))}, ref


def test_built_fiducial_d356() -> None:
    """``asm-fiducial-d356`` on the built board: each fiducial's copper pad is one ``327`` record on no net,
    covered on the other side only."""
    unit, records = fb.d356(lc.runner(), built_text())
    for ref, side in SIDES.items():
        found = fb.records_at(unit, records, _at(ref))
        other = "bottom" if side == "top" else "top"
        assert [(r.code, r.net, r.side, r.covered) for r in found] == [("327", "N/C", side, other)], ref


def _numbers(line: str) -> list[float]:
    return [float(value) for value in re.findall(r"[XY](-?\d+(?:\.\d+)?)", line)]


def test_tooling_drill() -> None:
    """``asm-tooling-drill``: the not-plated drill file holds one hit at the tooling hole's centre, with a
    tool of its diameter."""
    hits = drill_hits(dict(built_files()))
    assert hits is not None
    npth = next((lines for name, lines in hits.items() if "NPTH" in name), None)
    assert npth is not None
    x, y = (100 + PLACES["TH1"][0], 100 + PLACES["TH1"][1])
    here = [n for n in map(_numbers, npth) if abs(abs(n[0]) - x) < 0.002 and abs(abs(n[1]) - y) < 0.002]
    assert len(here) == 1
    with_tools = drill_tools(dict(built_files()))
    assert with_tools is not None and DRILL_MM in with_tools


def drill_tools(files: dict[str, str | bytes]) -> set[float] | None:
    """The tool diameters, in millimetres, declared in the not-plated drill file."""
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        args = ["pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm"]
        args += ["--excellon-separate-th", "--drill-origin", "absolute", "-o", "drill/", BOARD]
        run = lc.runner().run(args, files=tops, folders=["drill"])
    if not run.ok:
        return None
    tools: set[float] = set()
    for name, data in run.outputs.items():
        if "NPTH" in name and name.endswith(".drl"):
            text = data.decode("utf-8", "replace")
            tools |= {float(m) for m in re.findall(r"^T\d+C(\d+(?:\.\d+)?)", text, flags=re.MULTILINE)}
    return tools


def test_features_pos() -> None:
    """``asm-features-pos``: ``pcb export pos --format csv`` lists the two fiducials at their places, and
    neither the test point nor the tooling hole."""
    text = fb.pos(lc.runner(), built_text())
    rows = {row[0]: row for row in csv.reader(io.StringIO(text)) if row and row[0] != "Ref"}
    assert "TP1" not in rows and "TH1" not in rows
    for ref in SIDES:
        assert ref in rows, ref
        x, y = (100 + PLACES[ref][0], 100 + PLACES[ref][1])
        assert abs(abs(float(rows[ref][3])) - x) < 0.002 and abs(abs(float(rows[ref][4])) - y) < 0.002, ref
