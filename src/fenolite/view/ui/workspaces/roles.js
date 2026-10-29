// ================================================================== the Net Roles workspace (change c0245, capability roles-workspace)
// The reply of `fenolite roles PATH --check` (fenolite.view_roles.v0, its values unchanged) joined to the
// board: the Net Roles panel (Nets, Groups, Classes), the role Properties (Net, Role, Measures), the overlays
// (loop areas, measures, corridors, locked copper, role copper), the role findings in Messages and on the
// board. Every number shown names the analysis or the limit it comes from.
const ROLES = { byDoc: new Map(), entered: false, tab: "nets", ptab: "role", sel: null, selFinding: -1, view: "roles", error: "",
  ov: { loops: true, measures: true, corridors: true, locked: true, copper: true }, caches: new Map(), multi: new Set() };
const ROLE_ORDER = ["power", "switch_node", "ground", "high_voltage", "gate", "kelvin", "signal"];
const STATE_MARK = { confirmed: "✓", declared: "◆", inferred: "?" };
const GROUP_KIND = { hot: "switch_node", gate: "gate", kelvin: "kelvin" };
const inRoles = () => WS === "roles" && !!(S && !S.kind && S.prims && !LIB);
function rolesData() { return DOC ? ROLES.byDoc.get(DOC.id) || null : null; }
async function loadRolesData(d) {
  if (!d) return null; if (ROLES.byDoc.has(d.id)) return ROLES.byDoc.get(d.id); ROLES.error = "";
  let data = EMBED && EMBED.roles ? EMBED.roles[d.id] || null : null;
  if (!data && LIVE) try { const r = await fetch(`roles/${encodeURIComponent(d.id)}.json`, { cache: "no-store" }); const body = await r.json(); if (r.ok) data = body; else ROLES.error = body.error || `error ${r.status}`; }
    catch (e) { ROLES.error = "the server is not reachable"; }
  if (!data && !ROLES.error) ROLES.error = EMBED ? "This page holds no roles: export it with --workspace roles." : "No roles for this document.";
  if (data) { ROLES.byDoc.set(d.id, data); ROLES.caches.clear(); EVIDENCE_VERSION++; }
  return data;
}
async function enterRoles() {
  if (!S || S.kind || !S.prims || LIB) { say("The Net Roles workspace opens on a board."); return; }
  st.workspace = "roles"; ROLES.entered = true; const doc = DOC; await loadRolesData(doc); if (doc !== DOC) return;
  setWorkspace("roles"); buildRoles(); draw(); buildMessages(); updateStatus();
}
function leaveRoles() { st.workspace = "board"; setWorkspace(workspaceOf()); buildMessages(); draw(); updateStatus(); }
function roleRow(name) { const D = rolesData(); return D ? D.roles.find(r => r.net === name) || null : null; }
function roleOf(name) { const r = inRoles() ? roleRow(name) : null; return r ? r.kind : null; }
function groupsOf() { const D = rolesData(); if (!D) return [];
  return [...D.loops.map(g => ({ kind: "hot", g, pads: g.pads })), ...D.gates.map(g => ({ kind: "gate", g, pads: [g.drive, g.gate, g.source, g.ret].filter(Boolean) })),
    ...D.kelvins.map(g => ({ kind: "kelvin", g, pads: [...g.element, ...g.receiver] }))]; }
function padAt(label) { return S && S.pads ? S.pads.find(p => p.label === label) || null : null; }
function centroid(labels) { const pts = labels.map(padAt).filter(Boolean); if (!pts.length) return null; return [pts.reduce((a, p) => a + p.x, 0) / pts.length, pts.reduce((a, p) => a + p.y, 0) / pts.length]; }
function groupMeasure(name) { const D = rolesData(); return D ? D.measures.find(m => m.kind === "loop" && m.subject === name) || null : null; }
function netOfGroup(name) { const m = groupMeasure(name); if (m && m.values.net) return m.values.net; const gr = groupsOf().find(x => x.g.name === name); if (!gr) return null;
  const p = gr.pads.map(padAt).find(q => q && q.net); return p ? p.net : null; }

