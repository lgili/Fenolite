// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { esc } from "../core/dom";
import { S, st } from "../core/state";
import { SEV_COLOR, selectFinding } from "../review/check";
import { $ } from "../core/dom";
export const MSG_ROWS = 300;
export function buildMessages() {   // the Messages panel: findings grouped by rule, errors first
  const box = $("msgList"), C = S && S.check; box.innerHTML = ""; $("msgTitle").style.display = C ? "" : "none"; if (!C) return;
  const n = C.counts; $("msgTitle").textContent = `Messages: ${n.error} errors · ${n.warning} warnings · ${n.info} info`;
  for (const note of C.notes) { const d = document.createElement("div"); d.className = "notes"; d.textContent = note; box.appendChild(d); }
  const groups = new Map(); C.findings.forEach((x, i) => { if (!groups.has(x.code)) groups.set(x.code, []); groups.get(x.code).push(i); });
  st.msgOpen = st.msgOpen || new Set();
  for (const [code, list] of groups) {
    const first = C.findings[list[0]], open = st.msgOpen.has(code) || groups.size === 1, h = document.createElement("div"); h.className = "navg";
    h.innerHTML = `<span class="sw" style="display:inline-block;background:${SEV_COLOR[first.severity] || "#888"}"></span> ${open ? "▾" : "▸"} ${esc(code)} (${list.length})`;
    h.onclick = () => { if (open) st.msgOpen.delete(code); else st.msgOpen.add(code); buildMessages(); }; box.appendChild(h);
    if (!open) continue;
    for (const i of list.slice(0, MSG_ROWS)) { const x = C.findings[i], d = document.createElement("div"); d.className = "navi" + (i === st.selFinding ? " sel" : "");
      d.innerHTML = `${esc(x.message)}${x.at ? "" : " <small>(no position)</small>"}`; d.title = x.where; d.onclick = () => selectFinding(i); box.appendChild(d); }
    if (list.length > MSG_ROWS) { const d = document.createElement("div"); d.className = "notes"; d.textContent = `… ${list.length - MSG_ROWS} more`; box.appendChild(d); }
  }
}
