## Context

- **Request.** Part D of the maintainer's request "board slots and cut-outs, end to end" (2026-10-15). Depends on c0167 (`Outline.slots`, `lowered_outline`, `merge_rings`, `core.stadium`, the shared fixture `tests/data/slots/design.py`).
- **What exists** (`origin/dev` at `a87723c`, read on 2026-10-15). Each item checks a claim of the request; corrections are marked.
  - Lowering of a model. `lower._outline` writes `Outline.points` and, when the outline has cut-outs, records `account.skip("outline", …, "the cut-outs of the outline are not written")` (`backends/altium/lower.py:611-616`): *the request is right*. Arcs of `Outline.arcs` are dropped there without a record. For a board read from KiCad (`Board.outline` is `None`), `_ring_of` chains the `Edge.Cuts` graphics into the first ring only, writes an arc as two straight edges and skips every edge of another ring with "an edge outside the first ring of the outline" (`lower.py:554-593`).
  - Script build. `lens/altium.py:1059-1066` plans no `.PcbDoc` when the outline has arcs or cut-outs (`altium.pcbdoc-not-written`). A hole part with a slot is reported as not lowered, "it is a slot, and the board hole of the document is round" (`lens/altium.py:716-730`); `pad_extras` refuses a footprint pad with a slot, "the drill is oval or has an offset" (`:494`), and `pcblib._pad_refusal` refuses a pad with a padstack (`pcblib.py:155-170`).
  - Records. `pcbrecords.pad_record` writes no hole shape: subrecord 6 is written only for a rounded rectangle, with hole shape 0 and no slot (`pcbrecords.py:523-558`). `hole_record` writes a round free pad on Multi-Layer without name, net or component, every size equal to the drill (`:561-570`). *Correction:* the request's "the pad record writer supports HOLE_SHAPE_SLOT, slot length and rotation" does not hold for the writer; it holds for the reader and for the fact row of subrecord 6: hole shape at offset 262 (0 round, 1 square, 2 slot), slot length at 263, slot rotation (double) at 267 (`docs/formats/altium/pcb-records.md:55`, `INFERRED`). Every slotted hole of the measured documents is plated and belongs to a component (`:100`).
  - Reader. `PadRecord.slot_length` and `slot_rotation` are read (`read/pcbprims.py:185-186, 394-395`, labelled `INFERRED` at `:641-642`), and the adapter maps hole shape 2 to a padstack slot (`adapter/pads.py:28, 102-105`). *Correction:* a component-less pad reaches the model, as a board-only `FootprintInstance` holding that one pad (`adapter/board.py:359-388`), never as `Board.holes` and never as a slot of the outline. The import builds `Board` with `outline=None` and no `holes` (`adapter/board.py:443-456`); the board outline of `Board6` becomes `Edge.Cuts` lines and arcs (`adapter/copper.py:1020-1050`); a free region of any kind becomes a filled graphic on its layer (`adapter/copper.py:925-950`), so a board cut-out region is not a cut-out of the model.
  - Region records. Free regions are written in `Regions6` and, with 37-byte vertices, in `ShapeBasedRegions6` (`pcb-records.md`, "Fenolite's choices", graphics); a read shape-based vertex holds a round flag, a centre, a radius and two angles (`read/pcbprims.py:222-233`). Fact rows: `KIND=0` for copper or drawn shapes "(1 is a cutout)" (`pcb-records.md:80`), and three older documents hold regions on layer 56 with `ISBOARDCUTOUT=TRUE` (`:90`). No row says which keys make a board cut-out that Altium Designer accepts.
  - Rules. `edge_clearance` is lowered to `BoardOutlineClearance` (`backends/altium/rulemap.py:121`).
