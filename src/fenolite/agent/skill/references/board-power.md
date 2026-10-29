---
topic: board-power
title: Power paths, current and copper
summary: Current loops and loop area, copper sized by a public method, pours as wide straight bands, necks, parallel vias, gate drive, and connectivity after cut-outs.
---

# Power paths, current and copper

A power path has two jobs: to carry its current without overheating, and to keep the area of every
switching loop small. The first is a matter of copper area. The second is a matter of placement, and no
amount of copper fixes it later.

## Loops first

1. **Draw each current loop** on a picture of the board before you draw copper. The loops of a typical
   power stage are:
   - the input loop, from the connector through the filter and the rectifier to the bulk capacitors
     and back;
   - the switching loop, from the DC-link capacitor through the high-side switch, the low-side switch
     and the shunt back to the capacitor;
   - the gate loop of each switch, from the driver output to the gate, then from the source (or the
     emitter) back to the driver.
2. **Make the switching loop the smallest.** Its current changes fastest. Its area sets the voltage
   overshoot on the switches and the noise that the rest of the board receives. Put the DC-link
   capacitor at the supply pins of the switch or the module. Run the supply and the return on top of
   each other (two faces, or two adjacent layers), not side by side with a gap between them.
3. **Close each gate loop at the driver.** The return of a gate loop runs from the switch's source (the
   Kelvin source, when the part has one) to the driver, beside the gate track. It does not run through
   the power ground.
4. **Put the bootstrap and supply capacitors of a driver at its pins.** Their pins swing with the switch
   node. Keep other signals and vias out of the area around them, and keep the clearance that their
   voltage needs.

## Copper for the current

- **Size the copper by a method, not by habit.** IPC-2152 is the public method that relates a
  conductor's current, its cross-section and its temperature rise. Its inputs are the current, the
  temperature rise that the user accepts, the copper thickness, and whether the layer is outer or
  inner. Ask for the current and the accepted rise; do not assume them.
- **Use the right current.** Size the copper for the RMS value of the real, pulsed current at the
  highest operating point, not for power divided by voltage. Measure it at the narrowest section and at
  the pad entries. Compute again whenever the pours, the copper thickness or the stack-up change.
- **Never narrow a power path silently.** When a change makes a path narrower, compare the old and the
  new section, and have the narrower one accepted.
- **Size a via group by the barrels' cross-section**, and check how the current shares between the vias.
- **Measure what you drew.** `analyze` reports the capacity of each track and via for your inputs.
  `--kinds power` measures the resistance and the voltage drop of the copper between two sets of pads,
  pours included. An ampacity is never claimed from a geometry check alone.

```fenolite-cmd
fenolite analyze board/board.kicad_pcb --kinds current --temp-rise 10 --copper-thickness 35um --json
fenolite analyze board/board.kicad_pcb --kinds power --path J1-1 Q1-2 --resistivity 17.2 --copper-thickness 35um --json
```

The temperature rise, the thickness and the resistivity above are examples. Use the user's values.

## Pours that look drawn

- **Use wide bands, not thin tracks, for power.** Shape each power net as a band that follows its path
  in straight runs. Use 45° chamfers at the steps and bevels at the outer corners. Widen each side
  independently, as far as the clearance to the neighbouring band allows. A free-form pour that fills
  every gap looks improvised, and it leaves narrow fingers that carry nothing.
- **Let the build draw the band, the keep-outs and the vias.** The calls below run after placement, so
  they follow the parts; each writes ordinary zones, rule areas, tracks and vias that a rebuild replaces.
  A barrier and a body keep-out are convex; read the build's issues for the pads a barrier encloses.

```fenolite-design
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("power_copper")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="PWR")
j2 = Part("J2", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="HV")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")
design.add(j1, j2, r1)
vin, gnd, hv, hv_ret = Net("VIN"), Net("GND"), Net("HV"), Net("HV_RET")
connect(vin, j1[1], r1[1])
connect(gnd, j1[2], r1[2])
connect(hv, j2[1])
connect(hv_ret, j2[2])
design.rules.netclass("PWR", clearance=mm(0.3), track_width=mm(0.4), via_diameter=mm(0.6), via_drill=mm(0.3), nets=(vin, gnd))  # examples
design.rules.netclass("HV", clearance=mm(0.5), nets=(hv, hv_ret))  # examples
h1 = design.hole("H1", mm(35), mm(25), drill=mm(3.2))
j1.place(mm(6), mm(15))
j2.place(mm(34), mm(10))
r1.place(mm(20), mm(8))
design.zone(gnd, layers=("F.Cu", "B.Cu"))
# One zone along the spine: each side widens to 2 mm where the clearance allows, with 45° steps.
design.band(vin, ((mm(6), mm(16.27)), (mm(6), mm(25)), (mm(28), mm(25))), width=mm(2), max_width=mm(4), layers=("F.Cu",), priority=1)
design.keepout_ring(h1, setback=mm(1))  # no track, via or pour within 1 mm of the drill
design.barrier("HV", setback=mm(2), forbid=("tracks", "vias"))  # a 2 mm band around the HV copper
design.body_keepout(j1, setback=mm(0.5), layers=("B.Cu",))  # nothing under J1 on the bottom
design.fanout_zone(gnd)  # a track and a via from each top SMD pad of GND to its bottom pour
design.stitch_pieces(gnd, pitch=mm(4))  # vias that tie the two GND pours together
```

