# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placed copies on the bottom side (capability kicad-file-backend, "Footprint embedding", c0017)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.kicad.embed import (
    EVIDENCE,
    FLIP_UNSUPPORTED,
    MIRROR_HEADS,
    flip_evidence,
    flip_footprint_tree,
    local_footprint,
    place_footprint,
)
from fenolite.backends.kicad.layers import created_layers, flip_layer
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse, walk
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.model.board import FootprintInstance
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

MINI = Path(__file__).resolve().parents[4] / "tests" / "data" / "libs" / "Mini.pretty"
CHAMFER = Path(__file__).resolve().parents[4] / "tests/data/kicad/footprint/ExactChamfer.kicad_mod"
U1 = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="U1", value="QFP")
AT = Point(20_000_000, 15_000_000)


def qfp() -> FootprintDef:
    return read_footprint(MINI / "Mini_QFP-32_7x7mm_P0.8mm.kicad_mod", library="Mini")


def written(instance: FootprintInstance, component: Component = U1) -> Node:
    design = Design.new("bottom", seed=1)
    assert design.board is not None
    board = dataclasses.replace(design.board, layers=created_layers(2), footprints=(instance,))
    root = parse(
        write_board(
            dataclasses.replace(design, circuit=Circuit(components=(component,)), board=board), target=10
        ).text
    )
    (fp,) = root.nodes("footprint")
    return fp


def pad_node(fp: Node, number: str) -> Node:
    return next(p for p in fp.nodes("pad") if p.children[0] == Atom.string(number))


def test_bottom_placement_mirrors_the_children() -> None:
    instance = place_footprint(qfp(), component=U1, at=AT, rotation=30_000_000, side="bottom", key="U1")
    pad1 = next(p for p in instance.pads if p.number == "1")
    pad9 = next(p for p in instance.pads if p.number == "9")
    assert pad1.position == Point(-4_150_000, 2_800_000) and pad1.layers[0] == "B.Cu"
    assert pad9.rotation == 270_000_000
    fp = written(instance)
    assert pad_node(fp, "9").find("at") == parse("(at -2.8 -4.15 300)")
    assert fp.find("layer") == parse('(layer "B.Cu")') and instance.side == "bottom"


def test_top_angles_are_absolute() -> None:
    instance = place_footprint(qfp(), component=U1, at=AT, rotation=30_000_000, key="U1")
    pad9 = next(p for p in instance.pads if p.number == "9")
    assert pad9.rotation == 90_000_000 and pad9.position == Point(-2_800_000, 4_150_000)
    assert pad_node(written(instance), "9").find("at") == parse("(at -2.8 4.15 120)")


def test_bottom_layers_texts_and_graphics() -> None:
    fp = written(place_footprint(qfp(), component=U1, at=AT, side="bottom", key="U1"))
    layers = {a.value for _, n in walk(fp) if n.name in ("layer", "layers") for a in n.atoms()}
    assert not {name for name in layers if name.startswith("F.")}
    for prop in fp.nodes("property"):
        effects = prop.find("effects")
        assert effects is not None and effects.find("justify") == parse("(justify mirror)")
    source = parse((MINI / "Mini_QFP-32_7x7mm_P0.8mm.kicad_mod").read_text(encoding="utf-8"))
    first, flipped = source.nodes("fp_line")[0], fp.nodes("fp_line")[0]
    assert flipped.find("start") == parse("(start -3.61 3.61)") and first.find("start") == parse(
        "(start -3.61 -3.61)"
    )
    model = fp.find("model")
    assert model is not None and model == source.find("model")


def test_mirror_toggles_off() -> None:
    text = (MINI / "Mini_R_0603.kicad_mod").read_text(encoding="utf-8")
    font_end = "(thickness 0.15)\n\t\t\t)\n\t\t)"
    text = text.replace(font_end, "(thickness 0.15)\n\t\t\t)\n\t\t\t(justify left mirror)\n\t\t)", 1)
    defn = read_footprint(text, library="Mini")
    fp = written(place_footprint(defn, component=U1, at=AT, side="bottom", key="U1"))
    reference = fp.nodes("property")[0]
    effects = reference.find("effects")
    assert effects is not None and effects.find("justify") == parse("(justify left)")


