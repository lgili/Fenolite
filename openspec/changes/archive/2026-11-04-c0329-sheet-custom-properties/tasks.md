## 0. Entry

- [x] 0.1 Read the drawn/model/serialization contracts and c0326/c0327 boundaries;
  record the exact public refusal and settle a typed representation preserving
  code-owned text authority. Proof: `openspec validate c0329-sheet-custom-properties --strict --no-interactive`.

The drawn contract remains active in c0276 (not yet a living spec). Existing
canonical defaults and c0326 code-owned text authority were checked. Strict
validation passed before implementation. The drawn editor schema is manually
maintained; its closed keys must agree with the normative lens.

## 1. Implementation in order

- [x] 1.1 Add the typed property/carrier, closed exact TOML and editor schema.
  Prove ordered/empty/unicode round trips, invalid types, duplicates and reserved
  names with original authored tests. Proof: `uv run pytest tests/unit/model/test_drawn_sheet_properties.py -q`;
  `uv run python tools/gen_schemas.py --check`.
- [x] 1.2 Preserve supported native custom property text/poses/fonts through
  extraction, closed private backend adapters and native lowering. Reject every
  unsupported attribute or missing pose explicitly. Proof: `uv run pytest tests/unit/backends/kicad/test_drawn_sheet_properties.py -q`.
- [x] 1.3 Compare custom text/poses/fonts at S and render visible text under existing
  font refusal rules. Preserve hidden/empty states and native defaults. Proof:
  focused comparison/scene cases added to the two files above.

## 2. Proof

- [x] 2.1 Prove authored strict import/build/all-nine equality for both target
  majors and planted text/property-loss negatives, with unchanged original
  inputs and no accepted difference. Proof: `uv run pytest tests/fidelity/test_drawn_sheet_properties.py -q`.
- [x] 2.2 Repeat the declared VME owner on actual native tools, retaining all
  context/input hashes, pins, refusals, partitions and names. Extraction success
  alone does not close c0327 2.2 or the strict corpus gate. Proof: the literal
  c0276 driver for owner row 106 on the measured native version.
- [x] 2.3 Prove ordinary complete maps unchanged relative to signed `11fa8594`
  under the same recipe/runtime. Keep the immutable-table byte guard and its
  existing Mac failure separate; never refresh a baseline to close this task.

## 3. Documentation and validation

- [x] 3.1 Teach the typed property and text authority in drawn/format/agent docs,
  register only authored/public measurements, and update CHANGELOG Unreleased.
- [x] 3.2 Run focused tests, static/types/generator/residue and strict OpenSpec
  checks plus the local fast gate. Keep exact-head CI open until publication is
  authorized and required jobs finish on that exact commit.

## Measured implementation receipts — 2026-11-02

- Model/codec/editor-schema plus existing font neighbors: 104 passed; schema
  generator check passes. The new direct model boundary also rejects boolean
  coordinates rather than treating them as integer lengths.
- New native property/closed-adapter/S/scene file: 30 passed. Default explicit
  `show_name no` and `do_not_autoplace no` remain supported; true/unrepresented
  flags, repeated/malformed data and unresolved text variables refuse. Altium
  custom properties follow its existing explicit loss route.
- Existing native/default/font/comparison/scene neighbors: 245 passed before
  adding the dedicated new-property cases; no ordinary style checks weakened.
- Authored strict import/explicit build/full-proof: 4 passed (15.82 s), both
  target majors, one matched routed track, zero accepted differences and every
  original input byte unchanged. Planted property removal and changed text
  first have a passing control, then keep 1–7 equal and make S/8 differ.
- Actual CLI 10.0.6 authored controls: 4 passed (4.82 s). The same literal
  controls on pinned native 9.0.9: 2 passed, with only the two format-10 inputs
  skipped because the older reader cannot load them (6.46 s). Each run retains
  actual version, arguments, exit status and all input/output SHA-256 values.
  A format-9 custom `~` produces stroked paths in 9.0.9 but none in 10.0.6;
  extraction and scene explicitly refuse this ambiguous value. Format-10
  literal tilde remains supported; the target-9 writer refuses literal tilde.
  Neither result proves a GUI save.

