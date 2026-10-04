# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Writing footprint files and reading board footprints as definitions (capabilities
kicad-file-backend, "Footprint files are written", and kicad-library-read, "Board footprints read as
definitions"; change c0018)."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.mod import (
    BOARD_CHAIN,
    WRITE_ISSUE_CODES,
    board_footprints,
    footprint_from,
    read_footprint,
    write_footprint,
    write_pretty,
)
from fenolite.backends.kicad.sexpr import Node, parse, tree_equal
from fenolite.backends.kicad.versions import FileKind, FutureFormatError, LossyWriteError, check_emittable
from fenolite.core.errors import Issue
from fenolite.model.base import Opaque
from fenolite.model.board import Graphic, Pad
from fenolite.model.library import FootprintDef

ROOT = Path(__file__).resolve().parents[4]
MINI = ROOT / "tests" / "data" / "libs" / "Mini.pretty"
MINI_V9 = ROOT / "tests" / "data" / "libs" / "Mini_v9.pretty"
R0603 = MINI / "Mini_R_0603.kicad_mod"
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
SRC = ROOT / "src" / "fenolite" / "backends" / "kicad"
PRODUCED: set[str] = set()


def bare(defn: FootprintDef) -> FootprintDef:
    """The definition without provenance and ``ext``, on itself and every sub-entity."""

    def clean(pad: Pad) -> Pad:
        stack = pad.padstack
        if stack is not None:
            stack = dataclasses.replace(stack, provenance=None, ext={})
        return dataclasses.replace(pad, provenance=None, ext={}, padstack=stack)

    return dataclasses.replace(
        defn,
        provenance=None,
        ext={},
        pads=tuple(clean(p) for p in defn.pads),
        graphics=tuple(dataclasses.replace(g, provenance=None, ext={}) for g in defn.graphics),
    )


def heads(node: Node) -> list[str]:
    return [c.name for c in node.nodes()]


def collect(issues: list[Issue]) -> list[Issue]:
    PRODUCED.update(i.code for i in issues if i.code.startswith("kicad.footprint."))
    return issues


def opaque_fragments(defn: FootprintDef | Pad | Graphic) -> list[str]:
    return [s.fragment for s in slotlib.from_ext(defn.ext["kicad"]) if isinstance(s, Opaque)]


# -- writing


def test_mini_resistor_for_10() -> None:
    defn = read_footprint(R0603)
    text = write_footprint(defn, target=10)
    assert text.startswith('(footprint "Mini_R_0603"')
    for part in ("(version 20260206)", '(generator "fenolite")', '(generator_version "10.0")'):
        assert part in text
    source, written = parse(R0603.read_text(encoding="utf-8")), parse(text)
    assert heads(written) == heads(source)
    keep = [c for c in source.nodes() if c.name != "generator"]
    assert all(
        tree_equal(a, b)
        for a, b in zip(keep, [c for c in written.nodes() if c.name != "generator"], strict=True)
    )


def test_mini_resistor_for_9() -> None:
    defn = read_footprint(MINI_V9 / "Mini_R_0603.kicad_mod")
    text = write_footprint(defn, target=9)
    assert "(version 20241229)" in text and '(generator_version "9.0")' in text
    issues = check_emittable(parse(text), FileKind.FOOTPRINT, 9)
    assert [i for i in issues if i.severity == "error"] == []


@pytest.mark.parametrize(
    "path",
    sorted(MINI.glob("*.kicad_mod")) + sorted(MINI_V9.glob("*.kicad_mod")),
    ids=lambda p: f"{p.parent.name}/{p.stem}",
)
def test_round_trip(path: Path) -> None:
    defn = read_footprint(path)
    target = 10 if path.parent == MINI else 9
    found: list[Issue] = []
    again = read_footprint(write_footprint(defn, target=target, issues=found), library=defn.library)
    assert bare(again) == bare(defn) and found == []
    header = ("(version ", "(generator ", "(generator_version ")

    def strip(d: FootprintDef) -> list[str]:
        return [f for f in opaque_fragments(d) if not f.startswith(header)]

    assert strip(again) == strip(defn)


TEN_ONLY = """(footprint "J" (version 20260206) (generator "t") (generator_version "10.0") (layer "F.Cu")
  (duplicate_pad_numbers_are_jumpers no)
  (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (uuid "00000000-0000-4000-8000-000000000001")))"""


def test_ten_only_fragment_refused_for_9() -> None:
    defn = read_footprint(TEN_ONLY)
    with pytest.raises(LossyWriteError) as caught:
        write_footprint(defn, target=9)
    assert caught.value.droppable is True
    assert [i.code for i in caught.value.issues] == ["kicad.token.too-new"]
    found: list[Issue] = []
    text = write_footprint(defn, target=9, allow_lossy=True, issues=found)
    assert "duplicate_pad_numbers_are_jumpers" not in text
    assert [i.code for i in collect(found)] == ["kicad.footprint.dropped-too-new"]
    assert found[0].severity == "warning" and "duplicate_pad_numbers_are_jumpers" in found[0].message
    assert "duplicate_pad_numbers_are_jumpers" in write_footprint(defn, target=10)


