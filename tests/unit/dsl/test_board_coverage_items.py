# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board items of change c0277 in the DSL and the KiCad writer: copper graphics with a net (capability
design-dsl, "Board drawings in the DSL", scenario "Copper text and a copper shape on a net"), filled shapes
without an outline, free vias, smoothed zones and dimensions in mils or automatic units."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.dsl import Design, DslError, Net, mm, to_model

STAMP = "2026-10-30T00:00:00Z"
LINES = (
    'design.rect("cu/pad", (mm(2), mm(25)), (mm(6), mm(27)), layer="F.Cu", width=mm("0.2"), fill=True,'
    " net=gnd)\n"
    'design.polygon("silk/art", [(mm(2), mm(2)), (mm(5), mm(2)), (mm(3), mm(4))], layer="F.SilkS",'
    " width=None, fill=True)\n"
    'design.via("fv", mm(10), mm(26), net=gnd, diameter=mm("0.8"), drill=mm("0.4"), free=True)\n'
    'design.via_table("ft", net=gnd, diameter=mm("0.6"), drill=mm("0.3"),'
    " rows_nm=((20_000_000, 26_000_000),), free=True)\n"
    'design.zone(gnd, layers=("B.Cu",), smoothing="fillet", smoothing_radius=mm("0.5"))\n'
    'design.dimension("auto", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-4), units="auto")\n'
    'design.dimension("mil", (mm(0), mm(0)), (mm(0), mm(30)), offset=mm(4), units="mils", precision=0)\n'
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _design() -> Design:
    design = Design("items")
    design.board(mm(30), mm(30))
    return design


def test_copper_graphics_in_the_model() -> None:
    design = _design()
    gnd = Net("GND")
    design.line("cu/l", (mm(1), mm(1)), (mm(5), mm(1)), layer="F.Cu", width=mm("0.3"), net=gnd)
    design.circle("cu/c", (mm(10), mm(10)), (mm(11), mm(10)), layer="B.Cu", width=mm("0.2"))
    design.polygon(
        "art", [(mm(1), mm(5)), (mm(4), mm(5)), (mm(2), mm(8))], layer="F.SilkS", width=None, fill=True
    )
    board = to_model(design).board
    assert board is not None
    found = {g.kind: g for g in board.graphics}
    assert found["line"].layer == "F.Cu" and found["line"].net_id is not None
    assert found["circle"].net_id is None and found["polygon"].width == -1
    assert "GND" in design.nets


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (
            lambda d: d.line("x", (mm(1), mm(1)), (mm(2), mm(1)), layer="F.SilkS", width=mm(1), net=Net("A")),
            "copper layer",
        ),
        (
            lambda d: d.line("x", (mm(1), mm(1)), (mm(2), mm(1)), layer="F.Cu", width=mm(1), net="A"),
            "must be a Net",
        ),
        (lambda d: d.line("x", (mm(1), mm(1)), (mm(2), mm(1)), layer="F.Cu", width=None), "no unit"),
        (
            lambda d: d.via("v", mm(1), mm(1), net=Net("A"), diameter=mm(1), drill=mm("0.5"), free="yes"),
            "free must be a bool",
        ),
        (lambda d: d.zone(Net("A"), layers=("F.Cu",), smoothing="round"), "smoothing must be"),
        (lambda d: d.zone(Net("A"), layers=("F.Cu",), smoothing_radius=mm(1)), "only with a smoothing"),
        (
            lambda d: d.dimension("d", (mm(0), mm(0)), (mm(5), mm(0)), offset=mm(1), units="cm"),
            "units must be one of",
        ),
    ],
)
def test_refusals(call, match: str) -> None:  # noqa: ANN001
    with pytest.raises(DslError, match=match):
        call(_design())


def _build(script: Path, out: Path, target: int, *extra: str) -> tuple[int, Node, list[str]]:
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm", *extra,
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    codes = [issue["code"] for issue in (reply.envelope or {}).get("issues", [])]
    if reply.exit_code != 0:
        return reply.exit_code, parse("(none)"), codes
    return 0, parse((out / "blink.kicad_pcb").read_text(encoding="utf-8")), codes


@pytest.mark.parametrize("target", [9, 10])
def test_items_written(tmp_path: Path, target: int) -> None:
    code, root, _ = _build(blink_variant(tmp_path / "src", append=LINES), tmp_path / "out", target)
    assert code == 0
    (rect,) = [n for n in root.nodes("gr_rect") if n.find("layer") == parse('(layer "F.Cu")')]
    net = rect.find("net")
    assert net is not None
    assert [c.name for c in rect.nodes()] == ["start", "end", "stroke", "fill", "layer", "net", "uuid"]
    if target == 10:
        assert net == parse('(net "GND")')
    else:
        assert net.atoms()[0].value.isdigit()
    (poly,) = [n for n in root.nodes("gr_poly") if n.find("layer") == parse('(layer "F.SilkS")')]
    assert dumps(poly.find("stroke"), style="compact") == "(stroke (width -0.000001) (type solid))"  # type: ignore[arg-type]
    free = [v for v in root.nodes("via") if v.find("free") is not None]
    assert len(free) == 2
    for via in free:
        heads = [c.name for c in via.nodes()]
        assert heads.index("free") == heads.index("layers") + 1 and heads.index("free") < heads.index("net")
    (zone,) = root.nodes("zone")
    fill = zone.find("fill")
    assert fill is not None and fill.find("smoothing") == parse("(smoothing fillet)")
    assert fill.find("radius") == parse("(radius 0.5)")
    units = sorted(d.find("format").find("units").atoms()[0].value for d in root.nodes("dimension"))  # type: ignore[union-attr]
    assert units == ["1", "3"]
    texts = sorted(d.find("gr_text").atoms()[0].value for d in root.nodes("dimension"))  # type: ignore[union-attr]
    assert texts == ["1181 mils", "50.0000 mm"]


def test_copper_guard_judges_a_copper_graphic(tmp_path: Path) -> None:
    """A copper rectangle of GND laid over a pad of LED_DRV is a short the guard refuses."""
    bad = (
        'design.rect("cu/bad", (mm(30), mm(7)), (mm(34), mm(11)), layer="F.Cu", width=mm("0.2"), fill=True,'
        " net=gnd)\n"
    )
    code, _, codes = _build(blink_variant(tmp_path / "src", append=bad), tmp_path / "out", 10)
    assert code == 5 and "copper.short" in codes
