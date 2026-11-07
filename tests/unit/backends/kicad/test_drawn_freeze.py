# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Freezing a generated schematic into a drawn one (capability drawn-schematic, "Freezing a generated
schematic"; change c0276)."""

from __future__ import annotations

import re

import pytest
from _buildhelp import blink, build
from _schbuild import nested_design

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad import sch
from fenolite.dsl import Design

UUID = re.compile(r'"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"')


def _texts(files: dict[str, bytes] | object) -> dict[str, str]:
    assert isinstance(files, dict)
    return {p: d.decode("utf-8") for p, d in files.items() if p.endswith(".kicad_sch")}  # type: ignore[union-attr]


@pytest.mark.parametrize("make", [blink, nested_design], ids=["blink", "nested"])
@pytest.mark.parametrize("target", [9, 10])
def test_frozen_blink(make: type[Design], target: int) -> None:
    """Scenario "Frozen blink": the frozen drawing gives the generated sheets again.

    Decided 2026-10-29 (design.md, decision 12): drawn items take ids from their sheet and index, so labels,
    wires, flags and no-connect flags get new uuids at the freeze; every other byte is equal, and so are the
    board and the frozen value after another round."""
    output = build(make(), target)
    texts = _texts(dict(output.files))
    root_file = next(p for p in texts if "/" not in p)
    root = sch.read_schematic(texts[root_file], file=root_file)
    children = {p: sch.read_schematic(t, file=p) for p, t in texts.items() if p != root_file}
    components = kdrawn.refs_to_paths(output.design.circuit)
    frozen, issues = kdrawn.extract(root, children, components=components, root_file=root_file)
    assert issues == ()
    again = build(make(), target, drawn=frozen)
    assert not [i for i in again.issues if i.severity == "error"]
    redrawn = _texts(dict(again.files))
    assert sorted(redrawn) == sorted(texts)
    for path, text in texts.items():
        assert UUID.sub('"u"', redrawn[path]) == UUID.sub('"u"', text), path
    board = next(p for p in output.files if p.endswith(".kicad_pcb"))
    assert again.files[board] == output.files[board]
    root2 = sch.read_schematic(redrawn[root_file], file=root_file)
    children2 = {p: sch.read_schematic(t, file=p) for p, t in redrawn.items() if p != root_file}
    assert kdrawn.extract(root2, children2, components=components, root_file=root_file)[0] == frozen
