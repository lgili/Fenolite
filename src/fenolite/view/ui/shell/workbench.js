// ================================================================== the workbench: panels, toolbar, status, grid and crosshair (change c0245)
// ---- commands that only menus and the toolbar reach
const runSvg = $("bSvg").onclick, runLink = $("bLink").onclick;
function clearSelection() { st.mpts = []; st.selOv = -1; if (isSch()) schSelect(-1); else select(null); }
function downloadMarks() { download(JSON.stringify({ schema: "fenolite.review.v0", marks: MARKS }, null, 2) + "\n", "review.json", "application/json"); }
command({ id: "file.svg", menu: "File", group: "export", label: "Save View as SVG", hint: "the view as a vector file", run: () => runSvg() });
command({ id: "file.print", menu: "File", group: "export", label: "Print", hint: "print the view, or save it as PDF from the print dialog", run: () => printView() });
command({ id: "file.link", menu: "File", group: "share", label: "Copy Link to This View", hint: "document, selection, zoom and unit", run: () => runLink() });
command({ id: "file.marks", menu: "File", group: "share", label: "Download Review Marks", when: () => !serverMarks(), run: downloadMarks });
command({ id: "edit.clear-selection", menu: "Edit", label: "Clear Selection", when: onDoc, run: clearSelection });
command({ id: "edit.find", menu: "Edit", group: "find", label: "Find Part or Net", run: () => { if (isNarrow()) setSidebar(false); $("search").focus(); } });
command({ id: "edit.find-similar", menu: "Edit", group: "find", label: "Find Similar", when: () => on2D() && !isSch() && !LIB, run: () => $("bSimilar").click() });
command({ id: "view.grid-next", menu: "View", group: "grid", label: "Next Grid", keys: ["G"], when: () => onDoc() && !isSch(), run: () => stepGrid(1) });
command({ id: "view.grid-prev", menu: "View", group: "grid", label: "Previous Grid", keys: ["Shift+G"], when: () => onDoc() && !isSch(), run: () => stepGrid(-1) });
for (const [mode, label] of [["dim", "Dim Others"], ["mask", "Mask Others"], ["normal", "Normal"]])
  command({ id: "view.highlight-" + mode, menu: "View", group: "highlight", sub: "Highlight", label, when: () => onDoc() && !isSch(), run: () => { $("hlMode").value = mode; $("hlMode").onchange({ target: $("hlMode") }); }, checked: () => st.hl === mode });
for (const name of Object.keys(SETS))
  command({ id: "design.layers-" + name.toLowerCase().replace(/\s+/g, "-"), menu: "Design", group: "layers", sub: "Layer Sets", label: name, when: () => on2D() && !isSch() && !!S.layers, run: () => { for (const l of S.layers) vis.set(l.id, SETS[name](l)); buildTabs(); draw(); } });
command({ id: "roles.workspace", menu: "Roles", label: "Net Roles Workspace", when: () => false, run: () => {} });
command({ id: "route.phases", menu: "Route", label: "Router Phases (after c0243 and c0244)", when: () => false, run: () => {} });
command({ id: "reports.review", menu: "Reports", label: "Project Review", when: () => !!DOC, run: () => setProjectReview(true) });
command({ id: "reports.messages", menu: "Reports", label: "Messages", run: () => showPanel("messages", true) });
command({ id: "window.drawer", menu: "Window", group: "drawer", label: "Show or Hide Panels", when: isNarrow, run: () => setSidebar(!$("app").classList.contains("sidebar-open")) });
command({ id: "window.save-layout", menu: "Window", group: "layout", label: "Save Layout As", hint: "a fenolite.view_layout.v0 file for --layout", run: () => download(JSON.stringify(LAYOUT, null, 2) + "\n", `layout-${WS}.json`, "application/json") });
command({ id: "window.load-layout", menu: "Window", group: "layout", label: "Load Layout", run: () => pickLayout() });
command({ id: "window.reset-layout", menu: "Window", group: "layout", label: "Reset Layout", run: () => { LAYOUT = defaultLayout(WS); saveLayout(); renderDocks(); say("Layout reset."); } });
command({ id: "help.shortcuts", menu: "Help", label: "Keyboard Shortcuts", run: () => showPanel("shortcuts", true) });
command({ id: "help.about", menu: "Help", label: "About This Viewer", run: () => showInfo(aboutHtml()) });
function pickLayout() {
  const f = document.createElement("input"); f.type = "file"; f.accept = ".json,application/json";
  f.onchange = async () => { const file = f.files && f.files[0]; if (!file) return;
    try { const l = normalizeLayout(JSON.parse(await file.text()), WS); if (!l) throw new Error("not a fenolite.view_layout.v0 file");
      LAYOUT = l; saveLayout(); renderDocks(); say(`Layout ${file.name} loaded.`); }
    catch (e) { say(`Layout not loaded: ${e.message}`); } };
  f.click();
}
function aboutHtml() {
  return `<b>Fenolite viewer</b><br>An offline page: it loads nothing and writes only what you ask for.<br>Keymap: ${esc(KEYMAP)} · workspace: ${esc(WS)}` +
    (S && S.meta ? `<br>Document read by the ${esc(S.meta.backend || "?")} backend, evidence ${esc(S.meta.evidence || "?")}.` : "");
}

