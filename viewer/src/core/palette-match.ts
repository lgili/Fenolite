// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ---- palette (c0243)
// The matcher of the command palette (design decision 4): case-insensitive; a label that starts with the query
// ranks first, then one where a word starts with it, then one that holds its letters in order (a subsequence);
// shorter labels first within a rank, then the order given. A leading ">" keeps commands, "@" parts and "#" nets.
// Pure functions, run under Node by tests/unit/view/test_page.py -k palette_match.
export const PALETTE_LIMIT = 50;
export const PALETTE_PREFIX = { ">": "command", "@": "part", "#": "net" };
export function paletteScore(q, label) {
  const l = String(label || "").toLowerCase(); if (!q) return 1;
  const len = Math.min(l.length, 999);
  if (l.startsWith(q)) return 3000 - len;
  for (let i = 1; i < l.length; i++) if (!/[a-z0-9]/.test(l[i - 1]) && /[a-z0-9]/.test(l[i]) && l.startsWith(q, i)) return 2000 - len;
  let j = 0; for (let i = 0; i < l.length && j < q.length; i++) if (l[i] === q[j]) j++;
  return j === q.length ? 1000 - len : 0;
}
export function paletteParse(query) {   // the query without its prefix, and the kind the prefix keeps (or null)
  const t = String(query || "").trimStart(), kind = PALETTE_PREFIX[t[0]] || null;
  return { q: (kind ? t.slice(1) : t).trim().toLowerCase(), kind };
}
export function paletteMatch(query, items) {   // items: {kind, label, alt?}; the best PALETTE_LIMIT of them, best first
  const { q, kind } = paletteParse(query), scored = [];
  items.forEach((it, i) => {
    if (kind && it.kind !== kind) return;
    const s = Math.max(paletteScore(q, it.label), it.alt ? paletteScore(q, it.alt) - 500 : 0);
    if (s > 0) scored.push([s, i, it]);
  });
  scored.sort((a, b) => b[0] - a[0] || a[1] - b[1]);
  return scored.slice(0, PALETTE_LIMIT).map(x => x[2]);
}
// ---- end palette
