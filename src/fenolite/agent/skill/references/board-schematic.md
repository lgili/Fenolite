---
topic: board-schematic
title: Schematic and parts for a sound board
summary: One master for every change, net classes on the wire, connectivity by pin sets, a clean drawing, ratings with their conditions, parts from references.
---

# Schematic and parts for a sound board

The board is drawn from the schematic. A fault in the schematic reaches the board, and a fix made only on
the board is lost at the next update. Many faults that a layout review finds were born on a sheet.

## One master

- **Make every change in the schematic.** Change nets, values and part numbers there, and derive the
  board, the bill of materials and the position file from the compiled design. Never fix a net only on
  the board, or a value only in a spreadsheet.
- **Predict each update before you run it.** List the nets, parts and footprints that it should change,
  compare that list with what the update proposes, and stop on any difference.
- **Compare connectivity by pin sets, not by net names**, after every edit and every import. Index the
  comparison by pins and include single-pin nets. A net name can survive a broken connection; a pin set
  cannot.

```fenolite-cmd
fenolite parity board --json
fenolite netlist board --min-pins 1 --json
fenolite equivalent before/board.kicad_pcb after/board.kicad_pcb --json
```

## Net classes and names

- **Put each net class on the schematic,** on the net's own wire, so that every update carries it to the
  board. A class that exists only on the board is removed by the next update. Its nets are then checked
  at the default clearance, and no check says so.
- **Name every net that a rule, a test point or a script refers to.** Never scope a rule by an
  automatic net name: an update renames it, and the rule then holds for nothing. When you rename a net,
  change its labels, ports, classes and rule scopes in the same edit.
- **Draw the isolation barrier** on every sheet that holds both sides, as a line through the isolating
  parts, with each side labelled. Give each reference ground its own symbol. On a sheet whose control
  ground is at mains potential, say so: a programming tool must then be isolated.

## A clean drawing

- **Put every object on the house grid,** and make the connection points coincide exactly. An end that
  is off by a fraction of a grid looks connected and is not.
- **Wire local circuits,** and use net labels only between groups and sheets. Use one power-port style
  per net: grounds down, supplies up.
- **Keep connections unambiguous:** no four-way junctions, no wire over another wire, no dot where no
  junction is meant.
- **Show the value of every part.** Mark every part that is not fitted the same way everywhere (DNP),
  and keep the purchasing data in the part's parameters.
- **Write only true notes.** A note that describes a protection the drawn circuit does not implement is
  worse than none. Generate tables such as the microcontroller pin map from the netlist.
- **Keep the title block honest:** a fixed issue date, and the revision taken from one project
  parameter.
- **Draw repeated channels identically,** at a regular pitch.
- **Flag every part whose pins all land on one net.** Remove it, mark it DNP, or document it, for example
  as an intended return junction.
- **Keep the electrical rule check strict.** Waive only one specific check on one object, with a reason.
- **Make the pin-to-pad map explicit and tested** whenever symbol and footprint numbering differ.
  Swap pins on an instance only between pins that the datasheet calls equivalent, and record the swap.
  An update of the symbol from its library undoes the swap.

## Ratings and protection

- **Rate each bus part for DC.** Every part on a DC bus or an inverter output needs a DC rating and a
  rating for its real peak stress. An AC rating does not cover DC: a fuse or a relay that interrupts DC
  needs a DC breaking rating.
- **Read every rating with its kind and its test condition.** The 1 mA voltage of a varistor is not its
  continuous rating. The standoff voltage of a TVS diode is not its clamping voltage. An optocoupler's
  transfer ratio is given at a test current, not at your drive current.
- **Rate the resistors of a high-voltage divider** for working voltage as well as power, one resistor
  at a time. Apply the same check to every similar divider on the board.
- **Choose each clamp against the input it protects:** its absolute maximum and its normal range. Do not
  copy another channel's clamp.
- **Put the fuses in order.** The mains fuse comes first after the line terminal, before the surge
  parts, the filter and any tap. The bus fuse comes ahead of every DC load. Check each fuse's I²t against
  the surge and against the copper it protects.
- **Make the safe state the default.** Every power-stage command and relay driver gets an external pull
  to its off state, so that a microcontroller in reset leaves the outputs off.
- **Do not silently disable a protection** that the power stage offers, such as a module's fast
  overcurrent input. If it must be tied off, record why, and show how the firmware protects in time.

## Parts copied from a reference design

- **Know why each part exists** in the reference before you copy it, and whether your board has the same
  condition.
- **Check the reference's CAD against its production bill of materials.** A donor project may hold
  another microcontroller or other supplies than the product that was built.
- **Treat the microcontroller pin map as a firmware contract.** Compare it pin by pin, with the series
  resistors and pulls, and record every difference.
- **Recompute the surrounding values** when you replace a part by another type.
- **Treat an alternate part as unqualified** until its package, pinout, polarity and rated conditions
  match. Buy by manufacturer part number. Check every selection and alternate against the user's
  excluded manufacturers.
- **Generate one bill of materials** from the frozen design, with its fitted variant. Exclude fiducials
  and test points from it on purpose, not by accident.

## Typical failures

- **Classes lost in an update.** Several high-voltage nets had their class only on the board, because the
  class markers sat a grid step away from the wire. The next update removed the classes, and those nets
  were checked at the default clearance without any warning.
- **A floating pin that no check showed.** A comparison that ignored single-pin nets hid a divider pin
  left floating. That pin cut both the bus voltage sensing and the discharge path of the capacitor bank.
- **A fuse in the wrong place.** The input fuse sat after the common-mode choke, as in an older design.
  The review rejected it, and it was moved to directly after the mains terminals.
- **A bus interrupter rated for AC only.** The only hardware interrupter on the DC bus had AC ratings
  alone, which say nothing about breaking a DC fault.
- **Line and neutral crossed in a part.** A pin-to-pad map that nobody tested crossed line and neutral
  through the windings of the choke.

Read next: `board-practice`, `board-emc`, `parts`.
