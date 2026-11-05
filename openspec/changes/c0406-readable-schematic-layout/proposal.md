# Draw generated schematics with wires, power symbols and signal flow

## Why

The maintainer read the KiCad schematics that `build` generated for a board and could not follow the
circuit: almost every pin carries a global label, so a reader has to search the sheet for matching texts to
see what connects to what. The "readable" layout of c0070 snaps some two-pin parts beside an IC pin with a
wire, but the pair still carries a label, every other pin keeps its own label, the supplies are labels too,
and the parts are packed in rows by reference, not by function or signal flow.

A good hand-drawn schematic, as public drafting practice describes it (IEEE 315 / IEC 60617 symbols, the
common textbook and application-note style; sources in `docs/schematic-drafting.md`), reads differently:
local connections are wires, supplies are power symbols with the rails at the top and ground at the
bottom, signals run from left to right, the parts that serve a pin (a decoupling capacitor, a pull-up,
a divider, a base resistor) sit next to that pin, and labels are kept for the nets that leave the drawing.
This change makes that the default for every board Fenolite generates.

## What Changes

- A new KiCad sheet layout `"wired"`, the new default of `build` (`--schematic-layout wired`); `"readable"`
  (c0070) and `"grid"` (c0061) stay available and keep their bytes, and `generate_schematic` keeps
  `"readable"` as its own default, so the library API and the conversion path are unchanged.
- **Clusters.** Each part with three pins or more is an anchor; each two-pin part is drawn next to the
  anchor pin it serves, in columns beside that side of the anchor, in the order of the anchor's pins: a part
  between two signals in series, a part between a signal and a supply ending in a power symbol, a part
  between two supplies (decoupling) in a row under the anchor. Chains (a resistor then an LED) continue
  outwards. Two-pin parts that serve no anchor are clusters of their own.
- **Signal flow.** Clusters are placed in columns from left to right by the direction of their pins (an
  output or power output drives an input or power input), connectors that feed the circuit on the left;
  within a column clusters follow the order of their neighbours to reduce crossings.
- **Power symbols.** Every pin on a supply net (a declared power or ground interface, a net on a power
  pin of a part, or a supply-like name) gets a Fenolite-authored power symbol instead of a label: a ground
  symbol (`fenolite:GND`, three bars) pointing down, a rail symbol (`fenolite:RAIL`, a bar) pointing up,
  its Value the net name. KiCad joins power symbols by their Value (measured on 9.0.9 and 10.0.6). A
  supply net drawn with power symbols and driven by no power output gets a power flag, as declared
  supplies already do.
- **Wires.** Every other net on a sheet is routed orthogonally on the 1.27 mm grid by a deterministic
  maze search (A*, S-1309) that never passes over a body, a text, a label, a pin or a wire end, never
  runs along another net, crosses other wires only straight through, never makes a four-way joint and
  puts a junction dot at every T. A net that would cross much of the sheet, a bus member between
  clusters, or a net the router cannot draw within its budget is drawn per cluster instead, and joined by
  labels.
- **Net names.** KiCad names an unlabelled or locally labelled net `Net-(…)` or `/<sheet>/<name>`, while
  the board keeps the circuit's names, so each drawn group of a net carries exactly one global label (or
  the hierarchical label of a block port), placed on one of its wires or at its one pin, clear of
  everything else. A label therefore names a net once per drawn group instead of once per pin.
- **Texts.** Every Reference and Value is written at a computed pose, clear of bodies, wires, labels,
  power symbols and other texts.
- **Fallbacks.** A sheet with units named by `schematic-placements.toml`, or one that does not fit A0,
  is drawn with the `"readable"` layout and an info issue `build.schematic-wired-fallback`.
- **Own netlist.** Fenolite's own netlist of a generated sheet (`sch_netlist`, used by `check` parity
  without `kicad-cli`) reads wire chains, junctions, crossings, labels on wires and Fenolite's power
  symbols, so the wired sheets stay inside its grammar.
- **Measures.** `fenolite.backends.kicad.schreadability.measure_sheet` counts, per sheet, labels by kind, wires,
  junctions, power symbols, crossings, wires over pins or bodies, four-way joints, and overlaps of texts,
  labels and bodies; tests hold the authored designs to bounds on these.

## Capabilities

### Modified Capabilities
- `kicad-schematic`: the `"wired"` layout, power symbols and net names on a generated sheet, the own
  netlist of a wired sheet, and the readability measures.

## Non-goals

The Altium SchDoc generator (it has the opt-in block composition of c0165; adopting the same rules there
is a follow-up), the schematic of an Altium to KiCad conversion (still `"readable"`), frames drawn around
block groups on one sheet (the model has no sheet graphics; modules already get titled sheets of their
own), buses drawn as bus wires, keeping wires through a placements file (`sync` of an edited sheet keeps
symbol positions only), and recognising circuit functions by part names.

## Evidence level required

KiCad facts used here (power symbols named by their Value, coincident pin ends join, wire ends, T joins,
junctions, labels on a wire's inside) are recorded in `docs/formats/kicad/schematic.md` with the
measurement; the generated sheets are checked by `kicad-cli sch erc` and `sch export netlist` on 10.0.6
locally (9.0.9 in the pinned image where cheap) and by CI. Layout choices are Fenolite choices, not
format facts. Every design used is authored for these tests; no private board, template, statistic or
constant is used.

## Impact

`src/fenolite/backends/kicad/` (`schwired.py` new, `schgen.py`, `symembed.py`, `sch_netlist.py`),
`src/fenolite/backends/kicad/schreadability.py` (new), `lens/build.py` and `cli/cmd_build.py` (default layout),
`docs/`, the agent guide, `CHANGELOG.md`, `tests/data/build_bytes.json` (the sheets of every example
change), authored tests and renders under `docs/renders/c0406/`.
