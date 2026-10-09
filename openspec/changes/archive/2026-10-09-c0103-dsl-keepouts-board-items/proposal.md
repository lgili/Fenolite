## Why

The review of 2026-10-05 of the gaps to a complex board found that a script cannot declare a keep-out or rule area, a board text, a drawing or a dimension, nor a rule scoped to an area (BGA neck-down, a high-voltage section); its proposals are milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches"). The model has `Keepout`, `Text` and `Graphic`; on `origin/dev` at `9aba2dff` only the board readers create them. Hand-written area rules escape the copper check.

Probes on `kicad-cli` 10.0.6 and 9.0.9 (2026-10-05, same outcomes; on the branch where this proposal was written, not repeated on `dev`):

- Each keep-out setting gives `items_not_allowed` for tracks, vias, pads and footprints on the area's layers, edge crossings included. Stored fills are not reported; the filler cuts the area out.
- `A.intersectsArea('<name>')` selects items whose copper reaches into a named area, on the area's layers. Names are case-sensitive and take `*`. An unknown name selects nothing, silently.
- KiCad recomputes a dimension's text and position on load.

## What Changes

- **Rule areas.** `design.rule_area(name, outline, *, layers=None, forbid=())`, `forbid` taking `tracks`, `vias`, `pads`, `pours`. `Keepout` gains `name`. This is the one call of the DSL for rule areas and keep-outs: c0096's `keepout()` gives way to it (design, "Relation to c0096").
- **Area selector.** `select.area(name)`, written as `A.intersectsArea('<name>')` and lifted back. An unknown area stops the build (`build.area-unknown`).
- **Drawings.** `design.text`, `line`, `rect`, `circle`, `arc`, `polygon`, `dimension`, each with a key. `Text` gains a justification; the model gains `Dimension`, read and written.
- **Copper check.** Area rules are applied from the geometry; copper in a keep-out gives `copper.keepout`, which stops `build`'s copper guard.
- **Rebuilds.** Script items are regenerated, as script copper is.
- **Altium.** Rule areas with a restriction, centred texts and graphics of a script reach the PCB document through the records of c0085. What the document has no record for is reported item by item: an area's name, an area that forbids nothing, a justified text, a dimension. A rule with an `area` selector is not lowered (`scope-unsupported`).

**Limits.** Texts (one line each) and drawings go on silkscreen, mask, fabrication and user layers only. Rule areas are polygons on copper layers, with plain names; the copper check skips an area whose outline it cannot read. Intersection is the only area selector. Dimensions are linear, in mm or inches, 0 to 4 decimals. A KiCad edit of a script item is undone, with an info.

Size: 7.25 design-days; about 5.5 after the design's cuts.

## Prerequisites

- Release 0.3.0 is out, with c0084, c0085, c0088 and c0126 archived: the Altium requirement of this change is worded on c0084's rule lowering ("Scoped rule records", "Rules in an Altium build"), on c0085's records and accounting, and on c0088's copper guard; c0126 puts `Text` inside footprint instances and gives the convention and the 0.2.0 fixture for additive model keys.
- c0100 (the copper layers that `rule_area(layers=None)` takes), c0101 (it modifies "Modelled board content" first) and c0102 (outline and holes; `Edge.Cuts` stays its own) are on `dev`.
- c0096 (implemented on its own branch): by the maintainer's decision of 2026-10-07 `rule_area` stands and c0096 adapts. Either may reach `dev` first; the design says which names of c0096 go and who removes them.
- c0097 (implemented on its own branch): whichever of the two lands second adds the area leaf and `copper.keepout` to c0097's explanation rows and grouping (design, "Relation to c0097"). c0099 is not touched.
- This change lands before c0104 (it shares "Closed selector grammar" and regenerates), c0107, c0113 (`forbid=("footprints",)`), c0117 and c0118.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-dsl`: ADDED "Rule areas in the DSL", "Board drawings in the DSL", "Area selectors in the DSL", "Board items in a build".
- `design-model`: MODIFIED "Identifier derivation"; ADDED "Rule areas, board items and the area selector in the model".
- `kicad-file-backend`: MODIFIED "Modelled board content"; ADDED "Board items of a script are written".
- `rules-model`: MODIFIED "Closed selector grammar".
- `copper-check`: MODIFIED "Clearance in force"; ADDED "Rule areas in the copper check", "Keep-out findings".
- `verification-loop`: ADDED "Keep-out issue code".
- `layout-lens`: ADDED "Board items declared in the script".
- `altium-build`: ADDED "Rule areas, board items and area rules in an Altium build".
- `kicad-oracle`: ADDED "Rule areas and area conditions are probed", "Board texts and dimensions are probed", "Keep-outs and area rules agree with the copper check".

## Non-goals

- Areas forbidding footprints, placement keep-outs, part heights: c0113. Keep-outs sent to routers: c0107. Stitching around rule areas: c0074.
- Text or drawings on copper: nowhere, because the copper check cannot see glyphs (KiCad flags a copper text across a track, not a copper line).
- `enclosedByArea`; area selectors on creepage, courtyard and silkscreen rules; component-class selectors: nowhere, reasons in the design.
- Placement rule areas: roadmap v0.5b. Text boxes, tables, other dimension kinds: c0117 if its drawings need them.
- A dimension record, a name key of a keep-out, a justification key of a text and an area scope of a rule in the Altium document: nowhere for now. None has a fact row in `docs/formats/altium/`; each item is reported instead.

## Evidence level required

- New rows `H-K-AREA-KEEPOUT`, `H-K-AREA-COND`, `H-K-AREA-NAME`, `H-K-BOARD-TEXT`, `H-K-DIM`, `H-K-COPPER-AREA`, settled on 9.0.9 and 10.0.6 before merge; `SELECTOR_SUPPORT["area"]` holds probed majors only.
- DSL calls, uuids, rebuilds: unit scenarios. The Altium part is mechanical on the records of c0084 and c0085; the evidence of the Altium build does not rise.

## Impact

- Changed: `model/`, `backends/kicad/{pcb,rulemap}.py`, `checks/`, `dsl/`, `lens/` (the Altium accounting among it), `cli/data/explain.toml`, schemas, docs. New: `backends/kicad/boarditems.py`, `dsl/items.py`.
- `check` and `build`'s copper guard may report `copper.keepout` where KiCad alone reported `items_not_allowed`. The check is neutral, so `fenolite check` of an Altium board with keep-outs may report it too; the copper guard of an Altium build reports it as a warning and does not stop (c0088's rule for every copper error but a short).
- New model keys: `name` of a keep-out, `h_justify` and `v_justify` of a board text, `dimensions` of a board, and the selector op `area`. Documents written before load unchanged; release 0.2.x cannot read a document that carries one of them.
- If c0096 is on `dev` first, its `Design.keepout(key, …)`, `Design.keepouts` and the key `keepout:<key>` are removed by this change (an API that no release carries).
