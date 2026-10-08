---
topic: placement
title: Placing parts
summary: place() in the script, staged parts and the grid strategy, moving a part on the board, where the pads are, and text fields.
---

# Placing parts

A part gets its position in one of three ways: `place()` in the script, `fenolite place` on the built
board (`place --strategy grid`, `place --move`), or a person in KiCad. Whatever is on the board wins at the next build, so they do not fight.

## In the script

```fenolite-design
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("placed")
design.board(mm(30), mm(20))
design.rules.minimum(clearance=mm(0.2), track_width=mm(0.2), edge_clearance=mm(0.3))  # examples

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="PWR")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:Chip_0603", value="LED")
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="100n", height=mm(1))
tp1 = Part("TP1", "Fenolite:Terminal_1Pin", footprint="Fenolite:TestPoint_SMD_D1.0", value="GND")
design.add(j1, r1, d1, c1, tp1)
vin, led_a, gnd = Net("VIN"), Net("LED_A"), Net("GND")
connect(vin, j1[1], r1[1], c1[1])
connect(led_a, r1[2], d1[1])
connect(gnd, d1[2], j1[2], c1[2], tp1[1])

j1.place(mm(6), mm(9), locked=True)  # the connector stays where the enclosure wants it
r1.place(mm(15), mm(14))
d1.place(mm(15), mm(6), rot=180)
tp1.place(mm(24), mm(10), side="bottom")
# C1 has no place(): the build stages it beside the board, for `fenolite place`.

r1.field("Reference", outside="top")  # beside the courtyard, clear of the pads
d1.field("Value", visible=False)

design.near("led", d1, r1.pad(2), within=mm(10))  # D1 keeps a pad within 10 mm of R1's pad 2
corner = [(mm(25), mm(15)), (mm(30), mm(15)), (mm(30), mm(20)), (mm(25), mm(20))]
design.rule_area("ANT", corner, layers=("F.Cu",), forbid=("footprints",))  # no part on the front here
lid = [(mm(10), mm(1)), (mm(20), mm(1)), (mm(20), mm(4)), (mm(10), mm(4))]
design.rule_area("LID", lid, layers=("F.Cu",))
design.height_limit("LID", max=mm(5))  # parts under LID stay at most 5 mm tall
```

- **`part.place(x, y, rot=0, side="top", locked=False)`**, once per part. `x` and `y` are lengths from
  the outline's top-left corner, Y down, and they position the footprint's own origin. `rot` is the
  footprint's angle in degrees, as KiCad stores it. `side` is `top` or `bottom`.
- **`locked=True`** is the placement lock: `fenolite place` refuses to move the part (`place.locked`).
- **A part without `place()`** is staged: the build puts it in a row 5 mm to the right of the outline
  and reports `layout.unplaced` (warning). `result.staged` of `build` lists these parts.
- **`design.near(key, parts, anchor, within=…)`** is a placement rule: each part of `parts` keeps a
  pad within `within` of a pad of `anchor`, centre to centre. Each side is a part, `part.pad(n)`, a
  module or a list of them; use it for a decoupling capacitor, a crystal, a gate driver. `build` and
  `place` report a part that is too far as a warning (`placement.too-far`); `fenolite check` makes it
  an error (stage `placement.rules`, page `checks`). No placer moves a part to meet a rule.
- **`design.rule_area(name, outline, layers=…, forbid=("footprints",))`** keeps parts out of a
  polygon: `F.Cu` judges the parts on the top side, `B.Cu` those on the bottom. A courtyard that
  enters the area gives `place.keepout`, a warning in `build` and a refusal in `place`.
- **`Part(..., height=mm(h))`** states how tall a part is: the build gives its footprint a body of that
  height, kept in `.fenolite/`. **`design.height_limit(area, max=…)`** limits the parts under every rule
  area of that name. A part above the limit gives `placement.too-tall`, a part without a stated height
  under it `placement.height-unknown` (a warning): warnings in `build` and `place`, gated by `check`.
