# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Review sheets frame asymmetric origins correctly and reproduce all 100 patterns."""

import runpy
from pathlib import Path
from xml.etree import ElementTree

import pytest

from fenolite.catalog import list_entries

render = runpy.run_path("tools/catalog/render_footprints.py")["render"]


@pytest.mark.parametrize("name", ["MicroUSB_B_Wurth_629105150521", "JST_XH_B2B_XH_A"])
def test_asymmetric_footprint_courtyard_is_centered(name: str) -> None:
    root = ElementTree.fromstring(render((name,)))
    court = next(e for e in root if e.tag.endswith("rect") and e.get("stroke") == "#16a34a")
    assert float(court.attrib["x"]) + float(court.attrib["width"]) / 2 == pytest.approx(225, abs=0.01)
    assert float(court.attrib["y"]) + float(court.attrib["height"]) / 2 == pytest.approx(145, abs=0.01)


def test_full_gallery_and_five_review_pages_reproduce_catalog_geometry() -> None:
    names = tuple(e.lib_id.removeprefix("Fenolite:") for e in list_entries(kind="footprint"))
    assert len(names) == 100
    folder = Path("docs/catalog/previews")
    assert (folder / "c0076-current-gallery.svg").read_text(encoding="utf-8") == render(names)
    for index in range(5):
        page_names = names[index * 20 : (index + 1) * 20]
        text = (folder / f"c0076-current-gallery-page{index + 1}.svg").read_text(encoding="utf-8")
        assert text == render(page_names)
        root = ElementTree.fromstring(text)
        titles = [e.text for e in root if e.tag.endswith("text") and e.get("fill") == "#0f172a"]
        assert titles == list(page_names)
