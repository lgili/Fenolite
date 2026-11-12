# Tasks: c0463

Rules for every task:

- Public sources only. Each fact goes in `docs/formats/altium/pcb-pour.md` with an S- id from S-2220..2229
  and an evidence label.
- The maintainer's board is private: codes and counts only. It is never in tests, fixtures, commits or
  messages.
- Run each touched test file alone with `-n 0`. Heavy runs go through `fenolite-heavy` with `-n 2`.
- Kit runs go on the shared Altium VM: record a foreign restart, close only your own documents.
- This change starts after c0462 tasks 1 to 4.

## 1. Outline arcs

- [x] 1.1 Record S-2221: how the polygon record stores an arc vertex, and how the saved regions
  approximate it. Proof: `uv run pytest tests/unit/docs -q -n 0`. (No `tests/unit/docs` folder exists; the
  docs tests `tests/unit/test_format_facts.py`, `test_evidence_register.py`, `test_docs_altium_read.py` and
  `test_evidence_matrix_page.py` pass.)
- [x] 1.2 Chord the arcs by `ARCRESOLUTION` and pour. The written polygon keeps its arcs. Proof:
  `uv run pytest tests/unit/backends/altium/test_pour_outline_c0463.py -k arc -q -n 0`. The pour leaves the record as read.
  A build or conversion still cannot write an arc polygon: the model holds no outline for it, and
  `lower.py` skips the zone (reported to the coordinator).
- [x] 1.3 Arc polygons through a conversion (D1a): the model and KiCad carry the outline chorded by
  `ARCRESOLUTION`; nothing drops an arc polygon; the way back writes the source's arc vertices while the
  outline still matches them, else the chords as a reported `changed` zone. Repin the conversion census.
  Proof: `uv run pytest tests/unit/convert/test_altium_zone_arcs_c0463.py -q -n 0`, then
  `tests/corpus/test_convert_altium_census.py` (corpus job).
  Done: the import gives an arc polygon `adapter.arcring.record_outline`'s ring (shared with the pour, which
  no longer imports `math`); the KiCad zone is `changed` and the board carries the source vertices in
  `Fenolite.Altium.PolygonArcs`, keyed by the zone's KiCad uuid (derived from `UNIQUEID` when the polygon has
  one; row 02's arc polygons have none); the way back writes them while the outline is their ring moved by a
  translation at most (an end angle of 360 written 0, the same arc), else chords with
  `lower.ZONE_ARCS_EDITED`; a rewrite writes the chords. Both proofs passed on 2026-11-06 (7 unit tests; the
  census and import pins unchanged, rows 02, 07 and 08 counting their arc zones under the new reason).

## 2. Outlines

- [x] 2.1 Inspect the corpus's two `outline` refusals and record S-2222. Proof: the record in
  `pcb-pour.md`.
- [x] 2.2 Repeated vertices kept once; self-touching rings split where S-2222 shows Altium's fill.
  Proof: the same file, `-k "touch or repeat"`. S-2222 shows no ring that touches itself; the boolean
  backend already pours one as one piece per loop, and a crossing ring still refuses `outline`.

## 3. Hatch and the remaining reasons

