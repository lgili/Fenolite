---
topic: board-floorplan
title: Floorplan and placement practice
summary: Mechanical constraints first, regions by domain and function, a power flow in one direction, the loop parts first, decoupling at the pin, and reference blocks.
---

# Floorplan and placement practice

Placement decides most of a board's quality. A good placement makes the routing short and obvious. A
bad one cannot be saved by any router: it only finds long ways around. This page gives the order and
the rules. The page `placement` gives the commands that move parts.

## 1. What cannot move

Start from what the enclosure and the mechanics fix:
- the outline and the mounting holes;
- the connectors and where their cables go;
- heat sinks and the parts bolted to them;
- tall parts under a lid;
- the keep-outs around screws, washers, standoffs and heat-sink feet;
- a part that lies flat over others (a bridge rectifier, a large resistor).

Place these first and lock them (`locked=True`). Write each keep-out as a rule area, and each height
limit as a height rule, so that later steps respect them (`design.rule_area`, `design.height_limit`).
- **A physical sample governs.** When one exists, measure it with a caliper, and note the source of
  every dimension: sample, drawing, datasheet or estimate.
- **Take module mounting holes from the module's datasheet**, through its footprint, and delete any
  duplicate hole that a board drawing adds.
- **Reserve the heat sink's envelope** as an area where no part may sit.
- **Place the largest bodies first,** at their maximum envelope, and check the heights on both faces
  against the enclosure.
- **Keep clear what lies under a part.** For a part that lies flat, ask what may sit under its body,
  and keep that area clear unless the owner allows it. Keep SMD parts out from under the body of a
  through-hole module unless its standoff height is checked. Give a large electrolytic that sits flush on
  the board a relief hole under its vent.
- **Moving a mounting hole moves everything attached to it:** the keep-outs, the heat sink, the parts
  bolted to it, and the routing corridors around it.

## 2. Regions

- **Divide the board into regions** by insulation domain first (`board-insulation`), then by function:
  input and filter, rectifier and bus, power stage, gate drive, sensing, supply, control,
  communication.
