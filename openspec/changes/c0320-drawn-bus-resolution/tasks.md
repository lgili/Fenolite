## 0. Entry

- [x] 0.1 Read the existing drawn bus contracts and coordinate the clean source
  and shared-file ownership. Verify the change id/source range is unused; record
  actual native availability and validate this change before implementation.
  Proof: `npx -y @fission-ai/openspec validate c0320-drawn-bus-resolution --strict`;
  `kicad-cli --version`.
  Passed 2026-11-01: strict validation valid; actual native version 9.0.2.
  Read-only reproduction matches both reported full pin coverages, group
  differences and unknown-member counts. Source/model/acceptance files are
  unchanged. Task 1.1 still needs authored controls. Paused here for the
  maintainer's higher-priority final model0 freeze on clean dbfd6fc3. Resumed
  2026-11-02 after clean signed model1 cutoff09544d4f, without changing that tree.

## 1. Bounded resolver repair

- [x] 1.1 Reproduce the fetched public-row partition/member issues read-only,
  identify the concrete defect and add minimal entirely authored native controls
  for the implicated bus/group/alias/hierarchy semantics. Record native version,
  exact pin coverage and failing-before results without committing public CAD.
  Proof: `uv run pytest tests/unit/model/test_drawn_bus_scope.py -q`;
  `uv run pytest tests/kicad/schematic/test_drawn_bus_scope.py -q -s`, before repair.
  Reproduced 2026-11-02: nine intended unit failures and six native partition
  failures. Each actual9.0.2 vector/group/alias × entry/junction control exports
  all40 pins, with36 native groups versus40 own groups. No native export or
  coverage assertion failed. Public13 has17 bus labels at entry endpoints with
  no wire/pin there; public17's58 bus labels lack that contact. Native input
  construction uses only Fenolite's authored mini fixture and writer, no public CAD.
- [x] 1.2 Implement only the reproduced joins and prove deterministic positive
  and negative controls, including missing labels and unrelated member scopes.
  Proof: `uv run pytest tests/unit/model/test_drawn_connect.py tests/kicad/schematic/test_drawn_oracle.py -q`.
  Passed 2026-11-02: 26 unit cases and22 actual9.0.2 native cases,
  including all six new complete40-pin controls and the original fixture
  partitions/names/ERC checks. The missing-label negatives remain enforced.
- [x] 1.2a Resolve the remaining authored overbar/connected-bus definition cases
  only after their before-fix native measurements. Cover renamed/reordered
  vectors/groups and disconnected/literal negatives; preserve all source text.
  Proof: focused authored native and unit bus cases, then original resolver/oracle
  regressions and fresh public-row receipts.
  Passed 2026-11-02: 46 unit and36 native9.0.2 cases. All20 new native
  controls cover exactly40 pins, including disconnected/reversed nested-vector
  negatives. Public13 now matches all313 pins/95groups; public17 improves to
  36/16 differing groups, with all2033 pins retained. Unknown-member warnings
  remain visible; no acceptance or comparison threshold changed.
- [x] 1.2b Reproduce scalar local/hierarchical/global label scope aliases with
  entirely authored native controls before a KiCad-only correction. Preserve
  instance scope, unequal names, generic defaults and unmatched-port errors.
  Proof: focused authored native before/after controls, literal/scope negative
  regressions, then fresh public partition receipts.
  Passed 2026-11-02: two expected before-fix native partition failures/four
  controls pass, then42 native and64 unit cases pass. Both public rows have
  complete exact partitions:313pins/95groups and2033pins/588groups. The local
  label control was corrected to omit an invalid shape before the valid proof.
- [x] 1.2c Distinguish ascending vector position from equal numeric indices
  using authored offset/reversed-range controls before finalising the mapper.
  Proof: new native offset controls, existing native/literal regressions and
  a fresh public replay after the correction.
  Passed 2026-11-02: two discriminating offset controls first refute equal
  numeric indices, then44 native cases and64 unit cases pass. Both public
  complete partitions remain exact after the ascending-position correction.
