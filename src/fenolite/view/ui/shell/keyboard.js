// ================================================================== keymap choice, the Keyboard panel and the command search (change c0245)
const SETTINGS = (EMBED && EMBED.settings) || {};   // what `fenolite view` gave the page; a live page adds the server's at start
const KEYMAP_KEY = "fenolite.view.keymap";
function keymapDoc() { return { schema: "fenolite.view_keymap.v0", base: KEYMAP, bindings: KEYMAP_USER || {} }; }
function applyKeymap(doc, save) {   // a base keymap and a person's bindings over it
  KEYMAP = doc && KEYMAPS[doc.base] ? doc.base : "fenolite";
  KEYMAP_USER = doc && doc.bindings && Object.keys(doc.bindings).length ? Object.fromEntries(Object.entries(doc.bindings).map(([id, keys]) => [id, keys.map(normSpec)])) : null;
  if (save) try { localStorage.setItem(KEYMAP_KEY, JSON.stringify(keymapDoc())); } catch (e) { /* this page only */ }
  if (typeof decorateToolbar === "function") decorateToolbar();
  if (PANELS.has("keyboard")) buildKeyboard(); if (PANELS.has("shortcuts")) buildKeyTable();
}
function startKeymap() {   // --keymap first, then the person's choice kept in the browser
  if (SETTINGS.keymap) { applyKeymap(SETTINGS.keymap, false); return; }
  try { const kept = JSON.parse(localStorage.getItem(KEYMAP_KEY) || "null"); if (kept && kept.schema === "fenolite.view_keymap.v0") { applyKeymap(kept, false); return; } } catch (e) { /* none kept */ }
  applyKeymap(null, false);
}
function setKeymap(name) { applyKeymap({ base: name, bindings: KEYMAP_USER || {} }, true); say(`Keymap: ${name}.`); }
function keySource(c) {   // where a command's keys in the active keymap come from
  if (KEYMAP_USER && Object.prototype.hasOwnProperty.call(KEYMAP_USER, c.id)) return "your change";
  const s = KEYMAP_DATA.sources[KEYMAP] && KEYMAP_DATA.sources[KEYMAP][c.id];
  return s ? `${KEYMAP} (${s})` : KEYMAPS[KEYMAP] && KEYMAPS[KEYMAP][c.id] ? `${KEYMAP}, Fenolite's choice` : "fenolite";
}
function bindingProblem(id, spec) {   // why a key cannot be bound to a command, or "" (the browser's keys are refused)
  const first = spec.split(" ")[0];
  if (RESERVED.has(first)) return `${keyLabel(first)} belongs to the browser; choose another key.`;
  return "";
}
function conflictsOf(id, spec) { return COMMANDS.filter(c => c.id !== id && keysOf(c).includes(spec)).map(c => c.label); }
function setBinding(id, keys) {
  for (const k of keys) { const p = bindingProblem(id, k); if (p) { kbMessage(p); return false; } }
  KEYMAP_USER = { ...(KEYMAP_USER || {}), [id]: keys.map(normSpec) }; applyKeymap(keymapDoc(), true);
  const clash = keys.flatMap(k => conflictsOf(id, normSpec(k))); kbMessage(clash.length ? `Bound. The same key also runs: ${clash.join(", ")} (the first whose context holds runs).` : "Bound.");
  return true;
}

// ---- the Keyboard panel: every command with its keys, where they come from, and an editor
function buildKeyboard() {
  const body = $("kmTable").tBodies[0], q = $("kmFilter").value.trim().toLowerCase(); body.innerHTML = ""; $("kmSel").value = KEYMAP;
  for (const name of MENUS) for (const c of COMMANDS) {
    if (c.menu !== name) continue; const path = `${name} ▸ ${c.sub ? c.sub + " ▸ " : ""}${c.label}`;
    if (q && !path.toLowerCase().includes(q) && !c.id.includes(q)) continue;
    const keys = keysOf(c), tr = document.createElement("tr"); tr.dataset.cmd = c.id;
    tr.innerHTML = `<td>${esc(path)}</td><td class="kmkeys">${keys.map(k => `<kbd>${esc(keyLabel(k))}</kbd>`).join(" ") || "—"}</td><td>${esc(keySource(c))}</td><td><button class="kmedit" aria-label="Change the keys of ${esc(c.label)}">Change</button></td>`;
    tr.querySelector(".kmedit").onclick = () => captureKeys(c, tr);
    body.appendChild(tr);
  }
}
function captureKeys(c, tr) {   // the next chords pressed: Enter keeps them, Escape cancels, Backspace unbinds
  const cell = tr.querySelector(".kmkeys"), chords = [];
  cell.innerHTML = `<button class="kbcapture" aria-label="Press the new keys of ${esc(c.label)}">Press keys… Enter keeps, Esc cancels, Backspace unbinds</button>`;
  const cap = cell.querySelector(".kbcapture"); cap.focus();
  cap.onkeydown = e => {
    e.preventDefault(); e.stopPropagation();
    if (e.key === "Escape") { buildKeyboard(); kbMessage("Unchanged."); return; }
    if (e.key === "Enter" && !e.ctrlKey && !e.altKey && !e.metaKey) { if (chords.length) setBinding(c.id, [chords.join(" ")]); buildKeyboard(); return; }
    if (e.key === "Backspace" && !chords.length) { setBinding(c.id, []); buildKeyboard(); return; }
    const spec = eventSpec(e); if (!spec) return;
    const p = bindingProblem(c.id, spec); if (p) { kbMessage(p); return; }
    if (chords.length < 3) chords.push(spec); cap.textContent = keyLabel(chords.join(" ")) + " … Enter keeps";
  };
  cap.onblur = () => setTimeout(() => { if (document.activeElement !== cap && cell.contains(cap)) buildKeyboard(); }, 0);
}
function kbMessage(text) { $("kmMessage").textContent = text; }
panel("keyboard", "Keyboard", $("pKeyboard"), { shown: () => buildKeyboard() });
$("kmSel").onchange = e => setKeymap(e.target.value);
$("kmFilter").oninput = () => buildKeyboard();
$("kmDownload").onclick = () => download(JSON.stringify(keymapDoc(), null, 2) + "\n", `keymap-${KEYMAP}.json`, "application/json");
$("kmReset").onclick = () => { applyKeymap({ base: KEYMAP, bindings: {} }, true); kbMessage("Your changes were removed."); };

