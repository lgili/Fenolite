# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stack-up in a build and across rebuilds (capabilities design-dsl, "Stack-up in a build", and
layout-lens, "Stack-up across rebuilds"; change c0101)."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import stack_entry, stack_of
from _buildhelp import blink, build, codes, resolver
from _preserve_help import prepared, rebuild

from fenolite.backends.kicad import stackup
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, tree_equal
from fenolite.dsl import Design, placements, stack, stackup_locked, to_model
from fenolite.lens.build import BuildOutput, build_design

BOARD = "blink.kicad_pcb"
CORE_ROW = '(layer "dielectric 1" (type "core") (thickness 1.5) (material "FR4"))'


def stacked(*, locked: bool = False, core: str = "1.5mm") -> Design:
    """The stack-up blink: the blink with masks, 35 µm copper, a 1.5 mm FR4 core and ``ENIG``."""
    design = blink()
    design.stackup(
        stack.mask("10um"),
        stack.copper("35um"),
        stack.core(core, material="FR4"),
        stack.copper("35um"),
        stack.mask("10um"),
        finish="ENIG",
        locked=locked,
    )
    return design


def text_of(output: BuildOutput) -> str:
    assert not [i for i in output.issues if i.severity == "error"], codes(output)
    return output.files[BOARD].decode("utf-8")


def child(root: Node, head: str) -> Node:
    found = root.find(head)
    assert found is not None
    return found


def stack_codes(output: BuildOutput) -> list[str]:
    return [
        c for c in codes(output) if c.startswith(("kicad.stackup.", "kicad.board.stackup-", "model.stackup"))
    ]


def replaced(node: Node, old: Node, new: Node) -> Node:
    """``node`` with its descendant ``old`` (found by identity) replaced by ``new``."""
    children = [
        new if c is old else replaced(c, old, new) if isinstance(c, Node) else c for c in node.children
    ]
    return node.with_children(children)


def edited(text: str) -> str:
    """The built board with its core changed to 1.4 mm in KiCad, and the board thickness to match."""
    root = parse(text)
    assert dumps(root) == text
    node = child(child(root, "setup"), "stackup")
    (core,) = [r for r in node.nodes("layer") if dumps(r, style="compact") == CORE_ROW]
    root = replaced(root, child(core, "thickness"), parse("(thickness 1.4)"))
    root = replaced(root, child(child(root, "general"), "thickness"), parse("(thickness 1.49)"))
    return dumps(root)


@pytest.mark.parametrize("target", [9, 10])
def test_blink_with_a_stackup(target: int) -> None:
    design = stacked()
    first = build(design, target, lock_stackup=stackup_locked(design))
    text = text_of(first)
    board = read_board(text).board
    assert board is not None
    declared = to_model(design).board.stackup  # type: ignore[union-attr]
    assert declared is not None
    assert stackup.values(board.stackup) == stackup.values(stackup.complete(declared, board.layers))
    root = parse(text)
    assert (
        dumps(child(root, "general"), style="compact") == "(general (thickness 1.59) (legacy_teardrops no))"
    )
    assert child(root, "setup").nodes()[0].name == "stackup"
    assert first.summary["stackup"] == {"source": "script", "thickness": 1_590_000, "copper": 2}
    assert stack_codes(first) == []
    second = rebuild(stacked(), text, target)
    assert dict(second.files) == dict(first.files)
    assert second.summary["stackup"] == first.summary["stackup"] and stack_codes(second) == []


@pytest.mark.parametrize("target", [9, 10])
def test_script_without_a_stackup_builds_the_same_board_node(target: int) -> None:
    """A design without ``stackup()`` keeps ``(general (thickness 1.6) …)`` and a ``setup`` without a
    node; the bytes of every file are pinned by the golden and determinism tests of the build."""
    output = build(blink(), target)
    root = parse(text_of(output))
    assert dumps(child(root, "setup"), style="compact") == "(setup (pad_to_mask_clearance 0))"
    assert dumps(child(root, "general"), style="compact") == "(general (thickness 1.6) (legacy_teardrops no))"
    assert output.summary["stackup"] is None
    assert ".fenolite/board.json" in output.files
    assert b'"stackup"' not in output.files[".fenolite/board.json"]


