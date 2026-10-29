// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// "About this document" (c0243, design decision 6): the developer detail the status bar no longer shows, one
// click away under the document title: file name and path, size, the full SHA-256 with a copy control, the
// backend, the evidence level of the read, the scene version of a live page and the counts of the notes. Nothing
// in it is new data; it reads the tree's document and the scene's meta.
import * as preact from "preact";
import { $ } from "../core/dom";
import { DOC, PROJECT, S, st } from "../core/state";
import { KIND_COLOR } from "../panels/tree";
import { Icon } from "../ui/icons";
import { copyAndSay } from "../ui/toast";

export function fmtBytes(n) {
  if (n == null) return "—";
  const unit = n >= 1048576 ? [1048576, "MB"] : n >= 1024 ? [1024, "kB"] : null;
  return unit ? `${(n / (unit[0] as number)).toFixed(1)} ${unit[1]} · ${n.toLocaleString("en")} bytes` : `${n} bytes`;
}
function countsOf(meta) {
  const c = meta?.counts || {}, words = { footprints: "parts", components: "parts", pads: "pads", tracks: "tracks", vias: "vias", zones: "zones", pins: "pins", wires: "wires", nets: "nets", items: "items" };
  return Object.entries(words).filter(([k]) => typeof c[k] === "number").map(([k, w]) => `${c[k]} ${w}`).join(" · ");
}
export function About() {
  const d = DOC, meta = S && S.meta ? S.meta : {}, notes = (meta.notes || []).length, counts = countsOf(meta);
  const rows: any[] = [["Path", d ? d.path : "—"], ["Kind", d ? d.kind : "—"], ["Size", fmtBytes(d ? d.size : null)]];
  return <>
    <header class="aboutHead">
      <span class="dot" style={`background:${KIND_COLOR[d?.kind] || KIND_COLOR.other}`}></span>
      <div><h2 id="aboutTitle">{d ? d.name : "No document"}</h2><p>{PROJECT ? `${PROJECT.project_file || PROJECT.name} · ${PROJECT.source} project` : ""}</p></div>
      <button type="button" class="tb icon ghost" aria-label="Close" data-tip="Close" onClick={closeAbout}><Icon name="x" /></button>
    </header>
    <dl class="aboutRows">
      {rows.map(([k, v]) => <div><dt>{k}</dt><dd>{v}</dd></div>)}
      <div class="hash"><dt>SHA-256</dt><dd>{meta.sha256 ? <><code id="aboutHash">{meta.sha256}</code>
        <button id="aboutCopy" type="button" class="tb small" onClick={() => copyAndSay(meta.sha256, "SHA-256 copied")}><Icon name="copy" /><span class="lbl">Copy</span></button></> : "not read"}</dd></div>
      <div><dt>Backend</dt><dd>{meta.backend || "—"}</dd></div>
      <div><dt>Evidence</dt><dd><span id="aboutEvidence" class="badge">{meta.evidence || "UNKNOWN"}</span></dd></div>
      {LIVE ? <div><dt>Scene version</dt><dd><code>{st.version || "—"}</code></dd></div> : null}
      {counts ? <div><dt>Contents</dt><dd>{counts}</dd></div> : null}
      <div><dt>Notes</dt><dd>{notes ? `${notes} note${notes === 1 ? "" : "s"} of the read, listed in the side bar` : "None"}</dd></div>
    </dl>
  </>;
}
function aboutOutside(e: Event) { const t = e.target as Element; if (!$("about").contains(t) && !t.closest?.("#bAbout")) closeAbout(); }
function aboutKey(e: KeyboardEvent) { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeAbout(); $("bAbout")?.focus(); } }
export function openAbout() {
  const dlg = $("about"); if (dlg.open) { closeAbout(); return; }
  preact.render(<About />, dlg);
  const b = $("bAbout"), r = b ? b.getBoundingClientRect() : { left: 12, bottom: 44 };
  dlg.style.left = `${Math.max(8, Math.min(r.left - 12, innerWidth - 440))}px`; dlg.style.top = `${r.bottom + 8}px`;
  dlg.show(); dlg.focus();
  document.addEventListener("pointerdown", aboutOutside, true); document.addEventListener("keydown", aboutKey, true);
}
export function closeAbout() {
  const dlg = $("about"); if (dlg.open) dlg.close();
  document.removeEventListener("pointerdown", aboutOutside, true); document.removeEventListener("keydown", aboutKey, true);
}
