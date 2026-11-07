## 0. Reproduce and plan
- [x] 0.1 Validate the reviewed proposal and demonstrate the authored dated-parent/blank-child regression before code. Proof: strict OpenSpec validation and focused failing controls.

## 1. Preserve blank intent
- [x] 1.1 Extract native blank title metadata using the existing explicit blank representation; preserve nonempty values and authored inheritance. Proof: focused extraction/model/fidelity controls for targets9/10.
- [x] 1.2 Export original and generated authored parent/child pages through actual KiCad CLI with drawing sheets and verify date stays parent-only, source bytes unchanged. Proof: native receipts and SVG digests.

## 2. Validation
- [x] 2.1 Prove default scenes/builds byte-identical, document facts and update CHANGELOG. Proof: clean-baseline map and focused regressions.
- [x] 2.2 Coordinate exact-head check-fast/CI and rerun affected public-board proof without acceptance. Proof: actual required gates and source-bound outcomes before closure.

Task0.1 passed2026-11-02: strict proposal validation and both authored target9/10 controls fail before the fix, each with the exact undesired child date at S and footer pixel finding at8. No tolerance/acceptance flags or external source modification.

Tasks1.1/1.2/2.1 passed:36focused extraction/writer/full-proof controls pass
after the one-line extraction fix. Both target9/10 authored proofs preserve
blank child metadata with all nine levels equal and accepted/differences empty.
Actual CLI10.0.6 exports original and generated native pages with drawing
sheets included: parent date visible, child date absent, all inputs unchanged;
only native-created project-local settings are separately recorded on copies.
Fresh baselinee265 maps match all22 complete scenes (420455compactbytes) and
all75 complete API plans (1172files across65success/10existingrefusals).
Driver, native-output and input digests are recorded; no byte table changed.
Required coordinator batch gates and affected public-board replay remain open.

## 3. Freeze compatibility follow-up
- [x] 3.1 Preserve existing absent-native-title-block bytes when an extracted explicit blank suppresses inheritance; keep dated-parent/blank-child controls. Proof: four original test_drawn_freeze controls unchanged plus full authored title proofs.

Follow-up reproduced2026-11-02: all four original target9/10 blink/nested
freeze byte controls fail solely because lowering writes an empty(title_block)
node where the generated source omitted it. Resolve explicit blank intent
before native emission, then omit a wholly empty resolved native block. Native
absence is already the documented blank semantics; no inheritance is added.

Task3.1 passed: all4original frozen blink/nested target9/10 exact-byte tests
and both dated-parent/blank-child full1–8/S proofs pass unchanged; actual
KiCad10.0.6 title SVG control passes after the omission fix. No comparison
assertion, expected byte or tolerance was relaxed.

- [x] 3.2 Refresh the derived authored import example with literal blank intent;
  prove only three empty native title blocks and their manifest hashes change
  in ordinary imports before updating the independent aggregate pins.
  Proof: exact complete pre/post maps, 75 complete default plans and focused import/freeze tests.

Task3.2 proof: clean ed972353 and15661b65 complete ordinary-import maps
on9/10 differ only by omitting three empty native title_block nodes and their
three paired manifest hashes. All other bytes stay exact. The source import
aggregate stays exact. Only the corresponding independent rebuilt aggregates
are refreshed. Derived TOML adds exactly blank-title intent on its three
sheets, nothing else. Complete75default plans/1172files match bffa03fd with
zero changes after the omission repair. The full importer identity, original
freeze and examples modules pass53 tests in8.39s. Receipt:
`docs/evidence/drawn-empty-title-import-bytes.json`. Fast/CI remains pending.

Closed 2026-11-04: `make check-fast` passed on the batch (22620 passed, 51 skipped); every
required job of CI 41853235387 passed on the exact commit 0bce63e2 (unit on Linux 3.11/3.12/3.13, macOS
after a rerun of a runner-capacity cancellation, Windows; kicad-9, kicad-10, drawn-floor, routing
9/10, viewer, mcp, wheel, dco).
