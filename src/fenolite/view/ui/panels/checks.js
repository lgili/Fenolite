// ================================================================== check findings (c0188)
const SEV_COLOR = { error: "#ff4040", warning: "#ffb020", info: "#4da3ff" };
function checkToMM(sc) { const C = sc.check; if (!C || C.mm) return; C.mm = true; const f = v => v * MM;
  for (const x of C.findings) { if (x.at) x.at = x.at.map(f); if (x.box) x.box = x.box.map(f); } }
function drawCheck() {   // a ring with four ticks at each placed finding, the colour of its severity; the box of the one chosen
  const C = S.check; if (!C || !st.checks) return; if (!isSch()) worldTf(); ctx.globalAlpha = 1;
  for (let i = C.findings.length - 1; i >= 0; i--) { const x = C.findings[i];   // errors last, on top
    if (!x.at || (x.layer && vis.has(x.layer) && !vis.get(x.layer))) continue;
    const sel = i === st.selFinding, r = (sel ? 9 : 6) / view.s, [cx, cy] = x.at;
    ctx.strokeStyle = SEV_COLOR[x.severity] || "#cccccc"; ctx.lineWidth = (sel ? 2.5 : 1.6) / view.s; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI);
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { ctx.moveTo(cx + dx * r * 0.6, cy + dy * r * 0.6); ctx.lineTo(cx + dx * r * 1.6, cy + dy * r * 1.6); }
    ctx.stroke();
    if (sel && x.box && (x.box[2] > x.box[0] || x.box[3] > x.box[1])) { const b = x.box, e = 2 / view.s; ctx.setLineDash([5 / view.s, 3 / view.s]);
      ctx.strokeRect(b[0] - e, b[1] - e, b[2] - b[0] + 2 * e, b[3] - b[1] + 2 * e); ctx.setLineDash([]); } }
}
function selectFinding(i) {
  const x = S.check.findings[i]; st.selFinding = i; if (st.mode3d) set3D(false);
  if (x.layer && !isSch() && S.layers.some(l => l.id === x.layer)) { st.cur = x.layer; vis.set(x.layer, true); buildTabs(); }   // its layer, current
  if (x.at) { const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]], m = Math.max(b[2] - b[0], b[3] - b[1], isSch() ? 10 : 6) * 0.8; fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); }
  showInfo(`<b>${esc(x.code)}</b> · ${esc(x.severity)}<br>${esc(x.message)}` + (x.where ? `<br>Where: ${esc(x.where)}` : "") +
    (x.layer && !isSch() ? `<br>Layer: ${esc(layerName(x.layer))}` : "") + (x.at ? "" : "<br><i>No position on this document.</i>") +
    `<br>Stage: ${esc(x.stage || "?")} · evidence ${esc(x.evidence || "?")}`);
  if (S.project_review?.binding && !S.project_review.binding.matched) $("info").innerHTML += `<br><b>Historical report:</b> ${esc(S.project_review.binding.note)}`;
  buildMessages(); draw();
}
const MSG_ROWS = 300;
function buildMessages() {   // the Messages panel: findings grouped by rule, errors first
  const box = $("msgList"), C = S && S.check; box.innerHTML = ""; $("msgTitle").style.display = C ? "" : "none"; if (!C) return;
  const n = C.counts; $("msgTitle").textContent = `Messages: ${n.error} errors · ${n.warning} warnings · ${n.info} info`;
  for (const note of C.notes) { const d = document.createElement("div"); d.className = "notes"; d.textContent = note; box.appendChild(d); }
  const groups = new Map(); C.findings.forEach((x, i) => { if (!groups.has(x.code)) groups.set(x.code, []); groups.get(x.code).push(i); });
  st.msgOpen = st.msgOpen || new Set();
  for (const [code, list] of groups) {
    const first = C.findings[list[0]], open = st.msgOpen.has(code) || groups.size === 1, h = document.createElement("div"); h.className = "navg";
    h.innerHTML = `<span class="sw" style="display:inline-block;background:${SEV_COLOR[first.severity] || "#888"}"></span> ${open ? "▾" : "▸"} ${esc(code)} (${list.length})`;
    h.onclick = () => { if (open) st.msgOpen.delete(code); else st.msgOpen.add(code); buildMessages(); }; box.appendChild(h);
    if (!open) continue;
    for (const i of list.slice(0, MSG_ROWS)) { const x = C.findings[i], d = document.createElement("div"); d.className = "navi" + (i === st.selFinding ? " sel" : "");
      d.innerHTML = `${esc(x.message)}${x.at ? "" : " <small>(no position)</small>"}`; d.title = x.where; d.onclick = () => selectFinding(i); box.appendChild(d); }
    if (list.length > MSG_ROWS) { const d = document.createElement("div"); d.className = "notes"; d.textContent = `… ${list.length - MSG_ROWS} more`; box.appendChild(d); }
  }
}
