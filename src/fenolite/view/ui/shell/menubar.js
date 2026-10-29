// ================================================================== menu bar and popup menus (change c0245)
// The menu bar is generated from the command registry: one menu per name of MENUS, its entries in
// registration order with separators between groups, each with its key in the active keymap and its
// state. Keyboard use follows the menu bar pattern of the WAI-ARIA Authoring Practices (S-0926): F10
// focuses the bar, Left and Right move between menus, Down, Enter or Space open one, Up and Down move,
// Enter or Space run an entry, Escape closes; Alt with a menu's underlined letter opens it where the browser
// lets the page see that key.
let OPEN_MENU = null;   // { el, anchor, onClose }
function closeMenu(refocus) {
  if (!OPEN_MENU) return; const m = OPEN_MENU; OPEN_MENU = null; m.el.remove();
  if (m.anchor) { m.anchor.setAttribute("aria-expanded", "false"); if (refocus) m.anchor.focus(); }
  if (m.onClose) m.onClose();
}
function menuItems(name) {   // the entries of a menu of the bar, from the registry
  const out = []; let group = null; const subs = new Map();
  for (const c of COMMANDS) {
    if (c.menu !== name || c.hidden) continue;
    const item = { id: c.id, label: c.label, key: keysOf(c)[0] || "", disabled: !c.when(), checked: c.checked ? !!c.checked() : null, run: e => { if (c.when()) c.run(e); } };
    if (c.sub) { if (!subs.has(c.sub)) { const s = { label: c.sub, sub: [] }; subs.set(c.sub, s); if (group !== null && c.group !== group) out.push({ sep: true }); group = c.group; out.push(s); } subs.get(c.sub).sub.push(item); continue; }
    if (group !== null && c.group !== group) out.push({ sep: true });
    group = c.group; out.push(item);
  }
  return out;
}
function openMenu(items, anchor, opts = {}) {   // a popup menu under `anchor` (or at opts.x, opts.y)
  closeMenu(false);
  const el = document.createElement("div"); el.className = "menu"; el.setAttribute("role", "menu");
  if (opts.label) el.setAttribute("aria-label", opts.label);
  const rows = [];
  for (const it of items) {
    if (it.sep) { const s = document.createElement("div"); s.className = "msep"; s.setAttribute("role", "separator"); el.appendChild(s); continue; }
    const b = document.createElement("button"); b.className = "mitem"; b.tabIndex = -1;
    b.setAttribute("role", it.checked == null ? "menuitem" : "menuitemcheckbox"); if (it.checked != null) b.setAttribute("aria-checked", String(it.checked));
    if (it.disabled) b.setAttribute("aria-disabled", "true");
    if (it.id) b.dataset.cmd = it.id;
    b.innerHTML = `<span class="mchk">${it.checked ? "✓" : ""}</span><span class="mlbl">${esc(it.label)}</span><span class="mkey">${esc(it.sub ? "▸" : keyLabel(it.key || ""))}</span>`;
    if (it.sub) b.setAttribute("aria-haspopup", "menu");
    b.onclick = e => { e.stopPropagation(); if (it.disabled) return; if (it.sub) { openSub(it, b); return; } closeMenu(false); if (opts.refocus) opts.refocus.focus(); it.run(e); };
    el.appendChild(b); rows.push(b);
  }
  document.body.appendChild(el);
  const r = anchor ? anchor.getBoundingClientRect() : { left: opts.x || 0, bottom: opts.y || 0, right: opts.x || 0, top: opts.y || 0 };
  const w = el.offsetWidth, h = el.offsetHeight;
  el.style.left = Math.max(0, Math.min(opts.side ? r.right : r.left, innerWidth - w - 2)) + "px";
  el.style.top = Math.max(0, Math.min(opts.side ? r.top : r.bottom, innerHeight - h - 2)) + "px";
  OPEN_MENU = { el, anchor: opts.side ? null : anchor, onClose: opts.onClose };
  if (anchor && !opts.side) anchor.setAttribute("aria-expanded", "true");
  const move = (i) => { const live = rows.filter(x => !x.hasAttribute("aria-disabled") || true); if (!live.length) return; const j = (i + live.length) % live.length; live[j].focus(); };
  el.onkeydown = e => {
    const i = rows.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { e.preventDefault(); move(i + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); move(i < 0 ? rows.length - 1 : i - 1); }
    else if (e.key === "Home") { e.preventDefault(); move(0); }
    else if (e.key === "End") { e.preventDefault(); move(rows.length - 1); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeMenu(true); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (i >= 0) rows[i].click(); }
    else if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && opts.bar) { e.preventDefault(); const sub = rows[i]; if (e.key === "ArrowRight" && sub && sub.getAttribute("aria-haspopup")) { sub.click(); return; } opts.bar(e.key === "ArrowRight" ? 1 : -1); }
    else if (e.key.length === 1 && /\S/.test(e.key)) { const k = e.key.toLowerCase(), from = i + 1; const all = [...rows.slice(from), ...rows.slice(0, from)]; const hit = all.find(x => x.querySelector(".mlbl").textContent.toLowerCase().startsWith(k)); if (hit) hit.focus(); }
  };
  if (opts.focusFirst !== false) move(0);
  return el;
}
function openSub(it, row) {   // a submenu: replaces the open menu, beside its row; Escape returns to the bar
  const parent = OPEN_MENU; const anchor = parent && parent.anchor;
  openMenu(it.sub, row, { side: true, label: it.label, onClose: null, bar: null });
  if (OPEN_MENU) OPEN_MENU.anchor = null;
  if (anchor) { anchor.setAttribute("aria-expanded", "true"); OPEN_MENU.backTo = anchor; }
}
window.addEventListener("mousedown", e => { if (OPEN_MENU && !OPEN_MENU.el.contains(e.target) && !(e.target instanceof Element && e.target.closest("#menubar"))) closeMenu(false); });
window.addEventListener("blur", () => closeMenu(false));

