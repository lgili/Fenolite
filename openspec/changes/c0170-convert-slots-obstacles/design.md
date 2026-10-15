## Context

- **Request.** Part F of the maintainer's request "board slots and cut-outs, end to end" (2026-10-15): `convert kicad → altium` carries slots and cut-outs and reports what it drops; routing obstacles as a follow-up. Depends on c0167 (`edge_outline`, `outline_items`, `merge_rings`), c0168 (slot pad fields, cut-out regions and their gate, imported `Hole`s with `to_kicad.hole_footprints`), c0169 (`BoardFrame.board_edges`), and c0159 to c0161 (the conversion), which are open on `dev` at `a87723c` with 2, 20 and 18 tasks open.
- **What exists** (`origin/dev` at `a87723c`, read on 2026-10-15).
  - KiCad to Altium. `convert/to_altium.py:80-108` calls `lower.write_design(…, allow_lossy=True)`. A read KiCad board has `Board.outline = None`, so `lower._outline` takes `_ring_of` of the `Edge.Cuts` graphics (`backends/altium/lower.py:554-593, 611-626`): the first ring, an arc as two straight edges (skip "an arc of the outline is written as two straight edges"), and every edge of another ring skipped ("an edge outside the first ring of the outline"). The report counts them under the kind `outline` of the group `board` (`convert/report.py:66-77`).
  - Slotted drills. `lens.altium.pad_extras` refuses a pad whose padstack holds a slot, "the drill is oval or has an offset" (`lens/altium.py:494-495`), and `pcblib._pad_refusal` refuses a pad with a padstack (`backends/altium/pcblib.py:155-170`); the footprint is then lost. The model holds the slot of a KiCad oval drill (`Padstack.hole_shape`, `hole_length`, `hole_rotation`; `backends/kicad/_fpmap.py:221-265`).
  - Altium to KiCad. `convert/to_kicad.py:72-118` writes the imported model with the KiCad writer. Edge items are graphics and are written as read; no overlap check runs on graphics (`check_outline` reads only `Board.outline`, `backends/kicad/outline.py:442-499`). After c0168 an imported free hole is a `Hole`, which KiCad refuses (`pcb.py:3321`), and c0168's `to_kicad.hole_footprints` gives it back as the old board-only footprint.
  - Generated hole footprints. `dsl/holes.py:67-140` builds `Fenolite_Holes` footprints (`NPTH_3.2mm`, `NPTH_Slot_1x3mm`) with model types only; the KiCad backend may not import `dsl` (`tests/unit/test_import_graph.py:37-38`).
  - Routing. `cli/cmd_route.py:409-433` passes `board_outline(design).rings` to the router; the Specctra writer puts ring 0 as the boundary and every other ring as a `keepout` polygon (`backends/specctra/dsn.py:803-822`). After c0167, `board_outline` gives slots as rings, so they become keep-outs with no code change.
  - Placement. `placement/constrained_legality.py:98-124` and `placement/preview.py:67` read `Outline.points` and `Outline.cutouts` directly; `analysis/body_volumes.py:198-220` too. They miss slots after c0167.
  - Equivalence. `checks/equivalence/` compares no outline; `docs/altium.md:1495` lists the outline as "not compared" by RT-A2 (c0168 adds holes and cut-outs there).

## Goals / Non-Goals

**Goals**
- Every slot and cut-out of a converted board is kept, changed (merged, polygonised) or lost, and counted so.
- A KiCad board's oval drills survive a conversion to Altium.
- Slots stop placement and routing.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **KiCad to Altium takes the edges as an outline.** `lower._outline` takes `edge_outline(design)` when `Board.outline` is `None`: ring 0 as today (arcs as two straight edges, reported), every inner ring through c0168's lowering, merged with `merge_rings` where rings overlap. Each inner ring is counted under the new kind `cutout`: `kept` when written as a region, `changed` with the reason "merged" or "arcs polygonised", `lost` with c0168's gate reason while the gate is off. `_ring_of` stays for an outline that `edge_outline` cannot close (its skips unchanged).
   - Rejected: recognising stadiums (`slots_of`) and writing them as slot pads: a milled slot is a cut-out (c0168, Decision 1).

2. **Slotted drills of footprint pads.** `pad_extras` no longer refuses a slot whose drill has no offset; `pcblib` writes a pad whose padstack has only `hole_shape` `slot` (no per-layer shapes) with c0168's fields: hole size the drill, slot length `hole_length`, slot rotation `hole_rotation` relative to the pad. An offset drill and a per-layer padstack stay refused, as c0160 decides.

