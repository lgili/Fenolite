// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { DIFF_COLOR } from "../board/diff";
import { esc } from "../core/dom";
import { S } from "../core/state";
import { fit } from "../core/viewport";
import { $ } from "../core/dom";
export function buildDiffList() {
  const box = $("diffList"), D = S && S.diff; box.innerHTML = ""; $("diffTitle").style.display = D ? "" : "none"; if (!D) return;
  $("diffTitle").textContent = `Changes since ${D.old.name} (${D.changes.length})`;
  D.changes.forEach(c => { const d = document.createElement("div"); d.className = "navi"; d.innerHTML = `<span class="sw" style="background:${DIFF_COLOR[c.kind] || "#888"}"></span> ${esc(c.text)}`;
    if (c.box) d.onclick = () => { const b = c.box, m = Math.max(b[2] - b[0], b[3] - b[1], 1) * 0.6; fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); };
    box.appendChild(d); });
}
