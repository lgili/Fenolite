---
topic: footprints
title: Footprints and symbols written in the script
summary: Footprint and Symbol from dimensions when no library has the part, and what a person must still check against the datasheet.
---

# Footprints and symbols written in the script

When neither the catalog nor a KiCad library has a part, a script can declare its footprint and its
symbol from dimensions. The build writes both into the project's own libraries.

## A script with one authored part

```fenolite-design
from fenolite.dsl import Design, Footprint, Net, Part, Symbol, connect, mm

design = Design("shunt")
design.board(mm(30), mm(20))

# A two-pad land with a silkscreen box and a courtyard. Every number comes from the part's datasheet.
land = Footprint("Local", "Shunt_2512", kind="smd", description="current shunt, two pads")
land.pad("1", at=(mm(-3), mm(0)), size=(mm(1.5), mm(3.2)))
land.pad("2", at=(mm(3), mm(0)), size=(mm(1.5), mm(3.2)))
land.rect((mm(-2), mm(-1.8)), (mm(2), mm(1.8)), layer="F.SilkS", width=mm(0.12))
land.rect((mm(-4.2), mm(-2.1)), (mm(4.2), mm(2.1)), layer="F.CrtYd", width=mm(0.05))
design.add_footprint(land)

# A net tie: two pads of different nets joined on purpose by a copper bridge.
tie = Footprint("Local", "StarPoint", kind="smd", description="net tie of two pads")
tie.pad("1", at=(mm(-0.5), mm(0)), size=(mm(0.5), mm(0.5)))
tie.pad("2", at=(mm(0.5), mm(0)), size=(mm(0.5), mm(0.5)))
tie.line((mm(-0.5), mm(0)), (mm(0.5), mm(0)), layer="F.Cu", width=mm(0.3))
tie.net_tie("1", "2")
design.add_footprint(tie)

# A symbol for it: two pins and a body. Its footprint is the default of every part that uses it.
shunt = Symbol("Local", "Shunt", reference="R", footprint=land.lib_id)
shunt.pin("1", "A", etype="passive", at=(mm(-5.08), mm(0)), length=mm(2.54))
shunt.pin("2", "B", etype="passive", at=(mm(5.08), mm(0)), length=mm(2.54), rotation=180)
shunt.rect((mm(-2.54), mm(-1.27)), (mm(2.54), mm(1.27)))

r1 = Part("R1", shunt.lib_id, value="10m")
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="SENSE")
design.add(shunt, r1, j1)

connect(Net("SENSE_P"), r1[1], j1[1])
connect(Net("SENSE_N"), r1[2], j1[2])

r1.place(mm(18), mm(10))
j1.place(mm(6), mm(10), rot=90)
```

## Footprint

- `Footprint(library, name, kind="smd")` starts a definition; `kind` is `smd` or `through_hole`. Its
  lib id is `library:name` (`land.lib_id`), and `design.add_footprint(land)` registers it. Use a library
  name of your own, not `Fenolite`.
- **The frame** is the footprint's own: its origin is the point that `place()` positions, and `at` is
  measured from it, before any rotation of the part.
- **`pad(number, at=, size=)`** adds a pad; the number is a text. `shape` is `rect` (the default),
  `circle`, `oval` or `roundrect`. In a `through_hole` footprint a pad is drilled and takes `drill=`;
  `kind="np_thru_hole"` makes one pad a hole without plating. A slot takes `drill_shape="slot"`, with
  `drill` as its width and `drill_length` as its overall length; the Altium target refuses slots.
- **One number, several lands.** Pad numbers are unique by default. A second land of the same electrical
  pad repeats the number with `shared=True`.
- **Net ties.** `net_tie("1", "2")` says that pads of different nets are joined on purpose, by copper
  you draw: KiCad's DRC and Fenolite's copper check then judge no pair of pads of the group.
- **Graphics.** `rect`, `line`, `circle` and `polygon` draw on a named layer: `F.SilkS` for the
  silkscreen, `F.Fab` for the body, `F.CrtYd` for the courtyard, the area no other part may enter.
  Draw a courtyard: `fenolite place` and the checks use it to tell whether two parts overlap.
- The build adds the two text fields a KiCad footprint carries, `Reference` above the footprint and
  `Value` below it (page `placement`, field placement).

## Symbol

- `Symbol(library, name, reference="R", footprint=...)` starts a one-unit symbol. `reference` is the
  letter of its references, and `footprint` the default footprint of its parts.
- **`pin(number, name, etype=, at=, length=, rotation=)`** adds a pin. `etype` is the electrical type
  that KiCad's electrical check reads: `passive`, `input`, `output`, `power_in`, `power_out` and the
  others KiCad knows. `rotation` turns the pin, in degrees.
- `rect`, `line`, `circle` and `polygon` draw the body.
- The symbol joins the design through `design.add(symbol)`, like a part.

## What a person still checks

Geometry written from a datasheet is `INFERRED`: nobody has compared it with the real part, and no
check of Fenolite or of KiCad can. Before boards are ordered, a person compares, with the datasheet of
the exact part number:

- the pad positions, sizes and numbering, seen from the top, and which pad is pin 1;
- drill sizes with the plating, for the lead's largest diameter;
- the courtyard and the height of the body against its neighbours;
- the solder paste and mask openings, when the manufacturer asks for other than the default;
- the symbol's pin numbers against the pinout of that package, not of another package of the family.

`fenolite catalog show` gives the same warning for every catalog footprint: its evidence is `INFERRED`.
Say so when you report a board that uses authored or catalog geometry.

## When to author and when not

- A part of KiCad's libraries: name it (page `parts`); do not redraw it.
- A two-pin passive, a header, a common package: look in the catalog first.
- Anything else: author it, and list it for review.

Read next: `parts`, `placement`, `checks`.
