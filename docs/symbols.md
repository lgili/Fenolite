# Symbols from pin tables

A symbol of a large part is not drawn by hand in Fenolite: it is generated from a **pin table**, the facts a
datasheet gives (pin number, name, electrical type, function group), by a deterministic **layout rule**
(change c0261). The same table gives byte-identical KiCad and Altium libraries on every machine, and every
connection point lies on the 2.54 mm grid. The facts and constants behind the rule, with their sources and
evidence labels, are in [`formats/library/symbols.md`](formats/library/symbols.md).

## The pin table (`fenolite.pins.v0`)

One TOML file per symbol. The record header is the minimum of change c0259's common header; the rest is the
body. The example below is authored for Fenolite and describes no real product
(`examples/symbols/pins/EXB6202.toml`):

```toml
schema = "fenolite.pins.v0"
id = "Example:EXB6202"          # <namespace>:<symbol name>
version = "1.0.0"
summary = "6 V 2 A step-down regulator (illustrative)"   # the Description, unless [symbol] gives one
licence = "CC0-1.0"
evidence = "UNVERIFIED"

[symbol]
reference = "U"
keywords = ["regulator", "buck"]

[[pin]]
number = "5"
name = "VIN"
type = "power_in"
group = "supply"

[[pin]]
number = "2"
name = "GND"
type = "power_in"
group = "ground"
stacked = ["7"]                 # the exposed pad: a further pad of the same pin

[[pin]]
number = "4"
name = "EN"
type = "input"
group = "control"

[[pin]]
number = "3"
name = "FB"
type = "input"

[[pin]]
number = "6"
name = "SW"
type = "power_out"

[[pin]]
number = "1"
name = "BST"
type = "passive"
side = "right"                  # an explicit side wins over the group

[[variant]]                     # a derived symbol: same drawing, own properties
name = "EXB6202DR"
value = "EXB6202DR"
```

| row key | required | meaning |
|---|---|---|
| `number` | yes | non-empty text, unique across `number` and `stacked` of all rows |
| `name` | yes | non-empty text; `~` for an unnamed pin; KiCad's overbar `~{...}` is kept |
| `type` | yes | one of the 12 KiCad pin types (`input` … `no_connect`) |
| `group` | no | `supply`, `ground`, `input`, `control`, `output`, `io`, `passive`, `nc`; default from the type |
| `side` | no | `left`, `right`, `top`, `bottom`; wins over the group's side |
| `bus` | no | rows of one bus are kept together, in natural order of their names |
| `unit` | no | integer ≥ 0 on every row or on none; 0 is common to all units |
| `shape` | no | one of the 9 KiCad pin shapes; default `line` |
| `hidden` | no | the pin keeps its slot and is hidden; refused on a `power_in` row |
| `stacked` | no | further pad numbers of the same pin |
| `alternates` | no | `[{ name, type, shape? }]`, the alternate functions of the pin |

`[symbol]` takes `reference` (`[A-Z][A-Z_]*`, default `U`), `description`, `keywords`, `split_above` (16 …
1000, default 100), `unit_pins` (8 … 200, default 48), `auto_bus` (default true) and `[[symbol.unit]]` rows
`{ number, name }` that name units. `[[variant]]` takes `name`, `value`, `description`, `datasheet`
(`https://`), `footprint`, `keywords` and `fp_filters`.

Any other key, a missing key or a wrong type is refused with `FEN-3004`, naming the file, the row and the
key; a newer schema gives `FEN-3002`. `fenolite.catalog.pins` reads (`read_pins`, `parse_pins`) and writes
(`pins_text`, the canonical text) tables; no float is ever created.

## The layout rule

- **Sides.** Supply pins on top, ground at the bottom, `input`, `control` and `passive` on the left,
  `output`, `io` and `nc` on the right, in that group order, with one empty slot between two groups. A row
  without `group` takes the default of its type (a `power_in` named like `GND`, `VSS`, `AGND` or `EP` is
  ground, any other supply).
- **Order.** Rows keep table order within a group: adding a pin moves only the pins after it in its own
  group. A bus is one block at its first row; with `auto_bus`, rows of one group and side named
  `<prefix><number>` form a bus by themselves. A bus that skips an index gives `symbol.bus-gap`.
- **Geometry.** Pins are 2.54 mm long on a 2.54 mm pitch; the body is a rectangle centred on the origin
  whose width and height are multiples of 5.08 mm, large enough for the slots and an estimate of the name
  widths. So every connection point and corner is on the grid, which is also on the Altium writer's 10-mil
  grid.

The example draws as follows (body 10.16 mm × 15.24 mm):

```
                 VIN 5
                   |
            +-------------+
     3 FB --|             |-- SW 6
            |             |
     4 EN --|             |-- BST 1
            |             |
            +-------------+
                   |
                 GND 2 (+ hidden 7)
```

## Units

- **Explicit:** when every row has `unit`, the units are those of the table (1 … n without a gap); unit 0
  rows are drawn in every unit, at the same place, and every unit then has the same body size.
- **Automatic:** above `split_above` visible rows, the rows other than supply and ground are packed in table
  order into signal units of at most `unit_pins` rows, a bus or a run of one group staying whole (a bus larger
  than a unit is cut, with `symbol.bus-split`); the supply and ground rows form the power units after them.
  `symbol.units-split` names the counts. `examples/symbols/pins/EXM120.toml` (120 pins) gives two signal units
  of 48 pins and one power unit of 24, named `POWER` by `[[symbol.unit]]`.

A single-unit symbol draws its body common to all units (unit 0), as hand-drawn symbols do; a symbol of
several units draws one body per unit.

## Variants, hidden and stacked pins

- Each `[[variant]]` gives a derived symbol: `extends` the base, its own properties only, no pins. KiCad
  writes it as `(extends "<base>")` after its base in the same library.
- A `stacked` number gives a further pin at the connection point of its row, hidden, of type `passive`,
  without alternates: the form KiCad joins (change c0123). Connect the pin by name (`u1["GND"]`) to reach
  every pad.
- `hidden = true` keeps the row's slot. A hidden power input is refused, because KiCad joins hidden power
  inputs by name and Altium does not, so a connection would depend on the target.

## Using the generated symbols

```python
from fenolite.catalog.pins import read_pins
from fenolite.dsl import Design, Part, Symbol

design = Design("example")
table = read_pins("pins/EXB6202.toml")
u = Symbol.from_pins(table, library="Example", footprint="Example:SOT23-6")
design.add(u, *u.variants)
design.add(Part("U1", "Example:EXB6202DR"))
```

`fenolite library symbol pins/EXB6202.toml --out lib/Example.kicad_sym --dry-run` plans the same library
without a design (`docs/cli-contract.md`, "library"); `--out lib/Example.SchLib` plans an Altium schematic
library.

## Altium notes

The Altium library has no derivation: a variant is written flat, under its own lib ref. Each unit is a part,
unit 0 pins are Part Zero pins, each body rectangle belongs to its part (`OWNERPARTID`), and alternates are
dropped with `altium.symbol-simplified`. That Altium Designer shows such a library as written is
`H-A-SCHLIB-GEN-PARTS`, pending the maintainer's kit step; KiCad's reading of the KiCad library is
`H-K-SYM-UNITS-WRITE`.

## Not covered

No body styles (De Morgan), no drawing beyond the rectangle body (functional symbols stay hand-drawn), no
extraction of a table from a datasheet, and no library checks: those are later changes.
