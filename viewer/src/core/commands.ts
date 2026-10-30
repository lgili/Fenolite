// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the command registry (c0300, design decision 2)
// Every action of the shell, declared once: the toolbar is built from it, the palette lists it, the shortcut sheet
// prints it, and the keydown listener of core/input looks its shortcuts up here. `when()` says whether a command
// applies to what is shown (board, sheet, library, table, 3D); `pressed()` gives a toggle's state. Later changes
// add their commands (c0301 to c0303).
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
import { closeSheet, DOCK, dockNarrow, toggleDock } from "../panels/dock";
import { INSPECT, refreshInspector } from "../panels/inspector";
import { filterReviewFindings, REVIEW } from "../panels/project-review";
import { gotoFinding } from "../panels/findings";
import { netBounds, selectCompAt, selectNetAt } from "../panels/review";
import { selectComp, selectNet } from "../sch/project-nets";
import { netBox } from "../sch/select";
import { crossProbe } from "../sch/load";
import { bboxOf } from "../board/cache";
import { LIB } from "../library/library";
import { allDocs } from "./documents";
import { SCENES } from "./state";
import { waiveBlocked } from "../actions/actions";
import { confirmOffered, confirmRoles, rolesRunOffered, setRoleView } from "../panels/roles";
import { ROLE_SEL, ROLE_VIEW, roleOfNet, rolesData } from "../roles/roles";

export let IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");   // let: a test sets it to check the macOS chord
const cad = () => !!S && S.kind !== "table";
const board = () => !!S && !S.kind && !isSch();
const board2d = () => board() && !st.mode3d;
const flat = () => cad() && !st.mode3d;
const narrow = () => matchMedia("(max-width:760px)").matches;
const sidebarOpen = () => $("app").classList.contains("sidebar-open");

export function escapeKey() {   // Esc, in the order the page always followed: the narrow side bar, a tool, the selection
  if (narrow() && sidebarOpen()) { setSidebar(false); $("bSidebar").focus(); return; }
  if (narrow() && closeSheet()) return;   // c0301: the inspector's bottom sheet
  if (!cad()) return;
  if (st.edge) { toggleEdge(); return; }
  if (st.marking) { toggle("marking"); return; }
  if (st.measure || st.mpts.length) { st.mpts = []; st.mhover = null; if (st.measure) toggle("measure"); else draw(); return; }
  if (isSch()) { schSelect(-1); shareNet(null); return; }
  if (st.mode3d) return;
  st.mpts = []; st.selOv = -1; ROLE_SEL.group = -1; ROLE_SEL.finding = -1; select(null); shareNet(null);
}
const PRINT = [["fit", "Fit to the page"], ["1", "1:1"], ["2", "2:1"], ["5", "5:1"], ["10", "10:1"]];
// ---- the selection's actions (c0301, design decision 3; c0303): commands of the group "Selection" on the target of
// the inspector's model, shown in the inspector and listed in the palette.
const target = () => (INSPECT.model && INSPECT.model.target) || null;
const tComp = () => { const t = target(); return t && t.comp >= 0 ? t.comp : -1; };
const tNet = () => { const t = target(); return t && t.net >= 0 ? t.net : -1; };
const tFinding = () => { const t = target(); return t && t.finding != null && S.check && S.check.findings[t.finding] ? t.finding : -1; };
const kind = () => INSPECT.model ? INSPECT.model.kind : "";
export function probeKind() { return isSch() ? "pcb" : "schematic"; }
export function probeOffered() {   // Show in schematic / on board: only when another document of that kind could hold the part
  const ci = tComp(); if (ci < 0 || !S || !S.comps || LIB) return false;
  const c = S.comps[ci], want = String(c.group || c.ref).toLowerCase(), docs = allDocs().filter(d => d.kind === probeKind() && d.viewable && d.present);
  if (!docs.length) return false;
  const known = docs.map(d => SCENES.get(d.id)).filter(Boolean);
  return known.length < docs.length || known.some(sc => sc.comps.some(x => x.ref.toLowerCase() === want || String(x.group || "").toLowerCase() === want));
}
export function zoomToTarget() {
  const t = target(); if (!t || !S) return;
  const frame = (b, m) => { if (b) fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); };
  if (st.mode3d) set3D(false);
  if (t.overlay != null) { gotoFinding(t.overlay); return; }
  if (t.finding != null && S.check) { const x = S.check.findings[t.finding]; if (x.at) { const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]]; frame(b, Math.max(b[2] - b[0], b[3] - b[1], 6) * 0.8); } return; }
  if (isSch()) { if (t.comp >= 0) frame(S.comps[t.comp].b, 12); else if (t.net >= 0) frame(netBox(t.net), 8); return; }
  if (t.pr) frame(bboxOf(t.pr), 3); else if (t.comp >= 0) frame(S.comps[t.comp].bbox, 5); else if (t.net >= 0) frame(netBounds(t.net), 3);
}
export function openInReview(i) {   // a finding of --check, selected in the Project review
  setProjectReview(true); const k = REVIEW.items.findIndex(x => x.checkIndex === i); if (k >= 0) { REVIEW.selected = k; filterReviewFindings(); }
}
export function moveInActions(ci) {   // Move part (c0303): the Actions panel's move form, filled with the part
  st.selComp = ci; setProjectReview(true);
  const box = document.querySelector<HTMLDetailsElement>('#actionPanel details[data-action="move"]'); if (!box) return;
  box.open = true; box.scrollIntoView({ block: "center" }); (box.querySelector('[data-opt="x"]') as HTMLElement)?.focus();
}
export function waiveState() {   // c0303, fix of 2026-10-29: Waive only on findings of the file's current revision
  const i = tFinding(); if (i < 0) return { offered: false, why: "" };
  const x = S.check.findings[i], A = window.FenoliteActions && window.FenoliteActions.state;
  if (!A || !A.enabled || !A.offer?.waive?.available || x.stage !== "drc.kicad") return { offered: false, why: "" };
  const why = waiveBlocked();
  return { offered: !why, why };
}

