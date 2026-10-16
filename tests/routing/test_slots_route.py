# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots in Specctra design files (capability specctra-dsn, "Slots in design files"; hypothesis
H-G-DSN-SLOT; change c0170).

The board is the shared fixture ``tests/data/slots/design.py`` (c0167): the outline of its model, the lone
slot ``S1`` (12 × 2 mm turned 30°), the L of ``S2`` and ``S3`` and the rounded cut-out, with two resistors
of the mini library whose pads of the net ``A`` lie 3 mm on either side of ``S1``'s centre, across its
axis, so the straight connection crosses the slot. The design file's rings are ``board_outline``'s: the
board ring first, then each cut-out and slot, a group of overlapping ones merged (``lowered_outline``),
which needs the ``geo`` extra. The route test runs where the extra is missing too (the router job installs
none): the rings are then the board ring, the cut-out and each slot's stadium, the L as two overlapping
keep-outs, which bound the router the same way.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import runpy
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest
from _placed import Part, design_of
from _resources import FREEROUTING_ENV

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.specctra.dsn import DsnDefaults, write_dsn
from fenolite.backends.specctra.ses import read_session, to_copper
from fenolite.core.coords import Point
from fenolite.dsl import Design as Script
from fenolite.dsl import to_model
from fenolite.geometry import DEFAULT_TOL, Thick, thick_touch
from fenolite.geometry.errors import BackendUnavailable
from fenolite.geometry.rings import CurvedRing
from fenolite.model.board import Track
from fenolite.model.design import Design
from fenolite.model.outline import outline_items, slot_ring
from fenolite.routing.plugins.specctra.freerouting import UNROUTED_NET

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "data" / "slots" / "design.py"
DEFAULTS = DsnDefaults(width=200_000, clearance=200_000, via_diameter=600_000, via_drill=300_000)
MM = 1_000_000
ACROSS = 3 * MM
"""How far each pad of ``A`` lies from ``S1``'s centre, across its axis."""
PASSES = 20
TIMEOUT = 900
JAVA_MIN = 25
EVIDENCE = ROOT / "docs" / "evidence" / "routing" / "freerouting-2.4.1.json"
WRITE = "FENOLITE_ROUTING_EVIDENCE"


def _fixture() -> Design:
    script = runpy.run_path(str(FIXTURE))["design"]
    assert isinstance(script, Script)
    return to_model(script)


def bench() -> Design:
    """The fixture's outline with two resistors whose pads of ``A`` lie on either side of ``S1``."""
    fixture = _fixture()
    assert fixture.board is not None and fixture.board.outline is not None
    outline = fixture.board.outline
    (s1,) = [slot for slot in outline.slots if slot.name == "S1"]
    # the normal of the slot's axis, from a straight edge of its stadium (the axis's direction)
    points = slot_ring(s1).points
    straight = next(
        (a, b)
        for k, (a, b) in enumerate(zip(points, (*points[1:], points[0]), strict=True))
        if slot_ring(s1).mids[k] is None
    )
    dx, dy = straight[1].x - straight[0].x, straight[1].y - straight[0].y
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length
    mm = 1 / MM

    def at(sign: int) -> tuple[float, float]:
        return ((s1.center.x + sign * ACROSS * nx) * mm, (s1.center.y + sign * ACROSS * ny) * mm)

    (x1, y1), (x2, y2) = at(-1), at(1)
    # R1's pad 2 and R2's pad 1 sit 0.8 mm from the part's origin; the parts are turned so that those pads
    # face the slot, and the pads themselves land near the two points
    design = design_of(
        Part("R1", "Mini_R_0603", x1, y1, nets={"2": "A"}),
        Part("R2", "Mini_R_0603", x2, y2, nets={"1": "A"}),
    )
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, outline=outline))


def rings(design: Design) -> tuple[tuple[Point, ...], ...]:
    """``board_outline``'s rings, or without the ``geo`` extra each ring of ``outline_items`` polygonised
    (the L as two overlapping stadiums)."""
    try:
        return board_outline(design).rings
    except BackendUnavailable:
        pass
    assert design.board is not None and design.board.outline is not None
    return tuple(
        CurvedRing(item.points, item.mids).polygonize(DEFAULT_TOL)
        for item in outline_items(design.board.outline)
    )


def test_keepouts_of_the_fixture() -> None:
    """Scenario "Keep-outs of the fixture": three ``keepout`` polygons, one of them the merged L."""
    pytest.importorskip("pyclipper")
    design = bench()
    found = board_outline(design)
    assert found.source == "model" and len(found.rings) == 4
    text = write_dsn(
        design, pads=board_pads(design), outline=found.rings, selected=("A",), defaults=DEFAULTS
    ).text
    assert text.count("(keepout") == 3
    # the merged L is the largest keep-out: more vertices than either stadium alone
    assert design.board is not None and design.board.outline is not None
    lone = len(CurvedRing(*_stadium(design, "S1")).polygonize(DEFAULT_TOL))
    assert max(len(ring) for ring in found.rings[1:]) > lone


