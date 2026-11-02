# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement rule areas of KiCad's multichannel tool (change c0277): ``rule_area(..., placement="/CH1/")``
and area names with a slash, as KiCad names its automatic placement areas."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.dsl import Design, DslError, mm, to_model

STAMP = "2026-10-30T00:00:00Z"
AREA = [(mm(1), mm(1)), (mm(9), mm(1)), (mm(9), mm(9))]


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_placement_in_the_model() -> None:
    design = Design("p")
    design.board(mm(20), mm(20))
    design.rule_area("auto-placement-area-/CH1/", AREA, placement="/CH1/")
    (area,) = to_model(design).board.keepouts  # type: ignore[union-attr]
    assert (area.name, area.placement) == ("auto-placement-area-/CH1/", "/CH1/")
    with pytest.raises(DslError, match="placement"):
        design.rule_area("b", AREA, placement="")


@pytest.mark.parametrize("target", [9, 10])
def test_placement_written(tmp_path: Path, target: int) -> None:
    line = (
        'design.rule_area("auto-placement-area-/CH1/", [(mm(1), mm(1)), (mm(9), mm(1)), (mm(9), mm(9))],'
        ' placement="/CH1/")\n'
    )
    script = blink_variant(tmp_path / "src", append=line)
    out = tmp_path / "out"
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    (zone,) = [
        z
        for z in parse((out / "blink.kicad_pcb").read_text(encoding="utf-8")).nodes("zone")
        if z.find("keepout")
    ]
    heads = [c.name for c in zone.nodes()]
    assert heads.index("placement") == heads.index("keepout") + 1
    assert dumps(zone.find("placement"), style="compact") == '(placement (enabled yes) (sheetname "/CH1/"))'  # type: ignore[arg-type]
