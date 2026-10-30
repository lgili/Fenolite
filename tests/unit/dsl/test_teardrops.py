# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Teardrop settings of vias in the DSL (capability design-dsl, "Teardrop settings of vias in the DSL";
change c0277): ``teardrop()`` and ``teardrop=`` of ``Design.via`` and ``Design.via_table``."""

from __future__ import annotations

import pytest

import fenolite.dsl as dsl
from fenolite.dsl import Design, DslError, Net, ViaIntent, copper, mm, teardrop
from fenolite.model.board import Teardrop


def _design() -> tuple[Design, Net]:
    design = Design("tear")
    design.board(mm(50), mm(30))
    return design, Net("GND")


def test_values_of_teardrop() -> None:
    assert teardrop() == Teardrop()
    assert teardrop(max_length=mm(1), length_ratio=500_000, curved=True) == Teardrop(
        max_length=1_000_000, length_ratio=500_000, curved=True
    )
    assert teardrop(enabled=False) == Teardrop(enabled=False)
    full = teardrop(
        max_length=mm(1), max_width=mm(2), length_ratio=500_000, width_ratio=1_000_000, curved=False,
        filter_ratio=900_000, two_segments=True, prefer_zones=True,
    )  # fmt: skip
    assert (full.max_width, full.width_ratio, full.filter_ratio, full.two_segments) == (
        2_000_000,
        10**6,
        900_000,
        True,
    )
    assert "teardrop" in dsl.__all__


@pytest.mark.parametrize(
    ("arguments", "word"),
    [
        ({"length_ratio": 0.5}, "length_ratio"),
        ({"width_ratio": 1_000_001}, "width_ratio"),
        ({"filter_ratio": -1}, "filter_ratio"),
        ({"length_ratio": True}, "length_ratio"),
        ({"max_length": 1}, "max_length"),
        ({"max_width": mm(0)}, "max_width"),
        ({"curved": "yes"}, "curved"),
        ({"two_segments": 1}, "two_segments"),
        ({"enabled": None}, "enabled"),
    ],
)
def test_refused_values(arguments: dict[str, object], word: str) -> None:
    with pytest.raises(DslError, match=word):
        teardrop(**arguments)


def test_settings_on_a_via_and_a_table() -> None:
    design, gnd = _design()
    settings = teardrop(max_length=mm(1))
    design.via("v", mm(5), mm(5), net=gnd, teardrop=settings)
    design.via("plain", mm(9), mm(5), net=gnd)
    design.via_table(
        "t", net=gnd, diameter=mm(0.6), drill=mm(0.3), rows_nm=((1_000_000, 2_000_000),), teardrop=settings
    )
    intents = {intent.key: intent for intent in copper(design)}
    via = intents["v"]
    assert isinstance(via, ViaIntent) and via.teardrop == settings
    assert intents["plain"].teardrop is None  # type: ignore[union-attr]
    assert intents["t"].teardrop == settings  # type: ignore[union-attr]


def test_refused_teardrop_arguments() -> None:
    design, gnd = _design()
    with pytest.raises(DslError, match="via v: teardrop"):
        design.via("v", mm(1), mm(1), net=gnd, teardrop={"max_length": 1})
    with pytest.raises(DslError, match="via_table t: teardrop"):
        design.via_table("t", net=gnd, diameter=mm(0.6), drill=mm(0.3), rows_nm=((0, 0),), teardrop=True)


# --- Design.teardrops(where=...) (scenario "Teardrops on a class"; task 2.6b) ---------------------------


def _built(tmp_path, append: str, target: int = 10):  # noqa: ANN001, ANN202
    from _buildhelp import blink_variant

    from fenolite.api import run

    script = blink_variant(tmp_path / "src", append=append)
    out = tmp_path / "out"
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp="2026-10-30T00:00:00Z",
    )  # fmt: skip
    return reply, out / "blink.kicad_pcb"


@pytest.fixture
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_where_refuses_values() -> None:
    d, _ = _design()
    with pytest.raises(DslError, match="length_ratio"):
        d.teardrops(length_ratio=0.5)
    with pytest.raises(DslError, match="where"):
        d.teardrops(where="Default")
    with pytest.raises(DslError, match="pads and vias"):
        d.teardrops(pads=False, vias=False)
    d.teardrops(where=dsl.select.netclass("Default"), max_length=mm(1), length_ratio=500_000)
    (rule,) = d.teardrop_rules
    assert rule.settings == Teardrop(max_length=1_000_000, length_ratio=500_000)
    assert rule.pads and rule.vias


VIAS = (
    'design.via("tv", mm(5), mm(26), net=gnd, diameter=mm(0.6), drill=mm(0.3))\n'
    'design.via("sig", mm(40), mm(5), net=led_a, diameter=mm(0.6), drill=mm(0.3))\n'
)


def _net_names(root):  # noqa: ANN001, ANN202
    """A pad's or via's ``net`` child → the net name, for both net forms (numbered on 9, named on 10)."""
    numbers = {n.atoms()[0].text: n.atoms()[1].value for n in root.nodes("net") if len(n.atoms()) == 2}

    def name(item) -> str | None:  # noqa: ANN001
        held = item.find("net")
        if held is None:
            return None
        atoms = held.atoms()
        return (
            atoms[-1].value if len(atoms) == 2 or not atoms[0].text.isdigit() else numbers.get(atoms[0].text)
        )

    return name


@pytest.mark.parametrize("target", [9, 10])
def test_where_teardrops_on_a_class(tmp_path, isolated: None, target: int) -> None:  # noqa: ANN001
    """Scenario "Teardrops on a class": the pads and vias of the class get the settings, the others none."""
    from fenolite.backends.kicad.sexpr import dumps, parse

    lines = (
        "from fenolite.dsl import select\n"
        + VIAS
        + 'design.teardrops(where=select.netclass("PWR"), max_length=mm(1), length_ratio=500_000)\n'
    )
    reply, board = _built(tmp_path, lines, target)
    assert reply.exit_code == 0, reply.error
    root = parse(board.read_text(encoding="utf-8"))
    name = _net_names(root)
    expected = "(teardrops (best_length_ratio 0.5) (max_length 1) (enabled yes))"
    seen: dict[str, set[str | None]] = {}
    items = [*root.nodes("via"), *(pad for fp in root.nodes("footprint") for pad in fp.nodes("pad"))]
    for item in items:
        held = item.find("teardrops")
        seen.setdefault(str(name(item)), set()).add(
            dumps(held, style="compact") if held is not None else None
        )
    assert seen["GND"] == {expected} and seen["VIN"] == {expected}
    assert seen["LED_A"] == {None} and seen["LED_DRV"] == {None}


def test_where_later_call_wins(tmp_path, isolated: None) -> None:  # noqa: ANN001
    lines = (
        "from fenolite.dsl import select\n"
        "design.teardrops(max_length=mm(1))\n"
        'design.teardrops(where=select.net("GND"), max_length=mm(2))\n'
    )
    reply, board = _built(tmp_path, lines)
    assert reply.exit_code == 0, reply.error
    (found,) = [i for i in reply.envelope["issues"] if i["code"] == "build.teardrops-overlap"]  # type: ignore[index]
    assert found["severity"] == "info"
    assert "(max_length 2)" in board.read_text(encoding="utf-8")