// ---- numbers with their source (decision 9, M1)
function pv(text, source, evidence) { return `<span data-value="" data-source="${esc(source)}" data-evidence="${esc(evidence || rolesEvidence())}" title="${esc(source)} · evidence ${esc(evidence || rolesEvidence())}">${esc(text)}</span>`; }
function rolesEvidence() { const D = rolesData(); return D && D.evidence ? D.evidence.level : "INFERRED"; }
function fmtArea(nm2) { return UNIT === "mil" ? `${(nm2 / 1e12 / (MIL_MM * MIL_MM)).toFixed(0)} mil²` : `${(nm2 / 1e12).toFixed(2)} mm²`; }
function fmtValue(key, v) {
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v !== "number") return Array.isArray(v) ? v.map(x => Array.isArray(x) ? x.join("–") : String(x)).join(", ") || "none" : String(v);
  if (/_nm2$/.test(key)) return fmtArea(v);
  if (/(_nm|^gap|^length|^unreferenced|^over_fill|^broadside)$/.test(key)) return fmtNm(v);
  if (/_permille$/.test(key)) return (v / 1000).toFixed(2);
  if (/_mv$/.test(key)) return `${(v / 1000).toFixed(1)} V`;
  if (/^milliamps|_ma$/.test(key)) return `${(v / 1000).toFixed(2)} A`;
  if (/_mohm$/.test(key)) return `${v} mΩ`;
  return String(v);
}
function fmtLimit(l) {   // a limit in the unit of its key (ROLE_LIMIT_UNITS of fenolite.model.rules)
  if (l.value == null) return "no limit";
  const u = l.unit || ""; if (u === "nm") return fmtNm(l.value); if (u === "nm²") return fmtArea(l.value); if (u === "nm per ampere") return `${fmtNm(l.value)} per A`;
  if (u === "per mille") return `${(l.value / 1000).toFixed(2)} (ratio)`; if (u.startsWith("flag")) return l.value ? "judged" : "not judged";
  if (u === "mA") return `${l.value} mA`; return `${l.value}${u ? " " + u : ""}`;
}
function limitSource(l) {
  if (l.origin === "profile") return l.source === "user" ? "no default ships: only yours" : `profile default, ${l.source}`;
  return l.origin === "override" ? "override in the roles' rules" : `${l.origin} file`;
}

// ---- the Net Roles panel
const SHORT = { medium: "med", declared: "decl", confirmed: "conf", inferred: "inf" };
function badge(text, cls) { return `<span class="rbadge ${cls || ""}" title="${esc(text)}">${esc(SHORT[text] || text)}</span>`; }
const MEASURE_NAMES = { area_nm2: "area", bound_nm2: "placement bound", ratio_permille: "ratio", gap: "gap", length: "length", unreferenced: "unreferenced",
  over_fill: "over switching fill", broadside: "broadside overlap", score: "score", offsets: "offset t", open: "open legs" };
