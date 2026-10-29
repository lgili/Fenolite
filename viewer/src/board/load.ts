// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { buildCaches } from "./cache";
import { draw } from "./draw";
import { queryParse, queryRun } from "./query";
import { buildTabs } from "./tabs";
import { buildVariants } from "./variants";
import { esc } from "../core/dom";
import { S, cv, st, vis } from "../core/state";
import { fit, fitted } from "../core/viewport";
import { buildDiffList } from "../panels/changes";
import { buildFindings } from "../panels/findings";
import { buildMessages } from "../panels/messages";
import { buildReview } from "../panels/review";
import { applyProjNet } from "../sch/project-nets";
import { V3, build3D, draw3D } from "../three/view3d";
import { $ } from "../core/dom";
import { setS } from "../core/state";
import { setFitted } from "../core/viewport";
export function buildPanels() {
  buildFindings();
  const c = S.meta.counts || {};
  $("notes").innerHTML = (S.meta.notes || []).map(esc).join("<br>") + `${(S.meta.notes || []).length ? "<br>" : ""}Read by the ${esc(S.meta.backend || "?")} backend, evidence ${esc(S.meta.evidence || "?")}.` +
    `<br>${c.footprints || 0} parts · ${c.pads || 0} pads · ${c.tracks || 0} tracks · ${c.vias || 0} vias · ${c.zones || 0} zones`;
}

export function loadBoard(scene, keepView) {
  document.body.classList.remove("sch"); st.itemInfo = false;
  const first = S === null || S !== scene && !keepView; setS(scene);
  for (const l of S.layers) if (!vis.has(l.id)) vis.set(l.id, l.visible);
  if (!st.cur || !S.layers.some(l => l.id === st.cur)) st.cur = (S.layers.find(l => l.id === "F.Cu") || S.layers[0] || {}).id;
  if (st.query) st.query = st.query.text && S.prims ? { text: st.query.text, ...queryRun(S, queryParse(st.query.text)) } : null;
  buildCaches(); buildTabs(); buildPanels(); buildDiffList(); buildMessages(); buildVariants(); buildReview(); applyProjNet();
  cv.style.display = st.mode3d ? "none" : "block";
  $("fname").textContent = S.meta.name; document.title = S.meta.name + " · Fenolite viewer";
  $("gen").textContent = S.meta.sha256 ? `SHA-256 ${S.meta.sha256.slice(0, 12)}` : "";
  if (V3.built) { V3.built = false; if (st.mode3d) { build3D(); draw3D(); } }
  if (first) { setFitted(false); fit(); } else draw();
}
