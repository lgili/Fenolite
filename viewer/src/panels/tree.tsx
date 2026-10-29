// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== project tree (left panel)
// A Preact component (c0243): the project, its groups (each folds) and their documents, the open one marked; a
// document that is missing or has no viewer says so.
import * as preact from "preact";
import { openDoc } from "../core/documents";
import { $ } from "../core/dom";
import { setSidebar } from "../core/input";
import { DOC, PROJECT } from "../core/state";
import { Icon } from "../ui/icons";
import { showSection } from "../ui/section";
export const KIND_COLOR = { pcb: "#3fb950", schematic: "#d29922", "schematic-library": "#a371f7", "pcb-library": "#58a6ff", "integrated-library": "#58a6ff", "output-job": "#8b949e", rules: "#8b949e",
  stackup: "#8b949e", project: "#8b949e", "library-table": "#8b949e", draftsman: "#db61a2", other: "#6e7681" };
export const TREE_CLOSED = new Set<string>();
export function ProjectTree({ project }: { project: any }) {
  return <>
    <div class="proj" title={`${project.source} project`}><Icon name="folder" /><span>{project.project_file || project.name}</span></div>
    {project.groups.map(g => { const closed = TREE_CLOSED.has(g.name);
      return <div class="grpBox" key={g.name}>
        <div class={"grp" + (closed ? " closed" : "")} role="button" tabIndex={0} aria-expanded={Boolean(!closed)}
          onClick={() => toggleTreeGroup(g.name)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleTreeGroup(g.name); } }}>
          <span class="chev"><Icon name="chevRight" size={12} /></span><span class="grpName">{g.name}</span><span class="grpN">{g.documents.length}</span></div>
        {closed ? null : <div class="grpList">{g.documents.map(d =>
          <div key={d.id} class={"doc" + (DOC && DOC.id === d.id ? " sel" : "") + (d.present ? "" : " missing") + (d.viewable ? "" : " noview")}
            role="button" tabIndex={0} aria-current={DOC && DOC.id === d.id ? "true" : undefined}
            title={`${d.path} · ${d.kind}${d.present ? d.viewable ? "" : " (no viewer yet)" : " (missing)"}`}
            onClick={() => { openDoc(d); setSidebar(false); }} onKeyDown={e => { if (e.key === "Enter") { openDoc(d); setSidebar(false); } }}>
            <span class="ic" style={`background:${KIND_COLOR[d.kind] || KIND_COLOR.other}`}></span><span class="docName">{d.name}</span>
          </div>)}</div>}
      </div>; })}
  </>;
}
function toggleTreeGroup(name) { if (TREE_CLOSED.has(name)) TREE_CLOSED.delete(name); else TREE_CLOSED.add(name); buildTree(); }
export function buildTree() {
  const docs = PROJECT ? PROJECT.groups.reduce((n, g) => n + g.documents.length, 0) : 0;
  showSection("project", true, docs || undefined, "Project");
  preact.render(PROJECT ? <ProjectTree project={PROJECT} /> : null, $("tree"));
}
