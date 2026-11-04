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
