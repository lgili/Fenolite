---
topic: footprints
title: Footprints and symbols written in the script
summary: Author footprints, symbols and library records; obtain library items and check datasheets.
---

# Footprints and symbols written in the script

Declare missing footprints and symbols in the script. The build writes project libraries.

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

## Symbols from pin tables

A pin table (`fenolite.pins.v0`, TOML) lists each pin's `number`, `name` and `type`; the generator draws the symbol: supply on top, ground at the bottom, inputs left, outputs right, every pin on the 2.54 mm grid, units above 100 pins. `stacked` adds a hidden pin per further pad; `[[variant]]` rows give derived symbols.

```fenolite-design
from fenolite.catalog.pins import parse_pins
from fenolite.dsl import Design, Net, Part, Symbol, connect, mm

ROWS = [("1", "VIN", "power_in", ""), ("2", "GND", "power_in", 'stacked = ["4"]'), ("3", "EN", "input", "")]
TABLE = """schema = "fenolite.pins.v0"
id = "Local:EXB1"
version = "1.0.0"
summary = "Illustrative regulator"
licence = "CC0-1.0"
evidence = "UNVERIFIED"
""" + "".join(f'[[pin]]\nnumber = "{n}"\nname = "{a}"\ntype = "{t}"\n{x}\n' for n, a, t, x in ROWS)

design = Design("pins")
design.board(mm(20), mm(16))
reg = Symbol.from_pins(parse_pins(TABLE), library="Local", footprint="Fenolite:SOIC_8")
tr = reg.derive("EXB1_TR", value="EXB1-TR")  # a derived symbol: the base's drawing and pins
dual = Symbol("Local", "DUAL", reference="U")  # a hand-drawn symbol of two units
dual.unit(1, "A")
dual.unit(2, "B")
dual.pin("1", "A", etype="input", at=(mm(-5.08), mm(0)), length=mm(2.54), unit=1)
dual.pin("2", "B", etype="input", at=(mm(-5.08), mm(0)), length=mm(2.54), unit=2)
dual.pin("3", "V+", etype="power_in", at=(mm(0), mm(5.08)), length=mm(2.54), rotation=270, unit=0)
design.add(reg, tr, dual)
u1 = Part("U1", "Local:EXB1_TR")
design.add(u1)
connect(Net("VIN"), u1["VIN"])
connect(Net("GND"), u1["GND"])  # pins 2 and 4: the stacked pad has the name of its pin
u1.place(mm(10), mm(8))
```

- `Symbol.from_pins(table, library=, footprint=)` is finished: change the table, not the code.
- `Symbol.pin(..., unit=0)` is common to every unit; `hidden=True` is refused on a `power_in` pin.
- `fenolite library symbol` writes the tables' symbols as one library (`.kicad_sym` or `.SchLib`):

  ```fenolite-cmd
  fenolite library symbol pins/EXB1.toml --out lib/Local.kicad_sym --dry-run --json
  ```
- The script is no finished board: `fenolite check` reports open connections,
  `kicad.erc.pin-not-connected`, `kicad.erc.pin-not-driven` and `kicad.erc.power-pin-not-driven`.

## Footprints from package records

A package record (`fenolite.package.v0`) gives a package's dimensions as ranges with their source; the generator of its `family` draws pads, courtyard, silkscreen and 3D bodies (`docs/footprint-generators.md`).

```fenolite-design
from fenolite.dsl import Design, Footprint, Part, mm

RECORD = """schema = "fenolite.package.v0"
family = "chip"
name = "CHIP0603_B1.6x0.8"
evidence = "INFERRED"
sources = ["S-0315"]
body = { length = "1.50mm..1.70mm", width = "0.70mm..0.90mm", height = "0.35mm..0.55mm" }
terminal = { length = "0.10mm..0.40mm" }
[generate]
lands = 1
drawing = 1
"""
design = Design("chip")
design.board(mm(10), mm(6))
chip = Footprint.from_package(RECORD)  # Local:CHIP0603_B1.6x0.8; the land is calculated
design.add_footprint(chip)
design.add(Part("R1", "Fenolite:Resistor", footprint=chip.lib_id, value="1k"))
```

- `[land]` with a `source` gives the manufacturer's land, which wins; without it the land is `INFERRED`.
- The build writes `lib/Local.3dshapes/<name>.step` beside the footprint when it has bodies.
- `fenolite library generate` writes the `.kicad_mod`, `.step` and one `.PcbLib` without a design:

  ```fenolite-cmd
  fenolite library generate packages/soic8.toml --out lib --dry-run --json
  fenolite explain package.no-goals
  ```
