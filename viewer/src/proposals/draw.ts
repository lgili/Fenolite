// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// Proposed copper is dashed, never painted into a committed-copper cache.
import { ctx, S, st, view, vis } from "../core/state";
import { worldTf } from "../core/viewport";
import { proposalScene, PROPOSALS } from "../proposals";
export function drawProposals() {
  const data = proposalScene(S); if (!data) return;
  worldTf(); ctx.save(); const u = 1 / view.s;
  const on = layer => S.layers.some(l => l.id === layer) && vis.get(layer) !== false && (!st.single || st.cur === layer);
  for (const subject of data.proposals || []) {
    for (const candidate of subject.candidates || []) {
      if (PROPOSALS.hidden.has(candidate.id || "")) continue;
      const focus = PROPOSALS.focused === candidate.id || PROPOSALS.focused === candidate.bundle;
      ctx.globalAlpha = candidate.rejected ? 0.4 : 0.9;
      ctx.strokeStyle = focus ? "#ffb640" : "#36bdd0";
      ctx.setLineDash(candidate.rejected ? [2 * u, 5 * u] : [7 * u, 4 * u]);
      for (const line of candidate.polylines || []) {
        if (!on(line.layer) || line.points.length < 2) continue;
        ctx.lineWidth = Math.max(line.width, (focus ? 3 : 2) * u);
        ctx.beginPath(); line.points.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.stroke();
      }
      for (const via of candidate.vias || []) {
        const stack = S.layers.filter(l => l.kind === "copper").map(l => l.id);
        const a = stack.indexOf(via.layers[0]), b = stack.indexOf(via.layers[via.layers.length - 1]);
        const span = a >= 0 && b >= a ? stack.slice(a, b + 1) : via.layers;
        if (!span.some(on)) continue;
        ctx.lineWidth = (focus ? 3 : 2) * u;
        ctx.beginPath(); ctx.arc(via.at[0], via.at[1], Math.max(via.diameter / 2, 4 * u), 0, Math.PI * 2); ctx.stroke();
        if (via.drill != null) { ctx.setLineDash([]); ctx.beginPath(); ctx.arc(via.at[0], via.at[1], via.drill / 2, 0, Math.PI * 2); ctx.stroke(); }
        ctx.setLineDash([7 * u, 4 * u]);
      }
    }
    // Endpoints of unresolved subjects remain visible, including when every alternative is hidden.
    ctx.globalAlpha = 1; ctx.strokeStyle = subject.candidates?.length ? "#36bdd0" : "#ffb640";
    ctx.lineWidth = 2 * u; ctx.setLineDash([]);
    for (const end of subject.ends || []) {
      if (!end.at || !(end.layers || []).some(on)) continue;
      const [x, y] = end.at; ctx.strokeRect(x - 4 * u, y - 4 * u, 8 * u, 8 * u);
    }
  }
  ctx.restore();
}
