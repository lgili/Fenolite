## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`cli-contract`, `fenolite-component-catalog`, `visual-diff`, `verification-evidence`, `package-layering`), and record under this task, with the date and the base commit:
  - whether c0259, c0260 and c0261 are archived; the spellings of c0259's `review` key, deprecation key and source register; c0260's family names and terminal count; c0261's action dispatch. Align the rule table and the scenarios with them;
  - whether c0184's sheet comparison and c0179's library scenes are on `dev` (the sheet overlay reuses them);
  - whether c0195's MCP tool list has an exclusion mechanism;
  - the maintainer's answers to the open questions of `design.md`, first of all question 1 (the level a review gives).

  Proof: `openspec validate c0262-library-rules --strict`; `make check-fast`.

  Entry recorded 2026-11-01, base `8d74a798372c3a8c96b96daa97726223e30411ab`:
  c0259/c0260/c0261 are implemented but not archived. c0259 spells reviews `[[reviewed_by]]`
  (`who,date,version,digest,evidence,sheet`), deprecation `[deprecated]`, and sources use S ids;
  c0279 repository source D ids remain separate. c0260 families are chip, molded, gullwing,
  nolead, grid, to, dip, header and connector; numbered copper pads count terminals (EP included
  where specified). c0261 dispatches on the first `path` word; c0279 verbs remain available.
  c0179 scenes and c0184 board/sheet comparison are present. MCP has per-command argument
  exclusions; action words additionally need runtime rejection. Full gate is root-owned, so 0.1
  stays open until its complete proof runs.

## 1. Facts and test records

- [x] 1.1 Write `docs/formats/library/rules.md`: the constant `T`, the pin-1 centroid convention, the grid tiers, the ball row-letter rule with its public source registered in `docs/evidence/sources.md`, each `INFERRED` and Fenolite-authored. Proof: `make residue`; `uv run pytest tests/unit -k "sources or facts_page" -q`.
- [x] 1.2 Author `tests/data/library_rules/good/` (a package, a pin table and a device per family c0260 ships, the illustrative regulator and a waived connector) and `tests/data/library_rules/bad/` (static bad records and isolated authored model/state mutations for rules requiring native geometry, comparison or an accepted review), each with the authored-for-Fenolite line. Proof: `make residue`; `uv run pytest tests/unit/library/test_fixtures.py -q`.

## 2. Rules

- [x] 2.1 Add `library/rules.py` with the footprint rules (`pad-count`, `pin1-location`, `pin1-marker`, `courtyard-missing`, `courtyard-containment`, `pad-clearance`) and their scenarios. Proof: `uv run pytest tests/unit/library/test_rules.py -k footprint -q`.
- [x] 2.2 Add the package rules (`body-span`, `depopulated`, `land-mismatch`, `land-calculator-delta`) and their scenarios. Proof: `uv run pytest tests/unit/library/test_rules.py -k package -q`.
- [x] 2.3 Add the symbol, filter and record rules (`pin-grid`, `hidden-power`, `duplicate-pin`, `pin-group-type`, `footprint-filter-miss`, `footprint-filter-broad`, `source-unknown`, `evidence-claim`), waivers and effective evidence. Register `H-G-LIBRARY-RULES`. Proof: `uv run pytest tests/unit/library/test_rules.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [x] 2.4 Run the rules on every shipped catalog definition and record; fix a definition or waive the code with a reason, so that the shipped data has no error and no unexplained warning. Proof: `uv run pytest tests/unit/library/test_rules.py -k shipped -q`.
- [x] 2.5 Add every `library.*` code to `cli/data/explain.toml`. Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -q`.

## 3. Command, sheets and comparison

