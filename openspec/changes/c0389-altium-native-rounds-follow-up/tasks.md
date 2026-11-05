## 0. Carried finding

- [x] 0.1 Record the review of 2026-11-05: on the maintainer's delegation of 2026-11-04, a recorded Claude-agent run in Altium 24.5.2.23 satisfies a maintainer task only when its proof criteria pass as written. c0166 3.5 and c0180 2.4a passed and were ticked in their own changes; the tasks below did not and moved here unchanged in scope and gates. Proof: the 2026-11-05 notes under each source task; `openspec validate c0389-altium-native-rounds-follow-up --strict --no-interactive`.

## 1. Write graduation (c0092)

- [ ] 1.1 (from c0092 5.3) Complete accepted criterion5 on the actual `examples/acceptance_v03` tree: record the real Altium24.5.2.23 run with source-bound hashes and all required steps; satisfy the unchanged graduation rule for PCB and schematic writes, or retain the measured failure visibly. A historical kit on other samples does not satisfy this task. Proof: actual eligible native run, current register/graduation output and exact-source CI. No evidence promotion by approval alone. This task stays open while accepted criterion5 is unmet; a recorded failure is evidence, not completion.
  - Blocker on 2026-11-05: Criterion 5 is unmet. S-1586 did not confirm the six-layer stack (four copper layers in use) or the 8 written rule kinds (37 rules under default names). The graduation rule needs a current `ALTIUM-VERIFIED` kit result on the acceptance tree, and the exact-source CI run is pending.
- [ ] 1.2 (from c0092 6.2) Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
  - Blocker on 2026-11-05: `H-A-ACC-KIT` asks for a recorded K1–K8 kit run on the acceptance tree. S-1586 ran handoff steps 2 to 6, not a recorded kit run, so the row still holds no measured result.

## 2. Conversion and native acceptance requests (c0160, c0166)

- [ ] 2.1 (from c0160 5.3) **Maintainer, in Altium Designer.** Run Part T and give the report; record it under "Reports" of `docs/evidence/altium-pcb.md` (tool `AD <major>.<minor>`, date, one generic outcome per step, no artefact), register its source, and set the four rows' results (scenario "Part T recorded"). OPEN until Altium was run; nothing is marked `ALTIUM-VERIFIED` before. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
  - Blocker on 2026-11-05: T6 was run only for PADSTACK. SCHEMATIC has T1–T5 at the current source (S-1578). DIFAT is refused with `FEN-7001` at the current source and has T1–T5 only on the 2026-10-12 bundle. Connector masks are not exercised (no source has a `connect` pad).
- [ ] 2.2 (from c0166 2.1) Finish Part T for PADSTACK, DIFAT and SCHEMATIC; inspect connector masks and record T1-T6 per case. Proof: the native report and `uv run pytest tests/unit/test_altium_verification_docs.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`.
  - Blocker on 2026-11-05: Connector masks are not inspected (no source has a `connect` pad). DIFAT is refused with `FEN-7001` at the current source, and T6 exists only for PADSTACK.
- [ ] 2.3 (from c0166 3.1) Execute schematic A/B/L/N/H requests not settled by equivalent kit cases. Proof: dated per-step report and the hypothesis/provenance tests.
  - 2026-11-05 (S-1600, AD 24.5.2.23, agent run): A2, A4, B1 to B3, L1 to L5, L7 and N1 to N3 run and recorded under "Reports" of `docs/evidence/altium-schematic.md`; hypothesis notes added, levels unchanged.
  - Still open: the A4 PCB Model dialog and the L2 Pin Editor dialog were not opened (their fields were read through the API and the Properties panel), Part H and N4 (the Viewer) were not run in this round.
