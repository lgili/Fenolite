## 0. Plan

- [x] 0.1 Record the actual source-bound finding and validate the bounded root
  identity design before implementation. Proof: strict OpenSpec validation.
  Passed 2026-11-02 on base a8b1d215, before implementation.

## 1. Reproduce and repair

- [x] 1.1 Reproduce the two false missing panels with original authored strict
  import/build/all-nine controls for both source formats, preserving source
  hashes and nonempty copper. Proof: focused fidelity test before the fix.
  Both target-format controls reproduce exit 5 with exactly two root
  render-missing findings before the fix (2 failed, 3.80 s). They both pass
  after the correction with complete levels, unchanged inputs and one matched
  routed track. The combined new selection passes 8 tests (5.12 s).
- [x] 1.2 Pair only the explicitly resolved roots, preserve all scene content
  and children, and refuse collisions. Proof: focused identity/visible-loss
  negatives plus the authored complete controls.
  Passed: both authored all-nine controls plus six role/child/collision/loss
  controls. A changed visible root still fails render-pixels; both collision
  directions refuse, child renames stay missing and a missing root is not
  synthesized. No acceptance or tolerance override is added.

- [x] 1.3 Reconcile the older font integration witness with the explicit root
  identity contract: preserve its visible Footprint-text negative and replace
  its obsolete root-name failure expectation with a complete zero-acceptance
  nine-level positive. Keep the existing child-name/collision/loss negatives.
  Proof: affected font, root-scene and renamed-root fidelity selectors.

## 2. Validate

- [ ] 2.1 Update fidelity documentation and CHANGELOG; run affected tests,
  static/types/residue/generation/strict checks and the local fast gate on the
  stable batch. Keep native/manual/exact-head CI gates independent.
- [x] 2.2 Repeat the actual public sonde full proof on a clean signed source,
  recording every level, refusal or finding without a new acceptance.

## Measured local validation

The new two-format full controls and six identity/loss/collision controls pass
8 tests (5.12 s). The broader verify-source/copy/drawn/custom-property
selection passes 51 tests (37.22 s). Whole-tree lint and format pass (3235
Python files), source types report zero diagnostics, the generated guide is
current and strict OpenSpec validates without warnings. Private-list residue
reports zero hits in 6397 files with sixteen existing waivers, private gate on.

The local fast gate still requires repetition on the stable batch; its previous
completed c0329 run retains the known Mac Altium byte failure. No complete
passing local gate, public sonde result or exact-head CI is inferred here.

## Stable-batch follow-up — 2026-11-02

Clean signed de6c6f2f completes make check-fast with 2 failed, 20081 passed
and 50 skipped (1093.50 s of pytest; 1175.53 s total). One failure is the
existing Mac board_40parts@altium byte discrepancy. The other is c0326's
older root-filename witness expecting a false missing panel; task 1.3 now
retains its visible Footprint negative and proves safe root spelling with
all nine levels, nonempty matched copper and no accepted difference. The
affected font/root/fidelity selection passes 25 tests (12.34 s), including
unchanged visible-loss, missing-child and collision controls. This is a
focused correction after the completed failing gate, not a green full run.

Task 2.2 passes on clean signed de6c6f2f: the actual Sonde full proof exits 0
in 3.378 s, all nine levels equal, zero differences/acceptance, and original
source hashes unchanged. Video/Sonde refreshed library items and portable
replays are recorded separately in signed local library commit 08b464f.
Native application and required exact-head CI gates remain independent.
