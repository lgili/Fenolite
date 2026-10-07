---
topic: design-script
title: Writing a design script
summary: The shape of a script: design, modules, nets, parts, lengths with units, the board frame, and the edit and build cycle.
---

# Writing a design script

A design script is a Python file that binds a module-level name `design` to a `Design`. `fenolite build`
runs it as your own code, in its own process, and writes a project from what `design` holds. Never build
a script you do not trust. A script imports from `fenolite.dsl` and nothing else of Fenolite.

## A whole script

```fenolite-design
from fenolite.dsl import Design, Module, Net, Part, connect, inch, mil, mm, nm, no_connect

design = Design("lamp")  # the name becomes the stem of every file
design.board(mm(30), inch("0.8"))  # width and height of the outline; two copper layers

# Your fabricator's limits. These numbers are examples.
design.rules.minimum(clearance=mm(0.2), track_width=nm(200_000), edge_clearance=mm(0.3))

j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54", value="IN")
design.add(j1)  # nothing joins the design without add()

lamp = Module("lamp")  # a group of parts; the path of R1 is lamp/R1
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:Chip_0603", value="RED")
lamp.add(r1, d1)
design.add(lamp)

vin, gnd = Net("VIN"), Net("GND")
anode = Net(f"{lamp.path}/ANODE")  # net names are global: the script names a local net
connect(vin, j1[1], r1[1])  # a pin by its number
connect(anode, r1[2], d1["A"])  # or by its name
connect(gnd, d1["K"], j1[2])
no_connect(j1[3])  # left open on purpose

# From the outline's top-left corner: X to the right, Y down.
j1.place(mil(250), mm(10), rot=90)
r1.place(mm(15), mm(14))
d1.place(mm(15), mm(6), rot=180)
```

## What each piece is

- **`Design(name)`** holds everything. `design.board(width, height, copper=2)` declares the outline, once;
  `copper` is 2, 4, 6 or 8.
- **`Module(name)`** groups parts. A module has `add()` like the design, and modules nest. A part's path
  is its reference at the top and `module/REF` inside a module; the path names the part across builds.
- **`Part(ref, lib_id, footprint=..., value=...)`** is one component (page `parts`).
- **`Net(name)`** is a net. Two `Net` objects with one name are an error.
- **`connect(net, *pins)`** joins pins to a net. `part[1]` is the pin with that number; `part["A"]` is
  every pin with that name. A pin joins one net.
- **`no_connect(*pins)`** marks pins that stay open on purpose, so the electrical check does not
  report them. A pin is either connected or marked, never both.
- **`Power(hv, lv)`** records a supply: its high net and its low net; `design.add(Power(vin, gnd))` adds
  it. The design block of the page `altium` uses it. A KiCad build puts a power flag on both nets, so
  the electrical check takes a supply that comes in through a connector as driven. It builds with
  parts of the built-in catalog as well: the flag then lies in the catalog's library.
- A wrong call raises an error at its own line: a duplicate reference, a second `place()`, a bare
  number where a length is expected. The build reports it as `FEN-3004` with `line:N` (page `recovery`).

## Lengths carry a unit

`mm()`, `mil()`, `inch()` and `nm()` return an exact length, stored in whole nanometres. They take an
`int`, a string or a float literal: `mm(0.2)`, `mm("0.2")`, `mil(250)`, `inch("0.8")`. A string with a
unit works wherever a length is expected (`"2.54mm"`). A bare number is refused, and so is a value that
is not a whole number of nanometres. Angles are degrees.

## The board frame

Every coordinate of a script is measured from the outline's top-left corner, X to the right and Y
down. The board file holds the outline at (100 mm, 100 mm), so `place(mm(15), mm(6))` is the point
(115 mm, 106 mm) of the file. Commands that read a board report file coordinates; `fenolite pads` takes
`--origin 100mm,100mm` to answer in the script's frame (page `placement`).

## The cycle

```fenolite-cmd
fenolite init blink --confirm --json
fenolite build blink/design.py --out blink/build --dry-run --json
fenolite build blink/design.py --out blink/build --confirm --json
fenolite build blink/design.py --out blink/build --kicad-version 9 --dry-run --json
```

- `init` writes `blink/design.py`, a starter that builds as it is. Edit it, or write your own file.
- `build --dry-run` runs the script and returns `result.plan`, the files it would write, and every issue.
  Read the issues here: an `error` means nothing would be written. `--confirm` writes.
- The project goes under `--out`, never beside the script: the board, the schematic, the project and
  rules files, the library tables and copies of the footprints and symbols it uses, and `.fenolite/`,
  which holds the design as data. The folder is self-contained.
- `--kicad-version 9` writes for KiCad 9; the default is 10.
- `result.staged` lists the parts that have no `place()`; they lie beside the board (page `placement`).
- A script that builds is not yet a board: the script above has no copper, so `fenolite check` reports
  `kicad.drc.unconnected-items` for it until it is routed (page `routing`).

## What a rebuild keeps

Build again after every edit of the script, into the same folder. The board is merged, not replaced:

- footprints keep the position they have on the board, also one moved by `fenolite place` or by hand
  (`layout.place-overridden`, info, when the script says otherwise); a new part comes in where its
  `place()` says;
- tracks and vias that a router or a person drew stay; copper that the script declares is written again
  from the script (page `routing`);
- the schematic is generated again each time.

A part or a net that you rename is a new one unless the script says `design.moved("R1", "R9")` or
`design.moved_net("VIN", "VBUS")` for one build. A build refuses to replace a library table or a
library file that someone edited (`FEN-7001`); `--discard-layout` builds from scratch, with backups.

## Taking placements back

```fenolite-cmd
fenolite sync blink/design.py --out blink/build --to-source --dry-run --json
fenolite sync blink/design.py --out blink/build --to-source --check --json
```

`sync --to-source` copies the positions of the board into `placements.toml` beside the script. A build
reads that file, so a fresh folder gets the same layout. `--check` writes nothing and exits 5 when the
file is stale.

## A drawing sheet

`design.sheet("A3", drawing_sheet="frame.sheet.toml")` sets the paper and names your frame, by a path
relative to the script; `design.title_block(title="Lamp", revision="A")` fills the title block. Fenolite
ships no frame. This command turns a specification of yours into a KiCad drawing sheet on its own:

```fenolite-cmd
fenolite template build blink/frame.sheet.toml --target kicad -o blink/frame.kicad_wks --dry-run --json
```

Read next: `parts`, `placement`, `routing`.