- **Find the necks.** The narrowest point of a band sets its capacity: a gap between two pads, a row of
  vias, the spokes of a thermal relief. Measure there, not at the widest part. Widen a neck, or add a
  parallel path on the other face.
- **Thermal reliefs on power pads** cut the current path to the width of their spokes. Agree with the
  owner whether a power pad is connected solid (better for current, harder to solder by hand) or with
  wide spokes.
- **Change layers with vias in parallel.** One via carries far less than a band. Use an array, spread
  across the band's width, near the part that the current leaves.
- **Remove copper that carries nothing.** Remove isolated islands, fingers that end nowhere, and pour
  far from any connection. Dead copper does not cool much, and it shortens clearances.
- **Share the current in a bank.** In a bank of parallel capacitors, give each capacitor a similar
  path. The nearest capacitor of a lopsided bank takes most of the ripple current and ages first.

Measure these with `analyze`. `necks` finds the places narrower than a `[[neck]]` row of the user's
requirements, `loops` measures the area of each `[[loop]]` row, and `balance` compares the copper at the
two pads of each two-pad part. `--split` gives each parallel path and via its share of a path's current.
`--loop-baseline` gives each loop's change against an earlier board.

```fenolite-cmd
fenolite analyze board.kicad_pcb --kinds necks,loops,balance --requirements req.toml --json
fenolite analyze board.kicad_pcb --kinds power --split --path J1-1 Q1-2 --copper-thickness 35um --json
fenolite analyze board.kicad_pcb --kinds loops --requirements req.toml --loop-baseline before.kicad_pcb --json
```

## Heat

- **Decide the heat path from a loss budget** before the layout freezes: which part goes on the heat
  sink, which one cools into copper, and at what ambient.
- **Give a part without a heat sink the largest copper**, assigned per pin, with a grid of vias to the
  other face. Rate a rectifier without a heat sink by its free-air rating, not its rating on a heat
  sink, and plan a thermal test.
- **Spread heat into copper.** A part with a thermal pad needs its pad copper connected to an area on
  the same face, with vias to the other face when the datasheet asks for them. Compute a regulator's
  dissipation, and size its copper for this board.
- **Keep heat sources apart** from each other, and away from electrolytic capacitors, relays,
  magnetics and the analog parts whose reading must not drift.
- **Check each bulk capacitor's ripple current** at the real frequency and with the real sharing,
  against the part that is fitted.
- **Measure, then decide.** Ask for the temperature limit of each hot part. Report the copper area that
  each part has; do not claim a temperature that nothing computed. Copper area is a proxy: schedule
  temperature measurements on the hot parts.

## After pours and cut-outs

Pour cut-outs, keep-outs and slots remove copper. After every change to them, check that every pad of a
poured net is still connected, and that each band is still continuous. A rule check that runs only on
the copper you drew, without the cut-outs, misses this. `fenolite net` lists the open connections of a
net; `analyze --kinds connectivity,dead` pours the zones again and lists cut-off pads and dead copper.
- **Refill and check before any output or measurement.** The saved fill is what gets fabricated. An
  outline edited after its last refill holds an old fill, and every distance, connection and current
  measured on it is wrong.
- **Keep a pour out of an area with a pour cut-out,** not with a drawing on a keep-out layer that the
  pour may ignore.
- **Look at the refilled pour:** the relief spokes, the slivers, the slits and the acute tips.
- **Judge a change of a switching path by its loop inductance**, not by its milliohms.

```fenolite-cmd
fenolite net board DC_BUS --json
fenolite fill board --dry-run --json
fenolite analyze board.kicad_pcb --kinds connectivity,dead --dead-distance 5mm --json
```

## Priorities between power and signals

When power copper and a signal compete for the same face, the power copper normally wins, and the
signal moves. Agree this with the owner once, then apply it everywhere. One owner put it this way:
"if someone has to change face, it is the signals".

## Typical failures

- **A rectifier pin left open.** Pour cut-outs under a bank of capacitors removed the only copper that
  joined a rectifier pin to the bus. A preview model without the cut-outs showed the pin connected. The
  fix was a neck on the other face, fed from an area below the bank, and a rule script that checks the
  connectivity with the cut-outs applied.
- **A switching loop closed late.** The DC-link film capacitor first sat away from the power module. It
  was moved next to the module's positive supply pin, with the shunt turned to sit beside it on the
  module's side. The loop of capacitor, module and shunt became as short as the parts allow.
- **Pours rejected as "free-form".** Pours generated to fill every free area were rejected by the
  owner. Thick straight bands with chamfered steps, the same nets and the same clearances, were
  accepted.

Read next: `board-grounds`, `board-routing`, `rules`.
