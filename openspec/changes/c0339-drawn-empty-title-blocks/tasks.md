## 0. Reproduce and plan
- [x] 0.1 Validate the reviewed proposal and demonstrate the authored dated-parent/blank-child regression before code. Proof: strict OpenSpec validation and focused failing controls.

## 1. Preserve blank intent
- [x] 1.1 Extract native blank title metadata using the existing explicit blank representation; preserve nonempty values and authored inheritance. Proof: focused extraction/model/fidelity controls for targets9/10.
- [x] 1.2 Export original and generated authored parent/child pages through actual KiCad CLI with drawing sheets and verify date stays parent-only, source bytes unchanged. Proof: native receipts and SVG digests.

## 2. Validation
- [x] 2.1 Prove default scenes/builds byte-identical, document facts and update CHANGELOG. Proof: clean-baseline map and focused regressions.
- [ ] 2.2 Coordinate exact-head check-fast/CI and rerun affected public-board proof without acceptance. Proof: actual required gates and source-bound outcomes before closure.

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
