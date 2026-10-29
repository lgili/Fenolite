## Context

- **Source.** `docs/research/component-library.md`, section 4.3 ("Symbols from pin tables"), section 2
  (derived symbols in KiCad's library; Horizon's part wizard that splits large parts into gates; AI
  extracts pin tables well, drawings badly) and the table of section 5 (c0261, size M, depends on c0259).
- **What exists on `dev` (0.6.0).**
  - `model/library.py`: `SymbolDef` with `extends`, `units`, `pins` and `graphics`; `SymbolPin` with
    `unit`, `body_style`, `hidden` and `alternates` (`PinAlternate(name, etype, shape)`); `SymbolGraphic`
    has **no** unit, so every graphic is common to all units.
  - `dsl/symbol.py`: `Symbol` authors one unit (`unit=1, body_style=1` on every pin), no hidden pins, no
    alternates, no derivation.
  - `backends/kicad/sym.py`: the reader keeps units, alternates and `extends` (`resolve_extends`
    flattens). `write_symbol_library` writes "the simple authored subset": one `_0_1` graphics block, one
    `_1_1` pin block, no `hide`, no alternate, no `extends`.
  - `backends/kicad/symembed.py` (change c0123): a pin bonded to several pads is written as the pin plus
    one hidden `passive` pin per further pad at the same connection point (`STACKED_TYPE`,
    `STACKED_HIDDEN`); KiCad joins coincident pins (`H-K-SCH-STACKED`).
  - `backends/altium/altsym.py`: `from_symbol_def` maps units to parts (unit 0 to Part Zero), requires
    every position and length on the 10-mil grid (254 000 nm, `altium.symbol-off-grid`), drops alternates
    and other body styles with `altium.symbol-simplified`, sets the hidden bit 0x04.
  - The catalog's hand-drawn symbols use a 2.54 mm grid (`catalog/__init__.py`, `_GRID`).
  - `fenolite library BOARD --out LIB.pretty | --diff LIB` exists (change c0223) with a positional path.
- **What public tools do** (concepts only, research section 2): one library generates symbols from CSV
  pin tables and splits large parts into gates; another derives variants from a base (`extends`); KiCad's
  library conventions put pin ends on a 100 mil grid. Nothing of their code, files or tables is taken.

## Goals / Non-Goals

**Goals**

- A pin table is the only input a person or an agent writes for a symbol of any size.
- The same table gives byte-identical KiCad and Altium libraries on every machine.
- A generated symbol is on the 2.54 mm grid, readable, and stable: adding one pin moves only the pins of
  its own side and group.
- Multi-unit and derived symbols can be authored in the DSL too, not only generated.

**Non-Goals**

- See the proposal. In addition: no automatic choice of pin types from names (the table states the type);
  no pin swapping or gate swapping metadata (c0257).

## Decisions

### 1. The pin table (`fenolite.pins.v0`)

A pin table is one TOML file read with `tomllib` (`parse_float=Decimal`; no float exists in the format
anyway). The envelope keys (`schema`, `name`, `version`, `licence`, `sources`, `evidence`, `review`,
deprecation) and the stable id `(kind="pins", canonical name)` are c0259's; this change defines the body.
Example, authored for Fenolite (illustrative device, not a real product):

```toml
schema = "fenolite.pins.v0"
name = "EXB6202"
version = "1.0.0"
licence = "CC0-1.0"
sources = ["S-0zzz datasheet rev C, table 1"]
evidence = "UNVERIFIED"

[symbol]
reference = "U"
description = "6 V 2 A step-down regulator (illustrative)"

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
stacked = ["7"]          # exposed pad, same pin

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
side = "right"           # an explicit side wins over the group

[[variant]]              # derived symbols: same drawing, own properties
name = "EXB6202DR"
value = "EXB6202DR"
```

