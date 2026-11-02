# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 native text controls for honest scene effects and refusals (c0326)."""

from __future__ import annotations

import pytest

from fenolite.core.errors import FormatError
from fenolite.view.fidelity import compare_scenes
from fenolite.view.kicad_schematic import build_kicad_schematic_scene
from fenolite.view.themes import palette

SURFACES = ("field", "power", "local", "global", "hierarchical", "pin", "sheetname", "sheetfile", "free")


def native(surface: str, font: str, *, justify: str | None = "left", hidden: bool = False) -> str:
    """Original inline CC0 schematic geometry; no copied CAD, native save or font resource."""
    align = f"(justify {justify})" if justify is not None else ""
    effects = f"(effects {font} {align} {'hide' if hidden else ''})"
    if surface in {"field", "power"}:
        key = "Reference" if surface == "field" else "Value"
        definition = '(lib_symbols (symbol "Authored:Probe" (power)))' if surface == "power" else ""
        item = (
            f'{definition} (symbol (lib_id "Authored:Probe") (at 40 40 0) (unit 1) '
            f'(property "{key}" "FontProbe" (at 40 40 0) {effects}))'
        )
    elif surface in {"local", "global", "hierarchical"}:
        head = "label" if surface == "local" else surface + "_label"
        shape = "" if surface == "local" else "(shape input)"
        item = f'({head} "FontProbe" {shape} (at 40 40 0) {effects})'
    elif surface in {"pin", "sheetname", "sheetfile"}:
        if surface == "pin":
            item = f'(pin "FontProbe" input (at 30 40 180) {effects})'
        else:
            key = "Sheetname" if surface == "sheetname" else "Sheetfile"
            item = f'(property "{key}" "FontProbe" (at 30 29 0) {effects})'
        item = f"(sheet (at 30 30) (size 20 20) {item})"
    else:
        item = f'(text "FontProbe" (at 40 40 0) {effects})'
    return f'(kicad_sch (version 20250114) (generator "fenolite_authored_font_probe") (paper "A4") {item})'


def scene(text: str):
    return build_kicad_schematic_scene(text, name="authored-font-probe.kicad_sch", palette=palette("kicad"))


def probe(value):
    return next(prim for prim in value["prims"] if prim["k"] == "t" and prim["s"].endswith("FontProbe"))


@pytest.mark.parametrize("surface", SURFACES)
def test_native_height_width_are_independent_scene_axes(surface: str) -> None:
    first = probe(scene(native(surface, "(font (size 0.5 1))")))
    second = probe(scene(native(surface, "(font (size 1 0.5))")))
    assert (first["sz"], first["gw"]) == (500, 620)
    assert (second["sz"], second["gw"]) == (1000, 310)


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("nm", (1, 499, 500))
def test_positive_submicrometre_text_never_becomes_default_size(surface: str, nm: int) -> None:
    font = f"(font (size 0.{nm:06d} 1.27))"
    with pytest.raises(FormatError, match="sub-micrometre") as caught:
        scene(native(surface, font))
    assert "font" in caught.value.locator


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("effect", ("bold", "italic", '(face "Authored Sans")', "(thickness 0.1)"))
def test_unrepresentable_visible_style_refuses_instead_of_default_ink(surface: str, effect: str) -> None:
    with pytest.raises(FormatError, match="unsupported schematic rendering") as caught:
        scene(native(surface, f"(font (size 1.27 1.27) {effect})"))
    assert caught.value.file == "authored-font-probe.kicad_sch" and caught.value.locator


@pytest.mark.parametrize("surface", SURFACES)
def test_native_false_zero_and_absent_styles_keep_the_same_default_scene(surface: str) -> None:
    first = scene(native(surface, "(font (size 1.27 1.27))"))
    second = scene(native(surface, "(font (size 1.27 1.27) (bold no) (italic no) (thickness 0))"))
    assert first == second


@pytest.mark.parametrize("surface", ("local", "global", "hierarchical", "pin"))
def test_missing_and_empty_native_justification_centre_text(surface: str) -> None:
    missing = probe(scene(native(surface, "(font (size 1.27 1.27))", justify=None)))
    empty = probe(scene(native(surface, "(font (size 1.27 1.27))", justify="")))
    left = probe(scene(native(surface, "(font (size 1.27 1.27))", justify="left")))
    right = probe(scene(native(surface, "(font (size 1.27 1.27))", justify="right")))
    assert missing == empty and missing["h"] == "center"
    assert left["h"] == "left" and right["h"] == "right"


def test_hidden_field_can_retain_unrendered_style_without_visible_ink() -> None:
    value = scene(native("field", '(font (size 1.27 1.27) (face "Authored Sans") bold italic)', hidden=True))
    assert not any(prim["k"] == "t" and prim["s"] == "FontProbe" for prim in value["prims"])


def test_mirrored_text_has_an_explicit_renderer_refusal() -> None:
    with pytest.raises(FormatError, match="unsupported schematic rendering"):
        scene(native("field", "(font (size 1.27 1.27))", justify="mirror"))


@pytest.mark.parametrize("surface", SURFACES)
def test_one_micrometre_axis_keeps_its_small_size(surface: str) -> None:
    value = probe(scene(native(surface, "(font (size 0.001 1.27))")))
    assert value["sz"] == 1 and value["gw"] == 787


@pytest.mark.parametrize("font", ("(font (size 1.27 0.5))", "(font (size 0.5 1.27))"))
def test_changed_single_axis_remains_a_level_8_mask_difference(font: str) -> None:
    a = scene(native("field", "(font (size 0.5 0.5))"))
    b = scene(native("field", font))
    found = compare_scenes({"sheet:authored.kicad_sch": a}, {"sheet:authored.kicad_sch": b})
    assert found.findings and {finding.kind for finding in found.findings} == {"render-pixels"}
    assert found.summary["pixel_ppm"] == 1_000