// ---- panels
panel("projects", "Projects", $("pProjects"));
panel("pcb", "PCB", $("pPcb"), { applies: () => !!(S && S.kind !== "table" && !isSch() && !LIB) });
panel("navigator", "Navigator", $("pNavigator"), { applies: () => isSch() && !LIB });
panel("library", "Library", $("pLibrary"), { applies: () => !!LIB });
panel("layers", "Layers", $("pLayers"), { applies: () => !!(S && S.layers && S.kind !== "table" && !isSch()) });
panel("findings", "Findings", $("pFindings"), { applies: () => !!(S && S.kind !== "table") });
panel("changes", "Changes", $("pChanges"), { applies: () => !!(S && S.diff) });
panel("marks", "Marks", $("pMarks"));
panel("notes", "Notes", $("pNotes"));
panel("shortcuts", "Shortcuts", $("pShortcuts"), { shown: () => buildKeyTable() });
panel("properties", "Properties", $("pProperties"));
panel("messages", "Messages", $("pMessages"));
function panelMenu(id, anchor) {
  const at = findPanel(id), here = at ? at[0] : null, items = [];
  for (const d of DOCKS) if (d !== here) items.push({ label: `Move to ${d[0].toUpperCase() + d.slice(1)} Dock`, run: () => movePanel(id, d, 0) });
  if (at && at[2].panels.length > 1) items.push({ label: "Move to a New Group", run: () => movePanel(id, here, null) });
  if (LIVE && !FLOAT && PANELS.get(id).floats) items.push({ label: "Float in a Window", run: () => floatPanel(id) });
  items.push({ sep: true }, { label: `Close ${PANELS.get(id).title}`, run: () => closePanel(id) });
  openMenu(items, anchor, { label: `${PANELS.get(id).title} panel`, refocus: anchor });
}
for (const id of PANELS.keys())
  command({ id: "window.panel-" + id, menu: "Window", group: "panels", sub: "Panels", label: PANELS.get(id).title, run: () => { if (findPanel(id)) closePanel(id); else showPanel(id, true); }, checked: () => !!findPanel(id) });
function buildKeyTable() {
  const body = $("keyTable").tBodies[0]; body.innerHTML = "";
  for (const name of MENUS) for (const c of COMMANDS) {
    if (c.menu !== name) continue; const keys = keysOf(c); if (!keys.length) continue;
    const tr = document.createElement("tr"); tr.innerHTML = `<td>${esc(name)} ▸ ${c.sub ? esc(c.sub) + " ▸ " : ""}${esc(c.label)}</td><td>${keys.map(k => `<kbd>${esc(keyLabel(k))}</kbd>`).join(" ")}</td>`; body.appendChild(tr);
  }
}

// ---- the toolbar: each button runs its command; its tooltip names the command and its key
function decorateToolbar() {
  for (const b of $("top").querySelectorAll("button[data-cmd]")) {
    const c = CMD.get(b.dataset.cmd); if (!c) continue;
    if (b.dataset.icon) { const label = b.querySelector(".lbl") ? b.querySelector(".lbl").textContent : b.textContent.trim(); b.innerHTML = icon(b.dataset.icon) + `<span class="lbl">${esc(label)}</span>`; }
    const key = keysOf(c)[0];
    b.title = c.label + (key ? ` (${keyLabel(key)})` : "") + (c.hint ? ` — ${c.hint}` : ""); b.setAttribute("aria-label", c.label);
    b.onclick = e => { if (c.when()) c.run(e); };
  }
}