- `package.*` findings: errors (`package.no-goals`, `package.name-mismatch`, ...) draw nothing.

## What a person still checks

Geometry written from a datasheet is `INFERRED`: nobody has compared it with the real part, and no check of Fenolite or of KiCad can. Before boards are ordered, a person compares, with the datasheet of the exact part number:

- the pad positions, sizes and numbering, seen from the top, and which pad is pin 1;
- drill sizes with the plating, for the lead's largest diameter;
- the courtyard and the height of the body against its neighbours;
- the solder paste and mask openings, when the manufacturer asks for other than the default;
- the symbol's pin numbers against the pinout of that package, not of another package of the family.

`fenolite catalog show` gives the same warning for every catalog footprint: its evidence is `INFERRED`. Say so when you report a board that uses authored or catalog geometry.

## When to author and when not

- A part of KiCad's libraries: name it (page `parts`); do not redraw it.
- A two-pin passive, a header, a common package: look in the catalog first.
- Anything else: author it, and list it for review.

## A library from the board

```fenolite-cmd
fenolite library blink/build --diff lib/Mini.pretty --json
fenolite library blink/build --out board.pretty --confirm --json
```

`--diff` reports board footprints that differ from the library and the kinds (`pads`, `silkscreen`, `courtyard`, `models`, `fields`, `missing`), exits 5 on drift and writes nothing. `--out` writes each footprint back at its origin, rotation 0 and top side; a second instance that differs becomes `<name>_2` (`library.instances-differ`).

## Library records and orderable parts

A record of your own is a TOML file under `devices/` beside the script: `pins`, `package`, `device` or `part`. Each opens with a header: `schema`, `id`, `version`, `summary`, `licence`, `evidence`, `sources` (`docs/library-records.md`). An orderable part is `<device id>@<mpn>`.

```fenolite-design
from fenolite.catalog.records import parse_record
from fenolite.dsl import Design, mm

REG = """schema = "fenolite.device.v1"
id = "Proj:REG"
version = "1.0.0"
summary = "Two-pin regulator stand-in"
licence = "CC0-1.0"
evidence = "UNVERIFIED"
symbol = "Fenolite:Resistor"
footprint = "Fenolite:Chip_0603"
[pins]
IN = "1"
OUT = "2"
[[part]]
mpn = "REG100DR"
packing = "reel 2500"
"""
design = Design("parts")
design.board(mm(20), mm(10))
design.devices(parse_record(REG))
design.part("U1", device="Proj:REG@REG100DR").place(mm(10), mm(5))  # MPN REG100DR
```

`check` reports `kicad.erc.pin-not-connected` for both unconnected pins of `U1`.

## Items from fenolite-library

`fenolite-library` holds items with individual licences. `get` copies an item and its dependencies to `fenolite_library/`, keeps `LICENSE`, `NOTICE`, `PROVENANCE.json`, writes `ATTRIBUTION.md` and pins the lock. It never runs a payload.

```fenolite-cmd
fenolite get --search buck --licence cc0 --json
fenolite get device Demo:EXB --from release --dry-run --json
fenolite get footprint Demo:SA_PAD --from release --accept-licence CC-BY-SA-4.0 --confirm --json
fenolite get board demo-src/blink --into blink --accept-licence CERN-OHL-S-2.0 --dry-run --json
fenolite get --locked design.py --offline --dry-run --json
fenolite get --status --json
```

- Read `result.licences` before confirming: an id other than `CC0-1.0` must be named in
  `--accept-licence` (`FEN-4003`). A `reciprocal` item brings share-alike terms with it; tell the user.
- A download happens only with `--confirm`; `--offline` uses the cache. A build whose pinned folder is
  missing exits 6 (`FEN-6004`): restore it with `get --locked`.
- The library's own CI runs `library audit`, `replay`, `release` and `gallery`:

  ```fenolite-cmd
  fenolite library audit . --json
  fenolite library release . --version 1.0.0 --out dist --dry-run --json
  fenolite library gallery . --release dist --out site --dry-run --json
  fenolite library replay boards/cc-by-sa/kicad-demos/ecc83 --upstream upstream --json
  ```

Read next: `parts`, `placement`, `checks`.
