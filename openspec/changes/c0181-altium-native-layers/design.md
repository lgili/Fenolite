## Context

- **Request.** P0-1 of the analysis of 2026-10-25: "o usuário de Altium nota na hora".
- **What exists.**
  - `read.pcbstack.read_board` gives the numbered layers with their names (`LAYER<i>NAME`) and Altium's default
    names (`_layer_names`).
  - `pcbrecords.LAYER_MAP` maps model names to Altium layer ids (`F.SilkS` to 33, `F.Mask` to 37 …).
  - The pad record holds the paste and solder-mask expansions at offsets 86 and 90 and their modes at 101 and
    102 (`pcb-records.md`, "Pad", `INFERRED`); `read.pcb` does not type them.
  - `read.rules` reads `Rules6`; `read.scope` evaluates a subset of rule scopes.
  - The scene (c0176) derives mask and paste openings from the pads when the model has no mask layer.

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. **Labels, not ids.** A scene layer keeps `id` (the model name) and gains `name`, the native name.
   `view/altium_layers.py` gives `layer_labels(pcbdoc) -> dict[str, str]` and `layer_order(...)`. The scene
   builder takes an optional mapping; the KiCad path passes none.
2. **Names.** A numbered layer's `LAYER<i>NAME`, when present and not empty, wins over the default name; a
   mechanical layer that is not enabled keeps its default name and is still drawn if it holds primitives.
3. **Openings.** For each pad: the opening is the copper shape grown by the expansion (a negative expansion
   shrinks it, never below zero). Mode 0 is an expansion of 0 (source `none`); mode 2 the pad
   value; mode 1 the first rule by priority whose scope `read.scope` evaluates for that pad and that matches it
   (a scope with a net class, a layer or an unparsed query is skipped and counted), else Fenolite's default of
   4 mil for mask and 0 for paste (named in a note). The import already keeps the mode and value of every pad
   whose mode is not 1 in the pad's `ext` (`mask`, `paste`), so only `Board6/Data` and `Rules6/Data` are read
   again. A through-hole pad opens the mask on both sides, a surface pad on its side.
4. **Properties.** Rows "Solder mask expansion", "Paste expansion", "Source" and "Opening".
5. **Copper edge.** A filled pad drawn as a ring with an edge stroke opens its mask by the stroke too (the
   openings of c0176 left the half stroke out).

## Risks / Trade-offs

- **Rule scopes.** A board whose mask rules use queries outside `read.scope` gets the `All` rule for those
  pads; the note counts them so the reviewer knows.

## Authored comparison preparation, 2026-11-03

The maintainer selected Fenolite-authored inputs for the pending comparison, without approving any rendering. Preparation is external and source-bound: no CAD UI or configuration change, no fabricated native image/version, no human-review completion. Native Designer24.5.2.23, an actual KiCad-written authored theme and DraftsmanF0.5 observations remain separately measured where applicable. See docs/evidence/native-viewer-maintainer-review-plan.md for the required criteria.

## Configurable layer order — approved decision, 2026-11-03

The maintainer's explicit choice supersedes the original universal order claim. Keep the existing
scene ranking as **Default viewer order**, without calling it Altium's default. The Layers panel gets
an **Order layers** native modal dialog with a selected layer, Move up/down buttons, Alt+Up/Down,
Apply, Cancel/Escape and Reset to default. Changes remain a draft until Apply. Reset changes the draft;
Cancel discards it. Return focus to the opener. Disable moves at the ends and announce moves accessibly.

Store only stable layer IDs, using the existing browser localStorage convention, under a key scoped to
project/document identity and the scene's source SHA-256. Invalid stored values cannot add, duplicate or
remove scene layers. Missing IDs are ignored and new available IDs follow in their default order.
Another document/hash cannot inherit the preference. Storage failures keep the applied choice in this
page session; an identity without a trustworthy hash stays session-only. Reset removes the preference.

The default grouped list remains unchanged. A custom order uses one global list in exactly the chosen
order, with the original group-visibility controls retained separately. Keyboard layer stepping uses the
same chosen order. Reordering never mutates the original scene layer array/tab values, vis, current
layer, single-layer state, part/net selections, geometry, source bytes, or the canvas draw order.

Prove the actual 14-layer v6 input separately from an authored 17-layer interaction fixture. A fixture
with 17 layers is not evidence that v6 contains 17 available layers. Native comparison task 3.3 and
release/integration gates remain open; no evidence label or prior approval is rewritten.
