# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``design.load_schematic()`` (capability design-dsl, "Drawn schematic in the DSL"; change c0276)."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DslError, Net, Part, connect, drawn_schematic, mm, to_model
from fenolite.model import canonical


def _design(load: bool) -> Design:
    design = Design("drawn_dsl")
    design.board(mm(20), mm(20))
    r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
    design.add(r1)
    connect(Net("A"), r1[1])
    if load:
        design.load_schematic("schematic.toml")
    return design


def test_recorded_path() -> None:
    """Scenario "Recorded path"."""
    loaded = _design(True)
    assert drawn_schematic(loaded) == "schematic.toml"
    assert drawn_schematic(_design(False)) is None
    assert canonical.dump_texts(to_model(loaded)) == canonical.dump_texts(to_model(_design(False)))


def test_second_call() -> None:
    """Scenario "Second call"."""
    design = _design(True)
    with pytest.raises(DslError, match="schematic.toml"):
        design.load_schematic("other.toml")


@pytest.mark.parametrize("path", ["../other/schematic.toml", "/abs/schematic.toml", "C:/x.toml", "a//b.toml"])
def test_path_outside_the_folder(path: str) -> None:
    """Scenario "Path outside the folder"."""
    with pytest.raises(DslError, match="inside the folder"):
        _design(False).load_schematic(path)


def test_only_toml_files() -> None:
    with pytest.raises(DslError, match="toml"):
        _design(False).load_schematic("schematic.kicad_sch")
    design = _design(False)
    design.load_schematic("drawings/main.toml")
    assert drawn_schematic(design) == "drawings/main.toml"