const MNEMONIC = { File: "F", Edit: "E", View: "V", Place: "P", Design: "D", Roles: "O", Route: "U", Tools: "T", Reports: "R", Window: "W", Help: "H" };
function buildMenubar() {
  const bar = $("menubar"); bar.innerHTML = "";
  MENUS.forEach((name, i) => {
    const b = document.createElement("button"); b.className = "menubtn"; b.setAttribute("role", "menuitem"); b.setAttribute("aria-haspopup", "menu");
    b.setAttribute("aria-expanded", "false"); b.tabIndex = i ? -1 : 0; b.dataset.menu = name;
    const m = MNEMONIC[name], at = name.toUpperCase().indexOf(m);
    b.innerHTML = `${esc(name.slice(0, at))}<u>${esc(name[at])}</u>${esc(name.slice(at + 1))}`; b.setAttribute("aria-keyshortcuts", "Alt+" + m);
    const open = () => { const items = menuItems(name); openMenu(items.length ? items : [{ label: "(no commands here yet)", disabled: true, run: () => {} }], b, { label: name, refocus: b, bar: step => barStep(i, step, true) }); };
    b.onclick = () => { if (OPEN_MENU && OPEN_MENU.anchor === b) closeMenu(false); else open(); };
    b.onmouseenter = () => { if (OPEN_MENU && OPEN_MENU.anchor && OPEN_MENU.anchor !== b && OPEN_MENU.anchor.closest("#menubar")) open(); };
    b.onkeydown = e => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); barStep(i, e.key === "ArrowRight" ? 1 : -1, false); }
      else if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
      else if (e.key === "Home") { e.preventDefault(); barStep(-1, 1, false); }
      else if (e.key === "End") { e.preventDefault(); barStep(MENUS.length, -1, false); }
      else if (e.key === "Escape") { e.preventDefault(); b.blur(); cv.focus(); }
    };
    bar.appendChild(b);
  });
}
function barStep(i, step, keepOpen) {
  const btns = [...$("menubar").querySelectorAll(".menubtn")], j = (i + step + btns.length) % btns.length;
  btns.forEach((b, k) => { b.tabIndex = k === j ? 0 : -1; });
  closeMenu(false); btns[j].focus(); if (keepOpen) btns[j].click();
}
window.addEventListener("keydown", e => {   // F10, or Alt with a menu's first letter, reaches the menu bar
  if (e.defaultPrevented || e.isComposing) return;
  const t = e.target; if (t instanceof Element && t.closest("input, select, textarea, dialog[open], .kbcapture")) return;
  if (e.key === "F10" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) { e.preventDefault(); barStep(-1, 1, false); return; }
  if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.code && /^Key[A-Z]$/.test(e.code)) {
    const letter = e.code.slice(3), i = MENUS.findIndex(n => MNEMONIC[n] === letter);
    if (i >= 0 && !resolveKey(eventSpec(e))) { e.preventDefault(); barStep(i - 1, 1, true); }
  }
}, true);
