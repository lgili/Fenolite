## Context

- **What exists** on `dev` at `5191911`, in the modules of `viewer/src/` that c0247 (`viewer-build`) made
  from the old `page.html` (built into `src/fenolite/view/static/` and committed):
  - `select(h, at)` (`board/info.ts`, with `compInfo`, `padInfo`) builds an HTML string for the hit primitive (layer, net, `compInfo`, track width and
    length, arc radius, `padInfo`, hole or circle diameter) and passes it to `showInfo(html)`, (`core/dom.ts`) which fills
    `#info`, an absolutely placed box at the top right of `#wrap`. Sheets (`schSelect`), libraries,
    Draftsman drawings, keep-outs, findings (`selectFinding`) and the catalog fill the same box.
  - `draw()` (`board/draw.ts`, with `paintCache` of `board/cache.ts`) paints every layer at `alpha × HL_ALPHA[st.hl]` (Dim 0.28, Mask 0.06, Normal 1) while something
    is picked, then repaints the picked net or part with `lighten(l.color, 0.45)` at opacity 1. A pour of the
    net becomes a pale sheet over the board.
  - `buildTabs()` (`board/tabs.ts`) fills `#tablist` in the bottom bar `#tabs` with one `.tab` per layer of `tabLayers()`;
    `#ls` opens `#lsmenu` (layer sets). Each layer has `l.alpha` (used by `draw`), `vis` holds visibility,
    `st.cur` the current layer, `st.single` single-layer mode. In schematic view `#tablist` holds the sheet
    tabs instead.
  - 3D (`three/view3d.ts`, matrices in `three/math.ts`): `init3D()` builds two programs whose fragment shaders light by `abs(dot(N, uL))` with an ambient of
    0.42; `#bar3d` holds Top, Bottom, Iso and a Bodies checkbox; `camPreset(kind)` sets yaw and pitch. Bodies
    without a model are extruded outlines drawn with `uBody`, a grey.
  - Tests read `$("info")` (`tests/visual/test_interaction.py`, `test_catalog.py`, `test_navigation.py`) and
    `test_page.py` requires the ids `tree`, `tablist`, `ls`, `cv`, `gl`, `status`.
- **Builds on c0243**: tokens (`--accent`, `--focus`, the new `--emphasis`), the command registry and the
  toolbar groups. This change can land without c0245 and c0246.
- **Module structure (c0247).** UI is Preact, the renderers stay hand-written; a module's top-level names stay
  page globals; every change of `viewer/` is committed with its rebuilt bundle (`make viewer`). Where each part
  goes:

| part | module | form |
|---|---|---|
| dock, tabs, resize | `viewer/src/panels/dock.tsx`; the grid column in `styles/` | Preact |
| inspector model and rendering | `viewer/src/inspect/model.ts` (models from hits: `board/info.ts`, `sch/select.ts`, `library/library.ts`, `review/check.ts`), `panels/inspector.tsx` (`renderInspector`) | TS, Preact |
| inspector actions | registry commands in `core/commands.ts` (c0243) with a `target` | TS |
| net emphasis | `board/draw.ts`, `board/cache.ts` (hand-written canvas code) | TS |
| Layers panel | `viewer/src/panels/layers.tsx`; `board/tabs.ts` keeps `tabLayers()`, the sheet tabs stay in `sch/load.ts` | Preact |
| 3D controls | `three/view3d.ts` (lighting, presets), `three/view-cube.ts` (the cube, canvas), `panels/view3d-panel.tsx` | TS, Preact |

## Goals / Non-goals

- **Goals:** properties beside the drawing, never over it; every value copyable; a next step from the
  selection; a net that stands out; every layer reachable with its full name; a 3D view that is easy to
  orient.
- **Non-goals:** the proposal's.

## Decisions

### 1. The right dock

`#dock` is a third grid column of 320 px at the right of `#wrap`, with two tabs, **Properties** and
**Layers** (the 3D panel replaces Layers in 3D), a collapse control (`I` toggles it, a registry command) and
a resize handle (240 to 480 px, kept in `localStorage`). The Properties body keeps the id `info`, so
`showInfo(html)` and the tests that read `$("info")` keep working while the content becomes structured.
When nothing is selected the Properties tab shows the document summary (counts, layers, notes) instead
of an empty box. Below 760 px the dock becomes a bottom sheet of at most 60 % of the height, opened by a
selection and dismissed by `Esc` or its close button; the canvas keeps the full width.

### 2. Inspector model

`select()` and its siblings build an inspector model instead of HTML: `{kind, title, sections: [{title,
rows: [{label, value, raw, unit?, copy?, link?}]}], actions: [...]}`, rendered by one Preact component,
`renderInspector(model)` in `panels/inspector.tsx`. Sections by hit: **Part** (reference, value, footprint, side, position, rotation,
extent, parameters, variant state), **Pad** (number, shape, size, corner radius, drill and slot, layers,
mask and paste openings with their source), **Track** (width, length, layer, net), **Arc** (width, radius,
angle), **Via** (diameter, drill, layers, tenting), **Zone** (net, layer, filled area, unfilled flag),
**Net** (name, pads, routed length, layers), **Keep-out** (what it forbids), **Finding** (code, severity,
stage, evidence, message, hint). Lengths format in the page unit (`fmtLen`) and change with `Q`; the copy
control copies the displayed text, "Copy all" copies the sections as `label: value` lines. Copy uses
`navigator.clipboard.writeText` with a fallback through a hidden textarea and `execCommand("copy")` for
`file://` pages. Values the scene does not hold are left out, never shown as 0.

