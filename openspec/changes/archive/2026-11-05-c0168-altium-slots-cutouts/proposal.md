## Why

Second change of the request "board slots and cut-outs, end to end" (2026-10-15), after c0167, against `origin/dev` at `a87723c`. An Altium build or conversion drops every slot and cut-out (design, "Context"):

- A script build plans no `.PcbDoc` at all for an outline with cut-outs or arcs (`altium.pcbdoc-not-written`); c0167 adds slots to that refusal.
- The lowering writes the outer ring only ("the cut-outs of the outline are not written"); for a read KiCad board, the first edge ring.
- No record writes a slotted hole: the pad record has no hole shape, a board hole is round, and a footprint pad with a slot is refused. 
- A read document's free slot pads and board cut-outs do not reach the model as what they are.

Altium has two forms, and its public pages say what each is for (S-0460, read 2026-10-15): Board Outline Clearance measures to outline, cavity, cut-out and split-line edges and names no hole, and Hole To Hole Clearance flags overlapping pad holes. So a milled slot, which exists for its edge, is a board cut-out; a drilled slot is a slot pad.

## What Changes

- **Two forms, one meaning each.** A drilled slot (`Hole` with a length, from `design.hole(…, length=…)` or a model caller) becomes a free non-plated pad with a slot hole, Multi-Layer, no net, pad size equal to the hole. A milled cut-out or slot (`Outline.cutouts`, `Outline.slots`, merged by c0167's `lowered_outline`) becomes a board cut-out region.
- **Model.** `Hole.length` and `Hole.rotation`, additive keys.
- **Facts first.** The slot fields of the pad and the form of a board cut-out region are written as fact rows from Altium's public pages, the records already measured and KiCad's importer run as an oracle, before any writer code.
- **A planned document for cut-outs.** A script build with cut-outs or slots plans the document and reports each cut-out as not lowered until the maintainer's kit has confirmed the region form; then the regions are written.
- **Read-back.** A board cut-out region is imported as `Edge.Cuts` edges, so `board_outline` and `edge_outline` give it as a cut-out; a free unnamed non-plated pad becomes a model `Hole` with its slot. RT-A0 to RT-A2 compare both.
- **The maintainer's kit cases** S1 to S8 (Altium Designer) on the shared fixture, in the form of c0166: board shape, drill outputs, Board Outline Clearance, Hole To Hole Clearance.

Size: 6 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Slotted board holes".
- `altium-pcb-writer`: MODIFIED "Non-plated holes and slots"; ADDED "Board cut-out regions".
- `altium-build`: MODIFIED "PCB document output".
- `altium-import`: ADDED "Board cut-outs and free holes of a document".
- `altium-verification`: ADDED "Slots and cut-outs in the round trips", "Kit cases for slots and cut-outs".

## Non-goals

- Arcs of the outer board ring in `Board6` (a follow-up; the refusal stays).
- Plated free slots with copper, and slots in footprint pads of a library (c0170).
- `ALTIUM-VERIFIED(kit)` for anything the kit has not run.

## Evidence level required

- Fact rows `INFERRED` (S-0460, the registered pad and region pages, measured records); KiCad's import of the written files `ORACLE-VERIFIED(kicad-cli)` (10.0.6).
- Regions written by default only after `ALTIUM-VERIFIED(kit)` cases S3 to S5; until then the skip is reported.

## Impact

- `model/board.py` and the schema; `backends/altium/pcbrecords.py`, `pcbdoc.py`, `lower.py`, `adapter/board.py`, `adapter/copper.py`, `PROVENANCE.md`; `lens/altium.py`; `checks/rta2.py`; `convert/to_kicad.py`; docs.
- Depends on c0167. Release 0.4.x cannot read a model document whose hole carries `length`.
