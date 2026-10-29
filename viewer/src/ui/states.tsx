// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// Loading, empty and error states (c0300, design decision 7): the document card over the drawing (reading,
// a failed read with Retry, a missing file, a kind without a viewer, a project without a viewable document), the
// indeterminate progress bar under the toolbar, and the line a list shows when it has nothing to list.
import * as preact from "preact";
import { Icon } from "./icons";

export const VIEWABLE_KINDS = ["Boards (.kicad_pcb, .PcbDoc)", "Schematics (.kicad_sch, .SchDoc)", "Symbol and footprint libraries",
  "Draftsman drawings (.PCBDwf)", "Bills of materials and output jobs"];
function fmtSize(n) { return n == null ? "size unknown" : n >= 1024 ? `${(n / 1024).toFixed(1)} kB` : `${n} bytes`; }
export function DocCard({ doc, state, error, onRetry, project }: { doc: any, state: string, error?: string, onRetry?: () => void, project?: boolean }) {
  const icon = state === "error" ? "alert" : state === "reading" ? "doc" : "info";
  return <div class={"cardBox " + state} role={state === "error" ? "alert" : "status"}>
    <div class="cardIc"><Icon name={icon} size={20} /></div>
    <div class="cardMain">
      <h2>{doc ? doc.name : "Nothing to show"}</h2>
      {doc ? <p class="cardMeta">{`${doc.kind} · ${doc.path} · ${fmtSize(doc.size)}`}</p> : null}
      {state === "reading" ? <p>Reading… <span class="spin" aria-hidden="true"></span></p> : null}
      {state === "error" ? <><p class="cardErr">{`Could not read it: ${error}`}</p>
        <div class="cardActions"><button id="docRetry" type="button" class="tb accentBtn" onClick={onRetry}><Icon name="refresh" /><span class="lbl">Retry</span></button></div></> : null}
      {state === "missing" ? <p>The file is not in the project folder.</p> : null}
      {state === "noviewer" ? <p>{project ? "This project holds no document Fenolite can draw yet." : "Fenolite has no viewer for this kind of document yet."}</p> : null}
      {state === "noviewer" || state === "missing" ? <><p class="cardSub">These kinds open in the viewer:</p>
        <ul class="cardKinds">{VIEWABLE_KINDS.map(k => <li>{k}</li>)}</ul></> : null}
      {state === "empty" ? <p>The scene is empty.</p> : null}
    </div>
  </div>;
}
export function Empty({ text, icon }: { text: string, icon?: string }) {
  return <div class="empty" role="note"><Icon name={icon || "info"} /><span>{text}</span></div>;
}
export function emptyNote(box: HTMLElement, text: string, icon?: string) { preact.render(<Empty text={text} icon={icon} />, box); }
export function setLoading(on: boolean) { document.getElementById("progress")?.classList.toggle("on", on); }
