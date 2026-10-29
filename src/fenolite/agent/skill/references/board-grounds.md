---
topic: board-grounds
title: Grounds, ties and current sensing
summary: Ground domains, one tie between two domains and where it goes, Kelvin sensing, return paths, proving a single tie, and the commands that show a net.
---

# Grounds, ties and current sensing

In the schematic, "ground" is one symbol. On a board it is a set of copper areas that carry very
different currents. The power return carries amperes that switch in nanoseconds. The control ground
carries milliamperes and must stay quiet, because every measurement is made against it. A board is
good when the large currents stay on their own copper, and the two areas meet at one chosen place.

## Domains

- **Name the ground domains**, at least: the power ground (the return of the power stage and of the
  bulk capacitors), the control ground (microcontroller, amplifiers, references), the protective earth,
  and each isolated ground behind an isolation barrier. The schematic may show them as one net joined
  by a net tie. That tie is the place where they meet.
- **Give each domain its own copper.** The control ground is a plane or a pour under the control
  region. The power ground follows the power path. Neither one runs through the other's region.
- **Keep earth separate.** Protective earth joins the other grounds only through parts that the design
  intends (Y capacitors, a discharge path) and only where the safety design puts them.

## One tie, at the right place

- **Join two domains at exactly one place.** A second connection makes a loop. The power current then
  shares the control copper, and the control ground moves with it.
- **Choose the place by the measurement.** With a low-side shunt, the control ground must equal the
  shunt's ground end, because the current is measured against it. Tie the two grounds at that end of
  the shunt, next to the control ground pin of the driver or the module. Do not tie them at a bulk
  capacitor or a connector that happens to be near.
- **Draw the tie as a short, defined piece of copper.** In the schematic, use a net-tie part (see
  `footprints`, `net_tie`), so the tie is visible and intended. Every other place where the two areas
  come close keeps the clearance between them.
- **Put the supplies on the control side.** A switching supply's output and its return belong to the
  control domain. Its primary side belongs to the power domain, and it returns to the bulk capacitor,
  not to the control ground.

## Proving a single tie

A rule check sees one net and cannot tell one tie from three. Prove it yourself:
1. Remove the tie, and only the tie, from a copy of the board. Remove it by its exact geometry: the
   track, the arc or the net-tie copper. Do not remove everything that touches its area, because that
   also drops neighbouring copper and can make a second tie disappear.
2. Compute the connected copper of the ground net. You must find exactly two separate groups: the
   power ground and the control ground.
3. List the pads of each group. Every pad that is on the wrong side is a second tie, or a part that
   is connected to the wrong ground.

`fenolite analyze --kinds ties` runs these three steps without a copy. `--tie REF` removes a net-tie
part's pads, and `--tie-item ID` removes tracks, vias or zones by id or KiCad uuid. The row lists the
groups and their pads. One group is `analysis.tie-parallel`, with the other path item by item. With
`--domains PWR=Q*,CTL=U*`, a pad on the wrong side is `analysis.tie-extra`. `fenolite net` lists the pads,
the copper, the vias and the open connections of a net.

Run this test again after every change to pours, bands or power copper, as a regression test. A refill
that floods past a gap creates a second tie, and no other check notices it.

- **Anchor each intended ground connection in drawn copper,** not in pour fill. A pour that is refilled
  with another clearance or priority can drop the connection, or make a new one.
- **Keep the copper of two ground groups apart** wherever they may meet only at the tie, and do not let
  a pour grow automatically into that gap.
- **Count the parts as well as the copper.** A capacitor whose two pads sit on the two ground groups is
  a tie too. Either it is the intended one, or it is a second one.
- **Give each decoupling capacitor a direct ground via,** not one thermal spoke. Join a control ground
  pour to its other face with several vias, not one.

