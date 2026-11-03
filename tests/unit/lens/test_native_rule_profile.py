# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored bounded selector forms and independent original/output guards (c0359)."""

import pytest
from _importcode import BOARD, ROOT

from fenolite.backends.kicad.native_rule_profile import validate_profile
from fenolite.backends.kicad.sexpr import Atom, dumps, parse
from fenolite.cli.cmd_import import _native_rule_context as compare_context
from fenolite.core.errors import FormatError
from fenolite.core.units import parse_length


def rule(condition: str, *, layer: str = "outer") -> str:
    return (
        '(version 1)\n(rule "Fenolite authored profile control" (layer '
        + dumps(Atom.string(layer))
        + ") (condition "
        + dumps(Atom.string(condition))
        + ") (constraint clearance (min 0.2mm)))\n"
    )


@pytest.mark.parametrize(
    "condition",
    [
        "A.Type == 'Track'",
        "A.Type == 'pad' && B.Type == A.Type",
        "A.Net == B.Net",
        "A.Net != B.Net",
        "!A.isPlated()",
        "A.isPlated() && B.isPlated()",
        "A.Fabrication_Property == 'Castellated pad'",
        "B.Layer == '?.Silkscreen'",
        "A.Type == 'Text' || A.Type == 'Text Box'",
        "(A.Type == 'track' && !B.isPlated()) || A.Net == B.Net",
    ],
)
def test_only_generic_documented_measured_predicates(condition: str):
    assert validate_profile(rule(condition, layer="?.Silkscreen")) == 1


@pytest.mark.parametrize(
    "condition",
    [
        "A.Reference == 'R1'",
        "A.Value == '1k'",
        "A.Footprint == 'Mini:R'",
        "A.NetName == 'IN'",
        "A.NetClass == 'Power'",
        "A.Unknown()",
        "A.Type == 'Footprint'",
        "A.X > 1mm",
        "A.Fabrication_Property == 'Unknown mark'",
        "A.Layer == 'User.1'",
        "A.Net != 'literal'",
    ],
)
def test_unproved_predicates_are_refused(condition: str):
    with pytest.raises(FormatError, match="profile"):
        validate_profile(rule(condition))


def test_text_requires_its_proved_layer_scope():
    with pytest.raises(FormatError, match="profile"):
        validate_profile(rule("A.Type == 'Text'"))


def test_native_source_geometry_and_referred_attributes_are_independent():
    source = BOARD.read_text()
    rules = rule("A.Type == 'pad' && A.Net != B.Net")
    assert compare_context(source, source, rules) == 1
    root = parse(source)
    first = root.nodes("footprint")[0]
    at = first.find("at")
    assert at is not None
    values = at.atoms()
    changed_at = at.with_children((Atom.from_nm(parse_length(values[0].value + "mm") + 1), *at.children[1:]))
    fp = first.with_children(tuple(changed_at if c is at else c for c in first.children))
    changed = dumps(root.with_children(tuple(fp if c is first else c for c in root.children)))
    with pytest.raises(FormatError, match="physical context"):
        compare_context(source, changed, rules)  # Exactly1nm remains a refusal, never a tolerance.
    fp = next(f for f in root.nodes("footprint") if any(p.find("net") is not None for p in f.nodes("pad")))
    pad = next(p for p in fp.nodes("pad") if p.find("net") is not None)
    net = pad.find("net")
    assert net is not None
    renamed = net.with_children((*net.children[:-1], Atom.string("AUTHORED_CHANGED")))
    changed_pad = pad.with_children(tuple(renamed if c is net else c for c in pad.children))
    changed_fp = fp.with_children(tuple(changed_pad if c is pad else c for c in fp.children))
    changed = dumps(root.with_children(tuple(changed_fp if c is fp else c for c in root.children)))
    with pytest.raises(FormatError, match="attributes differ|physical context"):
        compare_context(source, changed, rules)


def test_agent_teaching_keeps_immutable_scope_and_no_semantic_promotion():
    page = (ROOT / "src/fenolite/agent/skill/references/equivalent-s.md").read_text()
    assert "native/project.rules-context.json" in page
    assert "immutable imported" in page
    assert "explicitly unjudged by level6" in page


