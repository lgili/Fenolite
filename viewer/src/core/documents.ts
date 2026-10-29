// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import * as preact from "preact";
import { loadBoard } from "../board/load";
import { unpackScene } from "../board/scene";
import { LIB, loadLibrary, setLib, toUnits } from "../library/library";
import { buildProjectReview, REVIEW } from "../panels/project-review";
import { buildTree } from "../panels/tree";
import { runReapply } from "../review/runs";
import { loadSch } from "../sch/load";
import { loadTable } from "../table/table";
import { glc } from "../three/view3d";
import { DocCard, setLoading } from "../ui/states";
import { $, showInfo } from "./dom";
import { cv, DOC, PROJECT, RAW, SCENE_READS, SCENES, setDoc, st } from "./state";
import { setDocTitle } from "../panels/toolbar";
import { refreshDock } from "../panels/dock";
import { refreshSummary } from "../panels/inspector";
import { refreshToolbar } from "../panels/toolbar";
import { ACTS, actionsLoad } from "../actions/actions";
import { PREVIEW_MODE } from "./env";
export let navigation = 0, loadingNavigation = 0;
export function docCard(d, state?, error?) {   // the card over the drawing (c0300): reading, a failed read with Retry, nothing to draw
  REVIEW.doc = null; buildProjectReview(); preact.render(null, $("infoEmpty"));
  $("doccard").style.display = "flex"; $("tablewrap").style.display = "none"; cv.style.display = "none"; glc.style.display = "none";
  const kind = state || (!d.present ? "missing" : !d.viewable ? "noviewer" : "empty");
  const project = !allDocs().some(x => x.viewable && x.present);
  preact.render(preact.h(DocCard, { doc: d, state: kind, error, project, onRetry: () => retryDoc(d) }), $("doctext"));
}
export function retryDoc(d) {   // Retry of a failed read: only while that document is still the one chosen
  if (!DOC || DOC.id !== d.id) return; invalidateScene(d.id); openDoc(d);
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
  if (!keepView) setDocTitle(d.name);
  if (!d.viewable || !d.present) { docCard(d); return 0; }
  if (!keepView) docCard(d, "reading");
  loadingNavigation = generation; setLoading(true);
  let sc; try { sc = await sceneOf(d); } catch (e) {
    if (generation === navigation) docCard(d, "error", e.message); return 0;
  } finally { if (loadingNavigation === generation) { loadingNavigation = 0; setLoading(false); } }
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
  runReapply(scene);   // c0302: the results of this session's runs
  refreshDock(); refreshSummary(); refreshToolbar();   // c0301: the dock's tabs and the document's summary
  if (LIVE && !PREVIEW_MODE && DOC && ACTS.doc !== DOC.id) { ACTS.doc = DOC.id; actionsLoad(); }   // c0303: what the inspector may offer
  REVIEW.doc = DOC?.id || null; buildProjectReview();
}

export function allDocs() { return PROJECT ? PROJECT.groups.flatMap(g => g.documents) : []; }

export function docByFile(name) { const want = String(name).replace(/\\/g, "/").split("/").pop().toLowerCase(); return allDocs().find(d => d.name.toLowerCase() === want && d.viewable && d.present); }
