// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== start: embedded data or the live server
import { LIB, openItem } from "../library/library";
import { buildMarks, loadMarks } from "../panels/marks";
import { reviewEntry } from "../panels/project-review";
import { refreshStatus } from "../panels/status-bar";
import { toolbarReady } from "../panels/toolbar";
import { buildTree } from "../panels/tree";
import { runsInit } from "../review/runs";
import { invalidateScene, loadingNavigation, navigation, openDoc } from "./documents";
import { $ } from "./dom";
import { applyLink, applySelect, linkReady, setLinkReady } from "./links";
import { DOC, POLLS, PROJECT, RAW, setProject, st } from "./state";
import { refreshDock } from "../panels/dock";
import { refreshSummary } from "../panels/inspector";
export async function start() {
  if (EMBED) { setProject(EMBED.project); for (const [id, sc] of Object.entries(EMBED.scenes)) RAW.set(id, sc); }   // decoded when opened
  else if (LIVE) { setProject(await (await fetch("project.json", { cache: "no-store" })).json()); }
  document.body.classList.toggle("catalog", PROJECT?.source === "catalog");
  toolbarReady(); refreshStatus(); reviewEntry(); refreshDock(); refreshSummary();
  buildTree();
  loadMarks((EMBED && EMBED.marks) || (PROJECT && PROJECT.marks)); buildMarks();
  const docs = PROJECT ? PROJECT.groups.flatMap(g => g.documents) : [];
  const link = new URLSearchParams(location.hash.slice(1));   // c0189: a link opens where it was made
  const want = link.get("doc") || (EMBED && EMBED.open) || (PROJECT && PROJECT.open);
  const d = docs.find(x => x.id === want) || docs.find(x => x.viewable && x.present) || docs[0];
  const shown = d ? await openDoc(d) : 0;
  if (shown && shown === navigation) {
    if (link.get("doc") && DOC && DOC.id === link.get("doc")) applyLink(link);
    else applySelect((EMBED && EMBED.select) || (PROJECT && PROJECT.select));
    if (link.get("item") && LIB) { const i = LIB.items.findIndex(item => item.name === link.get("item")); if (i >= 0) openItem(i); }
  }
  setLinkReady(true);
  if (LIVE) setInterval(poll, 2000);
  runsInit();   // c0270: asks a live server whether it runs checks
}
export async function poll() {
  if (!DOC || !DOC.viewable || loadingNavigation === navigation) return;
  const doc = DOC, request = (POLLS.get(doc.id) || 0) + 1; let generation = navigation;
  POLLS.set(doc.id, request);
  const current = () => generation === navigation && DOC.id === doc.id && POLLS.get(doc.id) === request;
  try { const v = await (await fetch(`version/${encodeURIComponent(doc.id)}`, { cache: "no-store" })).json();
    if (!current()) return;
    liveState(v.error ? "err" : v.building ? "busy" : "ok", v.error ? `Read error: ${v.error}` : v.building ? "Building…" : v.updated ? `Live · updated ${v.updated}` : "Live");
    if (v.building) return;
    if (v.version && v.version !== st.version) {
      invalidateScene(doc.id); const opening = openDoc(doc, true); generation = navigation;
      const shown = await opening; if (!shown || shown !== generation || !current()) return;
    }
    st.version = v.version || st.version;
  } catch (e) { if (current()) liveState("err", "Server not reachable"); }
}
export function liveState(kind, text) { const el = $("live"); el.textContent = text; el.dataset.state = kind; el.hidden = !text; }
