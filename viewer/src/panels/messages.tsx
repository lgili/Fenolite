// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The Messages panel of `--check` (c0188), a Preact component (change c0247): the notes, then the findings
// grouped by rule, errors first; a group opens on a click, a finding is selected on the drawing.
import * as preact from "preact";
import { $ } from "../core/dom";
import { S, st } from "../core/state";
import { selectFinding, SEV_COLOR } from "../review/check";
import { showSection } from "../ui/section";

export const MSG_ROWS = 300;
function toggleGroup(code, open) { if (open) st.msgOpen.delete(code); else st.msgOpen.add(code); buildMessages(); }
export function MessagesPanel({ check }: { check: any }) {
  const groups = new Map(); check.findings.forEach((x, i) => { if (!groups.has(x.code)) groups.set(x.code, []); groups.get(x.code).push(i); });
  const out = check.notes.map((note, k) => <div key={"t:" + k} class="notes">{note}</div>);   // keys: as in the Findings panel
  for (const [code, list] of groups) {
    const first = check.findings[list[0]], open = st.msgOpen.has(code) || groups.size === 1;
    out.push(<div key={"g:" + code} class="navg" onClick={() => toggleGroup(code, open)}>
      <span class="sw" style={`display:inline-block;background:${SEV_COLOR[first.severity] || "#888"}`}></span>{` ${open ? "▾" : "▸"} ${code} (${list.length})`}
    </div>);
    if (!open) continue;
    for (const i of list.slice(0, MSG_ROWS)) {
      const x = check.findings[i];   // the title is the location as the panel always set it: "undefined" when there is none
      out.push(<div key={"f:" + i} class={"navi" + (i === st.selFinding ? " sel" : "")} title={String(x.where)} onClick={() => selectFinding(i)}>
        {String(x.message)}{x.at ? null : " "}{x.at ? null : <small>(no position)</small>}
      </div>);
    }
    if (list.length > MSG_ROWS) out.push(<div key={"m:" + code} class="notes">{`… ${list.length - MSG_ROWS} more`}</div>);
  }
  return <>{out}</>;
}
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
export function SevLine({ counts }: { counts: any }) {   // the severity summary at the head of the section
  return <><span class="sev err">{plural(counts.error, "error", "errors")}</span><span class="sev warn">{plural(counts.warning, "warning", "warnings")}</span>
    <span class="sev info">{`${counts.info} info`}</span></>;
}
export function buildMessages() {   // the Messages panel: findings grouped by rule, errors first
  const box = $("msgList"), C = S && S.check, n = C ? C.counts : null;
  showSection("messages", !!C, C ? C.findings.length : undefined, "Messages", n && n.error ? "err" : n && n.warning ? "warn" : "");
  preact.render(n ? <SevLine counts={n} /> : null, $("msgTitle"));
  st.msgOpen = st.msgOpen || new Set();
  preact.render(C ? <MessagesPanel check={C} /> : null, box);
}
