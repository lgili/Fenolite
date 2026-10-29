const SEV_COLOR = { error: "#ff4040", warning: "#ffb020", info: "#4da3ff" };
function checkToMM(sc) { const C = sc.check; if (!C || C.mm) return; C.mm = true; const f = v => v * MM;
for (const x of C.findings) { if (x.at) x.at = x.at.map(f); if (x.box) x.box = x.box.map(f); } }
function drawCheck() {
const C = S.check; if (!C || !st.checks) return; if (!isSch()) worldTf(); ctx.globalAlpha = 1;
for (let i = C.findings.length - 1; i >= 0; i--) { const x = C.findings[i];
if (!x.at || (x.layer && vis.has(x.layer) && !vis.get(x.layer))) continue;
const sel = i === st.selFinding, r = (sel ? 9 : 6) / view.s, [cx, cy] = x.at;
ctx.strokeStyle = SEV_COLOR[x.severity] || "#cccccc"; ctx.lineWidth = (sel ? 2.5 : 1.6) / view.s; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI);
for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { ctx.moveTo(cx + dx * r * 0.6, cy + dy * r * 0.6); ctx.lineTo(cx + dx * r * 1.6, cy + dy * r * 1.6); }
ctx.stroke();
if (sel && x.box && (x.box[2] > x.box[0] || x.box[3] > x.box[1])) { const b = x.box, e = 2 / view.s; ctx.setLineDash([5 / view.s, 3 / view.s]);
ctx.strokeRect(b[0] - e, b[1] - e, b[2] - b[0] + 2 * e, b[3] - b[1] + 2 * e); ctx.setLineDash([]); } }
}
const MARKER_PICKS = [];
function pickFinding(X, Y) {
const C = S && S.check; if (!C || !st.checks || st.mode3d) return -1; let best = -1, bd = 9;
C.findings.forEach((x, i) => { if (!x.at || (x.layer && vis.has(x.layer) && !vis.get(x.layer))) return; const [sx, sy] = w2s(x.at[0], x.at[1]), d = Math.hypot(sx - X, sy - Y); if (d <= bd) { bd = d; best = i; } });
return best;
}
function selectFinding(i) {
const x = S.check.findings[i]; st.selFinding = i; st.selMessage = null; if (st.mode3d) set3D(false);
const ni = findingNet(x); st.selNet = ni; st.selComp = -1;
if (isSch()) { SCH.sel = -1; SCH.selComp = -1; SCH.selNet = x.net ? S.nets.findIndex(n => (n.project || n.name) === x.net) : -1; }
if (ni >= 0) shareNet(S.nets[ni]);
if (x.layer && !isSch() && S.layers.some(l => l.id === x.layer)) { st.cur = x.layer; vis.set(x.layer, true); buildTabs(); }
if (x.at) { const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]], m = Math.max(b[2] - b[0], b[3] - b[1], isSch() ? 10 : 6) * 0.8; fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m], true); }
showInfo(`<b>${esc(x.code)}</b> · ${esc(x.severity)}<br>${esc(x.message)}` + (x.where ? `<br>Where: ${esc(x.where)}` : "") +
(x.layer && !isSch() ? `<br>Layer: ${esc(layerName(x.layer))}` : "") + (x.at ? "" : "<br><i>No position on this document.</i>") +
`<br>Stage: ${esc(x.stage || "?")} · evidence ${esc(x.evidence || "?")}`, { source: x.stage || "check", evidence: x.evidence || "UNKNOWN" });
if (S.project_review?.binding && !S.project_review.binding.matched) $("info").innerHTML += `<br><b>Historical report:</b> ${esc(S.project_review.binding.note)}`;
buildMessages(); selectionChanged(); evidenceStatus();
if (!x.at) draw();
}
const MSG_ROWS = 300;
const MESSAGE_SOURCES = [];
const MSG_OPEN = new Set();
const EXPLAIN_SOURCES = [];
function explanationOf(code) { for (const src of EXPLAIN_SOURCES) { const e = src(code); if (e) return e; } return null; }
EXPLAIN_SOURCES.push(code => S && S.check && S.check.explain ? S.check.explain[code] || null : null);
function checkMessages() {
const C = S && S.check; if (!C) return [];
return C.findings.map((x, i) => ({ key: "check:" + i, severity: x.severity, code: x.code, object: findingObject(x), message: x.message + (x.at ? "" : " (no position)"),
source: [x.stage, x.evidence].filter(Boolean).join(" · "), evidence: x.evidence || "", layer: x.layer && !isSch() ? layerName(x.layer) : "", placed: !!x.at, selected: i === st.selFinding, pick: () => selectFinding(i) }));
}
MESSAGE_SOURCES.push(checkMessages);
function findingObject(x) {
if (x.object) return String(x.object);
const words = String(x.where || "").split(/\s+/).filter(w => w && !/^@-?[0-9.]+,-?[0-9.]+$/.test(w));
return words.length ? words[0] : "";
}
const SEV_RANK = { error: 0, warning: 1, info: 2 };
function allMessages() { const out = []; for (const src of MESSAGE_SOURCES) for (const m of src()) out.push(m); return out; }
function buildMessages() {
const body = $("msgBody"); body.innerHTML = "";
const all = allMessages(), n = { error: 0, warning: 0, info: 0 };
for (const m of all) if (m.severity in n) n[m.severity]++;
const stages = [...new Set(all.map(m => (m.source || "").split(" · ")[0]).filter(Boolean))].slice(0, 3);
$("msgTitle").textContent = all.length ? `${stages.length ? stages.join(", ") + " — " : ""}${n.error} errors · ${n.warning} warnings · ${n.info} info` : "No messages";
const want = $("msgSeverity").value, q = $("msgFilter").value.trim().toLowerCase();
const rows = all.filter(m => (!want || m.severity === want) && (!q || [m.code, m.object, m.message, m.source, m.layer].join(" ").toLowerCase().includes(q)));
$("msgEmpty").hidden = all.length > 0; $("msgTable").hidden = !all.length;
for (const m of rows.slice(0, MSG_ROWS)) {
const tr = document.createElement("tr"); tr.dataset.key = m.key; tr.setAttribute("aria-selected", String(!!m.selected)); tr.tabIndex = m.selected ? 0 : -1;
tr.innerHTML = `<td class="sev"><span class="sevdot ${esc(m.severity)}" title="${esc(m.severity)}"></span><span class="sr-only">${esc(m.severity)}</span></td><td>${esc(m.code)}</td><td>${esc(m.object)}</td>` +
`<td title="${esc(m.message)}" data-value="message" data-source="${esc(m.source)}" data-evidence="${esc(m.evidence || "UNKNOWN")}">${esc(m.message)}</td><td data-value="source" data-source="${esc(m.source)}" data-evidence="${esc(m.evidence || "UNKNOWN")}">${esc(m.source)}</td><td>${esc(m.layer || "—")}</td>`;
tr.onclick = () => m.pick(); tr.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); m.pick(); } };
const why = document.createElement("button"); why.className = "why"; why.textContent = "?"; why.title = `Explain ${m.code}`; why.setAttribute("aria-label", `Explain ${m.code}`);
why.setAttribute("aria-expanded", String(MSG_OPEN.has(m.key))); why.onclick = e => { e.stopPropagation(); if (MSG_OPEN.has(m.key)) MSG_OPEN.delete(m.key); else MSG_OPEN.add(m.key); buildMessages(); };
tr.children[1].prepend(why);
body.appendChild(tr);
if (MSG_OPEN.has(m.key)) { const ex = explanationOf(m.code), d = document.createElement("tr"); d.className = "explain";
d.innerHTML = `<td></td><td colspan="5">${ex ? `<b>${esc(m.code)}</b>: ${esc(ex.meaning)}<br><i>Fix:</i> ${esc(ex.fix)}${ex.see ? `<br><i>See:</i> ${esc(ex.see)}` : ""}` : `No explanation is embedded for ${esc(m.code)}: run <code>fenolite explain ${esc(m.code)}</code>.`}</td>`;
body.appendChild(d); }
}
if (rows.length > MSG_ROWS) { const tr = document.createElement("tr"); tr.innerHTML = `<td></td><td colspan="5" class="notes">… ${rows.length - MSG_ROWS} more; filter to see them</td>`; body.appendChild(tr); }
const sel = body.querySelector('tr[aria-selected="true"]'); if (sel && sel.scrollIntoView) sel.scrollIntoView({ block: "nearest" });
}
$("msgSeverity").onchange = buildMessages;
$("msgFilter").oninput = buildMessages;
MESSAGE_SOURCES.push(() => (S?.project_review?.operation_findings || []).map((x, i) => ({
key: "operation:" + i, severity: x.severity, code: x.code, object: findingObject(x),
message: x.message + " (no position)", source: x.stage || "recorded operation", evidence: x.evidence || "UNKNOWN",
selected: st.selMessage === "operation:" + i, pick: () => { st.selMessage = "operation:" + i; st.selFinding = -1;
showInfo(`<b>${esc(x.code)}</b><br>${esc(x.message)}<br>${esc(x.hint || "")}<br>No position on this document.`, {source:x.stage || "recorded operation", evidence:x.evidence || "UNKNOWN"});
buildMessages(); selectionChanged(); }
})));
MESSAGE_SOURCES.push(() => (S?.diff?.changes || []).map((c, i) => ({ key:"change:" + i, severity:"info",
code:"compare." + c.kind, object:c.key || "", message:c.text + (c.box ? "" : " (no position)"), source:"compare",
evidence:S.meta.evidence || "INFERRED", placed:!!c.box, selected:st.selMessage === "change:" + i, pick:() => selectChange(i) })));
