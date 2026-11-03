# Part S: actual Altium24.5.2.23 observations

Source S-1297, 2026-11-03. The Fenolite-authored regions kit was generated on sourcea0e8e5ed
(writer963f9cc0), copied with all three native input digests checked, and opened in actual24.5.2.23.
[The measured recap](altium-slots-24-native.json) retains every input/export/screenshot digest.
Historical26.5 results and the earlier blank3D viewport remain historical observations.

| Case | Current24 observation | Result |
|---|---|---|
| S3 | Board Planning1, actual3D3, then2D2 show the milled S1 and rounded rectangle opening. The3D board has visible hole side-walls/shadows, with no blank GPU viewport. Native NC export contains exactly three drilled slots and one round NPTH hole, accounting for D1/D2/D3/H1; no hit exists for S1/S2/S3/cut-out1. | as expected |
| S4 | Clicking the entire merged L selects one object. Native Properties says Region, Kind Board Cutout, area0.067sq.inch, and one object selected. The contour has the authored three rounded extremities; it is not two independently selected regions. | as expected |
| S5 | No current24 clearance DRC was run in this operator window. | pending |

All three original native inputs retain their hashes after the views, native NC generation and
property inspection. Default NC setup was observed as metric4:4 with trailing zero suppression,
relative origin, optimization enabled and board-edge route generation disabled; it was unchanged.
The exported report counts three2mm NPTH slots and one3.2mm NPTH round hole. Route endpoints and
round centre in the recap account for every native drill object; the milled upper openings are absent.
Native NC auto-preview opened CAM import dialogs; both imports were cancelled, followed by their
specific cancellation notices. No CAM units, global ERC, GPU or VM setting was changed.

S1 pad properties/Drill Drawings, S2/S5 DRC and S6/S7/S8 on24 remain pending. CUTOUT_REGIONS stays
false and H-A-SLOT-KIT stays INFERRED. S3/S4 observations alone do not enable the writer or close5.2.
