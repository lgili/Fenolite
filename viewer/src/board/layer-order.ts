// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// Presentation preferences only (c0181): never write into a scene or its tab/draw-order data.
import { DOC, PROJECT, S } from "../core/state";

const LAYER_ORDER_SESSION = new Map<string, string[] | null>();
const LAYER_ORDER_ANONYMOUS = new WeakMap<object, Map<string, string[]>>();
export function layerOrderDocumentKey() {
  return JSON.stringify([PROJECT?.name || "", DOC?.id || "", DOC?.name || S?.meta?.name || ""]);
}
export function layerOrderKey() {
  const sha = S?.meta?.sha256;
  if (typeof sha !== "string" || !/^[a-f0-9]{64}$/i.test(sha)) return null;
  return "fenolite.view.layerOrder:" + JSON.stringify([layerOrderDocumentKey(), sha.toLowerCase()]);
}
function readLayerOrder() {
  const key = layerOrderKey();
  if (!key) return S ? LAYER_ORDER_ANONYMOUS.get(S)?.get(layerOrderDocumentKey()) || null : null;
  if (!LAYER_ORDER_SESSION.has(key)) {
    let ids = null;
    try {
      const value = JSON.parse(localStorage.getItem(key) || "null");
      if (Array.isArray(value) && value.every(id => typeof id === "string")) ids = value;
    } catch (e) { /* unavailable storage or malformed data: this page's default */ }
    LAYER_ORDER_SESSION.set(key, ids);
  }
  return LAYER_ORDER_SESSION.get(key);
}
export function orderedLayerIds(defaultIds: string[], saved: unknown): string[] {
  const left = new Set(defaultIds), ids: string[] = [];
  if (Array.isArray(saved) && saved.every(id => typeof id === "string")) {
    for (const id of saved) if (left.delete(id)) ids.push(id);
  }
  return [...ids, ...left];
}
export function preferredLayers(layers: any[]): any[] {
  const by = new Map<string, any>(layers.map(l => [l.id, l]));
  return orderedLayerIds(layers.map(l => l.id), readLayerOrder()).map(id => by.get(id));
}
export function hasLayerOrder(layers) {
  const saved = readLayerOrder(), available = new Set(layers.map(l => l.id));
  return Array.isArray(saved) && saved.some(id => available.has(id));
}
export function keepLayerOrder(ids: string[] | null, defaultIds: string[]) {
  const order = orderedLayerIds(defaultIds, ids);
  const custom = ids !== null;
  const key = layerOrderKey();
  if (!key) {
    if (S) {
      if (!LAYER_ORDER_ANONYMOUS.has(S)) LAYER_ORDER_ANONYMOUS.set(S, new Map());
      const stored = LAYER_ORDER_ANONYMOUS.get(S), doc = layerOrderDocumentKey();
      if (custom) stored.set(doc, order); else stored.delete(doc);
    }
    return;
  }
  LAYER_ORDER_SESSION.set(key, custom ? order : null);
  try {
    if (custom) localStorage.setItem(key, JSON.stringify(order)); else localStorage.removeItem(key);
  } catch (e) { /* the applied preference stays in this page session */ }
}