3. **Altium to KiCad merges and generates.**
   - `to_kicad` takes `edge_outline` of the imported board, merges overlapping inner rings, and writes them as the model outline of the board (its edge graphics replaced): `changed`, reason "merged". Without the `geo` extra the overlap is a `cutout` loss of class `refuse` (exit 7 without `--allow-lossy`), because KiCad would call the board malformed.
   - A `Hole` becomes a board-only footprint from the moved builder `model.holes.hole_footprint(drill, length=…)`, placed at the hole, turned by its rotation, `NPTH_…` of the library `Fenolite_Holes` written beside the board as `design.hole` writes it; it replaces c0168's `hole_footprints`. A plated hole is reported `changed` (a pad without net).
   - `dsl/holes.py` keeps its names and imports the builder from `model/holes.py`, so scripts and their bytes are unchanged.

4. **Edge rings verified.** After a conversion, the edge rings of the source and of the written project read back (`BoardFrame.board_edges`, c0169) are compared as sets: each ring matched within 1 µm plus the region chord, a merged ring matched to the union of its sources. An unmatched ring that the report does not explain is a difference of the verification (exit 5), as c0159's "Differences matched to the report" says for other kinds.

5. **Obstacles.** `constrained_legality`, `preview` and `body_volumes` take `outline_items` of the model outline (slots as rings). Specctra needs no code: a test asserts one `keepout` per slot ring and that a Freerouting run on the fixture with a net on either side of `S1` routes around it.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/altium/lower.py` | `_outline` through `edge_outline`; the kind `cutout` |
| `src/fenolite/lens/altium.py`, `backends/altium/pcblib.py` | slotted drills written |
| `src/fenolite/convert/report.py`, `to_altium.py`, `to_kicad.py` | `cutout`; merge; generated hole footprints; ring verification |
| `src/fenolite/model/holes.py` (moved), `dsl/holes.py` | `hole_footprint`, `hole_name` |
| `src/fenolite/placement/constrained_legality.py`, `preview.py`, `analysis/body_volumes.py` | slots |
| tests | `tests/unit/convert/test_convert_slots.py`, `tests/unit/backends/altium/test_slot_drills.py`, `tests/unit/placement/test_slot_obstacles.py`, `tests/kicad/convert/test_slots_convert.py`, `tests/routing/test_slots_route.py` |
| docs | `docs/conversion.md`, `docs/altium.md`, `docs/placement.md`, `docs/routing.md` |

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-CONV-SLOTS | The fixture converted to Altium and back to KiCad loads in 9.0.9 and 10.0.6 with no `invalid_outline`, its slots in no drill file and its drilled slot in the NPTH file (S-0020, S-0029) | `tests/kicad/convert/test_slots_convert.py` | `convert-slots-drc` `absent`, `convert-slots-drill` `equal` on both majors |
| H-G-DSN-SLOT | Freerouting routes no track through a slot written as a Specctra keep-out (S-0220) | `tests/routing/test_slots_route.py` | `route-slot` `absent` |

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| converted outline and holes, KiCad side | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-CONV-SLOTS` |
| slotted drills and regions, Altium side | ORACLE-VERIFIED(kicad-cli) through the import; regions at c0168's level | c0168's rows |
| routing around slots | ORACLE-VERIFIED(freerouting) | `H-G-DSN-SLOT` |
| report counts, ring verification, placement | mechanical | unit tests |

## Risks / Trade-offs

- **Converted boards change.** A conversion that lost every inner ring now writes them (or counts them as lost with the gate's reason); the census of c0159 is measured again.
- **The builder moves.** `fenolite.dsl.holes` keeps its public names; a test pins the generated footprints' bytes.

## Migration Plan

- Reports gain the kind `cutout`; the `outline` kind keeps only the outer ring's losses. The changelog says so.

## Budget (4.5 days)

| part | days |
|---|---|
| edges as an outline, `cutout` kind, KiCad to Altium | 1.0 |
| slotted drills in the library and document | 0.75 |
| Altium to KiCad: merge, generated holes, builder moved | 1.0 |
| ring verification | 0.5 |
| obstacles and the routing test | 0.5 |
| oracle runs, census, docs, closing | 0.75 |

Cut order: (1) ring verification (the report stands without it); (2) the routing run (the Specctra keep-out test stays); never cut: the counts of the report and the refusal of an unmerged overlap.

## Open questions

1. **Should a converted KiCad stadium cut-out become an Altium slot pad instead of a region?** Recommended: no; milled stays milled (c0168, Decision 1).
2. **Should `fenolite equivalent` compare board edge rings?** Recommended: yes, in a follow-up change of `design-equivalence`; this change verifies rings inside `convert` only.
3. **Should the merge of overlapping Altium cut-outs need `--allow-lossy`?** Recommended: no; a merge keeps the milled area, so it is `changed`, not `lost`.
