// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The run strip of c0302, a Preact component (change c0304, decision 10): under the toolbar, the running job's
// command, its last progress record, the elapsed time and Cancel; after it, the outcome with Dismiss. The
// strip's class names its state (running, done, failed, cancelled).
import * as preact from "preact";
import { $ } from "../core/dom";
import { RUNS, runCancel } from "../review/runs";
import { refreshToolbar } from "./toolbar";

export function RunStrip({ job, message }: { job: any, message: any }) {
  if (job) {
    const last = (job.progress || []).slice(-1)[0], step = last ? [last.step, last.detail].filter(Boolean).join(" · ") : "starting";
    return <><span class="runSpin" aria-hidden="true"></span><b>{job.command}</b><span>{step}</span><span>{`${Number(job.elapsed || 0).toFixed(0)} s`}</span>
      <button id="runCancel" disabled={!!job.cancelling} onClick={() => runCancel()}>Cancel</button></>;
  }
  if (!message) return null;
  return <><span>{message.text}</span>{message.hint ? <small>{message.hint}</small> : null}
    {message.action ? <button id="runAgain" class="primary" onClick={() => { const a = message.action; RUNS.message = null; runStrip(); a.run(); }}>{message.action.label}</button> : null}
    <button onClick={() => { RUNS.message = null; runStrip(); }}>Dismiss</button></>;
}
export function runStrip() {
  const el = $("runStrip"); if (!el) return; const j = RUNS.job, m = RUNS.message;
  el.hidden = !j && !m; el.className = j ? "running" : m ? m.kind : "";
  preact.render(<RunStrip key={j ? "job" : "message"} job={j} message={m} />, el);
  refreshToolbar();   // c0300: Run checks follows the job
}
