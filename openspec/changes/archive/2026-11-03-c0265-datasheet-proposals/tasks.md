## 0. Entry check

- [x] 0.1 Read `openspec list` and the changes and living specs this change builds on, and record under this task, with the date and the base commit:
  - whether c0246, c0259, c0260, c0261, c0262 and c0264 are archived; take from them the range spelling, the record keys, the pin types and groups, the family table and the manufacturer-land parameters, the rule codes, the review command and the device folder writer, and adapt the names of this change to them;
  - whether the MCP server change (c0195, c0196) is archived, and how its tool list is generated, so that `library propose` is exposed and open question 1 can be applied;
  - the page count and budget rules of the living "Guide pages" and "Page budgets and writing rules";
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0265-datasheet-proposals --strict`; `make check-fast`.

  Entry 2026-11-01: base prerequisite merge `7a2f6746485d8d118965ac75d6b5821efb64b75e`.
  c0246/c0259/c0260/c0261/c0262/c0264 are implemented and unarchived. The common header uses reviewed_by;
  import records retain external native definitions, normalized bodies and ImportOrigin. c0260 has
  nine families and exact LengthRange values. Pin types/groups use catalog.pins and model.library.
  c0195/c0196 are implemented and unarchived. MCP derives one library tool from argparse, with review
  action rejected by schema and runtime. The guide had 13 written tool pages before this change,
  11 practice pages and seven generated pages; new
  pages keep the existing 12,000-byte/250-line and 400,000-byte folder budgets. Recommended decisions
  and the H-G namespace alignment are recorded in design.md. The root owns the complete local gate,
  so 0.1 remains open despite strict validation passing.

  Entry refresh 2026-11-02, integration base `697cdf02b39c570b7827bd2b7b5419dfcf6bdea6`:
  c0246/c0259/c0260/c0261/c0262/c0264 remain active and implemented. Public range
  input is `Range`/`between(a,b,nominal=...)`; record pins use `type`/`group`, while model
  `PinRow` calls the electrical type `etype`. c0260's nine families and manufacturer-land
  parameters, c0262's rules/review, and c0264's canonical record sealing are present.
  `ProposalOrigin` stays distinct from `ImportOrigin`; current human review and current
  output seals remain necessary for shipping proposals. c0195/c0196 remain active; MCP
  derives the shared library tool from argparse and excludes review in schema and runtime,
  while file-based propose stays reachable. The living guide still says 22 written pages,
  750 generated lines and 300000 folder bytes. Active c0275 raises the latter budgets to
  800 lines/400000 bytes; the implemented guide has 19 tool, 11 practice and four feature
  pages, eight generated references (six command detail pages), and the start page. Written
  pages retain 250 lines/12000 bytes and the start page has the existing 200-line bound.
  All four recommendations are accepted: human review outside MCP, file proposals rather
  than inline proposals, explicit CC0 proposals still requiring review, and cited land
  parameters allowed. These choices confer no new source terms or automatic approval.

  Available proof: `openspec validate c0265-datasheet-proposals --strict` passes without warnings
  (OpenSpec 1.16.0).
  The literal `make check-fast` is not run by this worker and has no applicable passing
  serialized receipt yet. Task 0.1 remains unchecked for that actual proof; independent
  CI, native/manual and release criteria are unchanged.

  Entry proof completed 2026-11-02 on `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`: root
  ran the serialized `make check-fast` from 09:45:03 to 10:17:02 UTC, exit 0
  (19564 passed, 55 skipped; JUnit records zero failures/errors). Fresh OpenSpec
  1.16.0 strict validation of this change also passes without warnings. The
  `a85f7846` entry review was checked against this source: dependencies remain
  active, no new archival requires rebasing a delta, and the named APIs, accepted
  decisions and current dispatcher/record contracts still apply.
  This dated proof supersedes the earlier missing-fast-gate blocker only.
  Independent CI, native/manual, corpus, external-library and release criteria
  remain unchanged. The source-bound receipt, log and JUnit hashes are recorded
  in [the integration validation record](../c0319-integration-repairs/validation.md).

## 1. Proposal file

- [x] 1.1 Add `src/fenolite/library/proposals/schema.py`: `parse_proposal`, the closed keys, the geometry refusal, citations, doubts, grids and the canonical writer. Author `tests/data/proposals/` (an SOIC-8 proposal, a grid proposal pair, and a one-page PDF written for Fenolite, each with the authored-for-Fenolite line; the illustrative part and datasheet are invented). Scenarios "An authored proposal is read", "Coordinates refused", "A doubt is reported". Register `H-G-PROPOSAL` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/library/proposals/test_parse.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 2. Checks

- [x] 2.1 Add `proposals/checks.py`: binding to the datasheet and the self-checks of design decision 5 (scenarios "Another datasheet", "One pin missing", "Ball outside the grid", "Exposed pad named but not declared"). Proof: `uv run pytest tests/unit/library/proposals/test_checks.py -q`.
- [x] 2.2 Add the two-proposal rules: `proposal.second-required`, `proposal.not-independent` and `proposal.disagree` (scenarios "One proposal for a grid", "Shifted rows caught"). Document the threshold of 100 pins as `INFERRED` in `docs/datasheet-proposals.md`. Proof: `uv run pytest tests/unit/library/proposals/test_agreement.py -q`.

## 3. Conversion, drawing and the command

- [x] 3.1 Add `proposals/convert.py`: records with `[origin]`, drawing with c0260 and c0261, and c0262's rules (scenarios "The device folder", "Same proposal, same bytes", "Span smaller than the land needs"). Proof: `uv run pytest tests/unit/library/proposals/test_convert.py -q`.
- [x] 3.2 Add `library propose` to `cli/cmd_library.py`: the skeleton form, the proposal form, `--out` through c0264's target rule, re-proposal, the result schema, and the `proposal.*` codes in `fenolite.library.codes` and `explain.toml` (scenarios "Skeleton of the authored datasheet", "Corrected proposal over a reviewed device", "Result fields", "Consistency suite covers propose", "Import graph of proposals"). Proof: `uv run pytest tests/unit/cli/test_library_propose.py tests/consistency tests/unit/test_import_graph.py -q`.
- [x] 3.3 Add `review_gate` and call it from c0262's `library review --accept` (scenario "Acceptance with an open doubt"). Proof: `uv run pytest tests/unit/library/proposals/test_review_gate.py tests/unit/cli/test_library_review.py -q`.

## 4. Closing

- [x] 4.1 Agent guide: write `src/fenolite/agent/skill/references/datasheets.md` with the tested lines of `library propose`, add it to the start page index, then run `uv run python tools/gen_agent_guide.py` (scenarios "The page through the command line", "The page is indexed and within budget"). Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [x] 4.2 Docs: `docs/datasheet-proposals.md` (the pipeline, the schema with every key, the checks, dense packages, the review gate, why no model runs in Fenolite), `library propose` in `docs/cli-contract.md`, links from `docs/index.md` and `docs/library-import.md`. Proof: `uv run pytest tests/unit -k docs -q`.
- [x] 4.3 Residue and evidence: every test file authored for Fenolite, no real datasheet or manufacturer document committed, the evidence matrix regenerated. Proof: `make residue`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 4.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [x] 4.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.

Proof 2026-11-01: combined proposal/rule/importer/record/CLI/MCP compatibility: 234 passed;
consistency: 727 passed, 41 intentional mutating skips; guide/residue tests: 120 passed, five corpus
skips; docs/changelog selection: 69 passed, one SDK-oracle skip. Final review-staleness regressions:
20 passed. Ruff, formatting, Pyright src, residue and both generated-file checks pass. The authored
PDF independently reports exactly one page. Strict OpenSpec validation passes without warnings.
Tasks 0.1 and 4.5 remain open because the integration owner runs the complete local gate and checks
the required CI jobs on the exact published commit; this worktree was neither pushed nor archived.


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

Proposal review stays a real human gate for future proposed records. This
change does not require publishing a server/plugin or a future proposal.
