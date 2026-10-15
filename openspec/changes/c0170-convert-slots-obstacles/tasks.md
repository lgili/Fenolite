## 0. Entry check

- [ ] 0.1 Read `openspec list`, c0159's `design-conversion` delta (or the living spec once archived), and the living `altium-pcb-writer`, `kicad-file-backend`, `constrained-board-placement` and `specctra-dsn` specs. Write under this task, with the date: that c0167, c0168 and c0169 are archived or their code is on the branch, and the state of c0168's gate; that c0159, c0160 and c0161 are archived (else stop: the conversion's report and verification are theirs); the maintainer's answers to the open questions. Proof: `openspec validate c0170-convert-slots-obstacles --strict --no-interactive` passes.

## 1. Register

- [ ] 1.1 Add `H-K-CONV-SLOTS` and `H-G-DSN-SLOT` to `docs/hypotheses.md` (level `INFERRED`, the tests and criteria of `design.md`), and run c0159's census to record the `outline` losses before this change in `docs/evidence/conversion.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run pytest tests/corpus/test_convert_census.py -rA` with the corpus cached.

## 2. KiCad to Altium

- [ ] 2.1 Take the edges with `edge_outline` in `lower._outline` and count inner rings under `cutout` (scenario "Fixture to Altium"). Proof: `uv run pytest tests/unit/convert/test_convert_slots.py -k altium tests/unit/convert/test_report.py -q`.
- [ ] 2.2 Write slotted drills of footprint pads (scenario "An oval mounting slot"); every committed Altium sample keeps its bytes. Proof: `uv run pytest tests/unit/backends/altium/test_slot_drills.py tests/unit/backends/altium -q`.

## 3. Altium to KiCad

- [ ] 3.1 Move the hole footprint builder to `model/holes.py`, re-exported by `dsl/holes.py` with the same bytes. Proof: `uv run pytest tests/unit/dsl/test_holes.py tests/unit/test_import_graph.py -q`.
- [ ] 3.2 Merge overlapping cut-outs and give each `Hole` its generated footprint in `to_kicad`, replacing c0168's `hole_footprints` (scenarios "Overlapping Altium cut-outs to KiCad", "Same footprint from a script and a conversion"). Proof: `uv run pytest tests/unit/convert/test_convert_slots.py -k "kicad or holes" -q`.
- [ ] 3.3 Record `H-K-CONV-SLOTS` on the fixture converted to Altium and back. Proof: `uv run pytest tests/kicad/convert/test_slots_convert.py -rA` in the pinned 9.0.9 and 10.0.6 images; `uv run pytest tests/kicad/test_probe_results.py -q`.

## 4. Verification and obstacles

- [ ] 4.1 Verify edge rings after a conversion (scenario "A dropped ring is a difference"). First item of the cut order. Proof: `uv run pytest tests/unit/convert/test_convert_slots.py -k verify -q`.
- [ ] 4.2 Take slots in the constrained placer, its preview and `body_volumes` (scenario "A footprint over a slot"). Proof: `uv run pytest tests/unit/placement/test_slot_obstacles.py tests/unit/placement tests/unit/analysis/test_body_volumes.py -q`.
- [ ] 4.3 Test the Specctra keep-outs and record `H-G-DSN-SLOT` with Freerouting (scenarios "Keep-outs of the fixture", "Routed around the slot"). Second item of the cut order for the run. Proof: `uv run pytest tests/routing/test_slots_route.py -rA` with Freerouting available.

## 5. Closing

- [ ] 5.1 Run the census again and write the `cutout` counts after this change into `docs/evidence/conversion.md`; document the kind, the merge, the generated holes and the obstacles in `docs/conversion.md`, `docs/altium.md`, `docs/placement.md` and `docs/routing.md`. Proof: `uv run pytest tests/corpus/test_convert_census.py -rA` with the corpus cached; `uv run pytest tests/consistency -q`.
- [ ] 5.2 Run the residue scan and the fast checks. Proof: `uv run python tools/residue/scan.py` exits 0; `make check-fast` passes.
- [ ] 5.3 Update the evidence labels: the two rows hold their measured levels; `uv run python tools/gen_evidence_matrix.py`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_evidence_matrix_page.py -q`.
- [ ] 5.4 Add to `CHANGELOG.md` under `## [Unreleased]`: slots and cut-outs in conversions, the kind `cutout`, slotted drills to Altium, generated hole footprints from Altium, slots as placement and routing obstacles. Proof: `grep -n "cutout" CHANGELOG.md`; `openspec validate c0170-convert-slots-obstacles --strict --no-interactive` passes.