- **Row keys.**

  | key | required | meaning |
  |---|---|---|
  | `number` | yes | Non-empty text, unique across `number` and `stacked` of all rows. |
  | `name` | yes | Non-empty text; `~` for an unnamed pin; KiCad's overbar `~{...}` is kept. |
  | `type` | yes | One of the 12 `PinType` values (`input` ... `no_connect`), as `Symbol.pin`. |
  | `group` | no | `supply`, `ground`, `input`, `control`, `output`, `io`, `passive`, `nc`. Default from `type` (decision 2). |
  | `side` | no | `left`, `right`, `top`, `bottom`. Wins over the group's side. |
  | `bus` | no | A bus name; rows of one bus are kept together (decision 2). |
  | `unit` | no | Integer ≥ 0. All rows or none (decision 3). 0 is common to all units. |
  | `shape` | no | One of the 9 `PinShape` values; default `line`. |
  | `hidden` | no | Boolean, default false. Refused on a `power_in` row (decision 6). |
  | `stacked` | no | Further pad numbers of the same pin (decision 6). |
  | `alternates` | no | List of `{ name, type, shape? }` tables. |

- **`[symbol]` keys:** `reference` (`[A-Z][A-Z_]*`, default `U`), `description`, `keywords` (list),
  `split_above` (integer 16 … 1000, default 100), `unit_pins` (integer 8 … 200, default 48),
  `auto_bus` (boolean, default true), and `[[symbol.unit]]` rows `{ number, name }` naming units.
- **`[[variant]]` keys:** `name` (required, a symbol name), `value`, `description`, `datasheet`
  (`https://`), `footprint`, `keywords`, `fp_filters`. Each becomes one derived symbol (decision 5).
- Any other key, a missing key or a wrong type gives `FormatError` (`FEN-3004`) naming the file, the row
  index and the key; a newer schema gives `FEN-3002`.
- **Model.** `fenolite.model.library` gains frozen `PinRow(number, name, etype, group="", side="",
  bus="", unit=None, shape="line", hidden=False, stacked=(), alternates=())` and `PinTable(name, rows,
  reference="U", description="", keywords=(), split_above=100, unit_pins=48, auto_bus=True,
  unit_names=(), variants=())` with `PinVariant(...)`. Envelope fields are c0259's record type, which
  holds the `PinTable` as its body. `catalog/pins.py` holds `parse_pins(text, *, file)`,
  `pins_text(table)` (canonical TOML) and `read_pins(path)`.
- *Alternative considered:* CSV, as one public wizard uses. Rejected: no place for alternates, stacked
  numbers, units or provenance, and every other Fenolite record is TOML (c0248, c0259).

### 2. Sides, order and buses

- **Default group from type.**

  | type | default group | side |
  |---|---|---|
  | `power_in`, name matching `(?i)^(A|D|P|S)?(GND|VSS)` or `(?i)^(EP|PAD|THERMAL)$` | `ground` | bottom |
  | other `power_in` | `supply` | top |
  | `input` | `input` | left |
  | — (explicit only) | `control` | left |
  | `output`, `power_out`, `open_collector`, `open_emitter`, `tri_state` | `output` | right |
  | `bidirectional` | `io` | right |
  | `passive`, `free`, `unspecified` | `passive` | left |
  | `no_connect` | `nc` | right |

