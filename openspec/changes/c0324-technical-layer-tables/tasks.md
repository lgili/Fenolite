## 0. Contract

- [x] 0.1 Record the explicit API, existing model carrier, strict boundaries and
  evidence limits before implementation.
  Proof: `npx -y @fission-ai/openspec validate c0324-technical-layer-tables --strict`.
  Passed 2026-11-02: strict entry validation is valid without warnings.

## 1. Representation and exact build

- [x] 1.1 Add and validate the optional DSL selection through existing model
  layer rows. Honor it in a fresh build and refuse references to missing layers.
  Proof: `uv run pytest tests/unit/dsl/test_technical_layers.py tests/unit/lens/test_technical_layers.py tests/unit/backends/kicad/test_layer_undeclared.py -q`.
  Passed 2026-11-02: 23 cases, plus 64 layering contracts in the final 87-case
  group. Both target majors retain the exact selected table and independent
  User.n aliases; another build is byte-stable. Unknown/duplicate selections and
  missing drawing/field/pad/image references refuse, including allow-lossy images.
- [x] 1.2 Emit supported shorter source tables and retain unrelated refusals.
  Prove the authored missing-Eco import-copy/build table is exact and repeatable.
  Proof: `uv run pytest tests/unit/importer/test_technical_layers.py tests/unit/importer/test_unexpressed_c0281.py tests/unit/importer/test_outline_width.py tests/unit/checks/equivalence/test_c0281_levels.py -q`.
  Passed 2026-11-02: 19 cases. Strict authored import-copy and explicit builds
  preserve the short table on targets 9/10; repeated imports agree. The authored
  project is equal at all nine levels with no accepted differences. Unknown
  names, User.n gaps, absent Edge.Cuts and mixed widths remain strict refusals.

## 2. Teaching and regressions

- [x] 2.1 Add a tested focused guide page and public DSL/import documentation,
  one changelog entry, and regenerate the guide.
  Proof: `uv run pytest tests/unit/agent/test_pages.py -q`;
  `uv run python tools/gen_agent_guide.py --check`.
  Passed 2026-11-02: all 93 guide cases pass, including the executable short-table
  example on the existing board-workflow page (11,834 bytes/195 lines). The
  generator check passes; full reserved pages and their index remain unchanged.
- [x] 2.2 Prove all existing build-byte entries unchanged, model/schema files
  unchanged, and source types/style/residue/strict validation clean.
  Proof: `uv run pytest tests/unit/test_build_bytes.py -q`;
  `uv run pyright src`; `uv run ruff check .`; `uv run ruff format --check .`;
  `uv run python tools/gen_schemas.py --check`; `uv run python tools/residue/scan.py`;
  `npx -y @fission-ai/openspec validate c0324-technical-layer-tables --strict`.
  Passed 2026-11-02: all 76 existing byte entries pass unchanged (63.67 s).
  Final full source typing reports zero diagnostics; style, guide/schema
  generators, public residue and strict validation pass. No model/schema,
  dependency/lock or byte-pin file changed. The native application and complete
  combined CI gate remain independently open below.

## 3. Actual external proof and combined gates

- [x] 3.0 Recompute all 18 current source-emission rows after a signed source
  checkpoint, using the existing measurement tool and declared cached inputs.
  Preserve historical full-conversion measurements without hand-editing counts.
  Proof: actual `tools/measure_import_coverage.py --cache ... --date 2026-11-02 --write`
  plus its authored/public coverage guards on the resulting artifact.
  Add the affected public row 07 beside existing row 03 in complete-CLI agreement
  and compare both actual emissions to their stored observations.
  Passed 2026-11-02 on signed `fbec5cd9e711cc9b50f9b8d393ab8bb1cda48556`:
  all 18 declared inputs, including both heavy rows, were actually measured.
  Only row 07 changes, removing its two represented layer-table findings. All
  input hashes and source-item counts remain identical; the historical full
  conversion table retains SHA-256 `63b107b962134bcde1ab8c032128bb7c5361d2e53c6c705b6ab110aaa38422f1`.
  Eight authored/metadata/public proofs pass, including complete-CLI agreement
  for rows 03/07 and the unchanged original row-03 full-conversion assertions.

- [x] 3.1 Repeat strict cached public kit import and explicit build in scratch,
  retaining source hashes, unexpressed findings and all-level verification limits.
  Proof: recorded actual CLI commands/results on the signed source checkpoint,
  no lossy/acceptance/tolerance flags and source bytes unchanged.
  Earlier 2026-11-02, on `fbec5cd9`: actual strict full-project replay removes the
  two layer-table findings, then refuses at import self-check (exit 5, FEN-5001,
  one import.unequal finding from the written schematic's pin partition). All
  five source files and the copied original remain byte-identical; no converted
  code is written. Explicit build and all-level comparison are not reached, so
  this task remains open on that separate schematic resolver blocker. No
  acceptance or layer/comparison relaxation was added; see validation.md.
  Passed 2026-11-02 on signed `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`:
  fresh strict import and its reviewed confirmation exit 0, with no unexpressed
  items and all 113 planned hashes matching. A separate explicit build and its
  reviewed confirmation exit 0; all 119 planned hashes match. The five native
  input files remain byte-identical. Full verification reaches every level:
  1-7 and S are equal, while three level-8 render-pixels findings retain exit 5.
  No loss, acceptance or tolerance override was used. Default copy-mode copper
  checking reports zero shorts, clearance or edge-clearance findings; existing
  naming, placement, provenance and unjudged-routing notices remain visible.
  This closes the requested actual replay measurement, not full fidelity or
  task 3.2's combined CI gate. Exact commands and boundaries are in validation.md.
- [ ] 3.2 Run the serial combined complete gate and required exact-head CI.
  Proof: root's complete local gate and successful required CI jobs on the exact
  published candidate. No local focused proof substitutes for this gate.