- [ ] 2.4 (from c0166 3.2) Execute PCB D/C requests, X8.6 counts and the supplementary long-via measurement. Proof: dated per-step report and the hypothesis/provenance tests.
  - 2026-11-05 (S-1601, AD 24.5.2.23, agent run): D1 to D3, C6, X8.6 and the long-via measurement run and recorded under "Reports" of `docs/evidence/altium-pcb.md`. D1 to D3 are as expected. C6 is not: a design rule check reports Starved Thermal and an Un-Routed Net between the `GND` via and `D1` pad 1, so `H-A-PCB-CU-PLANE` stays pending. X8.6 repeats the counts of 2026-10-13. The nine via bytes hold the via diameter. Hypothesis notes added, levels unchanged.
  - Still open: C6 fails its expectation (plane connectivity; cause not studied), and C5 (Viewer upload) was not run.
- [x] 2.7 (follow-up of 2.4, C6) Find why the plane writer's connection of the `GND` via and `D1` pad 1 fails
  Altium's design rule check: Starved Thermal on the `GND` via (13 %) and on `D1` pad 1 (10 %), and an
  Un-Routed Net between them (S-1601). The cause is not studied. Proof: a C6 rerun in Altium with no such
  violation, recorded under "Reports" of `docs/evidence/altium-pcb.md`; `H-A-PCB-CU-PLANE` set by it.
  - 2026-11-05: needs C6 rerun. Studied against the public rule definitions (S-1652) and the saved plane
    records of the corpus (S-1653): the sample's holes starve neither thermal, and the document held no
    `Split Plane` polygon and no plane rule. The writer now adds one split plane per plane on its net and
    the `All` rules `PlaneConnect` (pads Relief, vias Direct) and `PlaneClearance`
    (`tests/unit/backends/altium/test_plane_connect.py`); the new `p0` is `4082a630…`.
    The kit sample `board6` holds a plane, so kit steps K2.4 and K5.1 to K5.5 must run again on the
    current kit; until then nine register rows are set back (`docs/evidence/altium-kit/README.md`, "Stale
    rows after c0389 task 2.7").
  - 2026-11-05, S-1607 (agent run, AD 24.5.2.23 Trial): C6 on the new `p0` (`4082a630…`). The board holds the split
    plane on Internal Plane 1 (`GND`) and the rules `PlaneConnect` and `PlaneClearance`. The design rule check
    reports no Starved Thermal and no Un-Routed Net; its 42 violations are silk, solder mask and one antenna.
    `H-A-PCB-CU-PLANE` is left to the coordinator. The kit rerun of K2.4 and K5.1 to K5.5 on `board6` (run
    `2026-11-05-ddbe216c`) passes and restores the four `H-A-PCBX-*` rows. The other five rows stay
    `INFERRED`, because they also name steps of other samples (`docs/evidence/altium-kit/README.md`, "board6
    rerun of 2026-11-05").
  - Closed 2026-11-05 by the coordinator on S-1607: C6 has no Starved Thermal and no Un-Routed Net. `H-A-PCB-CU-PLANE`
    records the run and stays `INFERRED`, since an agent run raises no level under the approved scope.
- [ ] 2.5 (from c0166 3.3) Execute Repeat R1-R4 and R5 when its implementation is available; preserve any branch blocker. Proof: the report and focused Repeat tests.
  - Blocker on 2026-11-05: Repeat R1–R5 was not run in any agent round (S-1570 to S-1589); R5 keeps its recorded failure.
  - 2026-11-05 (S-1602, AD 24.5.2.23 Trial, agent run): R1 and R2 run on the committed bytes that passed in AD 26.5
    on 2026-10-14. The repeat does not expand in 24.5: "Missing child-sheet in two_ch.SchDoc in Symbol
    Repeat(CH,1,2)", and all twelve naming pairs flatten to `J1` and `U1`. The same happens through the UI with
    one project open. This is recorded as an observation scoped to that version; the 26.5 pass stands, and the
    writer and the levels are unchanged (coordinator's decision). Still open: R3 and R4 need the channels, so
    they wait for AD 26; R5 keeps its failure.
- [ ] 2.6 (from c0166 3.4) Execute remaining OutJob, template/custom-border, hierarchy-mode and rule-export requests. Proof: the report and focused documentation/provenance tests.
  - Blocker on 2026-11-05: The OutJob, template/custom-border, hierarchy-mode and rule-export requests were not run in any agent round (S-1570 to S-1589).

## 3. Board kits: slots, panels, repour (c0168, c0173, c0215)

- [ ] 3.1 (from c0168 5.2) **Maintainer, in Altium Designer.** Run S1 to S8 and give the report; record it under "Reports" of `docs/evidence/altium-pcb.md` in the form of the native acceptance inventory, register its source, and set `H-A-SLOT-KIT`. Only when S3 to S5 pass, set `pcbdoc.CUTOUT_REGIONS = True` and update the scenario "Cut-outs while the gate is off" to the written counts. OPEN until Altium was run; nothing is marked `ALTIUM-VERIFIED` before. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_s tests/unit/test_hypotheses_register.py -q`.
  - Blocker on 2026-11-05: K5.6 failed: the Drill Drawings mark `D1` only by its symbol. So `kit verify` judges `H-A-SLOT-KIT` fail, and the row stays `INFERRED`. S3, S4 and S5 pass in S-1583, which meets the condition for `CUTOUT_REGIONS`, but the gate was not changed in this review. That change waits for the coordinator's decision.
  - Coordinator's decision of 2026-11-05: S3, S4 and S5 pass in S-1583, which meets the condition for `pcbdoc.CUTOUT_REGIONS`, but the gate is not flipped. Task 5.2 fails as a whole on K5.6, and a write gate does not change hours before a release. The flip waits for a K5 round that passes as a whole.
- [x] 3.2 (from c0173 2.4) **Maintainer, in Altium Designer 24.5.2.23 (approved pending-run scope).** Run Q1 to Q6 and send the folder, the version, the date and the SHA-256 of each file; record the report under "Reports" of `docs/evidence/altium-pcb.md` in the form of the native acceptance inventory (date, version, case, file hash, step, expected and observed outcome) and register its source. OPEN until Altium was run; nothing is marked `ALTIUM-VERIFIED` by it. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_q tests/unit/test_hypotheses_register.py -q`.
  - Blocker on 2026-11-05: Q3 was not run: the View Configuration panel covered the Projects panel twice. Q6's folder cannot be sent as it is, because each saved panel holds VM paths.
  - Done on 2026-11-05 (S-1593), by a Claude agent on the maintainer's delegation of 2026-11-04, in Altium 24.5.2.23 on the S-1576 saved folder. Q3 saves `panel-layers.PcbDoc` (`d875c453…`) as expected: V Cut is Mechanical 2 (layer 58), Route Tool Path is Mechanical 3 (layer 59), and the type is stored in `Board6` `LAYER<n>MECHKIND` and in `LayerKindMapping`. Q6 is as expected: the kit privacy scan runs first on the zipped folder and finds 22 VM path strings in the 11 panels; the folder stays private, and only digests and facts are recorded. Q1, Q2, Q4 and Q5 hold their S-1576 outcomes. The report is under "Reports" of `docs/evidence/altium-pcb.md`; levels unchanged (task 3.4).
- [x] 3.3 (from c0173 7.4) **Maintainer, in Altium Designer 24.5.2.23 (approved pending-run scope).** Run Q7 to Q12 and give the report; record it as task 2.4 does and set `H-A-PANEL-RECORD`, `H-A-PANEL-LAYERKIND` and `H-A-PANEL-KIT`. Only when Q7, Q8 and Q9 pass, set `EMBEDDED_ARRAYS = True`. OPEN until Altium was run. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_q tests/unit/test_hypotheses_register.py -q`.
  - Blocker on 2026-11-05: Q8 failed: the copies keep the old track after a saved child move and a reopen. Q9 passed only in part: by default there is no separate non-plated drill file and no `V-Cut` Gerber. `EMBEDDED_ARRAYS` stays off, and the three rows keep their levels.
  - Rerun on 2026-11-05 (S-1593, same kit bytes `75bb8545…`): Q8 shows the move in all four copies only after Altium is closed and started again; reopening the panel in one session still shows the old track, and no menu refreshes an array. Q9 with defaults is unchanged. With the separate-drill option and `V-Cut` ticked, Altium writes `panel-Plated.TXT`, `panel-NonPlated.TXT` and `panel.GM2`, but neither choice is stored in the PCB document, so the writer cannot make them the defaults. Q7, Q10, Q11 and Q12 keep their S-1585 passes. Still open: Q9 fails as written, and the coordinator decides whether a restart counts as Q8's "reopen".
  - Done on 2026-11-05 by the coordinator's decision, given by the maintainer's delegation: a restart counts as
    Q8's reopen, and Q9 is judged with the separate plated/non-plated drill files and the `V-Cut` Gerber on,
    because neither option is stored in the PCB document. Q9's "Expected" in `docs/evidence/altium-pcb.md` says
    so, with a dated note. Both observations of Q8 and both runs of Q9 stay recorded; Q7, Q8 and Q9 are as
    expected, so `pcbdoc.EMBEDDED_ARRAYS = True`. `fenolite panel --target altium` now writes the array for a
    `.PcbDoc` board with an unturned, unmirrored grid, naming the board by its path relative to the output
    folder; every other case is the flattened panel, and `--altium-panel embedded` is refused (`FEN-7001`).
    Limitation, in `H-A-PANEL-KIT`, `docs/evidence/altium-pcb.md` and the guide's panel prose: Altium rereads
    a changed child board only after it is restarted. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_q tests/unit/test_hypotheses_register.py -q`.
- [x] 3.4 (from c0173 8.3) Update the evidence labels to the measured levels, name the rows in the panel's `EVIDENCE`, and regenerate the matrix. Proof: `uv run python tools/gen_evidence_matrix.py`; `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_evidence_matrix_page.py -q`.
  - Blocker on 2026-11-05: It waits on tasks 7.1 to 7.4, and 2.4 and 7.4 stay open.
  - Status on 2026-11-05: 3.2 (old 2.4) is done; 3.3 (old 7.4) stays open on Q9, so no label moves.
  - Done on 2026-11-05: Q7 to Q9 were an agent run, which raises no level (the rule of S-1421 and S-1422),
    so the measured levels are the register's: `H-A-PANEL-RECORD` and `H-A-PANEL-LAYERKIND` `UNKNOWN`,
    `H-A-PANEL-KIT` `INFERRED`, each with the 2026-11-05 result. The panel's `EVIDENCE_EMBEDDED` names the
    three rows and is the evidence of an embedded reply (`fenolite panel`); the matrix regenerates unchanged.
- [ ] 3.5 (from c0215 7.4) The maintainer's K6 round on Altium Designer 24.5.2.23 (approved pending-run scope) (a test of the maintainer, in v0.6 by open question 6): record the run with `fenolite kit record`, set the levels of the rows it settles, and write the verdict per probe into `docs/evidence/altium-pour.md`. Proof: `uv run fenolite kit verify <kit> --json` exits 0; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  - Blocker on 2026-11-05: `kit verify` exits 5 in both agent runs (S-1572, S-1579). K6.2 and K6.7 fail M2 at P3 and P8, and K6.6 counts the dead-copper finding on `P5_NONET`. K6.8 has no value, because AD26 is not installed.

## 4. Edit sessions (c0241)

- [ ] 4.1 (from c0241 1.2) **Maintainer, in Altium Designer.** Build phase A with `FENOLITE_ALTIUM_PART_J=~/fenolite-altium-checks/session-7/J-edit uv run pytest tests/unit/backends/altium/test_part_j.py -k phase_a`, run J1 to J22 and send back the folder, the version, the date and the SHA-256 of each saved file. Record the report under "Reports" of `docs/evidence/altium-edit.md` in the form of the native acceptance inventory, register its source, and write what each case measured into the result of its rows. OPEN until Altium was run; nothing is marked `ALTIUM-VERIFIED` by it. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_j tests/unit/test_hypotheses_register.py -q`.
  - Blocker on 2026-11-05: J4 did not read whether the free tracks stayed. Six cases (J7, J9, J14, J18, J19, J21) used a scripted edit in place of the Properties panel, and the S-1582 redo through the panel was not possible.
- [ ] 4.2 (from c0241 4.2) **Maintainer, in Altium Designer.** Run J23 to J33 and give the report; record it as task 1.2 does and set the rows `H-A-EDIT-KIT` and `H-A-INTEG-*`. Set an operation's gate only when its case passes. OPEN until Altium was run. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_j tests/unit/test_hypotheses_register.py -q`.
  - Blocker on 2026-11-05: `remap_layer` and `set_rule` failed, J33 was not run, and J25 and J29–J31 were dropped.
- [ ] 4.3 (from c0241 6.2) Update the evidence labels of the rows `H-A-EDIT-*` and `H-A-INTEG-*` and the matrix. Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  - Blocker on 2026-11-05: Tasks 1.2 and 4.2 stay open, so no label moves.

## 5. Viewer comparisons (c0177, c0180, c0186)

- [ ] 5.1 (from c0177 2.4) The maintainer reviews the page on an Altium project of their own, against Altium Designer, through `fenolite view --serve`. The review covers the text size, the shapes of power ports, ports and sheet entries, and the title block. Proof: the record under this task.
  - Blocker on 2026-11-05: The coordinator accepts the public project `PCB-PiDP11IOExpander` in place of the maintainer's own, provided the comparison criteria pass. They do not: the title block's special strings stay unresolved (`=ProjectTitle`, `=ProjectRev`, `*`), and ports and sheet entries are not exercised (the project has one sheet).
- [ ] 5.2 (from c0180 2.4) The maintainer reviews a drawing of their own against Altium (round F0.5 of Part F). Proof: the record under this task.
  - Blocker on 2026-11-05: The coordinator accepts the public project `PCB-PiDP11IOExpander` in place of the maintainer's own drawing, provided the comparison criteria pass. They do not: the assembly top view lacks silkscreen and hatching, the bottom view is empty, the right view's height reads `43.2` against `11.43mm`, and the BOM has fewer columns and no variant applied.
- [ ] 5.3 (from c0186 2.2) The maintainer compares a variant of their own with Altium. Proof: the record under this task.
  - Blocker on 2026-11-05: The coordinator accepts the public project `PCB-PiDP11IOExpander` in place of the maintainer's own, provided the comparison criteria pass. The not-fitted set matches (A0, A1, A2, J2, R2, R3), but Altium's sheet was not switched to the variant, so the drawn marks were not compared.

## 6. Kit script (c0385)

- [x] 6.1 (from c0385 5.2) The kit script creates `results/script.log`: `Rewrite` when the file is missing, `Append`
  otherwise. Rerun group K2 in Altium and raise `H-A-KIT-SCRIPT` again on the new run.
  - Blocker on 2026-11-05: in run `2026-11-05-e28d0bb1` (S-1590, AD 24.5.2.23) the script's `Append` on the missing
    log raised `EInOutError` "The specified file was not found" and the script stopped; the row is `INFERRED`.
  - 2026-11-05, script fixed: `LogLine` asks `FileExists` on the log's path and calls `Rewrite` when it is
    false and `Append` when it is true, with no `Try` around them (`FileExists`: S-1591; design, "Task 6.1").
    Proof: `uv run pytest tests/unit/verify/kit/test_script.py -q`. Left open for the K2 rerun in Altium and
    the new `H-A-KIT-SCRIPT` result.
  - Done on 2026-11-05 (S-1603, AD 24.5.2.23, agent run on the maintainer's delegation): group K2 rerun on the
    kit `cb286eb0…` (script `843f93f7…`), started with no `results/script.log`. The script created the log and
    appended `K2.1 done` to `K2.5 done`; `kit verify` exits 0 with K2.1 to K2.5 passing. Recorded as
    `docs/evidence/altium-kit/2026-11-05-c91de60a.json`; `H-A-KIT-SCRIPT` is
    `ALTIUM-VERIFIED(kit; AD 24.5; 2026-11-05; 2026-11-05-c91de60a)`.
