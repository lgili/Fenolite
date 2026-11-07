// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The tooltip (c0300, design decision 3): one positioned element that shows the title of the control under the
// pointer or with the keyboard focus, after 400 ms, and its shortcut in <kbd>. A control declares them as
// data-tip and data-keys (keys separated by commas); native title tooltips are not used for these controls.
import * as preact from "preact";

let tipTimer = 0, tipFor: HTMLElement = null;
const tipHost = document.createElement("div"); tipHost.id = "tipHost"; document.body.appendChild(tipHost);
export function Tooltip({ text, keys, x, y, below }: { text: string, keys: string[], x: number, y: number, below: boolean }) {
  return <div id="tip" role="tooltip" class={below ? "below" : "above"} style={`left:${x}px;top:${y}px`}>
    <span>{text}</span>{keys.map(k => <kbd>{k}</kbd>)}
  </div>;
}
export function hideTip() { clearTimeout(tipTimer); tipFor = null; preact.render(null, tipHost); }
function showTip(el: HTMLElement) {
  if (!el.isConnected || el.getAttribute("aria-expanded") === "true") return;
  const r = el.getBoundingClientRect(), keys = (el.dataset.keys || "").split(",").map(k => k.trim()).filter(Boolean);
  const below = r.bottom + 40 < innerHeight;
  const x = Math.min(Math.max(8, r.left + r.width / 2), innerWidth - 8), y = below ? r.bottom + 6 : r.top - 6;
  preact.render(<Tooltip text={el.dataset.tip} keys={keys} x={x} y={y} below={below} />, tipHost);
  const tip = tipHost.firstElementChild as HTMLElement;   // kept inside the window
  if (tip) { const w = tip.offsetWidth; tip.style.left = `${Math.min(Math.max(8 + w / 2, x), innerWidth - 8 - w / 2)}px`; }
}
function tipTarget(e: Event) { const t = e.target as Element; return t && t.closest ? t.closest("[data-tip]") as HTMLElement : null; }
function arm(el: HTMLElement) { if (el === tipFor) return; hideTip(); if (!el || !el.dataset.tip) return; tipFor = el; tipTimer = setTimeout(() => showTip(el), 400); }
document.addEventListener("pointerover", e => arm(tipTarget(e)));
document.addEventListener("pointerout", e => { const to = (e as PointerEvent).relatedTarget as Element; if (!to || !tipFor || !tipFor.contains(to)) hideTip(); });
document.addEventListener("focusin", e => { const el = tipTarget(e); if (el && (el as any).matches(":focus-visible")) arm(el); else hideTip(); });
document.addEventListener("focusout", hideTip);
for (const type of ["pointerdown", "keydown", "wheel", "scroll"]) document.addEventListener(type, hideTip, true);
