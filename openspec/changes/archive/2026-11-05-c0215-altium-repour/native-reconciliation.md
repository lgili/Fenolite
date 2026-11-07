# Literal native coverage reconciliation —2026-11-03

This is an audit of existing source-bound receipts, not a new native run or acceptance. The
JSON companion pins every cited proof document by SHA256. Historical26.5 and current24.5.2.23
inputs stay distinct; no CI, write gate, graduation or hypothesis level changes.

| Literal criterion | Classification | Already measured | Exact remaining distinction |
|---|---|---|---|
| 6.4a nativeKiCad import proof | already executed; CIonlyremaining | ActualKiCad10.0.6plus16independent controls passed17tests3.92s. Allfills/holes/zoneidentity/XOR bounds retained, conservative continuous10nmcertificate and refusal/bridge/11nm negatives pass. ([proof](../../../openspec/changes/c0215-altium-repour/tasks.md)) | No nativeKiCad rerun needed merely for this audit. The literal exact-source CI clause remains unchecked. |
| 7.4 historicalK6.1 | historical different scope | Classicrouted nativeRepourAll/save/pour/copper checks pass on outline output. ([proof](../../../docs/evidence/altium-native-acceptance.md)) | Not the later computed-vs-reference probe suite; avoid calling every K6 repour never run. |
| 7.4 computedpour/pour4K6.2–K6.11 | not executed in existing receipts | c0215introduces21polygon2layer sampleP0–P10 plus4layer probes and computed/reference pairs; no recorded round exists in altium-pour.md. ([proof](../../../docs/evidence/altium-pour.md)) | Needs this specific source-bound round, probesM1–M4/declaredpoints, PolygonManager vsRepourAll, savedcomputed before/after, flaggedcounts andAdvancedPouroff, then kit verify/record. No olderK6or acceptance_v03substitution. |
| 7.4 evidence/promotion | open aggregate | Corpus3compared polygons failM2 (twoalsoM3/M4); no full nativecomputed-pour pass or kit record supplied. ([proof](../../../openspec/changes/c0215-altium-repour/tasks.md)) | Keep7.4and6.4aunchecked; no M3relaxation, newgolden, hypothesis promotion or CIinference. |

No whole unchecked aggregate task was proved complete by this audit, so no checkbox was
changed. Existing-receipt mapping is deliberately separated from an actually unexecuted test;
only literal unmatched criteria should trigger new native work. No waiver or source/version
merger is implied.
