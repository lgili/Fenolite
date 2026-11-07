# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Accessible order preferences in Chromium (c0181), using an authored 17-layer UI scene.

This is not the native v6 board: its separate, retained real scene has 14 available layers.
No fixture bytes, CAD tool or native acceptance result are generated here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from _visual import browser_missing, export, job, run

from fenolite.view.export import embedded, page

pytestmark = pytest.mark.needs_browser
ROOT = Path(__file__).resolve().parents[2]
LAYERS = (
    ("F.Cu", "Signal Top", "copper"),
    ("B.Cu", "Bottom Layer", "copper"),
    ("F.SilkS", "Top Overlay", "silkscreen"),
    ("B.SilkS", "Bottom Overlay", "silkscreen"),
    ("F.Paste", "Top Paste", "solderpaste"),
    ("B.Paste", "Bottom Paste", "solderpaste"),
    ("F.Mask", "Top Solder", "soldermask"),
    ("B.Mask", "Bottom Solder", "soldermask"),
    ("Mech.13", "Mechanical 13", "mechanical"),
    ("Mech.14", "Mechanical 14", "mechanical"),
    ("Mech.15", "Mechanical 15", "mechanical"),
    ("Mech.16", "Mechanical 16", "mechanical"),
    ("Guide", "Drill Guide", "mechanical"),
    ("Keepout", "Keep-Out Layer", "mechanical"),
    ("Drawing", "Drill Drawing", "mechanical"),
    ("Multi", "Multi-Layer", "mechanical"),
    ("Edge.Cuts", "Authored outline", "edge"),
)


@pytest.fixture(scope="module")
def order_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if browser_missing():
        pytest.skip("the browser is missing")
    folder = tmp_path_factory.mktemp("layer-order")
    original = export(ROOT / "tests/data/kicad/board/two_layer.kicad_pcb", folder / "original.html")
    data = embedded(original.read_text())
    assert data is not None
    doc_id = data["open"]
    scene = data["scenes"][doc_id]
    scene["layers"] = [
        {"id": ident, "name": name, "kind": kind, "tab": i, "color": "#c445c4", "visible": True}
        for i, (ident, name, kind) in enumerate(LAYERS)
    ]
    scene["meta"]["name"] = "Authored 17-layer UI fixture"
    scene["meta"].pop("sha256", None)
    scene["meta"]["sha256"] = hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest()
    tree = data["project"]
    tree["name"] = "Authored layer-order interaction"
    doc = next(d for group in tree["groups"] for d in group["documents"] if d["id"] == doc_id)
    other = dict(doc, id="other-board", name="Other authored board")
    tree["groups"][0]["documents"].append(other)
    target = folder / "order-17.html"
    target.write_text(page(tree, {doc_id: scene, other["id"]: copy.deepcopy(scene)}, open_id=doc_id))
    return target


HELP = """
const settle = () => new Promise(ok => setTimeout(ok, 25));
const ids = () => tabLayers().map(l => l.id);
const rows = () => [...$("layerList").querySelectorAll(".lrow")].map(r => r.dataset.layer);
const choose = id => { const s = $("layerOrderSelect"); s.value = id;
  s.dispatchEvent(new Event("change", {bubbles:true})); };
const arrow = dir => $("layerOrderSelect").dispatchEvent(new KeyboardEvent("keydown", {
  key:dir < 0 ? "ArrowUp" : "ArrowDown", altKey:true, bubbles:true, cancelable:true}));
const configure = async wanted => {
  for (let i = 0; i < wanted.length; i++) { choose(wanted[i]);
    while ([...$("layerOrderSelect").options].findIndex(o => o.value === wanted[i]) > i) {
      arrow(-1); await settle();
    }
  }
};
setDockTab("layers"); await settle();
"""


