// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { $, esc } from "../core/dom";
import { cv, S, setS, st, vis } from "../core/state";
import { fit, fitted, setFitted } from "../core/viewport";
import { buildDiffList } from "../panels/changes";
import { buildFindings } from "../panels/findings";
import { buildRoles } from "../panels/roles";
import { resetRoleCache } from "../roles/draw";
import { ROLE_SEL } from "../roles/roles";
import { buildMessages } from "../panels/messages";
import { buildReview } from "../panels/review";
import { applyProjNet } from "../sch/project-nets";
import { build3D, draw3D, V3 } from "../three/view3d";
import { buildCaches } from "./cache";
import { draw } from "./draw";
import { queryParse, queryRun } from "./query";
import { buildTabs } from "./tabs";
import { buildVariants } from "./variants";
import { setDocTitle } from "../panels/toolbar";
export function buildPanels() {
  buildFindings();
  const c = S.meta.counts || {};
  $("notes").innerHTML = (S.meta.notes || []).map(esc).join("<br>") + `${(S.meta.notes || []).length ? "<br>" : ""}Read by the ${esc(S.meta.backend || "?")} backend, evidence ${esc(S.meta.evidence || "?")}.` +
    `<br>${c.footprints || 0} parts · ${c.pads || 0} pads · ${c.tracks || 0} tracks · ${c.vias || 0} vias · ${c.zones || 0} zones`;
}

export function loadBoard(scene, keepView) {
  document.body.classList.remove("sch"); st.itemInfo = false;
  const first = S === null || S !== scene && !keepView; if (S !== scene) { ROLE_SEL.group = -1; ROLE_SEL.finding = -1; } setS(scene);
  for (const l of S.layers) if (!vis.has(l.id)) vis.set(l.id, l.visible);
  if (!st.cur || !S.layers.some(l => l.id === st.cur)) st.cur = (S.layers.find(l => l.id === "F.Cu") || S.layers[0] || {}).id;
  if (st.query) st.query = st.query.text && S.prims ? { text: st.query.text, ...queryRun(S, queryParse(st.query.text)) } : null;
  buildCaches(); resetRoleCache(); buildTabs(); buildPanels(); buildRoles(); buildDiffList(); buildMessages(); buildVariants(); buildReview(); applyProjNet();
  cv.style.display = st.mode3d ? "none" : "block";
  setDocTitle(S.meta.name);
  if (V3.built) { V3.built = false; if (st.mode3d) { build3D(); draw3D(); } }
  if (first) { setFitted(false); fit(); } else draw();
}
