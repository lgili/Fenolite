// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the Net roles panel (c0273)
// A side bar section of a board with role data (scene.roles): the legend of the role kinds (colour, glyph,
// name and count; a click lists one kind only), the role of each net (glyph, net, kind and current,
// confidence, state), the groups (hot loops, gate loops, Kelvin pairs) and the role findings by code. A net row
// highlights its net, a group row frames its pads, a finding row selects its marker; each opens in the
// inspector. In a served page the foot runs `fenolite roles --check` again and, with --allow-actions, plans
// Confirm roles for the inferred rows. The Roles group of the Layers panel (RoleLayers) shows or hides the
// overlays of roles/draw. Ported from the Net Roles workspace of c0245-engineering-viewer into c0269's look.
import * as preact from "preact";
import { draw } from "../board/draw";
import { $, natural } from "../core/dom";
import { DOC, S, st } from "../core/state";
import { fit } from "../core/viewport";
import { SEV_COLOR } from "../review/check";
import { RUNS } from "../review/runs";
import { GROUP_KIND, GROUP_LABEL, groupModel, inferredGroups, inferredRoles, amps, keepRoleView, ROLE_GLYPH, ROLE_ORDER, ROLE_SEL, ROLE_VIEW,
  roleColor, roleFindingModel, roleLegend, roleName, rolesData, STATE_MARK } from "../roles/roles";
import { set3D } from "../three/view3d";
import { Icon } from "../ui/icons";
import { showSection } from "../ui/section";
import { Empty } from "../ui/states";
import { inspect } from "./inspector";
import { buildLayers } from "./layers";
import { selectNetAt } from "./review";

