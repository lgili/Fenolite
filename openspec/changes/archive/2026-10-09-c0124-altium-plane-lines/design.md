## Context

- **Today.** `adapter/layers.LayerMap` names the copper layers by their position in the chain of the board record, so an internal plane (Altium id 39 to 54) is `In<j>.Cu` like a mid layer. `adapter/copper.tracks` and `arcs` make a `Track` or an `Arc` of every free primitive on a copper layer of the chain; `shapes` makes a filled `Graphic` of a free fill or region there and counts it in `altium.import.copper-shape`; `texts` makes a `Text`.
- **What a plane is in the imported model today.** A `Layer` of kind `copper` in the chain, with `plane_net` in its `altium` bag when `PLANE<n>NETNAME` names a net, and a copper `StackLayer`. Nothing else: no zone, no fill, no keep-out (living requirement "Layers and stack-up": "No zone MUST be synthesised for a plane"). The split-plane polygons of the document are counted as `polygons`, and the primitives that carry the split-plane polygon index (the pull-back) as `pour-primitives`. This change keeps all of that.
- **What c0088 did.** `backend.rules_from_bytes` gave the copper check a design without the tracks and arcs that have no net and lie on a layer whose bag holds `plane_net` (`_without_plane_lines`), and named the planes in `DesignRules.left_out`. The import, its ids and its round trips were left alone; c0088's design lists the move into the adapter as an open question.
- **The model** (`model/board.py`) has `Track`, `Arc`, `Via`, `Zone` (positive, with fills), `Keepout`, `Graphic` and `Text`. It has no negative copper.
- **Constraints.** No change of the model, no KiCad output of 0.2.0 changes, committed Altium samples keep their bytes.

## Measured before the proposal (2026-10-06, local corpus cache, the eight public PCB documents)

Counts only. Primitives on the layers 39 to 54, by owner and net:

| document | plane layers of the chain | free, no net | free, with a net | of a component | with the split-plane polygon index | split-plane polygons |
|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | 2 | 74 tracks | 0 | 0 | 24 tracks, 16 arcs | 8 |
| `altium-third-party-pcbdoc-02` | 2 | 43 tracks | 0 | 0 | 18 tracks, 16 arcs | 5 |
| `-03` to `-08` | 0 | 0 | 0 | 0 | 0 | 0 |

- No document holds a free arc, fill, region or text on a plane layer, and none holds a primitive with a net there. No document holds a primitive on a plane id outside its chain.
- **What the import makes of them today:** the 74 and the 43 free tracks are `Track` entities without a net on `In1.Cu` and `In2.Cu` (9 and 65 on the first document, 43 on `In2.Cu` of the second). The primitives with the split-plane index and the split-plane polygons give no entity (`pour-primitives`, `polygons`).
- **What KiCad's import makes of them** (`kicad-cli` 10.0.6, `pcb import --format altium`, read by Fenolite's KiCad reader): no track. Its boards hold 1 346 and 191 tracks where Fenolite's read holds 1 420 and 234: exactly 74 and 43 fewer. On the plane layers KiCad's boards hold rule areas (136 and 93) and one unfilled zone per split plane (8 and 5), and no track, arc or graphic.

## Measured after (2026-10-06, the same documents; `kicad-cli` 10.0.6 on macOS for the oracle rows)

| | `-01` before | `-01` after | `-02` before | `-02` after |
|---|---|---|---|---|
| tracks of the import | 1 420 | 1 346 | 234 | 191 |
| tracks of KiCad's import | 1 346 | 1 346 | 191 | 191 |
| tracks and arcs on a plane layer, the import | 74 | 0 | 43 | 0 |
| `plane-cuts` of `altium.import.unmapped` | — | 74 | — | 43 |
| `plane_cuts` per plane layer | — | 9, 65 | — | 0 (no pair), 43 |
| copper on no net at level 5 (Fenolite, KiCad) | 74, 0 | 0, 0 | 43, 1 | 0, 1 |
| level 5: differences, `route-unjudged` notices, pieces | 0, 8, 419 and 419 | the same | 0, 4, 44 and 44 | the same |
| copper check: tracks judged, pairs judged, shorts, clearance | 1 346, 10 482, 0, 2 | the same | 191, 553, 0, 0 | the same |
| copper check: `planes`, level | 2, `UNVERIFIED` | the same | 2, `UNVERIFIED` | the same |
| RT-A3: verdict, tracks written | equal, 1 420 | equal, 1 346 | equal, 191 | equal, 191 |
| RT-A3: `track` not written | 0 | 0 | 43 | 0 |

