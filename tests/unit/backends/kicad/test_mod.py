# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint reading: inputs, names, root mapping, slots and version policy (kicad-library-read)."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import pytest
from _libs import MINI

from fenolite.backends.kicad import slots
from fenolite.backends.kicad.mod import EVIDENCE, read_footprint
from fenolite.backends.kicad.sexpr import Node, parse_fragment
from fenolite.backends.kicad.versions import UnsupportedFormatError
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Level
from fenolite.model.base import Modeled, Opaque, Slot
from fenolite.model.board import Pad
from fenolite.model.canonical import dumps, loads
from fenolite.model.library import FootprintDef, Library

R0603 = MINI / "Mini.pretty" / "Mini_R_0603.kicad_mod"
HEADER = '(footprint "X" (version 20260206) (generator "t") (layer "F.Cu")'


def _slots(fp: FootprintDef) -> tuple[Slot, ...]:
    return slots.from_ext(fp.ext["kicad"])


def test_mini_resistor_from_a_path() -> None:
    fp = read_footprint(R0603)
    assert (fp.name, fp.library, fp.lib_id, fp.kind) == ("Mini_R_0603", "Mini", "Mini:Mini_R_0603", "smd")
    assert [(p.number, p.shape) for p in fp.pads] == [("1", "roundrect"), ("2", "roundrect")]
    assert fp.description.startswith("Mini 0603 resistor") and fp.keywords == ("resistor", "mini")
    assert fp.models == ("${KICAD10_3DMODEL_DIR}/Mini.3dshapes/Mini_R_0603.step",)
    assert list(fp.properties) == ["Reference", "Value", "Datasheet", "Description"]
    assert fp.reference == "REF**" and fp.value == "Mini_R_0603"
    assert fp.provenance is not None and fp.provenance.locator == "/footprint"
    assert fp.provenance.evidence == EVIDENCE and EVIDENCE.level is Level.INFERRED
    assert EVIDENCE.hypotheses == ("H-K-LIB-READ",)


def test_header_name_differs_from_the_stem(tmp_path: Path) -> None:
    other = tmp_path / "Other.kicad_mod"
    shutil.copyfile(R0603, other)
    issues: list[Issue] = []
    fp = read_footprint(other, issues=issues)
    assert fp.name == "Other" and fp.library == "" and fp.lib_id == "Other"
    assert [(i.code, i.severity) for i in issues] == [("kicad.lib.name-mismatch", "warning")]
    assert "Other" in issues[0].message and "Mini_R_0603" in issues[0].message


def test_text_input_uses_the_header_name_and_no_library() -> None:
    fp = read_footprint(HEADER + ")")
    assert (fp.name, fp.library, fp.lib_id, fp.pads, fp.graphics) == ("X", "", "X", (), ())


def test_node_input_and_explicit_library() -> None:
    node = parse_fragment(HEADER + ")")
    assert isinstance(node, Node)
    fp = read_footprint(node, library="L")
    assert fp.lib_id == "L:X" and fp.native_ids == {"kicad": "L:X"}


def test_folder_default_needs_a_pretty_parent(tmp_path: Path) -> None:
    plain = tmp_path / "Mini_R_0603.kicad_mod"
    shutil.copyfile(R0603, plain)
    assert read_footprint(plain).library == ""
    assert read_footprint(plain, library="Mine").lib_id == "Mine:Mini_R_0603"


def test_attribute_without_a_type() -> None:
    fp = read_footprint(HEADER + " (attr exclude_from_pos_files exclude_from_bom))")
    assert fp.kind == "unspecified" and fp.flags == ("exclude_from_pos_files", "exclude_from_bom")
    assert read_footprint(HEADER + " (attr through_hole dnp))").kind == "through_hole"
    assert read_footprint(HEADER + ")").kind == "unspecified"


def test_unknown_child_survives_in_place() -> None:
    fp = read_footprint('(footprint "X" (version 20260206) (frobnicate 1) (layer "F.Cu"))')
    found = _slots(fp)
    assert found[0] == Modeled("name")
    assert found[2] == Opaque("(frobnicate 1)", "20260206")


def test_property_is_projected_not_modelled() -> None:
    prop = '(property "Reference" "REF**" (at 0 -1.5 0) (layer "F.SilkS") (effects (font (size 1 1))))'
    fp = read_footprint(f"{HEADER} {prop})")
    assert fp.properties == {"Reference": "REF**"}
    opaque = _slots(fp)[4]
    assert (
        isinstance(opaque, Opaque)
        and "effects" in opaque.fragment
        and opaque.fragment.startswith("(property")
    )


