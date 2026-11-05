## 1. Attribution

- [ ] 1.1 Attribute the differences of `kicad-demo-10-0-6-pcb-14`, `kicad-demo-9-0-9-1-pcb-01`, `-02` and
  `-05` (Fenolite, KiCad or input), with the level, object and evidence of each. Proof: a dated note per row
  in `docs/evidence/fidelity.md`; `uv run pytest tests/unit/test_fidelity_docs.py -q`.
- [ ] 1.2 For each Fenolite attribution, open or name the change that fixes it; for each KiCad or input
  attribution, record the row in `accepted.toml` with its counts and reason. Proof:
  `uv run pytest tests/kicad/fidelity -rA` in the kicad-10 CI job.

## 2. Refused and skipped rows

- [ ] 2.1 Explain the `FEN-5001` and `FEN-3004` refusals of the census (10.0.6 pcb-01, 05, 07, 09, 11, 17)
  and either fix them in their own changes or document them as intended refusals. Proof: a dated note per
  row in `docs/evidence/fidelity.md`.
- [ ] 2.2 Measure the two heavy rows (10.0.6 pcb-06 and pcb-18) in a CI job or document why they stay skipped.
  Proof: the CI job's record or the note.

## 3. Validation

- [ ] 3.1 Run `make check-fast`, publish to a working branch and confirm the required CI jobs on the exact
  commit. Proof: the required jobs green on the pushed head.