def _act(order_page: Path, tmp_path: Path, script: str, **extra: Any) -> Any:
    if "reloadScript" in extra:
        extra["reloadScript"] = HELP + extra["reloadScript"]
    (reply,) = run(
        [job("layer-order", order_page, tmp_path, script=HELP + script, shot="", **extra)], tmp_path
    )
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_keyboard_apply_cancel_reset_preserve_data(order_page: Path, tmp_path: Path) -> None:
    """The 17-layer authored case: a global order, no source/state/draw-order mutation."""
    script = """
    const original = ids(), originalRows = rows();
    st.selComp = 0; st.cur = "F.Cu"; vis.set("B.Mask", false);
    S.layers[0].alpha = 0.35; buildTabs(); draw();
    const snapshot = () => JSON.stringify({scene:S, vis:[...vis], cur:st.cur, part:st.selComp,
      net:st.selNet, single:st.single, draw:order().map(e => e[0].id)});
    const before = snapshot();
    $("orderLayers").click(); await settle();
    const focused = document.activeElement.id, firstDisabled = $("layerOrderUp").disabled;
    arrow(1); await settle();
    const draftOnly = JSON.stringify(ids()) === JSON.stringify(original);
    $("layerOrderCancel").click(); await settle();
    const cancelled = JSON.stringify(ids()) === JSON.stringify(original), back = document.activeElement.id;
    $("orderLayers").click(); arrow(1); await settle();
    $("layerOrderDialog").dispatchEvent(new Event("cancel", {cancelable:true}));
    const escaped = !$("layerOrderDialog").open && JSON.stringify(ids()) === JSON.stringify(original);
    $("orderLayers").click(); await settle();
    const desired = ["F.Cu", "B.Cu", "Mech.13", "Mech.14", "Mech.15", "Mech.16",
      ...original.filter(id => !["F.Cu", "B.Cu", "Mech.13", "Mech.14", "Mech.15", "Mech.16"].includes(id))];
    await configure(desired); choose(desired[desired.length-1]);
    const lastDisabled = $("layerOrderDown").disabled;
    $("layerOrderApply").click(); await settle();
    const applied = ids(), listed = rows(), unchanged = snapshot() === before,
      groupsKept = !!$("layerList").querySelector(".layerVisibilityGroups");
    stepCurrent(1); const stepped = st.cur;
    stepCurrent(1); const steppedCustom = st.cur;
    const beforeReset = snapshot();
    $("orderLayers").click(); $("layerOrderReset").click(); $("layerOrderCancel").click(); await settle();
    const resetCancelled = JSON.stringify(ids()) === JSON.stringify(desired);
    $("orderLayers").click(); $("layerOrderReset").click(); await settle();
    const resetDraftOnly = JSON.stringify(ids()) === JSON.stringify(desired);
    $("layerOrderApply").click(); await settle();
    return {n:original.length, focused, firstDisabled, lastDisabled, draftOnly, cancelled, back, escaped,
      desired, applied, listed, unchanged, groupsKept, stepped, steppedCustom, resetDraftOnly, resetCancelled,
      reset:ids(), original, defaultRowsRestored:JSON.stringify(rows()) === JSON.stringify(originalRows),
      resetStateKept:snapshot() === beforeReset, cleared:localStorage.getItem(layerOrderKey()) === null};
    """
    found = _act(order_page, tmp_path, script)
    assert found["n"] == 17 and found["focused"] == "layerOrderSelect"
    assert found["firstDisabled"] and found["lastDisabled"]
    assert found["draftOnly"] and found["cancelled"] and found["escaped"]
    assert found["back"] == "orderLayers"
    assert found["applied"] == found["listed"] == found["desired"]
    assert found["unchanged"] and found["groupsKept"] and found["stepped"] == "B.Cu"
    assert found["steppedCustom"] == "Mech.13"
    assert found["resetDraftOnly"] and found["resetCancelled"] and found["reset"] == found["original"]
    assert found["resetStateKept"] and found["defaultRowsRestored"] and found["cleared"]


def test_reload_document_and_hash_scope(order_page: Path, tmp_path: Path) -> None:
    script = """
    const original = ids(); $("orderLayers").click(); arrow(1); await settle();
    $("layerOrderApply").click(); await settle();
    return {saved:ids(), key:layerOrderKey(), original};
    """
    reload = """
    setDockTab("layers"); const saved = ids(), firstKey = layerOrderKey();
    await openDoc(allDocs().find(d => d.id === "other-board")); setDockTab("layers");
    const other = ids(), otherKey = layerOrderKey();
    const changed = structuredClone(S); changed.meta.sha256 = "f".repeat(64); loadBoard(changed, true);
    return {saved, firstKey, other, otherKey, changed:ids(), changedKey:layerOrderKey(),
      changedCustom:hasLayerOrder(defaultTabLayers())};
    """
    found = _act(order_page, tmp_path, script, reloadScript=reload)
    before, after = found["before"], found["after"]
    assert before["saved"] != before["original"] and after["saved"] == before["saved"]
    assert before["key"] == after["firstKey"] != after["otherKey"] != after["changedKey"]
    assert after["other"] == after["changed"] == before["original"]
    assert after["changedCustom"] is False