- **Ids.** Over the eight public documents every id of a track, arc, via, zone, graphic, text, footprint, pad, layer and net that the import still holds is the id it had, in the same order; the 74 and the 43 ids of the cut lines are gone and no id is new. The issue codes of each import are the same; the message of `altium.import.unmapped` gains `plane-cuts`. The six documents without a plane layer are unchanged in every count.
- **The copper check** reports what it reported with c0088's filter: the 71 shorts and 48 clearance findings stay gone, now because the import holds no such track. The corpus test asserts that the board that is checked holds every track and arc of the board that was read.
- **RT-A3.** On `-01` the planes are written as signal layers (`plane 2`), so before this change a rewrite held the 74 cut lines as copper tracks; it no longer does. On `-02` the writer refused the 43 lines (`track 43`); nothing is left to refuse. RT-A0 and RT-A1 are record-level and did not move; the five project sets keep their verdicts.
- **Level 5 against KiCad's import.** The two reads converge: the same number of tracks, none on a plane layer. No level-5 difference appears, no rule of the profile is added and no probe outcome moves, so nothing is recorded with the probe mechanism. `tests/kicad/altium/test_import_oracle.py` counts the import's tracks without a net, which it does not compare: 123 on three rows before, 6 on one row after.
- **Committed samples and own files.** No file under `tests/data/altium/` changes: a document that Fenolite writes holds no primitive on a plane layer (`tests/_altium_pcb_read.py` refuses one).

## Found on 2026-10-06

1. **KiCad's import makes no track of a line on a plane.** It was not known before the measurement whether the triangle would converge or split. It converges; KiCad represents the cuts as rule areas, which level 5 does not compare.
2. **c0088's filter knew a plane by `plane_net`.** A plane on no net was no plane for it. The import and the view now ask for the layer id. No public document has such a plane, so no measured number moved by this.
3. **c0088's filter kept a line with a net.** The import leaves it out (decision 5). No public document has one.
4. **"Differences from KiCad's importer"** of `docs/formats/altium/import.md` counted 123 tracks without a net on three rows as kept by the import; 117 of them were the plane lines. The row is corrected.
5. **Outside this change:** the parity row of `altium-set:02` on `docs/evidence/altium-roundtrip.md` ("Light DRC over the corpus": 26 net conflicts, 189 pads that differ in the net name alone) is not what the base commit `ba21a109` measures (21 and 129, the same with and without this change). Parity reads no track, so this change does not move it and does not edit the row; it is reported to the maintainer.

## Goals / Non-Goals

