// ================================================================== state
const MM = 0.001;   // scene units are micrometres
let qCache = new Map(), PROJECT = null, DOC = null, S = null, cache = null, netCache = new Map(), compCache = new Map(), textCache = new Map(), byLayer = new Map();
const SCENES = new Map(), RAW = new Map();
const SCENE_READS = new Map(), POLLS = new Map();   // latest request per document, including cache invalidations
let navigation = 0, loadingNavigation = 0;
const cv = document.getElementById("cv"); let ctx = cv.getContext("2d"), P2D = Path2D;   // c0189: both swapped while an SVG is recorded
let W = 0, H = 0, dpr = 1;
const view = { cx: 0, cy: 0, s: 5, mirror: false };
const st = { edge: false, epick: [], eres: null, marking: false, checks: true, selFinding: -1, query: null, hl: (() => { try { return localStorage.getItem("fenolite.view.highlight") || "dim"; } catch (e) { return "dim"; } })(), diff: true, single: false, measure: false, mpts: [], selNet: -1, selComp: -1, selOv: -1, opac: 0.6, version: null, mode3d: false, cur: null,
  ovOff: new Set(), ovOpen: new Set() };
const vis = new Map();
const $ = id => document.getElementById(id);

