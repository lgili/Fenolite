## 0. Contract and red proof
- [x] 0.1 Validate scope against living Angle/model-presence contracts and reproduce authored cyclic rotation failure before runtime.
## 1. Focused metric repair
- [x] 1.1 Add explicit empty-default orientation paths; apply only to L7 Text/FootprintField rotation, preserving other leaves and original model values. Proof: exact cyclic positives, true orientation negatives, units/tolerance and presence/sweep controls.
## 2. External and integration proof
- [x] 2.1 Replay exact Tiny inputs, remove only the29 cyclic text-rotation false differences; preserve unrelated Edge.Cuts/pixel findings and immutable inputs.
- [ ] 2.2 Focused tests/lint/types/private residue/strict OpenSpec; root owns final fast/default plans/CI before archive.

Before-code authored proof fails for cyclic0/360 and-90/270 and for true rotations under a length tolerance, confirming the wrong integer-length metric. The comparison never rewrites canonical models; the red test snapshots verify this independently.

Proof:25 authored controls pass0.63s, including noncardinal full turns,
true90/180/1microdegree rotations, angular-vs-length units, generic sweep and
typed None/bool/zero presence; canonical model values never change. Runtime
Ruff/Pyright clean. Broader235-case focus gives231pass and4known pre-existing
c0334 BOM table/CLI-teaching failures, assigned separately to the native owner;
no angle test failed and no BOM code/table was changed by this worker.

Fresh exact-hash Tiny replay compares the old integer metric and the explicit
orientation metric on the same fresh source/build. A multiset analysis removes
exactly29 text-field rotation rows (22 unique locators, seven duplicates), all
-90000000→270000000. It adds no row and preserves every other row/multiplicity:
328field-pose rows for c0345,5graphic-missing and the311/14602 Edge.Cuts pixel
finding. The overall proof remains failed on those real independent findings;
no filter/waiver/acceptance was added. Root fast/default plans/exact CI remain
open under2.2; known BOM-table failures are not called a passing full focus.
