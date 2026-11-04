// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// An accessible draft editor: applying changes only this document's presentation preference.
import * as preact from "preact";
import { keepLayerOrder, layerOrderDocumentKey, layerOrderKey } from "../board/layer-order";
import { buildTabs, defaultTabLayers, tabLayers } from "../board/tabs";
import { $ } from "../core/dom";
import { S } from "../core/state";

const LAYER_ORDER_DRAFT: any = { scene: null, key: null, document: null, ids: [], selected: "", message: "", reset: false };
function layerOrderChangedDocument() {
  return LAYER_ORDER_DRAFT.scene !== S || LAYER_ORDER_DRAFT.key !== layerOrderKey() || LAYER_ORDER_DRAFT.document !== layerOrderDocumentKey();
}
function rejectChangedLayerOrder() {
  if (!layerOrderChangedDocument()) return false;
  LAYER_ORDER_DRAFT.message = "The document changed. Cancel and open Order layers again.";
  renderLayerOrder(); return true;
}
export function closeLayerOrder() {
  $("layerOrderDialog").close(); LAYER_ORDER_DRAFT.scene = null;
  $("orderLayers")?.focus();
}
function moveLayerOrder(dir: number) {
  if (rejectChangedLayerOrder()) return;
  const draft = LAYER_ORDER_DRAFT, at = draft.ids.indexOf(draft.selected), next = at + dir;
  if (at < 0 || next < 0 || next >= draft.ids.length) return;
  [draft.ids[at], draft.ids[next]] = [draft.ids[next], draft.ids[at]];
  draft.reset = false;
  const layer = draft.scene.layers.find(l => l.id === draft.selected);
  draft.message = `${layer.name} moved to position ${next + 1} of ${draft.ids.length}.`;
  renderLayerOrder(); $("layerOrderSelect").focus();
}
function applyLayerOrder() {
  if (rejectChangedLayerOrder()) return;
  keepLayerOrder(LAYER_ORDER_DRAFT.reset ? null : LAYER_ORDER_DRAFT.ids, defaultTabLayers().map(l => l.id));
  buildTabs(); closeLayerOrder();
}
function LayerOrderEditor() {
  const draft = LAYER_ORDER_DRAFT, at = draft.ids.indexOf(draft.selected), changed = layerOrderChangedDocument();
  const by = new Map<string, any>(draft.scene.layers.map(l => [l.id, l]));
  return <>
    <header class="dlgHead"><h2 id="layerOrderTitle">Order layers</h2></header>
    <div class="layerOrderBody">
      <p id="layerOrderHelp">Choose a layer, then use Move up/down or Alt+↑/↓. Apply saves the order for this document in this browser; Cancel keeps the current order.</p>
      <label for="layerOrderSelect">Layer to reorder</label>
      <select id="layerOrderSelect" disabled={changed} size={Math.min(10, Math.max(2, draft.ids.length))} value={draft.selected}
        aria-describedby="layerOrderHelp" onChange={e => { draft.selected = (e.target as HTMLSelectElement).value; renderLayerOrder(); }}
        onKeyDown={e => { if (e.altKey && !e.ctrlKey && !e.metaKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
          e.preventDefault(); e.stopPropagation(); moveLayerOrder(e.key === "ArrowUp" ? -1 : 1);
        } }}>
        {draft.ids.map(id => <option key={id} value={id}>{by.get(id).name}</option>)}
      </select>
      <div class="layerOrderMoves">
        <button type="button" id="layerOrderUp" class="tb" disabled={changed || at <= 0} onClick={() => moveLayerOrder(-1)}>Move up</button>
        <button type="button" id="layerOrderDown" class="tb" disabled={changed || at < 0 || at >= draft.ids.length - 1} onClick={() => moveLayerOrder(1)}>Move down</button>
        <button type="button" id="layerOrderReset" class="tb" disabled={changed} onClick={() => {
          if (rejectChangedLayerOrder()) return;
          draft.ids = defaultTabLayers().map(l => l.id); draft.reset = true;
          draft.message = "Default viewer order. Choose Apply to restore it.";
          renderLayerOrder(); $("layerOrderSelect").focus();
        }}>Reset to default</button>
      </div>
      <p id="layerOrderStatus" role="status" aria-live="polite">{draft.message || "Only the list and layer navigation order change. Visibility and selections stay as they are."}</p>
    </div>
    <footer class="layerOrderFoot">
      <button type="button" id="layerOrderCancel" class="tb" onClick={closeLayerOrder}>Cancel</button>
      <button type="button" id="layerOrderApply" class="tb primary" disabled={layerOrderChangedDocument()} onClick={applyLayerOrder}>Apply</button>
    </footer>
  </>;
}
function renderLayerOrder() { preact.render(<LayerOrderEditor />, $("layerOrderDialog")); }
export function openLayerOrder() {
  if (!S?.layers?.length) return;
  const ids = tabLayers().map(l => l.id);
  Object.assign(LAYER_ORDER_DRAFT, { scene: S, key: layerOrderKey(), document: layerOrderDocumentKey(), ids, selected: ids[0], message: "", reset: false });
  renderLayerOrder(); $("layerOrderDialog").showModal(); $("layerOrderSelect").focus();
}
$("layerOrderDialog").addEventListener("cancel", e => { e.preventDefault(); closeLayerOrder(); });