- **Give each region a compact shape** with straight borders. Between regions, leave the ways that
  nets need to cross. Count them now, not when routing fails (`board-routing`, "Count the
  crossings").
- **Put the control region next to its connector** and as far as practical from the switching nodes.
  Put the power region next to the power connectors and the heat sink.

A first placement by region puts each insulation domain in its own band of the board, with the isolator
across the border between the two bands it joins:

```fenolite-cmd
fenolite place board --strategy regions --barrier U5 --dry-run
fenolite place board --strategy regions --group hv=J1,R1* --group lv=U2,C* --region hv=0mm,0mm,25mm,40mm --region lv=25mm,0mm,60mm,40mm --barrier U5 --dry-run
```

Read `result.regions`: the parts of each region, those that did not fit (`place.no-room`), and the open
connections that cross a border (`place.region-crossing`). Across an isolation border only the barrier
part should join the two sides. Then confirm with `--confirm --plan <plan_id>`, and move parts by hand.

## 3. A power flow in one direction

Arrange the power path as a line, in the order the current flows:
1. the input terminal;
2. the fuse and the surge parts;
3. the filter and the inrush limiter;
4. the rectifier;
5. the bulk capacitors and the bus fuse;
6. the power stage;
7. the output connector.

A power path that folds back across the board crosses the control region, lengthens the loops, and makes
every insulation border longer. Only low-current branches may run backward; list each one. Place the
rectifier so that its AC side and its DC side do not cross. Keep the raw side of the filter apart from
its filtered side (`board-emc`).

## 4. The loop parts first

Inside the power region, place first the parts that close the large current loops:
- the switch or power module;
- its DC-link capacitors, film or ceramic, at its supply pins;
- the shunt in the return path;
- the bulk capacitors;
- the gate driver next to the switch it drives.

Put the decoupling capacitor of each supply pin of a switching part as close to the pins as the part's
layout allows. Then place everything else around these loops. `board-power` says how to judge a loop.
- **Bridge the module's supply pins with its local film or ceramic capacitor,** with the shunt between
  the capacitor and the module's return.
- **Give each floating phase its own column** of bootstrap and supply capacitors, at that phase's pins.
  A capacitor of one phase between the pins of another phase breaks the clearance between them.
- **Arrange a capacitor bank by its loop,** not only by its spacing: straight rows of equal polarity,
  each capacitor fed by a similar path.

After every placement change, run a collision audit between parts, whatever their nets. Check pad
against pad, pad against hole, courtyard against courtyard, and body against body on each face. A
clearance check does not see two pads of one net that overlap.

## 5. Small-signal rules

- **Put each decoupling capacitor at its pin**, on the same face, between the pin and the ground it
  returns to. A capacitor a few millimetres away along a thin track decouples little. Bulk capacitance
  can sit further away.
- **Keep the parts that measure next to what they measure.** A sense amplifier, a divider or a filter
  stays near its source or near the converter, whichever lets fewer nets cross a barrier (see the
  typical failures). A divider of a high voltage keeps its high-voltage end in the high-voltage
  region and its low end at the measuring input.
- **Keep sensitive parts away from switching nodes** and from the edges of the high-voltage region:
  references, crystals, amplifier inputs and feedback dividers.
- **Turn similar parts the same way.** Use the same polarity direction and rows on a grid. This helps
  assembly, inspection and routing, and a reviewer reads it as care.
- **Put the SMD parts on one face** when you can: a second reflow side costs money. Agree the test
  side early and keep the test points on it.
- **Keep heat away from electrolytic capacitors**, whose life halves with each step of temperature.
  Spread the hot parts.

## 6. Reference blocks

When a datasheet or a reference board gives a layout for a block (a regulator, a gate driver, a power
module and its capacitors), reproduce it. Do not redraw it by eye.
- **Copy by the pads.** Fit the copied parts so that their pads land on the reference pads (a rigid fit
  over pads with unique names), then copy the reference copper: `fenolite place --from REFERENCE --copper` does both
  (page `placement`). A copy that matches only the part centres can be mirrored or turned without anyone
  noticing.
- **Check the copy** by counting the pads that match the reference within a small tolerance, before you
  route. `fenolite pads` lists the pads of a part in the board frame. `result.reuse.parts` counts the
  pads within `--tolerance`, and `--turn` or `--shift` moves a placed block with its copper.

```fenolite-cmd
fenolite place board --from ref.kicad_pcb --only U1,C1,C2 --anchor U1 --tolerance 0.05mm --copper --drc --dry-run --json
fenolite place board --turn U1,C1,C2 --about 20mm,20mm --angle 90 --dry-run --json
```
- **Show the owner an overlay** of the proposal on the reference before routing, when the owner judges
  the layout against a physical sample.

## Looking

```fenolite-cmd
fenolite neighbors board U1 --radius 5mm --json
fenolite region board --box 10mm,5mm,40mm,30mm --kinds footprint,pad --json
fenolite pads board U1 --json
fenolite analyze board.kicad_pcb --kinds crossings --cut 10mm,20mm,40mm,20mm --width 0.25mm --json
```

`neighbors` lists the parts near one part by courtyard distance. `region` lists what touches a
rectangle. `analyze --kinds crossings` counts the tracks that fit across a barrier (a row of pads, a gap
between regions) on each layer, against the open connections that must cross it. When it reports
`analysis.crossings-short`, move parts before you route. Use them to confirm that a decoupling capacitor is the nearest part to its pin, and that a
keep-out is empty. Render the board (`fenolite render`) after each region is placed, and look at it.

## Typical failures

- **An amplifier in the wrong pocket.** A current-sense amplifier sat in a pocket beside a power
  module's control pins. Its output, its supply and its ground all had to cross the module's pin row,
  and only a few ways existed there. Hours of routing failed. Moving the amplifier next to the
  microcontroller left only the sense pair crossing. That pair is differential, so it tolerates the
  length.
- **A mirrored copy.** A reference block was copied with the part rotations right but the positions
  mirrored, because the reference used the other Y direction. Each resistor sat on the wrong side of its
  pin, and about eighty connections stayed open until a pad-level fit showed the mirror.
- **Parts under a flat part.** Driver parts were placed under the body of a bridge rectifier that lies
  flat. The owner's rule was that nothing goes under it, so the whole driver moved to the other face.
- **A placement that looked improvised.** The owner rejected two placements of an input stage because
  its parts did not sit where a proven reference board had them. The third version, with the parts at
  the reference positions, was approved.

Read next: `board-power`, `board-routing`, `placement`.
