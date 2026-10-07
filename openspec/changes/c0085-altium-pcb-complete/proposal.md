## Why

The experimental PCB document holds the outline, a stack of two or four copper layers, components, pads, footprint graphics, designators, tracks, arcs, through vias, unpoured polygons, net classes and rules. A board of the yardstick the maintainer uses for a complex design needs more, and each missing item is silently absent today or reported once as `altium.not-lowered`: six or more copper layers and a real stack-up, blind and buried vias, board texts and graphics, keep-outs, non-plated holes and slots, footprint texts and bodies with their heights.

The readers of c0041 and the import of c0043 already carry all of these from Altium into the model, so the model can hold them; only the writer is behind. Without them, an imported board cannot be written back (c0090), and a built board is not a board a fabricator's review would accept.

## What Changes

- **Stack.** Any even number of copper layers from 2 to 16 with the dielectrics, thicknesses and materials of the model's stack-up; signal and plane layers; the layer map extended to match.
- **Vias.** Blind and buried vias with their layer pairs, and the drill pairs the document needs for them; micro vias stay refused with a reason.
- **Board items.** Texts on any layer (with the string forms the reader knows), graphics (lines, arcs, fills, regions) on non-copper layers, keep-outs (regions with their restrictions), non-plated holes and slots.
- **Footprint extras.** Footprint texts besides the designator and comment, and component bodies with standoff and overall height (no 3D model file is embedded). *Corrected on 2026-10-06: neither is written; bodies were cut by the cut order and are reported one by one, and footprint texts have no requirement in this change (design, "Found on 2026-10-06").*
- **Polygons.** Written unpoured, with every pour property of the zone; the build says that the board must be repoured in Altium. Fenolite never writes poured copper it did not compute for Altium's rules.
- **Closed accounting.** `result.pcb.written` and `result.pcb.not_lowered` count every model item by kind, so nothing is absent without a line.

Size: 10 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-pcb-writer`: ADDED "Layer stacks of any even count", "Blind and buried via records", "Board text records", "Board graphics and keep-out records", "Non-plated holes and slots", "Component bodies are reported", "Unpoured polygons are a contract", "Written items are accounted"; MODIFIED "Four-layer stack", "Via records", "Polygon pour records" and "Copper layer map", whose limits these supersede.
- `altium-build`: ADDED "Complete board in an Altium build"; MODIFIED "Copper issue codes" ("PCB issue codes" names no code of an item that is now written and is not changed).

## Non-goals

- No poured polygon copper, no teardrops, no split planes drawn as plane splits (a plane layer carries one net, or the layer is a signal layer with polygons).
- No embedded 3D model files (STEP) and no embedded fonts; a body is its outline and heights.
- No dimensions, no drill tables, no layer-stack table objects (Draftsman and documentation objects).
- No rigid-flex stacks, no back-drilling, no micro vias.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- Own readback of every new record kind against the model: `INFERRED` under `H-A-PCBX-READBACK`.
- KiCad's importer on the written document, for the kinds it reads: `ORACLE-VERIFIED(kicad-cli 10.0.x)` for those kinds only, as c0038 did for copper.
- That Altium opens the document without a repair prompt and shows each item: `INFERRED` until Part X is reported; then `ALTIUM-VERIFIED(author-report; …)`. The kit of c0091 repeats it.

## Decision of the maintainer (2026-10-06): unpoured, as written below

- **Question.** Polygons: written unpoured with a repour step in Altium, or written with Fenolite's own fills?
- **Default written here.** Unpoured, always; the build reports `altium.zones-unpoured` and the kit has a "Repour all" step.
- **Alternative.** Write the fills that Fenolite computes (c0015/c0029 geometry) as poured regions.
- **To switch.** Replace the requirement "Unpoured polygons are a contract" by one that writes the model's fills as region records, add a task for the region writer and a Part X step that compares Altium's repour with the written fill; no other requirement changes.

## Impact

- Changed: `backends/altium/{pcbrecords,pcbdoc,docboard,layout}.py`, `lens/altium_copper.py`, `lens/altium.py`; `claims.py` notes.
- Pages: `docs/altium.md` ("PCB document"), `docs/formats/altium/{pcb-document,pcb-copper,pcb-bodies,pcb-records}.md`, `docs/evidence/altium-pcb.md`.
- Issue codes: `altium.via-unsupported` narrows to micro vias; `altium.not-lowered` for board items becomes per kind.
- Depends on: c0035, c0038, c0053 (PCB writers); c0041 and c0043 (the readers that prove readback); nothing else of the write part of v0.3.
