# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native review sheets are reproducible from catalog geometry and terminal roles."""

import runpy
from pathlib import Path
from xml.etree import ElementTree

from fenolite.catalog import get_symbol, list_entries

render = runpy.run_path("tools/catalog/render_symbols.py")["render"]


def _titles(text: str) -> list[str]:
    root = ElementTree.fromstring(text)
    return [
        element.text for element in root if element.tag.endswith("text") and element.get("fill") == "#0f172a"
    ]


def test_new_20_and_complete_49_gallery_reproduce_definitions() -> None:
    names = tuple(e.lib_id.removeprefix("Fenolite:") for e in list_entries(kind="symbol"))
    assert len(names) == 49
    folder = Path("docs/catalog/previews")
    text = (folder / "c0076-all-49-symbols.svg").read_text(encoding="utf-8")
    assert text == render(names) and _titles(text) == list(names)
    for index in range(3):
        subset = names[index * 20 : (index + 1) * 20]
        text = (folder / f"c0076-all-49-symbols-page{index + 1}.svg").read_text(encoding="utf-8")
        assert text == render(subset) and _titles(text) == list(subset)
    inventory = Path("docs/catalog/target-20-symbols.md").read_text(encoding="utf-8")
    new_names = tuple(
        line.split("`")[1]
        for line in inventory.splitlines()
        if line.startswith("| ") and line.split("|")[1].strip().isdigit()
    )
    assert len(new_names) == 20
    assert (folder / "c0076-new-20-symbols.svg").read_text(encoding="utf-8") == render(new_names)
    for index in range(2):
        subset = new_names[index * 10 : (index + 1) * 10]
        text = (folder / f"c0076-new-20-symbols-page{index + 1}.svg").read_text(encoding="utf-8")
        assert text == render(subset) and _titles(text) == list(subset)


def test_arrow_background_fill_and_thick_phase_circles_match_model() -> None:
    root = ElementTree.fromstring(render(("MOSFET_N_Channel", "Transformer")))
    polygons = [e for e in root if e.tag.endswith("polygon")]
    assert len(polygons) == 2
    assert all(p.get("fill") == "white" for p in polygons)
    circles = [e for e in root if e.tag.endswith("circle")]
    assert len(circles) == 2 and all(c.get("fill") == "none" for c in circles)
    assert all(float(c.attrib["stroke-width"]) == 2 * float(c.attrib["r"]) for c in circles)
    for name in ("MOSFET_N_Channel", "Transformer"):
        symbol = get_symbol(f"Fenolite:{name}")
        assert " · ".join(f"{p.number}={p.name}" for p in symbol.pins) in render((name,))


def test_relay_bottom_pins_are_labelled_on_opposite_sides_of_their_stems() -> None:
    """The relay hides its pin names (change c0134), so a stem carries its number alone; the roles stay
    in the line under the card."""
    text = render(("Relay_SPDT",))
    root = ElementTree.fromstring(text)
    labels = {e.text: e for e in root if e.tag.endswith("text")}
    assert labels["2"].get("text-anchor") == "end"
    assert labels["3"].get("text-anchor") == "start"
    assert "1=COIL1 · 2=COIL2 · 3=COM · 4=NC · 5=NO" in text


def test_functional_ic_roles_are_kept_outside_the_body_outline() -> None:
    root = ElementTree.fromstring(render(("Microcontroller",)))
    body = next(e for e in root if e.tag.endswith("rect") and e.get("stroke") == "#182a40")
    left, right = float(body.attrib["x"]), float(body.attrib["x"]) + float(body.attrib["width"])
    labels = {e.text: e for e in root if e.tag.endswith("text")}
    assert labels["1 VDD"].get("text-anchor") == "end"
    assert float(labels["1 VDD"].attrib["x"]) < left
    assert labels["5 IO2"].get("text-anchor") == "start"
    assert float(labels["5 IO2"].attrib["x"]) > right