- [x] 3.1 Add the action `library check` with targets, `--fail-on`, `--rules`, `--skip` and the result (scenarios "Mixed folder", "Clean records", "Findings exit", "Warnings as failures"). Proof: `uv run pytest tests/unit/cli/test_library_check.py -q`.
- [x] 3.2 Add `view/review_sheet.py` and `--sheets` (scenarios "Sheet of a device", "Dry run writes nothing"). Proof: `uv run pytest tests/unit/view/test_review_sheet.py tests/unit/cli/test_library_check.py -k sheets -q`; `uv run pytest tests/unit/test_import_graph.py -q`.
- [x] 3.3 Add `--compare` with pairing, field paths, `interface-changed`, `removed` and the reused visual-diff overlay (scenarios "Generator change", "Pins renumbered under one id"). Proof: `uv run pytest tests/unit/cli/test_library_check.py -k compare -q`.

## 4. Review record

- [x] 4.1 Add `library/review.py` (digest, review table, staleness) and register `H-G-LIBRARY-REVIEW` (scenarios "Edit after review", "Reformatting is not an edit"). Proof: `uv run pytest tests/unit/library/test_review.py -q`.
- [x] 4.2 Add the action `library review` with state, `--accept`, `--revoke` and the preconditions (scenarios "Accept a clean device", "Revoke", "Sheet changed after it was opened", "Error finding blocks the review", "State only", "Reviewer without accept"). Proof: `uv run pytest tests/unit/cli/test_library_review.py -q`.
- [x] 4.3 Exclude `review --accept` and `--revoke` from the MCP tool list (scenario "Not an MCP tool"). Proof: `uv run pytest tests/unit/mcp -q`.

## 5. Closing

- [x] 5.1 Docs: `docs/library-rules.md` (every rule with a picture from the bad records, waivers, effective evidence, the review), `docs/library-ci.md` (decision 8), `library check` and `library review` in `docs/cli-contract.md`, and links from `docs/index.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`; `uv run pytest tests/consistency -q`.
- [ ] 5.2 CI: add `fenolite library check` of the shipped records to the unit job, with the sheets uploaded as an artefact. Proof: the unit job green on the pushed head, with the artefact present.
- [x] 5.3 Agent guide: add tested lines to the focused `library-review.md` page for `fenolite library check` and for `library review` as a human step, then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [x] 5.4 Evidence: the hypotheses are registered and the evidence matrix is regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 5.5 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.6 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.

Local validation record, 2026-11-01: proof logs are in the shared scratch validation folder for this
change. The combined focused suite passed 153 tests (one official MCP SDK oracle skipped because the
oracles extra is absent); the combined guide/import/register/explain suite passed 190 tests. The
docs/sources/facts/changelog selection passed 169 tests (one SDK oracle skipped). Additional focused
regressions cover metadata normalization and sheet-path collisions. All named rule, sheet, CLI and
review proof cases are included in those runs. `make residue` reported zero hits. Strict OpenSpec
validation passed without warnings; generated guide and evidence matrix checks passed.

The shipped smoke check wrote 159 standalone sheets, an index and a manifest, with zero error or
warning findings. Its 150 informational findings are matched explicit code/reason compatibility
waivers in 80 records. A separate digest proof confirms all 80 metadata-edited records retain equal
generated outputs and licences; PATCH versions and the catalog index were updated. S-0988 is reused
for the public row-letter fact, while the additional omitted letters remain explicitly INFERRED.

0.1 and 5.6 remain open because the root coordinator owns the complete local gate, publication and
exact-commit CI. 5.2's workflow configuration is implemented and its local sheet command passed, but
its required green pushed-head job and uploaded artefact are not claimed here. 5.1 passed: the consistency suite reported 662 passed and 41 intentionally skipped mutating
CLI cases. Final focused regressions reported 26 passed, including staged dependency edits, namespace
filename collisions, authored-suffix edits and the existing scoped evidence grammar.

The final metadata regression also binds authored properties and source maps whose keys happen to
be named evidence/review, and keeps arbitrary authored suffix text. Its focused proof passed 15 tests
and pyright reported zero errors after the broader suites; no author text is normalized out of a digest.