```fenolite-cmd
fenolite analyze board.kicad_pcb --kinds ties --tie NT1 --domains PWR=Q*,CTL=U* --json
fenolite analyze board.kicad_pcb --kinds domains --barrier U5 --json
fenolite analyze board.kicad_pcb --kinds ties --sense ISENSE_P,ISENSE_N --json
fenolite net board GND --json
fenolite pads board R10 --json
```

## Kelvin sensing

- **Take the sense voltage from the shunt's own pads,** at the inner edge of each pad, with a dedicated
  pair of tracks. This pair carries no power current. A sense track that leaves from the power copper
  a few millimetres away measures that copper too.
- **Route the pair together:** parallel, close, on one face, with the same number of vias, from the
  shunt to the amplifier's inputs. Put the filter at the amplifier.
- **Count the barriers that the pair must cross** before you place the amplifier. A differential pair
  tolerates length. A single-ended output, its supply and its ground crossing the same barrier do not
  (`board-floorplan`, typical failures).
- **Give the sense return its own net,** joined to the ground net by a net tie at the shunt's pad. Then
  no rule and no pour can merge it with the power return somewhere else. `fenolite analyze --kinds ties
  --sense ISENSE_P,ISENSE_N` names every place where a sense net touches other copper
  (`analysis.sense-shared`).
- **Reference the amplifier's ground to the shunt's low side,** and keep the generated pours off the
  sense tracks and their vias. A fragment of pour that hangs on a sense track or a tie track becomes an
  antenna, or a second tie.
- **Use a four-terminal shunt** when it exists. Its sense pins are the Kelvin connection.

## Return paths

- **The return of a signal runs under it**, on the nearest plane. A signal routed across a gap or a
  split in that plane forces its return around the gap. That makes a loop antenna, and the result is
  noise or emissions.
- **At a layer change,** put a ground via next to the signal via, so that the return can change layer
  too.
- **Stitch the planes of a domain** with vias along their edges and through their area, so that the two
  faces act as one.
- **Do not stitch across domains.** A stitching via in the gap between two domains is a second tie.
- **`role_copper(ground_layers=...)` pours a plane per ground layer** (`B.Cu` on 2 layers, `In1.Cu` on 4)
  and stitches the planes at `stitch_pitch` (5 mm, at least two vias per overlap); pick a pitch from your
  highest significant frequency, not from the default.

```fenolite-cmd
fenolite analyze board.kicad_pcb --kinds returns --net CLK --net SPI_* --via-distance 1mm --json
```

`analyze --kinds returns` finds each track that crosses a gap of its plane (`analysis.return-split`, with
the span and its two ends) and each via without a reference via near it (`analysis.return-via`). Fill the
zones first: only stored fill counts as reference.

`fenolite roles PATH --check` does the same for every gate net and every signal declared sensitive
(`design.net_role(net, "signal", sensitive=True)`), against the ground nets, and reports
`roles.return-gap` instead.

## Typical failures

- **Ties in more than one place.** The control ground of a board met the power ground at a bulk
  capacitor terminal, besides the place near the shunt. After the rework, the only tie is a short track
  from the shunt's ground end to the module's control ground pin, beside the sense pair. Removing that
  one track now leaves only the expected power parts on the power side: the rectifier, the bulk and film
  capacitors, and the shunt.
- **A tie that a refill undid.** In a later round, a refilled pour flooded the signal-ground pins of a
  power module and made a second tie. The expected error of the current reading more than doubled. The
  single-tie test, run again, found it, and it has run after every copper change since.
- **A tie test that tested another board.** A first tie test removed every track that touched the
  tie's area. It dropped neighbouring tracks as well, so its answer described a board that did not
  exist. Removing exactly the tie's own copper gave the real answer.

- **Sense lines taken from power copper.** A review found the shunt's sense lines leaving from the power
  copper beside the shunt. The rework takes both lines from the shunt's own pads, as a tight symmetric
  pair, with the sense return on its own net and a net tie.

Read next: `board-power`, `board-routing`, `board-insulation`.
