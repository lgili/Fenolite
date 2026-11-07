# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Literal parity controls before relocating the existing native binding helpers (c0355)."""

import dataclasses

import pytest
from _importcode import BOARD

from fenolite.api import read_board
from fenolite.api._native_rules import bindings, raw_bindings
from fenolite.backends.kicad.sexpr import parse
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Net


def authored():
    source = read_board(BOARD).design
    component = dataclasses.replace(source.circuit.components[0], ref="U1")
    nets = tuple(Net(id=derived_id("net", "authored-binding", name), name=name) for name in ("A", "B"))
    footprint = dataclasses.replace(
        source.board.footprints[0],
        component_id=component.id,
        pads=tuple(
            dataclasses.replace(pad, number=str(i + 1), net_id=nets[i].id)
            for i, pad in enumerate(source.board.footprints[0].pads[:2])
        ),
    )
    assert len(footprint.pads) == 2
    return dataclasses.replace(
        source,
        circuit=dataclasses.replace(source.circuit, components=(component,), nets=nets),
        board=dataclasses.replace(source.board, footprints=(footprint,)),
    )


def test_existing_model_binding_exact_edge_semantics():
    design = authored()
    expected = {"A": ("U1-1",), "B": ("U1-2",)}
    assert bindings(design) == expected
    assert bindings(dataclasses.replace(design, board=None)) == {}
    fp = design.board.footprints[0]
    assert bindings(dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=()))) == {}
    assert (
        bindings(dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(fp, fp))))
        == expected
    )
    unnamed = dataclasses.replace(fp, pads=(dataclasses.replace(fp.pads[0], number=""), fp.pads[1]))
    assert bindings(
        dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(unnamed,)))
    ) == {"B": ("U1-2",)}
    no_net = dataclasses.replace(fp, pads=(dataclasses.replace(fp.pads[0], net_id=None), fp.pads[1]))
    assert bindings(
        dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(no_net,)))
    ) == {"B": ("U1-2",)}
    missing = dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=()))
    assert bindings(missing) == {"A": ("-1",), "B": ("-2",)}


@pytest.mark.parametrize("change", ["pad", "ref", "no-net", "name"])
def test_existing_model_binding_conflicts_still_refuse(change):
    design = authored()
    fp = design.board.footprints[0]
    if change == "name":
        design = dataclasses.replace(
            design,
            circuit=dataclasses.replace(
                design.circuit,
                nets=tuple(dataclasses.replace(net, name="COLLISION") for net in design.circuit.nets),
            ),
        )
    elif change == "ref":
        other = dataclasses.replace(
            fp,
            pads=tuple(
                dataclasses.replace(pad, net_id=design.circuit.nets[1 - i].id)
                for i, pad in enumerate(fp.pads)
            ),
        )
        design = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(fp, other)))
    else:
        duplicate = dataclasses.replace(
            fp.pads[0], net_id=None if change == "no-net" else design.circuit.nets[1].id
        )
        design = dataclasses.replace(
            design,
            board=dataclasses.replace(
                design.board, footprints=(dataclasses.replace(fp, pads=(*fp.pads, duplicate)),)
            ),
        )
    with pytest.raises(ValueError, match="ambiguous"):
        bindings(design)


def native(extra="", pads='(pad "1" smd rect (net 1 "A")) (pad "2" smd rect (net 2 "B"))'):
    return parse(
        '(kicad_pcb (net 0 "") (net 1 "A") (net 2 "B") '
        '(footprint "Authored" (property "Reference" "U1") ' + pads + ")" + extra + ")"
    )


def test_existing_raw_binding_literal_complete_partitions_and_copies():
    expected = frozenset({("U1-1",), ("U1-2",)})
    result = {"A": ("U1-1",), "B": ("U1-2",)}
    assert raw_bindings(native(), expected) == result
    extra = (
        '(footprint "Authored" (property "Reference" "U1") '
        '(pad "1" smd rect (net 1 "A")) (pad "2" smd rect (net 2 "B")))'
    )
    assert raw_bindings(native(extra), expected) == result
    ignored = '(footprint "Mechanical" (pad "" np_thru_hole circle) (pad "3" smd rect (net 0 "")))'
    assert raw_bindings(native(ignored), expected) == result
    with pytest.raises(ValueError, match="partitions changed"):
        raw_bindings(native(), frozenset({("U1-1", "U1-2")}))
    with pytest.raises(ValueError, match="ambiguous"):
        raw_bindings(native(pads='(pad "1" smd rect (net 1 "A")) (pad "1" smd rect (net 2 "B"))'), expected)
