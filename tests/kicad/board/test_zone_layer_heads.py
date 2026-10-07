# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The two heads of a zone's layers against ``kicad-cli`` 10 (change c0145; capability kicad-file-backend,
"Singular and plural layer heads of a zone"; ``H-K-ZONE-LAYER-HEAD``).

What KiCad 10.0.6 loads, what it writes when it saves a board again, and that a zone or rule area whose
layers the model changed is written in the form KiCad itself writes.
"""

from __future__ import annotations

import _probes
import _zonelayers as zl
import pytest

from fenolite.backends.kicad.pcb import read_board, write_board

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


@pytest.mark.parametrize("name", ["singular-wildcard", "singular-mask", "singular-list"])
def test_kicad_rejects_several_layers_under_the_singular_head(name: str) -> None:
    """The record of 10.0.6: a board whose zone and rule area hold a wildcard, a mask or a list of names
    under ``layer`` does not load."""
    assert _probes.run(f"pcb-zone-layers-load-{name}") == "reject"


@pytest.mark.parametrize("name", ["plural-wildcard", "plural-mask", "plural-one"])
def test_kicad_loads_the_plural_head(name: str) -> None:
    assert _probes.run(f"pcb-zone-layers-load-{name}") == "load"


@pytest.mark.parametrize("name", sorted(zl.SAVES))
def test_kicad_saves_names_and_picks_the_head_by_their_number(name: str) -> None:
    """A wildcard or a mask is saved as the names it stands for under ``layers``, and one name under
    ``layers`` is saved under ``layer``: the forms of Fenolite's emitter."""
    child, expected = zl.SAVES[name]
    saved = zl.layer_children(zl.resaved(zl.variant(child)))
    assert saved[zl.ZONE_UUID] == [expected] and saved[zl.AREA_UUID] == [expected]
    assert _probes.run(f"pcb-zone-layers-save-{name}") == "equal"


@pytest.mark.parametrize(
    ("probe", "start", "layers", "written"),
    [
        ("widened", zl.SINGULAR_ONE, zl.BOTH, zl.PLURAL_LIST),
        ("narrowed", zl.PLURAL_LIST, ("F.Cu",), '(layer "F.Cu")'),
    ],
)
def test_changed_layers_are_written_in_the_form_kicad_keeps(
    probe: str, start: str, layers: tuple[str, ...], written: str
) -> None:
    """Scenario "A changed layer set is written by the number of layers": KiCad loads the written board
    and saves the same layer child again, for the zone and for the rule area."""
    text = zl.changed(start, layers)
    ours = zl.layer_children(text)
    assert ours[zl.ZONE_UUID] == [written] and ours[zl.AREA_UUID] == [written]
    assert _probes.load(text) == "load"
    theirs = zl.layer_children(zl.resaved(text))
    assert theirs[zl.ZONE_UUID] == [written] and theirs[zl.AREA_UUID] == [written]
    assert _probes.run(f"pcb-zone-layers-write-{probe}") == "equal"


def test_rewrite_of_a_plural_wildcard_board_loads() -> None:
    """A board with ``(layers "*.Cu")`` on its zone and rule area, read and written back unchanged, keeps
    both children and loads."""
    source = zl.variant(zl.PLURAL_WILDCARD)
    text = write_board(read_board(source), target=10).text
    kept = zl.layer_children(text)
    assert kept[zl.ZONE_UUID] == [zl.PLURAL_WILDCARD] and kept[zl.AREA_UUID] == [zl.PLURAL_WILDCARD]
    assert _probes.load(text) == "load"