**Goals:**
- No reader of an imported board sees copper where a plane was cut: the copper check without a filter, level 5, a rewrite, an export.
- The records that are left out are counted, per document and per plane layer.
- The items that stay keep their ids.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Not lowered, counted (choice a), not a graphic (choice b).** The two honest choices were: (a) no entity, counted by an import issue and kept in a bag; (b) a `Graphic` on the plane's layer. A graphic on a copper layer is not read as copper by Fenolite's own checks (`checks/copper.py` and level 5 read no graphic), but it is copper for the next consumer: the KiCad writer writes it as a drawing on `In<j>.Cu`, which KiCad fabricates and checks as copper without a net, and `lower._items` counts it as a `copper-shape` that was lost. A cut drawn as a graphic would still say "copper here" to everything outside Fenolite, which is the fault this change removes. So (a).
2. **Where nothing is lost.** The model is a projection of the records ("Extension bags": "a record or a key the adapter does not map stays in the reader's document and is counted"). The census counts each record under its kind with the new category `plane-cuts`, so `altium.import.unmapped` names the number and the census still adds up. The layer of the plane holds the number in its bag (`plane_cuts`), so a reader of the model alone (the copper view) knows that the document cut the plane and how often. The geometry is not copied into a bag: a bag holds short texts of a record, the lines are 74 on one board, and RT-A0 and RT-A1 work on the records, which keep every value.
3. **No new issue code.** `altium.import.unmapped` is the import's counting issue. A code of its own would be a third open delta of "Import issue codes" (c0083 and c0122 each hold one that is not archived). The count is in the message either way.
4. **A plane is a layer id, not a net name.** A layer of the chain with an id from 39 to 54 is an internal plane (`docs/formats/altium/pcb-records.md`, "Layers"). c0088's view asked for `plane_net`, which a plane on no net does not have; such a plane is copper in negative too. `LayerMap.is_plane` is the one test; the copper view reads the bag's `layer_id`.
5. **With or without a net.** Altium's documentation says that an object on a plane layer is a void, and that a line that splits a plane is set to no net (S-0531); the page on layer queries says it of any object on those layers (S-0550). No public document holds one with a net. A primitive with a net on a plane layer is left out like the others: the net index cannot make copper of a void. c0088's view kept such a track; this is a correction, and it moves nothing that was measured.
6. **Every free kind, not lines alone.** Tracks and arcs were the request. A free fill, a free region and a free text on a plane layer are voids by the same fact; today they would be a filled graphic counted as "copper shape" and a text on copper. They are five lines of adapter code and one authored test each, and leaving them would keep the fault for the documents that have them. Pads and vias are not touched: a via spans layers, a pad is a footprint's, and no public document holds a pad on a plane layer.
7. **What is checked first.** Component index, then polygon index, then the plane: a primitive of a component or of a polygon keeps its old category, so the counts `footprint-graphics` and `pour-primitives` do not move. The plane is asked before the width and the radius: a cut needs neither, so no `altium.import.bad-geometry` is given for it.
8. **Ids.** `adapter/ids.Ids` gives an imported track or arc a content id: the hash of its model fields plus the number of earlier entities of the same content in the same section. No id holds a record index. A track that stays cannot have the content of one that is left out (the layer is part of the content, and every free track of a plane layer is left out), so no counter of a kept entity moves and every kept id is the one it was. Provenance locators hold the record index (`Tracks6/Data#<i>`), which is the position in the stream, not in the list of tracks, so they do not move either. Task 2.3 compares the ids of the eight public documents before and after.
9. **The copper view.** `_without_plane_lines` and `PLANE_KEY` are removed: nothing is left to take out. `DesignRules.left_out` stays (a field of the protocol; `checks.copper.rules_issues` reads it), and the Altium rules source still fills one entry `plane`: the count is the number of plane layers, as c0088 specifies, and the reason holds the sum of the layers' `plane_cuts`. So `copper.item-unsupported` (`where` = `plane`) and the level `UNVERIFIED` are given exactly where they were. c0091's kit asserts that a repoured sample gives no `copper.item-unsupported` (`cli/_kit.py`); its samples hold no plane layer, so it gets none, as before.
10. **`backend-protocol`, "Design rules source", is not modified.** Its sentence "`DesignRules.design` is then without the items that stand for it" still holds: after this change no item of an imported board stands for a plane.
11. **Cut order.** First decision 6 (back to tracks and arcs alone), then the assertion on KiCad's import; never the id comparison and the copper-check measurement.

## What a plane would need to be copper in the model (not done)

KiCad's importer shows one way: a zone per plane (or per split plane) on the plane's net, and a rule area for each object that cuts it. Fenolite's model has both entities (`Zone`, `Keepout`). It would give the copper check something to judge and level 5 a fill to follow, but it needs the plane's outline (the board shape minus the pull-back), the split-plane polygons with their nets, a pour to get fills, and a decision on what the Altium writer makes of such a zone. That is a change of its own; "Layers and stack-up" keeps "No zone MUST be synthesised for a plane".