- **Public pages** (read 2026-10-15; S-0460 is registered, the two others are registered by task 1.1):
  - S-0460, "Manufacturing" rule types: Board Outline Clearance has the edge kinds Outline Edge, Cavity Edge, Cutout Edge, Split Barrier and Split Continuation, and names no hole; Hole To Hole Clearance flags "multiple vias / pads at the same location, or overlapping pad / via holes".
  - The pad properties page (proposed S-0770): hole shapes Round, Rectangular and Slot; Hole Size is the diameter of a round hole "or width of a Rectangular or Slot"; Length cannot be smaller than the size; the hole's rotation is counter-clockwise relative to the pad, resolution 0.001°; Plated; "a free pad is one that is not part of a parent component object" and may have an empty designator; solder mask and paste are created at the pad site with rule or manual expansion; Multi-Layer makes a through-hole pad.
  - The region properties page (proposed S-0771): a region's Kind is Copper, Polygon Cutout, Board Cutout or Cavity (the last in the library editor); a Board Cutout defines a negative area inside the board shape and shows no Layer and no Net field; Arc Approximation is the largest deviation from a true arc.
- **Constraint.** Facts come from these pages, from records already measured and labelled, from KiCad's importer run as an oracle (`kicad-cli`), and from the maintainer's kit. No third-party source code is read for this change.

## Goals / Non-Goals

**Goals**
- A built or converted Altium document holds the slots and cut-outs, each in the form whose rules and outputs match its meaning, and reads back to the same geometry.
- Nothing is claimed for Altium Designer before the kit has shown it.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Milled is a board cut-out region; drilled is a slot pad.**
   - `Outline.cutouts` and `Outline.slots` are lowered through c0167's `lowered_outline`: every inner ring, merged where items overlap, becomes one Board Cutout region. Its edge is a cut-out edge of Board Outline Clearance (S-0460), so the edge-clearance rule of c0169 has a counterpart; overlapping slots are one region, so no hole rule fires.
   - A `Hole` with a length becomes a free slot pad. It is drilled (NC drill, drill drawing), as KiCad's oval NPTH pad is (c0167, measurement 4).
   - Rejected: every milled slot as a slot pad (the request's form). An L of two slot pads is two overlapping pad holes, which Hole To Hole Clearance flags (S-0460), and a pad near a slot pad is not a board-outline case. Kit case S5 runs both forms side by side, so the maintainer can overrule this with evidence; the recommended answer is open question 1.
   - Rejected: one region per cut-out without merging: Altium's behaviour for overlapping cut-out regions is not documented, and c0167 already merges.

2. **`Hole` gains `length` and `rotation`.** `Hole.length: Nm | None = None` (overall; `None` is round; above `drill` when set) and `Hole.rotation: Udeg = 0`, the axis of the length in the model frame. The canonical writer omits defaults. `lens/altium.py` fills them from a hole part's slot (`Padstack.hole_length`, `hole_rotation` turned by the part's rotation), and the import fills them for a free slot pad (Decision 6). KiCad still refuses `Board.holes` (c0167, Decision 8).

3. **The slot pad record.** `pad_record(…, hole_shape=0, slot_length=0, slot_rotation=0.0)` writes subrecord 6 when `hole_shape` is not 0, with the offsets of the fact row: inner sizes and shapes as the top layer, hole shape 2 at 262, slot length at 263, slot rotation at 267, zero offsets, alternate shapes and percentages as for a plain pad. `hole_record(x, y, drill, *, length=None, rotation=0, plated=False)`: for a slot, a free pad on Multi-Layer without name, net or component, shape round with size (`length`, `drill`) and pad rotation `rotation`, hole size `drill`, hole shape 2, slot length `length`, slot rotation 0 (relative to the pad, S-0770), so the copper equals the hole and no ring remains. Mask and paste stay "from rules" as for the round hole of c0085. What Altium does with the mask and paste of such a pad is kit case S1; until then `PROVENANCE.md` says it is Fenolite's choice.
   - Rejected: pad rotation 0 and the slot rotation in the hole. Both are permitted by the page; turning the pad keeps the copper and the hole one shape for any angle.

4. **The board cut-out region record.** Task 1.2 writes the form as fact rows: the property keys that make a Board Cutout (`KIND` and `ISBOARDCUTOUT` values, the layer), measured by importing written candidates with `kicad-cli pcb import` (10.0.6) and by the reader of this repository, and confirmed by the kit. Vertices are the lowered ring's, an arc written as a shape-based arc vertex when task 1.2 finds that KiCad's import and Fenolite's reader keep it, otherwise polygonised at 1 µm (`ARCRESOLUTION` stays `0.5mil`). If task 1.2 finds no form that KiCad imports as a board cut-out, the change stops there and the cut-outs stay reported (first item of the cut order).

