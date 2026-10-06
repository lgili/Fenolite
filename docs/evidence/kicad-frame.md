# Board-frame queries and script copper on kicad-cli 9.0.9 and 10.0.6

Counts and outcomes only (change c0028, task group 9). Measured on 2026-10-03 by `tests/kicad/frame/` with
kicad-cli 10.0.6 (macOS) and 9.0.9 (the pinned image). Every board was written to a temporary folder; no
built file is kept.

## The bench

`tests/kicad/frame/_framebench.py`: the three Mini footprints and six authored footprints of
`tests/data/libs/Frame.pretty`, each at 0°, 90°, 180°, 270° and 30° on both sides, 85 placements (the
trapezoid footprint is on the top side only, because `place_footprint` refuses to mirror a `rect_delta`).
Every pad is on a net of its own. The board has a `{}` project file, a project `fp-lib-table` and a rules
file with one rule: every clearance is 0.2 mm.

## Outcomes

| probe | 9.0.9 | 10.0.6 |
|---|---|---|
| `pcb-frame-uuid-9` | `load` | `load` |
| `pcb-frame-uuid-10` | not run (target 10 on 9.0) | `load` |
| `pcb-frame-uuid-keep` | not run (no `pcb upgrade` in 9.0) | `equal` |
| `pcb-frame-shape-near` | `present` | `present` |
| `pcb-frame-shape-far` | `absent` | `absent` |
| `pcb-frame-crtyd-overlap` | `present` | `present` |
| `pcb-frame-crtyd-gap` | `absent` | `absent` |
| `pcb-frame-route` | `absent` | `absent` |
| `pcb-frame-route-cut` | `present` | `present` |
| `pcb-frame-route-moved` | `absent` | `absent` |

**Pad positions.** Every non-via record of `pcb export ipcd356` matches one `board_pads` record by
reference and pin. Position differences agree within one export unit (2540 nm) for pads whose stored angle
is a multiple of 90°, and within two units at 30°; the `R` field is `(−rotation) mod 360°`. The export
rounds each record to a unit, so no tighter bound can be read from it.

**Clearance canary.** 100 probe vias (0.4 mm, drill 0.2 mm, one net), two per pad of the ten
`Frame_Shapes` placements: one along the pad's local +X axis and one along its +X+Y diagonal, placed by
exact bisection where the gap to the pad's copper entries is 0.18 mm (near board) or 0.22 mm (far board).
On the near board every probe gives exactly one `clearance` violation; on the far board none does. This
covers one pad each of `circle`, `rect`, `oval`, `roundrect` and filled-polygon `custom`.

**Courtyard canary.** Twelve pairs: rectangle, line-loop and circle courtyards, on both sides, at 0° and
30°. Rectangle and line-loop pairs whose extents overlap by 20 µm give one `courtyards_overlap` each, and
pairs 20 µm apart none.

Circle courtyards do not hold at 20 µm of overlap, on either major: the extent of a circle is an outer
polygon about 5 µm outside the circle, and KiCad itself reports two circle courtyards only once they
overlap by more than 10 µm (measured on 10.0.6 with two courtyards of radius 2 mm: none with centres
3.990 mm apart, one at 3.985 mm). So an extent overlap of 20 µm can go unreported, and one of 25 µm is
reported. `H-G-FRAME-CRTYD` is refuted for circles at 20 µm and succeeded by `H-G-FRAME-CRTYD-2`, which
asks 40 µm of overlap for circles; 20 µm apart still gives no violation. The extent rule is unchanged: it
stays a conservative superset of the courtyard.

**Routed blink.** `examples/blink_routed/design.py` built for the running major: no unconnected item, and
no `clearance` or `shorting_items` violation naming script copper. Without the `led_a` segment that
reaches `D1`: exactly one unconnected item. After `D1` was moved 4 mm down by token edit (re-saved by
`pcb upgrade --force` on 10.0.6) and the build ran again: every copper uuid kept, the `led_a` track ends
at the moved pad, and the report is clean again.

Two things KiCad reports that are not failures of the copper API:

- The five stitching vias on the bottom-layer `GND` track give `via_dangling` warnings: a through via
  that touches copper on one layer only.
- Moving `D1` 4 mm to the right instead brings the `led_a` track, which follows pad 2, within 0.06 mm of
  pad 1, and KiCad reports that clearance violation. Script copper follows its pads; whether the result
  keeps its clearances is for `fenolite check` (and c0029's copper check) to say. The probe therefore
  moves `D1` along Y.

## The offset of a pad's drill (c0068, 2026-10-05)

`H-G-FRAME-OFFSET`. The bench of `tests/kicad/frame/_offsetbench.py` holds four copies of the authored
footprint `Frame_Offset` (a through-hole `rect` pad of 2 mm × 2 mm with a 0.8 mm drill), each with its
`(offset X Y)` set by token edit and one track of another net above it, under a class clearance of 0.2 mm
and the scoped canary. The gap is the edge distance between the track and the pad's box.

| row | offset | gap without the offset | gap with the copper moved | KiCad 10.0.6 | `check_copper`, v0.1 | `check_copper`, c0068 |
|---|---|---|---|---|---|---|
| `towards` | 0.4 mm towards the track | 0.5 mm | 0.1 mm | `clearance` | clean | `clearance` |
| `short-of` | 0.25 mm towards the track | 0.5 mm | 0.25 mm | clean | clean | clean |
| `away` | 0.5 mm away from the track | 0.1 mm | 0.6 mm | clean | `clearance` | clean |
| `turned` | 0.4 mm towards the track, footprint at 90° | 0.5 mm | 0.1 mm | `clearance` | clean | `clearance` |

So KiCad keeps the hole at the pad's `at` and moves the copper by the offset, which turns with the pad.
v0.1 moved the hole and left the copper. Run with the local `kicad-cli` 10.0.6 (macOS) on 2026-10-05, and with 9.0.9 on 2026-10-06, in the pinned
image and in the `kicad-9` job: the same four verdicts on both majors.
The probe `pcb-frame-pad-offset` records `equal`.

**Census** (`tests/corpus/test_copper_offset_census.py`, 21 readable non-heavy demo boards, each checked
with the classes and the board minimum of its own project file; the corpus holds no rules file for a
demo, and one board has no project file). Two boards hold pads whose drill has an offset; the other 19
hold none, and their counts are the same before and after.

| board | pads | pads with an offset drill | clearance findings, v0.1 | of them naming such a pad | clearance findings, c0068 | of them naming such a pad |
|---|---|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-02` | 165 | 27 | 35 | 35 (12 of a fill and a pad, 18 of two pads, 5 of a pad and a track) | 0 | 0 |
| `kicad-demo-10-0-6-pcb-13` | 428 | 27 | 15 | 0 | 15 | 0 |

Every false finding of v0.1 on the first board named a pad with an offset drill, and all 35 are gone. On
the second board the pads with an offset drill were never close enough to other copper to be reported,
under either reading.