- **Order on a side.** Left: `input`, `control`, `passive`. Right: `output`, `io`, `nc`. Top: `supply`.
  Bottom: `ground`. A row with an explicit `side` joins that side in the group order of its group.
  Within one group, rows keep **table order** (the datasheet's order is meaningful), except buses.
  Consecutive groups on one side are separated by one empty slot.
- **Buses.** Rows with the same `bus` value are one block at the position of their first row, ordered by
  natural order of their names (`D2` before `D10`). With `auto_bus`, rows of one group and side whose names
  match `^(.*[^0-9])([0-9]+)$` with the same prefix and at least two members form an implicit bus named
  by the prefix. A bus whose indices skip a number gives `symbol.bus-gap` (info).
- **Why table order and not alphabetical.** Adding a pin then moves only the pins after it in its own
  group, which keeps the old/new visual diff of c0262 small. *Alternative considered:* balancing pins
  between left and right to minimise height. Rejected: the side of a pin would depend on the count of
  other pins, so a one-pin edit could move many pins.

### 3. Units

- **Explicit.** When any row has `unit`, every row must (`FEN-3004` otherwise). Units are 1 … n with no
  gap; unit 0 rows are common and drawn in every unit, on their own side.
- **Automatic.** When no row has `unit` and the visible rows number more than `split_above`:
  1. the **power units** hold every `supply` and `ground` row, cut into chunks of `unit_pins` rows in
     table order (supply first, then ground);
  2. the other rows form **blocks**: a bus is one block, and a run of rows of one group in table order is
     one block;
  3. blocks are packed in the table order of their first row into **signal units**: a new unit starts
     when the next block would exceed `unit_pins`; a block larger than `unit_pins` is cut at that size,
     with `symbol.bus-split` (warning) when it is a bus;
  4. signal units are numbered first (1 … k), power units after them; `symbol.units-split` (info)
     names the counts.
- Below the threshold the symbol has one unit and the table's groups are laid out around one body.
- *Alternative considered:* one unit per group. Rejected: a 100-pin MCU has three or four groups of very
  different sizes, and port pins (`io`) would form one 80-pin unit.

### 4. Geometry (all integers, nanometres, Y up as in the symbol model)

Constants, Fenolite-authored and recorded `INFERRED` in `docs/formats/library/symbols.md`:
`G = 2_540_000` (grid and pin pitch, 100 mil), `L = 2_540_000` (pin length), `A = 1_016_000` (estimated
advance of one character of a pin name at the 1.27 mm font), stroke `254_000`.

Per unit, with `nL`, `nR` the slots of the left and right sides (gaps included), `nT`, `nB` the top and
bottom pins, `cL`, `cR`, `cT`, `cB` the longest names (in characters, overbar markup removed) on each side:

```
ceil2G(x) = the smallest multiple of 2G that is >= x
W = max(ceil2G(A*(cL + cR) + 2G), ceil2G((max(nT, nB) + 1) * G), 4G)
H = max(ceil2G((max(nL, nR) + 1) * G), ceil2G(A*(cT + cB) + 2G), 4G)
body = rect (-W/2, -H/2) .. (W/2, H/2), filled background, unit u
left slot i  (0 from the top): point (-W/2 - L, H/2 - G*(i+1)), rotation 0
right slot i:                  point ( W/2 + L, H/2 - G*(i+1)), rotation 180
top pin j (0 from the left):   point (G*(j - (nT-1)//2), H/2 + L), rotation 270
bottom pin j:                  point (G*(j - (nB-1)//2), -H/2 - L), rotation 90
```

W and H are multiples of 2G, so every corner and every connection point is a multiple of G, which is a
multiple of the Altium writer's 10-mil unit (254 000 nm): `altium.symbol-off-grid` cannot occur. The
properties: `Reference` from `[symbol]`, `Value` = the table name, `Description`, `ki_keywords`,
`Footprint` and `ki_fp_filters` from the device when the symbol is generated for one (decision 8).

### 5. Derived symbols

- A `[[variant]]` row gives `SymbolDef(name=<variant>, library=<base library>, extends=<base name>,
  properties=<own properties only>, pins=(), units=(), graphics=())`, the form the KiCad reader returns
  for a derived symbol "as written". `resolve_extends` (living spec "Derived symbols") flattens it for
  every consumer that needs pins (build, checks, Altium).
- DSL: `base.derive("EXB6202DR", value="EXB6202DR", footprint=...)` returns a `DerivedSymbol` whose
  `.definition` is that `SymbolDef`; `Design.add` accepts it and requires the base to be added under the
  same library (`DslError` otherwise: KiCad resolves `extends` within one library only).
- KiCad writes `(symbol "EXB6202DR" (extends "EXB6202") ...properties...)` after its base. Altium has no
  derivation in the writer: the flattened symbol is written under its own lib ref.
- *Alternative considered:* copying the base into every variant in KiCad too. Rejected: KiCad's own
  library uses derivation, a change of the base then reaches every variant, and the file stays small.

### 6. Hidden and stacked pins

- `stacked = ["7"]` on the `GND` row gives pin `2` (as the row says) and pin `7` at the same connection
  point, hidden, of type `STACKED_TYPE`, without alternates: the representation c0123 already writes and
  KiCad joins (`H-K-SCH-STACKED`). The Altium writer gives the further pin the hidden bit at the same
  location. Stacked numbers take no slot.
- `hidden = true` hides a row that still takes its slot (so its connection point is unique). It is
  refused on `power_in` (`FEN-3004`): a hidden power input can create an implicit global connection in
  one target and not in the other, and no connection of a Fenolite design may depend on the target.

### 7. Writers

- **KiCad** (`write_symbol_library`): per symbol, `(symbol "<name>_0_1")` holds graphics and pins of unit
  0, and `(symbol "<name>_<u>_1")` those of unit u, in unit order; a named unit writes `(unit_name "...")`
  in its block; a hidden pin writes `(hide yes)`; each alternate writes `(alternate "<name>" <type>
  <shape>)` in its pin, in table order; a derived symbol writes `extends` and its own properties only,
  directly after its base. A single-unit symbol without these features keeps today's bytes, so existing
  builds do not change. The reader keeps the unit of a graphic.
- **Altium** (`altsym.from_symbol_def`): a graphic of unit u gets `OWNERPARTID=u` (0 stays Part Zero);
  alternates are still dropped with `altium.symbol-simplified`; a derived symbol is flattened with
  `resolve_extends` first.
- **Model.** `SymbolGraphic` gains `unit: int = 0` and `body_style: int = 0`; the library schema is
  regenerated. Graphics read from a single-unit KiCad symbol keep unit 0 and body style 0, as today, so no
  existing canonical JSON changes.

### 8. DSL, devices and CLI

```python
# Today (0.6.0): every pin placed by hand, one unit
u = Symbol("Example", "EXB6202", reference="U")
u.pin("5", "VIN", etype="power_in", at=("0mm", "7.62mm"), length="2.54mm", rotation=270)
# ... five more pins and a rectangle

# Proposed: generated from the table
from fenolite.catalog.pins import read_pins
from fenolite.dsl import Symbol

table = read_pins("pins/EXB6202.toml")
u = Symbol.from_pins(table, library="Example")
dr = u.derive("EXB6202DR", value="EXB6202DR")
design.add(u)
design.add(dr)

# Proposed: a hand-drawn dual unit
q = Symbol("Example", "DUAL_OPAMP", reference="U")
q.unit(1, "A")
q.unit(2, "B")
q.pin("1", "OUTA", etype="output", at=("7.62mm", "0mm"), length="2.54mm", rotation=180, unit=1)
q.pin("8", "V+", etype="power_in", at=("0mm", "7.62mm"), length="2.54mm", rotation=270, unit=0)
```

- `Symbol.pin` gains `unit=1` (0 for common), `hidden=False`, `alternates=()` (tuples `(name, etype)`
  or `(name, etype, shape)`); `Symbol.unit(number, name="")`; `Symbol.graphic(..., unit=0)` and the
  shortcuts take `unit`. A pin of unit n without `Symbol.unit(n)` declares unit n unnamed. Defaults keep
  today's one-unit definitions byte for byte.
- `Symbol.from_pins(table, *, library, footprint="", fp_filters=())` returns a finished `Symbol` whose
  definition is the generator's output; calling `pin()` on it raises `DslError` (a generated symbol is
  changed in its table, not in code). The DSL reads no file: `read_pins` belongs to `fenolite.catalog`.
