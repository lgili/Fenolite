## 1. Reproduction and repair

- [x] 1.1 Preserve the six actual native compiler/pin/net exports, the failed
  save-kind probe and actual saved-copy observations. Add and run the focused
  alias regression before changing the writer; retain its failure.
  Proof: source-bound native report and original focused failure receipt.
  Passed 2026-11-02: six original native partitions equal, all compiler/name
  findings retained, 92 original input digests unchanged. The saved root clone
  parses as native CFB with two components and no reader findings. All twelve
  initial new regressions fail on the unchanged writer (1.74 s); receipt retained.
- [x] 1.2 Implement exact-member bus lowering and located refusals. Prove both
  forms, connected hierarchy, scope, scalar/vector controls and negative groups.
  Proof: `uv run pytest tests/unit/backends/altium/test_drawn_bus_aliases.py tests/unit/backends/altium/test_drawn_altium.py -q`.
  Passed: the complete new/existing drawn and font selection passes 77 tests
  (5.96 s), including precedence, descending groups, scalar/vector preservation,
  exact diagonal geometry, connected hierarchy and both loss-flag refusals.
- [x] 1.3 Compile corrected full and connected bus controls in actual Altium;
  independently compare all native pins/net memberships and compiler messages.
  Verify written native copies and reopen without modifying original inputs.
  Proof: recorded native reports with source/input/output digests.
  Passed on clean signed c8faa50c, actual Altium 22.2.1: both corrected forms
  remove exactly the bus-label error and preserve every other compiler/name
  finding. Connected controls retain all 40 pins/36 groups. Twenty complete
  positive graph observations include all ten saved/reopened projects, with
  22 actual native saved schematics. An independent broken child-port control
  retains all pins but splits exactly four pairs; the comparator refuses it.
  All 167 declared original/corrected/negative input hashes remain unchanged.
- [x] 1.4 Update the existing native-kit metadata regression to retain pending
  acceptance while requiring the actual available Altium version and measured
  report, rather than the obsolete unavailable-application reason.
  Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -q`.
  Reproduced after updating the report: one obsolete unavailable-reason
  assertion fails, with 93 other focused metadata controls passing (27.92 s).
  Passed after the update: all 94 focused hypothesis/format/evidence/kit metadata
  controls (38.32 s). The dated unavailable-tool request remains intact; current
  status requires the actual native report, remaining findings and refusal.

## 2. Validation

- [x] 2.1 Update Unreleased, format knowledge and continuation ledger. Run
  static/types, focused consistency, private residue and strict OpenSpec checks.
  Proof: recorded commands and exact results.
  Passed 2026-11-02: 77 focused drawn/font tests and 66 format/evidence/Altium
  documentation controls; whole-tree lint/format, source types (zero diagnostics),
  generated guide/evidence matrix and strict OpenSpec checks. Whole-tree private
  residue: zero hits in 6404 files, sixteen existing waivers, private gate on.
- [x] 2.2 Run `make check-fast` on the repaired candidate, preserving the separate
  Mac board-40 failure if unresolved. Publish only on explicit authorization;
  require exact-head CI before closure.
  Completed 2026-11-02 on clean signed c8faa50c: 1 failed / 20099 passed /
  50 skipped, pytest 798.45 s, whole command 890.86 s, make exit 2. Head and
  source stay unchanged/clean. Only the existing Mac board-40 byte guard fails;
  no golden is refreshed. Keep this task open for a passing gate and required
  exact-head CI; no publication is authorized.

Closed 2026-11-04: `make check-fast` passed on the batch (22620 passed, 51 skipped); every
required job of CI 41853235387 passed on the exact commit 0bce63e2 (unit on Linux 3.11/3.12/3.13, macOS
after a rerun of a runner-capacity cancellation, Windows; kicad-9, kicad-10, drawn-floor, routing
9/10, viewer, mcp, wheel, dco).
