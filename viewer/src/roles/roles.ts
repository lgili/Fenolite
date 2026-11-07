// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== net roles on the board (c0305)
// The role data of a board (scene.roles, fenolite.view_roles.v0): the reply of `fenolite roles --check` that
// `fenolite view --roles` or a roles run from a served page joined to the scene, its values unchanged. The role
// palette and glyphs and the idea of the view come from c0245-engineering-viewer (another session, superseded
// by the maintainer's decision of 2026-10-29 except for this view): seven colours chosen for Fenolite and told
// apart under simulated colour-vision deficiency, and a glyph for each role, so colour is never the only cue.
// The panel is panels/roles, the drawing roles/draw; the builders between the markers are pure and run under
// Node in tests/unit/view/test_page.py -k role.
import { MM, S } from "../core/state";
import { FMT, findingSection, imodel, irow, isection } from "../inspect/model";

// ---- roles model (c0305)
export const ROLE_ORDER = ["power", "switch_node", "ground", "high_voltage", "gate", "kelvin", "signal"];
export const ROLE_GLYPH = { power: "P", switch_node: "SW", ground: "G", kelvin: "K", gate: "GT", high_voltage: "HV", signal: "S" };
export const ROLE_COLORS = {   // canvas colours: the dark set on a dark board, the light set on a light one
  dark: { power: "#b8322c", switch_node: "#e28900", ground: "#0f6eb7", kelvin: "#7ec5a2", gate: "#d2a2f7", high_voltage: "#ffff89", signal: "#777777" },
  light: { power: "#631d1d", switch_node: "#b68500", ground: "#003a6a", kelvin: "#2f7157", gate: "#a357de", high_voltage: "#775b09", signal: "#8a8a8a" },
};
export const GROUP_KIND = { hot: "switch_node", gate: "gate", kelvin: "kelvin" };   // the role colour of a group
export const GROUP_LABEL = { hot: "Hot loop", gate: "Gate loop", kelvin: "Kelvin pair" };
export const STATE_MARK = { confirmed: "✓", declared: "◆", inferred: "?" };
export function roleName(kind) { return String(kind).replace(/_/g, " "); }
export function amps(ma) { return `${+(ma / 1000).toFixed(3)} A`; }
export function volts(mv) { return `${+(mv / 1000).toFixed(3)} V`; }
export function roleLegend(data) {   // the kinds of the board in ROLE_ORDER, each with its glyph and count
  return ROLE_ORDER.filter(k => data && data.kinds && data.kinds[k]).map(k => ({ kind: k, glyph: ROLE_GLYPH[k], name: roleName(k), n: data.kinds[k] }));
}
export function groupsOfNet(data, name, padNet) {   // the groups that hold the net: the net their measure names, or one of their pads
  return (data && data.groups || []).filter(g => g.net === name || g.pads.some(p => padNet(p) === name));
}
export function roleSection(row, groups, f) {   // f: the formatters of inspect/model (unused but for symmetry with the other sections)
  if (!row) return null;
  return isection("Role", [
    irow("Kind", row.kind), irow("State", row.state), irow("Rule", row.rule), irow("Confidence", row.confidence),
    row.pads && row.pads.length ? irow("Evidence pads", row.pads.join(", ")) : null,
    row.milliamps != null ? irow("Current", amps(row.milliamps)) : null,
    row.working_mv != null ? irow("Working voltage", volts(row.working_mv)) : null,
    row.sensitive ? irow("Sensitive", "yes") : null,
    groups.length ? irow("Groups", groups.map(g => `${g.name} (${(GROUP_LABEL[g.type] || g.type).toLowerCase()})`).join(", ")) : null,
  ]);
}
export function groupSection(g, f) {   // a hot loop, gate loop or Kelvin pair; areas in nm² as the reply gives them
  return isection(GROUP_LABEL[g.type] || "Group", [
    irow("Name", g.name), irow("Origin", g.origin), irow("Rule", g.rule), irow("Confidence", g.confidence), irow("Pads", g.pads.join(", ")),
    g.net ? irow("Net", g.net) : null,
    g.area_nm2 != null ? irow("Loop area", f.area(g.area_nm2 / 1e12)) : null,
    g.bound_nm2 != null ? irow("Placement bound", f.area(g.bound_nm2 / 1e12)) : null,
    g.ratio_permille != null ? irow("Area to bound", `${(g.ratio_permille / 1000).toFixed(2)}`) : null,
  ]);
}
// ---- end roles model

export const ROLES_KEY = "fenolite.view.roles";
export const ROLE_VIEW = (() => { const on = { colors: true, loops: true, kelvin: true, findings: true };
  try { return { ...on, ...JSON.parse(localStorage.getItem(ROLES_KEY) || "{}") }; } catch (e) { return on; } })();
export const ROLE_SEL = { group: -1, finding: -1, kind: "" };
export function keepRoleView() { try { localStorage.setItem(ROLES_KEY, JSON.stringify(ROLE_VIEW)); } catch (e) { /* kept for this page only */ } }
export function rolesData() { return S && !S.kind && S.roles ? S.roles : null; }
export function rolesToMM(sc) {   // the points of the groups and findings in micrometres, like the scene
  const R = sc.roles; if (!R || R.mm) return; R.mm = true; const f = v => v * MM;
  for (const g of R.groups || []) g.points = (g.points || []).map(p => p.map(f));
  for (const x of R.findings || []) { if (x.at) x.at = x.at.map(f); if (x.box) x.box = x.box.map(f); }
}
function luminance(hex) { const n = parseInt(String(hex).slice(1, 7), 16); return Number.isNaN(n) ? 0 : (0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255; }
export function roleTone() { return luminance((S && S.theme && S.theme.background) || "#15171b") > 0.5 ? "light" : "dark"; }
export function roleColor(kind) { const set = ROLE_COLORS[roleTone()]; return set[kind] || set.signal; }
export function roleRow(name) { const R = rolesData(); return R ? R.roles.find(r => r.net === name) || null : null; }
export function roleOfNet(ni) { const R = rolesData(); return R && ni >= 0 ? R.roles.find(r => r.net_index === ni) || null : null; }
export function padNet(label) { const p = S && S.pads ? S.pads.find(q => q.label === label) : null; return p ? p.net : null; }
export function boardRole(ni) { const row = roleOfNet(ni); return row ? roleSection(row, groupsOfNet(rolesData(), row.net, padNet), FMT) : null; }
export function groupModel(i) { const g = rolesData().groups[i];
  return imodel("group", g.name, [groupSection(g, FMT)], { subtitle: `${GROUP_LABEL[g.type] || g.type} · ${g.origin || ""}`, target: { group: i, comp: -1, net: -1 } }); }
export function roleFindingModel(i) { const x = rolesData().findings[i];
  return imodel("finding", x.code, [findingSection(x, null)], { subtitle: [x.severity, x.stage].filter(Boolean).join(" · "), target: { roleFinding: i, comp: -1, net: -1 } }); }
export function inferredRoles() { const R = rolesData(); return R ? R.roles.filter(r => r.state === "inferred").map(r => r.net) : []; }
export function inferredGroups() { const R = rolesData(); return R ? R.groups.filter(g => g.origin === "inferred").map(g => g.name) : []; }