def test_value_edited() -> None:
    defn = read_footprint(R0603)
    edited = dataclasses.replace(defn, properties={**defn.properties, "Value": "10k"})
    written = parse(write_footprint(edited, target=10))
    source = parse(R0603.read_text(encoding="utf-8"))

    def value(node: Node) -> Node:
        return next(c for c in node.nodes("property") if c.atoms()[0].value == "Value")

    new, old = value(written), value(source)
    assert new.atoms()[1].value == "10k"
    assert tree_equal(new.with_children([new.children[0], old.children[1], *new.children[2:]]), old)


def test_read_only_projection_edited() -> None:
    defn = read_footprint(R0603)
    edited = dataclasses.replace(defn, properties={**defn.properties, "Datasheet": "https://example.org/x"})
    with pytest.raises(LossyWriteError) as caught:
        write_footprint(edited, target=10)
    issues = collect(list(caught.value.issues))
    assert caught.value.droppable is False
    assert [i.code for i in issues] == ["kicad.footprint.projection-read-only"]
    assert "properties" in issues[0].message and issues[0].where.startswith("/footprint/property[")


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"keywords": ("x",)}, "keywords"),
        ({"models": ("${X}/other.step",)}, "models"),
    ],
)
def test_other_projections_read_only(change: dict[str, object], field: str) -> None:
    defn = dataclasses.replace(read_footprint(R0603), **change)
    with pytest.raises(LossyWriteError) as caught:
        write_footprint(defn, target=10)
    issues = collect(list(caught.value.issues))
    assert [i.code for i in issues] == ["kicad.footprint.projection-read-only"] and field in issues[0].message


def test_stroke_width_read_only() -> None:
    defn = read_footprint(R0603)
    graphic = defn.graphics[0]
    edited = dataclasses.replace(
        defn, graphics=(dataclasses.replace(graphic, width=graphic.width + 1), *defn.graphics[1:])
    )
    with pytest.raises(LossyWriteError) as caught:
        write_footprint(edited, target=10)
    assert "width" in collect(list(caught.value.issues))[0].message


def test_future_definition_refused() -> None:
    defn = read_footprint('(footprint "F" (version 20991231) (generator "t") (layer "F.Cu"))')
    with pytest.raises(FutureFormatError):
        write_footprint(defn, target=10)


def test_definition_without_slots_can_be_authored() -> None:
    text = write_footprint(FootprintDef(id="fpd_x", name="X"))
    assert '(footprint "X"' in text
    assert "(version " in text


def test_dsl_authored_definition_writes_deterministically() -> None:
    from fenolite.dsl import Footprint, mm

    footprint = Footprint("Local", "TwoPin", kind="smd")
    footprint.pad("1", at=(mm(-1), mm(0)), size=(mm(1), mm(1)))
    footprint.pad("2", at=(mm(1), mm(0)), size=(mm(1), mm(1)))
    footprint.rect((mm(-2), mm(-1)), (mm(2), mm(1)), layer="F.SilkS", width=mm(0.12))
    first = write_footprint(footprint.definition, target=10)

    assert first == write_footprint(footprint.definition, target=10)
    readback = read_footprint(first, library="Local")
    assert [(pad.number, pad.position, pad.size) for pad in readback.pads] == [
        (pad.number, pad.position, pad.size) for pad in footprint.definition.pads
    ]
    assert [(graphic.kind, graphic.layer, graphic.points) for graphic in readback.graphics] == [
        (graphic.kind, graphic.layer, graphic.points) for graphic in footprint.definition.graphics
    ]


def test_dsl_authored_aligned_slot_writes_oval_drill() -> None:
    from fenolite.dsl import Footprint, mm

    footprint = Footprint("Local", "Slot", kind="through_hole")
    footprint.pad(
        "1",
        at=(mm(0), mm(0)),
        size=(mm(2), mm(1)),
        rotation=90,
        drill=mm(0.8),
        drill_shape="slot",
        drill_length=mm(1.6),
        drill_rotation=90,
    )
    text = write_footprint(footprint.definition, target=10)
    assert "(drill oval 0.8 1.6)" in text
    readback = read_footprint(text, library="Local")
    pad = readback.pads[0]
    assert pad.drill == 800_000 and pad.padstack is not None
    assert (pad.padstack.hole_shape, pad.padstack.hole_length, pad.padstack.hole_rotation) == (
        "slot",
        1_600_000,
        90_000_000,
    )


