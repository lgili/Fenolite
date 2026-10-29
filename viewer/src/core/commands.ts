// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the command registry (c0243, design decision 2)
// Every action of the shell, declared once: the toolbar is built from it, the palette lists it, the shortcut sheet
// prints it, and the keydown listener of core/input looks its shortcuts up here. `when()` says whether a command
// applies to what is shown (board, sheet, library, table, 3D); `pressed()` gives a toggle's state. Later changes
// add their commands (c0244 to c0246).
import { draw } from "../board/draw";
import { select } from "../board/info";
import { buildTabs, stepCurrent } from "../board/tabs";
import { openAbout } from "../dialogs/about";
import { openPalette } from "../dialogs/palette";
import { openShortcuts } from "../dialogs/shortcuts";
import { printView, saveSvg } from "../export/svg";
import { toggleEdge } from "../measure/edge-tool";
import { setProjectReview } from "../panels/project-review";
import { clearQuery, findSimilar } from "../panels/review";
import { refreshToolbar } from "../panels/toolbar";
import { RUNS } from "../review/runs";
import { shareNet } from "../sch/project-nets";
import { isSch } from "../sch/scene";
import { schSelect } from "../sch/select";
import { camPreset, set3D } from "../three/view3d";
import { $ } from "./dom";
import { flip, setSidebar, toggle, zoomBy } from "./input";
import { copyLink } from "./links";
import { DOC, S, st, view } from "./state";
import { setTheme, THEME } from "./theme";
import { setUnit, UNIT } from "./units";
import { fit } from "./viewport";

export let IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");   // let: a test sets it to check the macOS chord
const cad = () => !!S && S.kind !== "table";
const board = () => !!S && !S.kind && !isSch();
const board2d = () => board() && !st.mode3d;
const flat = () => cad() && !st.mode3d;
const narrow = () => matchMedia("(max-width:760px)").matches;
const sidebarOpen = () => $("app").classList.contains("sidebar-open");

export function escapeKey() {   // Esc, in the order the page always followed: the narrow side bar, a tool, the selection
  if (narrow() && sidebarOpen()) { setSidebar(false); $("bSidebar").focus(); return; }
  if (!cad()) return;
  if (st.edge) { toggleEdge(); return; }
  if (st.marking) { toggle("marking"); return; }
  if (st.measure || st.mpts.length) { st.mpts = []; st.mhover = null; if (st.measure) toggle("measure"); else draw(); return; }
  if (isSch()) { schSelect(-1); shareNet(null); return; }
  if (st.mode3d) return;
  st.mpts = []; st.selOv = -1; select(null); shareNet(null);
}
const PRINT = [["fit", "Fit to the page"], ["1", "1:1"], ["2", "2:1"], ["5", "5:1"], ["10", "10:1"]];