function roleChip(kind) { return `<span class="rchip" style="--rc:${roleColor(kind)}"><b>${esc(roleGlyph(kind))}</b></span>`; }
function buildRoles() {
  const D = rolesData(), body = $("roleBody"), head = $("roleHead"); if (!body) return;
  for (const b of document.querySelectorAll("[data-rtab]")) { b.setAttribute("aria-selected", String(b.dataset.rtab === ROLES.tab)); b.tabIndex = b.dataset.rtab === ROLES.tab ? 0 : -1; }
  body.innerHTML = ""; $("roleEmpty").hidden = !!D; if (!D) { $("roleEmpty").textContent = ROLES.error || "Open a board to see its roles."; head.innerHTML = ""; return; }
  const q = $("roleFilter").value.trim().toLowerCase();
  if (ROLES.tab === "nets") {
    head.innerHTML = "<tr><th scope='col'></th><th scope='col'>Net</th><th scope='col'>Role</th><th scope='col'>Conf.</th><th scope='col' aria-label='State'></th></tr>";
    const rows = [...D.roles].filter(r => !q || `${r.net} ${r.kind}`.toLowerCase().includes(q)).sort((a, b) => ROLE_ORDER.indexOf(a.kind) - ROLE_ORDER.indexOf(b.kind) || natural(a.net, b.net));
    for (const r of rows) {
      const tr = document.createElement("tr"); tr.dataset.net = r.net; tr.setAttribute("aria-selected", String(!!(ROLES.sel && ROLES.sel.kind === "net" && ROLES.sel.name === r.net) || ROLES.multi.has(r.net)));
      const current = r.milliamps != null ? " <small>" + pv(fmtValue("milliamps", r.milliamps), `${r.source} current of the role`) + "</small>" : "";
      tr.innerHTML = `<td>${roleChip(r.kind)}</td><td>${esc(r.net)}</td><td>${esc(r.kind)}${current}</td><td>${badge(r.confidence || r.source, "c-" + (r.confidence || r.source))}</td><td title="${esc(r.state)}">${STATE_MARK[r.state] || ""}<span class="sr-only">${esc(r.state)}</span></td>`;
      tr.onclick = e => { if (e.ctrlKey || e.metaKey) { if (ROLES.multi.has(r.net)) ROLES.multi.delete(r.net); else ROLES.multi.add(r.net); buildRoles(); return; } ROLES.multi.clear(); selectRoleNet(r.net); };
      tr.tabIndex = -1; tr.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tr.click(); } }; body.appendChild(tr);
    }
  } else if (ROLES.tab === "groups") {
    head.innerHTML = "<tr><th scope='col'></th><th scope='col'>Group</th><th scope='col'>Parts</th><th scope='col'>Conf.</th></tr>";
    for (const gr of groupsOf()) {
      const g = gr.g; if (q && !g.name.toLowerCase().includes(q)) continue;
      const parts = [...new Set(gr.pads.map(p => String(p).split("-")[0]))].join(" ");
      const tr = document.createElement("tr"); tr.dataset.group = g.name; tr.setAttribute("aria-selected", String(!!(ROLES.sel && ROLES.sel.kind === "group" && ROLES.sel.name === g.name)));
      tr.innerHTML = `<td>${roleChip(GROUP_KIND[gr.kind])}</td><td>${gr.kind === "kelvin" ? "⇉" : "⟲"} ${esc(g.name)}</td><td>${esc(parts)}</td><td>${badge(g.confidence || g.origin, "c-" + (g.confidence || g.origin))}</td>`;
      tr.onclick = () => selectRoleGroup(g.name); tr.tabIndex = -1; tr.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tr.click(); } }; body.appendChild(tr);
    }
  } else {
    head.innerHTML = "<tr><th scope='col'>Part</th><th scope='col'>Class</th><th scope='col'>Conf.</th><th scope='col'>From</th></tr>";
    for (const [ref, c] of Object.entries(D.classes).sort((a, b) => natural(a[0], b[0]))) {
      if (q && !`${ref} ${c.class}`.toLowerCase().includes(q)) continue;
      const tr = document.createElement("tr"); tr.innerHTML = `<td>${esc(ref)}</td><td>${esc(c.class)}</td><td>${badge(c.confidence, "c-" + c.confidence)}</td><td>${esc(c.evidence)}</td>`;
      tr.onclick = () => { const ci = S.comps.findIndex(x => x.ref === ref); if (ci >= 0) selectCompAt(ci); }; body.appendChild(tr);
    }
  }
  const n = D.counts.roles; $("roleCounts").textContent = `${n.confirmed} confirmed · ${n.declared} declared · ${n.inferred} inferred`;
  $("titleState").textContent = `[roles: ${n.confirmed + n.declared} confirmed or declared, ${n.inferred} pending]`;
}
function selectRoleNet(name) { ROLES.sel = { kind: "net", name }; ROLES.selFinding = -1; st.selMessage = null; selectNetByName(name); showRoleProps(); buildRoles(); }
function selectRoleGroup(name) {
  ROLES.sel = { kind: "group", name }; ROLES.selFinding = -1; st.selMessage = null; const gr = groupsOf().find(x => x.g.name === name);
  const net = netOfGroup(name); if (net) selectNetByName(net);
  const pts = gr ? gr.pads.map(padAt).filter(Boolean) : []; if (pts.length) { const xs = pts.map(p => p.x), ys = pts.map(p => p.y); fit([Math.min(...xs) - 4, Math.min(...ys) - 4, Math.max(...xs) + 4, Math.max(...ys) + 4]); }
  showRoleProps(); buildRoles(); draw();
}

// ---- role Properties: Net, Role, Measures
function measuresOf(sel) { const D = rolesData(); if (!D || !sel) return [];
  if (sel.kind === "group") return D.measures.filter(m => m.subject === sel.name || String(m.subject).startsWith(sel.name + ":"));
  return D.measures.filter(m => m.values && (m.values.net === sel.name || m.subject === sel.name)); }