function ink(hex) { const n = parseInt(String(hex).slice(1, 7), 16); const l = (0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255; return l > 0.55 ? "#111317" : "#ffffff"; }
export function RoleChip({ kind }: { kind: string }) {
  const c = roleColor(kind);
  return <span class="rchip" style={`background:${c};color:${ink(c)}`} title={roleName(kind)} aria-hidden="true">{ROLE_GLYPH[kind] || "?"}</span>;
}
function frame(pts, margin) {
  if (!pts.length) return; const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  fit([Math.min(...xs) - margin, Math.min(...ys) - margin, Math.max(...xs) + margin, Math.max(...ys) + margin]);
}
export function selectRoleGroup(i) {
  const g = rolesData().groups[i]; if (st.mode3d) set3D(false);
  ROLE_SEL.group = i; ROLE_SEL.finding = -1; st.selNet = -1; st.selComp = -1; frame(g.points || [], 3);
  inspect(() => groupModel(i)); buildRoles(); draw();
}
export function selectRoleFinding(i) {
  const x = rolesData().findings[i]; if (st.mode3d) set3D(false);
  ROLE_SEL.finding = i; ROLE_SEL.group = -1;
  if (x.at) { const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]], m = Math.max(b[2] - b[0], b[3] - b[1], 6) * 0.8; fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); }
  inspect(() => roleFindingModel(i)); buildRoles(); draw();
}
export function rolesRunOffered() { return !!(RUNS.enabled && RUNS.offer?.commands?.roles && DOC && rolesBoard()); }
export function confirmOffered() { const A = window.FenoliteActions && window.FenoliteActions.state; return !!(A && A.enabled && A.offer?.roles?.available); }
export function confirmRoles(nets, groups) { window.FenoliteActions.plan("roles", { nets, groups }); }
const rolesBoard = () => !!S && !S.kind && !!S.prims;
function Legend({ R }: { R: any }) {
  return <div class="rlegend" role="group" aria-label="Role kinds">
    {roleLegend(R).map(k => <button type="button" class={"rleg" + (ROLE_SEL.kind === k.kind ? " on" : "")} aria-pressed={ROLE_SEL.kind === k.kind}
      data-kind={k.kind} data-tip={ROLE_SEL.kind === k.kind ? "List every kind" : `List the ${k.name} nets only`}
      onClick={() => { ROLE_SEL.kind = ROLE_SEL.kind === k.kind ? "" : k.kind; buildRoles(); }}>
      <RoleChip kind={k.kind} /><span class="rlegName">{k.name}</span><span class="rlegN">{k.n}</span></button>)}
  </div>;
}
function NetRows({ R }: { R: any }) {
  const rows = R.roles.filter(r => !ROLE_SEL.kind || r.kind === ROLE_SEL.kind)
    .sort((a, b) => ROLE_ORDER.indexOf(a.kind) - ROLE_ORDER.indexOf(b.kind) || natural(a.net, b.net));
  if (!rows.length) return <Empty text="No role on this board." />;
  return <div class="list rlist" id="roleNets">{rows.map(r => <div key={r.net} class={"navi rrow" + (r.net_index >= 0 && r.net_index === st.selNet ? " sel" : "")}
    data-net={r.net} title={`${r.net}: ${roleName(r.kind)}, ${r.state}${r.rule ? ` (rule ${r.rule})` : ""}`} onClick={() => { if (r.net_index >= 0) { ROLE_SEL.group = -1; ROLE_SEL.finding = -1; selectNetAt(r.net_index); buildRoles(); } }}>
    <RoleChip kind={r.kind} /><span class="rnet">{r.net}</span>
    <span class="rkind">{roleName(r.kind)}{r.milliamps != null ? <small>{amps(r.milliamps)}</small> : null}</span>
    <span class={"rconf c-" + (r.confidence || r.state)}>{r.confidence || r.state}</span>
    <span class={"rstate s-" + r.state} aria-label={r.state}>{STATE_MARK[r.state] || ""}</span>
  </div>)}</div>;
}
function GroupRows({ R }: { R: any }) {
  if (!R.groups.length) return null;
  return <><div class="navg">Groups</div><div class="list rlist" id="roleGroups">{R.groups.map((g, i) => <div key={g.name} class={"navi rrow" + (i === ROLE_SEL.group ? " sel" : "")}
    data-group={g.name} title={`${GROUP_LABEL[g.type]}: ${g.pads.join(", ")}`} onClick={() => selectRoleGroup(i)}>
    <RoleChip kind={GROUP_KIND[g.type]} /><span class="rnet">{g.name}</span>
    <span class="rkind">{(GROUP_LABEL[g.type] || g.type).toLowerCase()}</span>
    <span class={"rconf c-" + (g.confidence || g.origin)}>{g.confidence || g.origin}</span>
    <span class={"rstate s-" + g.origin} aria-label={g.origin}>{STATE_MARK[g.origin] || ""}</span>
  </div>)}</div></>;
}
function FindingRows({ R }: { R: any }) {
  if (!R.findings.length) return null;
  const by = new Map(); R.findings.forEach((x, i) => { if (!by.has(x.code)) by.set(x.code, []); by.get(x.code).push(i); });
  const out = [<div key="h" class="navg">Role findings</div>];
  for (const [code, list] of by) {
    out.push(<div key={"c:" + code} class="rcode"><span class="sw" style={`background:${SEV_COLOR[R.findings[list[0]].severity] || "#888888"}`}></span>{` ${code} (${list.length})`}</div>);
    for (const i of list) { const x = R.findings[i];
      out.push(<div key={"f:" + i} class={"navi rfind" + (i === ROLE_SEL.finding ? " sel" : "")} data-code={x.code} title={String(x.where)} onClick={() => selectRoleFinding(i)}>
        {String(x.message)}{x.at ? null : <small>(no position)</small>}</div>); }
  }
  return <div class="list" id="roleFindings">{out}</div>;
}
function Foot({ R }: { R: any }) {
  const nets = inferredRoles(), groups = inferredGroups(), run = rolesRunOffered(), confirm = confirmOffered() && (nets.length + groups.length) > 0;
  const busy = !!RUNS.job || !!window.FenoliteActions?.state?.job;
  return <div class="rfoot">
    {run ? <button type="button" id="rolesRun" class="tb small" disabled={busy} onClick={() => window.FenoliteRuns.start("roles", {})}>
      <Icon name="refresh" size={14} /><span class="lbl">Run roles again</span></button> : null}
    {confirm ? <button type="button" id="rolesConfirm" class="tb small accentBtn" disabled={busy} data-tip="Plan fenolite roles --accept for every inferred role and group"
      onClick={() => confirmRoles(nets, groups)}><Icon name="check" size={14} /><span class="lbl">{`Confirm ${nets.length + groups.length} inferred…`}</span></button> : null}
    {!run && !confirm && nets.length + groups.length ? <p class="hint">{`Confirm with fenolite roles ${R.document || "BOARD"} --accept NET, or serve the page with --allow-actions.`}</p> : null}
  </div>;
}
export function RolesPanel({ R }: { R: any }) {
  const n = R.counts.roles;
  return <>
    <p class="rsum" id="roleSummary">{`${n.declared} declared · ${n.confirmed} confirmed · ${n.inferred} inferred`}<span class="rev">{R.evidence.level}</span></p>
    {(R.notes || []).map((t, k) => <div key={"n" + k} class="notes">{t}</div>)}
    <Legend R={R} />
    <NetRows R={R} />
    <GroupRows R={R} />
    <FindingRows R={R} />
    <Foot R={R} />
  </>;
}
export function buildRoles() {
  const box = $("roleList"); if (!box) return;
  const R = rolesData();
  if (!R && rolesRunOffered()) {   // a served board without role data yet: the run that gives it
    showSection("roles", true, "", "Net roles");
    preact.render(<><Empty text="No role data for this board yet." /><div class="rfoot"><button type="button" id="rolesRun" class="tb small" disabled={!!RUNS.job}
      onClick={() => window.FenoliteRuns.start("roles", {})}><Icon name="play" size={14} /><span class="lbl">Run fenolite roles --check</span></button></div></>, box);
    return;
  }
  if (!R) { showSection("roles", false); preact.render(null, box); return; }
  const f = R.counts.findings;
  showSection("roles", true, R.roles.length, "Net roles", f.error ? "err" : f.warning ? "warn" : "");
  preact.render(<RolesPanel R={R} />, box);
}
// ---- the Roles group of the Layers panel
const OVERLAYS = [["colors", "Role colours", "power"], ["loops", "Loops (hot and gate)", "switch_node"], ["kelvin", "Kelvin pairs", "kelvin"], ["findings", "Role findings", ""]];
export function setRoleView(key, on) { ROLE_VIEW[key] = on; keepRoleView(); draw(); buildLayers(); }
export function RoleLayers() {
  if (!rolesData()) return null;
  const shown = OVERLAYS.filter(([k]) => ROLE_VIEW[k]).length;
  return <section class="lgroup" aria-label="Roles" id="roleLayers">
    <div class="lgHead"><span class="lgTitle">Roles</span><span class="lgN">{`${shown}/${OVERLAYS.length}`}</span></div>
    {OVERLAYS.map(([k, title, kind]) => { const on = !!ROLE_VIEW[k];
      return <div key={k} class={"lrow rlrow" + (on ? "" : " off")} data-overlay={k}>
        <span></span><span class="sw" style={`background:${kind ? roleColor(kind) : SEV_COLOR.warning}`}></span>
        <span class="lname" onClick={() => setRoleView(k, !on)}>{title}</span><span></span>
        <button type="button" class="tb icon small ghost leye" aria-pressed={on} aria-label={`${on ? "Hide" : "Show"} ${title.toLowerCase()}`} data-tip={on ? "Hide" : "Show"}
          onClick={() => setRoleView(k, !on)}><Icon name={on ? "eye" : "eyeOff"} size={14} /></button>
      </div>; })}
  </section>;
}
