// ================================================================== changes since an older revision (c0184)
const DIFF_COLOR = { added: "#35e06b", removed: "#ff3cf0", moved: "#ffb020", changed: "#ffb020", zone: "#40c0ff", net: "#ffb020" };
function drawDiff() {
  const D = S.diff; if (!D || !st.diff || D.kind !== "board") return;
  if (!D.cache) { D.cache = { added: newCache(), removed: newCache() }; for (const pr of D.added) addPrim(D.cache.added, pr); for (const pr of D.removed) addPrim(D.cache.removed, pr); }
  worldTf(); paintCache(ctx, D.cache.removed, "diff", DIFF_COLOR.removed, 0.85, view.s); paintCache(ctx, D.cache.added, "diff", DIFF_COLOR.added, 0.85, view.s);
  ctx.globalAlpha = 1; ctx.strokeStyle = ctx.fillStyle = DIFF_COLOR.moved; ctx.lineWidth = 2 / view.s;
  for (const m of D.moved) { const [x0, y0] = m.from, [x1, y1] = m.to, a = Math.atan2(y1 - y0, x1 - x0), h = 10 / view.s;
    ctx.beginPath(); ctx.arc(x0, y0, 3 / view.s, 0, 2 * Math.PI); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    if (Math.hypot(x1 - x0, y1 - y0) > 0) { ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x1 - h * Math.cos(a - 0.4), y1 - h * Math.sin(a - 0.4)); ctx.lineTo(x1 - h * Math.cos(a + 0.4), y1 - h * Math.sin(a + 0.4)); ctx.closePath(); ctx.fill(); } }
}
function drawSchDiff() {
  const D = S.diff; if (!D || !st.diff) return; ctx.globalAlpha = 1; ctx.lineWidth = 2 / view.s; ctx.setLineDash([6 / view.s, 3 / view.s]);
  for (const c of D.changes) if (c.box) { const b = c.box, e = 1.5; ctx.strokeStyle = DIFF_COLOR[c.kind] || "#ffb020"; ctx.strokeRect(b[0] - e, b[1] - e, b[2] - b[0] + 2 * e, b[3] - b[1] + 2 * e); }
  ctx.setLineDash([]);
}
function buildDiffList() {
  const box = $("diffList"), D = S && S.diff; box.innerHTML = ""; $("diffTitle").style.display = D ? "" : "none"; if (!D) return;
  $("diffTitle").textContent = `Changes since ${D.old.name} (${D.changes.length})`;
  D.changes.forEach(c => { const d = document.createElement("div"); d.className = "navi"; d.innerHTML = `<span class="sw" style="background:${DIFF_COLOR[c.kind] || "#888"}"></span> ${esc(c.text)}`;
    if (c.box) d.onclick = () => { const b = c.box, m = Math.max(b[2] - b[0], b[3] - b[1], 1) * 0.6; fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); };
    box.appendChild(d); });
}