function limitsOf(sel) { const D = rolesData(); if (!D || !sel) return [];
  return D.limits.filter(l => sel.kind === "group" ? l.group === sel.name : l.net === sel.name); }
function showRoleProps() {
  const D = rolesData(), sel = ROLES.sel; if (!inRoles() || !D || !sel) return;
  const tabs = ["net", "role", "measures"].map(t => `<button role="tab" class="ptab2" data-ptab="${t}" aria-selected="${ROLES.ptab === t}">${t === "net" ? (sel.kind === "group" ? "Group" : "Net") : t[0].toUpperCase() + t.slice(1)}</button>`).join("");
  const rows = list => `<table>${list.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join("")}</table>`;
  let html = `<div class="ptabs2" role="tablist" aria-label="Role properties">${tabs}</div>`;
  const src = `fenolite roles --check, ${D.document}`;
  if (sel.kind === "net") {
    const r = roleRow(sel.name), ni = S.nets.indexOf(sel.name), info = (S.netinfo || [])[ni];
    if (ROLES.ptab === "net") html += rows([["Net", esc(sel.name)], ["Pads", info ? pv(String(info.pads), `${S.meta.name}, read by the ${S.meta.backend} backend`, S.meta.evidence) : "—"],
      ["Routed", info ? pv(fmtLen(info.length * MM), "centre lines of its tracks and arcs; Fenolite's computation", S.meta.evidence) : "—"]]);
    else if (ROLES.ptab === "role") html += r ? rows([["Role", `${roleChip(r.kind)} ${esc(r.kind)}`], ["Origin", esc(r.source === "inferred" ? `inferred · rule ${r.rule}` : r.source)], ["Evidence", esc((r.pads || []).join(" + ") || "—")],
      ["Confidence", esc(r.confidence || "stated")], ["State", `${STATE_MARK[r.state] || ""} ${esc(r.state)}`],
      ["Current", r.milliamps != null ? pv(fmtValue("milliamps", r.milliamps), `${r.source} role`) : "not given: its copper is not judged for current"],
      ["Working V", r.working_mv != null ? pv(fmtValue("working_mv", r.working_mv), `${r.source} role`) : "not given"], ["Sensitive", r.sensitive ? "yes" : "no"]])
      : `<p class="notes">${esc(sel.name)} has no role row.</p>`;
  } else {
    const gr = groupsOf().find(x => x.g.name === sel.name), g = gr ? gr.g : {};
    if (ROLES.ptab === "net" || ROLES.ptab === "role") html += rows([["Group", `${roleChip(GROUP_KIND[gr ? gr.kind : "hot"])} ${esc(sel.name)}`], ["Kind", esc(gr ? { hot: "hot loop", gate: "gate loop", kelvin: "Kelvin pair" }[gr.kind] : "?")],
      ["Origin", esc(g.origin === "inferred" ? `inferred · rule ${g.rule}` : g.origin || "?")], ["Confidence", esc(g.confidence || "stated")], ["Pads", esc(gr ? gr.pads.join(" → ") : "")]]);
  }
  if (ROLES.ptab === "measures") {
    const ms = measuresOf(sel), ls = limitsOf(sel);
    html += `<h4>Measures</h4>` + (ms.length ? ms.map(m => `<div class="rmeas"><b>${esc(m.kind)}</b> · ${esc(m.subject)} <small>${esc(m.analysis)} on ${esc((m.copper || []).join(", "))}</small>` +
      rows(Object.entries(m.values).filter(([k, v]) => typeof v === "number" || k === "open" || k === "offsets").map(([k, v]) => [MEASURE_NAMES[k] || k, pv(fmtValue(k, v), `${m.analysis} on ${(m.copper || []).join(", ")} copper`)])) + "</div>").join("") : `<p class="notes">No measure names it.</p>`);
    html += `<h4>Limits</h4>` + (ls.length ? rows(ls.map(l => [l.key, pv(fmtLimit(l), limitSource(l), l.label || rolesEvidence())])) : `<p class="notes">No limit applies to it.</p>`);
    html += routerHtml();
  }
  showInfo(html, { source: src, evidence: rolesEvidence() });
  for (const b of $("info").querySelectorAll("[data-ptab]")) b.onclick = () => { ROLES.ptab = b.dataset.ptab; showRoleProps(); };
}
function routerHtml() {   // the router phases in run order 0, 2, 1, 4, 3 (decision 12); phases 2 and 1 come with c0244 and c0243
  const D = rolesData(), n = D ? D.counts.findings : null;
  const phase0 = n ? (n.error + n.warning ? `${n.error} errors · ${n.warning} warnings` : "done") : "not run";
  const rows = [["0 Roles & checks", phase0], ["2 Critical routes", "not run"], ["1 Power copper", "not run"], ["4 Propose & lock", "not available"], ["3 The rest", "not available"]];
  return `<h4>Router</h4><table class="rphases">${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</table>`;
}
SELECTION_VIEWS.push(s => {   // a net selected anywhere shows its role Properties in the workspace
  if (!inRoles() || !rolesData()) return;
  if (ROLES.selFinding >= 0 && s.finding === "roles:" + ROLES.selFinding) return;
  if (ROLES.sel && ROLES.sel.kind === "group" && netOfGroup(ROLES.sel.name) === s.net) return;
  if (s.net && roleRow(s.net)) { ROLES.sel = { kind: "net", name: s.net }; showRoleProps(); }
  else if (!s.net && !s.comp) ROLES.sel = null;
  buildRoles();
});

