# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parts not populated in the DSL (capability design-dsl, "Parts not populated in the DSL"; change
c0277): ``Part(..., dnp=True)``."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import parse
from fenolite.dsl import Design, DslError, Part, mm, to_model

STAMP = "2026-10-30T00:00:00Z"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_dnp_in_the_model() -> None:
    design = Design("fit")
    design.board(mm(20), mm(20))
    r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", dnp=True)
    r2 = design.part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", dnp=True)
    r3 = Part("R3", "Mini:Mini_R", footprint="Mini:Mini_R_0603")
    design.add(r1, r3)
    components = {c.ref: c for c in to_model(design).circuit.components}
    assert (components["R1"].dnp, components["R2"].dnp, components["R3"].dnp) == (True, True, False)
    assert r2.dnp and not r3.dnp
    with pytest.raises(DslError, match="dnp"):
        Part("R4", "Mini:Mini_R", dnp="yes")  # type: ignore[arg-type]


@pytest.mark.parametrize("target", [9, 10])
def test_dnp_written_to_board_and_sheet(tmp_path: Path, target: int) -> None:
    script = blink_variant(
        tmp_path / "src",
        'r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")',
        'r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330", dnp=True)',
    )
    out = tmp_path / "out"
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    board = parse((out / "blink.kicad_pcb").read_text(encoding="utf-8"))
    attrs = {}
    for node in board.nodes("footprint"):
        ref = next(p.atoms()[1].value for p in node.nodes("property") if p.atoms()[0].value == "Reference")
        attr = node.find("attr")
        attrs[ref] = [a.value for a in attr.atoms()] if attr is not None else []
    assert attrs["R1"][-1] == "dnp" and "dnp" not in attrs["D1"] and "dnp" not in attrs["U1"]
    sheet = (out / "blink.kicad_sch").read_text(encoding="utf-8")
    assert sheet.count("(dnp yes)") == 1