// ---- commands (c0300)
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
  { id: "view.dock", title: "Inspector", group: "View", icon: "dock", keys: ["I"], when: () => !!S, run: () => toggleDock(), pressed: () => dockNarrow() ? DOCK.sheet : DOCK.open },
  { id: "insp.zoom", title: "Zoom to", group: "Selection", icon: "zoom", keys: [], domId: "inspZoom", when: () => !!target() && kind() !== "measure" && kind() !== "mark" && S.kind !== "table", run: () => zoomToTarget() },
  { id: "insp.net", title: "Highlight net", group: "Selection", icon: "net", keys: [], domId: "inspNet", when: () => tNet() >= 0 && kind() !== "net" && (!st.mode3d || isSch()),
    run: () => isSch() ? selectNet(tNet(), true) : selectNetAt(tNet()) },
  { id: "insp.part", title: "Select part", group: "Selection", icon: "chip", keys: [], domId: "inspPart", when: () => tComp() >= 0 && kind() !== "part" && kind() !== "component" && !LIB,
    run: () => isSch() ? selectComp(tComp(), true) : selectCompAt(tComp()) },
  { id: "insp.similar", title: "Find similar", group: "Selection", icon: "similar", keys: [], domId: "inspSimilar", when: () => board2d() && !LIB && (tComp() >= 0 || !!target()?.pr), run: () => findSimilar() },
  { id: "insp.probe", title: "Show in schematic", group: "Selection", icon: "schematic", keys: [], label: () => isSch() ? "Show on board" : "Show in schematic", domId: "inspProbe",
    when: () => probeOffered(), run: () => { const c = S.comps[tComp()]; crossProbe(c.group || c.ref, probeKind()); } },
  { id: "insp.review", title: "Open in review", group: "Selection", icon: "review", keys: [], domId: "inspReview", when: () => tFinding() >= 0, run: () => openInReview(tFinding()) },
  { id: "act.waive", title: "Waive finding…", group: "Selection", icon: "waive", keys: [], domId: "inspWaive", tone: "warnBtn", when: () => waiveState().offered,
    run: () => { INSPECT.waive = !INSPECT.waive; refreshInspector(); }, disabled: () => !!(window.FenoliteActions?.state?.job) },
  { id: "act.move", title: "Move part…", group: "Selection", icon: "move", keys: [], domId: "inspMove",
    when: () => tComp() >= 0 && board2d() && !LIB && !!window.FenoliteActions?.state?.enabled && !!window.FenoliteActions.state.offer?.move?.available, run: () => moveInActions(tComp()) },
  { id: "act.confirmRole", title: "Confirm role…", group: "Selection", icon: "check", keys: [], domId: "inspConfirmRole",
    when: () => tNet() >= 0 && board2d() && roleOfNet(tNet())?.state === "inferred" && confirmOffered(),
    run: () => confirmRoles([roleOfNet(tNet()).net], []), disabled: () => !!(window.FenoliteActions?.state?.job) },
  { id: "roles.colors", title: "Roles: colour the copper by role", group: "Roles", icon: "net", keys: [], when: () => board2d() && !!rolesData(),
    run: () => setRoleView("colors", !ROLE_VIEW.colors), pressed: () => !!ROLE_VIEW.colors },
  { id: "roles.loops", title: "Roles: hot and gate loops", group: "Roles", icon: "refresh", keys: [], when: () => board2d() && !!rolesData(),
    run: () => setRoleView("loops", !ROLE_VIEW.loops), pressed: () => !!ROLE_VIEW.loops },
  { id: "roles.kelvin", title: "Roles: Kelvin pairs", group: "Roles", icon: "gap", keys: [], when: () => board2d() && !!rolesData(),
    run: () => setRoleView("kelvin", !ROLE_VIEW.kelvin), pressed: () => !!ROLE_VIEW.kelvin },
  { id: "roles.findings", title: "Roles: role findings", group: "Roles", icon: "target", keys: [], when: () => board2d() && !!rolesData(),
    run: () => setRoleView("findings", !ROLE_VIEW.findings), pressed: () => !!ROLE_VIEW.findings },
  { id: "roles.run", title: "Roles: run fenolite roles --check", group: "Roles", icon: "play", keys: [], when: () => rolesRunOffered(),
    run: () => window.FenoliteRuns.start("roles", {}), disabled: () => !!RUNS.job },
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
