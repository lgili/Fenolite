## 0. Entry check

- [ ] 0.1 Read `openspec list` and the changes and living specs this change builds on, and record under this task, with the date and the base commit:
  - whether c0246, c0259, c0260, c0261, c0262 and c0264 are archived; take from them the range spelling, the record keys, the pin types and groups, the family table and the manufacturer-land parameters, the rule codes, the review command and the device folder writer, and adapt the names of this change to them;
  - whether the MCP server change (c0195, c0196) is archived, and how its tool list is generated, so that `library propose` is exposed and open question 1 can be applied;
  - the page count and budget rules of the living "Guide pages" and "Page budgets and writing rules";
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0265-datasheet-proposals --strict`; `make check-fast`.

## 1. Proposal file

- [ ] 1.1 Add `src/fenolite/library/proposals/schema.py`: `parse_proposal`, the closed keys, the geometry refusal, citations, doubts, grids and the canonical writer. Author `tests/data/proposals/` (an SOIC-8 proposal, a grid proposal pair, and a one-page PDF written for Fenolite, each with the authored-for-Fenolite line; the illustrative part and datasheet are invented). Scenarios "An authored proposal is read", "Coordinates refused", "A doubt is reported". Register `H-L-PROPOSAL` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/library/proposals/test_parse.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 2. Checks

- [ ] 2.1 Add `proposals/checks.py`: binding to the datasheet and the self-checks of design decision 5 (scenarios "Another datasheet", "One pin missing", "Ball outside the grid", "Exposed pad named but not declared"). Proof: `uv run pytest tests/unit/library/proposals/test_checks.py -q`.
- [ ] 2.2 Add the two-proposal rules: `proposal.second-required`, `proposal.not-independent` and `proposal.disagree` (scenarios "One proposal for a grid", "Shifted rows caught"). Document the threshold of 100 pins as `INFERRED` in `docs/datasheet-proposals.md`. Proof: `uv run pytest tests/unit/library/proposals/test_agreement.py -q`.

## 3. Conversion, drawing and the command

- [ ] 3.1 Add `proposals/convert.py`: records with `[origin]`, drawing with c0260 and c0261, and c0262's rules (scenarios "The device folder", "Same proposal, same bytes", "Span smaller than the land needs"). Proof: `uv run pytest tests/unit/library/proposals/test_convert.py -q`.
- [ ] 3.2 Add `library propose` to `cli/cmd_library.py`: the skeleton form, the proposal form, `--out` through c0264's target rule, re-proposal, the result schema, and the `proposal.*` codes in `fenolite.library.codes` and `explain.toml` (scenarios "Skeleton of the authored datasheet", "Corrected proposal over a reviewed device", "Result fields", "Consistency suite covers propose", "Import graph of proposals"). Proof: `uv run pytest tests/unit/cli/test_library_propose.py tests/consistency tests/unit/test_import_graph.py -q`.
- [ ] 3.3 Add `review_gate` and call it from c0262's `library review --accept` (scenario "Acceptance with an open doubt"). Proof: `uv run pytest tests/unit/library/proposals/test_review_gate.py tests/unit/cli/test_library_review.py -q`.

## 4. Closing

- [ ] 4.1 Agent guide: write `src/fenolite/agent/skill/references/datasheets.md` with the tested lines of `library propose`, add it to the start page index, then run `uv run python tools/gen_agent_guide.py` (scenarios "The page through the command line", "The page is indexed and within budget"). Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 4.2 Docs: `docs/datasheet-proposals.md` (the pipeline, the schema with every key, the checks, dense packages, the review gate, why no model runs in Fenolite), `library propose` in `docs/cli-contract.md`, links from `docs/index.md` and `docs/library-import.md`. Proof: `uv run pytest tests/unit -k docs -q`.
- [ ] 4.3 Residue and evidence: every test file authored for Fenolite, no real datasheet or manufacturer document committed, the evidence matrix regenerated. Proof: `make residue`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 4.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 4.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