def test_singleton_net_spelling_is_not_native_net_identity():
    import dataclasses

    from fenolite.backends.kicad.pcb import read_board, write_board
    from fenolite.core.ids import derived_id
    from fenolite.model.circuit import Net, PinRef

    design = read_board(BOARD.read_text())
    assert design.board is not None
    fp = design.board.footprints[0]
    pad = next(p for p in fp.pads if p.number)
    ident = derived_id("net", "authored", "isolated-control")
    member = PinRef(fp.component_id, pad.number)
    nets = tuple(
        dataclasses.replace(n, members=tuple(m for m in n.members if m != member))
        for n in design.circuit.nets
    )
    isolated = Net(id=ident, name="unconnected-(AUTHORED-Pad1)", members=(member,))
    changed_fp = dataclasses.replace(
        fp, pads=tuple(dataclasses.replace(p, net_id=ident) if p is pad else p for p in fp.pads)
    )
    original = dataclasses.replace(
        design,
        circuit=dataclasses.replace(design.circuit, nets=(*nets, isolated)),
        board=dataclasses.replace(
            design.board, footprints=tuple(changed_fp if f is fp else f for f in design.board.footprints)
        ),
    )
    renamed = dataclasses.replace(
        original,
        circuit=dataclasses.replace(
            original.circuit,
            nets=(*nets, dataclasses.replace(isolated, name="unconnected-(AUTHORED-1-Pad1)")),
        ),
    )
    assert (
        compare_context(
            write_board(original, target=10).text,
            write_board(renamed, target=10).text,
            rule("A.Net != B.Net"),
        )
        == 1
    )


def test_physical_net_membership_swaps_no_net_and_multiplicity_cannot_hide():
    import dataclasses

    from fenolite.backends.kicad.native_rule_profile import _attributes
    from fenolite.backends.kicad.pcb import read_board

    design = read_board(BOARD.read_text())
    assert design.board is not None
    fp = design.board.footprints[0]
    pad = next(p for p in fp.pads if p.net_id)
    other = next(n.id for n in design.circuit.nets if n.id != pad.net_id)
    for replacement in (dataclasses.replace(pad, net_id=other), dataclasses.replace(pad, net_id=None)):
        changed = dataclasses.replace(fp, pads=tuple(replacement if p is pad else p for p in fp.pads))
        model = dataclasses.replace(
            design,
            board=dataclasses.replace(
                design.board, footprints=tuple(changed if f is fp else f for f in design.board.footprints)
            ),
        )
        assert _attributes(model) != _attributes(design)
    duplicate = dataclasses.replace(fp, pads=(*fp.pads, pad))
    model = dataclasses.replace(
        design,
        board=dataclasses.replace(
            design.board, footprints=tuple(duplicate if f is fp else f for f in design.board.footprints)
        ),
    )
    assert _attributes(model) != _attributes(design)
    ambiguous = dataclasses.replace(fp, pads=(pad, dataclasses.replace(pad, net_id=other)))
    model = dataclasses.replace(
        design,
        board=dataclasses.replace(
            design.board, footprints=(ambiguous,), tracks=(), arcs=(), vias=(), zones=()
        ),
    )
    with pytest.raises(FormatError, match="partitions are ambiguous"):
        _attributes(model)


def test_physical_partition_merge_and_two_pad_swap_are_negative():
    import dataclasses

    from fenolite.backends.kicad.native_rule_profile import _attributes
    from fenolite.backends.kicad.pcb import read_board

    original = read_board(BOARD.read_text())
    board = original.board
    assert board is not None
    pads = [(fp, p) for fp in board.footprints for p in fp.pads if p.net_id]
    first = pads[0][1]
    second = next(p for _, p in pads if p.net_id != first.net_id)
    substitutions = {
        id(first): dataclasses.replace(first, net_id=second.net_id),
        id(second): dataclasses.replace(second, net_id=first.net_id),
    }
    swapped = dataclasses.replace(
        board,
        footprints=tuple(
            dataclasses.replace(fp, pads=tuple(substitutions.get(id(p), p) for p in fp.pads))
            for fp in board.footprints
        ),
    )
    assert _attributes(dataclasses.replace(original, board=swapped)) != _attributes(original)

    def merge(item):
        return dataclasses.replace(item, net_id=second.net_id) if item.net_id == first.net_id else item

    merged = dataclasses.replace(
        board,
        footprints=tuple(
            dataclasses.replace(fp, pads=tuple(merge(p) for p in fp.pads)) for fp in board.footprints
        ),
        tracks=tuple(merge(t) for t in board.tracks),
        arcs=tuple(merge(t) for t in board.arcs),
        vias=tuple(merge(t) for t in board.vias),
        zones=tuple(merge(t) for t in board.zones),
    )
    assert _attributes(dataclasses.replace(original, board=merged)) != _attributes(original)


@pytest.mark.parametrize("body", ["(min NaN)", "(min 0.2mm 0.3mm)", "(min 0.2mm) (min 0.3mm)"])
def test_malformed_native_numeric_limits_are_not_certified(body: str):
    source = '(version 1)\n(rule "Authored invalid limit" (constraint clearance ' + body + "))\n"
    with pytest.raises(FormatError):
        validate_profile(source)
