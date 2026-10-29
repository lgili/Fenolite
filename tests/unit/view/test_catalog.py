# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The installed catalog uses real symbol and pad scenes, without CAD files (c0234)."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import replace
from fractions import Fraction

import pytest

from fenolite.backends.kicad.sym import write_symbol_library
from fenolite.catalog import ENTRIES, CatalogEntry, get_footprint, get_symbol, list_entries
from fenolite.core.coords import Point, Size
from fenolite.model.board import Pad
from fenolite.model.library import FootprintDef, SymbolDef, SymbolGraphic, SymbolPin
from fenolite.view.catalog import CatalogItem, catalog_page
from fenolite.view.export import embedded


def _resolved(entries: Sequence[CatalogEntry]) -> tuple[CatalogItem, ...]:
    return tuple(
        CatalogItem(
            lib_id=entry.lib_id,
            category=entry.category,
            summary=entry.summary,
            evidence=entry.evidence,
            sources=entry.sources,
            definition=get_symbol(entry.lib_id) if entry.kind == "symbol" else get_footprint(entry.lib_id),
        )
        for entry in entries
    )


def test_complete_catalog_geometry_and_metadata() -> None:
    data = embedded(catalog_page(_resolved(ENTRIES)))
    assert data is not None
    assert list(data["scenes"]) == ["catalog-symbol", "catalog-footprint"]
    found = {item["lib_id"]: item for scene in data["scenes"].values() for item in scene["items"]}
    assert set(found) == {entry.lib_id for entry in ENTRIES}
    for entry in ENTRIES:
        item = found[entry.lib_id]
        assert item["name"] == entry.lib_id
        assert (item["category"], item["summary"], item["sources"], item["evidence"]) == (
            entry.category,
            entry.summary,
            list(entry.sources),
            entry.evidence,
        )
        assert ["Library ID", entry.lib_id] in item["info"]
        scene = item["scene"]
        assert scene["meta"]["evidence"] == "INFERRED"
        if entry.kind == "symbol":
            symbol = get_symbol(entry.lib_id)
            assert item["pins"] == len(symbol.pins)
            assert len([obj for obj in scene["objects"] if obj["k"] == "pin"]) == len(symbol.pins)
            for pin in symbol.pins:
                assert [f"Pin {pin.number}", f"{pin.name} · {pin.etype}"] in item["info"]
            assert item["catalog_selection"]["pins"] == [
                {"number": pin.number, "name": pin.name, "type": pin.etype} for pin in symbol.pins
            ]
        else:
            fp = get_footprint(entry.lib_id)
            assert item["pads"] == len(fp.pads) == len(scene["pads"])
            assert scene["layers"]
            actual = sorted((pad["w"], pad["h"], pad["shape"], pad["drill"]) for pad in scene["pads"])
            expected = sorted((pad.size.w, pad.size.h, pad.shape, pad.drill) for pad in fp.pads)
            assert actual == expected, entry.lib_id
            actual_places = sorted((p["number"], p["x"], p["y"], p["rot"]) for p in scene["pads"])
            expected_places = sorted(
                (
                    pad.number,
                    round(Fraction(pad.position.x, 1000)),
                    round(Fraction(pad.position.y, 1000)),
                    pad.rotation / 1_000_000,
                )
                for pad in fp.pads
            )
            assert actual_places == expected_places, entry.lib_id
            assert item["courtyard_nm"] is not None
            outlines = [layer for layer in scene["layers"] if layer["kind"] in {"fabrication", "courtyard"}]
            assert outlines and all(layer["visible"] for layer in outlines)
            assert not any(row[0] == "Pad numbers" for row in item["info"])
            facts = item["catalog_selection"]
            assert facts["pad_numbers"] == sorted({pad.number for pad in fp.pads if pad.number})
            assert facts["mounting"] == fp.kind and facts["pad_count"] == len(fp.pads)
            assert [(p["width_nm"], p["height_nm"], p["x_nm"], p["y_nm"]) for p in facts["pads"]] == [
                (p.size.w, p.size.h, p.position.x, p.position.y) for p in fp.pads
            ]


@pytest.mark.parametrize("kind,query", [("symbol", "diode"), ("footprint", "0603"), (None, "passive")])
def test_filtered_page_is_deterministic(kind: str | None, query: str) -> None:
    entries = list_entries(kind=kind, query=query)
    items = _resolved(entries)
    html = catalog_page(items)
    assert html == catalog_page(tuple(reversed(items)))
    data = embedded(html)
    assert data is not None
    assert {item["lib_id"] for scene in data["scenes"].values() for item in scene["items"]} == {
        entry.lib_id for entry in entries
    }
    assert all(scene["items"] for scene in data["scenes"].values())