def test_invalid_stackup_stops_the_build() -> None:
    """A model stack-up that names only ``F.Cu`` and ``B.Cu`` on a four-layer build: nothing is written."""
    source = blink()
    model = to_model(source)
    assert model.board is not None
    two = stack_of(
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("dielectric 1", "dielectric", 1_500_000),
        stack_entry("B.Cu", "copper", 35_000),
    )
    model = dataclasses.replace(model, board=dataclasses.replace(model.board, stackup=two))
    output = build_design(model, placements(source), name="blink", copper=4, resolver=resolver(10), target=10)
    assert dict(output.files) == {} and "model.stackup-copper" in codes(output)
    assert output.summary["stackup"] is None
    assert len(created_layers(4)) > len(created_layers(2))


def test_an_edit_in_kicad_wins() -> None:
    text = edited(text_of(build(stacked(), 10)))
    output = rebuild(stacked(), text, 10)
    written, source = parse(text_of(output)), parse(text)
    assert tree_equal(child(written, "setup"), child(source, "setup"))
    assert tree_equal(child(written, "general"), child(source, "general"))
    (issue,) = [i for i in output.issues if i.code.startswith("kicad.stackup.")]
    assert issue.code == "kicad.stackup.overridden" and "dielectric 1" in issue.message
    assert output.summary["stackup"] == {"source": "board", "thickness": 1_490_000, "copper": 2}


def test_a_locked_stackup_wins() -> None:
    text = edited(text_of(build(stacked(), 10)))
    unlocked = rebuild(stacked(locked=True), text, 10)  # without the lock argument the board wins
    locked_first = _locked_rebuild(text)
    written = parse(text_of(locked_first))
    assert CORE_ROW in dumps(child(written, "setup"), style="compact")
    assert "(thickness 1.59)" in dumps(child(written, "general"), style="compact")
    assert stack_codes(locked_first) == ["kicad.stackup.forced"]
    assert locked_first.summary["stackup"] == {"source": "script", "thickness": 1_590_000, "copper": 2}
    again = _locked_rebuild(text_of(locked_first))
    assert dict(again.files) == dict(locked_first.files) and stack_codes(again) == []
    assert stack_codes(unlocked) == ["kicad.stackup.overridden"]


def _locked_rebuild(text: str) -> BuildOutput:
    design = stacked(locked=True)
    ready = prepared(design, text)
    return build(
        design, 10, prepared=ready, placements_override=ready.placements, lock_stackup=stackup_locked(design)
    )


def test_a_stackup_added_to_a_built_board() -> None:
    plain = text_of(build(blink(), 10))
    output = rebuild(stacked(), plain, 10)
    setup, before = child(parse(text_of(output)), "setup"), child(parse(plain), "setup")
    assert setup.nodes()[0].name == "stackup"
    assert list(setup.children[1:]) == list(before.children)
    assert stack_codes(output) == []
    assert output.summary["stackup"] == {"source": "script", "thickness": 1_590_000, "copper": 2}


def test_a_kicad_stackup_kept_without_a_script_one() -> None:
    text = text_of(build(stacked(), 10))
    output = rebuild(blink(), text, 10)
    written = parse(text_of(output))
    assert tree_equal(child(written, "setup"), child(parse(text), "setup"))
    assert tree_equal(child(written, "general"), child(parse(text), "general"))
    assert stack_codes(output) == []
    assert output.summary["stackup"] == {"source": "board", "thickness": 1_590_000, "copper": 2}


def test_an_unused_node_is_replaced_by_the_scripts() -> None:
    """A node that KiCad ignores gives no projected stack-up, so the script's is written."""
    text = text_of(build(stacked(), 10))
    root = parse(text)
    node = child(child(root, "setup"), "stackup")
    broken = dumps(replaced(root, node, node.with_children(node.children[1:])))
    output = rebuild(stacked(), broken, 10)
    board = read_board(text_of(output)).board
    assert board is not None and board.stackup is not None and len(board.stackup.layers) == 9
    assert output.summary["stackup"] == {"source": "script", "thickness": 1_590_000, "copper": 2}
