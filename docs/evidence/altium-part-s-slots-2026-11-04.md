# Part S: actual Altium24.5.2.23 S1, S2 and S8

Source S-1570, 2026-11-04. A Claude agent ran these cases at the maintainer's request of 2026-11-04,
operating the Altium Designer installed in the maintainer's Parallels Windows VM. This is not the
maintainer's own review. The tool reports `Client.GetProductVersion` 24.5.2.23, and `X2.exe` has
FileVersion 24.5.2.23 (Trial licence, not signed in). The inputs are the same Fenolite-authored Part S
kit that S-1297 used, copied with every `SHA256SUMS` digest checked: regions
`be65d4b9884e1949abd162f64033f54b92167bf1cea5af535031d691467910f0`, clearance
`822d31cf5ee269e44b573db595388c0532008523ff4d0d93d103c7a528a8ec3e` and gate-off
`c798ec4604bddbd28674bdd7fde5a41fdf6440b8ed4c298bc984b005ecb95554`. After the run, all 15 staged
inputs still match their digests. [The measured recap](altium-slots-s1-s2-s8-24-native.json) keeps the
digests of the inputs, the native outputs and the read-only scripts.

**Method.** The agent ran public menu commands through Windows UI Automation in the VM's interactive
session. Native properties and results were read by authored read-only DelphiScript procedures, started
with File » Run Script. The procedures use the public PCB and workspace interfaces: they open a
document, iterate its objects and list the violation objects and the Messages panel. Nothing was saved.

| Case | Current24 observation | Result |
|---|---|---|
| S1 | `regions/slots.PrjPcb` and its PCB open. The workspace message count stays 0 and no dialog appears. `D1` is a free pad on Multi Layer with an empty designator and no net. It has hole type 2 (slot), hole size 2.0 mm and hole width (slot length) 12.0 mm. It is rotated 30°, not plated, and its copper size of 12.0 × 2.0 mm equals the hole, so there is no ring. Its solder mask and paste expansion modes are both 1 (the same value as on the other three free pads), with expansions of 4 mil and 0. File » Fabrication Outputs » NC Drill Files with unchanged defaults writes `slots-SlotHoles.TXT` (`;TYPE=NON_PLATED`, T01 2.0 mm) with three routed slots; the first runs from (22.6699, 4.5) to (31.3301, 9.5) mm, which is `D1`'s 12 mm slot at 30° centred on (27, 7). `slots-RoundHoles.TXT` holds the single 3.2 mm hole, and the report lists T1 slot ×3 NPTH and T2 round ×1 NPTH. The two native CAM auto-imports were cancelled, and each produced its cancellation notice. In Drill Drawings, the preview (2 pages) shows `D1` as a drill symbol at its centre, the same symbol as `D2`/`D3` (tool T1) and different from `H1`. The slot outline itself is not drawn, the board has no `.Legend`, and the preview did not finish refreshing after Fit On Page. | as expected for the pad and NC Drill; Drill Drawings only by symbol class |
| S2 | On a fresh copy of `clearance/`, Tools » Design Rule Check » Run Design Rule Check runs with the existing options (Create Report File off, Create Violations on, limit 500). Hole To Hole Clearance reports `Pad/Via Touching Holes` between the free pads at (1496.063, 511.811) mil and (1692.913, 314.961) mil, that is `D2` (38, 13) and `D3` (43, 8) mm. The complete result is 7 violation objects and 7 messages, the same seven findings that S-1297 recorded for S5: four Hole Size, one Hole To Hole, and two Board Outline Clearance (Cutout Edge) for pad `TP1-1` and the `TP1` text. | as expected |
| S8 | `gate-off/slots.PcbDoc` opens with no new message. It holds the four free holes (three slots and one round hole, with the same properties as in `regions/`). Its only region-type object has 4 points and an area of 60 × 40 mm, and `regions/` holds the same object next to its three cut-outs. No region of any cut-out exists. `gate-off/build-report.json` names `cutout/1`, `slot/S1` and `slot/S2+slot/S3` as `altium.not-lowered`. | as expected |

The 4-point region-type object is reported as observed. It is taken to be the board shape only because
its area equals the 60 × 40 mm outline. The value 1 of the mask modes is read as "from the rules" only
by comparison: Fenolite writes the rule mode on every pad, and the observed expansions equal the
default rule values. The tool's own name for the value was not displayed. The S1 drill-drawing
expectation ("`D1` is a slot in the drill drawing") was therefore observed only through the slot
tool's symbol, not as a drawn slot.