def _stadium(design: Design, name: str) -> tuple[tuple[Point, ...], tuple[Point | None, ...]]:
    assert design.board is not None and design.board.outline is not None
    (slot,) = [s for s in design.board.outline.slots if s.name == name]
    item = slot_ring(slot)
    return item.points, item.mids


def _java() -> str:
    java = os.environ.get("FENOLITE_JAVA") or shutil.which("java")
    if not java:
        pytest.fail("no Java runtime: set FENOLITE_JAVA or put java on PATH", pytrace=False)
    done = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=60, check=False)
    text = (done.stderr or done.stdout).strip().splitlines()
    line = next((row for row in text if "version" in row), "")
    major = int(line.split('"')[1].split(".")[0]) if '"' in line else 0
    if major < JAVA_MIN:
        pytest.fail(f"Freerouting 2.4.1 needs Java {JAVA_MIN}: {line!r}", pytrace=False)
    return java


def _record(value: str, detail: str) -> None:
    """Add the outcome ``route-slot`` to the results file when ``FENOLITE_ROUTING_EVIDENCE=1`` (as
    ``test_freerouting_planes.py`` records its own)."""
    if os.environ.get(WRITE) != "1":
        return
    data: dict[str, object] = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    outcomes = data.get("outcomes")
    merged: dict[str, object] = (
        dict(cast("dict[str, object]", outcomes)) if isinstance(outcomes, dict) else {}
    )
    jar = Path(os.environ[FREEROUTING_ENV])
    java = subprocess.run([_java(), "-version"], capture_output=True, text=True, timeout=60, check=False)
    version = next((row for row in java.stderr.splitlines() if "version" in row), "").strip()
    label = f"jar {hashlib.sha256(jar.read_bytes()).hexdigest()[:12]}, {version}"
    merged["route-slot"] = {"value": value, "detail": f"{detail}; {label}"}
    data["outcomes"] = dict(sorted(merged.items()))
    EVIDENCE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _route(design: Design, outline: Sequence[Sequence[Point]], folder: Path) -> tuple[tuple[Track, ...], str]:
    """Freerouting's tracks of ``A`` on the design file of ``design`` with the rings ``outline``, and its
    output."""
    folder.mkdir(parents=True, exist_ok=True)
    written = write_dsn(design, pads=board_pads(design), outline=outline, selected=("A",), defaults=DEFAULTS)
    (folder / "board.dsn").write_text(written.text, encoding="utf-8")
    command = [
        _java(), "-jar", os.environ[FREEROUTING_ENV], "-de", "board.dsn", "-do", "board.ses",
        "-mp", str(PASSES), "-mt", "1", "-da", "--gui.enabled=false",
    ]  # fmt: skip
    env = {**os.environ, "HOME": str(folder), "LANG": "C"}
    done = subprocess.run(
        command, cwd=folder, env=env, capture_output=True, text=True, timeout=TIMEOUT, check=False
    )
    output = done.stdout + done.stderr
    session = folder / "board.ses"
    assert session.is_file(), output[-2000:]
    tracks, _vias, issues = to_copper(
        read_session(session.read_text(encoding="utf-8"), file="board.ses"), written.names, selected=("A",)
    )
    assert not [i for i in issues if i.severity == "error"], issues
    return tracks, output


@pytest.mark.needs_freerouting
def test_routed_around_the_slot(tmp_path: Path) -> None:
    """Scenario "Routed around the slot" (``H-G-DSN-SLOT``, outcome ``route-slot``): Freerouting connects
    the two pads of ``A`` and no routed segment touches the ring of ``S1``. The control, the same board
    with its board ring alone, routes across ``S1``: the keep-outs are what the router avoids."""
    design = bench()
    s1 = Thick(CurvedRing(*_stadium(design, "S1")).polygonize(DEFAULT_TOL), 0, True)

    def touching(tracks: Sequence[Track]) -> list[Track]:
        return [t for t in tracks if thick_touch(Thick((t.start, t.end), t.width), s1)]

    found = rings(design)
    tracks, output = _route(design, found, tmp_path / "slots")
    control, _ = _route(design, found[:1], tmp_path / "control")
    open_nets = [m["name"] for m in UNROUTED_NET.finditer(output) if int(m["count"])]
    if not tracks or open_nets or not touching(control):
        outcome = "inconclusive"
    else:
        outcome = "present" if touching(tracks) else "absent"
    detail = (
        f"the shared slot fixture with R1-2 and R2-1 of net A 3 mm on either side of S1, {len(found) - 1} "
        f"keep-out(s): {len(tracks)} track(s), {len(touching(tracks))} touching S1, open nets {open_nets}; "
        f"control with the board ring alone: {len(control)} track(s), {len(touching(control))} touching S1"
    )
    _record(outcome, detail)
    assert outcome == "absent", detail
