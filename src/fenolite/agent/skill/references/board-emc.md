---
topic: board-emc
title: EMC, surge and protection on the board
summary: An immunity basis first, the mains entry in order, filter sides kept apart, the earth bond in copper, staged pin protection, gate buses and analog lines.
---

# EMC, surge and protection on the board

Emissions and immunity are decided by placement and copper long before the first test. A board that
passes every rule check can still fail its conducted-emission or surge test, because no rule describes
which copper is noisy and which copper must stay quiet. This page gives the habits that make the test
likely to pass. Only the test closes an EMC requirement.

## A basis first

- **Agree the immunity levels before you choose a clamp:** the ESD, fast-transient and surge levels of
  the product's standard. Without them, surge copper and clamp ratings are guesses.
- **Agree the emission limits** and the test set-up, including the real earth connection of the
  product. Plan the EMC tests on the assembled prototype.
- **Never declare EMC compliance from geometry.** An EMC requirement that has no layout criterion is
  closed only by test.

## The mains entry

1. **Order the parts along the line:** fuse, then the surge parts (varistors, gas arresters), then the
   X capacitor and the common-mode choke, then the rest. A fuse placed after the filter leaves the
   filter and the surge parts unprotected (`board-schematic`, "Ratings and protection").
2. **Coordinate the surge network as a whole.**
   - Put a fuse upstream of every varistor and of every varistor-arrester string.
   - Connect a varistor to earth only in series with a gas arrester.
   - Check the arrester's sparkover against the dielectric test voltage.
   - Do not compare surge energies measured with different pulse shapes.
3. **Keep the raw side and the filtered side apart** on every layer. No parallel run close by on one
   face, and no overlap through the board on the other face: cut the pours where the two sides overlap.
   A few picofarads across the choke undo its attenuation.
4. **Keep line and neutral in the order of the choke's windings**, so that they do not cross on the raw
   side.
5. **Use a slot to steer the current.** Where the choke and the bulk capacitors sit side by side, a
   routed slot between them forces the alternating current through the intended path, and adds
   creepage.

## Earth

- **Make the functional earth bond exist in copper:** short, wide, with several vias, from the earth
  terminal to the returns of the Y capacitors and the arresters. An earth terminal with no copper bonds
  nothing.
- **Compare the earth path by impedance** with a proven reference, not by copper length alone. A long
  earth path can resonate with the Y capacitors inside the conducted-emission band.
- **Recompute the leakage current** whenever the Y capacitance grows, at the highest mains voltage,
  and confirm it in test.
- **Say which metal is protective earth and which is functional earth**, and keep both decisions in
  the design notes.

## Protection at the pins

- **Protect an exposed input in stages:**
  - a primary clamp at the connector, returning to that connector's own domain;
  - a series resistor;
  - a secondary steering clamp next to the pin.
- **Check a new series resistor against the pulls** already on the line. The divider they form must
  still give valid logic levels.
- **Do not put clamps everywhere.** A TVS diode on a switching or mains node can do harm.
- **Reserve unfitted footprints** where adding a part later would need a new board. Examples are small
  phase-to-phase capacitors near the output connector, and the input filters that a power module's
  application note recommends. "Cheap now, impossible later." Note the loss that each one would add
  when fitted.

## Gate drive and analog lines

- **Route gate-drive lines short and together**, at a constant pitch, away from the bootstrap nodes.
  Put a return plane under the gate bus, tied to the module's logic ground where the inputs return. Send
  any gate route several times longer than its straight distance to the owner for review.
- **Keep analog lines off long parallel runs** beside aggressors: phase outputs, gate lines, bootstrap
  nodes, the switch node of a supply. Analog lines include current sense, voltage sense, temperature,
  reset and communication. Route them over a continuous return. `analyze --kinds coupling` ranks the
  pairs by parallel run and overlap; `--kinds returns` finds tracks across a gap of their plane.
- **When a sense line must run beside an aggressor**, put the slowest, most filtered signal next to it.
  Keep the RC filter at the converter pin, and have the firmware sample away from the switching edges.
- **Cross a power-return trunk at 90°**, and keep any parallel run beside it short.
- **Route a signal of a safety-extra-low-voltage interface only over its own reference**, never over a
  ground that is at mains potential.

```fenolite-cmd
fenolite analyze board/board.kicad_pcb --kinds length --net "GATE_*" --json
fenolite net board GATE_UH --json
fenolite analyze board.kicad_pcb --kinds coupling --aggressor 'PWM_*' --victim 'TEMP_*' --json
fenolite analyze board.kicad_pcb --kinds returns --net 'ISENSE_*' --reference GND --json
```

`--kinds length` gives the routed length of each gate line. Compare it with the straight distance
between its ends.

## Loops

- **Compare loop versions by inductance**, not by projected area. A figure-eight loop has a large area
  and a small inductance. An inductance estimate needs only the loop's path. Check it once against a
  square loop of known inductance.
- **Measure each loop along its designed return path:** the bootstrap, the supply decoupling, the
  snubber, the supply's switch node. Compare it with a proven reference board.

## Typical failures

- **An earth terminal bonded to nothing.** In one candidate layout, the earth terminals had no copper.
  A simulation of the filter with and without the bond showed a large loss of attenuation above a few
  megahertz.
- **A varistor rated below the mains.** The continuous rating of the line-to-neutral varistor was below
  the highest line voltage of the design. A parts registry had listed its 1 mA voltage as its mains
  rating.
- **Long gate inputs without filters.** The drive inputs of a power module ran about twice as far as on
  the reference board, with no place for the recommended input filter. The reviewer asked for unfitted
  pads, because they cost nothing now and are impossible to add later.
- **A temperature line inside the gate bus.** A module's temperature line ran a long way beside a PWM
  line at a tiny gap. Moving the dividers and reordering the lines removed almost all of the coupling.
- **A loop that looked worse and was better.** By area, a new capacitor loop seemed four times larger.
  The old loop had been a figure eight, and by inductance the new one was about a third smaller.

Read next: `board-routing`, `board-grounds`, `board-schematic`.
