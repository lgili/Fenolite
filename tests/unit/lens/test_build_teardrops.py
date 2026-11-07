# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Teardrop settings of vias and blind vias over the board through ``fenolite build`` (capability
design-dsl, "Teardrop settings of vias in the DSL" and "Blind vias over the board in via tables"; change
c0277). Each test builds a blink variant in ``tmp_path``, in-process."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import Node, dumps, parse

STAMP = "2026-10-30T00:00:00Z"
LINES = (
    "from fenolite.dsl import teardrop\n"
    'design.via("tv", mm(5), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4),'
    " teardrop=teardrop(max_length=mm(1), length_ratio=500_000))\n"
    'design.via("plain", mm(12), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4))\n'
    'design.via_table("tt", net=gnd, diameter=mm(0.6), drill=mm(0.3), rows_nm=((20_000_000, 26_000_000),),'
    ' kind="blind", layers=("F.Cu", "B.Cu"), teardrop=teardrop(enabled=False))\n'
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _build(script: Path, out: Path, target: int) -> str:
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    return (out / "blink.kicad_pcb").read_text(encoding="utf-8")


def _vias(text: str) -> dict[tuple[str, ...], Node]:
    return {tuple(a.value for a in v.find("at").atoms()): v for v in parse(text).nodes("via")}  # type: ignore[union-attr]


def _heads(via: Node) -> list[str]:
    return [child.name for child in via.nodes()]


@pytest.mark.parametrize("target", [9, 10])
def test_settings_written_where_kicad_writes_them(tmp_path: Path, target: int) -> None:
    script = blink_variant(tmp_path / "src", append=LINES)
    vias = _vias(_build(script, tmp_path / "out", target))
    settings = vias["105", "126"].find("teardrops")
    assert settings is not None
    assert (
        dumps(settings, style="compact") == "(teardrops (best_length_ratio 0.5) (max_length 1) (enabled yes))"
    )
    assert _heads(vias["105", "126"]) == ["at", "size", "drill", "layers", "teardrops", "net", "uuid"]
    assert vias["112", "126"].find("teardrops") is None
    blind = vias["120", "126"]
    assert blind.atoms()[0].value == "blind" and blind.find("layers") == parse('(layers "F.Cu" "B.Cu")')
    assert dumps(blind.find("teardrops"), style="compact") == "(teardrops (enabled no))"  # type: ignore[arg-type]


def test_rebuild_keeps_bytes_and_new_settings_replace_the_child(tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", append=LINES)
    out = tmp_path / "out"
    first = _build(script, out, 10)
    assert _build(script, out, 10) == first
    script.write_text(
        script.read_text(encoding="utf-8").replace("length_ratio=500_000", "curved=True"), "utf-8"
    )
    vias = _vias(_build(script, out, 10))
    (settings,) = [child for child in vias["105", "126"].nodes() if child.name == "teardrops"]
    assert dumps(settings, style="compact") == "(teardrops (max_length 1) (curved_edges yes) (enabled yes))"


def test_a_single_blind_via_over_the_board_stays_refused(tmp_path: Path) -> None:
    line = 'design.via("b", mm(5), mm(26), net=gnd, kind="blind", layers=("F.Cu", "B.Cu"))\n'
    script = blink_variant(tmp_path / "src", append=line)
    reply = run("build", str(script), "--out", str(tmp_path / "out"), "--dry-run", cwd=script.parent)
    assert reply.exit_code == 5
    assert "kicad.copper.bad-layer" in [issue["code"] for issue in reply.envelope["issues"]]  # type: ignore[index]
