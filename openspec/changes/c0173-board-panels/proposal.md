## Why

The maintainer's request of 2026-10-16: several copies of one board in one panel (2 × 2 = 4, 2 × 4 = 8, or as many as a panel size holds), for Altium as the native Embedded Board Array, with V-score, tabs with mouse bites, and a frame with rails, fiducials and tooling holes, in release 0.5.0. Change c0118 left panels out of v0.4 ("the board's fiducials and tooling holes are its own, not a panel's") and measured that `kicad-cli` has no panel command; nothing in Fenolite makes a panel today.

What is public (design, "Context"): Altium's pages name every property of the Embedded Board Array (referenced PCB document, row and column counts, spacing as pitch, margins, rotation, mirror, origin link), say that tabs are a route tool path on a mechanical layer of type Route Tool Path, that mouse bites are small unplated pads, and that a mechanical layer can be of type V Cut. No public page gives the array's records: KiCad's importer lists the storage `EmbeddedBoards6` as "not imported". Fabricators publish V-score, mouse-bite, rail and fiducial rules, and they differ.

## What Changes

- **A panel script.** `fenolite.dsl.panel.Panel(name, board=…)` binds `panel` in a script of its own that names a built board: `grid(rows, cols, …)` or `fit(width, height, …)`, gaps, a quarter-turn rotation, `rails(…)`, `separate("vscore" | "tabs", between=…)` per edge set, `tabs(…)` with mouse bites, `vscore(…)`, `fiducial(…)`/`fiducials(…)`, `tooling_hole(…)`/`tooling_holes(…)`. Integer nanometres and microdegrees.
- **A panel model.** `model.panel.Panel` (canonical JSON, schema `panel.json`) and `panel.layout(panel, board) -> PanelLayout`: copies, frame, gaps, tabs, holes, score lines, fiducials and tooling holes, each with an id derived from its key.
- **`fenolite panel PANEL.py --out DIR --target {9,10,altium}`**, a writing command with `--dry-run` and `--confirm --plan`, and the panel checks (`panel.*`: copper near a V-score or a tab, gap, shape, thickness, tab spacing, fiducial and tooling places, panel size).
- **KiCad:** a flattened panel board `<panel>.kicad_pcb` with its project, verified by `kicad-cli` 9.0.9 and 10.0.6 (load, DRC, drill, Gerber).
- **Altium:** a panel document `<panel>.PcbDoc` in its own project, the board placed as an Embedded Board Array behind the gate `pcbdoc.EMBEDDED_ARRAYS` once Part Q has measured the records and shown the written file; until then (and for ever, if the stop rules fire) a flattened panel document, which the existing writer can produce.
- **Exports:** `fenolite export` of a panel board includes its V-score layer among the Gerber layers.
- **Evidence:** thirteen sources registered (S-0790 to S-0802; S-0002 and S-0125 read again), fact rows on three format pages, nine hypotheses, Part Q of the Altium evidence page.

Size: 13 design-days, cut order in the design. Release 0.5.0 by the maintainer's decision; what waits on his Altium run is deferred and claims nothing.

## Capabilities

### New Capabilities
- `board-panels`: the panel layout, the separations, the panel checks and their limits, the panel evidence.

### Modified Capabilities
- `design-model`: ADDED "Panels in the model".
- `design-dsl`: ADDED "Panel scripts", "Panel fit rule".
- `kicad-file-backend`: ADDED "Panel boards written".
- `altium-pcb-writer`: ADDED "Embedded board array records", "Flattened panel documents".
- `altium-build`: ADDED "Panel project of an Altium board".
- `altium-verification`: ADDED "Kit cases for panels".
- `manufacturing-exports`: MODIFIED "Export kinds and their arguments".
- `cli-contract`: ADDED "Panel command".

## Non-goals

- Several different boards in one panel, nested arrays, arbitrary angles, jump scoring, and a mirrored KiCad copy (Altium's Mirrored stays a property of the array).
- Running or importing any panelisation tool; KiKit (S-0802) is prior art only.
- Vendor-named presets, and editing a Gerber file that `kicad-cli` wrote.
- `ALTIUM-VERIFIED(kit)` for anything Part Q has not run.

## Evidence level required

- KiCad panel board: `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-PANEL-LOAD`, `-DRILL`, `-NETS`; `-GERBER` records the file function).
- Flattened Altium panel: `ORACLE-VERIFIED(kicad-cli)` (10.0.6, `H-A-PANEL-FLAT`).
- Embedded Board Array written by default: `ALTIUM-VERIFIED(kit)` of Q7 to Q9 (`H-A-PANEL-KIT`); until then the gate is off.

## Impact

- New: `src/fenolite/model/panel.py`, `src/fenolite/panel/` (layout, checks, limits, KiCad and Altium lowering), `src/fenolite/dsl/panel.py`, `src/fenolite/cli/cmd_panel.py`, `schemas/fenolite.model.v0/panel.json`, `schemas/fenolite.panel.v0.json`; `backends/altium/pcbrecords.py`, `pcbdoc.py` (array records behind the gate); `exports/plan.py` (`gerber_layers`).
- Docs: `docs/panels.md`, `docs/dsl.md`, `docs/cli-contract.md`, `docs/altium.md`, `docs/evidence/altium-pcb.md` (Part Q), agent guide page `fabrication`.
- Depends on c0167 (inner rings, `merge_rings`, the `geo` extra) and c0118 (generated fiducial and tooling-hole footprints). It does not depend on c0168: the Altium panel needs no board cut-out region.