- **Devices.** When a c0259 device record names `pins` and no `symbol`, the catalog generates the symbol
  under the device's namespace and name, with `Footprint` and `ki_fp_filters` from the device's package,
  and the device uses it. A device with both keeps its named symbol and c0262 checks that its pins agree
  with the table.
- **CLI.**

  ```
  fenolite library symbol pins/EXB6202.toml --out lib/Example.kicad_sym --dry-run
  fenolite library symbol pins/EXB6202.toml --out lib/Example.SchLib --confirm --plan <id>
  ```

  `--library NAME` (default: the stem of `--out`), `--target 9|10` for KiCad. Several pin tables may be
  given; they share one library file. The result lists per symbol its units, the pins per side and the
  findings. `--out` must be relative and end in `.kicad_sym` or `.SchLib` (`FEN-2001`).
- **Action words of `fenolite library`.** The first positional is an action when it is one of `symbol`,
  `check`, `review`, `import`, `propose`, `fetch` (the last five are reserved here for c0262, c0264,
  c0265 and c0266, and give `FEN-2001` "not available in this version" until those land). Any other first
  positional is the board path of the existing form, which keeps working; a board folder literally named
  like an action is passed as `./check`. *Alternative considered:* a new top-level command
  (`fenolite symbols`). Rejected: the research and the batch place every library operation under
  `fenolite library`, and agents look for them there.

### 9. Package placement

`fenolite.catalog.generate.symbol` holds `generate_symbol(table, *, library, footprint="",
fp_filters=()) -> tuple[SymbolDef, tuple[SymbolDef, ...], tuple[Issue, ...]]` (the base, its derived
symbols, the findings). It imports only `model` and `core`. c0260 puts its footprint generators in the
same subpackage `catalog/generate/`; whichever of the two lands first creates it.

