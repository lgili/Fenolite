---
topic: board-insulation
title: High voltage on a board: clearance and creepage
summary: Insulation domains, the inputs that set a distance, slots and grooves, copper under parts and on both faces, measuring with analyze, and what not to claim.
---

# High voltage on a board: clearance and creepage

A board that carries mains or a high DC bus must keep each hazardous domain away from the others and from
anything a person can touch. Two distances do this. **Clearance** is the shortest path through air.
**Creepage** is the shortest path along a surface. A rule check that knows only one copper-to-copper
clearance per net class judges neither of them: a board can pass its own clearance rules with no finding
and still fail creepage.

## First: domains, not nets

1. **Classify by barrier, not by voltage.** A domain is a set of nets that no insulation separates. A
   controller that is not isolated from the mains is itself hazardous, even at 3.3 V: its ground, its
   test points and its programming port are all at mains potential.
2. **List the domains.** Typical domains are: the mains input, the rectified bus, each floating phase
   with its gate-drive supply, the control area, an isolated interface, and protective earth. Each net
   belongs to exactly one domain, and so does every piece of metal: screws, heat sinks, standoffs, and
   copper on no net.
3. **Decide the grade of each pair of domains:** functional, basic, supplementary or reinforced. This is
   a product decision, taken from the product's standard and its insulation coordination, not a layout
   choice. Ask for it, and record who gave it.
4. **Derive the working voltage of each pair from the real topology.** Use the highest of normal
   operation and of single faults: an open fuse or an open resistor in a series string moves the
   voltage. Decide, and write down, whether a switching node is classed by its RMS or by its peak value.
5. **Collect the other inputs of the distance:**
   - the overvoltage category or the rated impulse voltage;
   - the pollution degree;
   - the material group of the laminate, from its comparative tracking index;
   - the altitude of use.

   IEC 60664-1 is the public method that turns these inputs into a clearance and a creepage. A product
   standard may ask for more.
6. **Write the minima into a requirements file**, one pair of domains per row, each row naming its
   source. Fenolite measures against that file and holds no limit of its own. Leave a margin above each
   minimum for the tolerances of fabrication.

## Rules in the CAD tool

- **Never relax a class rule to make a layout pass.** When a narrow exception is needed, make it a
  scoped rule with a reason and an approval, never a lower class value.
- **Audit the scope and the priority of the rules.** A broad rule with a higher priority can silently
  override a class rule.
- **Give pours a larger clearance than tracks at a barrier.** A pour's edge moves at every refill.
- **Scope the rules for cut-outs and slots on purpose,** and check them in the final tool.

## Layout that makes the distances

- **Keep each domain in one region** of the board, with straight borders between regions. A border that
  zigzags around parts creates many short paths.
- **Order the domains** so that the two most distant ones never meet: mains next to the bus, the bus
  next to the switches, and the control area beyond the switches' gate-drive side.
- **Use a slot to add creepage.** A milled slot through the board lengthens the surface path between
  two pads. Check four things:
  - the slot is wider than the standard's minimum groove width for the pollution degree, because a
    narrower groove is bridged;
  - its ends reach past the copper on both faces;
  - no pour on the other face, and no via, bridges the path around its end;
  - the path down the slot wall and along the other face is counted too.

  Remove a slot that no longer separates anything.
- **Check the distances inside parts that span two domains.** An optocoupler, an isolator, a
  transformer, a relay or a power module sets the distance between its own pins. Choose the package for
  it, keep the board's copper from shortening that distance, and add a slot under the body where its
  pitch is too short.
- **Treat metal as a conductor.** Screws, washers, standoffs, heat sinks, shields and the cans of
  electrolytic capacitors are conductors; a can's sleeve is not insulation. Give each piece of metal a
  domain, or a keep-out around it sized from the screw head and the washer. Metal that floats between
  two domains bridges them: sum the two gaps.
- **A copper ring around an unplated hole is a new conductor.** Give it a class, or remove it.
- **Keep high voltage off the face under a part** whose body sits on the board, such as a capacitor
  can, a relay or a heat sink. Make the pour cut-outs real, so that a refill cannot bring the copper
  back. `analyze --kinds bodies` lists the copper under each body against your `[[body_copper]]` rows.
- **Mind the second face and the inner layers.** A distance on the top face says nothing about the
  bottom face. Inner layers of a multilayer board follow the rules for distance through insulation,
  not creepage. Check the distances across layers too.

## Measuring

```fenolite-cmd
fenolite analyze board/board.kicad_pcb --kinds clearance,creepage --pair DC_BUS GND_CTRL --json
fenolite analyze board/board.kicad_pcb --kinds clearance,creepage --within 3mm --requirements board/insulation.toml --groove-width 1mm --json
fenolite analyze board/board.kicad_pcb --kinds insulation --requirements board/insulation.toml --json
```

- **Measure the filled board.** Pours change every distance. Fill the zones first, and measure the file
  that will be fabricated.
- **`--pair` measures one pair of nets, and `--within` every pair closer than a distance.** A finding
  exists only against your `--requirements`. In the second line, 1 mm and 3 mm are examples.
- **`--groove-width` is the width below which a groove is bridged.** It comes from your inputs, not from
  Fenolite.
- **Measure pads as well as tracks:** through-hole leads, exposed pads, mounting holes.
- **Report the reply's evidence level** and the items it left out (`analysis.input-missing`).
- **Give the working voltage as a role.** `design.net_role(net, "power", voltage=volt(400))` (an example
  value) makes `fenolite roles PATH --check` measure that net's distances against your rows;
  `roles.limit-missing` says that no row covers it, since Fenolite ships no table.
- **Look at the worst pairs.** Check by eye that the path the tool found is the real one
  (`fenolite render`, `fenolite region`).
- **Put the material group into the fabrication order.** Give the laminate's material group, or its
  tracking index, and say that the fabricator may not substitute another. A creepage figure assumes a
  material group; the board must be made of it.

## What not to claim

A measurement shows that the distances in this file are above the minima that someone wrote. It does not
show that the product complies. The grade, the working voltage, the pollution degree and the standard
are the inputs of that judgement, and the person who signs for it makes it. Write "measured against the
configured minima", give the source of each minimum, and list the limits of the model: the path through
air above components, coating, and distances inside parts are not modelled.

## Typical failures

- **Clean clearance rules, failed creepage.** A board passed its own clearance rules with no finding and
  failed creepage in review, including between the pins of single parts. Its class rules came from an
  earlier design and were below the table the reviewer used.
- **A bus pour under capacitor cans.** The pour for the rectified bus ran on the face under the bulk
  capacitors, under their metal cans. The review rejected it. The fix was cut-outs under each can, and
  moving the bus to the other face.
- **A model that ignored the cut-outs.** A preview model ignored the pour cut-outs under the cans, so its
  distances and its connectivity were wrong. One rectifier pin was really left unconnected on the board.
  Measure with the cut-outs applied, and check the connectivity again after any cut-out.
- **A material group nobody ordered.** Every creepage figure assumed a laminate material group. That
  group appeared only on a drawing that the fabricator never received.

Read next: `board-grounds`, `rules`, `board-review`.
