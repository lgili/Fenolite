# Copper shorts and clearance against KiCad's DRC

`fenolite.checks.copper` judges the copper of a board for shorts and clearance without any external
tool (capability copper-check). This page lists the KiCad facts that check relies on, in Fenolite's own
words, and compares what it supports with KiCad's DRC. Sources are listed in
`docs/evidence/sources.md`. The rules grammar is on `docs/formats/kicad/rules.md`, the project file on
`docs/formats/kicad/project.md`, the DRC report on `docs/formats/kicad/drc.md`, and the board-frame pad
shapes on `docs/formats/kicad/frame.md`; this page does not repeat them.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| When several custom rules match a pair of items, the rule written later in the rules file governs | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-ORDER |
| A condition on `A` alone matches a pair in either order, and net, class and reference names compare without regard to letter case | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-COND |
| A board-setup minimum above a class clearance governs: the class value below it is not enforced | S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-FLOOR |
| A board-wide custom rule governs below the board-setup minimums, although the manuals call the minimums absolute | S-0038, S-0010, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN-RULE-2 |
| A board-wide custom clearance rule governs the items of a net class with a larger clearance | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN-CLASS |
| Without a custom rule, the clearance between two items is the larger clearance of their nets' classes; a rule with a condition stands to the classes and to the board minimum as a board-wide one does; a rule of severity `ignore` silences its pairs; a rule on `A.Type == 'Track'` governs arc tracks | S-0010, S-0038, S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-COPPER-RESOLVE |
| The DRC judges a track as its centre segment swept by its width, an arc track likewise, a via as a disc of its diameter on each layer of its span, and a pad as the shape of its tokens: on the bench pairs, a gap 10 µm below the clearance is reported and a gap equal to it or 10 µm above is not | S-0010, S-0038, S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-COPPER-SHAPES |
| A violation between copper of two nets that is closer than the clearance in force has the type `clearance`, and copper of two nets that touches has the type `shorting_items` | S-0055, S-0056, S-0058 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRC-TYPES |
| An item of a violation names a pad, a track, a via or a zone by the `uuid` it has in the board file | S-0055, S-0056 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRC-UUID |
| The DRC judges the stored `filled_polygon` of a zone as copper, with no added stroke, when the zone's own clearance is 0 and the zone carries `(filled_areas_thickness no)` | S-0038, S-0020 | KICAD-VERIFIED (10.0.x) | H-K-COPPER-ZONES |
| The DRC reports a clearance violation between two overlapping fills of different nets | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-COPPER-ZONES |
| The DRC applies a tolerance at the clearance boundary: a gap 1 µm below the clearance is reported, a gap 1 nm below it is not | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-COPPER-SHAPES |
| The DRC applies a zone's own clearance to its fill, and a default of 0.5 mm when the zone sets none | S-0038 | INFERRED | H-K-COPPER-ZONES |
| The DRC judges a stored fill against a track, a via or a pad of another net with the largest of the zone's own clearance, the class clearance and the board minimum when no custom rule governs the pair, and names "zone clearance" when the zone's value governs; a governing custom rule replaces the zone's value as it replaces a class value. On the benches a gap 10 µm below that value is reported and a gap equal to it or 10 µm above is not | S-0038, S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-COPPER-ZONECLR |
| The DRC reports no clearance violation between two stored fills of different nets that do not touch: two fills 0.1 mm apart, each zone with a clearance of 0.5 mm, both nets in a class of 0.3 mm, give no violation naming both zones | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-COPPER-ZONECLR |
| A fill that `pcb drc --refill-zones` has just made lies at the zone's clearance or beyond it from a track, an arc track, a via, an SMD pad, a round and a rectangular through-hole pad and a pad with an offset drill: `check_copper` reports none of them with the zone's value | S-0020, S-0022 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-COPPER-ZONECLR |
| `kicad-cli` loads a via of one net whose copper touches only a track of another net, itself joined to a pad of that net, on the track's net: the IPC-D-356 export lists the via under it, the DRC reports no short for it, and a 10.0 re-save writes the via on that net | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-VIA-RENET |
| Touching copper of two nets that holds no pad is treated as one net: the DRC reports no short and describes every item with one net name, and a 10.0 re-save writes that name on every item | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-VIA-RENET |

## Fenolite choices

These are decisions of the code, not facts about KiCad.

- A copper piece is a thick shape: the points within `width / 2` of an integer core (a point, an open
  polyline or a filled ring). Gaps are decided with integers and exact fractions, never a float
  (`docs/geometry.md`, "Thick shapes").
- Two items are judged when they share a copper layer and their nets differ. Copper without a net is
  judged against copper with a net.
- A short is always an error. A clearance finding takes the severity of the rule that governs, and
  `error` for a class, a zone or a board-minimum value.
