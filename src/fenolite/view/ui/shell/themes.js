// ================================================================== themes of the workbench and the role palette (change c0245, decision 6)
// The chrome has three themes, `dark` (the default), `light` and `contrast`, as CSS tokens in
// css/workbench.css. A document keeps the palette of its tool (c0178); with the light theme a board is drawn
// in a light variant computed here (Fenolite's own rule: a light background, each layer darkened). The role
// colours were chosen for Fenolite and checked apart under simulated colour-vision deficiency
// (H-G-WB-CVD, S-0928, advice of S-0927); every role also shows its glyph and name, and its overlays use
// their own hatch, so colour is never the only cue. The JSON between the braces is read by the tests as it stands.
const THEME_DATA = {
  "schema": "fenolite.view_theme_data.v0",
  "chrome": ["dark", "light", "contrast"],
  "roles": {
    "dark": {"power": "#b8322c", "switch_node": "#e28900", "ground": "#0f6eb7", "kelvin": "#7ec5a2", "gate": "#d2a2f7", "high_voltage": "#ffff89", "signal": "#777777"},
    "light": {"power": "#631d1d", "switch_node": "#b68500", "ground": "#003a6a", "kelvin": "#2f7157", "gate": "#a357de", "high_voltage": "#775b09", "signal": "#8a8a8a"}
  },
  "glyphs": {"power": "P", "switch_node": "SW", "ground": "G", "kelvin": "K", "gate": "GT", "high_voltage": "HV", "signal": "S"},
  "hatch": {"power": 45, "switch_node": 135, "ground": 0, "kelvin": 90, "gate": -1, "high_voltage": -2, "signal": null},
  "canvas": {"dark": "#101418", "light": "#f4f4f2"}
};
const THEME_KEY = "fenolite.view.theme";
let UI_THEME = "dark";
function startTheme() {   // the person's choice, else the reader's light or dark preference (decision 6, open question 8)
  let t = null; try { t = localStorage.getItem(THEME_KEY); } catch (e) { /* none kept */ }
  if (!THEME_DATA.chrome.includes(t)) t = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  applyTheme(t, false);
}
function applyTheme(name, save) {
  UI_THEME = THEME_DATA.chrome.includes(name) ? name : "dark"; document.documentElement.dataset.uiTheme = UI_THEME;
  if (save) try { localStorage.setItem(THEME_KEY, UI_THEME); } catch (e) { /* this page only */ }
  LIGHT_CACHE.clear(); if (S && S.layers) { buildTabs(); draw(); }
}
const roleTone = () => UI_THEME === "light" ? "light" : "dark";
function roleColor(kind) { return THEME_DATA.roles[roleTone()][kind] || THEME_DATA.roles[roleTone()].signal; }
function roleGlyph(kind) { return THEME_DATA.glyphs[kind] || "?"; }
// ---- the light variant of a board palette: Fenolite's rule, no value of a tool's theme
const LIGHT_CACHE = new Map();
function hexHsl(hex) { const n = parseInt(hex.slice(1, 7), 16), r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2; let h = 0, s = 0;
  if (mx !== mn) { const d = mx - mn; s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn); h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h /= 6; }
  return [h, s, l]; }
function hslHex(h, s, l) { const f = n => { const k = (n + h * 12) % 12, a = s * Math.min(l, 1 - l); return Math.round(255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)))); };
  return "#" + [f(0), f(8), f(4)].map(v => v.toString(16).padStart(2, "0")).join(""); }
function lightLayer(hex) {   // a layer colour readable on a light board: its hue, darkened, a little more saturated
  if (!/^#[0-9a-f]{6}/i.test(hex)) return hex; if (LIGHT_CACHE.has(hex)) return LIGHT_CACHE.get(hex);
  const [h, s, l] = hexHsl(hex), out = hslHex(h, Math.min(1, s * 1.1 + 0.05), Math.max(0.22, Math.min(0.42, l * 0.6)));
  LIGHT_CACHE.set(hex, out); return out;
}
function layerColor(l) { return UI_THEME === "light" && S && !isSch() ? lightLayer(l.color) : l.color; }
function boardTheme(th) {   // the background, board and grid colours of a board in the current theme
  if (UI_THEME !== "light") return th;
  return { ...th, background: "#f4f4f2", board: "#e6e8e1", grid: "#a9aeb5" };
}
for (const [name, label] of [["dark", "Dark"], ["light", "Light"], ["contrast", "High Contrast"]])
  command({ id: "view.theme-" + name, menu: "View", group: "theme", sub: "Theme", label, run: () => applyTheme(name, true), checked: () => UI_THEME === name });
