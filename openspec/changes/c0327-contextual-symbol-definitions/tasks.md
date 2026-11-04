## 0. Entry and review

- [x] 0.1 Record the exact CI cause, source/hash-bound read-only comparisons,
  authored CC0 witnesses and bounded recommendation without changing a decoder.
  Proof: `npx -y @fission-ai/openspec validate c0327-contextual-symbol-definitions --strict`.
  Passed 2026-11-02: strict validation valid without warnings; 24 format/source
  fact checks pass. Existing S-0058/S-0020/S-0367 cover the inputs/tool/grammar;
  no new external source or permission is needed. Read-only local 9.0.2 witnesses
  include 8-pin metadata controls and closed pin/body/flag/default negatives,
  40-pin vector/group/overbar name controls, and scalar/global election controls.
  Native 10, decoder support and required CI remain unproved.
- [x] 0.2 Review the context-index and per-sheet binding design before implementation.
  Proof: a dated accepted decision records the reviewed data flow and protected boundaries.
  Accepted 2026-11-02 by delegated maintainer review of `29a984544acc6f3be29506c9c49d5e47ecc68f83`.
  Record the concrete closed v0 TOML index, path/hash/order rules, required
  `load_schematic(..., symbol_contexts=...)` input, safe native namespaces and
  all-property preservation before decoder work. Strict validation passes.

## 1. Scoped implementation, after review

- [x] 1.1 Commit declared authored CC0 fixtures/tests for local Description metadata,
  protected core defaults, pin/geometry/flag changes and wrong-context selection.
  Proof: `uv run pytest tests/unit/importer/test_contextual_symbols.py -q`.
  Passed 2026-11-02: 12 witness/boundary cases plus the unchanged manifest
  declaration check pass (13 total, 2.87 s). The positive metadata fixture still
  demonstrates the current global refusal; task 1.2 will enable only that case.
  Distinct complete nodes remain observable despite equal unit pin signatures.
- [x] 1.2 Preserve full contextual definitions in importer assets/indexes and refuse
  non-property/core-default differences, malformed indexes and incomplete bindings.
  Preserve safe interior spaces in native library namespaces with closed path guards.
  Proof: `uv run pytest tests/unit/importer/test_contextual_symbols.py tests/unit/importer/test_drawn_import.py -q`.
  Passed 2026-11-02: 108 importer cases in 109.09 s; expanded index/DSL/guide
  group 149 passed in 16.96 s. Every used definition is indexed once a variant
  exists, so removing a whole group is detectable. Full repeated/opaque
  property nodes, first/all digests, path/symlink guards and safe namespaces
  are checked. Focused parser types report zero errors. Backend selection and
  reviewed plan input integration remain tasks 1.3/1.4.
- [x] 1.3 Carry context through backend lowering/cache identity and emit each original
  native ID with its complete property nodes. Preserve all model/S fields/defaults.
  Proof: `uv run pytest tests/unit/backends/kicad/test_contextual_symbols.py tests/unit/test_build_bytes.py -q`.
  Passed 2026-11-02: 86 backend/default-byte cases in 22.66 s; 74 context,
  manifest and backend-evidence compatibility cases in 10.34 s; 41 importer
  guards in 4.32 s. Full native AST readback rejects wrong-sheet snapshots,
  missing whole groups, duplicate/unknown definitions and property loss.
  Source comparison remains exact; only the documented legacy global-power
  projection is recognized against the library resolver. Contextual inherited
  definitions refuse before flattening properties. Changed backend/lens
  typing reports zero errors; no model/S field changes. The census adapter
  carries the same full contexts and checks actual written ASTs.
  Intermediate inspection checkpoint `a7998ede` refused every new context input
  with FEN-3004 until task 1.4 integrated the complete path; it never silently
  used a global property snapshot.
- [x] 1.4 Bind every asset/index/source input into import/build/sync plans; prove
  stale input refusal and exact confirmation replay with unchanged receipt rules.
  Proof: `uv run pytest tests/unit/cli/test_contextual_symbols.py -q`.
  Passed 2026-11-02: 23 literal CLI cases in 12.72 s; 126 plan/sync/backend/
  importer compatibility cases in 43.58 s; 46 path/import guards in 3.85 s;
  full source typing reports zero errors. Exact replay preserves bytes, issues
  and receipts without running a producer. Source, drawing, factory, index and
  every asset mutation stale the plan; same-byte symlink replacement and output
  ancestor links refuse before writing. An ordinary drawing with the same
  basename retains its existing replay behavior. Sync binds every context input
  and refuses native cache edits it cannot retain. All-nine-level strict owned
  conversion passes with nonempty copper coverage; no original CAD is needed
  for subsequent builds. KiCad schematic output is required in this phase.

## 2. Proof and documentation

- [x] 2.0 Prove the newly reachable same-module nested-page frame bug with an
  authored CC0 witness, then preserve an empty relative module for equality.
  Proof: `uv run pytest tests/unit/backends/kicad/test_drawn_frames.py -q`.
  The literal `217387a4` VME replay failed at native-original with two unknown
  duplicated-frame pin paths; preserve that receipt. No pin/path normalization,
  report exception, module relocation, model/S field or naming change is allowed.
  Passed 2026-11-02: the exact owned witness first failed with module `m`
  instead of empty; after the bounded reference-frame correction, 1 passed in
  1.86 s and 44 extraction/lowering/context cases passed in 9.78 s. Changed-file
  types report zero errors. The real replay outcome remains task 2.2.