- A pair of one fill and one track, arc, via or pad also takes the own clearance of the fill's zone
  (`ZoneSettings.clearance`), which counts as a class value does: the largest of it, the class value
  and the board minimum governs without a rule (source `zone`), and a governing rule replaces it where
  it replaces a class value. The value is read from the zone: no rule is written for it. Two fills
  take no zone value: nothing measured says which of the two zones' values KiCad's filler keeps
  between two fills.
- A zone's value is the distance KiCad's filler cuts to around the true copper. An arc is widened by
  its band so that no violation is missed, so for a value of source `zone` the arc narrowed by its
  band is judged with the zone's value, and the widened arc with the value in force without the zone.
  A fill that follows an arc at exactly the zone's clearance is therefore not reported.
- The clearance in force comes from the project's own files: the classes, the class of each net and the
  board minimum of `<stem>.kicad_pro`, and the rules of `<stem>.kicad_dru`. Fenolite ships no rule
  values, so a board without them is judged for shorts only (`copper.clearance-unset`).
- The comparison is strict: a gap equal to the clearance is clean, and a gap one nanometre below it is
  a finding. KiCad may apply a tolerance at the boundary; the `copper-boundary-*` probes record it.
- Zones of different nets, equal priority and a shared layer whose outlines overlap give
  `copper.zone-overlap`: the fill of the overlap would depend on the order in which a filler takes them.

## Supported cases against KiCad's DRC

Parity is what the canaries of `tests/kicad/copper/test_copper_parity.py` prove on authored benches,
per `kicad-cli` version: `equal` means that every row of the kind gave the same verdict in KiCad and in
Fenolite at `c − 10 µm`, `c` and `c + 10 µm` (an arc pair has no row at `c`), under each of three
sources of `c`: a custom rule (0.2 mm), the net class (0.3 mm) and the board minimum (0.4 mm). `n/a`
means that the row has no canary. No canary overlaps or touches: KiCad's verdict on touching copper is
not repeatable ("Via re-net" below), so shorts are proved by Fenolite's own exact tests.

| case | Fenolite | KiCad's DRC | parity 9.0.9 | parity 10.0.6 | basis |
|---|---|---|---|---|---|
| tracks | exact: the centre segment swept by the width | the same | equal | equal | H-K-COPPER-SHAPES |
| arc tracks | within a band of 1.001 µm: a short only when the true copper touches, a clearance finding whenever the true gap may be below the clearance | the true arc | equal | equal | H-K-COPPER-SHAPES |
| vias | exact: a disc of the via's diameter on every copper layer of its span | removes the annular ring on layers where the via connects to nothing, when the board asks for it | equal | equal | H-K-COPPER-SHAPES; unused-layer removal not modelled (Fenolite may report more): documented difference |
| SMD pads | exact for circle, rect, oval, roundrect and polygon custom pads; a conservative superset for trapezoid, chamfered and curved custom pads | the pad's own shape | equal | equal | H-K-COPPER-SHAPES; H-G-FRAME-SHAPE |
| through-hole pads | the pad's shape on every copper layer it names | removes unused pad layers when the board asks for it | equal | equal | H-K-COPPER-SHAPES; unused-layer removal not modelled (Fenolite may report more): documented difference |
| net-tie pads of one group | not judged against each other: two pads of one footprint whose numbers share a group of `net_ties` may touch or sit closer than the clearance (`summary.net_tie_pairs` counts them) | not judged: no `shorting_items` and no `clearance` between two pads of a footprint with `net_tie_pad_groups` | not run on 9.0.9 by this change (no local 9.0.9); the `kicad-9` job records it | equal (`copper-nettie-group`: `touching`, `close`, `spelling`, `three`, and `touching` and `close` without groups) | H-K-NETTIE-DRC |
| net-tie pads outside a common group | judged: a touch or a gap below the clearance between a tied pad and a pad outside its group is a finding, so Fenolite may report more | not judged: no pair of pads of a net-tie footprint is, grouped or not; only a `solder_mask_bridge` between two that touch | not run on 9.0.9 by this change (no local 9.0.9); the `kicad-9` job records it | different, recorded (`copper-nettie-ungrouped`: one finding each for `two-groups`, `ungrouped-touching`, `ungrouped-close` and `groups-close`, none in KiCad) | documented difference |
| zone fills | checked as stored, as filled rings; a stale fill is judged as it is | checked as stored unless the DRC refills | n/a | equal | H-K-COPPER-ZONES |
| zone outlines | not copper; only the overlap of two outlines of equal priority is reported | not copper | n/a | recorded: KiCad reports the overlapping fills as `clearance` | documented difference (`copper.zone-overlap` is a Fenolite rule) |
| the zone's own clearance | applied between a fill and a track, an arc, a via or a pad of another net, as a class value is: the largest of the zone, the class and the board minimum, and a governing custom rule replaces it | the same, 0.5 mm when the zone sets none | equal (the outcome recorded for the `kicad-9` job; measured by hand at proposal time) | equal | H-K-COPPER-ZONECLR: `copper-zoneclr-zone-above-class` (fill–track, fill–via, fill–pad), `-class-above-zone`, `-rule-below-zone`, `-floor-above-zone`; a refilled pour is clean (`copper-zoneclr-fresh`, 10.0.6) |
| pairs of two fills | judged with the rule, class and board-minimum values only, never with a zone's clearance | judges no pair of fills that do not touch | recorded: `copper-fill-fill` `absent` | recorded: `copper-fill-fill` `absent` | documented difference (Fenolite may report more: a stale or hand-made fill that comes too close to another fill) |
| graphics, texts, holes, board edges, mask and silkscreen | not checked, so the copper of a net tie's bridge is never seen | checked; with the net-tie token a pad is not judged against a copper graphic of its own footprint | n/a | n/a | documented difference |
| project severity overrides and exclusions | not applied to copper findings; one finding is accepted by a waiver of the design script (`design.waive()`; `docs/cli-contract.md`, "Waivers") | applied | n/a | n/a | documented difference |
| custom rules outside the closed grammar | not applied; `copper.rules-incomplete` and the stage is `UNVERIFIED` | applied | n/a | n/a | documented difference |
| clearance from a custom rule | the last matching rule in file order | the same | equal | equal | H-K-COPPER-RESOLVE; H-K-DRU-ORDER |
| clearance from net classes | the larger of the two classes | the same | equal | equal | H-K-COPPER-RESOLVE |
| clearance from the board minimum | raises class values; does not raise a custom rule | the same | equal | equal | H-K-PRO-FLOOR; H-K-PRO-MIN-RULE-2 |
| the clearance boundary | strict: a gap equal to the clearance is clean, 1 nm less is a finding | a tolerance: 1 µm less is reported, 1 nm less is not | recorded | recorded | documented difference |
| a project without net classes | no clearance in force; shorts only | KiCad's own defaults apply | n/a | n/a | documented difference |