- Place first what the mechanics fix (connectors, holes, anything that meets the enclosure), then the
  parts with the most connections, then their passives next to the pins they serve.

## On the board

```fenolite-cmd
fenolite place blink/build --strategy grid --dry-run --json
fenolite place blink/build --strategy grid --only C1,C2 --gap 1mm --margin 2mm --confirm --json
fenolite place blink/build --move R1=15mm,15mm,90 --dry-run --json
fenolite place blink/build --move R1=15mm,14mm --move D1=15mm,6mm,180,bottom --confirm --json
```

- **`--strategy grid`** puts every part that lies off the board onto it, on a grid, without overlap. It
  knows nothing about the circuit: it is a legal start, not a layout. `--only` names the parts,
  `--pitch` the grid step, `--gap` the space kept around a part and `--margin` the distance kept from
  the outline. A part already on the board is not moved.
- **`--move REF=X,Y[,ROT[,SIDE]]`** moves one part, in the frame of `place()`: `R1=15mm,14mm` is where
  `r1.place(mm(15), mm(14))` puts it. The option repeats, and the lengths carry a unit.
- `result.moved` gives each part's position before and after, in file coordinates (the outline's
  corner is at 100 mm, 100 mm).
- `result.rules` counts the `near` rules judged after the moves, and `result.measures` gives the wire
  length (`hpwl`, `ratsnest`, in nm) and a congestion estimate, with `change` against the layout
  before: compare two placements with them before routing.
- **Refusals** (exit 5, nothing written): `place.locked` for a locked part, `place.courtyard-overlap`
  when two courtyards would overlap, `place.keepout` for a part in a rule area that forbids
  footprints, `place.outside-outline` and `place.edge-clearance` near the board edge, `place.no-room` when the grid finds no free spot. `--force` writes an illegal placement
  and moves a locked part; use it only when you know why.
- **Copper does not follow.** A moved part leaves its tracks where they were (`place.copper-left`,
  warning). Route again with `--rip` afterwards (page `routing`).
- The script does not change. `fenolite sync --to-source` writes the positions beside it (page
  `design-script`).

## Where things are

```fenolite-cmd
fenolite pads blink/build D1 --origin 100mm,100mm --json
fenolite pads blink/build R1 2 --origin 100mm,100mm --json
fenolite neighbors blink/build R1 --radius 10mm --json
fenolite region blink/build --box 110mm,102mm,120mm,110mm --kinds footprint,pad --json
```

- **`pads`** lists each pad with its `position`, `layers`, `net` and `index`. With
  `--origin 100mm,100mm` the positions are in the frame of `place()`, so they go into `design.track` as
  they are. Without it they are file coordinates. Lengths in a reply are integers in nanometres.
- **`neighbors`** lists the footprints near one part by the distance between their courtyards, nearest
  first: use it before a move, and to find the part a track must pass.
- **`region`** lists what touches a rectangle: footprints, pads, tracks, vias, zones, texts. The box is
  in file coordinates. `--layer` and `--kinds` narrow the reply.
- None of the three runs a tool; each reads the board file.

## Text fields

A footprint carries two texts, `Reference` on the silkscreen and `Value` on the fabrication layer.
`part.field(name, ...)` places one, once per name:

- `outside="top"` (or `bottom`, `left`, `right`) puts it beside the courtyard, `gap=` away;
- `dx=` and `dy=` give its offset from the part's position in the board frame, with `rot=` for the
  angle of the text; they are given together and do not turn with the part;
- `visible=False` hides it; `layer="silk"` or `"fab"`, `size=` and `justify=` set the rest.

Only `Reference` and `Value` can be placed. On a rebuild a field moved in KiCad wins over the script
unless the request says `locked=True`.

## What the build refuses

A build over an existing board checks the copper of the board against the design. When copper now
collides with it (a part was moved onto a track, or onto an old zone fill), the build exits 5 with
`copper.short` or `copper.clearance` and writes nothing. Move the part, refill the zones with
`fenolite fill`, or remove the copper in the way with `fenolite route --rip`, and build again.

Read next: `routing`, `checks`, `design-script`.
