# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored physical pad metadata remains exact through import definitions (c0355)."""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from _importcode import build, imported, shared

from fenolite.backends.kicad.embed import local_footprint, placed_tree
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.importer._pad_annotations import annotation_restorer
from fenolite.importer.vendor import vendor
from fenolite.library import derive_library
from fenolite.model.circuit import Component

BOARD = Path(__file__).resolve().parents[3] / "tests/data/kicad/board/two_layer.kicad_pcb"
ANNOTATIONS = frozenset({"pinfunction", "pintype"})


def annotations(root: Node) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(dumps(c, style="compact") for c in pad.nodes() if c.name in ANNOTATIONS)
        for pad in root.nodes("pad")
    )


def authored() -> str:
    root = parse(BOARD.read_text())
    footprint = root.nodes("footprint")[0]
    pads = footprint.nodes("pad")
    clean = [
        p.with_children([c for c in p.children if not isinstance(c, Node) or c.name not in ANNOTATIONS])
        for p in pads
    ]
    first = pads[0].with_children(
        (*clean[0].children, parse('(pinfunction "")'), parse('(pintype "AUTH_UNKNOWN+no_connect")'))
    )
    duplicate = pads[0].with_children(
        (
            *(c for c in clean[0].children if not isinstance(c, Node) or c.name != "uuid"),
            parse('(uuid "00000000-0000-4000-8000-000000000099")'),
            parse('(pinfunction "AUTH_OTHER")'),
            parse('(pintype "input")'),
        )
    )
    second = pads[1].with_children((*clean[1].children, parse('(pintype "passive")')))
    absent = clean[1].with_children(
        (
            *(c for c in clean[1].children if not isinstance(c, Node) or c.name != "uuid"),
            parse('(uuid "00000000-0000-4000-8000-000000000100")'),
        )
    )
    made = footprint.with_children(
        [first if c is pads[0] else second if c is pads[1] else c for c in footprint.children]
        + [duplicate, absent]
    )
    return dumps(root.with_children([made if c is footprint else c for c in root.children]))


@pytest.mark.parametrize("target", (9, 10))
@pytest.mark.parametrize("side", ("top", "bottom"))
@pytest.mark.parametrize("source_side", ("top", "bottom"))
def test_physical_pad_metadata_and_presence_survive_vendor(target: int, side: str, source_side: str) -> None:
    text = authored()
    if source_side == "bottom":
        root = parse(text)
        fp = root.nodes("footprint")[0]
        flipped = (
            dumps(fp)
            .replace('"F.Cu"', '"B.Cu"')
            .replace('"F.Paste"', '"B.Paste"')
            .replace('"F.Mask"', '"B.Mask"')
        )
        text = dumps(root.with_children([parse(flipped) if c is fp else c for c in root.children]))
    original = parse(text).nodes("footprint")[0]
    found = vendor(read_board(text), text, target=target)
    lib_id = found.footprints["R1"]
    library, _, name = lib_id.partition(":")
    definition = read_footprint(found.files[f"lib/{library}.pretty/{name}.kicad_mod"], library=library)
    placed = placed_tree(
        definition,
        component=Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="R1"),
        at=Point(20_000_000, 15_000_000),
        rotation=90_000_000,
        side=side,  # type: ignore[arg-type]
        key="authored",
    )
    assert len(original.nodes("pad")) == len(placed.nodes("pad")) == 4
    assert annotations(placed) == annotations(original)
    assert annotations(original) == (
        ('(pinfunction "")', '(pintype "AUTH_UNKNOWN+no_connect")'),
        ('(pintype "passive")',),
        ('(pinfunction "AUTH_OTHER")', '(pintype "input")'),
        (),
    )


def test_generic_library_extraction_keeps_its_circuit_free_default() -> None:
    found = derive_library(authored(), library="Authored", target=10)
    assert all(not any(annotations(parse(item.text))) for item in found.footprints)


def test_authored_fixture_contains_a_duplicate_number_with_distinct_metadata() -> None:
    pads = parse(authored()).nodes("footprint")[0].nodes("pad")
    assert [pad.atoms()[0] for pad in pads] == [
        Atom.string("1"),
        Atom.string("2"),
        Atom.string("1"),
        Atom.string("2"),
    ]
    assert pads[0].find("at") == pads[2].find("at")
    assert (
        annotations(parse(authored()).nodes("footprint")[0])[0]
        != annotations(parse(authored()).nodes("footprint")[0])[2]
    )


def _local(text: str) -> Node:
    root = parse(text).nodes("footprint")[0]
    issues = []
    local = local_footprint(root, 90_000_000, "top", issues)
    assert not issues
    return local


@pytest.mark.parametrize("change", ("reverse", "drop", "uuid", "number", "extra", "reference"))
def test_changed_transform_identity_refuses_without_a_pad_number_fallback(change: str) -> None:
    text = authored()
    local = _local(text)
    pads = list(local.nodes("pad"))
    if change == "reverse":
        pads.reverse()
    elif change == "drop":
        pads.pop()
    elif change == "extra":
        pads.append(pads[0])
    elif change == "uuid":
        pads[0] = pads[0].with_children(
            [
                parse('(uuid "00000000-0000-4000-8000-000000000101")')
                if isinstance(c, Node) and c.name == "uuid"
                else c
                for c in pads[0].children
            ]
        )
    elif change == "number":
        pads[0] = pads[0].with_children([Atom.string("AUTH_OTHER_NUMBER"), *pads[0].children[1:]])
    if change == "reference":
        children = [
            c.with_children([Atom.string("Reference"), Atom.string("AUTH_WRONG"), *c.children[2:]])
            if isinstance(c, Node) and c.name == "property" and c.atoms()[0].value == "Reference"
            else c
            for c in local.children
        ]
    else:
        children = [c for c in local.children if not isinstance(c, Node) or c.name != "pad"] + pads
    with pytest.raises(FormatError, match="identity/cardinality/order"):
        annotation_restorer(text)(local.with_children(children))


