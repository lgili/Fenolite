# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint pads, padstacks and graphics; rejections; ids and provenance (kicad-library-read)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _libs import MINI

from fenolite.backends.kicad import slots
from fenolite.backends.kicad.mod import read_footprint
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id, is_id
from fenolite.model.base import Opaque
from fenolite.model.board import PadstackLayer
from fenolite.model.library import FootprintDef

PRETTY = MINI / "Mini.pretty"
R0603 = PRETTY / "Mini_R_0603.kicad_mod"
HEADER = '(footprint "X" (version 20260206) (generator "t") (layer "F.Cu")'


def _pad(body: str, number: str = "1") -> str:
    return f'(pad "{number}" thru_hole circle (at 0 0) (size 1.6 1.6) {body} (layers "*.Cu" "*.Mask"))'


def _opaque(bag_owner: object) -> list[Opaque]:
    return [s for s in slots.from_ext(bag_owner.ext["kicad"]) if isinstance(s, Opaque)]  # type: ignore[attr-defined]


def _codes(issues: list[Issue]) -> list[tuple[str, str]]:
    return [(i.code, i.severity) for i in issues]


# --- pads -----------------------------------------------------------------------------------------


def test_through_hole_led() -> None:
    fp = read_footprint(PRETTY / "Mini_LED_THT_3mm.kicad_mod")
    assert fp.kind == "through_hole"
    assert [p.kind for p in fp.pads] == ["thru_hole", "thru_hole"]
    assert {p.layers for p in fp.pads} == {("*.Cu", "*.Mask")}
    assert all(type(p.drill) is int and p.drill == 900_000 for p in fp.pads)
    assert fp.pads[1].position == Point(2_540_000, 0) and fp.pads[1].size == Size(1_800_000, 1_800_000)


def test_pad_rotation_in_microdegrees() -> None:
    fp = read_footprint(PRETTY / "Mini_QFP-32_7x7mm_P0.8mm.kicad_mod")
    assert len(fp.pads) == 32 and fp.pads[0].rotation == 0 and fp.pads[8].rotation == 90_000_000
    assert [p.number for p in fp.pads] == [str(n) for n in range(1, 33)]


def test_duplicate_and_empty_pad_numbers_are_kept() -> None:
    fp = read_footprint(PRETTY / "Mini_Edge_Cases.kicad_mod")
    numbers = [p.number for p in fp.pads]
    assert numbers[:3] == ["", "1", "1"] and fp.pads[0].kind == "np_thru_hole"
    assert len({p.id for p in fp.pads}) == len(fp.pads)


def test_padstack_pad_keeps_its_padstack() -> None:
    issues: list[Issue] = []
    fp = read_footprint(PRETTY / "Mini_Edge_Cases.kicad_mod", issues=issues)
    pad = next(p for p in fp.pads if p.number == "4")
    assert pad.padstack is not None and is_id(pad.padstack.id, "pst")
    assert pad.padstack.layers == (
        PadstackLayer("F.Cu", "circle", Size(1_700_000, 1_700_000)),
        PadstackLayer("Inner", "circle", Size(1_200_000, 1_200_000)),
        PadstackLayer("B.Cu", "rect", Size(1_500_000, 1_500_000)),
    )
    fragment = next(s for s in _opaque(pad) if s.fragment.startswith("(padstack"))
    assert fragment.min_version is not None and int(fragment.min_version) >= 20240929
    assert ("kicad.lib.kept-opaque", "info") in _codes(issues)


def test_oval_drill_is_modeled_as_slot() -> None:
    issues: list[Issue] = []
    fp = read_footprint(f"{HEADER} {_pad('(drill oval 1.2 2.0)')})", issues=issues)
    pad = fp.pads[0]
    assert pad.drill == 1_200_000
    assert pad.padstack is not None
    assert (pad.padstack.hole_shape, pad.padstack.hole_length, pad.padstack.hole_rotation) == (
        "slot",
        2_000_000,
        90_000_000,
    )
    assert not [s for s in _opaque(pad) if s.fragment.startswith("(drill")]
    assert not _codes(issues)


def test_offset_drill_is_projected() -> None:
    issues: list[Issue] = []
    fp = read_footprint(f"{HEADER} {_pad('(drill 0.8 (offset 0.1 0))')})", issues=issues)
    assert fp.pads[0].drill == 800_000
    assert [s.fragment for s in _opaque(fp.pads[0])] == ["(drill 0.8 (offset 0.1 0))"]
    assert _codes(issues) == [("kicad.lib.kept-opaque", "info")]


def test_plain_drill_is_modelled() -> None:
    issues: list[Issue] = []
    fp = read_footprint(f"{HEADER} {_pad('(drill 0.8)')})", issues=issues)
    assert fp.pads[0].drill == 800_000 and _opaque(fp.pads[0]) == [] and issues == []


