Implementation authorised by the maintainer. Each implementation task is scoped to at most one working day; keep tasks unchecked until
its proof passes. Native acceptance remains unmeasured until the maintainer's recorded GUI review.

Proposal validation on 2026-10-12: strict OpenSpec validation passed; residue scan found no hits;
`uv run pytest tests/consistency -q -n 4 --dist loadfile` passed (375 passed, 22 skipped);
`git diff --check` passed. These checks validate the proposal, not the unimplemented feature.

## 1. Intent and geometry contracts
- [x] 1.1 Add immutable presentation requests, DSL declarations and extraction; reject duplicates, missing anchors, ordering cycles and unsupported targets without mutating the circuit. Proof: `uv run pytest tests/unit/dsl/test_schematic_composition.py -q`: 11 passed.
- [x] 1.2 Define composition plan, fixed integer grids, code/severity table, algorithm version and deterministic candidate budgets. Add issue explanations and closed-code tests. Proof: `uv run pytest tests/unit/schematic/test_composition_contract.py tests/unit/cli/test_explain_cmd.py -q`: 11 passed.
- [x] 1.3 Resolve sheet membership, explicit/module/automatic groups and multi-unit coverage; exclude power/global and high-fanout grouping edges. Proof: `uv run pytest tests/unit/schematic/test_composition_groups.py -q`: 8 passed.

## 2. Automatic arrangement
- [x] 2.1 Compute symbol, pin and visible-text envelopes and content regions from representable native geometry; the template adapter is integrated in 3.1. Proof: `uv run pytest tests/unit/schematic/test_composition_bounds.py -q`: 3 passed.
- [x] 2.2 Compose within blocks: main flow, compatible pin alignment, safe quarter turns and nearby two-pin branches with staggered spacing. Record ambiguous choices. Proof: `uv run pytest tests/unit/schematic/test_composition_blocks.py -q`: 3 passed.
- [x] 2.3 Pack blocks in deterministic declared order; honour fixed paper and refuse impossible constraints and budget exhaustion (template verification integrated in 3.1). Proof: `uv run pytest tests/unit/schematic/test_composition_sheets.py -q`: 3 passed.
- [x] 2.4 Add bounded local orthogonal connection candidates and labelled fallback, with no foreign pin crossings, accidental junctions or hidden electrical changes. Proof: `uv run pytest tests/unit/schematic/test_composition_wires.py -q`: 3 passed.

## 3. Altium output and agent review
- [x] 3.1 Document any newly needed native transform/connection facts from public sources before emitter code; integrate composition with ASCII/binary emission and full electrical readback. Proof: `uv run pytest tests/unit/backends/altium/test_composition.py tests/unit/backends/altium/test_layout.py tests/unit/backends/altium/test_hierarchy.py -q`: 70 passed.
- [x] 3.2 Implement versioned structured reports and schematic SVG previews with shared geometry, escaped text and actionable findings. Proof: `uv run pytest tests/unit/schematic/test_composition_report.py tests/unit/schematic/test_composition_preview.py -q`: 3 passed.
- [x] 3.3 Add build selection and transactional report/preview writes; maintain exact c0164 replay/conflict rules and legacy document bytes. Proof: `uv run pytest tests/unit/cli/test_schematic_composition.py tests/unit/cli/test_altium_schematic_sync.py tests/unit/cli/test_build_altium.py tests/unit/lens/test_altium_determinism.py -q -n 4 --dist loadfile`: 68 passed.
- [x] 3.4 Add authored before/after examples, documentation and tested agent instructions for block declaration, overflow/fallback recovery and snapshot conflicts; regenerate the guide. Proof: `uv run python tools/gen_agent_guide.py --check` and `uv run pytest tests/unit/agent/test_pages.py tests/unit/schematic/test_composition_examples.py -q -n 4 --dist loadfile`: 47 passed.

## 4. Closing checks
- [x] 4.1 Run residue, focused tests and repository gates; report independent failures honestly rather than weakening them. Proof: `uv run pytest tests/residue -q`, `make check-fast` and one final `make check` (one full suite at a time).
  - 2026-10-16 (c0171): `uv run pytest tests/residue -q` and `make check-fast PYTEST_WORKERS=3` on `3a4937b` of `release-0.5.0` (13594 passed, 30 skipped, exit 0) pass; the full suite passed in CI run https://github.com/lgili/Fenolite/actions/runs/38825957126 of the release branch `release-0.5.0` at `9946628` (c0171), every job green: the five `unit` jobs (ruff, format, pyright, residue and the whole suite on Python 3.11, 3.12 and 3.13 on Ubuntu and 3.12 on macOS and Windows; `13732 passed, 3403 skipped` on 3.11), `kicad-9` (9.0.9, `tests/kicad -rA`: 1257 passed, 807 skipped, 1 xfailed; `test_probe_results.py::test_probe_results` PASSED) and `kicad-10` (10.0.6 with the corpus and `FENOLITE_HEAVY=1`, `tests/kicad tests/corpus`: 3340 passed, 117 skipped, 3 xfailed, the full `tests/kicad/test_probe_results.py` among them).
- [x] 4.2 Update evidence labels and record native review status, algorithm assumptions and text-bound limitations. A manual Altium review requires the maintainer; do not claim it from synthetic tests. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/backends/altium/test_composition_evidence.py -q`: 9 passed; `openspec validate c0165-schematic-block-composition --strict --no-interactive` passed.
- [x] 4.3 Update `CHANGELOG.md` with implemented behaviour, compatibility and limitations; replace the proposal-only entry when implementation lands. Proof: `uv run pytest tests/consistency -q -n 4 --dist loadfile`: 375 passed, 22 skipped; `git diff --check` and `git diff --cached --check` passed.

## Final validation — 2026-10-12

Implementation and focused proofs are complete. Task 4.1 remains unchecked because the repository
gate did not pass; no failing guard was weakened and no unrelated history or fixture declaration was
rewritten. Native GUI review remains unmeasured.

- Final `make check PYTEST_MAX_WORKERS=4`: lint, generated guide, formatting, pyright and residue
  passed; tests: **13,281 passed, 3,426 skipped, 5 failed**. All composition tests passed.
- Remaining failures predate this change: `test_libcache::test_symlink_refused`,
  `test_doctor_cmd::test_one_entry_per_binary` and `test_cli_candidates::test_one_entry_per_binary`
  need the Windows symbolic-link privilege (WinError 1314); DCO identifies existing unsigned commit
  `1e3e21fc` (`save`); corpus manifest validation identifies existing downgrade fixtures not declared
  in `tests/data/MANIFEST.toml`.
- Iteration `make check-fast` reached 13,073 passed, 152 skipped and 15 failures. Seven feature
  integration failures (layering, example classification and evidence declarations/matrix) were
  fixed and their focused suite passed **140 tests**. Four time-budget tests failed under parallel
  load, then passed isolated and in the final full gate. The other four failures are the Windows/DCO
  failures listed above. The final full gate supersedes this earlier run.
- Additional proofs: native composition and CLI cases **13 passed**; branch-chain geometry with
  those cases **17 passed**; final expanded native composition suite **9 passed**; residue tests
  **31 passed, 7 skipped**; consistency **375 passed, 22 skipped**. The strict OpenSpec validation,
  current generated guide and whitespace checks passed.
