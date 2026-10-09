## 0. Cause

- [x] 0.1 Measure the seven findings of `altium-third-party-pcbdoc-03`: the pad and track records, the model's geometry, the rule in force, and where the 8 to 9 nm come from (conversion of coordinates, end caps, polygonisation, pad size, rule, or Altium's comparison). Write it into the design. Proof: `openspec validate c0152-clearance-rounding --strict --no-interactive` passes.
  - **2026-10-08.** The document's integers put the straight segment 49 996.5 units from the pad's edge (3.5 units, 8.89 nm inside 5 mil); the model reads 126 991 nm against an exact 126 991.11. No rounding of Fenolite's takes part; Altium's comparison passes at least 3.5 units. Validation: valid.
  - 2026-10-09: c0124 is archived. The MODIFIED "Clearance rules of a PCB document" of this change's `altium-verification` delta was written on the text before c0124 and dropped its scenario "Planes of an imported board"; it now carries c0124's edits of the living text (the rules source takes no track or arc out; what an internal plane layer is, and the number of objects left out in the reason of `left_out`; that scenario) with this change's own. `openspec validate --all --strict --no-interactive` reports no error.

## 1. The tolerance

- [x] 1.1 Add `ALTIUM_PASSED_UNITS`, `ALTIUM_PASSED_NM` and `CLEARANCE_SLACK_NM` to `backends/altium/backend.py`, lower the rules by the last, and add the fact row to `docs/formats/altium/import.md`. Proof: `uv run pytest tests/unit/backends/altium/test_frame.py tests/unit/test_format_facts.py tests/unit/test_provenance.py -q`; `uv run pyright src`.
  - **2026-10-08.** 9 nm. `checks/` is not touched; KiCad judging stays strict at the nanometre.
- [x] 1.2 Tests on authored records and on the model: a pad of an odd size and a track exactly at the observed tolerance (no finding) and one file unit nearer (one finding); two tracks 3 and 4 units inside; 9 and 10 nm inside on the model. Proof: `uv run pytest tests/unit/backends/altium/adapter/test_rules.py -q`; `uv run pytest tests/unit/checks/test_copper.py -k strict_comparison -q`.
  - **2026-10-08.** The 21 tests of the file pass; the KiCad test passes unchanged.

## 2. Measurement

- [x] 2.1 The corpus test of `-03` and the counts of the eight public documents; update `docs/evidence/altium-roundtrip.md` and `docs/evidence/altium-pcb.md` (Part D). Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_copper.py -k "not parity" -q`.
  - **2026-10-08.** The class goes from 25 to 9 findings (1 on `-01`, 0 on `-03`, 8 on `-08`), all 10 to 20 nm short. Nothing else of `test_copper` changes.

## 3. Closing

- [x] 3.1 Run tests/residue and the manifest test. Proof: after `git add -A`, `uv run pytest tests/residue tests/corpus/test_manifest.py tests/unit/test_evidence_matrix_page.py -q`.
- [x] 3.2 Update evidence labels: the row on `import.md`, the pages of Part D, `docs/roadmap.md`, `openspec/README.md` and `LEGAL-ANNEX.md`; regenerate the generated pages. Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run python tools/gen_schemas.py --check`; `uv run python tools/gen_token_docs.py --check`.
- [x] 3.3 Update `CHANGELOG.md` under `[Unreleased]`; run the fast checks. Proof: `make check-fast`.
- [x] 3.4 Run the full suite once on the rebased branch. Proof: `make check` passes.
  - **2026-10-08.** Not run here: the coordinator runs it once at the merge.
  - **2026-10-08**, on the release branch (`release-0.4.0`, `32a19b3` and the settlement commits of c0154): `make check` exit 0 (ruff check all passed, 1772 files already formatted, pyright 0 errors, residue 0 hits with 11 waivers and the private gate skipped, `13828 passed, 2374 skipped in 1243.06s` on Python 3.11.15, 4 workers) (c0154, task 4.3). CI run https://github.com/lgili/Fenolite/actions/runs/37836186018 of `32a19b3` passed every job; the change passed CI run 37774909847 on its branch.
