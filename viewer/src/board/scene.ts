// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { decodeV1 } from "./decode";
import { arcOf } from "./geometry";
import { MM } from "../core/state";
import { checkToMM } from "../review/check";
export async function unpackScene(v) {   // c0182: a scene of a standalone page, "gz:" + base64 of its gzipped JSON
  if (typeof v !== "string") return v;
  const bin = Uint8Array.from(atob(v.slice(3)), c => c.charCodeAt(0));
  const text = await new Response(new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  return JSON.parse(text);
}
export function primToMM(pr, f) { const d = pr[2];
  if (pr[1] === "p" || pr[1] === "o" || pr[1] === "h") pr[2] = d.map(r => r.map(f)); else pr[2] = d.map(f);
  if (pr[1] === "a") pr.push(arcOf(pr[2])); }
export function diffToMM(sc) {   // c0184: the changes of --compare, in micrometres like the scene
  const D = sc.diff; if (!D) return; const f = v => v * MM;
  for (const pr of [...(D.added || []), ...(D.removed || [])]) primToMM(pr, f);
  for (const m of D.moved || []) { m.from = m.from.map(f); m.to = m.to.map(f); }
  for (const c of D.changes) if (c.box) c.box = c.box.map(f);
}
export function toMM(scene) {
  decodeV1(scene);
  if (scene.mm) return scene; scene.mm = true; diffToMM(scene); checkToMM(scene);
  for (const p of scene.pads || []) { p.x *= MM; p.y *= MM; }
  const f = v => v * MM;
  for (const pr of scene.prims) primToMM(pr, f);
  for (const t of scene.texts) for (const k of [1, 2, 3, 4, 5]) t[k] = t[k] * MM;
  for (const c of scene.comps) { c.x *= MM; c.y *= MM; if (c.bbox) c.bbox = c.bbox.map(f); }
  for (const r of scene.board) { r.points = r.points.map(f); r.mids = r.mids.map(m => m ? m.map(f) : null); }
  scene.bounds = scene.bounds.map(f); scene.board3d.thickness *= MM;
  for (const b of scene.bodies) { b.ring = b.ring.map(f); b.z0 *= MM; b.z1 *= MM; if (b.zs) b.zs = b.zs.map(f); }
  for (const o of scene.overlays || []) { o.pts = o.pts.map(p => p.map(f)); if (o.bbox) o.bbox = o.bbox.map(f); }
  return scene;
}