// ---- the command search: every command by its name, from the keyboard (Ctrl+K)
function openCommandSearch() {
  closeMenu(false);
  const box = document.createElement("div"); box.className = "menu cmdsearch"; box.setAttribute("role", "dialog"); box.setAttribute("aria-label", "Command search");
  box.innerHTML = `<input class="cs-input" placeholder="Type a command…" aria-label="Command"><div class="cs-list" role="listbox"></div>`;
  document.body.appendChild(box); box.style.left = Math.max(8, innerWidth / 2 - 220) + "px"; box.style.top = "60px";
  OPEN_MENU = { el: box, anchor: null, onClose: null };
  const input = box.querySelector(".cs-input"), list = box.querySelector(".cs-list"); let hits = [], at = 0;
  const show = () => { const q = input.value.trim().toLowerCase(); hits = COMMANDS.filter(c => c.when() && (`${c.menu} ${c.sub || ""} ${c.label}`.toLowerCase().includes(q))).slice(0, 12); at = Math.min(at, Math.max(0, hits.length - 1));
    list.innerHTML = hits.map((c, i) => `<div class="mitem" role="option" aria-selected="${i === at}" data-cmd="${c.id}"><span></span><span class="mlbl">${esc(c.menu)} ▸ ${esc(c.label)}</span><span class="mkey">${esc(keyLabel(keysOf(c)[0] || ""))}</span></div>`).join("") || '<div class="notes" style="padding:4px 8px">No command matches.</div>';
    list.querySelectorAll(".mitem").forEach((el, i) => { el.onmousedown = e => { e.preventDefault(); run(i); }; }); };
  const run = i => { const c = hits[i]; closeMenu(false); if (c) c.run(); };
  input.oninput = () => { at = 0; show(); };
  input.onkeydown = e => { if (e.key === "ArrowDown") { e.preventDefault(); at = Math.min(at + 1, hits.length - 1); show(); } else if (e.key === "ArrowUp") { e.preventDefault(); at = Math.max(at - 1, 0); show(); }
    else if (e.key === "Enter") { e.preventDefault(); run(at); } else if (e.key === "Escape") { e.preventDefault(); closeMenu(false); } };
  show(); input.focus();
}

// ---- commands of this part
const FAST_GRIDS = { mm: [0.1, 0.5], mil: [5, 25] };
command({ id: "view.highlight-net", menu: "View", group: "highlight-net", label: "Highlight the Net Under the Cursor", when: () => on2D() && !isSch() && !LIB && !!st.mouse,
  run: () => { const [X, Y] = w2s(st.mouse[0], st.mouse[1]), h = pick(X, Y); if (h && h.pr[3] >= 0) selectNetAt(h.pr[3]); } });
command({ id: "view.grid-fast-1", menu: "View", group: "grid", label: "Fast Grid 1", when: () => onDoc() && !isSch(), run: () => setGrid(FAST_GRIDS[UNIT][0]) });
command({ id: "view.grid-fast-2", menu: "View", group: "grid", label: "Fast Grid 2", when: () => onDoc() && !isSch(), run: () => setGrid(FAST_GRIDS[UNIT][1]) });
for (const name of Object.keys(KEYMAPS))
  command({ id: "tools.keymap-" + name, menu: "Tools", group: "keymap", sub: "Keymap", label: name[0].toUpperCase() + name.slice(1), run: () => setKeymap(name), checked: () => KEYMAP === name });
command({ id: "tools.keyboard", menu: "Tools", group: "keyboard", label: "Keyboard Preferences", run: () => showPanel("keyboard", true) });
command({ id: "tools.command-search", menu: "Tools", group: "keyboard", label: "Command Search", keys: ["Ctrl+K", "Meta+K"], run: openCommandSearch });