5. **The gate.** `pcbdoc.CUTOUT_REGIONS: Final = False` until kit cases S3 to S5 pass. With it off, a script build with cut-outs or slots plans the document and gives one `altium.not-lowered` per cut-out (`where` `cutout/<k>` or `slot/<name>`), counted under `cutout` of `result.pcb.not_lowered`; `lower._outline` reports the same per item. With it on, they are written and counted under `cutout` of `result.pcb.written`. Arcs of the board ring still refuse the document. The flag is flipped by task 5.2, which needs the kit's evidence.
   - Rejected: keeping the refusal of the whole document until the kit. A document without its cut-outs is what the lowering of a read board already writes today, and the report names each one.

6. **Read-back.** In the import, a region whose keys make it a board cut-out (task 1.2) becomes `Edge.Cuts` graphics: one polygon, or lines and arcs from shape-based vertices, width 0, so `board_outline` and `edge_outline` see a cut-out. A free pad on Multi-Layer without name, net or copper ring (every size equal to the hole; for a slot, size (length, hole)) becomes a `Hole` with its slot instead of a board-only footprint; any other free pad stays a board-only footprint. RT-A2 compares `Hole`s by position, drill, length and rotation, and the cut-out rings of `edge_outline` with the written ones within the region's chord.
   - This changes what an import gives for such pads; the census of the public documents (task 4.4) counts how many move from footprints to holes, and `docs/altium.md` says so.
   - KiCad refuses `Board.holes` (c0167, Decision 8), so `convert --to kicad` (c0161's `convert/to_kicad.py`) MUST give each such `Hole` back as the board-only footprint of one unnumbered pad that the import made before (`to_kicad.hole_footprints`), so a conversion to KiCad writes what it wrote before this change; c0170 replaces that by the generated `Fenolite_Holes` footprint.

7. **Kit cases** (maintainer, Altium Designer, the form of c0166: date, version, case, file hash, step, expected and observed outcome, level). On the shared fixture written by this change:
   - S1 the lone drilled slot: opens; a slot in the NC drill and the drill drawing; no copper ring; solder mask and paste openings noted.
   - S2 two drilled slots in an L: Hole To Hole Clearance reports the pair (expected, S-0460).
   - S3 the milled lone slot and the rounded cut-out as regions: the board shape shows both holes in 2D and 3D; nothing in the drill outputs.
   - S4 the milled L as one region: one cut-out.
   - S5 Board Outline Clearance 0.5 mm with a pad 0.2 mm from the milled slot (expected: flagged) and from the drilled slot (expected: not flagged).
   - S6 repour of a polygon over the board: no copper in the cut-outs.
   - S7 save and read back with `fenolite`: the same slots and cut-outs within 1 µm.
   - S8 the same document with the gate off: no region, and the build's report names each cut-out.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/board.py`, schema | `Hole.length`, `Hole.rotation` |
| `src/fenolite/backends/altium/pcbrecords.py` | `pad_record(…, hole_shape, slot_length, slot_rotation)`, `hole_record(…, length, rotation)`, `cutout_region(…)` |
| `src/fenolite/backends/altium/pcbdoc.py`, `lower.py` | `CUTOUT_REGIONS`; cut-outs from `lowered_outline`; per-item report |
| `src/fenolite/lens/altium.py` | the document planned for cut-outs and slots; slotted hole parts as `Hole` |
| `src/fenolite/backends/altium/adapter/board.py`, `adapter/copper.py` | free hole pads as `Hole`; cut-out regions as edges |
| `src/fenolite/checks/rta2.py` | holes and cut-out rings compared |
| `src/fenolite/convert/to_kicad.py` | `hole_footprints`: imported holes back as board-only footprints |
| `src/fenolite/backends/altium/PROVENANCE.md`, `docs/formats/altium/pcb-records.md`, `docs/evidence/sources.md` | the rows and sources |
| tests | `tests/unit/backends/altium/test_slot_records.py`, `test_cutout_regions.py`, `tests/unit/lens/test_altium_slots.py`, `tests/unit/backends/altium/adapter/test_free_holes.py`, `tests/kicad/altium/test_slots_import.py` |
| docs | `docs/altium.md` ("Outlines with arcs, and holes", the RT-A2 table), `docs/evidence/altium-pcb.md` (Part S) |

## Sources registered by this change

- S-0770 (proposed id; the next free one at task 1.1): https://www.altium.com/documentation/altium-designer/pcb-pad-properties, Altium documentation, read for facts.
- S-0771 (proposed id): https://www.altium.com/documentation/altium-designer/pcb-region-properties, Altium documentation, read for facts.
- S-0460 gains the reading of 2026-10-15 (Board Outline Clearance edge kinds; Hole To Hole Clearance on overlapping holes).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-SLOT-PAD | A free pad with hole shape 2, size (length, width) and slot length `length` is read back by Fenolite and imported by KiCad 10.0.6 as a non-plated oval hole of that size and angle (S-0770, S-0020) | `tests/kicad/altium/test_slots_import.py -k pad` | `altium-slot-pad` `equal` on 10.0.6 |
| H-A-CUTOUT-REGION | A region with the keys of task 1.2 is imported by KiCad 10.0.6 as an `Edge.Cuts` cut-out of the same ring within 1 µm (S-0771, S-0020) | `-k region` | `altium-cutout-region` `equal` on 10.0.6 |
| H-A-SLOT-KIT | Kit cases S1 to S8 hold their expected outcomes in Altium Designer | maintainer's report | one outcome per case |

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| slot pad record and its read-back | ORACLE-VERIFIED(kicad-cli) (10.0.6) | `H-A-SLOT-PAD` |
| cut-out region record and its read-back | ORACLE-VERIFIED(kicad-cli) (10.0.6) | `H-A-CUTOUT-REGION` |
| regions written by default (`CUTOUT_REGIONS = True`) | ALTIUM-VERIFIED(kit) | `H-A-SLOT-KIT` S3 to S5 |
| the build's per-item report while the gate is off | mechanical | unit tests |

## Risks / Trade-offs

- **Two forms of slot in Altium.** The kit shows each rule on each form (S2, S5); the docs say which DSL call gives which.
- **An import changes.** Free hole pads become `Hole`s; a design read before and after differs there. The census counts it, and the changelog says it.
- **Mask and paste of a free slot pad** are Fenolite's choice until S1.
- **Polygonised regions** if the arc vertex form is not settled: within 1 µm; Altium's arc approximation is separate.

## Migration Plan

- Additive model keys. Builds without cut-outs, slots or slotted holes write the same bytes (every committed Altium sample).
- A script build with cut-outs now plans a document; its report names each cut-out until the gate is on.

## Budget (6 days)

| part | days |
|---|---|
| facts, sources, rows; region candidates measured by KiCad's import | 1.25 |
| `Hole` keys; slot pad record; hole parts with slots | 1.0 |
| region record behind the gate; lowering and per-item report | 1.0 |
| import: holes and cut-out regions; RT-A2 | 1.0 |
| kit files, Part S, the maintainer's run, the gate | 1.0 |
| docs and closing | 0.75 |

Cut order: (1) cut-out regions (stop after task 1.2 when no imported form is found; slot pads stand alone); (2) arc vertices in regions (polygonised instead); never cut: the fact rows before the writer, the per-item report, the gate.

## Open questions

1. **Milled slots as board cut-out regions rather than slot pads?** Recommended: yes (Decision 1); S5 gives the maintainer the evidence either way.
2. **Should a free slot pad's solder mask be tented or opened?** Recommended: opened by the rule, as c0085's round hole; S1 records what Altium does.
3. **Should the import turn free unnamed non-plated pads into `Hole`s?** Recommended: yes, only those without a copper ring (Decision 6); any other free pad stays a footprint.
4. **Should the gate be a build option instead of a constant?** Recommended: no; an option would let a user write an unconfirmed form. The kit run flips it once.
5. **Arcs of the outer board ring in `Board6`?** Recommended: a follow-up change; the reader already knows the arc vertex, the writer needs its own rows and a kit case.
