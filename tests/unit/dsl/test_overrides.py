# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint-instance overrides and pad edits (capability design-dsl, "Footprint-instance overrides in the
DSL"; change c0277): ``Part.override`` writes the footprint-level settings of one instance, ``Part.edit_pad``
changes the pads of one instance, and the vendored library footprint is unchanged."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.core.coords import Size
from fenolite.dsl import DslError, Part, mm
from fenolite.model.board import FootprintOverrides

STAMP = "2026-10-30T00:00:00Z"
LINES = """
from fenolite.dsl import Footprint
qfn = Footprint("Local", "QFN_EP", kind="smd")
qfn.pad("1", at=(mm(-2), mm(0)), size=(mm("0.3"), mm("0.8")))
qfn.pad("EP", at=(mm(0), mm(0)), size=(mm(3), mm(3)))
design.add_footprint(qfn)
u2 = Part("U2", "Mini:Mini_R", footprint=qfn.lib_id, value="X")
design.add(u2)
u2.place(mm(25), mm(22))
u2.override(clearance=mm("0.15"), paste_ratio=-100_000, zone_connection="solid")
u2.edit_pad("EP", size=(mm("3.2"), mm("3.2")))
"""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _build(script: Path, out: Path, *extra: str, target: int = 10):  # noqa: ANN202
    return run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), *extra,
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip


def test_override_and_edit_records() -> None:
    u1 = Part("U1", "Mini:Mini_QFP32_IC")
    u1.override(clearance=mm("0.15"))
    assert u1.overrides == FootprintOverrides(clearance=150_000)
    with pytest.raises(DslError, match="once"):
        u1.override(mask_margin=mm(0.1))
    for bad, word in (({"paste_ratio": 0.5}, "paste_ratio"), ({"zone_connection": "full"}, "zone_connection"),
                      ({}, "sets nothing")):  # fmt: skip
        with pytest.raises(DslError, match=word):
            Part("U9", "Mini:Mini_QFP32_IC").override(**bad)  # type: ignore[arg-type]
    u1.edit_pad("EP", size=(mm("3.2"), mm("3.2")))
    with pytest.raises(DslError, match="fields"):
        u1.edit_pad("1", colour="red")
    with pytest.raises(DslError, match="already"):
        u1.edit_pad("EP", rotation=90)


@pytest.mark.parametrize("target", [9, 10])
def test_override_and_an_edited_pad(tmp_path: Path, target: int) -> None:
    """Scenario "Override and an edited pad"."""
    script = blink_variant(tmp_path / "src", append=LINES)
    out = tmp_path / "out"
    reply = _build(script, out, "--confirm", target=target)
    assert reply.exit_code == 0, reply.error
    first = (out / "blink.kicad_pcb").read_bytes()
    root = parse(first.decode("utf-8"))

    def ref(fp) -> str:  # noqa: ANN001
        return next(p.atoms()[1].value for p in fp.nodes("property") if p.atoms()[0].value == "Reference")

    u2 = next(fp for fp in root.nodes("footprint") if ref(fp) == "U2")
    heads = [c.name for c in u2.nodes()]
    assert heads.index("solder_paste_margin_ratio") < heads.index("clearance") < heads.index("zone_connect")
    assert heads.index("zone_connect") < heads.index("attr")
    assert dumps(u2.find("clearance"), style="compact") == "(clearance 0.15)"  # type: ignore[arg-type]
    assert dumps(u2.find("solder_paste_margin_ratio"), style="compact") == "(solder_paste_margin_ratio -0.1)"  # type: ignore[arg-type]
    pad = next(p for p in u2.nodes("pad") if p.atoms()[0].value == "EP")
    assert dumps(pad.find("size"), style="compact") == "(size 3.2 3.2)"  # type: ignore[arg-type]
    back = read_board(out / "blink.kicad_pcb")
    assert back.board is not None
    refs = {c.id: c.ref for c in back.circuit.components}
    (instance,) = [fp for fp in back.board.footprints if refs[fp.component_id] == "U2"]
    assert next(p for p in instance.pads if p.number == "EP").size == Size(3_200_000, 3_200_000)
    vendored = next(out.rglob("QFN_EP.kicad_mod")).read_text(encoding="utf-8")
    assert "(size 3 3)" in vendored and "3.2" not in vendored
    assert _build(script, out, "--confirm", target=target).exit_code == 0
    assert (out / "blink.kicad_pcb").read_bytes() == first


def test_unknown_pad(tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", append=LINES + 'u2.edit_pad("NOPE", size=(mm(1), mm(1)))\n')
    reply = _build(script, tmp_path / "out", "--dry-run")
    assert reply.exit_code == 5
    (found,) = [i for i in reply.envelope["issues"] if i["code"] == "build.pad-unknown"]  # type: ignore[index]
    assert found["severity"] == "error" and "NOPE" in found["message"]