- [x] 3.1 Kit sample `pour-hatched` authored and run (S-2223). Proof: the kit record, declared in
  `tests/data/MANIFEST.toml`, and `uv run pytest tests/corpus/test_manifest.py -q -n 0`.
  Authored (2026-11-06): `examples/kit/pour-hatched/design.py` (P0 sentinel, P1 to P4 one per hatch style,
  P5 and P6 the grid's origin, P7 a slanted edge, P8 a ring that touches itself, P9 a bow tie), kit step
  K6.12 (`H-A-POUR-HATCH`, `repoured` only), the writer's hatch keys, and
  `tools/kit_pour_c0463.py prepare|record` (`tests/unit/backends/altium/test_pourrecord_c0463.py`).
  Run (2026-11-06, AD 24.5.2.23, S-2223): `tests/data/altium/kit/pour-hatched.json`, declared; 0 dialogs
  and 0 messages; the hatched polygons pour tracks and arcs, no region. Proof passed.
- [x] 3.2 Hatched pour. Proof: `uv run pytest tests/corpus/test_altium_pour_hatched_c0463.py -q -n 0`.
  Done (2026-11-06): `backends/altium/hatch.py` and `pour._hatched` pour the model S-2223 shows
  (`pcb-pour.md`, "Hatched pour"); the writer writes a hatch as tracks of its polygon, the self-check and
  `pourcompare.pour_pieces` read tracks and arcs back. P1 to P7 meet M1 to M4 against Altium's tracks and
  arcs (M1 at most 0.002 of the allowance). Proof passed (9 tests).
- [x] 3.3 `unshaped-copper` and `unshaped-pad` shaped through the writer's text and pad geometry (c0460).
  `threshold` and `pour-over` read every documented value. Proof:
  `uv run pytest tests/unit/backends/altium/test_pour_inputs.py tests/unit/backends/altium/test_pour_refusal.py -q -n 0`.
  Done: `threshold` and `pour-over` read every documented value (test in `test_pour_refusal.py`). Open:
  the text and pad shapes wait for c0460, which is not on `cac/lote-29`.
  Known difference (2026-11-07, design D7): shaping a stroke text needs the glyphs of Altium's stroke font,
  for which no public source was found; no public row refuses `unshaped-copper` or `unshaped-pad`.
  Status: closed as a measured known difference (design D7), 2026-11-07, coordinator decision.
- [x] 3.4 `shelved` and `plane-layer` counted as `exact`. Proof: the same files.

## 4. The Repour oracle

- [x] 4.1 The kit step `repour` (S-2224), and its records for the 8 rows. Proof:
  `uv run pytest tests/unit/cli/test_kit_cmd.py tests/unit/backends/altium/test_pourrecord_c0463.py tests/corpus/test_manifest.py -q -n 0`,
  and the records declared in the manifest.
  The step runs from `tools/kit_pour_c0463.py` (the rows as published, copied from the corpus cache), not
  from `fenolite kit`: the rows are no kit sample. The record holds counts, areas and ring hashes only (the
  coordinator's rule of 2026-11-06: no vertex list of a row, no saved board in the repository), so 4.2 runs
  M1 to M4 against the saved boards of a folder named by an environment variable and checks their hashes
  against the record. Proof of the tool: `tests/unit/backends/altium/test_pourrecord_c0463.py`.
  Run (2026-11-06, AD 24.5.2.23, S-2224): `tests/data/altium/kit/repour.json`, declared; 0 dialogs and 0
  messages on every row. Proof passed. Rows 03, 05 and 07 saved exactly Altium 24.5's repour; on 01, 02, 04,
  06 and 08 some rings differ, by at most 0.13% of a polygon's area, so no saved pour is stale enough to
  explain the M2 failures of rows 04 and 07.
- [x] 4.2 `tests/corpus/test_altium_pour_repour_c0463.py`, with stale saved pours named. Proof:
  `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_pour_repour_c0463.py -q -n 0`.
  Done (2026-11-06): with the corpus only, the record is checked against each source and the stale
  polygons are pinned (2 on row 01, 6 on 02, 8 on 04, 6 on 06, 5 on 08); with
  `FENOLITE_ALTIUM_REPOUR_DIR` naming the run's folder, each saved board is checked against the record and
  Fenolite's pour of it is compared by M1 to M4 with Altium's regions. Altium saves the split-plane polygons
  of row 01 in another order; they pour nothing and are compared as a set. The oracle's pins are this
  branch's (the census's refusals, rows 03 and 05 compared); 4.3 repins them on `cac/lote-29`. Proof passed
  (25 tests with the folder, 8 and 17 skipped without it).
- [x] 4.3 Repin the census to no refusals. Proof:
  `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_pour_census.py -q -n 2`.
  Measured (2026-11-07, S-2227): the pour reads the in-footprint pad-pair Clearance (`-02`, `-06`), the
  Clearance matrices whose twin cells differ (`-06`, `-08`) and the Board Outline Clearance matrix whose
  edges differ (`-06`); polygon cut-outs keep no clearance and a via without a pad joins its polygon. Of
  the 81 polygons of the 8 rows, 80 pour; one of `-08` is refused `neck-bound`. Against the repour, M1
  fails on 15 polygons (`-01` 4, `-02` 2, `-04` 4, `-06` 3, `-08` 2): known differences, design D7. The pour of `-08` takes longer than the 60 s of `test_pour_time`; it has its own limit (D7).
  Status: closed as a measured known difference (design D7), 2026-11-07, coordinator decision: 80 of 81 polygons poured, M1 fails on 15 of 81 (`-01` 4, `-02` 2, `-04` 4, `-06` 3,
  `-08` 2). Proof passed (focused set with `FENOLITE_HEAVY=1`).
  Rerun (2026-11-10, S-2304): the smaller exact cut cells and keep-out restriction correction pour
  all 33 polygons of row `-08`. The published and fresh native references give the same M1–M4
  verdicts by index. All 33 meet M1 and the remaining findings are pinned per criterion.
  Follow-up (2026-11-10, S-2306): on row `-08`, the engine had treated a component keep-out fill with
  no restrictions as copper. The isolated P14 comparison passes M1 after the engine applies only the
  actual copper-pour restriction of keep-out primitives. Authored fill controls verify that bytes 0
  and 24 allow copper and byte 4 excludes it (`test_pour_engine.py`).

- [x] 4.4 Correct the solid-pour 45° relief conductor origins of through-hole copper capsules.
  S-2308 confirms independently authored horizontal and vertical plated slots and a round-drilled
  pad with elongated copper. Public row `-06` P7/P9 now meet M1. P6 remains open at 1.47584 and the
  rectangular pad control still differs. The separate 90° control stopped before a native save.
  Proof: `test_pour_engine.py`, `test_pourrecord_c0463.py`, and the S-2308 comparison.

- [x] 4.5 Resolve the legacy outer-edge clipping of public row `-02` without removing true board
  cut-outs. S-2311 confirms seven authored native controls for ordinary and explicit edge clearances,
  straight and curved outlines, interior and edge-crossing cut-outs, and Keep-Out stroke restrictions.
  All 14 authored M1 comparisons pass. Public row `-02` P18/P17 pass M1 at 0.222 and 0.188, with M2
  still open. Row `-03` retains its ordinary clearance around the true cut-out and the separate no-net
  copper border tracks. Row `-01` uses the original Keep-Out stroke geometry rather than an inferred
  outer-board obstacle. Proof: `test_pour_engine.py`, `test_pour_rules.py`, focused public census, and
  the S-2311 native comparison. The remaining D7 differences stay open.

- [x] 4.6 Match the void around a simple top-layer octagonal SMD pad of another net in a solid pour.
  S-2314 confirms that Altium grows the dimensions before chamfering. All three authored boards pass
  M1–M4 with six octagons and six rectangles at each gap. The largest M2 difference on public row
  `-02` P18, 0.113452 mm² around D4, disappears. Two local P18 differences and 17 P17 differences still
  fail M2. Proof: `test_solid_pour_void_of_a_simple_octagonal_smd_pad` and S-2314.

- [x] 4.7 Scope the 90° solid-pour SMD relief check to the air gaps of facing relief pads of the same
  net (S-2309). The 36 focused engine tests passed and all 12 native peer-direction probes agree at
  the east conductor. A full-width receiver allows an extension to be clipped at the facing gap;
  ten authored circular controls pass M1–M4, as does public row `-06` P6 with neck removal off
  (S-2317). With its original setting, P6 passes M1 (0.19821) and M3, with M2 and M4 still open.

- [x] 4.8 Validate the native octagonal void through the computed writer's readback check. Preserve
  the correct void and refuse a known clearance intrusion around the same authored shape. S-2314's
  three native controls all write and pass readback in one round. Proof:
  `test_solid_pour_void_of_a_simple_octagonal_smd_pad` and the S-2314 writer comparison.

- [x] 4.9 Apply the native Hole and THPad clearance cells to concentric plated drills in solid pours
  and in the written copper self-check (S-2312). Compare the authored native controls, exercise
  acceptance and rejection through the computed writer, and repin the measured public row `-08`
  outcomes from the integrated engine.
  Completed 2026-11-11. All 33 polygons pour and pass M1 against the published and fresh native
  inputs. P75 and P89 clear M3. The per-index findings match the oracle on both references.
  Published comparison SHA-256 `f713ed740b51525019b7303b74ac5a2f9ee9358e6502bdbe55a965ac15df5ef9`.
  Native comparison SHA-256 `26a030f5ee4bb22224083549a822e7134a72934fb50caae259eb1c2b10abe74f`.
- [x] 4.10 Apply the solid polygon area cutoff before adding thermal spokes (S-2321). Prove the
  small and large clear receivers, an independent `REMOVEDEAD=FALSE` control and native replay.
  Completed 2026-11-11. The two authored native boards and the K6 reference retain their prior
  comparisons except for the corrected small clear receiver, which now meets M1–M4. The three
  focused regression cases and the computed writer pass. Comparison SHA-256
  `acd9cda4a485e8961c71e12f5cd4843b3ce68139666ee2d18c666d7904ff845f`.
- [x] 4.11 Match the native chord at acute tips with sufficiently long straight sides (S-2322).
  Proof: rotated native controls, the same-component guard, focused engine and writer tests,
  and the isolated public P14/P65 replay.
  Completed 2026-11-11. All 18 rotated and long-rim native controls pass M1–M4. The guarded
  replay clears the targeted P14/P65 local pockets and restores P65's missing same-net contact.
  The focused engine, computed writer, comparison and K6 record tests pass.
- [x] 4.12 Retain isolated rotated right-angle caps (S-2322). Prove the native diamond matrix,
  the linked-ring control and the isolated public row `-04` P11 difference.
  Completed 2026-11-11. The four isolated native controls match exactly. The two linked-ring
  controls retain their earlier behavior. On P11 the 0.002149315 mm² pocket clears and the
  separate 0.001654949 mm² pocket remains. The focused engine, writer and K6 records pass.

## 5. Graduation

- [x] 5.1 K6 round of `pour`, `pour4` and `pour-hatched` on Altium Designer 24.5. Proof: the kit report,
  recorded as S-2302.
  Recorded 2026-11-07 as S-2225; the task stays open for v0.8. K6.1, K6.4 and K6.6 pass; K6.2 (the reference
  holds no copper after Repour All), K6.3 (M1 and M2 on probe P6) and K6.5 (2 of 21 polygons with zero area)
  fail; K6.7 to K6.12 are not measured (the forced repour hung, then the VM bridge timed out), so `pour4` and
  `pour-hatched` are not run.
  Rerun (2026-11-10, Altium 24.5.2.23, S-2302): native `pour` repours from both reference and
  computed files leave 19 of 21 polygons poured, with the two declared empty controls. K6.2/K6.7 now
  pass P8 and still fail M2 on two P3 pockets of 0.0044 mm² each. The two `pour4` native repours
  hold 3 of 3 poured polygons and pass their geometry comparisons. The `pour-hatched` native reference
  holds 10 of 10 and passes K6.12's positive probe check. A separate geometry comparison still
  differs on P8 (self-touching) and P9 (crossing). These are observations from the repour saves.
  The current computed board reports zero Modified Polygons and zero Violating Polygons in the Polygon
  Pour Manager. The complete native K6.6 DRC report has 42 raw findings, exactly one naming a polygon:
  the expected unrouted-net diagnostic on the netless, empty `P5_NONET`. The report check retains all
  findings and allows only this fixture diagnostic, after verifying the control's net and absence of
  copper. K6.6 passes the scoped check.
  Final run (2026-11-10): `fenolite kit verify` exits 0. K6.1–K6.7 and K6.9–K6.12 pass using
  their native results, including the separate Polygon Pour Manager and Tools repours. K6.8 stays
  skipped because the setting is absent in Altium 24.5 (S-1572 and S-1579), the approved validation
  version. Kit SHA-256 `a326436bd40cb796b0dd06849c5a2e086cb805ba5cea0b9b1ce8c36ebb442fa5`;
  report SHA-256 `31a370dd86708cd7245fae6764840dd483de1051fc88b55098ba60a265f286ef`.
- [x] 5.2 Flow B with the default keep-out clearance: 28 of 28 polygons poured, and Altium DRC with no
  Repour equal per rule to the DRC after Repour on the same return. Proof: S-2301.
  S-2226 recorded the private board's transition from 0 of 28 to 28 of 28 poured in-process. The private
  source was unavailable for the native replay, so the revised criterion uses an authored 28-polygon
  substitute with the same default keep-out clearance rule and the Altium → KiCad → Altium flow. The return
  holds 28 of 28 poured regions before and after native Repour All. Altium 24.5.2.23 executed the same 14
  DRC rule instances on both copies and returned zero violations for each, including Modified Polygon.
  The private board's before/after native DRC remains unverified.
- [ ] 5.3 Evidence `ALTIUM-VERIFIED(kit)`, the new message texts, CHANGELOG, `gen_evidence_matrix` and
  `gen_altium_graduation` checks, and `openspec validate --all --strict`. Proof:
  `uv run pytest tests/unit/backends/altium/test_pour_modes.py -q -n 0`, then each `--check`.
  State at the cutoff (2026-11-07 03:30, lote-29 f155216a4): the checks pass (`test_pour_modes.py` 7 passed;
  `gen_evidence_matrix --check` and `gen_altium_graduation --check` exit 0; `openspec validate --all
  --strict` 151 of 151). The evidence is not raised: `result.pcb.pour.evidence` stays `INFERRED` and
  `altium.zones-poured` keeps naming Repour All, since D6's conditions are not all met (the Repour oracle
  fails M1 on the public rows in design D7). The completed K6 and Flow B tasks do not change that requirement. Raising it is the
  first step once K6 (S-2225) and flow B (S-2226) pass and D7 is resolved.
