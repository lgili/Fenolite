const EDIT = { pending: null, receipts: [], busy: false };
const canWrite = () => !!(LIVE && SETTINGS.edit && !FLOAT);
function actionArgv(a) {
const nets = (a.nets || []).join(",");
switch (a.kind) {
case "accept": return ["--accept", nets];
case "accept-all": return ["--accept-all", "--min-confidence", a.value || "high"];
case "set": return a.nets.flatMap(n => ["--set", `${n}=${a.value}`]);
case "reject": return ["--reject", nets];
case "forget": return ["--forget", nets];
case "current": return a.nets.flatMap(n => ["--current", `${n}=${a.value}`]);
case "accept-group": return ["--accept-group", nets];
case "reject-group": return ["--reject-group", nets];
case "forget-group": return ["--forget-group", nets];
}
return [];
}
function actionLine(a) { const D = rolesData(); return ["fenolite", "roles", D ? D.document : "BOARD", ...actionArgv(a), "--dry-run", "--json"].map(w => /[\s"']/.test(w) ? JSON.stringify(w) : w).join(" "); }
function actionLabel(a) { if (a.argv) return a.argv.join(" "); return `${a.kind} ${(a.nets || []).join(", ")}${a.value && a.kind !== "accept-all" ? " = " + a.value : ""}`; }
async function post(route, body) {
const r = await fetch(route, { method: "POST", headers: { "Content-Type": "application/json", "X-Fenolite-Review": "1" }, body: JSON.stringify(body) });
let reply = null; try { reply = await r.json(); } catch (e) { reply = { error: `error ${r.status}` }; }
return { status: r.status, reply };
}
const stepAction = argv => ({ kind: "undo", nets: argv.filter((w, i) => i % 2 === 1 && !w.startsWith("--")), value: undefined, argv });
async function planAction(a, opts = {}) {
if (!canWrite()) { copyAction(a); return null; }
if (EDIT.busy) { say("A plan is being made; wait for it."); return null; }
EDIT.busy = true;
try {
const before = rolesData(), { status, reply } = await post("roles/plan", { doc: DOC.id, argv: opts.argv || actionArgv(a) });
if (status !== 200) { EDIT.pending = { error: reply.error || `error ${status}`, action: a }; buildPending(); showPanel("pending", true); return null; }
EDIT.pending = { action: a, argv: opts.argv || actionArgv(a), plan: reply, before, inverse: opts.inverse || reply.inverse || [], undoOf: opts.undoOf || null, redoOf: opts.redoOf || null };
buildPending(); if (!opts.quiet) showPanel("pending", true); return EDIT.pending;
} finally { EDIT.busy = false; }
}
async function applyPending() {
const p = EDIT.pending; if (!p || !p.plan || EDIT.busy) return false; EDIT.busy = true;
try {
const { status, reply } = await post("roles/confirm", { doc: DOC.id, plan_id: p.plan.plan_id });
if (status !== 200) { p.error = reply.error || `error ${status}`; p.stale = reply.code === "FEN-4002"; buildPending(); return false; }
const receipt = reply.receipt || {}, written = (receipt.files || receipt.written || []).map(f => ({ path: f.path, sha256: f.sha256 }));
EDIT.receipts.push({ label: actionLabel(p.action), command: ["fenolite", "roles", ...p.argv].join(" "), files: written, at: new Date().toISOString() });
if (!p.undoOf && !p.redoOf) { const entry = { label: `roles: ${actionLabel(p.action)}`, action: p.action, argv: p.argv, inverse: p.inverse, after: written };
pushUndo({ label: entry.label, undo: () => runSteps(entry.inverse, entry.after, entry), redo: () => runSteps([entry.argv], null, entry, true) }); }
EDIT.pending = null; ROLES.byDoc.delete(DOC.id); await loadRolesData(DOC); buildRoles(); if (ROLES.sel) showRoleProps(); buildMessages(); draw(); buildPending();
say(`Written: ${written.map(f => f.path).join(", ") || "the role document"}.`); return true;
} finally { EDIT.busy = false; }
}
function discardPending() { if (EDIT.pending && EDIT.pending.plan) post("roles/discard", { doc: DOC.id }); EDIT.pending = null; buildPending(); say("The plan was discarded; nothing was written."); }
async function runSteps(steps, expect, entry, forward) {
if (!canWrite()) { say("Undo of a role write needs the served page with --edit."); return; }
if (!steps.length) { say("Nothing to undo: the write changed nothing."); return; }
for (let i = 0; i < steps.length; i++) {
const argv = steps[i], p = await planAction(forward ? entry.action : stepAction(argv), { argv, quiet: true, inverse: [], undoOf: forward ? null : entry, redoOf: forward ? entry : null });
if (!p) return;
const current = (p.plan.current || []).map(f => f.sha256), unchanged = i > 0 || !expect || expect.every(f => current.includes(f.sha256));
if (!unchanged) { p.note = "The role document changed since the write: review this plan before you apply it."; buildPending(); showPanel("pending", true); return; }
if (!(await applyPending())) { showPanel("pending", true); return; }
}
}
function copyAction(a) {
const line = actionLine(a);
(navigator.clipboard ? navigator.clipboard.writeText(line) : Promise.reject()).then(() => say("Copied: " + line), () => {
EDIT.pending = { readonly: true, action: a, line }; buildPending(); showPanel("pending", true); });
}
function buildPending() {
const box = $("pendingBody"); if (!box) return; const p = EDIT.pending;
if (!p) { box.innerHTML = `<p class="notes">${canWrite() ? "No plan waits. An action of the Net Roles workspace plans a write here; Apply writes it." : "This page writes nothing: serve it with <code>--serve --edit</code> to confirm roles here, or copy the command an action shows."}</p>` + receiptsHtml(); return; }
if (p.readonly) { box.innerHTML = `<p>Run this, then confirm its plan:</p><input readonly class="cmdline" value="${esc(p.line)}" aria-label="Command">`; const i = box.querySelector("input"); i.focus(); i.select(); return; }
if (p.error && !p.plan) { box.innerHTML = `<p class="err">Not planned: ${esc(p.error)}</p><button id="pendDiscard">Close</button>`; $("pendDiscard").onclick = () => { EDIT.pending = null; buildPending(); }; return; }
const plan = p.plan, rows = (plan.result.roles || []), before = p.before ? p.before.roles : [];
const changes = [...new Set((p.action.nets || []).concat(p.action.kind === "accept-all" ? before.filter(r => r.state === "inferred").map(r => r.net) : []))].map(n => {
const o = before.find(r => r.net === n), q = rows.find(r => r.net === n);
return `<tr><td>${esc(n)}</td><td>${o ? esc(`${o.kind} · ${o.state}`) : "—"}</td><td>→</td><td>${q ? esc(`${q.kind} · ${q.source}`) : "—"}</td></tr>`; }).join("");
const files = (plan.result.plan || []).map(f => `<li><code>${esc(f.path)}</code> · ${esc(f.bytes)} bytes · SHA-256 ${esc(String(f.sha256).slice(0, 12))}</li>`).join("");
const n0 = p.before ? p.before.counts.findings : null, n1 = plan.counts || null;
box.innerHTML = `<div class="pendhead"><b>${esc(p.undoOf ? "Undo: " : p.redoOf ? "Redo: " : "")}${esc(actionLabel(p.action))}</b><span class="sfill"></span>` +
`<button id="pendApply" class="primary" ${p.stale ? "disabled" : ""}>Apply</button><button id="pendDiscard">Discard</button>${p.stale ? '<button id="pendAgain">Review again</button>' : ""}</div>` +
(p.note ? `<p class="warn">${esc(p.note)}</p>` : "") + (p.error ? `<p class="err">${esc(p.error)}</p>` : "") +
`<p class="notes">Plan <code>${esc(plan.result.plan_id)}</code> of <code>fenolite roles ${esc(p.argv.join(" "))}</code>; it writes:</p><ul class="files">${files || "<li>nothing</li>"}</ul>` +
(changes ? `<table class="grid"><thead><tr><th>Net</th><th>Before</th><th></th><th>After</th></tr></thead><tbody>${changes}</tbody></table>` : "") +
(n0 && n1 ? `<p class="notes">Findings: ${n0.error} errors · ${n0.warning} warnings before, ${n1.error} errors · ${n1.warning} warnings after.</p>` : "") + receiptsHtml();
$("pendApply").onclick = () => applyPending(); $("pendDiscard").onclick = discardPending; if ($("pendAgain")) $("pendAgain").onclick = () => planAction(p.action);
box.onkeydown = e => { if (e.key === "Enter" && e.target.tagName !== "BUTTON" && !p.stale) { e.preventDefault(); applyPending(); } };
}
function receiptsHtml() { return EDIT.receipts.length ? `<h4>Written here</h4><ul class="files">${EDIT.receipts.slice(-6).reverse().map(r => `<li>${esc(r.at.slice(11, 19))} · ${esc(r.label)} · ${r.files.map(f => `<code>${esc(f.path)}</code> ${esc(String(f.sha256).slice(0, 12))}`).join(", ")}</li>`).join("")}</ul>` : ""; }
MESSAGE_SOURCES.push(() => EDIT.receipts.map((r, i) => ({ key: "receipt:" + i, severity: "info", code: "roles.write", object: r.files.map(f => f.path).join(", "),
message: `${r.label}: wrote ${r.files.map(f => `${f.path} (SHA-256 ${String(f.sha256).slice(0, 12)})`).join(", ")}`, source: "fenolite roles", evidence: "INFERRED", layer: "", placed: false, selected: false, pick: () => showPanel("pending", true) })));
panel("pending", "Pending", $("pPending"), { applies: () => inRoles() || !!EDIT.pending, shown: () => buildPending() });
function selectedNets() { if (ROLES.multi.size) return [...ROLES.multi]; return ROLES.sel && ROLES.sel.kind === "net" ? [ROLES.sel.name] : []; }
function selectedGroups() { return ROLES.sel && ROLES.sel.kind === "group" ? [ROLES.sel.name] : []; }
function act(kind, value) {
const groups = kind.endsWith("-group"), nets = groups ? selectedGroups() : kind === "accept-all" ? [] : selectedNets();
if (!nets.length && kind !== "accept-all") { say(groups ? "Select a group first." : "Select a net first (Ctrl+click selects several)."); return; }
return planAction({ kind, nets, value });
}
function buildRoleActions() {
const bar = $("roleActions"); if (!bar) return; const groups = ROLES.tab === "groups", ro = !canWrite();
const kinds = THEME_DATA.chrome && Object.keys(THEME_DATA.glyphs);
bar.innerHTML = (groups
? `<button data-act="accept-group">Confirm</button><button data-act="reject-group">Reject</button><button data-act="forget-group">Forget</button>`
: `<button data-act="accept">Confirm</button><select id="roleSetKind" aria-label="Set the role">${["", ...kinds].map(k => `<option value="${k}">${k ? "Set: " + k : "Set role…"}</option>`).join("")}</select>` +
`<button data-act="reject">Reject</button><button data-act="forget">Forget</button><input id="roleAmps" placeholder="A" aria-label="Current in amperes" size="3"><button data-act="current">Current</button><button data-act="accept-all" title="Confirm every inferred role and group of high confidence">Confirm all high</button>`) +
(ro ? `<span class="notes" title="Serve with --serve --edit to write">copy only</span>` : "");
for (const b of bar.querySelectorAll("[data-act]")) b.onclick = () => { const k = b.dataset.act; act(k, k === "current" ? $("roleAmps").value.trim() : k === "accept-all" ? "high" : undefined); };
const sel = $("roleSetKind"); if (sel) sel.onchange = () => { if (sel.value) act("set", sel.value); sel.value = ""; };
}
const buildRoles0 = buildRoles;
buildRoles = function () { buildRoles0(); buildRoleActions(); };
command({ id: "roles.confirm", menu: "Roles", group: "write", label: "Confirm the Selected Roles", when: inRoles, run: () => act(ROLES.tab === "groups" ? "accept-group" : "accept") });
command({ id: "roles.reject", menu: "Roles", group: "write", label: "Reject the Selected Roles", when: inRoles, run: () => act(ROLES.tab === "groups" ? "reject-group" : "reject") });
command({ id: "roles.forget", menu: "Roles", group: "write", label: "Forget the Selected Roles", when: inRoles, run: () => act(ROLES.tab === "groups" ? "forget-group" : "forget") });
command({ id: "roles.confirm-all", menu: "Roles", group: "write", label: "Confirm All of High Confidence", when: inRoles, run: () => act("accept-all", "high") });
command({ id: "roles.apply", menu: "Roles", group: "plan", label: "Apply the Pending Plan", when: () => !!(EDIT.pending && EDIT.pending.plan), run: () => applyPending() });
command({ id: "roles.discard", menu: "Roles", group: "plan", label: "Discard the Pending Plan", when: () => !!EDIT.pending, run: () => discardPending() });
