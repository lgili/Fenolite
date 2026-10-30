# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zone arcs (capability design-dsl, "Zones in the DSL"; change c0277): ``zone(outline=…)`` takes ``arc_to``
steps, the model holds them in ``Zone.arcs``, the KiCad writer writes each as an ``arc`` of the outline's
``pts``, and the copper check polygonises them."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.dsl import Design, Net, arc_to, mm, to_model

STAMP = "2026-10-30T00:00:00Z"
LINE = (
    "from fenolite.dsl import arc_to\n"
    'design.zone(gnd, layers=("B.Cu",), name="ROUND", outline=((mm(2), mm(2)), (mm(10), mm(2)),'
    " arc_to((mm(12), mm(4)), (mm(10), mm(6))), (mm(2), mm(6))))\n"
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_zone_arcs_in_the_model() -> None:
    design = Design("z")
    design.board(mm(20), mm(20))
    outline = ((mm(2), mm(2)), (mm(10), mm(2)), arc_to((mm(12), mm(4)), (mm(10), mm(6))), (mm(2), mm(6)))
    design.zone(Net("GND"), layers=("F.Cu",), outline=outline)
    (zone,) = to_model(design).board.zones  # type: ignore[union-attr]
    assert len(zone.outline) == 4 and [(a.ring, a.edge) for a in zone.arcs] == [(0, 1)]
    assert zone.arcs[0].mid.x == 112_000_000


@pytest.mark.parametrize("target", [9, 10])
def test_zone_arcs_written(tmp_path: Path, target: int) -> None:
    script = blink_variant(tmp_path / "src", append=LINE)
    out = tmp_path / "out"
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    (zone,) = [z for z in parse((out / "blink.kicad_pcb").read_text(encoding="utf-8")).nodes("zone")]
    pts = zone.find("polygon").find("pts")  # type: ignore[union-attr]
    assert dumps(pts, style="compact") == (  # type: ignore[arg-type]
        "(pts (xy 102 102) (arc (start 110 102) (mid 112 104) (end 110 106)) (xy 102 106))"
    )
