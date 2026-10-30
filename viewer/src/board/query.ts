// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ---- query (c0187): the board filter. key:value terms joined by spaces (and), "|" (or), a leading "-" (not),
// * and ? wildcards, quoted values. Keys: net, ref, footprint, value, layer, side; any other key is the name of a
// part parameter; a bare value matches a reference or a net. Pure functions of a scene, run in Node by the tests.
export function wildRe(v) { return new RegExp("^" + String(v).replace(/[.+^${}()[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$", "i"); }
export function queryParse(text) {
  const s = String(text), groups = [[]]; let i = 0;
  while (i < s.length) {
    if (/\s/.test(s[i])) { i++; continue; }
    if (s[i] === "|") { groups.push([]); i++; continue; }
    let neg = false, key = "", val; if (s[i] === "-") { neg = true; i++; }
    let j = i; while (j < s.length && /[\w.]/.test(s[j])) j++;
    if (j > i && s[j] === ":") { key = s.slice(i, j).toLowerCase(); i = j + 1; }
    if (s[i] === "\"") { const e = s.indexOf("\"", i + 1); val = s.slice(i + 1, e < 0 ? s.length : e); i = e < 0 ? s.length : e + 1; }
    else { j = i; while (j < s.length && !/[\s|]/.test(s[j])) j++; val = s.slice(i, j); i = j; }
    groups[groups.length - 1].push({ key, neg, val, re: wildRe(val) });
  }
  return groups.filter(g => g.length);
}
export function termTest(t, c) {
  const any = vs => vs.some(v => v != null && v !== "" && t.re.test(String(v)));
  let hit;
  if (t.key === "") hit = any([c.ref, ...c.nets]);
  else if (t.key === "net") hit = any(c.nets);
  else if (t.key === "layer") hit = any(c.layers);
  else if (t.key === "ref" || t.key === "footprint" || t.key === "value" || t.key === "side") hit = any([c[t.key]]);
  else { const p = c.params || {}, k = Object.keys(p).find(n => n.toLowerCase() === t.key); hit = k !== undefined && any([p[k]]); }
  return hit !== t.neg;
}
export function queryTest(q, c) { return q.some(g => g.every(t => termTest(t, c))); }
export function queryRun(sc, q) {   // the primitives and the parts of the board scene `sc` that the parsed query `q` matches
  const lt = new Map<any, any>(sc.layers.map(l => [l.id, { tags: [l.id, l.name], side: l.side }]));
  const cn = sc.comps.map(() => new Set()), cl = sc.comps.map(() => new Set()), prims = new Set();
  for (const pr of sc.prims) {
    const L = lt.get(pr[0]) || { tags: [pr[0]], side: "" }, c = pr[4] >= 0 ? sc.comps[pr[4]] : null, net = pr[3] >= 0 ? sc.nets[pr[3]] : "";
    if (c) { if (net) cn[pr[4]].add(net); for (const t of L.tags) cl[pr[4]].add(t); }
    const ctx = { nets: net ? [net] : [], layers: L.tags, ref: c ? c.ref : "", footprint: c ? c.footprint : "", value: c ? c.value : "",
      side: c ? c.side : L.side || "", params: c ? c.params : null };
    if (queryTest(q, ctx)) prims.add(pr);
  }
  const comps = [];
  sc.comps.forEach((c, i) => { if (queryTest(q, { nets: [...cn[i]], layers: [...cl[i]], ref: c.ref, footprint: c.footprint, value: c.value, side: c.side, params: c.params })) comps.push(i); });
  return { prims, comps };
}
export function similarQuery(sc, pr, ci) {   // Find similar: a query for the parts of the same footprint and value, or the same net on the same layer
  const qv = v => `"${String(v).replace(/"/g, "")}"`;
  if (ci >= 0) { const c = sc.comps[ci]; return `footprint:${qv(c.footprint)}` + (c.value ? ` value:${qv(c.value)}` : ""); }
  if (!pr) return "";
  const l = sc.layers.find(x => x.id === pr[0]), layer = `layer:${qv(l ? l.name : pr[0])}`;
  return pr[3] >= 0 ? `net:${qv(sc.nets[pr[3]])} ${layer}` : layer;
}
// ---- end query