- [ ] 2.1 Prove authored native cache/property preservation, component semantics,
  negative guards and all-nine-level fidelity on actual KiCad 9 and 10.
  Proof: `uv run pytest tests/kicad/schematic/test_contextual_symbols.py -q` in both required CI jobs.
  Supplemental local actual 9.0.2: 2 passed in 7.34 s. All component fields and
  flags, four native BOM rows, full local property nodes and all nine levels
  match; the owned census retains 8 pins / 5 groups and four snapshots.
  Required 9.0.9/10.0.6 exact CI remains open; local proof does not substitute.
  Local 10.0.6 repeat 2026-11-04 on clean 468d8a61, `FENOLITE_REQUIRE=kicad`: 2 passed in 17.34 s
  (4 components and 4 BOM rows, all nine levels equal; 8 pins / 5 groups, 4 complete contextual
  definitions, all partitions equal). The required 9.0.9 and 10.0.6 CI jobs still close this task.
- [x] 2.2 Replay the real VME owner and all of its row contexts with declared inputs.
  Preserve any remaining refusal, naming difference and all five reader-floor failures.
  Proof: the literal c0276 corpus driver reports its actual source/version-bound outcomes.
  Clean `7584b394`, actual local 9.0.2: literal owner row 106 failed in 127.60 s.
  All 36 sheets / 460 complete contexts survive; native original/written agree
  on all 6811 pins / 1800 groups with zero partition/name differences. Own
  source/lowered resolver still has 1700 groups (36 only-own / 136 only-native),
  418 raw name differences and unchanged warnings. No pin is missing.
  The 35 other row parameters were not executed; repeating the same failing
  owner is not a passing proof. Keep this task open. Count/hash records in
  docs/evidence/contextual-symbols.json preserve both failed source-bound runs.
- [x] 2.3 Update the one changelog entry, format facts and tested guide teaching;
  run focused proofs, styles, source types, generated guides, residue and strict spec.
  Proof: `uv run ruff check .`; `uv run ruff format --check .`; `uv run pyright src`;
  `uv run python tools/gen_agent_guide.py --check`; `uv run python tools/residue/scan.py`;
  `npx -y @fission-ai/openspec validate c0327-contextual-symbol-definitions --strict`.
  Teach the required context index and additive DSL keyword; notify the c0217
  descriptor owner of both surfaces without changing model/S/CLI envelopes.
  Initial c535edb2 integration inspection 2026-11-02: the merged static scan found the public
  Default-class sentinel in the declared authored project fixture. Its author
  confirms that the fixture has only one netclass, so an explicit priority 0
  preserves every class selection and witness. Change only that priority and
  its manifest digest; keep every native drawing/property/UUID byte and all
  residue patterns unchanged. The context-index helper declares owned-data
  bookkeeping, while native symbol syntax remains the existing reader's scope.
  This is fixture configuration and evidence classification, not acceptance
  of a comparison difference or a native/full-CI result. At that checkpoint,
  tasks 1.3/1.4 remained open; the later proofs above/below supersede that blocker.

  Passed 2026-11-02: 219 focused guide/format/evidence/manifest/context cases
  in 64.75 s; full source types zero errors; ruff and all 3211 Python files
  formatted; guide/matrix/schema/token generation checks pass; strict spec is
  valid; residue zero hits with the same 16 waivers (private gate unavailable).
  The permanent schema contract is docs/symbol-contexts.md. Descriptor owner
  notified; no model1 activation or CLI envelope/schema change is included.
  Final frame/evidence follow-up: 197 focused cases pass in 42.85 s; all 3213
  Python files formatted, four generation checks/strict spec pass, residue
  remains zero with the same 16 waivers and no available private gate.
- [ ] 2.4 Root repeats one complete gate and required CI on the exact published
  combined head. Keep c0276 task 7.2 and naming/native application proofs separate.
  Proof: required exact-head jobs complete successfully; no full KiCad suite on the maintainer PC.

## Maintainer-host native continuation — 2026-11-02

The initial L12 property-preservation test assembled a target-10 board beside
versioned target-9 drawings, then compared raw pre-conversion property nodes
against target-10 output. `Mini:Mini_GND` Datasheet `~` correctly converts to
empty text at the legacy boundary; the existing symembed conversion control
remains strict. c0319 task 1.21 builds the matching target-9 authored board and
binds import/build/verify to that source version, independently of the actual
oracle executable. The original complete property-node, component/BOM, source
hash and all-nine equality assertions remain unchanged. Native 10.0.6 plus the
embedding unit controls: 15 passed. The native 9.0.9 pinned-image repetition:
2 passed (13.97 s). This proves same-format native preservation on both tools;
it does not assert raw AST identity across format conversion or close combined
exact-head CI, the real VME resolver discrepancy or task 2.2.

## Complete literal owner-row continuation — 2026-11-02

Task 2.2 passes on clean signed de6c6f2f and actual KiCad 10.0.6: the
unchanged official driver executes every one of 36 parameters whose
discovered owner is row 106 (36 passed, 1130.36 s). Every source/input
digest, 73-instance context, 36 definitions and 460 complete snapshots are
retained. Extracted, lowered and native written partitions agree on all
6811 pins / 1800 groups; native original/written names also agree. Own
name election retains 486 differences across 967 compared named groups,
plus the existing 2501/1079 bus/dangling and four unconnected-name warnings.
No naming equality, reader-floor retirement, native-9 or exact-head CI
is inferred. The separate orphan row 092 is not owned by 106. Earlier
failed observations stay in the evidence JSON. The dedicated proof
worktree stays clean and its actual source/head never changed.
