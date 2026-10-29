const HL_ALPHA = { dim: 0.28, mask: 0.06, normal: 1 };
const ROW = 20;
function vlist(box, items, row, click, selected) {
const inner = document.createElement("div"); inner.style.cssText = `position:relative;height:${items.length * ROW}px`;
box.innerHTML = ""; box.appendChild(inner);
const paint = () => { const top = box.scrollTop, h = box.clientHeight || 240;
const a = Math.max(0, Math.floor(top / ROW) - 4), z = Math.min(items.length, Math.ceil((top + h) / ROW) + 4); inner.innerHTML = "";
for (let i = a; i < z; i++) { const d = document.createElement("div"); d.className = "navi" + (selected(items[i]) ? " sel" : "");
d.style.cssText = `position:absolute;left:0;right:0;top:${i * ROW}px;height:${ROW}px;line-height:${ROW}px`; d.innerHTML = row(items[i]); d.onclick = () => click(items[i]); inner.appendChild(d); } };
box.onscroll = paint; paint();
}
function netBounds(ni) { let b = null;
for (const list of byLayer.values()) for (const [pr, q] of list) if (pr[3] === ni) b = b ? [Math.min(b[0], q[0]), Math.min(b[1], q[1]), Math.max(b[2], q[2]), Math.max(b[3], q[3])] : [...q];
return b; }
function primBounds(set) { let b = null;
for (const list of byLayer.values()) for (const [pr, q] of list) if (set.has(pr)) b = b ? [Math.min(b[0], q[0]), Math.min(b[1], q[1]), Math.max(b[2], q[2]), Math.max(b[3], q[3])] : [...q];
return b; }
function selectCompAt(ci) { if (st.mode3d) set3D(false); st.selComp = ci; st.selNet = -1; const b = S.comps[ci].bbox; if (b) fit([b[0] - 5, b[1] - 5, b[2] + 5, b[3] + 5]); showInfo(compInfo(ci)); buildReview(); draw(); }
function selectNetAt(ni) { if (st.mode3d) set3D(false); st.selNet = ni; st.selComp = -1; shareNet(S.nets[ni]); const b = netBounds(ni); if (b) fit([b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3]);
const info = (S.netinfo || [])[ni]; showInfo(`Net: <b>${esc(S.nets[ni])}</b>` + (info ? `<br>${info.pads} pads · routed ${fmtLen(info.length * MM)}` : "")); buildReview(); draw(); }
function buildReview() {
if (!S || S.kind || !S.prims) return; const qy = st.query, inQ = qy ? new Set(qy.comps) : null;
const cf = $("compFilter").value.trim().toLowerCase(), nf = $("netFilter").value.trim().toLowerCase();
const comps = S.comps.map((c, i) => i).filter(i => !inQ || inQ.has(i)).filter(i => { const c = S.comps[i]; return !cf || [c.ref, c.value, c.footprint].some(v => String(v || "").toLowerCase().includes(cf)); })
.sort((a, b) => natural(S.comps[a].ref, S.comps[b].ref));
let netSet = null; if (qy) { netSet = new Set(); for (const pr of qy.prims) if (pr[3] >= 0) netSet.add(pr[3]); }
const nets = S.nets.map((n, i) => i).filter(i => S.nets[i] && (!netSet || netSet.has(i)) && (!nf || S.nets[i].toLowerCase().includes(nf))).sort((a, b) => natural(S.nets[a], S.nets[b]));
$("compsTitle").textContent = `Components (${comps.length})`; $("netsTitle").textContent = `Nets (${nets.length})`;
vlist($("compList"), comps, i => { const c = S.comps[i]; return `${esc(c.ref)} <small>${esc(c.value || "")} · ${esc(c.footprint)}${c.side === "bottom" ? " · bottom" : ""}</small>`; }, selectCompAt, i => i === st.selComp);
vlist($("netList"), nets, i => { const info = (S.netinfo || [])[i]; return `${esc(S.nets[i])}` + (info ? ` <small>${info.pads} pads · ${fmtLen(info.length * MM)}</small>` : ""); }, selectNetAt, i => i === st.selNet);
$("queryInfo").textContent = qy ? (qy.prims.size || qy.comps.length ? `${qy.comps.length} part(s) · ${qy.prims.size} primitive(s)` : "Nothing matches the filter.") : "";
}
function applyQuery(text, zoom) {
if (!S || S.kind || !S.prims) return; text = text.trim();
if (!text) { clearQuery(); return; }
st.query = { text, ...queryRun(S, queryParse(text)) }; qCache.delete(text); buildReview();
if (zoom && st.query.prims.size) { const b = primBounds(st.query.prims); if (b) fit([b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3]); }
draw();
}
function clearQuery() { st.query = null; $("query").value = ""; st.selNet = -1; st.selComp = -1; showInfo(null); buildReview(); draw(); }
let qTimer = null;
$("query").addEventListener("input", e => { clearTimeout(qTimer); qTimer = setTimeout(() => applyQuery(e.target.value, false), 250); });
$("query").addEventListener("keydown", e => { if (e.key === "Enter") { clearTimeout(qTimer); applyQuery(e.target.value, true); } else if (e.key === "Escape") e.target.blur(); });
$("compFilter").addEventListener("input", buildReview); $("netFilter").addEventListener("input", buildReview);
$("bSimilar").onclick = () => { if (!S || S.kind) return; const h = st.lastHit, ci = st.selComp >= 0 ? st.selComp : -1;
const text = similarQuery(S, h ? h.pr : null, ci >= 0 ? ci : h && h.pr[4] >= 0 && h.pr[3] < 0 ? h.pr[4] : -1);
if (!text) { $("queryInfo").textContent = "Select a part or a primitive first."; return; }
$("query").value = text; applyQuery(text, false); };
$("bQClear").onclick = clearQuery;
$("hlMode").value = HL_ALPHA[st.hl] !== undefined ? st.hl : "dim";
$("hlMode").onchange = e => { st.hl = e.target.value; try { localStorage.setItem("fenolite.view.highlight", st.hl); } catch (err) {  } draw(); };
