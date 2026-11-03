# Literal native coverage reconciliation —2026-11-03

This is an audit of existing source-bound receipts, not a new native run or acceptance. The
JSON companion pins every cited proof document by SHA256. Historical26.5 and current24.5.2.23
inputs stay distinct; no CI, write gate, graduation or hypothesis level changes.

| Literal criterion | Classification | Already measured | Exact remaining distinction |
|---|---|---|---|
| 5.3 PartT PADSTACK/T6 | historical native coverage | AD26.5 authored four-layer Full Stack and actual PcbLib placement passed: In1 round1.2×1.2mm, In2rect1.4×1.1mm. The native report explicitly excludes connector masks and other stack cases. ([proof](../../../docs/evidence/altium-padstack-part-t.md)) | Do not repeat that measured Full Stack placement. Connector mask/paste inspection remains unproved for PartT. |
| 5.3 SCHEMATIC/T2 | historical native coverage | Corrected converted public project compiles without errors, with18warnings; explicit no-connect pins retained. ([proof](../../../docs/evidence/altium-native-acceptance.md)) | Retain warnings/source-vintage; it does not cover the DIFAT or PADSTACK compile cases. |
| 5.3 SCHEMATIC/T3 | existing receipt mapping | Later report supersedes the earlier unpoured failure: public SCHEMATIC native saved copy has one polygon/one fill after native rebuild. ([proof](../../../docs/evidence/altium-native-acceptance.md)) | Bind the corresponding existing saved-file receipt before asking for another repour; no new native pass is inferred for other cases. |
| 5.3 SCHEMATIC/T4 | existing receipt mapping | After offset repair, actual native DRC reports0clearance plus25unrouted,9mask-sliver,152silk-to-mask,60silk-to-silk; earlier23clearance fault is preserved. ([proof](../../../docs/evidence/altium-native-acceptance.md)) | The literal T4 asks category counts, not DRC-clean output. Reconcile this dated receipt with its repaired source before declaring the entire DRC step untested. |
| 5.3 SCHEMATIC/T5 inspection | literal observation covered | S0731/stable-link retry matches all68components automatically; four valid removals are the2explicitly unconnected nets and2PCB-only classes. No component additions/removals or footprint replacements; ECO closed without Execute. ([proof](../../../docs/evidence/altium-native-acceptance.md)) | T5 explicitly requests ECO inspection without executing on the only copy. Do not invent an execution requirement; full PartT remains incomplete. |
| 5.3 T1all docs / DIFAT T1–T6 / remaining PADSTACK / connector masks | not established by these receipts | Root SCHEMATIC opening and the four-layer placement are recorded, but no complete case×T1–T6 report exists for all3converted projects, especially the large DIFAT case. ([proof](../../../docs/evidence/altium-pcb.md)) | Only genuinely unmatched cases need native work; acceptance_v03 and old generic kit use different input identities. |
| 5.3 aggregate +4hypotheses | open aggregate | No complete PartT report settles all4conversion hypotheses; source-specific partial observations above remain retained. ([proof](../../../openspec/changes/c0160-convert-to-altium/tasks.md)) | Leave5.3unchecked and do not promote hypothesis/evidence or claim closure. |

No whole unchecked aggregate task was proved complete by this audit, so no checkbox was
changed. Existing-receipt mapping is deliberately separated from an actually unexecuted test;
only literal unmatched criteria should trigger new native work. No waiver or source/version
merger is implied.
