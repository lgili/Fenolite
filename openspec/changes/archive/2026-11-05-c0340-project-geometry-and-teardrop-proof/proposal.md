## Why
Strict public-board conversion preserves teardrop settings but loses the project’s geometric approximation setting. Common-tool native regeneration then produces different copper: the Complex Hierarchy project uses max_error0.01mm while the fresh output template uses0.005mm. Native controls show116 of167 regenerated outlines differ; setting only the generated copy to the source0.01mm makes all167 outlines and filled polygons exactly equal. Cached source165 and rebuilt0 regions still differ honestly; this is not equality of original caches.

## What Changes
- Append optional positive integer-nm Board.max_curve_error and a tested board(...,max_curve_error=...) DSL argument, canonical/schema support and agent teaching.
- Preserve this explicit target-project approximation parameter through KiCad project read/write/import; compare its effective setting at level6, retain strict unsupported-target loss policy.
- Add a narrow source-proof path for qualified native-derived padvia caches: same actual tool/options and verified geometry-affecting configuration on isolated copies, exact complete regenerated geometry comparison, visible raw and regenerated counts/receipts.
- Keep pure model comparison, other opaque items, normal-zone priorities, editable fields, thresholds and original files unchanged. No opaque waiver, hidden sidecar or native-save model substitution.

## Impact
Public board model/DSL and generated guide/schema; KiCad project codec; verify-source level6/7 evidence. Model0 inventory/freeze must incorporate the final appended field before model1 freeze. No runtime dependency is added; actual KiCad runs across its existing process boundary.
