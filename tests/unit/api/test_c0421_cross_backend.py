# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sides of a comparison across backends (change c0421; capability design-equivalence, "Cross-backend
side completion"): a KiCad side gets what its project and rules file hold, sides of one backend stay as
read, and the native rule check of two KiCad projects does not refuse a comparison with another backend.
Every input is authored for Fenolite (the two-layer board and the public-format test project and rules)."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import pytest

from fenolite.api import _cross_backend, _native_rules
from fenolite.api.sides import ReadSide, read_side
from fenolite.checks.equivalence import compare_designs
from fenolite.core.errors import FenoliteError

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
PROJECT = DATA / "kicad" / "project" / "tuning_10.kicad_pro"
RULES = DATA / "kicad" / "rules" / "selectors.kicad_dru"


def project(tmp_path: Path, *, rules: bool = True) -> Path:
    """A KiCad project of the two-layer board in ``tmp_path``: board, project file and, with ``rules``,
    a rules file, all named ``case``."""
    shutil.copyfile(TWO_LAYER, tmp_path / "case.kicad_pcb")
    shutil.copyfile(PROJECT, tmp_path / "case.kicad_pro")
    if rules:
        shutil.copyfile(RULES, tmp_path / "case.kicad_dru")
    return tmp_path / "case.kicad_pro"


def other_backend(side: ReadSide) -> ReadSide:
    """``side`` as if another backend had read it: no traced files, so no native context."""
    return dataclasses.replace(side, backend="altium", source_files=())


def test_a_kicad_side_gets_its_project_classes_and_rules_across_backends(tmp_path: Path) -> None:
    kicad = read_side(project(tmp_path))
    assert kicad.design.circuit.netclasses == () and kicad.design.rules is None
    done = _cross_backend.complete(other_backend(read_side(TWO_LAYER)), kicad)
    names = {cls.name for cls in done.b.design.circuit.netclasses}
    assert {"Default", "SE50", "USB90"} <= names
    assert done.b.design.rules is not None
    assert "sel_net" in {rule.name for rule in done.b.design.rules.rules}


def test_a_kicad_side_without_a_rules_file_keeps_its_rules(tmp_path: Path) -> None:
    done = _cross_backend.complete(
        other_backend(read_side(TWO_LAYER)), read_side(project(tmp_path, rules=False))
    )
    assert done.b.design.rules is None
    assert done.b.design.circuit.netclasses != ()


def test_sides_of_one_backend_stay_as_read(tmp_path: Path) -> None:
    kicad = read_side(project(tmp_path))
    done = _cross_backend.complete(read_side(TWO_LAYER), kicad)
    assert done.b is kicad and done.keepout_layers == (frozenset(), frozenset())


def changed(tmp_path: Path) -> ReadSide:
    """A KiCad side whose traced project changed after it was read: its native context refuses."""
    side = read_side(project(tmp_path))
    (tmp_path / "case.kicad_pro").write_text("{}", encoding="utf-8")
    return side


def test_native_rules_do_not_refuse_a_comparison_with_another_backend(tmp_path: Path) -> None:
    kicad = changed(tmp_path)
    report = compare_designs(kicad.design, kicad.design, level=6)
    assert _native_rules.augment(report, other_backend(kicad), kicad) is report
    assert _native_rules.augment(report, kicad, other_backend(kicad)) is report


def test_native_rules_still_refuse_two_kicad_sides(tmp_path: Path) -> None:
    kicad = changed(tmp_path)
    report = compare_designs(kicad.design, kicad.design, level=6)
    with pytest.raises(FenoliteError):
        _native_rules.augment(report, kicad, kicad)


def test_an_altium_zone_no_record_outlines_stays_as_read(tmp_path: Path) -> None:
    from fenolite.model.board import Zone

    side = other_backend(read_side(TWO_LAYER))
    assert side.design.board is not None
    empty = Zone(id="zon-arc", outline=(), name="pour", layers=("F.Cu",))
    board = dataclasses.replace(side.design.board, zones=(empty,))
    side = dataclasses.replace(side, design=dataclasses.replace(side.design, board=board))
    done = _cross_backend.complete(side, read_side(TWO_LAYER), paths=(tmp_path / "x.PcbDoc", TWO_LAYER))
    assert done.a.design.board is not None and done.a.design.board.zones == (empty,)


def test_the_keepout_layer_of_an_altium_side_is_named() -> None:
    from fenolite.backends.altium.adapter.copper import KEEPOUT_LAYER_ID
    from fenolite.backends.altium.adapter.layers import LAYERS
    from fenolite.model.board import Layer

    name = LAYERS[KEEPOUT_LAYER_ID][0]
    side = other_backend(read_side(TWO_LAYER))
    assert side.design.board is not None
    layers = (*side.design.board.layers, Layer(id="lay-keepout", name=name, kind="user", ordinal=99))
    board = dataclasses.replace(side.design.board, layers=layers)
    side = dataclasses.replace(side, design=dataclasses.replace(side.design, board=board))
    done = _cross_backend.complete(side, read_side(TWO_LAYER))
    assert done.keepout_layers == (frozenset({name}), frozenset())
    assert _cross_backend.complete(
        other_backend(read_side(TWO_LAYER)), read_side(TWO_LAYER)
    ).keepout_layers == (
        frozenset(),
        frozenset(),
    )
