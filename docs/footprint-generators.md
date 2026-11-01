# Footprints from package records

A footprint for a package the catalog lacks is not drawn pad by pad in Fenolite: it is **generated** from a
package record, the dimensions a datasheet's package outline gives with their tolerances and their source
(change c0260). One generator per package family draws the pads, the courtyard, the silkscreen and the
fabrication drawing by a versioned convention, extrudes 3D bodies from the same numbers and writes them as a
STEP model. The same record gives the same bytes on every machine.

The constants of the land calculator and the drawing conventions, with how each was obtained, are in
[`formats/library/lands.md`](formats/library/lands.md); the naming rule is
[`formats/library/naming.md`](formats/library/naming.md); the STEP file facts are
[`formats/step/part21.md`](formats/step/part21.md). Everything a generator decides is Fenolite's own and
labelled `INFERRED`: no IPC table, formula or naming pattern and no third-party footprint, generator or
model is used.

## A package record

One TOML file per package (`fenolite.package.v0`). Lengths are exact ranges with a unit: `"1.27mm"` (exact),
`"4.80mm..5.00mm"`, `"1.75mm max"`, `"0.10mm min"` or a table `{ min = "...", nom = "...", max = "..." }`;
the units are those of `fenolite.core.units` (`mm`, `um`, `mil`, `in`, ...), and a value that is not a whole
number of nanometres is refused (`FEN-3004`), never rounded. The record below is
`tests/data/packages/soic8.toml`, authored for Fenolite from a public case outline:

```toml
schema = "fenolite.package.v0"
family = "gullwing"
name = "SOIC8_B4.9x3.9_P1.27"
summary = "8-lead 1.27 mm pitch small outline, 4.9 x 3.9 mm body"
evidence = "INFERRED"
sources = ["S-0981"]

pins = 8
pitch = "1.27mm"
arrangement = "dual"
body = { length = "4.80mm..5.00mm", width = "3.80mm..4.00mm", height = "1.35mm..1.75mm", standoff = "0.10mm..0.25mm" }
span = "5.80mm..6.20mm"
lead = { length = "0.40mm..1.27mm", width = "0.33mm..0.51mm", thickness = "0.19mm..0.25mm" }

[generate]
lands = 1        # the constant table of the calculator (required when it is used)
drawing = 1      # the drawing convention (required)

[land]           # optional: the manufacturer's land wins over the calculator
source = "S-0981 soldering footprint"
pad = { length = "1.52mm", width = "0.60mm" }
row_spacing = "5.50mm"
```

