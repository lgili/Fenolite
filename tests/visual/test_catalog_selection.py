# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Choose exact catalog definitions with explicit geometric filters and pin mapping (c0240)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _visual import _cli, browser_missing, job, run

pytestmark = pytest.mark.needs_browser
OPEN = """
$("bCatalogSelection").click();
for (let i=0; i<200 && CATSEL.loading; i++) await new Promise(r=>setTimeout(r,10));
if (CATSEL.loading) throw new Error("Catalog selection did not load");
const input = (id,value) => { $(id).value=value; $(id).dispatchEvent(new Event("input",{bubbles:true})); };
const choose = (id,value) => { $(id).value=value; $(id).dispatchEvent(new Event("change",{bubbles:true})); };
"""


@pytest.fixture
def selection_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if reason := browser_missing():
        pytest.skip(reason)
    monkeypatch.chdir(tmp_path)
    args = ("catalog", "view", "--out", "catalog.html", "--json")
    plan = _cli(*args, "--dry-run")["result"]["plan_id"]
    _cli(*args, "--confirm", "--plan", plan)
    return tmp_path / "catalog.html"


def test_geometry_filters_and_explicit_selection(selection_page: Path, tmp_path: Path) -> None:
    script = (
        OPEN
        + """
    const all = {symbols:CATSEL.symbols.length,footprints:CATSEL.footprints.length};
    input("catSymbolQuery","resistor"); choose("catSymbol","Fenolite:Resistor");
    input("catFootprintQuery","Chip_0603"); choose("catFootprint","Fenolite:Chip_0603");
    const selected = {symbol:CATSEL.symbol.lib_id,footprint:CATSEL.footprint.lib_id,
      info:$("catFootprintFacts").textContent};
    input("catFootprintQuery","no-such-package");
    const absent = {value:$("catFootprint").value,text:$("catMessage").textContent,
      option:$("catFootprint").selectedOptions[0].textContent};
    input("catFootprintQuery",""); choose("catMounting","smd"); input("catPadCount","2");
    input("catSpacingMin","0.4");input("catSpacingMax","2.5");
    input("catWidthMin","0.1");input("catWidthMax","2");
    const matches = CATSEL.footprints.filter(x=>CATSEL.candidates.includes(x.lib_id))
      .map(x=>x.catalog_selection);
    input("catSpacingMin","3");
    const invalid = {valid:CATSEL.validFilters,text:$("catMessage").textContent,
      count:CATSEL.candidates.length};
    return {all,selected,absent,matches,invalid};
    """
    )
    (reply,) = run([job("catalog-select", selection_page, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["all"] == {"symbols": 49, "footprints": 100}
    assert result["selected"]["symbol"] == "Fenolite:Resistor"
    assert (
        result["selected"]["footprint"] == "Fenolite:Chip_0603" and "INFERRED" in result["selected"]["info"]
    )
    assert result["absent"]["value"] == "Fenolite:Chip_0603"
    assert "outside filters" in result["absent"]["option"] and "no matches" in result["absent"]["text"]
    assert result["matches"]
    for item in result["matches"]:
        assert item["mounting"] == "smd" and len(item["pad_numbers"]) == 2
        assert 400_000 <= item["min_center_spacing_nm"] <= 2_500_000
        assert all(100_000 <= pad["width_nm"] <= 2_000_000 for pad in item["pads"] if pad["number"])
    assert not result["invalid"]["valid"] and result["invalid"]["count"] == 0
    assert "minimum exceeds maximum" in result["invalid"]["text"]


def test_closing_during_loading_does_not_publish_stale_choices(selection_page: Path, tmp_path: Path) -> None:
    script = """
    const original = sceneOf, release = [];
    sceneOf = async d => { await new Promise(r=>release.push(r)); return original(d); };
    const opening = openCatalogSelection(); $("catalogSelection").close();
    release.forEach(r=>r()); await opening; await new Promise(r=>setTimeout(r,20));
    sceneOf = original;
    const closed = !$("catalogSelection").open;
    await openCatalogSelection();
    return {closed,open:$("catalogSelection").open,count:CATSEL.footprints.length};
    """
    (reply,) = run([job("catalog-select-race", selection_page, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    assert reply["result"] == {"closed": True, "open": True, "count": 100}


@pytest.mark.parametrize("width", (390, 1100))
def test_pair_previews_reuse_isolated_library_renderer(
    selection_page: Path, tmp_path: Path, width: int
) -> None:
    script = (
        OPEN
        + """
    choose("catSymbol","Fenolite:Resistor"); choose("catFootprint","Fenolite:Chip_0603");
    const frames = [...$("catalogSelection").querySelectorAll("iframe")];
    const rect = $("catalogSelection").getBoundingClientRect();
    return {frames:frames.map(f=>({src:f.src,title:f.title,sandbox:f.getAttribute("sandbox")})),
      count:frames.length,left:rect.left,right:rect.right,
      overflow:$("catalogSelection").scrollWidth > $("catalogSelection").clientWidth};
    """
    )
    (reply,) = run(
        [
            job(
                "catalog-pair",
                selection_page,
                tmp_path,
                script=script,
                shot="",
                width=width,
                frameScript=(
                    "return {item:LIB.items[LIBSEL].lib_id,kind:S.kind ?? null,prims:S.prims.length,"
                    "preview:PREVIEW_MODE,nested:document.querySelectorAll('iframe').length};"
                ),
            )
        ],
        tmp_path,
    )
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["count"] == 2 and result["left"] >= 0 and result["right"] <= width
    assert not result["overflow"]
    assert len(reply["frames"]) == 2
    assert {f["item"] for f in reply["frames"]} == {"Fenolite:Resistor", "Fenolite:Chip_0603"}
    assert all(f["preview"] and f["prims"] > 0 and f["nested"] == 0 for f in reply["frames"])
    for frame in result["frames"]:
        assert frame["src"].startswith(selection_page.as_uri() + "#") and "preview=1" in frame["src"]
        assert frame["sandbox"] == "allow-scripts"


@pytest.mark.parametrize(
    ("doc", "item", "kind"),
    [
        ("catalog-symbol", "Fenolite:Resistor", "schematic"),
        ("catalog-footprint", "Fenolite:Chip_0603", None),
    ],
)
def test_preview_hash_selects_exact_definition_without_nested_frames(
    selection_page: Path, tmp_path: Path, doc: str, item: str, kind: str | None
) -> None:
    from urllib.parse import urlencode

    script = """
    await openCatalogSelection();
    return {mode:PREVIEW_MODE,item:LIB.items[LIBSEL].lib_id,kind:S.kind ?? null,
      prims:S.prims.length,channel:BC,frames:document.querySelectorAll("iframe").length,
      dialog:$("catalogSelection").open,side:getComputedStyle($("side")).display,
      canvas:$("wrap").getBoundingClientRect().width};
    """
    (reply,) = run(
        [
            job(
                "catalog-preview",
                selection_page,
                tmp_path,
                script=script,
                shot="",
                width=320,
                hash="#" + urlencode({"doc": doc, "item": item, "preview": "1"}),
            )
        ],
        tmp_path,
    )
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["mode"] and result["item"] == item and result["kind"] == kind and result["prims"] > 0
    assert result["channel"] is None and result["frames"] == 0 and not result["dialog"]
    assert result["side"] == "none" and result["canvas"] == 320


def test_mapping_confirmation_and_generated_part_execute(selection_page: Path, tmp_path: Path) -> None:
    script = (
        OPEN
        + """
    choose("catSymbol","Fenolite:Resistor");choose("catFootprint","Fenolite:Chip_0603");
    const initial = $("catSnippet").hidden && $("catCopy").disabled;
    $("catEqualNumbers").click();
    $("catEqualNumbers").focus();
    $("catEqualNumbers").dispatchEvent(new KeyboardEvent("keydown",{key:"m",bubbles:true}));
    const backgroundShortcut = st.measure;
    const unreviewed = {hidden:$("catSnippet").hidden,checked:$("catReviewed").checked,
      disabled:$("catReviewed").disabled};
    $("catReviewed").click(); input("catReference","R42");input("catValue",'10k "selected"');
    const snippet = $("catSnippet").value;
    const map = (pin,value) => { const el=$("catMap").querySelector(`[data-pin="${pin}"]`);
      el.value=value;el.dispatchEvent(new Event("input")); };
    map("2","1"); const duplicate = {text:$("catMapState").textContent,
      hidden:$("catSnippet").hidden,checked:$("catReviewed").checked};
    map("2","99");const unknown = $("catMapState").textContent;
    map("2","");const missing = $("catMapState").textContent;
    $("catEqualNumbers").click();$("catReviewed").click();input("catFootprintQuery","no matching footprint");
    const filtered = {hidden:$("catSnippet").hidden,checked:$("catReviewed").checked};
    input("catFootprintQuery","");choose("catFootprint","Fenolite:Chip_0402");
    const changed = {hidden:$("catSnippet").hidden,checked:$("catReviewed").checked,map:CATSEL.mapping.size};
    return {initial,unreviewed,snippet,duplicate,unknown,missing,filtered,changed,backgroundShortcut};
    """
    )
    (reply,) = run([job("catalog-map", selection_page, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert not result["backgroundShortcut"]
    assert result["initial"] and result["unreviewed"] == {"hidden": True, "checked": False, "disabled": False}
    namespace: dict[str, object] = {}
    exec(result["snippet"], namespace)
    from fenolite.dsl import Part

    part = namespace["part"]
    assert isinstance(part, Part)
    assert part.ref == "R42" and part.value == '10k "selected"'
    assert part.lib_id == "Fenolite:Resistor" and part.footprint == "Fenolite:Chip_0603"
    assert dict(part.pad_map) == {"1": "1", "2": "2"}
    assert "more than once" in result["duplicate"]["text"]
    assert result["duplicate"]["hidden"] and not result["duplicate"]["checked"]
    assert "unknown pad 99" in result["unknown"] and "has no pad" in result["missing"]
    assert result["filtered"] == {"hidden": True, "checked": False}
    assert result["changed"] == {"hidden": True, "checked": False, "map": 0}


def test_one_pin_can_map_to_several_pads_but_none_can_be_unused(selection_page: Path, tmp_path: Path) -> None:
    script = (
        OPEN
        + """
    choose("catSymbol","Fenolite:Resistor");choose("catFootprint","Fenolite:SOT23_3");
    $("catEqualNumbers").click();const extra = $("catMapState").textContent;
    const first = $("catMap").querySelector('[data-pin="1"]');
    first.value="1, 3";first.dispatchEvent(new Event("input"));
    $("catReviewed").click();const snippet=$("catSnippet").value;
    input("catReference",'R1); invalid'); const invalidRef=$("catSnippet").hidden;
    return {extra,snippet,invalidRef};
    """
    )
    (reply,) = run([job("catalog-map-multiple", selection_page, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert "Unmapped numbered pads: 3" in result["extra"] and result["invalidRef"]
    namespace: dict[str, object] = {}
    exec(result["snippet"], namespace)
    from fenolite.dsl import Part

    part = namespace["part"]
    assert isinstance(part, Part) and dict(part.pad_map) == {"1": ("1", "3"), "2": "2"}
