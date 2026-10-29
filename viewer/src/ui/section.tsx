// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The side bar's sections (c0243, design decision 5): each panel is a <details class="sect"> whose summary holds
// a chevron, the title and a count; the open state of each is kept in localStorage (fenolite.view.sections).
// A section that has nothing to show for the open document is hidden; showSection() sets its title, count and
// visibility, and keeps the id of the title element the tests and the panels read (diffTitle, msgTitle, …).
import * as preact from "preact";
import { Icon } from "./icons";

export const SECTION_KEY = "fenolite.view.sections";
const sectState = (() => { try { return JSON.parse(localStorage.getItem(SECTION_KEY) || "{}") || {}; } catch (e) { return {}; } })();
const sectHeads = new Map<string, any>();
export function SectionHead({ title, count, titleId, tone }: { title: string, count?: number | string, titleId?: string, tone?: string }) {
  return <>
    <span class="chev"><Icon name="chevRight" size={12} /></span>
    <span class="sectTitle" id={titleId}>{title}</span>
    {count === undefined || count === null || count === "" ? null : <span class={"count" + (tone ? " " + tone : "")}>{String(count)}</span>}
  </>;
}
function renderHead(el: HTMLDetailsElement) {
  const h = sectHeads.get(el.dataset.sect); preact.render(<SectionHead {...h} />, el.querySelector(":scope > summary"));
}
export function initSections() {
  for (const el of document.querySelectorAll<HTMLDetailsElement>("details.sect")) {
    const id = el.dataset.sect;
    sectHeads.set(id, { title: el.dataset.title || id, titleId: el.dataset.titleId || undefined });
    if (id in sectState) el.open = !!sectState[id];
    el.addEventListener("toggle", () => {
      sectState[id] = el.open;
      try { localStorage.setItem(SECTION_KEY, JSON.stringify(sectState)); } catch (e) { /* kept for this page only */ }
    });
    renderHead(el);
  }
}
export function sectionEl(id: string) { return document.querySelector<HTMLDetailsElement>(`details.sect[data-sect="${id}"]`); }
export function showSection(id: string, visible: boolean, count?: number | string, title?: string, tone?: string) {
  const el = sectionEl(id); if (!el) return;
  el.hidden = !visible;
  const h = sectHeads.get(id) || { title: id }; sectHeads.set(id, { ...h, title: title ?? h.title, count, tone });
  renderHead(el);
}
initSections();
