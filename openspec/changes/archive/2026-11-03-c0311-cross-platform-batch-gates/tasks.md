## 0. Entry

- [x] 0.1 Record the exact failing CI baseline, existing command contracts and decisions. Proof: `npx -y @fission-ai/openspec validate c0311-cross-platform-batch-gates --strict`.
  2026-11-01: base `8d74a798`, run `41187585440`; decisions recorded in design.md; strict validation passed without warnings.

## 1. Portable paths and bytes

- [x] 1.1 Refuse native rooted output folders for library generation. Proof: `uv run pytest tests/unit/cli/test_library_generate.py -q`.
  2026-11-01: 14 passed; Windows-native rooted-path case remains covered by the required Windows CI job.
- [x] 1.2 Make library Git checkouts independent of global newline configuration and exercise both checkout/replay fixtures with conversion enabled. Proof: `uv run pytest tests/unit/cli/test_get.py tests/unit/library/test_replay.py -q`.
  2026-11-01: reproduced two byte-fidelity failures with autocrlf enabled on Linux; after the fix, all 18 focused tests passed.
- [x] 1.3 Correct binary JSON, cache-path and quoted-command assertions without relaxing byte equality. Proof: `uv run pytest tests/unit/dsl/test_describe.py tests/unit/cli/test_get_cache.py tests/unit/view/test_check_overlay.py -q`.
  2026-11-01: 25 passed; canonical payload equality is still byte-exact.

## 2. Container and closing

- [x] 2.1 Align KiCad 10 temporary and artifact paths inside its container. Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`.
  2026-11-01: 46 passed; actual KiCad 10 execution remains a CI proof.
- [x] 2.2 Add the Unreleased entry and run the local fast gate. Proof: `make check-fast`.
  2026-11-01: complete local gate passed: 17720 tests passed, 53 skipped; lint, generated files, formatting, types and residue passed. Log: external validation folder `c0311/check-fast.log`.
  Integrated follow-up proof 2026-11-01 on `997955c6982eb59a4b0501fa421898af391a1982`:
  17,880 passed, 53 skipped, with all fast-gate stages successful. This includes the measured
  heavy-census table follow-up and the newer integration branch's portable checkout tests.
- [x] 2.3 Publish this working branch and inspect unit, KiCad and DCO jobs on its exact commit. Proof: required CI jobs green on the pushed head. Keep open until observed.
  Follow-up 2026-11-01: run `41305101514` on `b8b24842` has successful Windows and other jobs, but KiCad 10 failed on the two missing census rows. This is not a green run; the task remains open for the new exact commit.

## 3. Heavy import census follow-up

- [x] 3.1 Inspect exact CI logs and pin the measured aggregate rows to their source, commit and version. Proof: job `124843785751` of run `41305101514` checks out `b8b24842c1b792a0fcb37a6a7e5ca0270b90efd6`; its two `IMPORT_CENSUS` records report exit 0 and equivalent=true before only the missing-row assertion fails.
- [x] 3.2 Add the measured rows 06/18 to `docs/evidence/import-corpus.md` and a unit table-coverage preflight. Keep the existing heavy imports and exact-equivalence assertions unchanged. Proof: `uv run pytest tests/unit/test_import_census_record.py -q`; replay the captured aggregate records against the completed table.
- [x] 3.3 Run focused documentation/census tests, static/generated checks, residue and strict validation. Proof: `uv run pytest tests/unit/test_import_census_record.py tests/unit/test_evidence_register.py tests/unit/test_format_facts.py tests/unit/test_legal_docs.py tests/unit/test_ci_workflow.py -q`; Ruff, formatting, source types, residue, generated checks and `openspec validate c0311-cross-platform-batch-gates --strict`. Do not claim a full local or new exact-commit CI pass.

Follow-up measurements (2026-11-01): exact CI job logs identify both imports as exit 0 and equivalent=true; the table and all displayed counts/seconds replay the emitted JSON exactly. The new preflight first failed with missing rows 06/18, then passed after recording them. Focused census/evidence/source/legal/workflow proof: 84 passed. Neither the corpus test nor the workflow was changed; no heavy test was skipped or rerun locally, and no external CAD payload was added.
Final follow-up proof: the census/hypothesis/evidence rerun passed 44 tests; Ruff, formatting, source types (0 errors/warnings), residue (0 hits), generated guide/schema/evidence checks and strict OpenSpec validation passed. Full local and renewed exact-commit CI gates were not run here; task 2.3 remains open.


## Scoped implementation closure — 2026-11-03

The maintainer clarified that problematic geometry was already outside this
closure CI batch before the run. Close only this specification’s implementation
on tested source 985f59a1d01a612b2eac0219243199896c24075a and reviewed
archival documentation. Run 41708879698 remains FAILURE: the27known c0332
geometry failures are DEFERRED_NOT_PASSED, not passed tests. KiCad9 and all
five unit jobs succeeded. The relevant KiCad10 module results are inferred
from complete unfiltered collection and the exhaustive -ra non-pass report.
Explicitly contracted unsupported-target skips remain skips; no nominal
PASSED line or green KiCad10 job is claimed.

`scoped-ci-985f59a1.json` binds the exact tests, explicit KiCad9 positive
lines, complete log hashes, reused fast proof and existing scoped records.
The isolated runtime/tests/tools/configuration remain byte-identical to985;
this does not validate later CAC runtime, close c0355 or replace subsequent
integration CI. Existing authored/native/default-map proofs and limitations
remain intact. No suite, native CAD test or CI rerun was started for archive.

Entry refresh: previously implemented prerequisites are now archived in the
required order: no literal prior archive requirement. Existing APIs and reviewed normative
unions were checked against the current living text; no runtime change or
external publication was needed. Contracted native9/10 unsupported-target
skips remain skips and are explicitly retained in the portable receipt.

The existing viewer job126171394431 passed bundle freshness and104visual
cases on source985. All eleven PNG references exactly match the prior
reviewed/published/source985 maps, preserving the dated delegated image
inspection without inventing a new approval from automation. Unit, viewer
and applicable MCP/DCO jobs are recorded individually in the portable proof.
No bundle, PNG, runtime, assertion or measurement was regenerated here.
The missing three native action CI cases ofc0303 and six real variant views
ofc0305 remain separate open requirements; neither is closed by this record.

The earlier heavy census measurements remain attributed to b8b24842 and their
original CI records. Required heavy assertions and byte equality are not
changed or skipped here; current geometry failures are deferred, not passed.
