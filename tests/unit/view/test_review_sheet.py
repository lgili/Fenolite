# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Review pages reuse standalone library scenes and escape authored metadata (c0262)."""

from dataclasses import replace

from fenolite.core.coords import Point
from fenolite.model.library import SymbolDef, SymbolPin, SymbolUnit
from fenolite.view import export
from fenolite.view.export import embedded
from fenolite.view.review_sheet import content_digest, review_sheet


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


def _demo_symbol(name="A"):
    return SymbolDef(
        id="s", name="Demo", units=(SymbolUnit(1, 1),), pins=(SymbolPin("1", name, "passive", Point(0, 0)),)
    )


def test_content_digest_ignores_the_viewer_and_binds_what_is_shown(monkeypatch):
    """c0415: a viewer change keeps the content digest; any change of shown content changes it."""
    kwargs = {"metadata": {"Pin table": [{"number": "1"}]}, "findings": [], "symbol": _demo_symbol()}
    sheet = review_sheet("Rules:Demo", **kwargs)
    packaged = export.template()
    viewer_2 = packaged.replace("</head>", "<!-- viewer 2 --></head>", 1)
    monkeypatch.setattr(export, "template", lambda: viewer_2)
    other_viewer = review_sheet("Rules:Demo", **kwargs)
    assert other_viewer != sheet
    assert content_digest(other_viewer) == content_digest(sheet)
    for changed in (
        {**kwargs, "metadata": {"Pin table": [{"number": "2"}]}},
        {**kwargs, "findings": [{"code": "library.pin-order"}]},
        {**kwargs, "symbol": _demo_symbol("B")},
    ):
        assert content_digest(review_sheet("Rules:Demo", **changed)) != content_digest(sheet)
    assert content_digest(review_sheet("Rules:Other", **kwargs)) != content_digest(sheet)


def test_content_digest_of_a_comparison_sheet_ignores_the_iframe_page_copy(monkeypatch):
    kwargs = {"metadata": {}, "findings": [], "symbol": _demo_symbol(), "old_symbol": _demo_symbol("OLD")}
    sheet = review_sheet("Rules:Demo", **kwargs)
    assert b"srcdoc=" in sheet
    packaged = export.template()
    viewer_2 = packaged.replace("</head>", "<!-- viewer 2 --></head>", 1)
    monkeypatch.setattr(export, "template", lambda: viewer_2)
    assert content_digest(review_sheet("Rules:Demo", **kwargs)) == content_digest(sheet)
