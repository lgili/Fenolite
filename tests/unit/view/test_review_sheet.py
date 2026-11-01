# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Review pages reuse standalone library scenes and escape authored metadata (c0262)."""

from dataclasses import replace

from fenolite.core.coords import Point
from fenolite.model.library import SymbolDef, SymbolPin, SymbolUnit
from fenolite.view.export import embedded
from fenolite.view.review_sheet import review_sheet


def test_sheets_are_standalone_deterministic_escaped_and_show_units():
    symbol = SymbolDef(
        id="s",
        name="Demo",
        units=(SymbolUnit(1, 1), SymbolUnit(2, 1)),
        pins=(
            SymbolPin("1", "A", "passive", Point(0, 0), unit=1),
            SymbolPin("2", "B", "passive", Point(0, 0), unit=2),
        ),
    )
    kwargs = {
        "metadata": {
            "Dimensions and sources": {
                "width": "2mm",
                "source": "S-0988",
                "note": "</pre><script>bad()</script>",
            }
        },
        "findings": [],
        "symbol": symbol,
    }
    data = review_sheet("Rules:Demo", **kwargs)
    assert data == review_sheet("Rules:Demo", **kwargs)
    assert b"S-0988" in data and b"&lt;script&gt;bad()&lt;/script&gt;" in data
    assert b"<script>bad()</script>" not in data
    scenes = embedded(data.decode())
    assert scenes is not None
    items = scenes["scenes"]["catalog-symbol"]["items"]
    assert len(items) == 2
    assert [["Unit", str(i + 1)] in item["info"] for i, item in enumerate(items)] == [True, True]
    assert all(len([obj for obj in item["scene"]["objects"] if obj["k"] == "pin"]) == 1 for item in items)
    assert b"Review state" in data
    changed = review_sheet(
        "Rules:Demo",
        **{
            **kwargs,
            "old_symbol": replace(symbol, pins=(replace(symbol.pins[0], name="OLD"), symbol.pins[1])),
        },
    )
    assert b"review-diff-0" in changed and b"srcdoc=" in changed
