# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The PCB document Fenolite writes against ``kicad-cli pcb import`` (capability altium-pcb-writer, "PCB
document oracle"; change c0035; hypotheses ``H-A-PCB-KICAD-DOC`` and ``H-A-PCB-DOC-BOTTOM``).

The blink build's ``blink.PcbDoc`` is imported with ``kicad-cli pcb import --format altium`` and read back
with ``backends.kicad.pcb.read_board``. KiCad reports a missing storage only on its standard output, not in
the JSON report, so both are read. KiCad moves the board to the middle of its sheet: positions are compared
relative to the first component. ``pcb import`` exists from 10.0 only (S-0166).

A pass checks only what KiCad's importer reads; it settles no Altium-only fact.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from _altium import blink, blink_resolver
from _kicad import oracle_env
from _resources import kicad_cli, kicad_cli_major

from fenolite.backends.kicad.pcb import read_board
from fenolite.dsl import placements, to_model
from fenolite.geometry.transform import Transform
from fenolite.lens.altium import build_altium
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad

TOLERANCE = 10
ALLOWED_WARNING = re.compile(r"Layer 'Internal Plane \d+' could not be mapped and will be skipped\.")
"""The only warnings ``pcb-document.md`` lists: the sixteen internal planes KiCad does not map."""


@dataclass(frozen=True)
class Imported:
    code: int
    stdout: str
    report: dict[str, object]
    board: Design | None
    text: str


@cache
def blink_build() -> tuple[bytes, Design, dict[str, object]]:
    design = blink()
    with tempfile.TemporaryDirectory() as folder:
        output = build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            placements=placements(design),
            resolver=blink_resolver(Path(folder)),
        )
        resolver = blink_resolver(Path(folder))
        footprints = {
            c.ref: resolver.footprint(c.lib_footprint_ref)
            for c in output.design.circuit.components
            if c.lib_footprint_ref
        }
    return output.files["blink.PcbDoc"], output.design, {**dict(placements(design)), "_fp": footprints}


@cache
def imported() -> Imported:
    cli = kicad_cli()
    assert cli is not None
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    data, _model, _extra = blink_build()
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source, target, report = root / "blink.PcbDoc", root / "b.kicad_pcb", root / "r.json"
        source.write_bytes(data)
        env = oracle_env(root / "config")
        proc = subprocess.run(
            [cli, "pcb", "import", "--format", "altium", "--report-format", "json",
             "--report-file", str(report), "-o", str(target), str(source)],
            capture_output=True, text=True, timeout=300, env=env, check=False,
        )  # fmt: skip
        found = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        board = read_board(target) if target.is_file() else None
        text = target.read_text(encoding="utf-8") if target.is_file() else ""
        return Imported(proc.returncode, proc.stdout + proc.stderr, found, board, text)


def test_import_succeeds_without_errors() -> None:
    """Scenario "Import of the sample": exit 0, no error in the report or on stdout, three footprints."""
    result = imported()
    assert result.code == 0, result.stdout
    assert result.report.get("errors") == []
    statistics = result.report.get("statistics")
    assert isinstance(statistics, dict) and statistics.get("footprints") == 3
    assert not [
        line for line in result.stdout.splitlines() if line.startswith("Error:") or "Error during" in line
    ]
    warnings = [line for line in result.stdout.splitlines() if "Warning:" in line]
    assert all(ALLOWED_WARNING.search(line) for line in warnings), warnings
    assert result.report.get("warnings") in ([], None)


def _absolute(model: Design, extra: dict[str, object]) -> dict[tuple[str, str], tuple[int, int]]:
    from fenolite.backends.altium.project import component_path

    footprints = extra["_fp"]
    assert isinstance(footprints, dict)
    out: dict[tuple[str, str], tuple[int, int]] = {}
    for component in model.circuit.components:
        place = extra[component_path(component)]
        transform = Transform.placement(place.at, place.rotation, mirror=place.side == "bottom")  # type: ignore[attr-defined]
        for pad in footprints[component.ref].pads:
            point = transform.apply(pad.position)
            out[(component.ref, pad.number)] = (point.x, point.y)
    return out


def test_references_nets_and_positions() -> None:
    result = imported()
    assert result.board is not None and result.board.board is not None
    _data, model, extra = blink_build()
    board = result.board
    refs = {c.id: c.ref for c in board.circuit.components}
    nets = {n.id: n.name for n in board.circuit.nets}
    assert sorted(refs.values()) == ["D1", "R1", "U1"]
    expected_nets: dict[tuple[str, str], str] = {}
    for net in model.circuit.nets:
        by_id = {c.id: c.ref for c in model.circuit.components}
        for member in net.members:
            expected_nets[(by_id[member.component_id], member.pin)] = net.name
    got: dict[tuple[str, str], tuple[int, int]] = {}
    sides: dict[str, str] = {}
    assert board.board is not None
    for footprint in board.board.footprints:
        ref = refs[footprint.component_id]
        sides[ref] = footprint.side
        transform = Transform.placement(footprint.position, footprint.rotation)
        for pad in footprint.pads:
            point = transform.apply(pad.position)
            got[(ref, pad.number)] = (point.x, point.y)
            assert nets.get(pad.net_id or "") == expected_nets.get((ref, pad.number)), (ref, pad.number)
    assert sides == {"D1": "bottom", "R1": "top", "U1": "top"}
    expected = _absolute(model, extra)
    assert set(got) == set(expected)
    ox, oy = got[("U1", "1")]
    ex, ey = expected[("U1", "1")]
    for key, (x, y) in got.items():
        dx, dy = expected[key][0] - ex, expected[key][1] - ey
        assert abs((x - ox) - dx) <= TOLERANCE and abs((y - oy) - dy) <= TOLERANCE, key


def test_outline_and_copper_layers() -> None:
    result = imported()
    assert result.board is not None and result.board.board is not None
    edges = [g for g in result.board.board.graphics if g.layer == "Edge.Cuts"]
    assert len(edges) == 4 and all(g.kind == "line" for g in edges)
    xs = sorted({p.x for g in edges for p in g.points})
    ys = sorted({p.y for g in edges for p in g.points})
    assert len(xs) == len(ys) == 2
    assert abs((xs[1] - xs[0]) - 50_000_000) <= TOLERANCE and abs((ys[1] - ys[0]) - 30_000_000) <= TOLERANCE
    assert (
        '(0 "F.Cu" signal "Top Layer")' in result.text and '(2 "B.Cu" signal "Bottom Layer")' in result.text
    )