// ---- the dot grid of a board, and the grid choice (decision 6)
const GRIDS = { mm: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5], mil: [1, 5, 10, 25, 50, 100] };
let GRID = (() => { try { const g = JSON.parse(localStorage.getItem("fenolite.view.grid") || "null"); if (g && GRIDS[g.unit] && GRIDS[g.unit].includes(g.step)) return g; } catch (e) { /* none kept */ } return { unit: "mm", step: 0.5 }; })();
const gridMM = () => GRID.unit === "mil" ? GRID.step * MIL_MM : GRID.step;
function gridText() { return `Grid ${GRID.step} ${GRID.unit}`; }
function buildGridSel() {
  const sel = $("gridSel"), unit = UNIT; sel.innerHTML = "";
  if (GRID.unit !== unit) { const mm = gridMM(), list = GRIDS[unit]; let best = list[0]; for (const s of list) if (Math.abs((unit === "mil" ? s * MIL_MM : s) - mm) < Math.abs((unit === "mil" ? best * MIL_MM : best) - mm)) best = s; GRID = { unit, step: best }; }
  for (const s of GRIDS[unit]) { const o = document.createElement("option"); o.value = String(s); o.textContent = `Grid ${s} ${unit}`; sel.appendChild(o); }
  sel.value = String(GRID.step); $("sGrid").textContent = isSch() || !S || S.kind === "table" ? "" : gridText();
}
function setGrid(step) { GRID = { unit: UNIT, step }; try { localStorage.setItem("fenolite.view.grid", JSON.stringify(GRID)); } catch (e) { /* this page only */ } buildGridSel(); draw(); }
function stepGrid(dir) { const list = GRIDS[UNIT], i = list.indexOf(GRID.step); setGrid(list[Math.max(0, Math.min(list.length - 1, (i < 0 ? 3 : i) + dir))]); }
$("gridSel").onchange = e => setGrid(Number(e.target.value));
function drawDotGrid() {   // dots at the grid, or at a multiple of it that keeps them 10 px apart or more
  if (!S || isSch() || S.kind === "table") return;
  let step = gridMM(); if (!(step > 0)) return;
  for (const k of [2, 2.5, 2, 2, 2.5, 2, 2, 2.5, 2]) { if (step * view.s >= 10) break; step *= k; }
  if (step * view.s < 10) return;
  const [ax, ay] = s2w(0, 0), [bx, by] = s2w(W, H), x0 = Math.min(ax, bx), x1 = Math.max(ax, bx), y0 = Math.min(ay, by), y1 = Math.max(ay, by);
  const th = S.theme || {}; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = th.grid || "#4a5060";
  const d = Math.max(1, Math.round(dpr)) / dpr;
  for (let gx = Math.ceil(x0 / step) * step; gx <= x1; gx += step) for (let gy = Math.ceil(y0 / step) * step; gy <= y1; gy += step) {
    const [X, Y] = w2s(gx, gy); ctx.fillRect(Math.round(X * dpr) / dpr - d / 2, Math.round(Y * dpr) / dpr - d / 2, d, d);
  }
  worldTf();
}

// ---- the overlay canvas: crosshair and cursor readout, drawn without redrawing the board (decision 7)
const ovc = $("ov"), octx = ovc.getContext("2d");
function sizeOverlay() { ovc.width = cv.width; ovc.height = cv.height; drawCursor(); }
function drawCursor() {
  octx.setTransform(1, 0, 0, 1, 0, 0); octx.clearRect(0, 0, ovc.width, ovc.height);
  if (!S || S.kind === "table" || st.mode3d || !st.mouse || !st.inside) return;
  const [X, Y] = w2s(st.mouse[0], st.mouse[1]); octx.setTransform(dpr, 0, 0, dpr, 0, 0);
  octx.strokeStyle = "#9aa4b866"; octx.lineWidth = 1; octx.beginPath();
  const x = Math.round(X) + 0.5, y = Math.round(Y) + 0.5; octx.moveTo(x, 0); octx.lineTo(x, H); octx.moveTo(0, y); octx.lineTo(W, y); octx.stroke();
  if (typeof drawOverlayTools === "function") drawOverlayTools();
}
cv.addEventListener("mouseenter", () => { st.inside = true; });
cv.addEventListener("mouseleave", () => { st.inside = false; drawCursor(); });