## Via re-net

`tests/kicad/copper/test_via_renet.py` writes four benches, each with a 0.6 mm via of net `GND` whose disc
overlaps a 0.25 mm `F.Cu` track of net `VIN` by 0.05 mm, and asks `kicad-cli` what it sees
(`H-K-VIA-RENET`). The outcomes below are pinned per version in `docs/evidence/kicad/probes/`.

| bench | what else is on the board | via's net in the export | `shorting_items` naming the via | DRC types naming the via |
|---|---|---|---|---|
| padded | the track ends on a pad of `VIN` | `VIN` on 9.0.9 and 10.0.6 | none on 9.0.9 and 10.0.6 | `via_dangling` on both |
| tied | as padded, and a `GND` track joins the via to a pad of `GND` | `GND` on both | reported on 9.0.9; not stable on 10.0.6 | `shorting_items`, `via_dangling` on 9.0.9; `via_dangling` and, in some runs, `shorting_items` on 10.0.6 |
| dangling | nothing | not stable | none on both | `via_dangling` on both |
| anchored | a `GND` track ending at the via's centre | not stable | none on both | `via_dangling` on both |

What the rows say:

- **Padded.** This is the reported case. The via is loaded on the net of the track it touches, no short
  is reported, and the 10.0.6 re-save (`pcb upgrade`) writes the via on `VIN`. A board that Fenolite
  wrote with this defect would pass KiCad's DRC and lose the defect on the next save.
- **Tied.** When both nets own a pad, KiCad keeps the via on its own net. `kicad-cli` 9.0.9 reported the
  short in 16 of 16 runs. `kicad-cli` 10.0.6 reported it in 8 of 16 runs of one unchanged board, and
  only `via_dangling` in the others, so the outcome is pinned on 9.0.9 only.
- **Dangling and anchored.** Without a pad, KiCad treats the touching copper as one net: it reports no
  short and describes the via and the track with one net name, and the 10.0.6 re-save writes that name
  on both. Which of the two names it takes differs between runs of one unchanged file. On 10.0.6 the
  dangling via was exported under `VIN` in 19 of 24 runs and the anchored via in 7 of 24. On 9.0.9 the
  export kept `GND` in 24 of 24 runs of each bench, while the DRC named the dangling cluster `VIN` in 5
  of 24 runs. These counts are supporting data of 2026-10-04 and are not pinned.

Fenolite does not depend on any of this: `check_copper` reports `copper.short` on all four benches
before a tool reads the board.
