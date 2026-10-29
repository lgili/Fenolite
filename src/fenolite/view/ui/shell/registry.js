// ================================================================== commands, keymaps and undo (change c0245)
// Every command is registered once, with an id, a label, its menu and its keys. The menu bar, the toolbar,
// the command search and the Keyboard panel are generated from this registry, and the keyboard reaches
// every command through it (design, decision 5). A key runs the first registered command whose binding
// matches and whose `when` holds, so several commands may share a key in different contexts (Escape).
const MENUS = ["File", "Edit", "View", "Place", "Design", "Roles", "Route", "Tools", "Reports", "Window", "Help"];
const COMMANDS = [];
const CMD = new Map();
function command(def) {
  const c = { keys: [], when: () => true, group: "", ...def };
  if (CMD.has(c.id)) throw new Error("duplicate command " + c.id);
  COMMANDS.push(c); CMD.set(c.id, c); return c;
}
function runCommand(id, e) { const c = CMD.get(id); if (c && c.when()) { c.run(e); return true; } return false; }

// ---- key specs: "M", "Shift+M", "Ctrl+Z", "+", "Escape", and sequences "V F" (one key per menu level)
const MOD_ORDER = ["Ctrl", "Meta", "Alt", "Shift"];
function normKey(spec) {   // one chord, normalised: modifiers in MOD_ORDER, letters upper case
  let key = spec, mods = [];
  if (spec.length > 1 && spec.endsWith("++")) { key = "+"; mods = spec.slice(0, -2).split("+"); }
  else if (spec !== "+") { const parts = spec.split("+"); key = parts.pop(); mods = parts; }
  if (key.length === 1 && /[a-z]/i.test(key)) key = key.toUpperCase();
  mods = MOD_ORDER.filter(m => mods.some(x => x.toLowerCase() === m.toLowerCase()));
  return [...mods, key].join("+");
}
function normSpec(spec) { return String(spec).trim().split(/\s+/).map(normKey).join(" "); }
function eventSpec(e) {   // the chord of a key event; null for a lone modifier
  let k = e.key;
  if (!k || ["Shift", "Control", "Alt", "Meta", "CapsLock", "Dead", "Unidentified", "Process", "AltGraph"].includes(k)) return null;
  if (e.altKey && e.code && /^Key[A-Z]$/.test(e.code)) k = e.code.slice(3);   // Alt+letter gives another character on some systems
  if (e.altKey && e.code && /^Digit[0-9]$/.test(e.code)) k = e.code.slice(5);
  const mods = []; if (e.ctrlKey) mods.push("Ctrl"); if (e.metaKey) mods.push("Meta"); if (e.altKey) mods.push("Alt");
  let key;
  if (k.length === 1) { if (/[a-z]/i.test(k)) { if (e.shiftKey) mods.push("Shift"); key = k.toUpperCase(); } else key = k === " " ? "Space" : k; }
  else { if (e.shiftKey) mods.push("Shift"); key = k; }
  return [...mods, key].join("+");
}
function keyLabel(spec) { return spec.split(" ").join(", "); }

// ---- keymaps: `fenolite` holds each command's own keys; the others are given over it (decision 5)
const KEYMAPS = { fenolite: {}, altium: {}, kicad: {} };
let KEYMAP = "fenolite", KEYMAP_USER = null;   // the active base keymap, and a user file's overrides
function keysOf(c, name) {
  const map = name || KEYMAP;
  if (!name && KEYMAP_USER && Object.prototype.hasOwnProperty.call(KEYMAP_USER, c.id)) return KEYMAP_USER[c.id];
  const over = KEYMAPS[map] && KEYMAPS[map][c.id];
  return (over || c.keys).map(normSpec);
}
function resolveKey(spec) {   // the command a chord or a sequence runs, "prefix" when it starts a sequence, or null
  let prefix = false;
  for (const c of COMMANDS) for (const b of keysOf(c)) {
    if (b === spec) { if (c.when()) return c; }
    else if (b.startsWith(spec + " ") && c.when()) prefix = true;
  }
  return prefix ? "prefix" : null;
}

// ---- undo and redo of what the viewer writes (marks now; role writes add their own entries, decision 11)
const HISTORY = { undo: [], redo: [] };
function pushUndo(entry) { HISTORY.undo.push(entry); HISTORY.redo = []; if (HISTORY.undo.length > 200) HISTORY.undo.shift(); }
async function undoLast() { const e = HISTORY.undo.pop(); if (!e) { say("Nothing to undo."); return; } await e.undo(); HISTORY.redo.push(e); say(`Undone: ${e.label}`); }
async function redoLast() { const e = HISTORY.redo.pop(); if (!e) { say("Nothing to redo."); return; } await e.redo(); HISTORY.undo.push(e); say(`Redone: ${e.label}`); }
function say(text) { $("live").textContent = text; }