def test_unsupported_geometry_on_the_bottom() -> None:
    text = (MINI / "Mini_R_0603.kicad_mod").read_text(encoding="utf-8")
    text = text.replace('(pad "1" smd roundrect', '(pad "1" smd trapezoid', 1).replace(
        "(size 0.9 0.95)\n", "(size 0.9 0.95)\n\t\t(rect_delta 0 0.1)\n", 1
    )
    defn = read_footprint(text, library="Mini")
    with pytest.raises(LossyWriteError) as info:
        place_footprint(defn, component=U1, at=AT, side="bottom", key="U1")
    assert info.value.droppable is False
    (issue,) = info.value.issues
    assert issue.code == "kicad.board.flip-unsupported" and issue.where == "/footprint/pad[0]/rect_delta[0]"
    top = written(place_footprint(defn, component=U1, at=AT, key="U1"))
    assert pad_node(top, "1").find("rect_delta") == parse("(rect_delta 0 0.1)")


def test_tables() -> None:
    assert MIRROR_HEADS == {"at", "start", "mid", "end", "center", "xy", "offset"}
    assert {"rect_delta", "dimension", "image"} <= FLIP_UNSUPPORTED
    names = ("F.Cu", "B.Mask", "F.CrtYd", "*.Cu", "In1.Cu", "Edge.Cuts", "User.1", "F.Fab")
    flipped = ("B.Cu", "F.Mask", "B.CrtYd", "*.Cu", "In1.Cu", "Edge.Cuts", "User.1", "B.Fab")
    assert tuple(flip_layer(n) for n in names) == flipped


def test_drill_offset_mirrored() -> None:
    text = (MINI / "Mini_LED_THT_3mm.kicad_mod").read_text(encoding="utf-8")
    text = text.replace("(drill 0.9)", "(drill 0.9 (offset 0.1 0.2))", 1)
    defn = read_footprint(text, library="Mini")
    fp = written(place_footprint(defn, component=U1, at=AT, side="bottom", key="D1"))
    drill = pad_node(fp, "1").find("drill")
    assert drill is not None and dumps(drill, style="compact") == "(drill 0.9 (offset 0.1 -0.2))"


@pytest.mark.parametrize("rotation", [0, 30_000_000, 90_000_000, 180_000_000])
@pytest.mark.parametrize("mask", range(16))
def test_bottom_chamfer_corners_and_derivation(rotation: int, mask: int) -> None:
    """Every corner subset follows the pad's local-Y mirror, independent of placement rotation."""
    names = ("top_left", "top_right", "bottom_left", "bottom_right")
    expected = ("bottom_left", "bottom_right", "top_left", "top_right")
    selected = tuple(name for index, name in enumerate(names) if mask & (1 << index))
    mirrored = tuple(name for index, name in enumerate(expected) if mask & (1 << index))
    text = CHAMFER.read_text(encoding="utf-8").replace("top_left bottom_right", " ".join(selected))
    definition = read_footprint(text, library="Authored")
    instance = place_footprint(definition, component=U1, at=AT, rotation=rotation, side="bottom", key="U1")
    fp = written(instance)
    pad = pad_node(fp, "1")
    assert pad.find("chamfer") == parse("(chamfer " + " ".join(mirrored) + ")")
    assert pad.find("chamfer_ratio") == parse("(chamfer_ratio 0.2)")
    assert pad.find("at").atoms()[0:2] == parse("(at 0.3 0.7)").atoms()  # type: ignore[union-attr]
    assert pad.find("layers") == parse('(layers "B.Cu" "B.Paste" "B.Mask")')
    issues = []
    local = local_footprint(fp, rotation, "bottom", issues)
    assert issues == []
    back = pad_node(local, "1")
    assert back.find("chamfer") == parse("(chamfer " + " ".join(selected) + ")")
    assert back.find("chamfer_ratio") == pad.find("chamfer_ratio")
    assert back.find("at") == parse("(at 0.3 -0.7 35)")
    assert "chamfer" not in FLIP_UNSUPPORTED


def test_chamfer_flip_is_an_involution() -> None:
    tree = parse(CHAMFER.read_text(encoding="utf-8"))
    issues = []
    assert flip_footprint_tree(flip_footprint_tree(tree, issues), issues) == tree
    assert issues == []
    # An opaque namesake outside a pad is preserved.
    other = parse("(footprint empty (opaque (chamfer top_left)))")
    assert flip_footprint_tree(other, []) == other


def test_flip_evidence_depends_on_the_definition() -> None:
    assert flip_evidence(qfp()) == EVIDENCE
    assert EVIDENCE.level is Level.KICAD_VERIFIED
    inferred = flip_evidence(read_footprint(CHAMFER, library="Authored"))
    assert inferred.level is Level.INFERRED
    assert "H-G-CHAMFER-FLIP" in inferred.hypotheses
    assert set(EVIDENCE.hypotheses) <= set(inferred.hypotheses)
