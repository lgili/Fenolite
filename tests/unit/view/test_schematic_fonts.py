# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 native text controls for honest scene effects and refusals (c0326)."""

from __future__ import annotations

import pytest

from fenolite.core.errors import FormatError
from fenolite.view.fidelity import compare_scenes, shapes_of
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
@pytest.mark.parametrize("effect", ('(face "Authored Sans")',))
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


@pytest.mark.parametrize("surface", SURFACES)
def test_explicit_thickness_changes_stroke_and_comparison_envelope(surface: str) -> None:
    baseline = scene(native(surface, "(font (size 1.27 1.27))"))
    changed = scene(native(surface, "(font (size 1.27 1.27) (thickness 0.8))"))
    assert probe(changed)["th"] == 800
    # Isolate the visible text: a filled label body can legitimately cover its box mask.
    baseline = {**baseline, "prims": [probe(baseline)]}
    changed = {**changed, "prims": [probe(changed)]}
    found = compare_scenes({"sheet:authored.kicad_sch": baseline}, {"sheet:authored.kicad_sch": changed})
    assert found.findings and {finding.kind for finding in found.findings} == {"render-pixels"}
    assert found.summary["pixel_ppm"] == 1_000


@pytest.mark.parametrize("nm", (1, 499, 500))
def test_unrepresentable_explicit_thickness_refuses(nm: int) -> None:
    with pytest.raises(FormatError, match="micrometre"):
        scene(native("field", f"(font (size 1.27 1.27) (thickness 0.{nm:06d}))"))


def test_explicit_thickness_uses_existing_half_even_scene_grid() -> None:
    assert probe(scene(native("field", "(font (size 1.27 1.27) (thickness 0.0015))")))["th"] == 2
    assert probe(scene(native("field", "(font (size 1.27 1.27) (thickness 0.0025))")))["th"] == 2


@pytest.mark.parametrize("surface", SURFACES)
def test_bold_selects_heavier_authored_stroke(surface: str) -> None:
    normal = probe(scene(native(surface, "(font (size 1.27 1.27))")))
    bold = probe(scene(native(surface, "(font (size 1.27 1.27) bold)")))
    assert normal["th"] < bold["th"] == 254
    explicit = probe(scene(native(surface, "(font (size 1.27 1.27) bold (thickness 0.1))")))
    assert explicit["th"] == 100


@pytest.mark.parametrize("surface", SURFACES)
def test_italic_selects_authored_shear_and_changes_text_mask(surface: str) -> None:
    normal = scene(native(surface, "(font (size 2.54 2.54))"))
    italic = scene(native(surface, "(font (size 2.54 2.54) italic)"))
    assert italic["fonts"][probe(italic)["font"]]["italic"] is True
    normal = {**normal, "prims": [probe(normal)]}
    italic = {**italic, "prims": [probe(italic)]}
    found = compare_scenes({"sheet:authored.kicad_sch": normal}, {"sheet:authored.kicad_sch": italic})
    assert found.findings and {finding.kind for finding in found.findings} == {"render-pixels"}
    assert all(finding.where.startswith("sheet:authored.kicad_sch:") for finding in found.findings)


@pytest.mark.parametrize("effect", ("bold", "italic", "(thickness 0.1)"))
@pytest.mark.parametrize("rot", range(4))
def test_style_changes_exact_mask_geometry_without_changing_pixel_tolerance(effect: str, rot: int) -> None:
    normal = scene(native("free", "(font (size 1.27 1.27))"))
    changed = scene(native("free", f"(font (size 1.27 1.27) {effect})"))
    probe(normal)["rot"] = probe(changed)["rot"] = rot
    assert shapes_of(normal, 127_000) != shapes_of(changed, 127_000)


def test_thin_asymmetric_text_mask_remains_nonempty() -> None:
    value = scene(native("free", "(font (size 1.27 0.001) (thickness 0.001))"))
    shapes = shapes_of({**value, "prims": [probe(value)]}, 127_000)
    assert shapes
    for shape in next(iter(shapes.values())):
        xs = [point.x for ring in shape.rings for point in ring]
        ys = [point.y for ring in shape.rings for point in ring]
        assert max(xs) > min(xs) and max(ys) > min(ys)


@pytest.mark.parametrize(
    "color,expected",
    (
        ("194 0 0 1", "#c20000"),
        ("128 128 128 1", "#808080"),
        ("194 0 0 0.5", "#c20000"),
        ("194 0 0 0", "#c20000"),
    ),
)
def test_opaque_free_text_displays_validated_native_effective_color(color: str, expected: str) -> None:
    source = native("free", f"(font (size 1.27 1.27) (color {color}))")
    assert probe(scene(source))["c"] == expected


def test_free_text_zero_rgba_sentinel_retains_exact_default_scene() -> None:
    assert scene(native("free", "(font (size 1.27 1.27) (color 0 0 0 0))")) == scene(
        native("free", "(font (size 1.27 1.27))")
    )


@pytest.mark.parametrize("surface", tuple(surface for surface in SURFACES if surface != "free"))
def test_typed_font_color_stays_refused(surface: str) -> None:
    with pytest.raises(FormatError, match="font attribute 'color'"):
        scene(native(surface, "(font (size 1.27 1.27) (color 194 0 0 1))"))


@pytest.mark.parametrize(
    "color",
    (
        "",
        "194 0 0",
        "194 0 0 1 2",
        "-1 0 0 1",
        "256 0 0 1",
        "0 1.5 0 1",
        "0 0 0 -0.1",
        "0 0 0 1.1",
        '"194" 0 0 1',
        "(red 194) 0 0 1",
    ),
)
def test_malformed_free_text_color_refuses_with_locator(color: str) -> None:
    with pytest.raises(FormatError) as caught:
        scene(native("free", f"(font (size 1.27 1.27) (color {color}))"))
    assert caught.value.file == "authored-font-probe.kicad_sch" and "font" in caught.value.locator


def test_duplicate_free_text_color_refuses() -> None:
    with pytest.raises(FormatError):
        scene(native("free", "(font (size 1.27 1.27) (color 194 0 0 1) (color 0 0 0 0))"))
