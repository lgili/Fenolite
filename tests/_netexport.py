# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored netlist exports for hermetic tests (change c0063): the text a fake ``kicad-cli`` writes for
``sch export netlist``, made from a ``KicadNetlist`` or from the pads of a board. Only the heads that
``netlist.read_netlist`` reads are written, with a made-up date and path in ``design``, so a test can
also check that neither reaches a result."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.kicad import netnames
from fenolite.backends.kicad.netlist import (
    KicadNetlist,
    NetComponent,
    NetlistNet,
    NetNode,
    build_netlist,
)
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Atom, dumps
from fenolite.model.circuit import Component
from fenolite.model.design import Design

DATE = "2026-01-01T00:00:00"
SOURCE = "/authored/project/sheet.kicad_sch"


def _q(text: str) -> str:
    return dumps(Atom.string(text)).strip()


def export_text(found: KicadNetlist) -> str:
    """``found`` as an export in the 9.0 shape, which both the reader and the 10.0 fake accept."""
    out = ['(export (version "E")', f"  (design (source {_q(SOURCE)}) (date {_q(DATE)}))", "  (components"]
    for comp in found.components:
        fields = "".join(
            f" (field (name {_q(name)}){' ' + _q(value) if value else ''})"
            for name, value in comp.properties.items()
        )
        out.append(
            f"    (comp (ref {_q(comp.ref)}) (value {_q(comp.value)}) (footprint {_q(comp.footprint)}) "
            f"(fields{fields}))"
        )
    out += ["  )", "  (nets"]
    for code, net in enumerate(found.nets, start=1):
        nodes = "".join(
            f" (node (ref {_q(n.ref)}) (pin {_q(n.pin)}) (pintype {_q(n.pintype or 'passive')}))"
            for n in net.nodes
        )
        out.append(
            f'    (net (code "{code}") (name {_q(net.name)}) (class {_q(net.netclass or "Default")}){nodes})'
        )
    out += ["  )", ")"]
    return "\n".join(out) + "\n"


def of_design(design: Design) -> KicadNetlist:
    """The netlist a schematic in agreement with the board of ``design`` has: one node per numbered pad,
    on the net of the pad, or on an ``unconnected-(…)`` net of its own for a pad on no net."""
    assert design.board is not None
    names = {n.id: n.name for n in design.circuit.nets}
    components: list[NetComponent] = []
    nets: dict[str, list[NetNode]] = {}
    for fp in design.board.footprints:
        component = design.by_id[fp.component_id]
        assert isinstance(component, Component)
        components.append(NetComponent(component.ref, component.value, component.lib_footprint_ref))
        for pad in fp.pads:
            if not pad.number:
                continue
            name = names.get(pad.net_id or "")
            if name is None:
                name = netnames.unconnected_name(
                    component.ref, unit=1, unit_count=1, pin_name="", pad_number=pad.number
                )
            nets.setdefault(netnames.stored_name(name), []).append(
                NetNode(component.ref, pad.number, "passive")
            )
    return build_netlist(components, (NetlistNet(name, "", tuple(nodes)) for name, nodes in nets.items()))


def for_board(board: Path) -> str:
    """The export text of a schematic that agrees with the board file at ``board``."""
    return export_text(of_design(read_board(board.read_text(encoding="utf-8"), file=board.name)))


__all__ = ["DATE", "SOURCE", "export_text", "for_board", "of_design"]
