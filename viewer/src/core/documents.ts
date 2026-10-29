// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { loadBoard } from "../board/load";
import { unpackScene } from "../board/scene";
import { LIB, loadLibrary, setLib, toUnits } from "../library/library";
import { buildProjectReview, REVIEW } from "../panels/project-review";
import { buildTree } from "../panels/tree";
import { runReapply } from "../review/runs";
import { loadSch } from "../sch/load";
import { loadTable } from "../table/table";
import { glc } from "../three/view3d";
import { $, esc, showInfo } from "./dom";
import { cv, DOC, PROJECT, RAW, SCENE_READS, SCENES, setDoc, st } from "./state";
export let navigation = 0, loadingNavigation = 0;
export function docCard(d) {
  REVIEW.doc = null; buildProjectReview();
  $("doccard").style.display = "flex"; $("tablewrap").style.display = "none"; cv.style.display = "none"; glc.style.display = "none";
  $("doctext").innerHTML = `<b style="color:#fff">${esc(d.name)}</b><br>Kind: ${esc(d.kind)}<br>Path: ${esc(d.path)}<br>Size: ${d.size == null ? "—" : d.size + " bytes"}<br>` +
    (d.present ? "" : "<br>The file is not in the project folder.<br>") + (d.viewable ? "" : "<br>Fenolite has no viewer for this kind of document yet.");
}
export async function sceneOf(d) {
  if (SCENES.has(d.id)) return SCENES.get(d.id);
  const read = (SCENE_READS.get(d.id) || 0) + 1; SCENE_READS.set(d.id, read);
  if (RAW.has(d.id)) { const raw = RAW.get(d.id), sc = toUnits(await unpackScene(raw));
    if (SCENE_READS.get(d.id) === read && RAW.get(d.id) === raw) { RAW.delete(d.id); SCENES.set(d.id, sc); } return sc; }
  if (!LIVE) return null;
  const r = await fetch(`scene/${encodeURIComponent(d.id)}.json`, { cache: "no-store" }); if (!r.ok) throw new Error(await r.text());
  const sc = toUnits(await r.json()); if (SCENE_READS.get(d.id) === read) SCENES.set(d.id, sc); return sc;
}
export function invalidateScene(id) {
  SCENES.delete(id); SCENE_READS.set(id, (SCENE_READS.get(id) || 0) + 1);
}
export async function openDoc(d, keepView?) {
  // A successful token lets callers verify ownership again after awaiting this function.
  const generation = ++navigation;
  if (!DOC || DOC.id !== d.id) { st.version = null; if (LIB) { setLib(null); document.body.classList.remove("lib"); } }
  setDoc(d); buildTree(); showInfo(null);
  if (!keepView) { $("fname").textContent = d.name; document.title = d.name + " · Fenolite viewer"; }
  if (!d.viewable || !d.present) { docCard(d); return 0; }
  if (!keepView) { docCard(d); $("doctext").innerHTML += "<br><br>Reading…"; }
  loadingNavigation = generation;
  let sc; try { sc = await sceneOf(d); } catch (e) {
    if (generation === navigation) { docCard(d); $("doctext").innerHTML += `<br><br>Could not read it: ${esc(e.message)}`; } return 0;
  } finally { if (loadingNavigation === generation) loadingNavigation = 0; }
  if (generation !== navigation) return 0;
  if (!sc) { docCard(d); return 0; }
  $("doccard").style.display = "none";
  loadScene(sc, keepView); return generation;
}

export function loadScene(scene, keepView) {
  st.mpts = []; st.mhover = null; st.lastHit = null; st.selFinding = -1;
  $("tablewrap").style.display = "none"; document.body.classList.remove("table"); cv.style.display = "block";
  if (scene.kind === "table") loadTable(scene);
  else if (scene.kind === "library") loadLibrary(scene, keepView);
  else if (scene.kind === "schematic") loadSch(scene, keepView);
  else loadBoard(scene, keepView);
  runReapply(scene);   // c0245: the results of this session's runs
  REVIEW.doc = DOC?.id || null; buildProjectReview();
}

export function allDocs() { return PROJECT ? PROJECT.groups.flatMap(g => g.documents) : []; }

export function docByFile(name) { const want = String(name).replace(/\\/g, "/").split("/").pop().toLowerCase(); return allDocs().find(d => d.name.toLowerCase() === want && d.viewable && d.present); }