Together with S-1297 (S3–S7), every case S1–S8 now has a current24 observation on these input
digests. They come from separate operator sessions, and no formal kit record exists. `H-A-SLOT-KIT`
therefore stays `INFERRED` and aggregate task 5.2 stays open. That needs a formal single-run record
of K5.6–K5.13 and the maintainer's decision on the S1 drill-drawing limit. No native file, screenshot
or saved document enters the repository; they stay in the agent's kit folder outside it.

## Single-run K5.6–K5.13, 2026-11-04 evening (source S-1583)

A Claude agent ran group K5's Part S steps K5.6 to K5.13 at the maintainer's request of 2026-11-04/05. It
used the same Altium Designer 24.5.2.23 (Trial) in the maintainer's VM. This is not the maintainer's own
review. The steps ran in one session on the `slots` sample of the kit built at `0207378b` (`kit.json`
`f1b0e767…`). It is the same run and form as the S-1579 K6 rerun, with version `AD 24.5`. The inputs
have the digests above (regions `be65d4b9…`, clearance `822d31cf…`, gate-off `c798ec46…`), and all 15
inputs still matched them after the run. The method is the same as above. Board Planning Mode and 3D
Layout Mode were judged from window captures of the document area, which were deleted after viewing.

| step | case | observation | form | `kit verify` |
|---|---|---|---|---|
| K5.6 | S1 | The project and PCB open with no message (message count 0). `D1` is a free Multi Layer pad with no designator, a slot hole of 2.0 × 12.0 mm at 30°, not plated, with copper equal to the hole. Its mask and paste modes are 1. NC Drill Files (defaults) showed no message and wrote `slots-SlotHoles.TXT` (`649c90c9…`, `TYPE=NON_PLATED`, three routed slots with centres at (27, 7), (38, 13) and (43, 8) mm) and `slots-RoundHoles.TXT` (`83d17f76…`, one 3.2 mm hole at (52, 8)). Drill Drawings opened a two-page print preview. Page 1 shows a small symbol and page 2 a cross at each of the four hole centres. Neither page draws `D1`'s slot outline | `false` | fail |
| K5.7 | S2 | DRC on `clearance/`: Hole To Hole Clearance reports `Pad/Via Touching Holes` between the free pads at (1496.063, 511.811) and (1692.913, 314.961) mil, that is `D2` and `D3` | `true` | pass |
| K5.8 | S3 | Board Planning Mode shows the openings of `S1`, the L of `S2` + `S3` and `cut-out 1`. 3D Layout Mode shows the board with the same three openings cut through it, next to the drilled holes. The NC drill files above hold no hit at `S1`, `S2`, `S3` or `cut-out 1` | `true` | pass |
| K5.9 | S4 | `regions/` holds three Board Cutout regions (kind 3) for the openings. The L is one region of 164 points, about 42.9 mm². Its three free ends are round in both views | `true` | pass |
| K5.10 | S5 | The same DRC has 7 violations: four Hole Size, the Hole To Hole pair, and two Board Outline Clearance (Cutout Edge) entries for pad `TP1-1` (7.874 mil against 19.685 mil) and the `TP1` text. No entry names `TP2` | `true` | pass |
| K5.11 | S6 | Repour All on `clearance/` showed no message. The `GND` polygon holds one region, and its copper surrounds the three milled openings without entering them | `true` | pass |
| K5.12 | S7 | File » Save As wrote `results/slots/slots-saved.PcbDoc` (`de793c6e…`). `FENOLITE_ALTIUM_S7=<file> uv run pytest tests/unit/backends/altium/test_part_s.py -k s7` gives 1 passed | file | pass |
| K5.13 | S8 | `gate-off/slots.PcbDoc` opens with no new message. It holds the four free holes and one 4-point region of 60 × 40 mm, and no cut-out. `build-report.json` names `cutout/1`, `slot/S1` and `slot/S2+slot/S3` as `altium.not-lowered` | `true` | pass |

`fenolite kit verify` (at `22855dae`) exits 5. K5.7 to K5.13 pass and K5.6 fails, so `H-A-SLOT-KIT` is
judged `fail`. The only failing criterion is the S1 drill drawing, which marks `D1` by its centre only.
That is the limit the S-1570 run noted. The agent typed `false` for K5.6 because the drawing does not show
the slot as the criterion asks. Whether that limit is acceptable is the maintainer's decision. No record
was confirmed. `H-A-SLOT-KIT` stays `INFERRED`, and task 5.2 stays open.
