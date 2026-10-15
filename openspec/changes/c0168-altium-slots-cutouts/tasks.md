## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `design-model`, `altium-pcb-writer`, `altium-build`, `altium-import` and `altium-verification` specs. Write under this task, with the date: that c0167 is archived or its `lowered_outline`, `Outline.slots` and fixture are on the branch (else stop); the state of c0166 (the native acceptance inventory) on the maintainer's branch and whether Part S joins it; whether another open change holds a delta of "Non-plated holes and slots" or "PCB document output" (regenerate the MODIFIED blocks from the living text if one was archived); the maintainer's answers to the open questions. Proof: `openspec validate c0168-altium-slots-cutouts --strict --no-interactive` passes.

## 1. Facts and register

- [ ] 1.1 Register the pad and region pages as the next two free source ids (proposed S-0770, S-0771) and add the reading of 2026-10-15 to S-0460 in `docs/evidence/sources.md`; write the rows of the slot pad (hole size is the width, length, rotation relative to the pad, empty designator, mask and paste at the pad site) and of the rules (Board Outline Clearance edge kinds, Hole To Hole Clearance on overlapping holes) into `docs/formats/altium/pcb-records.md` and `pcb-copper.md`; add `H-A-SLOT-PAD`, `H-A-CUTOUT-REGION` and `H-A-SLOT-KIT` to `docs/hypotheses.md`. No writer code before this task is ticked. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`.
- [ ] 1.2 Measure the board cut-out region: write candidate regions (the key sets of the rows at `pcb-records.md:80` and `:90` and of S-0771) into scratch documents, import each with `kicad-cli pcb import` (10.0.6) and with Fenolite's reader, and record which one KiCad gives as an `Edge.Cuts` cut-out and whether a shape-based arc vertex survives; write the rows "Board cut-outs" with label `ORACLE-VERIFIED(kicad-cli)` for the import and `INFERRED` for Altium. If none is imported as a cut-out, write that here and stop the region part (cut order 1). Proof: `uv run pytest tests/kicad/altium/test_slots_import.py -k candidates -rA` in the pinned 10.0.6 image; `uv run pytest tests/unit/test_format_facts.py -q`.

## 2. Slotted holes

- [ ] 2.1 Add `Hole.length` and `Hole.rotation` with the schema (scenario "A slotted hole round-trips"). Proof: `uv run pytest tests/unit/model/test_hole_slots.py tests/unit/model -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 2.2 Write the slot fields of `pad_record` and `hole_record` (scenario "A turned slot"); every committed Altium sample keeps its bytes. Proof: `uv run pytest tests/unit/backends/altium/test_slot_records.py tests/unit/backends/altium -q`.
- [ ] 2.3 Hand slotted hole parts to the document as `Hole`s (scenario "A plated hole and a slot are reported"); record `altium-slot-pad` by importing the written fixture with KiCad. Proof: `uv run pytest tests/unit/lens/test_altium_slots.py -q`; `uv run pytest tests/kicad/altium/test_slots_import.py -k pad -rA` in the pinned 10.0.6 image.

## 3. Cut-outs

- [ ] 3.1 Plan the document for an outline with cut-outs or slots and report each cut-out while `CUTOUT_REGIONS` is false, in the build and in `lower._outline` (scenario "Cut-outs while the gate is off"). Proof: `uv run pytest tests/unit/lens/test_altium_slots.py -k gate tests/unit/lens/test_altium_pcb.py -q`.
- [ ] 3.2 Write `cutout_region` from the rows of task 1.2 and the lowering behind the gate (scenarios "The merged L as one region", "KiCad imports the region"); record `altium-cutout-region`. Proof: `uv run pytest tests/unit/backends/altium/test_cutout_regions.py -q`; `uv run pytest tests/kicad/altium/test_slots_import.py -k region -rA` in the pinned 10.0.6 image.

## 4. Read-back

- [ ] 4.1 Import cut-out regions as edges and free hole pads as `Hole`s (scenario "Written fixture read back"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_free_holes.py tests/unit/backends/altium/adapter -q`.
- [ ] 4.2 Give each imported `Hole` back to `convert --to kicad` as the board-only footprint the import made before (`to_kicad.hole_footprints`, Decision 6); the conversion census of c0161 keeps its counts. Proof: `uv run pytest tests/unit/convert -q`.
- [ ] 4.3 Compare holes and cut-out rings in RT-A2 (scenario "Fixture passes RT-A0 to RT-A2"). Proof: `uv run pytest tests/unit/checks/test_rta2_slots.py tests/unit/checks -q`.
- [ ] 4.4 Run the census of the public Altium documents and write into `docs/evidence/altium-pcb-read.md` how many free pads became `Hole`s and how many regions became cut-outs. Proof: `uv run pytest tests/corpus/test_altium_pcb_census.py -rA` with the corpus cached.

## 5. Kit

- [ ] 5.1 Build the kit files of Part S (the fixture with the gate on, written for the kit only, and the variant with a pad 0.2 mm from each slot and the two rules) into `~/fenolite-altium-checks/session-4/S-slots/` with a `README.md` and their SHA-256; write Part S, cases S1 to S8 with their expected outcomes, into `docs/evidence/altium-pcb.md`. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_s -q`.
- [ ] 5.2 **Maintainer, in Altium Designer.** Run S1 to S8 and give the report; record it under "Reports" of `docs/evidence/altium-pcb.md` in the form of the native acceptance inventory, register its source, and set `H-A-SLOT-KIT`. Only when S3 to S5 pass, set `pcbdoc.CUTOUT_REGIONS = True` and update the scenario "Cut-outs while the gate is off" to the written counts. OPEN until Altium was run; nothing is marked `ALTIUM-VERIFIED` before. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_s tests/unit/test_hypotheses_register.py -q`.
- [ ] 5.3 Record in `src/fenolite/backends/altium/PROVENANCE.md` the slot pad, the cut-out region and the import rules with their sources, and S1's finding on mask and paste. Proof: `uv run pytest tests/unit/test_provenance.py -q`.

## 6. Closing

- [ ] 6.1 Document the two forms, the gate, the import change and the RT-A2 rows in `docs/altium.md` and the slot rule in `docs/dsl.md`. Proof: `uv run pytest tests/consistency -q`.
- [ ] 6.2 Run the residue scan and the fast checks. Proof: `uv run python tools/residue/scan.py` exits 0; `make check-fast` passes.
- [ ] 6.3 Update the evidence labels: the three rows hold their measured levels; `pcbdoc.EVIDENCE` names them; `uv run python tools/gen_evidence_matrix.py`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_evidence_matrix_page.py -q`.
- [ ] 6.4 Add to `CHANGELOG.md` under `## [Unreleased]`: slotted board holes, slot pads, cut-out regions behind the kit's gate, the import change, the 0.4.x sentence. Proof: `grep -n "cut-out region" CHANGELOG.md`; `openspec validate c0168-altium-slots-cutouts --strict --no-interactive` passes.