def test_tags_descr_and_model_slots() -> None:
    fp = read_footprint(f'{HEADER} (descr "d") (tags "a  b") (model "${{X}}/m.step" (offset (xyz 0 0 0))))')
    kinds = [type(s).__name__ for s in _slots(fp)]
    assert kinds[4:] == ["Modeled", "Opaque", "Opaque"]
    assert fp.description == "d" and fp.keywords == ("a", "b") and fp.models == ("${X}/m.step",)
    assert '"a  b"' in _slots(fp)[5].fragment  # type: ignore[union-attr]


def test_pads_are_board_pads_without_nets() -> None:
    for path in sorted((MINI / "Mini.pretty").glob("*.kicad_mod")):
        for pad in read_footprint(path).pads:
            assert type(pad) is Pad and pad.net_id is None


def test_9_and_10_variants_read_alike() -> None:
    def strip(fp: FootprintDef) -> tuple[object, ...]:
        def clean(entity: object) -> object:
            return dataclasses.replace(entity, id="x", provenance=None, ext={})  # type: ignore[type-var]

        return tuple(clean(p) for p in fp.pads), tuple(clean(g) for g in fp.graphics)

    v9 = read_footprint(MINI / "Mini_v9.pretty" / "Mini_R_0603.kicad_mod", library="Mini")
    v10 = read_footprint(R0603, library="Mini")
    assert strip(v9) == strip(v10)


def test_kicad_7_footprint_refused() -> None:
    with pytest.raises(UnsupportedFormatError) as caught:
        read_footprint('(footprint "X" (version 20221018) (generator "t") (layer "F.Cu"))')
    assert "kicad-cli fp upgrade" in caught.value.hint


def test_pre_6_module_head() -> None:
    with pytest.raises(UnsupportedFormatError) as caught:
        read_footprint("(module R_0603 (layer F.Cu))")
    assert "module" in str(caught.value) and "not supported" in str(caught.value)
    assert "kicad-cli fp upgrade" in caught.value.hint


def test_other_root_refused() -> None:
    with pytest.raises(FormatError, match="footprint") as caught:
        read_footprint('(kicad_symbol_lib (version 20251024) (generator "t"))')
    assert caught.value.locator == "/kicad_symbol_lib"


def test_future_version_read_with_a_warning() -> None:
    text = R0603.read_text(encoding="utf-8").replace("(version 20260206)", "(version 20990101)", 1)
    issues: list[Issue] = []
    fp = read_footprint(text, issues=issues)
    assert [(i.code, i.severity) for i in issues] == [("kicad.version.future", "warning")]
    groups = [fp.ext["kicad"], *(p.ext["kicad"] for p in fp.pads), *(g.ext["kicad"] for g in fp.graphics)]
    opaque = [s for bag in groups for s in slots.from_ext(bag) if isinstance(s, Opaque)]
    assert opaque and {s.min_version for s in opaque} == {"20990101"}


def test_development_version_adds_an_info() -> None:
    issues: list[Issue] = []
    read_footprint('(footprint "X" (version 20250513) (generator "t") (layer "F.Cu"))', issues=issues)
    assert [(i.code, i.severity) for i in issues] == [("kicad.version.dev", "info")]


def test_opaque_minimum_version_rule() -> None:
    issues: list[Issue] = []
    fp = read_footprint(MINI / "Mini.pretty" / "Mini_Edge_Cases.kicad_mod", issues=issues)
    padstack_pad = next(p for p in fp.pads if p.padstack is not None)
    fragments = [s for s in slots.from_ext(padstack_pad.ext["kicad"]) if isinstance(s, Opaque)]
    padstack = next(s for s in fragments if s.fragment.startswith("(padstack"))
    assert padstack.min_version is not None and 20240929 <= int(padstack.min_version) < 20260206
    remove = next(s for s in fragments if s.fragment.startswith("(remove_unused_layers"))
    assert remove.min_version == "20260206"


def test_library_canonical_idempotence() -> None:
    lib = Library(
        "Mini",
        footprints=tuple(read_footprint(p) for p in sorted((MINI / "Mini.pretty").glob("*.kicad_mod"))),
    )
    text = dumps(lib)
    assert dumps(loads(text, Library)) == text