# --- graphics -------------------------------------------------------------------------------------


def test_courtyard_graphics_are_selectable() -> None:
    fp = read_footprint(PRETTY / "Mini_QFP-32_7x7mm_P0.8mm.kicad_mod")
    court = fp.graphics_on("F.CrtYd")
    assert len(court) == 4 and {g.kind for g in court} == {"line"}
    assert all(
        len(g.points) == 2 and all(type(c) is int for p in g.points for c in (p.x, p.y)) for g in court
    )
    assert {p for g in court for p in g.points} == {
        Point(x, y) for x in (-5_250_000, 5_250_000) for y in (-5_250_000, 5_250_000)
    }


def test_graphic_kinds_and_fill() -> None:
    led = read_footprint(PRETTY / "Mini_LED_THT_3mm.kicad_mod")
    assert sorted(g.kind for g in led.graphics) == ["arc", "arc", "circle", "rect"]
    arc = next(g for g in led.graphics if g.kind == "arc")
    assert len(arc.points) == 3
    qfp = read_footprint(PRETTY / "Mini_QFP-32_7x7mm_P0.8mm.kicad_mod")
    poly = next(g for g in qfp.graphics if g.kind == "polygon")
    assert poly.filled and len(poly.points) == 3 and poly.layer == "F.SilkS"


def test_stroke_is_projected() -> None:
    line = '(fp_line (start 0 0) (end 1 0) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))'
    issues: list[Issue] = []
    fp = read_footprint(f"{HEADER} {line})", issues=issues)
    graphic = fp.graphics[0]
    assert graphic.width == 120_000 and graphic.points == (Point(0, 0), Point(1_000_000, 0))
    assert [s.fragment for s in _opaque(graphic)] == ["(stroke (width 0.12) (type solid))"]
    assert issues == []


def test_dashed_stroke_adds_an_info() -> None:
    line = '(fp_line (start 0 0) (end 1 0) (stroke (width 0.1) (type dash)) (layer "F.SilkS"))'
    issues: list[Issue] = []
    read_footprint(f"{HEADER} {line})", issues=issues)
    assert _codes(issues) == [("kicad.lib.kept-opaque", "info")]


@pytest.mark.parametrize(
    "graphic",
    [
        "(fp_poly (pts (xy 0 0) (arc (start 0 0) (mid 1 1) (end 2 0)))"
        ' (stroke (width 0.1)) (fill yes) (layer "F.SilkS"))',
        '(fp_rect (start 0 0) (end 1 1) (stroke (width 0.1)) (fill hatch) (layer "F.SilkS"))',
        '(fp_rect (start 0 0) (end 1 1) (radius 0.2) (stroke (width 0.1)) (fill no) (layer "F.SilkS"))',
        '(fp_line (start 0 0) (stroke (width 0.1)) (layer "F.SilkS"))',
    ],
    ids=["arc-in-pts", "hatch", "radius", "no-end"],
)
def test_unrepresentable_graphic_stays_opaque(graphic: str) -> None:
    issues: list[Issue] = []
    fp = read_footprint(f"{HEADER} {graphic})", issues=issues)
    assert fp.graphics == ()
    found = slots.from_ext(fp.ext["kicad"])[4]
    assert isinstance(found, Opaque) and found.fragment.startswith(graphic[:8])
    assert _codes(issues) == [("kicad.lib.kept-opaque", "info")]


# --- rejections -----------------------------------------------------------------------------------


def _pads(*kinds: str) -> str:
    return " ".join(
        f'(pad "{i + 1}" {k} rect (at 0 0) (size 1 1) (layers "F.Cu"))' for i, k in enumerate(kinds)
    )


def test_unknown_pad_type() -> None:
    with pytest.raises(FormatError, match="bogus") as caught:
        read_footprint(f"{HEADER} {_pads('smd', 'smd', 'smd', 'bogus')})", file="x.kicad_mod")
    assert caught.value.locator == "/footprint/pad[3]" and caught.value.file == "x.kicad_mod"
    assert caught.value.offset is not None


def test_unknown_pad_shape() -> None:
    with pytest.raises(FormatError, match="hexagon"):
        read_footprint(f'{HEADER} (pad "1" smd hexagon (at 0 0) (size 1 1) (layers "F.Cu")))')


def test_sub_nanometre_length() -> None:
    with pytest.raises(FormatError, match=r"1\.0000001") as caught:
        read_footprint(f'{HEADER} (pad "1" smd rect (at 0 0) (size 1.0000001 1) (layers "F.Cu")))')
    assert caught.value.locator == "/footprint/pad[0]/size[0]"


def test_sub_microdegree_angle() -> None:
    with pytest.raises(FormatError, match="0.0000001"):
        read_footprint(f'{HEADER} (pad "1" smd rect (at 0 0 0.0000001) (size 1 1) (layers "F.Cu")))')