## Files and public API

- `src/fenolite/backends/altium/adapter/layers.py`: `LayerMap.is_plane(layer_id) -> bool`, `LayerMap.cut(layer_id)`, the pair `plane_cuts` in `entities`.
- `src/fenolite/backends/altium/adapter/copper.py`: `tracks`, `arcs`, `shapes` and `texts` leave the free primitives of a plane layer out and count them.
- `src/fenolite/backends/altium/adapter/ids.py`: `plane_cuts` in `EXT_KEYS`, after `plane_net`.
- `src/fenolite/backends/altium/backend.py`: `_without_plane_lines` and `PLANE_KEY` removed; `_planes_left_out(design)` builds the entry of `left_out`.
- `src/fenolite/backends/altium/import_evidence.py`: the row `H-A-IMP-PLANE-CUT`.
- No signature of a public function changes.

## Sources registered by this change

- S-0550: Altium's documentation page on the layer query functions (`OnPlane`), read for one fact on 2026-10-06: the presence of any object on an internal plane layer is an absence of copper, and the plane layers are Internal Plane 1 to 16. Nothing is transcribed.
- S-0531 (registered by c0088) is read again for the same page's facts on the lines that split a plane: they are placed on the plane layer and set to no net, and the pull-back tracks are made by the tool.
- S-0020 (`kicad-cli`) on the public documents of S-0188 and S-0176 for what KiCad's import holds on the plane layers.
- S-0551 to S-0554 of this change's block are not used.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-IMP-PLANE-CUT | A free primitive on the layer of an internal plane (Altium id 39 to 54) is a void of the plane and no copper: KiCad's import of a document makes no track of it | `tests/kicad/equivalence/test_triangle_level5.py -k plane` on the public documents with planes | Fenolite's read and KiCad's import hold the same number of tracks on each such row, and neither holds a track or an arc on a plane layer |

It starts `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Size (design-days)

| group | dd |
|---|---|
| entry, measurement and registers | 0.25 |
| import and its tests | 0.5 |
| copper view | 0.25 |
| measurements and pages | 0.25 |

Total: 1.25. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-import`: "Layers and stack-up", "Tracks, arcs and vias", "Outline, graphics and texts" and "Unmapped records are counted" are MODIFIED from the living text of `openspec/specs/altium-import/spec.md` (no active change holds a delta for any of the four on the base commit; checked 2026-10-06). "Objects on an internal plane" is ADDED. The sibling change c0127 (arcs keep their record values) may hold a delta for "Tracks, arcs and vias": the two edits touch different bullets and are merged by hand when the second of the two is archived.
- `altium-verification`: "Clearance rules of a PCB document" is MODIFIED from the text of c0088's delta (`openspec/changes/c0088-altium-light-drc/specs/altium-verification/spec.md`), which ADDS it and is not archived.
- The deltas are written by a script that asserts each sentence it replaces.
- Archive order: after c0088. After c0090 and c0089 too, whose pages and pinned corpus tests this change edits.

## Risks / Trade-offs

- [A board whose designer drew real routing on a plane layer] → Altium has no such thing: the layer is negative for every object. The count is in the import's issue and in the layer's bag.
- [The content of an imported board with planes changes] → the changelog says so in bold; boards without planes and every committed sample are unchanged.
- [A saved model of an earlier import still holds the tracks] → it is read as it was written; the copper view no longer filters it, so the copper check reports those tracks. An import is repeated, not migrated.
- [`plane_cuts` is one more key of a closed table] → one row of `docs/formats/altium/import.md`; the writer reads `plane_net` only and ignores it.

## Migration Plan

- None for callers. An import of a document with internal planes gives fewer tracks than 0.2.0 did.
- Rollback: the four `is_plane` branches of `adapter/copper.py` and the filter of the view.

## Open Questions

- **Should a plane become a zone with rule areas for its cuts, as in KiCad's import?** Not decided here; "What a plane would need" above lists the work.