def test_empty_catalog_page_is_explicit() -> None:
    with pytest.raises(ValueError, match="no catalog entries"):
        catalog_page(())


def test_catalog_property_text_does_not_cover_or_resize_geometry() -> None:
    entries = list_entries(kind="symbol", query="Resistor")
    before = write_symbol_library([get_symbol(entry.lib_id) for entry in entries])
    items = _resolved(entries)
    original = embedded(catalog_page(items))
    assert original is not None

    def verbose(item: CatalogItem) -> CatalogItem:
        symbol = item.definition
        assert isinstance(symbol, SymbolDef)
        return replace(
            item,
            definition=replace(
                symbol,
                properties=symbol.properties
                | {
                    "Description": "An intentionally very long metadata description " * 30,
                    "Value": "long value " * 40,
                    "Reference": "long reference " * 40,
                },
            ),
        )

    enlarged = embedded(catalog_page(tuple(verbose(item) for item in items)))
    assert enlarged is not None
    for plain, noisy in zip(
        original["scenes"]["catalog-symbol"]["items"],
        enlarged["scenes"]["catalog-symbol"]["items"],
        strict=True,
    ):
        assert plain["scene"]["bounds"] == noisy["scene"]["bounds"]
        assert plain["scene"]["prims"] == noisy["scene"]["prims"]
        assert any(row[0] == "Reference" for row in noisy["info"])
        assert any(obj["k"] == "pin" for obj in noisy["scene"]["objects"])
    assert write_symbol_library([get_symbol(entry.lib_id) for entry in entries]) == before


def test_viewer_renders_injected_definitions_without_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    symbol = SymbolDef(
        id="sy_00000000-0000-0000-0000-000000000001",
        name="InjectedSymbol",
        library="Test",
        pins=(SymbolPin("P", "INJECTED", "input", Point(-2_000_000, 0), length=1_000_000),),
        graphics=(SymbolGraphic("rect", (Point(-1_000_000, -1_000_000), Point(1_000_000, 1_000_000))),),
    )
    footprint = FootprintDef(
        id="fp_00000000-0000-0000-0000-000000000001",
        name="InjectedFootprint",
        library="Test",
        pads=(
            Pad(
                id="pd_00000000-0000-0000-0000-000000000001",
                number="P",
                shape="rect",
                size=Size(1_300_000, 2_700_000),
                position=Point(0, 0),
                layers=("F.Cu",),
            ),
        ),
    )
    items = tuple(
        CatalogItem(definition.lib_id, "test", "Injected definition", "INFERRED", ("TEST",), definition)
        for definition in (symbol, footprint)
    )
    monkeypatch.setitem(sys.modules, "fenolite.catalog", None)
    data = embedded(catalog_page(items))
    assert data is not None
    symbol_item = data["scenes"]["catalog-symbol"]["items"][0]
    footprint_item = data["scenes"]["catalog-footprint"]["items"][0]
    assert symbol_item["lib_id"] == "Test:InjectedSymbol"
    assert ["Pin P", "INJECTED · input"] in symbol_item["info"]
    assert footprint_item["lib_id"] == "Test:InjectedFootprint"
    assert ["Public source IDs", "TEST"] in footprint_item["info"]
    pad = footprint_item["scene"]["pads"][0]
    assert (pad["number"], pad["w"], pad["h"]) == ("P", 1_300_000, 2_700_000)


def test_selection_spacing_uses_numbered_pad_centres_not_a_guessed_pitch() -> None:
    fp = get_footprint("Fenolite:Chip_0603")
    first = replace(fp.pads[0], position=Point(0, 0))
    second = replace(fp.pads[1], position=Point(3_000_000, 4_000_000))
    mechanical = replace(first, id="pd_00000000-0000-0000-0000-000000000099", number="", position=Point(1, 0))
    custom = replace(fp, pads=(first, second, mechanical))
    item = CatalogItem(custom.lib_id, "test", "Authored centres", "INFERRED", (), custom)
    data = embedded(catalog_page((item,)))
    assert data is not None
    facts = data["scenes"]["catalog-footprint"]["items"][0]["catalog_selection"]
    assert facts["min_center_spacing_nm"] == 5_000_000
    assert facts["pad_count"] == 3 and facts["pad_numbers"] == ["1", "2"]
    assert "not manufacturer pitch" in facts["spacing_basis"]
    item = replace(item, definition=replace(custom, pads=(first, mechanical)))
    data = embedded(catalog_page((item,)))
    assert data is not None
    assert (
        data["scenes"]["catalog-footprint"]["items"][0]["catalog_selection"]["min_center_spacing_nm"] is None
    )