// ---- the commands of the viewer (fenolite keymap: the keys the page had before c0245, unchanged)
const onDoc = () => !!(S && S.kind !== "table");
const on2D = () => onDoc() && !st.mode3d;
const narrowOpen = () => matchMedia("(max-width:760px)").matches && $("app").classList.contains("sidebar-open");
function escapeChain() {   // Esc: close the drawer, end a tool, then clear the selection
  if (narrowOpen()) { setSidebar(false); $("bSidebar").focus(); return; }
  if (!onDoc()) return;
  if (st.edge) { toggleEdge(); return; }
  if (st.marking) { closeMarkEditor(); toggle("marking", "bMark"); return; }
  if (st.measure || st.mpts.length) { st.mpts = []; st.mhover = null; if (st.measure) toggle("measure", "bMeasure"); return; }
  if (isSch()) { schSelect(-1); shareNet(null); return; }
  if (st.mode3d) return;
  st.mpts = []; st.selOv = -1; select(null); shareNet(null);
}
command({ id: "edit.escape", menu: "Edit", label: "Cancel / Clear Selection", keys: ["Escape"], run: escapeChain });
command({ id: "view.units", menu: "View", group: "units", label: "Toggle Units (mm / mil)", keys: ["Q", "Shift+Q"], when: onDoc, run: () => setUnit(UNIT === "mm" ? "mil" : "mm") });
command({ id: "place.edge", menu: "Place", label: "Edge Measure", keys: ["Shift+M"], when: () => on2D() && !isSch(), run: () => toggleEdge(), checked: () => st.edge });
command({ id: "place.measure", menu: "Place", label: "Measure Distance", keys: ["M", "Shift+M"], when: on2D, run: () => toggle("measure", "bMeasure"), checked: () => st.measure });
command({ id: "place.mark", menu: "Place", label: "Review Mark", keys: ["N", "Shift+N"], when: on2D, run: () => toggle("marking", "bMark"), checked: () => st.marking });
command({ id: "view.changes", menu: "View", group: "show", label: "Show Changes", keys: ["X", "Shift+X"], when: () => onDoc() && !!S.diff, run: () => { st.diff = !st.diff; draw(); }, checked: () => st.diff });
command({ id: "view.checks", menu: "View", group: "show", label: "Show Check Markers", keys: ["E", "Shift+E"], when: () => onDoc() && !!S.check, run: () => { st.checks = !st.checks; draw(); }, checked: () => st.checks });
command({ id: "view.zoom-in", menu: "View", group: "zoom", label: "Zoom In", keys: ["PageUp"], when: () => onDoc() && isSch(), run: e => { if (e) e.preventDefault(); zoomBy(1.25); } });
command({ id: "view.zoom-out", menu: "View", group: "zoom", label: "Zoom Out", keys: ["PageDown"], when: () => onDoc() && isSch(), run: e => { if (e) e.preventDefault(); zoomBy(0.8); } });
command({ id: "view.fit", menu: "View", group: "zoom", label: "Fit Document", keys: ["F", "Shift+F"], when: onDoc, run: () => { if (!isSch() && st.mode3d) camPreset("iso"); else fit(); } });
command({ id: "view.3d", menu: "View", group: "mode", label: "2D / 3D", keys: ["D", "Shift+D"], when: () => onDoc() && !isSch(), run: () => set3D(!st.mode3d), checked: () => st.mode3d });
command({ id: "view.single", menu: "View", group: "layers", label: "Single Layer Mode", keys: ["Shift+S"], when: () => on2D() && !isSch(), run: () => { st.single = !st.single; buildTabs(); draw(); }, checked: () => st.single });
command({ id: "view.next-layer", menu: "View", group: "layers", label: "Next Layer", keys: ["+", "="], when: () => on2D() && !isSch(), run: () => stepCurrent(1) });
command({ id: "view.prev-layer", menu: "View", group: "layers", label: "Previous Layer", keys: ["-", "_"], when: () => on2D() && !isSch(), run: () => stepCurrent(-1) });
command({ id: "view.flip", menu: "View", group: "mode", label: "Flip Board (Top / Bottom)", keys: ["B", "Shift+B"], when: () => on2D() && !isSch(), run: flip, checked: () => view.mirror });
command({ id: "edit.clear-filter", menu: "Edit", label: "Clear Filter", keys: ["Shift+C"], when: () => on2D() && !isSch(), run: clearQuery });
command({ id: "edit.undo", menu: "Edit", group: "history", label: "Undo", note: "The history is this page's: a reload forgets it.", keys: ["Ctrl+Z", "Meta+Z"], run: undoLast });
command({ id: "edit.redo", menu: "Edit", group: "history", label: "Redo", note: "The history is this page's: a reload forgets it.", keys: ["Ctrl+Y", "Ctrl+Shift+Z", "Meta+Shift+Z"], run: redoLast });

// ---- the keyboard: a chord, or a sequence of chords, runs the command bound to it
let KEY_PREFIX = null, KEY_TIMER = 0;
const SEQUENCE_MS = 1500;
window.addEventListener("keydown", e => {
  const target = e.target;
  if (e.defaultPrevented || e.isComposing ||
      (target instanceof Element && (target.closest("input, select, textarea, dialog[open], #projectReview, #menubar, .menu, .kbcapture") || target.isContentEditable))) return;
  const spec = eventSpec(e); if (!spec) return;
  const full = KEY_PREFIX ? KEY_PREFIX + " " + spec : spec;
  const hit = resolveKey(full);
  clearTimeout(KEY_TIMER);
  if (hit === "prefix") { KEY_PREFIX = full; e.preventDefault(); keyPending(full); KEY_TIMER = setTimeout(() => { KEY_PREFIX = null; keyPending(null); }, SEQUENCE_MS); return; }
  const had = KEY_PREFIX; KEY_PREFIX = null; keyPending(null);
  if (!hit) { if (had) e.preventDefault(); return; }
  hit.run(e);
});
function keyPending(spec) { const el = $("keyPending"); if (el) el.textContent = spec ? keyLabel(spec) + ", …" : ""; }