// ---- role findings: Messages rows, markers, explanations
function roleFindingPlace(x) {   // where a finding sits: the pads, group or net its place names; null for the whole board
  const words = String(x.where || "").split(/[:/,]/).map(w => w.trim()).filter(Boolean); if (!words.length || words[0] === "roles") return null;
  const pads = [];
  for (const w of words) { if (padAt(w)) pads.push(w); else { const gr = groupsOf().find(g => g.g.name === w); if (gr && words.length === 1) pads.push(...gr.pads);
    else if (S.pads.some(p => p.net === w) && words.length === 1) pads.push(...S.pads.filter(p => p.net === w).map(p => p.label)); } }
  const c = centroid(pads); return c ? { at: c, pads } : null;
}
function roleFindingNet(x) { const w = String(x.where || "").split(/[:/,]/)[0]; if (S.nets.includes(w)) return w; const g = groupsOf().find(gr => gr.g.name === w); return g ? netOfGroup(w) : null; }
function roleSource(x) { const m = /\(((?:profile|override|requirements)[^)]*)\)/.exec(x.message || ""); return m ? `roles.rules · ${m[1]}` : "roles.rules"; }
MESSAGE_SOURCES.push(() => {
  const D = inRoles() ? rolesData() : null; if (!D) return [];
  return D.issues.map((x, i) => ({ key: "roles:" + i, severity: x.severity, code: x.code, object: x.where || "", message: x.message + (roleFindingPlace(x) ? "" : " (no position)"),
    source: roleSource(x), evidence: rolesEvidence(), layer: "", placed: !!roleFindingPlace(x), selected: ROLES.selFinding === i, pick: () => selectRoleFinding(i) }));
});
EXPLAIN_SOURCES.push(code => { const D = inRoles() ? rolesData() : null; return D && D.explain ? D.explain[code] || null : null; });
EVIDENCE_SOURCES.push(() => { const D = inRoles() ? rolesData() : null; return D ? [D.evidence.level] : []; });
function selectRoleFinding(i) {
  const D = rolesData(), x = D.issues[i]; ROLES.selFinding = i; st.selFinding = -1; st.selMessage = "roles:" + i;
  const net = roleFindingNet(x), ni = net ? S.nets.indexOf(net) : -1; st.selNet = ni; st.selComp = -1; if (ni >= 0) shareNet(net);
  const place = roleFindingPlace(x);
  const ex = explanationOf(x.code);
  showInfo(`<b>${esc(x.code)}</b> · ${esc(x.severity)}<br>${esc(x.message)}<br>Where: ${esc(x.where || "the board")}` + (place ? "" : "<br><i>No position on this board.</i>") +
    (x.hint ? `<br><i>Next:</i> ${esc(x.hint)}` : "") + `<br>Source: ${esc(roleSource(x))} · evidence ${esc(rolesEvidence())}` + (ex ? `<br><small>${esc(ex.meaning)}</small>` : ""), { source: roleSource(x), evidence: rolesEvidence() });
  if (place) { const m = 6; fit([place.at[0] - m, place.at[1] - m, place.at[0] + m, place.at[1] + m], true); }
  buildMessages(); selectionChanged(); if (!place) draw();
}
function pickRoleFinding(X, Y) {
  const D = inRoles() ? rolesData() : null; if (!D || !st.checks) return false; let best = -1, bd = 9;
  D.issues.forEach((x, i) => { const p = roleFindingPlace(x); if (!p) return; const [sx, sy] = w2s(p.at[0], p.at[1]), d = Math.hypot(sx - X, sy - Y); if (d <= bd) { bd = d; best = i; } });
  if (best < 0) return false; selectRoleFinding(best); return true;
}
MARKER_PICKS.push(pickRoleFinding);

