## 0. Evidence and scope

- [x] 0.1 Record the exact Mac failure and bounded local observations, with no
  cause or baseline-change claim. Validate this proposal before helper changes.
  Proof: `npx -y @fission-ai/openspec validate c0323-build-byte-diagnostics --strict`.
  Passed 2026-11-01 before helper changes. The local state and alternate
  interpreter probes do not reproduce the Mac hash; the differing fallback
  pour and one-digit view-setting observations remain separately attributed.

## 1. Internal diagnostics

- [x] 1.1 Retain the one failed authored row's original staged PcbDoc and bounded
  stream/runtime receipt. Preserve its comparison, same-run identity, default
  map and first evidence. Prove capture and the negative boundaries.
  Proof: `uv run pytest tests/unit/test_build_byte_diagnostics.py -q`.
  Passed 2026-11-01: 18 cases, including a single real authored build with a
  forced bad expected digest. The original assertion failed; retained bytes
  equal that run's staged file and all stream hashes agree. Private/unrelated,
  damaged, oversized, disabled, matching, unsafe-destination and first-evidence
  boundaries pass. A capture error leaves the original assertion in control.
  Final 2026-11-02 diagnostic/policy group: 24 passed, including rejection of
  forged stage-file paths and oversized actual payloads before reading bytes.
- [x] 1.2 Enable the fixed external folder only in the Mac unit test step and
  upload only the diagnostic PcbDoc and receipt after failure.
  Proof: `uv run pytest tests/unit/test_build_byte_diagnostics.py -k workflow -q`;
  `uv run pytest tests/unit/test_ci_workflow.py -q`.
  Passed 2026-11-01: four positive/negative artifact-policy cases and all 48
  existing workflow contracts. Broadening either platform condition or the
  two-file upload fails the policy witness; the pytest command is unchanged.

## 2. Validation

- [x] 2.1 Preserve all default byte maps and run the complete focused contracts.
  Proof: `uv run pytest tests/unit/test_build_bytes.py tests/unit/test_build_byte_diagnostics.py tests/unit/test_ci_workflow.py -q`.
  Passed 2026-11-02: 148 cases, including all 75 existing example/target maps,
  24 diagnostic/policy cases and 48 existing workflow contracts. No recorded
  digest changed. The diagnostic tests bind bytes to their own staged run,
  independently of whether the original platform mismatch recurs.
- [x] 2.2 Update one Unreleased entry and pass styles, source types, generated
  guide/schema checks, residue and strict validation.
  Proof: `uv run ruff check .`; `uv run ruff format --check .`; `uv run pyright src`;
  `uv run python tools/gen_agent_guide.py --check`; `uv run python tools/gen_schemas.py --check`;
  `uv run python tools/residue/scan.py`;
  `npx -y @fission-ai/openspec validate c0323-build-byte-diagnostics --strict`.
  Passed 2026-11-02: styles, source types (zero errors), fresh guide/schema,
  zero residue hits and strict validation. The new diagnostic module also has
  zero type errors. Production source, dependencies and byte tables are unchanged.
- [ ] 2.3 Observe an actual Mac failure capture and compare its streams before
  claiming the original mismatch resolved. Root owns the complete gate and CI.
  Proof: retained actual failing-row artifact and required exact-head CI results.

## 3. Early Mac observation follow-up

- [x] 3.1 Run the exact strict authored single-row guard before the complete Mac
  unit step with its own external basetemp; tolerate only that preprobe's exit,
  upload only the same two files immediately, and preserve strict main tests,
  distinct artifact names and late first-evidence capture.
  Proof: `uv run pytest tests/unit/test_build_byte_diagnostics.py tests/unit/test_ci_workflow.py -q`;
  `uv run pytest 'tests/unit/test_build_bytes.py::test_example_keeps_its_bytes[board_40parts@altium]' -q --basetemp /tmp/fenolite-byte-preprobe-proof`;
  global styles, residue, guide/schema freshness and strict validation.
  Passed 2026-11-02: 76 diagnostic/workflow cases, including four early-scope
  negative controls, and the exact single-row command (one passed). The full
  matrix contract refuses tolerance anywhere outside the Mac-only preprobe.
  Styles, generated-file freshness, residue and strict validation pass. These
  local results do not establish the Mac result or the complete unit outcome.

## 4. Same-run geometry hashes

- [x] 4.1 Add opt-in source-filtered geometry observation before the original
  authored build, bounded canonical integer input/output hashes, counts and
  method parameters in the existing receipt. Restore methods in finally;
  preserve one producer call, matching/default/private behavior and all native
  bytes. Prove limits and observer failures without changing artifact paths.
  Proof: `uv run pytest tests/unit/test_build_geometry_trace.py tests/unit/test_build_byte_diagnostics.py tests/unit/test_ci_workflow.py -q`;
  `uv run pytest 'tests/unit/test_build_bytes.py::test_example_keeps_its_bytes[board_40parts@altium]' -q`;
  styles, source/helper types, guide/schema freshness, residue and strict validation.
  Passed 2026-11-02: 88 focused cases and the original single-row command (one
  passed with capture enabled, leaving no matching artifact). The forced-failure
  control builds once, retains unchanged native 7f49 bytes and all 188 operations
  (indices 0..187) with ordered/canonical hashes, zero errors and no truncation.
  Its receipt is 187790 bytes. Private/edited/context filters, setup/hash errors,
  exception restoration and operation/vertex/receipt limits pass. Source and
  all three modified/new helper type checks have zero errors; styles, generated
  files, residue and strict validation pass. No workflow/producer/baseline change.
- [x] 4.2 Compare actual Mac and Linux same-run trace rows before identifying the
  first platform-divergent geometry operation or proposing a geometry fix.
  Proof: source-bound retained traces from both platforms; no inferred Mac intermediate.
  Passed 2026-11-02: actual run 41421198968, head ea762411, early artifact
  13128924288 compared with the immutable d47b67a5 Linux forced-mismatch
  control. Their production source and observer/helper bytes are identical.
  Both traces contain all 188 operations (0..187), zero errors and no limit.
  Operations 0..175 match completely; operation 176, difference, has equal
  ordered/canonical inputs and parameters but different ordered/canonical
  outputs (5624 Linux vertices; 5631 Mac vertices). Operation 179 receives
  downstream-different input but returns the same output. All other rows match.
  The retained native files remain 7f49 (Linux) and 01fd (Mac). This localizes
  the actual mismatch; it does not resolve it or establish complete CI success.
