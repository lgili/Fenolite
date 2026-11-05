# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sheet-path nets of a drawn build keep KiCad's spelling (capability kicad-file-backend, "Net names in
KiCad's stored form"; change c0408). The KiCad parity proof is
``tests/kicad/schematic/test_drawn_sheet_net_names.py``."""

from __future__ import annotations

import dataclasses
import re

import _drawn
from _buildhelp import BLINK, build
from _schbuild import design_of

from fenolite.backends.kicad.pcb import STORED_KEY
from fenolite.dsl import Design, to_model
from fenolite.lens.build import BuildOutput, sheet_spellings
from fenolite.lens.drawn import read_drawn
from fenolite.model.base import ExtBag


def _renamed() -> Design:
    """Fixture ``hier`` whose child-sheet nets carry their sheet-path names."""
    code = _drawn.design("hier")
    for old, new in (("IN", "/child/IN"), ("FB", "/child/FB")):
        net = code.nets.pop(old)
        net.name = new
        code.nets[new] = net
    return code


def _built() -> BuildOutput:
    return build(_renamed(), 10, project_dir=_drawn.folder("hier"), drawn=_drawn.drawn("hier"),
                 drawn_file="schematic.toml", schematic_layout="wired")  # fmt: skip


def _board_nets(output: BuildOutput, board: str = "drawn_hier.kicad_pcb") -> set[str]:
    text = output.files[board].decode("utf-8")
    return set(re.findall(r'\(net(?: \d+)? "([^"]*)"\)', text))


def test_sheet_path_nets_are_written_with_raw_slashes() -> None:
    output = _built()
    assert output.files, output.issues
    nets = _board_nets(output)
    assert {"/child/IN", "/child/FB", "VCC", "GND"} <= nets
    assert not any("{slash}" in name for name in nets)


def test_only_label_named_nets_of_one_split_are_respelled() -> None:
    drawn, netlist, _ = _drawn.resolved(_built())
    circuit = to_model(_renamed()).circuit
    by_name = {net.name: net for net in circuit.nets}
    found = sheet_spellings(drawn, netlist, circuit)
    # the global VCC and the power GND keep stored_name
    assert found == {by_name["/child/IN"].id: "/child/IN", by_name["/child/FB"].id: "/child/FB"}
    kept = dataclasses.replace(by_name["/child/FB"], ext={"kicad": ExtBag(None, ((STORED_KEY, "x"),))})
    circuit = dataclasses.replace(circuit, nets=tuple(kept if n.id == kept.id else n for n in circuit.nets))
    assert set(sheet_spellings(drawn, netlist, circuit)) == {by_name["/child/IN"].id}
    # the fixture's own code names IN and FB are not the drawn names, so nothing is respelled
    plain = _drawn.circuit("hier")
    assert sheet_spellings(drawn, netlist, plain) == {}


def test_a_global_label_starting_with_a_slash_keeps_the_label_spelling() -> None:
    """A leading ``/`` is a sheet path only for a net that labels of a sheet name: the global label ``/X``
    is stored ``{slash}X`` (``H-K-SCH-SLASH``), in a drawn build and in a wired generated one."""
    code = _drawn.design("hier")
    net = code.nets.pop("VCC")
    net.name = "/X"
    code.nets[net.name] = net
    text = _drawn.text("hier")
    assert text.count('text = "VCC"') == 2
    drawing = read_drawn(text.replace('text = "VCC"', 'text = "/X"'), file="schematic.toml")
    drawn_build = build(code, 10, project_dir=_drawn.folder("hier"), drawn=drawing,
                        drawn_file="schematic.toml", schematic_layout="wired")  # fmt: skip
    assert drawn_build.files, drawn_build.issues
    assert "{slash}X" in _board_nets(drawn_build) and "/X" not in _board_nets(drawn_build)
    source = BLINK.read_text(encoding="utf-8")
    assert 'Net("LED_A")' in source
    wired = build(design_of(source.replace('Net("LED_A")', 'Net("/X")')), 10, schematic_layout="wired")
    assert wired.files, wired.issues
    nets = _board_nets(wired, "blink.kicad_pcb")
    assert "{slash}X" in nets and "/X" not in nets