// ---- overlays on the board
OVERLAYS.push({ id: "role-loops", name: "Loop areas", color: roleColorSafe("switch_node"), applies: inRoles, on: () => ROLES.ov.loops, toggle: () => { ROLES.ov.loops = !ROLES.ov.loops; draw(); } });
OVERLAYS.push({ id: "role-measures", name: "Measures", color: "#00e08a", applies: inRoles, on: () => ROLES.ov.measures, toggle: () => { ROLES.ov.measures = !ROLES.ov.measures; draw(); } });
OVERLAYS.push({ id: "role-corridors", name: "Corridors", color: "#35c26a", applies: inRoles, on: () => ROLES.ov.corridors, toggle: () => { ROLES.ov.corridors = !ROLES.ov.corridors; draw(); } });
OVERLAYS.push({ id: "role-locked", name: "Locked copper", color: "#e6e6e6", applies: inRoles, on: () => ROLES.ov.locked, toggle: () => { ROLES.ov.locked = !ROLES.ov.locked; draw(); } });
OVERLAYS.push({ id: "role-copper", name: "Role copper", color: roleColorSafe("power"), applies: inRoles, on: () => ROLES.ov.copper, toggle: () => { ROLES.ov.copper = !ROLES.ov.copper; draw(); } });
function roleColorSafe(kind) { return THEME_DATA.roles.dark[kind]; }
function corridorPrims() {   // the rule areas named role.corridor.<group>.<net> (c0243, c0244; task 0.1)
  if (ROLES.caches.has("corridors")) return ROLES.caches.get("corridors");
  const out = S.prims.filter(pr => pr[1] === "h" && /role\.corridor\./.test(String(pr[5] || ""))); ROLES.caches.set("corridors", out); return out;
}
function lockedPrims() {
  if (ROLES.caches.has("locked")) return ROLES.caches.get("locked");
  const D = rolesData(), want = new Set(); if (D && D.locked) for (const [kind, nums] of Object.entries(D.locked)) for (const n of nums) want.add(`${kind.replace(/s$/, "")} ${n}`);
  const out = S.prims.filter(pr => want.has(String(pr[5] || ""))); ROLES.caches.set("locked", out); return out;
}
function roleCopperCache(category) {   // the copper of the nets of one role kind (or state), per layer
  const key = `${ROLES.view}:${category}`; if (ROLES.caches.has(key)) return ROLES.caches.get(key);
  const D = rolesData(), of = new Map(); for (const r of D.roles) of.set(S.nets.indexOf(r.net), ROLES.view === "state" ? r.state : r.kind);
  const m = new Map(); for (const l of S.layers) m.set(l.id, newCache());
  for (const pr of S.prims) if (pr[3] >= 0 && of.get(pr[3]) === category) { const c = m.get(pr[0]); if (c) addPrim(c, pr); }
  ROLES.caches.set(key, m); return m;
}
const STATE_COLOR = { confirmed: "#7ee787", declared: "#5aa6ff", inferred: "#e3b341" };
function hatchPoly(pts, color, angle, alpha) {   // a polygon in world units, hatched at its role's angle
  if (pts.length < 3) return; const path = new P2D(); pts.forEach((p, k) => k ? path.lineTo(p[0], p[1]) : path.moveTo(p[0], p[1])); path.closePath();
  ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.globalAlpha = alpha * 0.18; ctx.fill(path); ctx.globalAlpha = alpha; ctx.clip(path);
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), step = 6 / view.s, span = (x1 - x0) + (y1 - y0);
  ctx.strokeStyle = color; ctx.lineWidth = 1 / view.s; ctx.beginPath();
  if (angle === 90 || angle === 0) { for (let t = (angle ? x0 : y0); t <= (angle ? x1 : y1); t += step) { if (angle) { ctx.moveTo(t, y0); ctx.lineTo(t, y1); } else { ctx.moveTo(x0, t); ctx.lineTo(x1, t); } } }
  else { const s = angle === 135 ? -1 : 1; for (let t = -span; t <= span; t += step) { ctx.moveTo(x0 + t, s > 0 ? y0 : y1); ctx.lineTo(x0 + t + span, s > 0 ? y0 + span : y1 - span); } }
  ctx.stroke(); ctx.restore(); ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.lineWidth = 1.6 / view.s; ctx.stroke(path); ctx.globalAlpha = 1;
}
function label(text, x, y, color) { ctx.setTransform(dpr, 0, 0, dpr, 0, 0); const [X, Y] = w2s(x, y); ctx.font = "600 12px ui-monospace, monospace"; const w = ctx.measureText(text).width;
  ctx.fillStyle = "#000000cc"; ctx.fillRect(X + 8, Y - 18, w + 10, 18); ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.strokeRect(X + 8.5, Y - 17.5, w + 9, 17); ctx.fillStyle = color; ctx.fillText(text, X + 13, Y - 5); worldTf(); }
