// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { renderInspector, showModel } from "../panels/inspector";
export const $ = (id: string): any => document.getElementById(id);   // any: the page reads value, checked, showModal… of what it finds

// A message of HTML in the inspector (c0269: the dock's Properties tab); a selection uses showModel of panels/inspector.
export function showInfo(html) { if (!html) renderInspector(null); else showModel({ kind: "note", title: "", sections: [], html }); }
export function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" })[c]); }
export function linkify(v) { const t = String(v); return /^https?:\/\/\S+$/i.test(t) ? `<a href="${esc(t)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>` : esc(t); }

export function natural(a, b) { return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" }); }

export function download(text, name, type) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); }
