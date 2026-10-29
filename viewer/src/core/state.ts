// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== state
export const MM = 0.001;   // scene units are micrometres
// The state the modules share (change c0272, design decision 5): a `let` that another module assigns has its
// setter here; the objects are mutated in place.
export let PROJECT: any = null, DOC: any = null, S: any = null;
export function setProject(v) { PROJECT = v; }
export function setDoc(v) { DOC = v; }
export function setS(v) { S = v; }
export const SCENES = new Map(), RAW = new Map();
export const SCENE_READS = new Map(), POLLS = new Map();   // latest request per document, including cache invalidations
export const cv = document.getElementById("cv") as HTMLCanvasElement;
export let ctx: any = cv.getContext("2d"), P2D: any = Path2D;   // c0189: both swapped while an SVG is recorded
export function setCtx(v) { ctx = v; }
export function setP2D(v) { P2D = v; }
export const view = { cx: 0, cy: 0, s: 5, mirror: false };
export const st: any = { edge: false, epick: [], eres: null, marking: false, checks: true, selFinding: -1, query: null, hl: (() => { try { return localStorage.getItem("fenolite.view.highlight") || "dim"; } catch (e) { return "dim"; } })(), diff: true, single: false, measure: false, mpts: [], selNet: -1, selComp: -1, selOv: -1, opac: 0.6, version: null, mode3d: false, cur: null,
  ovOff: new Set(), ovOpen: new Set() };
export const vis = new Map();