@pytest.mark.parametrize(
    "saved", ["{", '{"not":"an array"}', '["B.Cu",4]', '["Mech.13","unknown","Mech.13","F.Cu"]']
)
def test_untrusted_saved_ids(order_page: Path, tmp_path: Path, saved: str) -> None:
    script = f"localStorage.setItem(layerOrderKey(), {json.dumps(saved)}); return ids();"
    reload = "return {ordered:tabLayers().map(l => l.id), base:defaultTabLayers().map(l => l.id)};"
    found = _act(order_page, tmp_path, script, reloadScript=reload)["after"]
    assert len(found["ordered"]) == len(set(found["ordered"])) == 17
    assert sorted(found["ordered"]) == sorted(found["base"])
    if saved.startswith('["Mech.13"'):
        assert found["ordered"] == [
            "Mech.13",
            "F.Cu",
            *[x for x in found["base"] if x not in {"Mech.13", "F.Cu"}],
        ]
    else:
        assert found["ordered"] == found["base"]


def test_unavailable_storage_and_changed_document_draft(order_page: Path, tmp_path: Path) -> None:
    script = """
    Object.defineProperty(window, "localStorage", {configurable:true, get() {throw new Error("blocked");}});
    const original = ids(); $("orderLayers").click(); arrow(1); await settle();
    $("layerOrderApply").click(); await settle();
    const applied = ids(); buildTabs(); const kept = ids();
    $("orderLayers").click(); arrow(1); await settle();
    const changed = structuredClone(S); changed.meta.sha256 = "e".repeat(64); loadBoard(changed, true);
    $("layerOrderApply").click(); await settle();
    const refused = $("layerOrderDialog").open && $("layerOrderApply").disabled,
      notice = $("layerOrderStatus").textContent;
    $("layerOrderCancel").click();
    $("orderLayers").click(); arrow(1); await settle(); $("layerOrderApply").click();
    $("orderLayers").click(); $("layerOrderReset").click(); $("layerOrderApply").click(); await settle();
    return {original, applied, kept, refused, notice, reset:ids()};
    """
    found = _act(order_page, tmp_path, script)
    assert found["applied"] != found["original"] and found["kept"] == found["applied"]
    assert found["refused"] and "document changed" in found["notice"]
    assert found["reset"] == found["original"]


def test_reset_refuses_a_live_changed_layer_set(order_page: Path, tmp_path: Path) -> None:
    """An open draft cannot reset/apply against a replacement scene with a new layer."""
    script = """
    $("orderLayers").click(); arrow(1); await settle();
    const changed = structuredClone(S); changed.meta.sha256 = "b".repeat(64);
    changed.layers.push({id:"new-authored-layer", name:"New authored layer", kind:"mechanical",
      color:"#112233", tab:1000, visible:false});
    loadBoard(changed, true);
    $("layerOrderReset").click(); await settle();
    return {notice:$("layerOrderStatus").textContent, refused:$("layerOrderApply").disabled,
      stillOpen:$("layerOrderDialog").open, ordered:ids(), base:defaultTabLayers().map(l => l.id)};
    """
    found = _act(order_page, tmp_path, script)
    assert found["stillOpen"] and found["refused"] and "document changed" in found["notice"]
    assert found["ordered"] == found["base"]


def test_no_hash_preference_is_session_and_document_scoped(order_page: Path, tmp_path: Path) -> None:
    script = """
    S.meta.sha256 = ""; buildTabs(); const original = ids(), firstDoc = DOC;
    $("orderLayers").click(); arrow(1); await settle(); $("layerOrderApply").click(); await settle();
    const applied = ids(), noStorage = Object.keys(localStorage)
      .filter(k => k.startsWith("fenolite.view.layerOrder:")).length === 0;
    setDoc({...DOC, id:"other-without-hash"}); buildTabs(); const other = ids();
    setDoc(firstDoc); buildTabs();
    return {original, applied, other, returned:ids(), noStorage};
    """
    found = _act(order_page, tmp_path, script)
    assert found["applied"] != found["original"] and found["returned"] == found["applied"]
    assert found["other"] == found["original"] and found["noStorage"]


def test_apply_the_shown_order_then_explicit_reset(order_page: Path, tmp_path: Path) -> None:
    """Apply uses the dialog's complete order even when the draft needs no moves."""
    script = """
    const grouped = rows(), original = ids();
    $("orderLayers").click(); $("layerOrderApply").click(); await settle();
    const listed = rows(), custom = hasLayerOrder(defaultTabLayers());
    $("orderLayers").click(); $("layerOrderReset").click(); $("layerOrderApply").click(); await settle();
    return {original, listed, custom, grouped, restored:rows(),
      resetCustom:hasLayerOrder(defaultTabLayers())};
    """
    found = _act(order_page, tmp_path, script)
    assert found["listed"] == found["original"] and found["custom"]
    assert found["restored"] == found["grouped"] and found["resetCustom"] is False
