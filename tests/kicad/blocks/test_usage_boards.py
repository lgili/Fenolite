# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every shipped block's usage circuit reads back on KiCad targets 9 and 10 (change c0270)."""

import shutil

import _erc
import pytest
from _probes import major, runner

from fenolite.cli.blocksrc import find_blocks
from fenolite.testing import load
from fenolite.testing.blocks import convention

pytestmark = pytest.mark.needs_kicad
SHIPPED = tuple(entry for entry in find_blocks() if entry.id.startswith("Fenolite:"))


@pytest.mark.parametrize("target", (9, 10))
@pytest.mark.parametrize("entry", SHIPPED, ids=lambda entry: entry.id)
def test_usage_board_readback(entry, target, tmp_path):
    if major() != target:
        pytest.skip(f"target {target} is judged by its own KiCad job")
    usage = convention(entry.definition).path("usage")
    assert usage is not None and usage.is_file(), entry.id
    copied = tmp_path / "usage"
    shutil.copytree(usage.parent, copied)
    with load(copied / usage.name, kicad_version=target) as design:
        files = {
            path.relative_to(design.path).as_posix(): path.read_bytes()
            for path in design.path.rglob("*")
            if path.is_file() and ".fenolite" not in path.parts
        }
        schematic = next(design.path.glob("*.kicad_sch")).name
        board = next(design.path.glob("*.kicad_pcb")).name
        nets = _erc.netlist(runner(), schematic, files)
        components = {part.id: part for part in design.model.circuit.components}
        expected = {
            frozenset(
                (components[pin.component_id].ref, pad)
                for pin in net.members
                for pad in components[pin.component_id].pads_of(pin.pin)
            )
            for net in design.model.circuit.nets
            if net.members
        }
        assert expected <= {frozenset(nodes) for nodes in nets.values()}, (entry.id, nets)
        assert _erc.parity(_erc.run_parity(runner(), board, files)) == []
