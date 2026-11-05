## 1. Attribution

- [x] 1.1 Attribute the differences of `kicad-demo-10-0-6-pcb-14`, `kicad-demo-9-0-9-1-pcb-01`, `-02` and
  `-05` (Fenolite, KiCad or input), with the level, object and evidence of each. Proof: a dated note per row
  in `docs/evidence/fidelity.md`; `uv run pytest tests/unit/test_fidelity_docs.py -q`.
  2026-11-05: done. `design.md` tables and `docs/evidence/fidelity.md` "Attribution — 2026-11-05";
  `test_fidelity_docs.py` 3 passed.
- [ ] 1.2 For each Fenolite attribution, open or name the change that fixes it; for each KiCad or input
  attribution, record the row in `accepted.toml` with its counts and reason. Proof:
  `uv run pytest tests/kicad/fidelity -rA` in the kicad-10 CI job.
  2026-11-05: open for CI. Fenolite causes: pcb-14 and 9-05 fixed here (1.3, 1.4); 9-02 owned by c0384; the two
  9-01 causes need a change id from the coordinator. Local 10.0.6: 13 passed, 12 skipped in 221.76 s.

- [x] 1.3 Pair equal strict-matching keys as a multiset of their compared fields (pcb-14: coincident tracks
  of widths 0.3 and 0.29997 mm paired in file order). Proof:
  `uv run pytest tests/unit/checks/equivalence/test_strict.py -q`.
  2026-11-05: done. 10 passed (the new test failed on the unfixed source); pcb-14 now all levels equal.
- [x] 1.4 Keep a root Edge.Cuts `gr_rect` outline as an explicit rectangle through import and build (9.0.9.1
  pcb-05: one `gr_rect` became four `gr_line`s). Proof:
  `uv run pytest tests/unit/importer/test_explicit_edge_ownership.py -q`.
  2026-11-05: done. 17 passed (targets 9 and 10); 9.0.9.1 pcb-05 now all levels equal.

## 2. Refused and skipped rows

- [x] 2.1 Explain the `FEN-5001` and `FEN-3004` refusals of the census (10.0.6 pcb-01, 05, 07, 09, 11, 17)
  and either fix them in their own changes or document them as intended refusals. Proof: a dated note per
  row in `docs/evidence/fidelity.md`.
  2026-11-05: done. All six are intended refusals (input or corpus), no code fix; notes in
  `fidelity.md` and `design.md`.
- [x] 2.2 Measure the two heavy rows (10.0.6 pcb-06 and pcb-18) in a CI job or document why they stay skipped.
  Proof: the CI job's record or the note.
  2026-11-05: documented, not measured in CI. Local run with `FENOLITE_HEAVY=1`: pcb-06 refused
  `FEN-7001` (lossy: dimension styles, Dwgs.User drawings, placement rule areas) after 268.8 s; pcb-18 refused
  `FEN-3004` (undeclared worksheet) after 35.0 s. Both stay pending; a CI run would only repeat the refusals.

## 3. Validation

- [ ] 3.1 Run `make check-fast`, publish to a working branch and confirm the required CI jobs on the exact
  commit. Proof: the required jobs green on the pushed head.