def test_unknown_padstack_mode() -> None:
    body = '(drill 1) (padstack (mode frobnicate) (layer "B.Cu" (shape circle) (size 1 1)))'
    with pytest.raises(FormatError, match="frobnicate") as caught:
        read_footprint(f"{HEADER} {_pad(body)})")
    assert caught.value.locator == "/footprint/pad[0]"


@pytest.mark.parametrize(
    ("layer", "match"),
    [('(layer "B.Cu" (size 1 1))', "no shape"), ('(layer "B.Cu" (shape circle))', "no size"),
     ('(layer "B.Cu" (shape star) (size 1 1))', "star")],
)  # fmt: skip
def test_padstack_layer_problems(layer: str, match: str) -> None:
    body = f"(drill 1) (padstack (mode front_inner_back) {layer})"
    with pytest.raises(FormatError, match=match) as caught:
        read_footprint(f"{HEADER} {_pad(body)})")
    assert caught.value.locator.startswith("/footprint/pad[0]/padstack[0]/layer[0]")


def test_syntax_errors_propagate() -> None:
    with pytest.raises(FormatError):
        read_footprint(HEADER)


# --- ids and provenance ---------------------------------------------------------------------------


def test_stable_ids_across_reads() -> None:
    def ids(fp: FootprintDef) -> list[str]:
        return [fp.id, *(p.id for p in fp.pads), *(g.id for g in fp.graphics)]

    path = PRETTY / "Mini_QFP-32_7x7mm_P0.8mm.kicad_mod"
    first, second = read_footprint(path, library="Mini"), read_footprint(path, library="Mini")
    assert ids(first) == ids(second) and is_id(first.id, "fpd")
    assert len(set(ids(first))) == len(ids(first))


def test_copied_uuids_stay_distinct_across_definitions(tmp_path: Path) -> None:
    folder = tmp_path / "Mini.pretty"
    folder.mkdir()
    shutil.copyfile(R0603, folder / "Mini_R_0603.kicad_mod")
    shutil.copyfile(R0603, folder / "Mini_R_0603_B.kicad_mod")
    a = read_footprint(folder / "Mini_R_0603.kicad_mod", library="Mini")
    b = read_footprint(folder / "Mini_R_0603_B.kicad_mod", library="Mini")
    assert not {p.id for p in a.pads} & {p.id for p in b.pads}
    assert a.pads[0].native_ids == b.pads[0].native_ids


def test_same_file_under_two_nicknames() -> None:
    a, b = read_footprint(R0603, library="A"), read_footprint(R0603, library="B")
    assert a.id != b.id and not {p.id for p in a.pads} & {p.id for p in b.pads}


def test_identical_pads_without_uuid_get_distinct_reproducible_ids() -> None:
    pads = _pads("smd", "smd").replace('(pad "2"', '(pad "1"')
    text = f"{HEADER} {pads})"
    first, second = read_footprint(text), read_footprint(text)
    assert first.pads[0].id != first.pads[1].id
    assert [p.id for p in first.pads] == [p.id for p in second.pads]
    assert first.pads[0].native_ids == {}


def test_locator_and_provenance_of_a_pad() -> None:
    fp = read_footprint(R0603)
    prov = fp.pads[1].provenance
    assert prov is not None and prov.locator == "/footprint/pad[1]" and prov.backend == "kicad"
    assert prov.file == str(R0603) and len(prov.file_sha256) == 64
    graphic = fp.graphics[0].provenance
    assert graphic is not None and graphic.locator.startswith("/footprint/fp_")
    assert fp.pads[0].native_ids["kicad"].startswith("a1000000-")


def test_text_input_hashes_its_text() -> None:
    import hashlib

    text = HEADER + ")"
    fp = read_footprint(text)
    assert (
        fp.provenance is not None and fp.provenance.file_sha256 == hashlib.sha256(text.encode()).hexdigest()
    )


def test_uuid_repeated_inside_one_definition() -> None:
    uuid = "c0000000-0000-4000-8000-000000000001"
    line = f'(fp_line (start 0 0) (end 1 0) (stroke (width 0.1)) (layer "F.SilkS") (uuid "{uuid}"))'
    first = read_footprint(f"{HEADER} {line} {line} {line})")
    ids = [g.id for g in first.graphics]
    assert len(set(ids)) == 3 and ids[0] == derived_id(
        "gfx", "kicad", "X:c0000000-0000-4000-8000-000000000001"
    )
    assert ids[2] == derived_id("gfx", "kicad", "X:c0000000-0000-4000-8000-000000000001:2")
    assert [g.id for g in read_footprint(f"{HEADER} {line} {line} {line})").graphics] == ids
    assert {g.native_ids["kicad"] for g in first.graphics} == {uuid}
