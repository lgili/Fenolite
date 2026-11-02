// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// Edit conflict actions (c0250): the server binds the source; the page sends only a finding and side.
import * as preact from "preact";
import { ACTS, actPlan } from "../actions/actions";
import { S } from "../core/state";

export function conflictChoices(record) {
  return record?.reason === "sides-disagree" ? ["board", "schematic"] : ["code", "cad"];
}
export function conflictTake(finding, side) { return actPlan("take", { finding, side }); }
export function ConflictActions({ finding }: { finding: number }) {
  const record = S?.check?.findings?.[finding]?.conflict, binding = S?.check?.resolve;
  if (!record || !ACTS.enabled) return null;
  if (!ACTS.offer?.take || binding?.why) return <p class="notes" role="status">{binding?.why || "Load a current build reply to review a take."}</p>;
  const labels = { code: "Take code", cad: "Take CAD", board: "Take board", schematic: "Take schematic" };
  return <><p class="notes">{`Planning runs ${binding.script} for ${binding.out}.`}</p>
  <div class="inspActs" role="toolbar" aria-label="Resolve this edit conflict">
    {conflictChoices(record).map(side => <button type="button" class="tb small" id={`conflictTake${side}`}
      disabled={!!ACTS.job} onClick={() => conflictTake(finding, side)}>{labels[side]}</button>)}
  </div></>;
}