### 3. Inspector actions

Actions are registry commands with a `target` (part index, net index, finding index): **Zoom to**
(existing `fit` on the box), **Highlight net** (`selectNetAt`), **Select part** (`selectCompAt`), **Find
similar** (existing `bSimilar` logic), **Show in schematic** / **Show on board** (the cross-probe that a
double click runs, under its navigation guard; hidden when the project has no other document holding the
part), **Open finding** (`selectFinding`). Each is also in the palette for the current selection.

### 4. Net emphasis

`draw()` changes for a picked net or part: the rest of the board is painted at `alpha × HL_ALPHA[st.hl]`
as today; the picked items are painted in their own layer colour at opacity 1 (no `lighten`), then stroked
with a 1.5 px outline in `--emphasis` (resolved once per theme). Zone fills of the picked net are painted at
opacity 0.55 with the outline, so the net's tracks and pads stay readable over its pour. Dim's default
factor becomes 0.22. The same rule applies to the filter query's results. Schematic net highlight is
unchanged (its dim of 0.22 already stands).

### 5. Layers panel

The Layers tab lists `tabLayers()` in groups: Copper, Mask and paste, Silkscreen, Mechanical and
fabrication, View (drill, ratsnest, zone outlines, checks). A row holds the swatch, the full name (wrapped,
never cut; the native name of Altium layers), a visibility toggle (`aria-pressed`), an opacity slider that
sets `l.alpha` (0 to 100 %, stored per document in the link only for the current layer) and a radio for the
current layer. A group header toggles its group. The presets are the layer sets of `#lsmenu` (all,
signal, top side, bottom side, defaults) plus "Current layer only" (`Shift+S`); `+` and `-` step the current
layer as today; the "Other side" opacity of c0243's Top/Bottom popover stays the opacity of the far side.
On boards and footprints the bottom bar no longer lists layers; on sheets it keeps the sheet tabs. The ids
`tablist` and `ls` stay (sheet tabs, presets menu); `test_page.py` gains `layerList`.

### 6. 3D controls

- **2D-only controls hidden in 3D:** Measure, Edge gap, Mark, Top/Bottom and its opacity, the Layers tab
  and the filter's Find similar. Their registry entries carry `when: !st.mode3d`.
- **View cube:** a 96 px canvas at the top right of the 3D view, drawn with the same WebGL context's camera
  (a second viewport) or a 2D canvas projection of a labelled cube: Top, Bottom, Front, Back, Left, Right on
  its faces, the eight corners as iso views. A click animates yaw and pitch over 250 ms to the face or
  corner; `camPreset` gains `front`, `back`, `left`, `right`. Labels use Fenolite's stroke font.
- **Lighting:** `ambient 0.30 + key 0.55 × max(N·L1, 0) + fill 0.20 × max(N·L2, 0)` with the key light from
  the camera's upper left and the fill from the opposite side, in both programs; the abs-dot two-sided
  hack goes, back faces are lit by the fill.
- **Bodies without a model:** a body colour token of the 3D palette (dark charcoal sides, a lighter top
  face, the pin-1 corner marked when the footprint has pad 1), Fenolite's own values. Bodies with a model
  keep the model's colours.
- **3D panel:** toggles for bodies, board, silkscreen and copper textures; Reset view.

### 7. Tests

- `tests/unit/view/test_page.py` (on the assembled `template()`): `layerList` and `dock` exist; the model
  builder of `inspect/model.ts`, cut out of the bundle between Node-test markers as `test_filter.py` cuts the
  query functions, turns an authored hit into a model with copy controls and leaves out missing values; the 3D shaders compile is left to
  Chromium.
- `tests/visual/test_inspector.py` (new): a pad of `R1` shows Pad and Part sections with its size in mm,
  then mil after `Q`; Copy copies the size (clipboard permission granted to the context); Zoom to frames the
  part; Show in schematic on the Altium blink project opens the sheet with the part selected.
- `tests/visual/test_layers.py` (new): every layer row of the Altium board shows its full name at 1440 px
  with no horizontal overflow; visibility and opacity change the drawing; `Shift+S`, `+`, `-` still work;
  sheet tabs still list the sheets.
- `tests/visual/test_3d.py` (new): in 3D the Measure and Layers controls are hidden; a click on the cube's
  Front face sets the front camera; no page error.
- Net emphasis: a pixel test on `two_layer.kicad_pcb` with `GND` selected, a track pixel of `GND` keeps its
  layer colour and a pixel of another net is darker than before the selection; new reference
  `kicad_board_net.png`. The existing references are regenerated with the dock in place.

## Risks / Trade-offs

- **Less canvas width.** The dock takes 320 px; it collapses with `I` and remembers that state, and the
  drawing fits the remaining width.
- **Clipboard on `file://`.** `navigator.clipboard` may be refused on an exported page; the textarea
  fallback covers Chromium and Firefox, and the copy control reports a failure instead of claiming success.
- **Every screenshot reference changes again** after c0243; the two changes' reference updates can be one
  CI round when both land in one batch.

## Open Questions

- Should the dock be on the right (as KiCad's Appearance and Altium's Properties panels are) or should the
  Layers panel live in the left side bar, keeping the right side free?
- Should per-layer opacity be stored in the link for every layer, or only visibility and the current layer
  (as designed)?
- Is a pin-1 marker on extruded bodies welcome, or is a plain body preferred?