@pytest.mark.parametrize("fragment", ("(pintype 1)", '(pintype "a" "b")', '(pinfunction (nested "x"))'))
def test_malformed_annotations_refuse(fragment: str) -> None:
    text = authored().replace('(pintype "AUTH_UNKNOWN+no_connect")', fragment)
    with pytest.raises(FormatError, match="one string|one child"):
        annotation_restorer(text)


def test_ambiguous_annotated_physical_identity_is_not_chosen_first() -> None:
    root = parse(authored())
    duplicate = root.nodes("footprint")[0]
    text = dumps(root.with_children([*root.children, duplicate]))
    with pytest.raises(FormatError, match="ambiguous"):
        annotation_restorer(text)(_local(text))


def test_shared_reference_absent_annotations_keep_the_complete_absent_path() -> None:
    root = parse(authored())
    clean = []
    for fp in root.nodes("footprint"):
        clean.append(
            fp.with_children(
                [
                    c.with_children(
                        [p for p in c.children if not isinstance(p, Node) or p.name not in ANNOTATIONS]
                    )
                    if isinstance(c, Node) and c.name == "pad"
                    else c
                    for c in fp.children
                ]
            )
        )
    root = root.with_children(
        [
            *(c for c in root.children if not isinstance(c, Node) or c.name != "footprint"),
            *clean,
            clean[0],
            clean[0],
        ]
    )
    text = dumps(root)
    local = _local(text)
    assert annotation_restorer(text)(local) is local


def test_nonannotation_children_and_annotation_order_remain_exact() -> None:
    text = authored()
    local = _local(text)
    restored = annotation_restorer(text)(local)
    without = restored.with_children(
        [
            c.with_children([p for p in c.children if not isinstance(p, Node) or p.name not in ANNOTATIONS])
            if isinstance(c, Node) and c.name == "pad"
            else c
            for c in restored.children
        ]
    )
    assert without == local
    assert annotations(restored) == annotations(parse(text).nodes("footprint")[0])


@pytest.mark.parametrize("target", (9, 10))
def test_annotation_variants_split_and_identical_physical_metadata_share(target: int) -> None:
    root = parse(authored())
    original = root.nodes("footprint")[0]

    def copy(node: Node, ref: str, *, remove: bool) -> Node:
        children = []
        for c in node.children:
            if isinstance(c, Node):
                if c.name == "uuid":
                    c = parse(f'(uuid "{uuid5(NAMESPACE_URL, ref + c.atoms()[0].value)}")')
                elif c.name == "property" and c.atoms()[0].value == "Reference":
                    c = c.with_children([Atom.string("Reference"), Atom.string(ref), *c.children[2:]])
                elif remove and c.name in ANNOTATIONS:
                    continue
                else:
                    c = copy(c, ref, remove=remove)
            children.append(c)
        return node.with_children(children)

    text = dumps(
        root.with_children(
            [*root.children, copy(original, "R9", remove=True), copy(original, "R10", remove=False)]
        )
    )
    found = vendor(read_board(text), text, target=target)
    assert found.footprints["R1"] == found.footprints["R10"]
    assert found.footprints["R1"] != found.footprints["R9"]


def test_real_import_build_preserves_shared_references_per_physical_pad(tmp_path: Path) -> None:
    project = shared(tmp_path / "src")
    board = project.with_suffix(".kicad_pcb")
    root = parse(board.read_text())
    physical = iter(range(len(root.nodes("footprint"))))
    children = []
    for c in root.children:
        if isinstance(c, Node) and c.name == "footprint":
            index = next(physical)
            c = c.with_children(
                [
                    p.with_children(
                        [
                            *(x for x in p.children if not isinstance(x, Node) or x.name not in ANNOTATIONS),
                            parse(f'(pinfunction "AUTH_{index}_{j}")'),
                            parse('(pintype "input")'),
                        ]
                    )
                    if isinstance(p, Node) and p.name == "pad"
                    else p
                    for j, p in enumerate(c.children)
                ]
            )
        children.append(c)
    root = root.with_children(children)
    board.write_text(dumps(root))
    reply = imported(tmp_path, project, "--confirm")
    assert reply.exit_code == 0, reply.error
    built = build(tmp_path / "out")
    assert built.exit_code == 0, built.error
    again = parse((tmp_path / "out/built/shared.kicad_pcb").read_text())

    def keyed(tree: Node) -> dict[tuple[str, str], tuple[tuple[str, ...], ...]]:
        return {
            (
                next(p.atoms()[1].value for p in fp.nodes("property") if p.atoms()[0].value == "Reference"),
                dumps(fp.find("at"), style="compact"),  # type: ignore[arg-type]
            ): annotations(fp)
            for fp in tree.nodes("footprint")
        }

    assert len(keyed(root)) == len(root.nodes("footprint"))
    assert keyed(again) == keyed(root)


def test_malformed_annotation_refuses_before_import_plan(tmp_path: Path) -> None:
    text = authored().replace('(pinfunction "")', '(pinfunction "a" "b")')
    source = tmp_path / "malformed.kicad_pcb"
    source.write_text(text)
    reply = imported(tmp_path, source)
    assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004"
    assert not reply.result.get("plan") and not reply.result.get("plan_id")
    assert not (tmp_path / "out").exists()
    assert source.read_text() == text