function drawRoleOverlays() {
  if (!inRoles()) return; const D = rolesData(); if (!D) return; worldTf(); const ord = order();
  if (ROLES.ov.copper && ROLES.view !== "layers") {
    const cats = ROLES.view === "state" ? Object.keys(STATE_COLOR) : ROLE_ORDER.filter(k => k !== "signal");
    const sel = st.selNet >= 0, other = HL_ALPHA[st.hl] ?? HL_ALPHA.dim;
    for (const cat of cats) { const m = roleCopperCache(cat), color = ROLES.view === "state" ? STATE_COLOR[cat] : roleColor(cat);
      for (const [l, a] of ord) if (l.kind === "copper" || l.id.endsWith(".Cu")) paintCache(ctx, m.get(l.id), l.id, color, (sel ? other : 1) * a * 0.85, view.s); }
    if (sel) { const mm = selCache(netCache, st.selNet, pr => pr[3] === st.selNet); const kind = roleOf(S.nets[st.selNet]);
      for (const [l] of ord) paintCache(ctx, mm.get(l.id), l.id, kind ? lighten(roleColor(kind), 0.25) : lighten(layerColor(l), 0.45), 1, view.s); }
  }
  if (ROLES.ov.corridors) for (const pr of corridorPrims()) { if (!vis.get(pr[0])) continue; for (const r of pr[2]) { const pts = []; for (let i = 0; i + 1 < r.length; i += 2) pts.push([r[i], r[i + 1]]); hatchPoly(pts, "#35c26a", 45, 0.9); }
    const b = bboxOf(pr); if (b) label(String(pr[5]).replace(/^.*?(role\.corridor\.[^:\s]+).*$/, "$1"), b[0], b[1], "#35c26a"); }
  if (ROLES.ov.locked) { ctx.setLineDash([4 / view.s, 3 / view.s]); ctx.strokeStyle = "#e6e6e6"; ctx.lineWidth = 1.2 / view.s;
    for (const pr of lockedPrims()) { const b = bboxOf(pr); if (!b) continue; ctx.strokeRect(b[0], b[1], b[2] - b[0], b[3] - b[1]); label("locked", b[2], b[1], "#e6e6e6"); } ctx.setLineDash([]); }
  if (ROLES.ov.loops) for (const gr of groupsOf()) {
    const m = groupMeasure(gr.g.name), pads = m ? m.values.pads : gr.pads, pts = pads.map(padAt).filter(Boolean).map(p => [p.x, p.y]); if (pts.length < 3) continue;
    const chosen = ROLES.sel && ROLES.sel.kind === "group" && ROLES.sel.name === gr.g.name || (st.selNet >= 0 && netOfGroup(gr.g.name) === S.nets[st.selNet]);
    const kind = GROUP_KIND[gr.kind]; hatchPoly(pts, roleColor(kind), THEME_DATA.hatch[kind] ?? 45, chosen ? 1 : 0.45);
    if (m && m.values.open) { ctx.strokeStyle = "#ff7b72"; ctx.lineWidth = 1.5 / view.s; ctx.setLineDash([3 / view.s, 2 / view.s]); ctx.beginPath();
      for (const [a, b] of m.values.open) { const p = padAt(a), q = padAt(b); if (p && q) { ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); } } ctx.stroke(); ctx.setLineDash([]); }
    if (chosen && m) { const c = centroid(pads); if (c) label(`${gr.g.name} ${fmtArea(m.values.area_nm2)} · bound ${fmtArea(m.values.bound_nm2)} · ratio ${(m.values.ratio_permille / 1000).toFixed(2)}`, c[0], c[1], roleColor(kind)); }
  }
  if (ROLES.ov.measures) for (const m of D.measures) {
    if ((m.kind === "attachment" || m.kind === "gate_return") && m.values.points) m.values.points.forEach((p, k) => { const x = p[0] / 1e6, y = p[1] / 1e6;
      ctx.strokeStyle = "#00e08a"; ctx.lineWidth = 1.5 / view.s; ctx.beginPath(); ctx.arc(x, y, 4 / view.s, 0, 2 * Math.PI); ctx.stroke();
      if (m.values.offsets && m.values.offsets[k] != null) label(`t = ${fmtNm(m.values.offsets[k])}`, x, y, "#00e08a"); });
  }
  if (st.checks) D.issues.forEach((x, i) => { const p = roleFindingPlace(x); if (!p) return; const sel = i === ROLES.selFinding, r = (sel ? 9 : 6) / view.s, [cx, cy] = p.at;
    ctx.strokeStyle = SEV_COLOR[x.severity] || "#ccc"; ctx.lineWidth = (sel ? 2.5 : 1.6) / view.s; ctx.beginPath(); ctx.moveTo(cx, cy - r); ctx.lineTo(cx + r, cy); ctx.lineTo(cx, cy + r); ctx.lineTo(cx - r, cy); ctx.closePath(); ctx.stroke(); });
}