The family is `family` (or c0259's `generator`); the name is `name` or the name part of `id`
(`Local:NAME`). An unknown key, a missing required key, a wrong type or a TOML float is `FEN-3004` naming the
file and the key.

## Families and their keys

Required keys are **bold**.

| family | packages | keys |
|---|---|---|
| `chip` | two-terminal chips: R, C, L, bead | **`body`** (length, width, height), **`terminal`** (length), `polarity` (`none` / `pad1`) |
| `molded` | SOD, SMA/SMB/SMC, molded tantalum, MELF | **`body`**, **`span`**, **`lead`** (length, width), `lead_style` (`flat` / `inward` / `cylinder`), `polarity` |
| `gullwing` | SOIC, SSOP, TSSOP, MSOP, QFP, SOT | **`pins`**, **`pitch`**, **`arrangement`** (`dual` / `quad` / `sides`), **`body`**, `span` (or `span_x`, `span_y` for `quad`), **`lead`** (length, width, thickness), `[[side]]` (`edge`, `numbers`, `positions`, for `sides`), `tab` (number, width, length, edge) |
| `nolead` | QFN, DFN, SON | **`pins`**, **`pitch`**, **`arrangement`** (`dual` / `quad`), **`body`**, **`terminal`** (length, width), `pull_back`, `ep` (length, width), `ep_number` (default `EP`), `paste` (`grid`, `window`, `pitch`) |
| `grid` | ball and land grid arrays | **`rows`**, **`columns`**, `pitch` (or `pitch_x`, `pitch_y`), **`body`**, **`ball`** (diameter), `pad` (`nsmd` / `smd`), `depopulated` (ball names, or `center = "RxC"`) |
| `to` | TO-220, TO-247, TO-92 (`tht`); DPAK-style (`smd`) | **`mount`**, **`leads`**, **`pitch`**, **`body`** (with `offset`), `span`, **`lead`** (width, thickness, length), `tab` (width, length, hole, number) |
| `dip` | through-hole dual rows | **`pins`**, **`pitch`**, **`row_spacing`**, **`body`**, **`lead`** (width, thickness, length) |
| `header` | pin headers and sockets | **`rows`**, **`columns`**, **`pitch`**, **`mount`**, **`orientation`**, **`pin`** (width, thickness, length_above, length_below), **`body`** (height, offset), `numbering` (`rows-first` / `columns-first`) |
| `connector` | a connector series | **`series`**, **`positions`** (`"2..15"`), **`pitch`**, **`name_pattern`** (`{series}`, `{n}`, `{pitch}`), **`body`** (`length = { per_position, extra }`, width, height, offset), **`pin`**, `mount`, `orientation`, `[[mechanical]]` (pegs and retention pads) |

A `connector` record is a series: it expands to one footprint per position count, each named by
`name_pattern` (`CONN{n}_{series}_P{pitch}` gives `CONN3_XH_P2.5`).

## The land: manufacturer or calculated

- **`[land]` given.** Its numbers are used unchanged (`pad`, `row_spacing` or `row_spacing_x`/`_y`, `ep`,
  `paste`, `tab`, `drill`, `pad_diameter`, per family); `source` names the registered source and the place
  in it. The footprint keeps the record's evidence label for those numbers. When the land class has goals,
  the calculator still runs, and the info `package.land-override` names the largest difference.
- **No `[land]`.** The worst-case calculator computes the land from the toleranced dimensions and the goals
  of the table `lands/<n>` for the package's land class (`chip`, `molded`, `gullwing`, `gullwing-fine` below a
  0.65 mm pitch, `nolead`, `smd-tab`). The land is `INFERRED` whatever the record says. A class without
  calibrated goals gives `package.no-goals`: the record needs a `[land]`.
- Through-hole drills are the lead's diagonal plus a clearance, pads the drill plus two rings; grid-array
  lands are the ball diameter times a ratio. A land narrower than `pitch - pad_gap` is clipped
  (`package.pads-clipped`).

Only the density `nominal` exists; `compact` and `robust` are reserved and refused (`FEN-3004`). A released
table never changes: a new calibration is `lands/2`, and a record names its version, so an upgrade never
moves a land silently.

## Conventions

`drawing = 1`, the convention for new packages: rounded-rectangle surface pads (20 % of the shorter side,
at most a 0.1 mm radius), through-hole pad 1 square; pin 1 at the top left, numbered counter-clockwise in the
top view (`A1` top left for a grid, rows lettered without `I`, `O`, `Q`, `S`, `X`, `Z`); a fabrication outline
of the nominal body with a chamfer at the pin-1 corner; a silkscreen outline cut 0.175 mm away from copper
with a pin-1 dot (an L mark for no-lead and grid packages) and a polarity bar for polarized two-terminals; a
courtyard 0.5 mm around the body and pads, rounded outward to 10 µm. `drawing = 0` reproduces the 0.6
catalog's drawing and placement, for records moved from the catalog. A released convention never changes;
a new look is `drawing = 2`.

## Bodies and STEP models