def test_kicad_writer_refuses_diagonal_slot_axis() -> None:
    from fenolite.dsl import Footprint, mm

    footprint = Footprint("Local", "Diagonal", kind="through_hole")
    footprint.pad(
        "1",
        at=(mm(0), mm(0)),
        size=(mm(2), mm(2)),
        drill=mm(0.8),
        drill_shape="slot",
        drill_length=mm(1.6),
        drill_rotation=45,
    )
    with pytest.raises(LossyWriteError, match="horizontal or vertical"):
        write_footprint(footprint.definition, target=10)


def test_library_folder_mapping() -> None:
    defs = [read_footprint(p) for p in sorted(MINI.glob("*.kicad_mod"), reverse=True)]
    files = write_pretty(defs, target=10)
    assert list(files) == sorted(f"{d.name}.kicad_mod" for d in defs) and len(files) == 4
    with pytest.raises(ValueError, match="two footprints"):
        write_pretty([defs[0], defs[0]])
    for bad in ("a/b", "a\\b", "a:b"):
        with pytest.raises(ValueError):
            write_pretty([dataclasses.replace(defs[0], name=bad)])


def test_codes() -> None:
    literals: set[str] = set()
    for path in SRC.glob("*.py"):
        literals |= set(re.findall(r'"(kicad\.footprint\.[a-z0-9.-]+)"', path.read_text(encoding="utf-8")))
    assert literals == set(WRITE_ISSUE_CODES)
    assert dict(WRITE_ISSUE_CODES) == {
        "kicad.footprint.dropped-too-new": "warning",
        "kicad.footprint.projection-read-only": "error",
    }
    assert PRODUCED <= set(WRITE_ISSUE_CODES)


# -- board footprints


def test_board_footprints() -> None:
    defs = board_footprints(BOARD)
    assert [(d.library, d.name) for d in defs] == [
        ("Fenolite_Test", "R_0603"),
        ("Fenolite_Test", "LED_THT_3mm"),
    ]
    assert [d.provenance.locator for d in defs] == ["/kicad_pcb/footprint[0]", "/kicad_pcb/footprint[1]"]  # type: ignore[union-attr]
    for defn in defs:
        fragments = opaque_fragments(defn)
        assert any(f.startswith("(at ") for f in fragments) and any(f.startswith("(uuid ") for f in fragments)
        for pad in defn.pads:
            pad_fragments = opaque_fragments(pad)
            assert any(f.startswith("(net ") for f in pad_fragments)
            assert pad.provenance.locator.startswith(defn.provenance.locator + "/pad[")  # type: ignore[union-attr]
    assert any(f.startswith("(pintype ") for p in defs[0].pads for f in opaque_fragments(p))
    assert any(f.startswith("(pinfunction ") for p in defs[1].pads for f in opaque_fragments(p))


def test_board_footprint_round_trip() -> None:
    for defn in board_footprints(BOARD):
        again = read_footprint(write_footprint(defn, target=9), library=defn.library)
        assert bare(again) == bare(defn)


INLINE = """(kicad_pcb (version 20241229) (generator "t")
  (footprint "{name}" (layer "F.Cu") (uuid "00000000-0000-4000-8000-0000000000aa") (at 1 2)
    (path "/1f2e") (sheetname "Root") (sheetfile "a.kicad_sch")))"""


def test_sheet_links_kept_opaque() -> None:
    (defn,) = board_footprints(INLINE.format(name="Lib:R_0603"))
    fragments = [f for f in opaque_fragments(defn) if f.startswith(("(path", "(sheetname", "(sheetfile"))]
    assert fragments == ['(path "/1f2e")', '(sheetname "Root")', '(sheetfile "a.kicad_sch")']


def test_lib_id_without_colon() -> None:
    (defn,) = board_footprints(INLINE.format(name="R_0603"))
    assert (defn.library, defn.name) == ("", "R_0603")


def test_board_chain_index_and_default() -> None:
    from fenolite.backends.kicad._libread import load_source

    loaded = load_source(BOARD)
    second = footprint_from(loaded, root_chain=BOARD_CHAIN, index=1)
    assert second.name == "LED_THT_3mm"
    with pytest.raises(IndexError):
        footprint_from(loaded, root_chain=BOARD_CHAIN, index=2)
    with pytest.raises(ValueError, match="root chain"):
        footprint_from(loaded, root_chain=("x",))


def test_board_version_issues_once() -> None:
    found: list[Issue] = []
    text = (
        INLINE.format(name="A")
        .replace("(footprint", '(footprint "B" (layer "F.Cu"))\n  (footprint', 1)
        .replace("20241229", "20250101")
    )
    board_footprints(text, issues=found)
    assert [i.code for i in found].count("kicad.version.dev") == 1