// ---- panel, toolbar and commands
panel("netroles", "Net Roles", $("pNetRoles"), { applies: inRoles, shown: () => buildRoles() });
for (const b of document.querySelectorAll("[data-rtab]")) b.onclick = () => { ROLES.tab = b.dataset.rtab; buildRoles(); };
$("roleFilter").oninput = () => buildRoles();
$("rolesView").onchange = e => { ROLES.view = e.target.value; ROLES.caches.clear(); draw(); };
command({ id: "window.panel-netroles", menu: "Window", group: "panels", sub: "Panels", label: "Net Roles", when: inRoles, run: () => { if (findPanel("netroles")) closePanel("netroles"); else showPanel("netroles", true); }, checked: () => !!findPanel("netroles") });
const afterScene0 = afterScene;
afterScene = function () {   // the workspace follows each scene: --workspace roles at start, the roles of each new board
  afterScene0();
  if (S && !S.kind && S.prims && !LIB && (st.workspace === "roles" || (SETTINGS.workspace === "roles" && !ROLES.entered))) enterRoles();
};
command({ id: "roles.workspace", menu: "Roles", group: "workspace", label: "Net Roles Workspace", when: () => !!(S && !S.kind && S.prims && !LIB) && WS !== "roles", run: () => enterRoles() });
command({ id: "window.workspace-roles", menu: "Window", group: "workspace", sub: "Workspace", label: "Net Roles", when: () => !!(S && !S.kind && S.prims && !LIB), run: () => enterRoles(), checked: () => WS === "roles" });
command({ id: "window.workspace-board", menu: "Window", group: "workspace", sub: "Workspace", label: "Board", when: () => WS === "roles", run: () => leaveRoles(), checked: () => WS === "board" });
command({ id: "roles.view-roles", menu: "Roles", group: "view", sub: "Roles View", label: "Role Colours", when: inRoles, run: () => { $("rolesView").value = "roles"; $("rolesView").onchange({ target: $("rolesView") }); }, checked: () => ROLES.view === "roles" });
command({ id: "roles.view-state", menu: "Roles", group: "view", sub: "Roles View", label: "Confirmation", when: inRoles, run: () => { $("rolesView").value = "state"; $("rolesView").onchange({ target: $("rolesView") }); }, checked: () => ROLES.view === "state" });
command({ id: "roles.view-layers", menu: "Roles", group: "view", sub: "Roles View", label: "Layer Colours", when: inRoles, run: () => { $("rolesView").value = "layers"; $("rolesView").onchange({ target: $("rolesView") }); }, checked: () => ROLES.view === "layers" });
