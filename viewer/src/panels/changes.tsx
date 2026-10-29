// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The Changes panel of `--compare` (c0184), a Preact component (change c0247): one row per change, coloured by
// its kind; a row with a box frames it.
import * as preact from "preact";
import { DIFF_COLOR } from "../board/diff";
import { $ } from "../core/dom";
import { S } from "../core/state";
import { fit } from "../core/viewport";
import { showSection } from "../ui/section";

function frameChange(b) { const m = Math.max(b[2] - b[0], b[3] - b[1], 1) * 0.6; fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); }
export function ChangesPanel({ changes }: { changes: any[] }) {
  return <>{changes.map(c => (
    <div class="navi" onClick={c.box ? () => frameChange(c.box) : undefined}>
      <span class="sw" style={`background:${DIFF_COLOR[c.kind] || "#888"}`}></span>{` ${c.text}`}
    </div>))}</>;
}
export function buildDiffList() {
  const box = $("diffList"), D = S && S.diff;
  showSection("changes", !!D, D ? D.changes.length : undefined, D ? `Changes since ${D.old.name}` : "Changes");
  preact.render(D ? <ChangesPanel changes={D.changes} /> : null, box);
}
