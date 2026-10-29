# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Installed catalog drawings are selectable and inspectable in the real browser (c0234)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _visual import _cli, browser_missing, job, run

pytestmark = pytest.mark.needs_browser


@pytest.fixture
def catalog_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if reason := browser_missing():
        pytest.skip(reason)
    monkeypatch.chdir(tmp_path)
    args = ("catalog", "view", "--out", "catalog.html", "--json")
    plan = _cli(*args, "--dry-run")["result"]["plan_id"]
    _cli(*args, "--confirm", "--plan", plan)
    return tmp_path / "catalog.html"


def test_catalog_symbols_and_footprints_are_inspectable(catalog_page: Path, tmp_path: Path) -> None:
    script = """
    const docs = PROJECT.groups.flatMap(g => g.documents);
    await openDoc(docs.find(d => d.kind === "schematic-library"));
    const symbolCount = LIB.items.length;
    const resistor = LIB.items.findIndex(it => it.name === "Fenolite:Resistor");
    openItem(resistor);
    const details = $("info").querySelector("details");
    const initiallyCollapsed = !details.open;
    details.querySelector("summary").click();
    const expanded = details.open;
    const symbol = {name: $("fname").textContent, info: $("info").textContent,
      pins: S.meta.counts.pins, kind: S.kind};
    details.querySelector("summary").click();
    const collapsed = !details.open;
    await openDoc(docs.find(d => d.kind === "pcb-library"));
    const footprintCount = LIB.items.length;
    $("libFilter").value = "CHIP_0603";
    $("libFilter").dispatchEvent(new Event("input", {bubbles: true}));
    const matches = [...$("libList").children].map(e => e.textContent);
    $("libList").firstElementChild.click();
    const footprint = {name: $("fname").textContent, info: $("info").textContent,
      pads: S.pads.length};
    const p = S.pads[0], r = cv.getBoundingClientRect(), [x, y] = w2s(p.x, p.y);
    for (const type of ["mousedown", "mouseup"]) cv.dispatchEvent(new MouseEvent(type,
      {clientX: r.left + x, clientY: r.top + y, bubbles: true, view: window}));
    const padInfo = $("info").textContent;
    $("libFilter").value = "no-such-catalog-entry";
    $("libFilter").dispatchEvent(new Event("input", {bubbles: true}));
    return {symbolCount, footprintCount, symbol, footprint, matches, padInfo,
      initiallyCollapsed, expanded, collapsed,
      noMatches: $("libList").children.length};
    """
    (reply,) = run([job("catalog", catalog_page, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["initiallyCollapsed"] and result["expanded"] and result["collapsed"]
    assert result["symbolCount"] == 49 and result["footprintCount"] == 100
    assert result["symbol"]["kind"] == "schematic" and result["symbol"]["pins"] == 2
    assert "Fenolite:Resistor" in result["symbol"]["name"]
    assert "INFERRED" in result["symbol"]["info"] and "S-0314" in result["symbol"]["info"]
    assert len(result["matches"]) == 1 and "Fenolite:Chip_0603" in result["matches"][0]
    assert result["footprint"]["pads"] == 2
    assert "Fenolite:Chip_0603" in result["footprint"]["info"]
    assert "Pad" in result["padInfo"] and "Size" in result["padInfo"]
    assert result["noMatches"] == 0


@pytest.mark.parametrize("width", (390, 1100))
def test_catalog_sidebar_remains_usable(catalog_page: Path, tmp_path: Path, width: int) -> None:
    script = """
    const narrow = matchMedia("(max-width:760px)").matches;
    if (narrow) $("bSidebar").click();
    const visible = getComputedStyle($("side")).display;
    $("libFilter").value = "resistor";
    $("libFilter").dispatchEvent(new Event("input", {bubbles: true}));
    const matches = $("libList").children.length;
    $("libList").firstElementChild.click();
    if (narrow) $("bSidebar").click();
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    return {visible, matches, name: $("fname").textContent,
      canvas: $("wrap").getBoundingClientRect().width,
      overflow: $("top").scrollWidth > $("top").clientWidth};
    """
    (reply,) = run(
        [job("catalog-width", catalog_page, tmp_path, script=script, shot="", width=width)], tmp_path
    )
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["visible"] == "flex" and result["matches"] >= 1
    assert "Resistor" in result["name"]
    assert result["canvas"] == (width if width <= 760 else width - 260)
    assert result["overflow"] is False