Final fast checks and the real VME owner measurement remain open. No corpus
result or exact-head CI passes by inference from authored controls.

- Complete independent API plan captures on signed `11fa8594` and this c0329
  working source use the same runtime, authored inputs, output paths, seed1 and
  timestamp. All 75 rows match, including 1172 planned files, 130 version-bearing
  files and the same ten refusals. No row/file is omitted and no committed byte
  table is changed. The existing Mac immutable-table failure is separate.
- Combined new property, Altium loss, font/codec/comparison/scene selection:
  252 passed (8.84 s). Agent/format/schema documentation checks: 144 passed
  (10.80 s). Source typing after the closed JSON-binding cast: zero errors,
  warnings or informational diagnostics. Guide names text authority explicitly.
- After the native cross-reader disagreement, the final extraction/scene
  ambiguity guard and authored all-nine proof selection pass 34 tests (19.24 s).
  The complete 75-row default-map capture was repeated on this final production
  source: all 1172 planned files and the same ten refusals still match signed
  `11fa8594`. No byte table or tolerance changed.
- Final whole-tree lint/format (3233 Python files), guide/schema generation,
  source typing and strict OpenSpec checks pass. Private-list residue: zero hits
  in 6390 scanned files, the same sixteen waivers, private gate on. The final
  model/guide selection passes 120 tests (10.74 s).
- The completed local fast run reports 1 failed, 20068 passed, 50 skipped
  (1268.02 s). Its only failure is the existing immutable
  `board_40parts@altium` Mac byte guard. The final legacy-tilde refusal was
  adjusted while this run was in progress and was then proved by the focused
  34-test selection and both native tools above; this run is not an exact-head
  passing gate. Keep task 3.2 open. Logs, native authored SVGs/receipts, complete
  map captures and production-source digests are retained in the external
  `fenolite-c0329-20261102` evidence directory, not in the core repository.

## Clean-source public VME measurement

Signed `2a5b396f0bfe610377b3179bb95041738cbd8269`, native CLI 10.0.6,
literal owner-106 census: 1 failed (62.33 s). Extraction now succeeds without
issues, preserving 36 sheet definitions, 73 hierarchy instances, 460 contextual
definitions and all 6811 pins. The native original and native rebuilt complete
partitions and names agree: 1800 groups, zero differing groups/names or missing
pins. The own resolver still has 1700 groups versus native 1800, with 36
own-only/136 native-only groups and 418 name differences. The same discrepancy
appears after lowering. Resolve warnings remain visible (2501 unknown bus
members and 1079 dangling contacts); four unconnected-name warnings remain.

The actual hash-bound census JSON and complete failed log are retained beside
the c0329 external receipts. This establishes removal of the extraction blocker
and native reconstruction equality, not a passing strict corpus test. Tasks
2.2/3.2 and c0327's VME/naming/combined gates stay open.

The later signed `1918e63214a7d0123e1f5fa8ef095c73fd2e1472` c0320 repair
repeats the literal owner on native 10.0.6: 1 passed (84.67 s). Extraction,
lowering and both native exports preserve every pin and all 1800 groups.
Native original/written names agree. The own resolver's 486 name differences
are explicitly retained; c0327's other row contexts and naming/combined gates
stay open. This measured repeat closes 2.2 only; 3.2 remains open.


Local documentary reconciliation — 2026-11-03: task3.2 is complete only in its
local scope. The existing clean fast18 on signed ad8cbf2e passed22516 tests,
52 recorded skips and every static/private-residue stage. Relevant production,
unit/fidelity and generator paths are byte-identical between that source and
local integration0102716d; the later viewer UI and documentary-reader changes
are independent. The complete quiet fast log establishes source/selection
coverage, not individually printed PASSED node receipts. Retained focused/native
observations keep their original sources, versions and limits. Schema, evidence
and agent-guide generator --check commands were also executed successfully
without new tests or native calls. See local-proof-20261103.json for exact
log/driver/source digests and the six retained c0350 native log seals.

This checks no CI/native/manual task and does not archive the change, promote
a label, declare current integration green or repair any Royal/geometry finding.
The independent exact-source CI boundary remains open.
