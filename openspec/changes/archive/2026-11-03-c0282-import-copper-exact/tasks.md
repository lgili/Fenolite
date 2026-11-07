## 0. Entry

- [x] 0.1 Read the contracts and record decisions before coding. Proof:
  `npx -y @fission-ai/openspec validate c0282-import-copper-exact --strict`;
  root's integrated `make check-fast` gate.
  Read and decisions recorded 2026-11-01; strict OpenSpec validation passed without warnings.
  The integrated `make check-fast` passed on commit
  `997955c6982eb59a4b0501fa421898af391a1982`: 17,880 tests passed, 53 skipped;
  lint, generated pages, formatting, types and residue passed. External validation record:
  `c0282-final/receipt.json` and `c0282-final/check-fast.log`.

## 1. Exact arc geometry

- [x] 1.1 Add exact thick arc distance decisions, boxes, integer gap floors and witnesses.
  Cover tangency, equality, fractional centres, shallow/major/straight arcs, arc pairs,
  filled rings, reversal and quarter-turn/reflection invariance. Proof:
  `uv run pytest tests/unit/geometry/test_arc_thick.py tests/unit/geometry/test_arc.py tests/unit/geometry/test_shapes.py tests/unit/geometry/test_thick.py -q`.
  Passed 2026-11-01: 77 tests; proof log `geometry.log` in the external validation folder.
  Final proof with indexed-core and independent sampled arc-pair cases: 79 geometry tests passed
  in the combined `geometry-copper-final.log` (253 tests including copper).

## 2. Copper comparisons

- [x] 2.1 Use exact arc cores in copper, rule-area and edge checks and remove band special cases.
  Add strict and 500 nm boundary cases and update prior band expectations. Proof:
  `uv run pytest tests/unit/checks/test_copper*.py -q`.
  Passed 2026-11-01: 174 tests, including exact c, c-500 nm and c-501 nm rows for five pair kinds.
  Integration with c0277 adds an off-axis graphic-arc counterpart. Its regression first misses the
  below-tolerance violation with polygonised graphics; graphic arcs now retain the exact arc core.

- [x] 2.2 Preserve bounded analysis arc polylines and compare their underlying exact arcs,
  widths and declared bands with the copper check. Regenerate the evidence matrix after
  feature-specific flip evidence changes. Proof:
  `uv run pytest tests/unit/analysis tests/unit/test_evidence_matrix_page.py -q`;
  `uv run python tools/gen_evidence_matrix.py --check`.
  Passed 2026-11-01: 404 analysis and matrix tests; generated matrix check passed.

## 3. Bottom chamfers

- [x] 3.1 Mirror pad chamfer corner tokens during placement and bottom derivation; preserve ratios.
  Add authored corner subsets, rotation and flip-involution cases. Proof:
  `uv run pytest tests/unit/backends/kicad/test_embed_bottom.py tests/unit/backends/kicad/test_embed_property.py tests/unit/backends/kicad/test_frame_custom.py tests/unit/library/test_derive.py -q`.
  Passed 2026-11-01: 92 tests; all 16 authored corner subsets at 0, 30, 90 and 180 degrees.

- [x] 3.2 Propagate feature-specific inferred chamfer evidence into builds while retaining the
  existing verified evidence for previously supported bottom shapes. Proof:
  `uv run pytest tests/unit/lens/test_build_issues.py tests/unit/backends/kicad/test_embed_bottom.py -q`.
  Added 2026-11-01 following integration review: the build's evidence must reflect the new mapping.
  Passed 2026-11-01: 79 tests; actual bottom/top builds and definition-specific evidence are covered.

## 4. Evidence and validation

- [x] 4.1 Document exact geometry, changed copper decisions and inferred chamfer mapping; add one
  Unreleased changelog entry and authored oracle canaries. Proof:
  `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_inferred_hypotheses.py tests/unit/test_pyproject_invariants.py tests/unit/agent/test_pages.py tests/kicad/copper/test_parity_bench.py -q`.
  Passed 2026-11-01: 175 tests; the final documentation-only rerun passed 133 tests. Guide generation
  check passed. Local `kicad-cli` 9.0.2 focused tolerance/chamfer oracles: 8 passed; S-1010 records
  the authored measurements, including the documented c-500 nm arc difference.
- [x] 4.2 Run focused checks, formatting, types, residue and strict OpenSpec validation. Proof:
  `uv run ruff check src tests`; `uv run ruff format --check src tests`;
  `uv run pyright src`; `uv run pytest tests/residue -q`;
  `npx -y @fission-ai/openspec validate c0282-import-copper-exact --strict`.
  Passed 2026-11-01: ruff checks clean; 2548 files formatted; pyright 0 errors/warnings;
  staged residue proof 38 passed, 5 skipped (unfetched corpus); strict OpenSpec valid without warnings.
- [x] 4.3 Confirm exact-commit unit, KiCad 9 and KiCad 10 CI jobs, including authored arc and
  bottom-chamfer oracle tests. Proof: required jobs green on the published commit.
  Open: publication and exact-commit CI are grouped with the larger integration batch.
  Local 9.0.2 oracle results are recorded above; exact-commit required CI jobs remain unconfirmed.


## Scoped implementation closure — 2026-11-03

The maintainer clarified that problematic geometry was already excluded from
this closure batch before the run. Close only this specification on tested
source 985f59a1d01a612b2eac0219243199896c24075a plus reviewed documentation.
Run 41708879698 and KiCad10 job126171394674 remain FAILURE; the27known
c0332 failures remain DEFERRED_NOT_PASSED. KiCad9 job126171394740 and all
five unit jobs succeeded. Selected KiCad10 results are source-bound
inferences from completed unfiltered collection and exhaustive -ra non-pass
classification, with no printed nominal PASSED line or green job10 claimed.

`scoped-ci-985f59a1.json` binds source/fixture/log hashes and exact oracle
assertions. The retained census contains18real full conversions, all exit0
and equivalenttrue, plus1byte-identical pytest-current alias;19ZIP members
were checked against original hashes and CRC. Historical and emission-only
measurements remain separate. Upgrade9 is one legitimate minimum-major skip
within the631grouped skips, not an invented per-node result.

The arc controls require native clear/violation endpoints while recording
near-boundary behaviour separately from exact ideal Fenolite decisions. No
arc parity is claimed. The chamfer canary covers four authored rotations
and a wrong-corner control, not every native shape. H-G-CHAMFER-FLIP
and H-A-IMPORT-CODE remain INFERRED. H-G-IMPORT-CODE retains its existing
CORPUS-VERIFIED label and its historical failed-job qualifications, without
new promotion or a global-green claim. Existing observations and scope
limits remain unchanged.

The isolated runtime/tests/tools/configuration remain byte-identical to985.
Fast13 is reused only after checking its tested source equivalence. Later
CAC runtime, c0355, integration CI and release remain independent gates.
No import, CAD/native test, geometry test, full/fast suite or CI was rerun.
Normal OpenSpec1.3 archive, complete normative-body/scenario comparison,
living strict, diff check and private-on staged scan are recorded in the
external per-spec closure receipt. No cumulative rehearsal ordering is
introduced as a new prerequisite: c0249 is archived, and c0281 keeps its own
distinct open archive order.
