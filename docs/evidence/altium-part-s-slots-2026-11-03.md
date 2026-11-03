# Part S: actual Altium24.5.2.23 observations

Source S-1297, 2026-11-03. The Fenolite-authored regions kit was generated on sourcea0e8e5ed
(writer963f9cc0), copied with all three native input digests checked, and opened in actual24.5.2.23.
[The measured recap](altium-slots-24-native.json) retains every input/export/screenshot digest.
Historical26.5 results and the earlier blank3D viewport remain historical observations.

| Case | Current24 observation | Result |
|---|---|---|
| S3 | Board Planning1, actual3D3, then2D2 show the milled S1 and rounded rectangle opening. The3D board has visible hole side-walls/shadows, with no blank GPU viewport. Native NC export contains exactly three drilled slots and one round NPTH hole, accounting for D1/D2/D3/H1; no hit exists for S1/S2/S3/cut-out1. | as expected |
| S4 | Clicking the entire merged L selects one object. Native Properties says Region, Kind Board Cutout, area0.067sq.inch, and one object selected. The contour has the authored three rounded extremities; it is not two independently selected regions. | as expected |
| S5 | One clearance DRC on the hash-guarded authored alias yields seven complete native findings. Board Outline Clearance flags pad TP1 at 7.874mil against 19.685mil and no TP2 occurs in that category. | as expected, literal subtest only |

All three original native inputs retain their hashes after the views, native NC generation and
property inspection. Default NC setup was observed as metric4:4 with trailing zero suppression,
relative origin, optimization enabled and board-edge route generation disabled; it was unchanged.
The exported report counts three2mm NPTH slots and one3.2mm NPTH round hole. Route endpoints and
round centre in the recap account for every native drill object; the milled upper openings are absent.
Native NC auto-preview opened CAM import dialogs; both imports were cancelled, followed by their
specific cancellation notices. No CAM units, global ERC, GPU or VM setting was changed.

## S5 literal native-result subtest

The unchanged authored clearance file has SHA-256
`822d31cf5ee269e44b573db595388c0532008523ff4d0d93d103c7a528a8ec3e` and was opened under the
unique alias `slots-clearance-native-v2.PcbDoc`. An instrumented SDK activation proved its complete
owned path before the single DRC invocation. Existing options stayed unchanged: Create Report File
off, Create Violations on and limit500. No native report file was requested and no Save was performed.

The native PCB Rules And Violations panel was read through Windows UI Automation, scoped to the
owned active alias. Its selected class is `[All Rules]`, display mode is `eGraphicalView_Normal`, and
its header says `7 Violations (0 Highlighted)`, with zero waived violations. All seven one-column grid
rows0–6 were extracted twice; the second read is stable at7→7, below the500 cap. No row selection,
filter, rule, DRC setting or comparator was changed. The complete native descriptions and receipt
hashes are retained in the measured recap, including every finding outside the S5 criterion:

| Native category | Findings | Observation |
|---|---:|---|
| Hole Size Constraint | 4 | Three slot-width findings and one round-hole size finding remain preserved. |
| Board Outline Clearance (Cutout Edge) | 2 | Pad `TP1-1` at `(1496.063mil,1114.173mil)` has `7.874mil < 19.685mil`; a separate collision names the `TP1` overlay text. No TP2 is named in this category. |
| Hole To Hole Clearance Constraint | 1 | Touching holes between free pads at `(1496.063mil,511.811mil)` and `(1692.913mil,314.961mil)` remain preserved; this does not close the separate S2 case. |

Only the literal TP1-positive/TP2-absent result criterion passes. TP2's negative is scoped to the
complete native result for the hash-guarded authored input; no independent SDK census of TP2 in the
active board was executed. This is no clean-board or saved/reopened claim. The native result reads
have VM timestamps, while host observation times are recorded separately without clock calibration.
The full/stable raw panel receipts have SHA-256
`67b4394f86e08803f997457f7d91a19b9136181b43f6ebdaea16de7a234eead4` and
`76e5566c4e29377c334473bc4004a2ea6656d7f4a5ed232db02d6e3086209627` respectively.

S1 pad properties/Drill Drawings, complete S2 acceptance and S6/S7/S8 on24 remain pending.
CUTOUT_REGIONS stays false and H-A-SLOT-KIT stays INFERRED. These observations do not enable the
writer or close5.2.