## Codes introduced

| code | severity / exit | when |
|---|---|---|
| `symbol.units-split` | info | the automatic split made more than one unit; names the counts |
| `symbol.bus-split` | warning | a bus larger than `unit_pins` was cut across units |
| `symbol.bus-gap` | info | a bus skips an index (`D0`, `D1`, `D3`) |
| `FEN-3004` | exit 3 | malformed pin table (existing code) |
| `FEN-3002` | exit 3 | pin table schema newer (existing code) |
| `FEN-2001` | exit 2 | bad `--out`, or a reserved `library` action (existing code) |

No new `FEN-` code.

## Hypotheses registered by this change

| id | statement | settled by |
|---|---|---|
| `H-G-SYMBOL-LAYOUT` | the generator gives the same bytes for the same table, every point on the 2.54 mm grid, and a one-pin edit moves only pins of its side and group | `tests/unit/catalog/test_symbol_generate.py` (hypothesis-based) |
| `H-K-SYM-UNITS-WRITE` | KiCad 9 and 10 read the written units, unit names, hidden pins, alternates and `extends` as written | `tests/kicad/library/test_symbol_generate_oracle.py` |
| `H-A-SCHLIB-GEN-PARTS` | Altium Designer shows a generated multi-part symbol with Part Zero pins and per-part bodies as written | a kit step of the maintainer's Altium kit |

## Evidence level per behaviour (before merge)

| behaviour | level |
|---|---|
| pin-table parsing, layout, units | `INFERRED` (`H-G-SYMBOL-LAYOUT`) |
| KiCad symbol library with units, alternates, `extends` | `KICAD-VERIFIED (9.0.x, 10.0.x)` after the oracle (`H-K-SYM-UNITS-WRITE`) |
| Altium SchLib of a generated symbol | `ORACLE-VERIFIED(kicad-cli)`; `ALTIUM-VERIFIED(kit)` after `H-A-SCHLIB-GEN-PARTS` |
| the pin facts of a table | the table's own label; generation never raises it |

## Risks / Trade-offs

- **Text width is estimated.** `A` is a constant, not a font metric; a name of wide letters may touch the
  body edge. Mitigation: names are short in practice, the review sheet of c0262 shows the drawing, and
  `A` is one documented constant.
- **The default group heuristic for ground names** may misplace an unusual name (`0V`). Mitigation: the
  table states `group` or `side`, and the generator never guesses beyond the table in the decision 2 list.
- **Changing `SymbolGraphic`** touches the library schema. Mitigation: defaults keep every current
  definition's canonical JSON; the schema check task proves it.
- **Reserved action words** could shadow a board folder named `check`. Mitigation: documented; `./check`
  works; the existing form is otherwise unchanged.

## Open questions

1. *Default `split_above` of 100 pins and `unit_pins` of 48?* Recommended: yes, as the research suggests
   about 100; both are per-table settings, so a library can choose.
2. *Should bidirectional pins default to the right?* Recommended: yes; MCU ports on the right read as
   "drives the board", and a table can move them with `side`.
3. *Should `Symbol.from_pins` accept a path?* Recommended: no; the DSL reads no file. `read_pins` is one
   import away and keeps the rule simple.
4. *Unit names: letters (`A`, `B`) by default for automatic units?* Recommended: no names by default;
   KiCad shows letters itself, and a name like `POWER` comes from `[[symbol.unit]]`.

## Relation to the batch

- **c0259** (data format): owns the envelope, stable ids, versions, licence, sources, evidence and the
  data tree; this change owns the body of `fenolite.pins.v0`. If c0259 lands a different key spelling for
  the envelope, this change follows it.
- **c0260** (footprint generators): sibling under `catalog/generate/`; the device's package name gives
  the generated symbol's `Footprint` and `ki_fp_filters`.
- **c0262** (library rules): checks generated and hand-drawn symbols (`library.pin-grid`,
  `library.footprint-filter-*`, `library.hidden-power`), renders the review sheet, and diffs old and new
  generator output.
- **c0264** (import) and **c0265** (datasheet proposals) write pin tables in this format.
- **c0248** (devices): the `dsl` → `catalog` edge already exists; a device's function map is checked
  against the table's numbers by c0262.
- **c0257** (pin assignment, later): may add swap groups to rows; the key `swap` is not reserved here.
