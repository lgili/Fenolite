# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The style sheet and the script of the library gallery (change c0405): written once under ``assets/``.

Plain CSS with a light and a dark palette (``prefers-color-scheme`` until the visitor picks one) and a
little vanilla JavaScript that filters the cards, switches the theme and copies the ``fenolite get``
command. Every page works without the script. Nothing is loaded from another origin.
"""

from __future__ import annotations

CSS = """\
:root{--bg:#f5f7fa;--surface:#ffffff;--surface-2:#eef2f6;--text:#18212f;--muted:#5b6677;--border:#dfe5ec;
--accent:#0f766e;--accent-text:#ffffff;--focus:#14b8a6;--code:#eef2f6;--shadow:0 1px 2px rgba(16,24,40,.05),
0 6px 18px rgba(16,24,40,.07);--symbol:#7c3aed;--footprint:#c2410c;--device:#1d4ed8;--block:#be185d;
--board:#047857;--radius:14px;color-scheme:light}
:root[data-theme=dark]{--bg:#0c1118;--surface:#141b25;--surface-2:#1b2431;--text:#e5eaf1;--muted:#97a2b2;
--border:#253142;--accent:#2dd4bf;--accent-text:#06231f;--focus:#5eead4;--code:#1b2431;
--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);--symbol:#a78bfa;--footprint:#fb923c;
--device:#60a5fa;--block:#f472b6;--board:#34d399;color-scheme:dark}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0c1118;--surface:#141b25;
--surface-2:#1b2431;--text:#e5eaf1;--muted:#97a2b2;--border:#253142;--accent:#2dd4bf;--accent-text:#06231f;
--focus:#5eead4;--code:#1b2431;--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);--symbol:#a78bfa;
--footprint:#fb923c;--device:#60a5fa;--block:#f472b6;--board:#34d399;color-scheme:dark}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 system-ui,-apple-system,"Segoe UI",
Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--accent)}a:hover{text-decoration-thickness:2px}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:.9em}
.wrap{max-width:76rem;margin:0 auto;padding:0 1.25rem}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--surface) 88%,transparent);
backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid var(--border)}
.top .wrap{display:flex;align-items:center;gap:1rem;height:3.75rem}
.brand{display:flex;align-items:center;gap:.6rem;color:var(--text);text-decoration:none;font-weight:700;
letter-spacing:-.01em}
.brand svg{width:1.8rem;height:1.8rem}
.ver{font-weight:600;font-size:.78rem;color:var(--muted);background:var(--surface-2);border:1px solid
var(--border);border-radius:999px;padding:.05rem .5rem}
.top nav{margin-left:auto;display:flex;align-items:center;gap:.25rem}
.top nav a{color:var(--muted);text-decoration:none;padding:.4rem .7rem;border-radius:8px;font-weight:500}
.top nav a:hover,.top nav a[aria-current=page]{color:var(--text);background:var(--surface-2)}
.theme{border:1px solid var(--border);background:var(--surface);color:var(--text);border-radius:8px;
width:2.3rem;height:2.3rem;cursor:pointer;display:grid;place-items:center}
.theme svg{width:1.1rem;height:1.1rem}
main{padding:2rem 0 3rem}
.hero{padding:1.5rem 0 1.25rem}
.hero h1{font-size:clamp(1.8rem,3.5vw,2.6rem);line-height:1.15;margin:0 0 .5rem;letter-spacing:-.02em}
.hero p{color:var(--muted);max-width:46rem;margin:0}
.stats{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0 0;padding:0;list-style:none}
.stats li{background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:.25rem .8rem;
font-size:.88rem;color:var(--muted)}
.stats strong{color:var(--text)}
.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:.75rem;margin:1.5rem 0 1.25rem;padding:.9rem;
background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow)}
.search{flex:1 1 16rem;display:flex;align-items:center;gap:.5rem;background:var(--bg);border:1px solid
var(--border);border-radius:10px;padding:0 .75rem}
.search svg{width:1rem;height:1rem;color:var(--muted);flex:none}
.search input{flex:1;border:0;background:transparent;color:var(--text);font:inherit;padding:.55rem 0;
min-width:0}
.search input:focus{outline:none}
.search:focus-within{outline:3px solid var(--focus);outline-offset:1px}
.chips{display:flex;flex-wrap:wrap;gap:.35rem}
.chip{border:1px solid var(--border);background:var(--bg);color:var(--text);border-radius:999px;
padding:.35rem .8rem;font:inherit;font-size:.88rem;cursor:pointer}
.chip[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--accent-text)}
.toolbar select{font:inherit;font-size:.9rem;color:var(--text);background:var(--bg);border:1px solid
var(--border);border-radius:10px;padding:.45rem .6rem}
.count{color:var(--muted);font-size:.88rem;margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(15.5rem,1fr));gap:1.1rem;margin:0;
padding:0;list-style:none}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;
box-shadow:var(--shadow);transition:transform .15s ease,box-shadow .15s ease}
.card:hover{transform:translateY(-2px)}
.card>a{display:flex;flex-direction:column;height:100%;color:inherit;text-decoration:none}
.thumb{aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;gap:2px;
background:var(--surface-2);border-bottom:1px solid var(--border);overflow:hidden}
.thumb img{width:100%;height:100%;object-fit:contain;display:block;min-width:0}
.thumb.pair img{width:50%}
img.paper{background:#ffffff}img.board{background:#17202b}
.card .body{padding:.85rem 1rem 1rem;display:flex;flex-direction:column;gap:.4rem}
.card h2{font-size:1rem;line-height:1.3;margin:0}
.badges{display:flex;flex-wrap:wrap;gap:.35rem;margin:0}
.badge{display:inline-flex;align-items:center;gap:.3rem;font-size:.75rem;font-weight:600;line-height:1;
padding:.3rem .55rem;border-radius:999px;background:var(--surface-2);color:var(--muted);border:1px solid
var(--border)}
.badge.kind{color:var(--kc);border-color:color-mix(in srgb,var(--kc) 35%,transparent);
background:color-mix(in srgb,var(--kc) 12%,transparent)}
.k-symbol{--kc:var(--symbol)}.k-footprint{--kc:var(--footprint)}.k-device{--kc:var(--device)}
.k-block{--kc:var(--block)}.k-board{--kc:var(--board)}
.badge.ok{color:var(--board)}.badge.warn{color:var(--footprint)}
.attr{color:var(--muted);font-size:.8rem;margin:0;display:-webkit-box;-webkit-line-clamp:3;
-webkit-box-orient:vertical;overflow:hidden}
.empty{text-align:center;color:var(--muted);padding:3rem 1rem}
.crumbs{font-size:.88rem;color:var(--muted);margin:0 0 1rem}
.crumbs a{color:var(--muted)}
.item-head h1{font-size:clamp(1.5rem,3vw,2.1rem);line-height:1.2;margin:.25rem 0 .6rem;letter-spacing:-.015em}
.item-head .summary{color:var(--muted);margin:.6rem 0 0;max-width:50rem}
.previews{display:grid;grid-template-columns:repeat(auto-fit,minmax(18rem,1fr));gap:1rem;margin:1.5rem 0}
.previews figure{margin:0;background:var(--surface);border:1px solid var(--border);
border-radius:var(--radius);
overflow:hidden;box-shadow:var(--shadow)}
.previews img{display:block;width:100%;height:clamp(14rem,36vw,24rem);object-fit:contain;padding:1.25rem;
box-sizing:border-box}
.previews figcaption{padding:.55rem .9rem;font-size:.85rem;color:var(--muted);
border-top:1px solid var(--border)}
.placeholder{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.35rem;
text-align:center;color:var(--muted);padding:2rem 1.25rem;min-height:14rem;
background:repeating-linear-gradient(
-45deg,var(--surface-2) 0 12px,var(--surface) 12px 24px);border:1px dashed var(--border);
border-radius:var(--radius)}
.placeholder svg{width:2.2rem;height:2.2rem}
.placeholder strong{color:var(--text)}
.placeholder .why{font-size:.85rem;max-width:36rem;margin:0;overflow-wrap:anywhere}
.thumb .placeholder{min-height:0;height:100%;width:100%;border:0;border-radius:0;padding:1rem;font-size:.8rem}
.attribution{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--accent);
border-radius:10px;padding:.85rem 1rem;margin:0 0 1.5rem;font-size:.92rem}
.columns{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:1.25rem;align-items:start}
@media (max-width:52rem){.columns{grid-template-columns:1fr}.top nav a.hide-sm{display:none}}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
box-shadow:var(--shadow);padding:1.1rem 1.2rem}
.panel h2{font-size:1rem;margin:0 0 .75rem}
.panel+.panel{margin-top:1.25rem}
table{width:100%;border-collapse:collapse;font-size:.92rem}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--border);vertical-align:top}
th{color:var(--muted);font-weight:600}
.facts th{width:36%}
.facts td{overflow-wrap:anywhere}
.table-wrap{overflow-x:auto}
.cmd{display:flex;align-items:flex-start;gap:.5rem;background:var(--code);border:1px solid var(--border);
border-radius:10px;padding:.55rem .55rem .55rem .8rem}
.cmd code{flex:1;min-width:0;white-space:pre-wrap;overflow-wrap:break-word;align-self:center;padding:.15rem 0}
.copy{flex:none;font:inherit;font-size:.85rem;font-weight:600;border:0;border-radius:8px;cursor:pointer;
padding:.35rem .8rem;background:var(--accent);color:var(--accent-text)}
.links{list-style:none;margin:.5rem 0 0;padding:0;display:grid;gap:.35rem}
.foot{color:var(--muted);font-size:.85rem;border-top:1px solid var(--border);padding:1.5rem 1.25rem 2.5rem}
.result-pass{color:var(--board);font-weight:600}.result-fail{color:var(--block);font-weight:600}
[hidden]{display:none!important}
"""

JS = """\
(function () {
  var d = document, root = d.documentElement;
  var theme = d.querySelector(".theme");
  if (theme) theme.addEventListener("click", function () {
    var now = root.getAttribute("data-theme");
    if (now !== "dark" && now !== "light") {
      now = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    var next = now === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("fenolite-library-theme", next); } catch (e) {}
  });
  Array.prototype.forEach.call(d.querySelectorAll("[data-copy]"), function (button) {
    button.addEventListener("click", function () {
      var text = d.getElementById(button.getAttribute("data-copy")).textContent;
      var done = function () {
        button.textContent = "Copied";
        setTimeout(function () { button.textContent = "Copy"; }, 1600);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done); else done();
    });
  });
  var query = d.getElementById("q"), licence = d.getElementById("licence");
  if (!query || !licence) return;
  var kind = "all", cards = Array.prototype.slice.call(d.querySelectorAll(".card"));
  var empty = d.getElementById("empty"), count = d.getElementById("count");
  function apply() {
    var text = query.value.trim().toLowerCase(), wanted = licence.value, shown = 0;
    cards.forEach(function (card) {
      var ok = (kind === "all" || card.getAttribute("data-kind") === kind) &&
        (wanted === "all" || card.getAttribute("data-licence") === wanted) &&
        (!text || card.getAttribute("data-text").indexOf(text) >= 0);
      card.hidden = !ok;
      if (ok) shown++;
    });
    empty.hidden = shown > 0;
    count.textContent = shown + (shown === 1 ? " item" : " items");
  }
  query.addEventListener("input", apply);
  licence.addEventListener("change", apply);
  Array.prototype.forEach.call(d.querySelectorAll(".chip"), function (chip) {
    chip.addEventListener("click", function () {
      kind = chip.getAttribute("data-kind");
      Array.prototype.forEach.call(d.querySelectorAll(".chip"), function (other) {
        other.setAttribute("aria-pressed", other === chip ? "true" : "false");
      });
      apply();
    });
  });
})();
"""

THEME_BOOT = (
    "<script>try{var t=localStorage.getItem('fenolite-library-theme');"
    "if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t)}catch(e){}</script>"
)
"""Applies a stored theme before the first paint (no flash of the other palette)."""

LOGO = (
    '<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="1" y="1" width="30" height="30" rx="8" '
    'fill="var(--accent)"/><path d="M9 23V9h10M9 16h7" fill="none" stroke="var(--accent-text)" '
    'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><circle cx="23" cy="21" r="3" '
    'fill="var(--accent-text)"/></svg>'
)
THEME_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9 7 7 0 0 1-9-9z" '
    'fill="currentColor"/></svg>'
)
SEARCH_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" '
    'stroke="currentColor" stroke-width="2"/><path d="m20 20-3.5-3.5" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round"/></svg>'
)
NO_IMAGE_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" fill="none" '
    'stroke="currentColor" stroke-width="1.6"/>'
    '<path d="m3 4 18 16" stroke="currentColor" stroke-width="1.6"/>'
    "</svg>"
)

__all__ = ["CSS", "JS", "LOGO", "NO_IMAGE_ICON", "SEARCH_ICON", "THEME_BOOT", "THEME_ICON"]