- [x] 1.3 Prove raw labels/S geometry and generic/Altium literal behavior stay
  intact. Document actual facts and add one Unreleased changelog entry.
  Proof: focused source-preserving, drawn round-trip and backend controls.
  Passed 2026-11-02: 116 extraction/lowering/freeze/writer/levelS/drawn-file/
  build-guard/sync/Altium-netlist cases,64 unit scope cases and63 evidence
  register cases. Raw labels/ports/geometry/opaque fields remain unchanged;
  model class ASTs, schemas, DSL and dependency metadata are unchanged.
  S-1280 records only actual9.0.2 controls; existing evidence levels stay intact.
- [x] 1.4 Rerun the two public partition diagnostics with actual native 9.0.2,
  compare complete pin coverage and report remaining differences honestly.
  Proof: read-only corpus partition receipts; no ratchet/acceptance edits.
  Passed 2026-11-02: final public13 has313 own/native pins and95groups;
  public17 has2033 own/native pins and588groups, with0/0 differing groups
  and0/0 native/PCB differences each. All9/10 source files remain byte-equal
  to the respective entry snapshots. Unknown-member warnings32/374 and
  public17's979 dangling warnings remain visible; no overall fidelity claim.

- [x] 1.5 Investigate the clean c0329 VME own-1700/native-1800 partition
  discrepancy using original authored disconnected-bus/member controls first.
  Record actual native outcomes, including any refuted hypothesis. Implement
  only a demonstrated bounded scope correction; preserve generic/Altium
  behavior, full source/S data, all pins, warnings and native acceptance gates.
  Proof: authored complete-partition controls on actual KiCad 9/10, existing
  scope regressions and the literal fresh owner-106 census on a clean source.

  Initial four original native 10.0.6 controls: one isolation failure and
  three valid joins pass (14.36 s). The stronger six-case version adds a
  single-labelled-island negative: two failures/four passes before the fix
  (2.91 s). After the KiCad-only explicit policy, the entire native scope
  file passes 34 tests on 10.0.6 (17.50 s) and 34 on pinned 9.0.9 (43.72 s).
  Model/backend/Altium/source-stage/all-nine neighbors pass 127 tests
  (18.95 s), including six source/pin-preserving generic-policy controls.
  The earlier four single-child diagnostics all matched native and refuted
  the broader idea that actual scalar labels elsewhere should be ignored.
  No scalar-label rule, warning policy or acceptance is relaxed. The fresh
  clean-source VME replay and combined/static gate remain open.

  Final whole-tree lint/format, source types (zero diagnostics), guide/schema
  generation and strict c0320 validation pass. Format/agent documentation
  selection: 120 passed (8.28 s). Private-list residue: zero hits in 6391
  files, sixteen existing waivers, private gate on. All 75 complete API maps
  (1172 planned files including version-bearing files, ten unchanged refusals)
  remain identical to signed `11fa8594`. The last complete local fast run
  predates this bus correction and fails only the recorded Mac Altium byte
  guard; it is not a passing gate for this source. Fresh public replay and
  final combined validation remain open.

  Clean signed `1918e63214a7d0123e1f5fa8ef095c73fd2e1472`, actual native
  10.0.6, literal owner-106 census: 1 passed (84.67 s). Source, lowered and
  both native views have all 6811 pins and exactly 1800 groups; zero missing
  pins or differing groups. Native original/written names also agree exactly.
  Own naming remains a separate open finding: 486 differences across 967
  compared named groups; the census's partition pass does not close it.
  All context/input hashes and warnings remain in the actual external receipt.

## 2. Closing

- [x] 2.1 Run focused lint/format/types, generated-guide/schema, residue and
  strict OpenSpec checks; record exact scope and a clean signed checkpoint.
  Proof: affected Ruff checks, `uv run pyright src`, generated checks,
  `uv run python tools/residue/scan.py`, strict OpenSpec validation.
  Passed 2026-11-02 on clean signed implementation3ac5605a: affected Ruff
  and format, fullsrc types0errors, generated guide/schemas/evidence matrix,
  residue0hits/6267files/16existing waivers (private list not configured),
  strict OpenSpec. Tested source hashes and exact author/committer/DCO agree.
  The final task-note checkpoint changes no implementation or proof scope.
- [ ] 2.2 Run the root-owned combined/full gate and exact-head CI.
  Proof: successful complete gate and required CI jobs on the recorded commit.