A record that gives a body height gets extruded bodies (`ComponentBody`, `component-body-volumes`): `body`
from the standoff minimum to the height maximum over the nominal outline, one foot and one shoulder per
gull-wing lead, the tab, and one pin per through-hole lead reaching below the board. Their heights work in
the placement and height checks like any body. A `drawing >= 1` footprint with bodies names
`${KIPRJMOD}/lib/<library>.3dshapes/<name>.step`; Fenolite writes that file itself
(`fenolite.backends.step`, AP214 planar solids, no dependency), so `fenolite export step` and KiCad's 3D
viewer find it. The bodies are volumes for clearance, not renderings: no fillet, bend or texture.

## In a script

```python
from pathlib import Path

from fenolite.dsl import Design, Footprint, Part, mm

design = Design("demo")
soic = Footprint.from_package(Path("packages/soic8.toml").read_text(encoding="utf-8"))
design.add_footprint(soic)  # Local:SOIC8_B4.9x3.9_P1.27
u1 = Part("U1", "Fenolite:Microcontroller", footprint=soic.lib_id)
design.add(u1)
u1.place(mm(10), mm(10))
```

`Footprint.from_package(text, library="Local", positions=None)` takes the record's text (the DSL reads no
file); `positions` picks one count of a connector series. The footprint is sealed: `.pad()`, `.graphic()`
and `.net_tie()` raise `DslError`. An unreadable record raises `DslError` with `FEN-3004`, an error finding
with its `package.*` code. `fenolite build` writes `lib/Local.pretty/<name>.kicad_mod` and, for a footprint
with bodies, `lib/Local.3dshapes/<name>.step`. `examples/generated/` uses one footprint of each family.

## Without a design: `fenolite library generate`

```
fenolite library generate packages/soic8.toml packages/connector_xh.toml --out lib --dry-run --json
fenolite library generate packages/soic8.toml packages/connector_xh.toml --out lib --confirm --plan <plan_id>
```

The command plans `lib/Local.pretty/<name>.kicad_mod` and `lib/Local.3dshapes/<name>.step` for every
footprint (every position count of a series, or `--positions N`), and one Altium PCB library
`lib/Local.PcbLib` holding them all (`--no-pcblib` leaves it out, `--no-step` the models; `--library` changes
`Local`). It writes all files or none; a package with an error finding writes nothing and exits 5.
`result.packages` reports each footprint's stamp, land (source, `z`, `g`, `x`, pad sizes, differences from
the calculation), courtyard and bodies. See [`cli-contract.md`](cli-contract.md), "`library generate`".

## The stamp

The description of a generated footprint carries its stamp, for example `gullwing/1 lands/1 drawing/1
nominal` (calculated) or `gullwing/1 manufacturer drawing/1`, followed by where the land came from
(`land: manufacturer S-0981 soldering footprint` or `land: calculated lands/1 nominal (INFERRED)`). Equal
record bytes and equal Fenolite code give equal footprints, `.kicad_mod` and `.step` bytes; a different
stamp under the same name is a library change.

## Findings

| code | severity | when |
|---|---|---|
| `package.missing-bound` | error | the calculator needs a bound the record does not give |
| `package.dimensions-inconsistent` | error | span not larger than the body, a pin row longer than the body, a terminal longer than half the body, an exposed pad larger than the body, a depopulated ball outside the grid |
| `package.pin-count` | error | `pins` disagrees with the arrangement, the sides or the depopulation |
| `package.no-goals` | error | the land class has no calibrated goals and the record has no `[land]` |
| `package.land-impossible` | error | the calculated or given land has no positive gap or size |
| `package.name-mismatch` | error | a generic name disagrees with the record's numbers |
| `package.pads-clipped` | warning | a land was narrowed or shortened to keep the pad gap |
| `package.land-override` | info | the manufacturer's land was used; names the largest difference from the calculation |

`fenolite explain <code>` prints each one.

## The catalog

The catalog's 100 footprints are c0259 records with explicit pads, written byte for byte as before
(`tests/data/catalog/footprints.sha256`). `drawing = 0` reproduces the family-shaped ones from a record with a
`[land]` holding the same numbers; a catalog record moves to its family in a later version, when the sources
it cites give the keys the 0.6 tables never held (span, lead length and width).