// ---- the status bar
const EVIDENCE_ORDER = ["ALTIUM-VERIFIED(kit)", "KICAD-VERIFIED", "ORACLE-VERIFIED", "CORPUS-VERIFIED", "ALTIUM-VERIFIED(author-report)", "INFERRED", "UNKNOWN", "UNVERIFIED"];
function evidenceRank(label) {   // higher is weaker; an unknown label is the weakest
  const t = String(label || "").trim(); if (!t) return -1;
  let i = EVIDENCE_ORDER.indexOf(t); if (i < 0) i = EVIDENCE_ORDER.indexOf(t.replace(/\(.*$/, "")); return i < 0 ? EVIDENCE_ORDER.length : i;
}
function lowestEvidence(labels) { let worst = null, r = -1; for (const l of labels) { const k = evidenceRank(l); if (k > r) { r = k; worst = String(l); } } return worst; }
function shownEvidence() {   // every evidence label of what the screen shows (decision 9, M8)
  const out = []; if (!S) return out;
  if (S.meta && S.meta.evidence) out.push(S.meta.evidence);
  if (S.check && st.checks) for (const x of S.check.findings) if (x.evidence) out.push(x.evidence);
  for (const extra of EVIDENCE_SOURCES) for (const l of extra()) out.push(l);
  return out;
}
const EVIDENCE_SOURCES = [];
const BACKEND_NAME = { kicad: "KiCad", altium: "Altium", catalog: "Catalog" };
function updateStatus() {
  EVIDENCE_KEY = ""; evidenceStatus();
  $("sNet").textContent = selectedNetText();
  $("titleState").textContent = DOC && DOC.kind ? `[${DOC.kind}${LIVE ? " · live" : ""}]` : "";
  buildGridSel();
}
function selectedNetText() {
  if (!S || S.kind === "table") return "";
  const name = isSch() ? (SCH.selNet >= 0 && S.nets ? S.nets[SCH.selNet] : null) : (st.selNet >= 0 && S.nets ? S.nets[st.selNet] : null);
  if (!name) return "";
  const role = typeof roleOf === "function" ? roleOf(name) : null;
  return `Net ${typeof name === "string" ? name : name.name || ""}${role ? " · " + role : ""}`;
}
function updateDelta(x, y) {
  const o = st.origin; $("sDelta").textContent = o ? `dx ${fmtNum(x - o[0])} dy ${fmtNum(isSch() ? o[1] - y : y - o[1])}` : "";
}
function fmtNum(mm) { return UNIT === "mil" ? (mm / MIL_MM).toFixed(1) : mm.toFixed(2); }

// ---- the net drop-down of the toolbar
function buildNetSel() {
  const sel = $("netSel"); sel.innerHTML = '<option value="">Net: none</option>';
  if (!S || isSch() || S.kind === "table" || !S.nets || LIB) return;
  const order = S.nets.map((n, i) => [n, i]).filter(([n]) => n).sort((a, b) => natural(a[0], b[0]));
  for (const [n, i] of order) { const o = document.createElement("option"); o.value = String(i); o.textContent = `Net: ${n}`; sel.appendChild(o); }
  sel.value = st.selNet >= 0 ? String(st.selNet) : "";
}
$("netSel").onchange = e => { const v = e.target.value; if (v === "") clearSelection(); else selectNetAt(Number(v)); $("netSel").blur(); };

// ---- the Layers panel: the board's layers with visibility, and the overlay layers
const OVERLAYS = [];   // { id, name, color, applies(), on(), toggle() }
OVERLAYS.push({ id: "checks", name: "Check markers", color: "#ff7b72", applies: () => !!(S && S.check), on: () => st.checks, toggle: () => { st.checks = !st.checks; draw(); } });
OVERLAYS.push({ id: "changes", name: "Changes", color: "#35e06b", applies: () => !!(S && S.diff), on: () => st.diff, toggle: () => { st.diff = !st.diff; draw(); } });
function layerRow(name, color, on, cur, onToggle, onPick, hatch) {
  const row = document.createElement("div"); row.className = "lrow" + (cur ? " cur" : "") + (on ? "" : " off"); row.setAttribute("role", "listitem");
  row.innerHTML = `<span class="sw" style="background:${esc(color)}${hatch ? ";background-image:repeating-linear-gradient(45deg,#0007 0 2px,transparent 2px 4px)" : ""}"></span><span class="lname">${esc(name)}</span><button class="leye" aria-pressed="${on}" aria-label="${on ? "Hide" : "Show"} ${esc(name)}" title="${on ? "Hide" : "Show"}">${icon(on ? "eye" : "eyeOff")}</button>`;
  row.querySelector(".leye").onclick = e => { e.stopPropagation(); onToggle(); };
  if (onPick) row.onclick = onPick; return row;
}
function buildLayers() {
  const list = $("layerList"), ovl = $("overlayList"); list.innerHTML = ""; ovl.innerHTML = "";
  if (!S || !S.layers || isSch()) return;
  for (const l of tabLayers()) list.appendChild(layerRow(l.name, l.color, !!vis.get(l.id), l.id === st.cur, () => { vis.set(l.id, !vis.get(l.id)); buildTabs(); draw(); }, () => setCurrent(l.id)));
  const shown = OVERLAYS.filter(o => o.applies());
  for (const o of shown) ovl.appendChild(layerRow(o.name, o.color, o.on(), false, () => { o.toggle(); buildLayers(); }, null, true));
  if (!shown.length) ovl.innerHTML = '<div class="notes">No overlay on this document.</div>';
}

// ---- hooks: the workbench follows each scene, selection, layer and unit change
const loadScene0 = loadScene, buildTabs0 = buildTabs, showCoord0 = showCoord, setUnit0 = setUnit, measure0 = measure, buildFindings0 = buildFindings;
loadScene = function (scene, keepView) { loadScene0(scene, keepView); afterScene(); };
buildTabs = function () { buildTabs0(); const cur = S && S.layers ? S.layers.find(l => l.id === st.cur) : null; $("cur").textContent = cur ? `Layer ${cur.name}${st.single ? " (single)" : ""}` : ""; buildLayers(); };
showCoord = function (x, y) { showCoord0(x, y); updateDelta(x, y); drawCursor(); };
setUnit = function (u) { setUnit0(u); buildGridSel(); if (st.mouse) updateDelta(st.mouse[0], st.mouse[1]); };
measure = function () { measure0(); sizeOverlay(); };
buildFindings = function () { buildFindings0(); $("ovEmpty").hidden = $("overlays").childElementCount > 0; };
function afterScene() {
  if (DOCS_BC && !FLOAT && DOC) DOCS_BC.postMessage({ doc: DOC.id });
  setWorkspace(workspaceOf()); renderDocks(); buildNetSel(); buildLayers(); buildMessages(); updateStatus();
  if (S && S.kind === "table") { $("cur").textContent = ""; $("coord").textContent = ""; }
}
window.addEventListener("mouseup", e => { if (e.target === cv && S && st.mouse && !st.mode3d) { st.origin = [st.mouse[0], st.mouse[1]]; updateDelta(st.mouse[0], st.mouse[1]); } });
function selectionStatus() {   // the net of the selection in the status bar and the Net drop-down; called after each draw
  if (!S) return; const t = selectedNetText(); if ($("sNet").textContent !== t) $("sNet").textContent = t;
  if (!isSch() && S.nets && !LIB) { const v = st.selNet >= 0 ? String(st.selNet) : ""; if ($("netSel").value !== v && document.activeElement !== $("netSel")) $("netSel").value = v; }
}
let EVIDENCE_KEY = "", EVIDENCE_VERSION = 0;   // a new evidence source (role findings) bumps the version
function evidenceStatus() { const k = [S && S.meta && S.meta.name, S && S.check ? S.check.findings.length : 0, st.checks, EVIDENCE_VERSION].join("|");
  if (k === EVIDENCE_KEY) return; EVIDENCE_KEY = k; const labels = shownEvidence(), ev = lowestEvidence(labels); $("sEvidence").textContent = ev ? `evidence ${ev}` : "";
  const tools = new Set(); for (const l of labels) { const m = /\(([^)]*\d[^)]*)\)/.exec(String(l)); if (m) tools.add(m[1]); }   // a checking tool with its version
  $("sTool").textContent = S && S.meta ? [BACKEND_NAME[S.meta.backend] || S.meta.backend || "", ...tools].filter(Boolean).join(" · ") : "";
  $("sTool").title = `The tool that read the document${tools.size ? " and the tools that checked it" : ""}; Fenolite ${FENOLITE_VERSION}`; }
SELECTION_VIEWS.push(() => selectionStatus());
SELECTION_VIEWS.push(() => { if (S && !S.kind && S.prims && !LIB) buildReview(); });   // the highlight of the Components and Nets lists
SELECTION_VIEWS.push(() => buildMessages());
const draw0 = draw;
draw = function () { draw0(); selectionChanged(); evidenceStatus(); };

// ---- start the workbench before the first document opens
buildMenubar(); decorateToolbar(); setWorkspace("board", true); buildGridSel();
