# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The layer head of a rule area that the script declares (capability kicad-file-backend, "Singular and
plural layer heads of a zone", change c0145): the emitter picks the head by the number of layers and
writes names, never a wildcard. A rule area that was read is another case: its child is kept as written
(``tests/unit/backends/kicad/test_pcb_zone_layer_heads.py``). No tool runs."""

from __future__ import annotations

import pytest
from _buildhelp import blink, build

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.dsl import mm

CORNERS = [(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(4)), (mm(40), mm(4))]


def area_layer_children(text: str) -> list[str]:
    (area,) = [n for n in parse(text).nodes("zone") if n.find("keepout") is not None]
    return [dumps(c, style="compact") for c in area.nodes() if c.name in ("layer", "layers")]


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize(
    ("layers", "written"),
    [
        (None, '(layers "F.Cu" "B.Cu")'),
        (("F.Cu", "B.Cu"), '(layers "F.Cu" "B.Cu")'),
        (("B.Cu",), '(layer "B.Cu")'),
    ],
)
def test_declared_rule_area_is_written_by_the_number_of_its_layers(
    target: int, layers: tuple[str, ...] | None, written: str
) -> None:
    """Scenario "A rule area declared in the script": every copper layer of a two-layer board is two
    names under ``layers``, one layer is one name under ``layer``; a rewrite of the built board keeps the
    child."""
    design = blink()
    design.rule_area("ANT", CORNERS, layers=layers, forbid=("tracks", "vias"))
    output = build(design, target)
    assert not [i for i in output.issues if i.severity == "error"], [i.code for i in output.issues]
    text = output.files["blink.kicad_pcb"].decode("utf-8")
    assert area_layer_children(text) == [written]
    assert area_layer_children(write_board(read_board(text), target=target).text) == [written]
