// ================================================================== docked panels and layouts (change c0245)
// Panels live in tabbed groups in three docks: left, right and bottom (design, decision 4). A panel body
// is one element that moves between groups; panels that do not apply to the document shown leave their
// group's tabs. The layout of each workspace is a `fenolite.view_layout.v0` document, kept in the browser,
// saved and read as a file, and restored by Window ▸ Reset Layout.
const PANELS = new Map();
function panel(id, title, body, opts = {}) {
  const p = { id, title, body, applies: opts.applies || (() => true), shown: opts.shown || null, floats: opts.floats !== false };
  body.classList.add("panel-body"); body.dataset.panel = id; PANELS.set(id, p); $("panelStore").appendChild(body); return p;
}
const LAYOUT_SCHEMA = "fenolite.view_layout.v0";
const DOCKS = ["left", "right", "bottom"];
const DOCK_EL = { left: "side", right: "dockRight", bottom: "dockBottom" };
const DOCK_SIZE = { left: [160, 600, 260], right: [160, 600, 240], bottom: [60, 600, 132] };   // min, max, default (CSS px)
const WORKSPACES = ["board", "sheet", "library", "drawing", "table", "roles"];
function defaultLayout(ws) {
  const g = (panels, size, active) => ({ panels, active: active || panels[0], size, collapsed: false });
  const left = ws === "roles"
    ? [g(["netroles"], 3), g(["layers", "projects", "findings"], 2)]
    : [g(["projects"], 2), g(["pcb", "navigator", "library", "layers", "findings"], 3)];
  const docks = {
    left: { size: DOCK_SIZE.left[2], groups: left },
    right: { size: DOCK_SIZE.right[2], groups: [g(["properties"], 3), g(["notes", "shortcuts"], 1)] },
    bottom: { size: DOCK_SIZE.bottom[2], groups: [g(["messages", "pending", "changes", "marks"], 1)] } };
  for (const d of DOCKS) docks[d].groups = docks[d].groups.map(x => ({ ...x, panels: x.panels.filter(id => PANELS.has(id)) }))
    .filter(x => x.panels.length).map(x => ({ ...x, active: x.panels.includes(x.active) ? x.active : x.panels[0] }));
  return { schema: LAYOUT_SCHEMA, workspace: ws, docks, closed: CLOSED_FIRST.filter(id => PANELS.has(id)) };
}
const CLOSED_FIRST = ["keyboard"];   // panels that start closed, and the dock and group they open in
const PANEL_HOME = { keyboard: ["right", 1] };
let WS = "board", LAYOUT = null, GIVEN_LAYOUT = null;
function workspaceOf() {
  if (!S || !DOC) return WS;
  if (S.kind === "table") return "table";
  if (DOC.kind === "draftsman") return "drawing";
  if (LIB) return "library";
  if (S.kind === "schematic") return "sheet";
  return st.workspace === "roles" ? "roles" : "board";
}
function layoutKey(ws) { return "fenolite.view.layout." + ws; }
function normalizeLayout(raw, ws) {   // a layout read from storage or a file: unknown panels dropped, missing ones added back
  if (!raw || typeof raw !== "object" || raw.schema !== LAYOUT_SCHEMA || !raw.docks || typeof raw.docks !== "object") return null;
  const def = defaultLayout(ws), seen = new Set(), out = { schema: LAYOUT_SCHEMA, workspace: ws, docks: {}, closed: [] };
  for (const d of DOCKS) {
    const src = raw.docks[d] || {}, [lo, hi, size0] = DOCK_SIZE[d];
    const size = Number.isFinite(src.size) ? Math.round(Math.min(hi, Math.max(lo, src.size))) : size0;
    const groups = [];
    for (const g of Array.isArray(src.groups) ? src.groups : []) {
      if (!g || !Array.isArray(g.panels)) continue;
      const panels = g.panels.filter(id => typeof id === "string" && PANELS.has(id) && !seen.has(id));
      panels.forEach(id => seen.add(id));
      if (!panels.length) continue;
      groups.push({ panels, active: panels.includes(g.active) ? g.active : panels[0], size: Number.isFinite(g.size) && g.size > 0 ? Math.min(g.size, 100) : 1, collapsed: !!g.collapsed });
    }
    out.docks[d] = { size, groups };
  }
  for (const id of Array.isArray(raw.closed) ? raw.closed : []) if (typeof id === "string" && PANELS.has(id) && !seen.has(id)) { out.closed.push(id); seen.add(id); }
  for (const d of DOCKS) for (const [gi, g] of def.docks[d].groups.entries()) for (const id of g.panels) if (!seen.has(id)) {   // a panel the file does not know
    const target = out.docks[d].groups[Math.min(gi, out.docks[d].groups.length - 1)];
    if (target) target.panels.push(id); else out.docks[d].groups.push({ panels: [id], active: id, size: 1, collapsed: false });
    seen.add(id);
  }
  return out;
}
function loadLayout(ws) {
  if (GIVEN_LAYOUT && GIVEN_LAYOUT.workspace === ws) { const l = normalizeLayout(GIVEN_LAYOUT, ws); if (l) return l; }
  try { const l = normalizeLayout(JSON.parse(localStorage.getItem(layoutKey(ws)) || "null"), ws); if (l) return l; } catch (e) { /* no storage */ }
  return defaultLayout(ws);
}
function saveLayout() { try { localStorage.setItem(layoutKey(WS), JSON.stringify(LAYOUT)); } catch (e) { /* this page only */ } }
function setWorkspace(ws, force) {
  if (!force && ws === WS && LAYOUT) return;
  WS = ws; LAYOUT = loadLayout(ws); document.body.dataset.workspace = ws; renderDocks();
}
function findPanel(id) {   // [dock, group index, group] of a panel, or null when it is closed
  for (const d of DOCKS) { const gs = LAYOUT.docks[d].groups; for (let i = 0; i < gs.length; i++) if (gs[i].panels.includes(id)) return [d, i, gs[i]]; }
  return null;
}
function detach(id) {
  const at = findPanel(id); if (!at) { LAYOUT.closed = LAYOUT.closed.filter(x => x !== id); return; }
  const [d, i, g] = at; g.panels = g.panels.filter(x => x !== id); if (g.active === id) g.active = g.panels[0];
  if (!g.panels.length) LAYOUT.docks[d].groups.splice(i, 1);
}
function movePanel(id, dock, gi) {   // into group `gi` of `dock`, or a new group at its end when gi is null
  detach(id); const gs = LAYOUT.docks[dock].groups;
  if (gi == null || !gs[gi]) gs.push({ panels: [id], active: id, size: 1, collapsed: false });
  else { gs[gi].panels.push(id); gs[gi].active = id; gs[gi].collapsed = false; }
  saveLayout(); renderDocks(); focusPanel(id);
}
function closePanel(id) { detach(id); LAYOUT.closed.push(id); saveLayout(); renderDocks(); }
function showPanel(id, focus) {   // open (where it was by default when closed), make active, uncollapse
  let at = findPanel(id);
  if (!at) {
    LAYOUT.closed = LAYOUT.closed.filter(x => x !== id);
    const def = defaultLayout(WS); let [home, hg] = PANEL_HOME[id] || ["left", 0];
    for (const d of DOCKS) def.docks[d].groups.forEach((g, i) => { if (g.panels.includes(id)) { home = d; hg = i; } });
    const gs = LAYOUT.docks[home].groups;
    if (gs[hg]) gs[hg].panels.push(id); else gs.push({ panels: [id], active: id, size: 1, collapsed: false });
    at = findPanel(id);
  }
  at[2].active = id; at[2].collapsed = false; saveLayout(); renderDocks();
  if (isNarrow() && focus) setSidebar(true);
  if (focus) focusPanel(id);
}
function focusPanel(id) { const t = document.querySelector(`[data-tab="${id}"]`) || document.querySelector(`[data-head="${id}"]`); if (t) t.focus(); }
const isNarrow = () => matchMedia("(max-width:760px)").matches;
// a panel floated into its own window (served pages only): the same page, showing that panel alone
const FLOAT = LIVE ? new URLSearchParams(location.hash.slice(1)).get("float") : null;
const DOCS_BC = LIVE && "BroadcastChannel" in window ? new BroadcastChannel("fenolite-view-docs") : null;
function floatPanel(id) {
  const w = window.open(`panel/${encodeURIComponent(id)}?doc=${encodeURIComponent(DOC ? DOC.id : "")}`, "fenolite-panel-" + id, "popup,width=460,height=640");
  if (!w) { say("The browser did not open the window."); return; }
  detach(id); renderDocks(); say(`${PANELS.get(id).title} floats in its own window; it returns here when that window closes.`);
  const t = setInterval(() => { if (w.closed) { clearInterval(t); showPanel(id); } }, 500);
}
function groupEl(d, gi, g) {
  const applicable = g.panels.filter(id => PANELS.get(id).applies());
  if (!applicable.length) return null;
  const active = applicable.includes(g.active) ? g.active : applicable[0], p = PANELS.get(active);
  const sec = document.createElement("section"); sec.className = "pgroup" + (g.collapsed ? " collapsed" : ""); sec.dataset.dock = d; sec.dataset.group = gi;
  sec.style.flex = g.collapsed ? "0 0 auto" : `${g.size} 1 0`;
  const bodyId = `pb-${d}-${gi}`;
  sec.innerHTML = `<div class="phead"><button class="ptitle" data-head="${active}" aria-expanded="${!g.collapsed}" aria-controls="${bodyId}" title="Collapse or expand">${esc(p.title)}</button>` +
    `<span class="pact"><button class="pbtn pmenu" aria-haspopup="menu" title="Panel menu: move, float or close">${icon("menu")}</button><button class="pbtn pclose" title="Close ${esc(p.title)}">${icon("close")}</button></span></div>` +
    `<div class="pbody" id="${bodyId}" role="tabpanel"></div>`;
  sec.querySelector(".pbody").appendChild(p.body);
  if (applicable.length > 1) {
    const tabs = document.createElement("div"); tabs.className = "ptabs"; tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "Panels of this group");
    for (const id of applicable) {
      const b = document.createElement("button"); b.className = "ptab"; b.setAttribute("role", "tab"); b.dataset.tab = id; b.textContent = PANELS.get(id).title;
      b.setAttribute("aria-selected", String(id === active)); b.setAttribute("aria-controls", bodyId); b.tabIndex = id === active ? 0 : -1; b.draggable = true;
      b.onclick = () => { g.active = id; g.collapsed = false; saveLayout(); renderDocks(); focusPanel(id); };
      b.onkeydown = e => { const i = applicable.indexOf(id); let j = -1;
        if (e.key === "ArrowRight") j = (i + 1) % applicable.length; else if (e.key === "ArrowLeft") j = (i - 1 + applicable.length) % applicable.length;
        else if (e.key === "Home") j = 0; else if (e.key === "End") j = applicable.length - 1;
        if (j >= 0) { e.preventDefault(); g.active = applicable[j]; saveLayout(); renderDocks(); focusPanel(applicable[j]); } };
      b.ondragstart = e => { e.dataTransfer.setData("text/x-fenolite-panel", id); e.dataTransfer.effectAllowed = "move"; };
      tabs.appendChild(b);
    }
    sec.appendChild(tabs);
  } else sec.querySelector(".ptitle").draggable = true;
  sec.querySelector(".ptitle").ondragstart = e => { e.dataTransfer.setData("text/x-fenolite-panel", active); e.dataTransfer.effectAllowed = "move"; };
  sec.querySelector(".ptitle").onclick = () => { g.collapsed = !g.collapsed; saveLayout(); renderDocks(); focusPanel(active); };
  sec.querySelector(".pclose").onclick = () => closePanel(active);
  sec.querySelector(".pmenu").onclick = e => panelMenu(active, e.currentTarget);
  sec.ondragover = e => { if ([...e.dataTransfer.types].includes("text/x-fenolite-panel")) { e.preventDefault(); sec.classList.add("drop"); } };
  sec.ondragleave = () => sec.classList.remove("drop");
  sec.ondrop = e => { e.preventDefault(); e.stopPropagation(); sec.classList.remove("drop"); const id = e.dataTransfer.getData("text/x-fenolite-panel"); if (id && id !== active || id && g.panels.length > 1) movePanel(id, d, gi); };
  if (p.shown) SHOWN_LATER.push(p);
  return sec;
}
const SHOWN_LATER = [];   // panels to refresh once their group is in the page
function groupSplitter(d, gs, a, b) {   // between two groups of a dock: drag or arrows share their space
  const s = document.createElement("div"); s.className = "gsplit " + (d === "bottom" ? "v" : "h"); s.tabIndex = 0;
  s.setAttribute("role", "separator"); s.setAttribute("aria-orientation", d === "bottom" ? "vertical" : "horizontal"); s.setAttribute("aria-label", "Share the space of two panel groups");
  const shift = px => { const A = gs[a], B = gs[b], ea = s.previousElementSibling, eb = s.nextElementSibling; if (!ea || !eb) return;
    const la = d === "bottom" ? ea.offsetWidth : ea.offsetHeight, lb = d === "bottom" ? eb.offsetWidth : eb.offsetHeight, tot = A.size + B.size;
    const na = Math.min(Math.max(la + px, 40), la + lb - 40); A.size = tot * na / (la + lb); B.size = tot - A.size; ea.style.flex = `${A.size} 1 0`; eb.style.flex = `${B.size} 1 0`; };
  s.onkeydown = e => { const k = d === "bottom" ? ["ArrowLeft", "ArrowRight"] : ["ArrowUp", "ArrowDown"]; const i = k.indexOf(e.key); if (i < 0) return; e.preventDefault(); shift(i ? 10 : -10); saveLayout(); };
  s.onmousedown = e => { e.preventDefault(); let last = d === "bottom" ? e.clientX : e.clientY;
    const mv = ev => { const now = d === "bottom" ? ev.clientX : ev.clientY; shift(now - last); last = now; };
    const up = () => { window.removeEventListener("mousemove", mv); window.removeEventListener("mouseup", up); saveLayout(); };
    window.addEventListener("mousemove", mv); window.addEventListener("mouseup", up); };
  return s;
}
function dockSplitter(d) {   // the inner edge of a dock: drag or arrows set its size
  const s = document.createElement("div"); s.className = "dsplit " + d; s.tabIndex = 0; s.setAttribute("role", "separator");
  s.setAttribute("aria-orientation", d === "bottom" ? "horizontal" : "vertical"); s.setAttribute("aria-label", `Resize the ${d} dock`);
  const [lo, hi] = DOCK_SIZE[d], val = () => LAYOUT.docks[d].size;
  const set = v => { LAYOUT.docks[d].size = Math.round(Math.min(hi, Math.max(lo, v))); s.setAttribute("aria-valuenow", String(LAYOUT.docks[d].size)); applyDockSizes(); };
  s.setAttribute("aria-valuemin", String(lo)); s.setAttribute("aria-valuemax", String(hi)); s.setAttribute("aria-valuenow", String(val()));
  const sign = d === "left" ? 1 : -1;
  s.onkeydown = e => { const keys = d === "bottom" ? { ArrowUp: 10, ArrowDown: -10 } : { ArrowRight: 10 * sign, ArrowLeft: -10 * sign }; if (!(e.key in keys)) return; e.preventDefault(); set(val() + keys[e.key]); saveLayout(); };
  s.onmousedown = e => { e.preventDefault(); const start = d === "bottom" ? e.clientY : e.clientX, v0 = val();
    const mv = ev => set(v0 + (d === "bottom" ? start - ev.clientY : (ev.clientX - start) * sign));
    const up = () => { window.removeEventListener("mousemove", mv); window.removeEventListener("mouseup", up); saveLayout(); };
    window.addEventListener("mousemove", mv); window.addEventListener("mouseup", up); };
  return s;
}
const SHOWN = { left: false, right: false, bottom: false };
function applyDockSizes() {
  const app = $("app"), narrow = isNarrow();
  app.style.setProperty("--dl", narrow ? "0px" : (SHOWN.left ? LAYOUT.docks.left.size : 0) + "px");
  app.style.setProperty("--dr", narrow || !SHOWN.right ? "0px" : LAYOUT.docks.right.size + "px");
  app.style.setProperty("--db", narrow || !SHOWN.bottom ? "0px" : LAYOUT.docks.bottom.size + "px");
}
function renderDocks() {
  if (!LAYOUT) return;
  if (FLOAT && PANELS.has(FLOAT)) { renderFloat(); return; }
  const narrow = isNarrow(), store = $("panelStore");
  for (const p of PANELS.values()) store.appendChild(p.body);
  for (const d of DOCKS) { const el = $(DOCK_EL[d]); el.innerHTML = ""; }
  for (const d of DOCKS) {
    const el = $(DOCK_EL[narrow ? "left" : d]), gs = LAYOUT.docks[d].groups; let n = 0, prev = -1;
    gs.forEach((g, gi) => { const sec = groupEl(d, gi, g); if (!sec) return;
      if (prev >= 0 && !narrow) el.appendChild(groupSplitter(d, gs, prev, gi)); el.appendChild(sec); prev = gi; n++; });
    SHOWN[d] = n > 0;
    if (n && !narrow) $(DOCK_EL[d]).appendChild(dockSplitter(d));
  }
  for (const d of ["right", "bottom"]) $(DOCK_EL[d]).hidden = narrow || !SHOWN[d];
  applyDockSizes();
  for (const p of SHOWN_LATER.splice(0)) p.shown();
}
function renderFloat() {   // one panel fills the window
  document.body.classList.add("float"); const p = PANELS.get(FLOAT), side = $("side"); side.innerHTML = "";
  const sec = document.createElement("section"); sec.className = "pgroup"; sec.style.flex = "1 1 0";
  sec.innerHTML = `<div class="phead"><span class="ptitle">${esc(p.title)}</span></div><div class="pbody" role="region" aria-label="${esc(p.title)}"></div>`;
  sec.querySelector(".pbody").appendChild(p.body); side.appendChild(sec); if (p.shown) p.shown();
  document.title = `${p.title} · Fenolite viewer`;
}
if (DOCS_BC && FLOAT) DOCS_BC.onmessage = e => { const id = e.data && e.data.doc, d = id && allDocs().find(x => x.id === id); if (d && (!DOC || DOC.id !== id)) openDoc(d); };
matchMedia("(max-width:760px)").addEventListener("change", () => { renderDocks(); resize(); });