// ---- commands (c0243)
export const COMMANDS: any[] = [
  { id: "view.3d", title: "3D view", group: "View", icon: "cube", keys: ["D"], when: () => board(), run: () => set3D(!st.mode3d), pressed: () => st.mode3d },
  { id: "view.fit", title: "Fit to the window", group: "View", icon: "fit", keys: ["F"], when: () => cad(), run: () => st.mode3d ? camPreset("iso") : fit() },
  { id: "view.flip", title: "View from below", group: "View", icon: "flip", keys: ["B"], when: () => board2d(), run: () => flip(), pressed: () => view.mirror },
  { id: "view.zoomIn", title: "Zoom in", group: "View", icon: "zoom", keys: ["PageUp"], when: () => isSch(), run: () => zoomBy(1.25) },
  { id: "view.zoomOut", title: "Zoom out", group: "View", icon: "zoom", keys: ["PageDown"], when: () => isSch(), run: () => zoomBy(0.8) },
  { id: "view.single", title: "Current layer only", group: "Layers", icon: "layer", keys: ["Shift+S"], when: () => board2d(), run: () => { st.single = !st.single; buildTabs(); draw(); }, pressed: () => st.single },
  { id: "view.nextLayer", title: "Next layer", group: "Layers", icon: "arrowUp", keys: ["+", "="], when: () => board2d(), run: () => stepCurrent(1) },
  { id: "view.prevLayer", title: "Previous layer", group: "Layers", icon: "arrowDown", keys: ["-", "_"], when: () => board2d(), run: () => stepCurrent(-1) },
  { id: "view.changes", title: "Show or hide the changes", group: "View", icon: "changes", keys: ["X"], when: () => cad() && !!S.diff, run: () => { st.diff = !st.diff; draw(); }, pressed: () => st.diff },
  { id: "view.checks", title: "Show or hide the check markers", group: "View", icon: "target", keys: ["E"], when: () => cad() && !!S.check, run: () => { st.checks = !st.checks; draw(); }, pressed: () => st.checks },
  { id: "tools.edge", title: "Edge gap", group: "Tools", icon: "gap", keys: ["Shift+M"], when: () => board2d(), run: () => toggleEdge(), pressed: () => st.edge },
  { id: "tools.measure", title: "Measure", group: "Tools", icon: "ruler", keys: ["M"], when: () => flat(), run: () => toggle("measure"), pressed: () => st.measure },
  { id: "tools.mark", title: "Review mark", group: "Tools", icon: "pin", keys: ["N"], when: () => flat(), run: () => toggle("marking"), pressed: () => st.marking },
  { id: "tools.units", title: "Units: millimetres or mil", group: "Tools", icon: "units", keys: ["Q"], when: () => cad(), run: () => setUnit(UNIT === "mm" ? "mil" : "mm") },
  { id: "tools.similar", title: "Find similar", group: "Tools", icon: "similar", keys: [], when: () => board2d() && (st.selComp >= 0 || !!st.lastHit), run: () => findSimilar() },
  { id: "tools.clearFilter", title: "Clear the filter", group: "Tools", icon: "filter", keys: ["Shift+C"], when: () => board2d(), run: () => clearQuery() },
  { id: "tools.escape", title: "Clear the selection or leave the tool", group: "Tools", icon: "clear", keys: ["Escape"], when: () => true, run: () => escapeKey() },
  { id: "share.link", title: "Copy link", group: "Share", icon: "link", keys: [], when: () => !!DOC, run: () => copyLink() },
  { id: "share.svg", title: "Save as SVG", group: "Share", icon: "image", keys: [], when: () => flat(), run: () => saveSvg() },
  ...PRINT.map(([k, label]) => ({ id: `share.print.${k}`, title: `Print · ${label}`, group: "Share", icon: "printer", keys: [], when: () => flat(), run: () => printView(k) })),
  { id: "app.palette", title: "Search or run a command", group: "General", icon: "search", keys: ["Mod+K"], when: () => true, run: () => openPalette() },
  { id: "app.shortcuts", title: "Keyboard shortcuts", group: "General", icon: "keyboard", keys: ["?"], when: () => true, run: () => openShortcuts() },
  { id: "app.about", title: "About this document", group: "General", icon: "info", keys: [], when: () => !!DOC, run: () => openAbout() },
  { id: "app.review", title: "Project review", group: "General", icon: "review", keys: [], when: () => !!DOC, run: () => setProjectReview($("projectReview").hidden) },
  { id: "app.sidebar", title: "Show or hide the side bar", group: "General", icon: "sidebar", keys: [], when: () => narrow(), run: () => setSidebar(!sidebarOpen()), pressed: () => sidebarOpen() },
  { id: "app.run", title: "Run checks", group: "General", icon: "play", keys: [], when: () => RUNS.enabled && !!DOC && (DOC.viewable || DOC.kind === "project"),
    run: () => window.FenoliteRuns.start("check", {}), disabled: () => !!RUNS.job },
  { id: "app.theme.system", title: "Interface theme: follow the system", group: "General", icon: "monitor", keys: [], when: () => true, run: () => setTheme("system"), pressed: () => THEME === "system" },
  { id: "app.theme.dark", title: "Interface theme: dark", group: "General", icon: "moon", keys: [], when: () => true, run: () => setTheme("dark"), pressed: () => THEME === "dark" },
  { id: "app.theme.light", title: "Interface theme: light", group: "General", icon: "sun", keys: [], when: () => true, run: () => setTheme("light"), pressed: () => THEME === "light" },
];
// ---- end commands

export const commandById = id => COMMANDS.find(c => c.id === id);
export function available(c) { try { return !!c.when(); } catch (e) { return false; } }
export function runCommand(id) {
  const c = commandById(id); if (!c || !available(c) || (c.disabled && c.disabled())) return false;
  c.run(); refreshToolbar(); return true;
}
const KEY_NAMES = { Escape: "Esc", PageUp: "PgUp", PageDown: "PgDn" };
export function keyLabel(spec) {   // "Shift+M" → "Shift M", "Mod+K" → "Ctrl K" or "⌘ K", "Escape" → "Esc"
  return spec === "+" ? "+" : spec.replace("Mod+", IS_MAC ? "⌘+" : "Ctrl+").split("+").map(k => KEY_NAMES[k] || k).join(" ");
}
export function keyMatches(spec, e) {
  if (spec === "+" || spec === "-" || spec === "=" || spec === "_" || spec === "?") return e.key === spec;
  const parts = spec.split("+"), key = parts.pop(), mods = new Set(parts);
  if (mods.has("Mod")) return (IS_MAC ? e.metaKey : e.ctrlKey) && e.key.toLowerCase() === key.toLowerCase();
  if (key.length === 1 && /[a-z]/i.test(key)) return e.key.toLowerCase() === key.toLowerCase() && e.shiftKey === mods.has("Shift");
  return e.key === key;
}
export function commandForKey(e) {   // the first command whose shortcut the event is and that applies now
  for (const c of COMMANDS) if (c.id !== "app.palette" && c.keys.some(k => keyMatches(k, e)) && available(c)) return c;
  return null;
}
