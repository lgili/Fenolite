// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// Short confirmations (c0243): "Link copied", "Copied", a copy that failed. One message at a time at the foot of
// the drawing, read by screen readers (role="status"), gone after three seconds. And the clipboard: the
// asynchronous API, else a hidden textarea and execCommand("copy") for a page opened from file:// (c0244).
import * as preact from "preact";

const toastHost = document.createElement("div"); toastHost.id = "toastHost"; document.body.appendChild(toastHost);
let toastTimer = 0;
export function toast(text: string, kind = "ok") {
  clearTimeout(toastTimer);
  preact.render(<div id="toast" class={kind} role="status" aria-live="polite">{text}</div>, toastHost);
  toastTimer = setTimeout(() => preact.render(null, toastHost), 3000);
}
export async function copyText(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* refused: the fallback below */ }
  const area = document.createElement("textarea"); area.value = text; area.setAttribute("readonly", "");
  area.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0"; document.body.appendChild(area);
  const focus = document.activeElement as HTMLElement; area.select();
  let ok = false; try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
  area.remove(); focus?.focus?.(); return ok;
}
export async function copyAndSay(text: string, what = "Copied") {
  const ok = await copyText(text); toast(ok ? what : "The browser refused the clipboard: select the text and copy it", ok ? "ok" : "err"); return ok;
}
