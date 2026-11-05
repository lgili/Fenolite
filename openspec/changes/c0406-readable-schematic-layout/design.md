# Design: wired schematic layout (c0406)

## Context

`schgen.generate_schematic` turns a circuit into KiCad sheets: one sheet per module, symbols in cells
packed in rows (`schlayout.layout_units`), a global label at every connected pin, satellites snapped with
one wire (c0070). The format facts it relies on are in `docs/formats/kicad/schematic.md`. The drafting
practice this change follows is in `docs/schematic-drafting.md` (new), with its public sources.

## Decisions

### D1. A new layout, the new build default

`schgen.LAYOUTS` becomes `("readable", "grid", "wired")`. `build` and `fenolite build` default to
`"wired"`. `generate_schematic(layout=...)` keeps `"readable"` as its own default so the library API,
the Altium-to-KiCad conversion and every existing unit test of the generator keep their output. The
`"readable"` and `"grid"` sheets keep their bytes.

### D2. Net roles

A net is a **supply** when it is a member of an interface of kind `power` or `ground`, when a fitted
part's pin of type `power_in` or `power_out` is on it, or when its name has the form of a supply
(`GND`, `AGND`, `PGND`, `0V`, `VSS…`, `VCC…`, `VDD…`, `VEE…`, `VIN`, `VBAT`, `VBUS`, `+5V`, `3V3`,
`-12V` and the like; the patterns are in `schwired.SUPPLY_NAMES`). A supply is **ground** when its
interface kind is `ground` or its name has a ground form; **negative** when its name starts with `-` or
`VEE`; otherwise a **rail**. Every other net is a **signal**. A signal is a **bus member** when an
interface of kind `i2c`, `spi`, `uart` or `usb2` names it. Names are matched case-insensitively on the
net's stored name; no name list comes from any private design.

### D3. Power symbols, authored for Fenolite

`symembed.power_symbol(kind, target, library)` gives `GND` (a stem and three bars of decreasing width,
the IEEE 315 / IEC 60617 shape) or `RAIL` (a stem and one bar). Each is flagged `power` (`power global`
for target 10), has one hidden `power_in` pin of length 0 at the origin named `~`, and a visible Value.
An instance's Value is the stored net name, its Reference `#PWR<nnn>` numbered over the whole design.
Measured on 2026-11-05 with `kicad-cli` 10.0.6 and the pinned 9.0.9 image: two instances of one such
symbol whose Values are `+5V` and `VBAT` give the nets `+5V` and `VBAT`, a global label `VBAT` joins the
second, and a pin end on the pin end of a power symbol is on its net. The symbols live in the flag
library (`symembed.flag_library`), beside `PWR_FLAG`.

A power symbol always points away from the pin it serves: the glyph continues the direction of its stub
wire. Ground and negative supplies are drawn pointing down and rails pointing up wherever the pin's side
allows it (a pin on the bottom or top edge, a two-pin part placed vertically, or a side pin whose
neighbour in that direction is free); otherwise the glyph points outwards from a side pin.

A supply net drawn with power symbols needs a driver for ERC: each such net that no fitted `power_out`
pin drives gets one power flag on the root sheet, joined to a power symbol of its net by a wire (the
declared supplies of c0061 are a subset).

### D4. Clusters

An **anchor** is a unit with three pins or more, a unit of a multi-unit part, or a part whose two pins do
not face each other. A **two-pin part** is the one unit of a component with two pins on one axis facing
each other (`schlayout.is_satellite` without its net conditions). Anchors are drawn unturned.

Anchors are ranked: anchors with pins on more than one side first, then by falling pin count, then in
layout order (a connector, whose pins all lie on one side, ranks after the parts it serves). Two-pin parts
attach, in natural path order, to the best-ranked **node** over both of their pins: a pin of an anchor, or
the far pin of a two-pin part already attached. A part between a signal and a supply (or an open pin) attaches to the node of its signal and
ends in a power symbol; a part between two signals attaches in series and its far pin becomes a node; a
part between two supplies (decoupling, bulk) attaches to the first anchor that has a pin on its non-ground
supply and joins that anchor's **decoupling row**. A node takes any number of power-terminated parts and
at most one series part. A part between two signal pins of one anchor (a feedback resistor) is a
**bridge**: it lies level above everything drawn over that anchor, centred on the span of its two pins.
Parts that attach nowhere form **chains** (paths of loose parts that share signal nets, stacked with a
power symbol at each supply end) or clusters of their own.

Geometry, relative to the anchor's origin: the parts attached to the pins of one side form **columns**
beside that side (left, right) or **rows** above or below it (top, bottom); column 1 holds the parts on
anchor pins, column 2 the parts on the far pins of column 1, and so on. In a column the parts keep the
order of their nodes along the side and are packed so that each lies as close as possible to the height
of its node: a straight wire when nothing is in the way, a single jog otherwise. A series part lies along
the axis of the side (horizontal beside a left or right side); a power-terminated part beside a side lies
along the axis too and its power symbol hangs from its far pin, down for ground and up for a rail, inside
its slot; above or below the anchor parts stand vertically. The decoupling row lies under the anchor,
each capacitor vertical with its rail symbol on top and its ground symbol below, the row starting on the
side of the supply pin. Each slot keeps room for the part's Reference and Value.

### D5. Placement of clusters: signal flow

Clusters are placed in columns from left to right. A directed edge joins cluster A to cluster B when a
non-ground net holds an `output`, `power_out` or `open_collector` pin of A and an `input` or `power_in`
pin of B. A cluster made of a connector (an anchor whose pins are all `passive`) that is on such a net
with an input of another cluster is a source. The column of a cluster is the length of the longest edge
path into it (cycles broken in layout order); a cluster without edges takes the column of its first
neighbour on a signal net, else column 0. Within a column clusters are ordered by the mean row of their
neighbours in the column before (one barycentre pass, ties in layout order). A column taller than
`COLUMN_HEIGHT` (152.4 mm) wraps into the next. Three alignment passes then move each cluster towards the
median height difference of its pins and the pins of their neighbours in other columns, keeping the order
of the column. A **follower** (a one-sided anchor such as a connector, or a unit of at most four pins none
of which is an input or output) takes no column of its own: it stands beside the drawn cluster with which
it shares most signal nets, on the side where that cluster's pins lie, mirrored to face it. Columns are
spaced by a routing channel. Block schematic groups (c0269) take a
column each, in group order, before any other cluster. Sheet references take the last column; power
flags a row at the bottom.

### D6. Routing

Each sheet is a grid of `GRID` (1.27 mm) cells. Obstacles: every body box and pin line, every text and
label room, every power symbol, the page margin and the title band. A wire may pass a pin point or wire
end only if it ends there and is of that net; it may share no cell edge with another net; it may cross a
wire of another net only straight through a point where that wire runs straight. A pin is left and
entered along its outward direction.

Nets are routed in a fixed order (fewest pins first, then by span, then by name), each as a Steiner tree
grown from its first pin: every further terminal is joined to the nearest point of the tree by an A*
search (S-1309) with costs 1 per step, 6 per bend and 12 per crossing, inside the terminals' box grown by
24 cells; a join on the inside of a straight run or at a corner makes a T and a junction, and no point
takes a fourth direction. The search stops after a fixed number of expansions per terminal.

A net is drawn per cluster (each cluster's part of it wired, the clusters joined by labels) when it is a
bus member between clusters, when two of its clusters are more than `ROUTE_REACH` (101.6 mm Manhattan)
apart, or when a terminal cannot be joined.

### D7. Net names and labels

KiCad names a net from a global label or a power symbol by its text, from a local or hierarchical label
as `/<sheet path>/<text>`, and without a label as `Net-(…)` (S-0046; `H-K-DRAWN-NAMES`). The board keeps
the circuit's names, so each connected group of a signal net on a sheet carries exactly one label: the
global label of the net, or the hierarchical label of a block port net (c0269). The label of a group of one
pin lies at that pin, pointing away from the body, as before. The label of a wired group lies on one of
its wires, at a point that is no corner, joint or crossing, turned across the wire, where its room is
free; vertical runs are tried first (the label then reads level), longest first, each from its middle
outwards; when no point is free, the inner point and direction whose room holds the fewest busy cells.
A label's id is `<sheet>:label:net:<module>:<net name>:<group>`. KiCad and the own netlist join
a label to the wire its anchor lies on. Two-pin parts of a series chain need no label of their own.

### D8. Texts

Every Reference and Value is written at a pose the layout computes (`sch.field_pose_ext`): two lines of
`ORIGIN_STEP`, centred, above an anchor's body (or to its right when a pin leaves it upwards), above a
horizontal two-pin part, beside a vertical one; a power symbol's Value beyond its glyph. The rooms of
these texts are obstacles for the router and for label placement.

### D9. Own netlist of a wired sheet

`sch_netlist.grammar_issues` accepts what the wired layout writes: junctions (but no bus, bus entry or bus
alias), wire ends on pins, on other wire ends or on junctions, crossings of two wires without a
junction (not joined), labels on a wire's inside (joined to it) and instances of Fenolite's `GND` and
`RAIL` power symbols (joined to the global net of their Value). A wire end on the inside of another wire
without a junction, a pin on the inside of a wire, and other power symbols stay outside the grammar.

### D10. Fallbacks

A sheet with a unit named by `schematic-placements.toml`, or whose wired drawing does not fit A0, is drawn
with the `"readable"` layout, reported by `build.schematic-wired-fallback` (info). `sync` of an edited
wired sheet keeps symbol positions only; the next build then draws that sheet as `"readable"`.

### D11. Measures

`schreadability.measure_sheet(sheet) -> SheetMeasures` reads a `SchematicSheet` with its embedded
definitions: counts of global, hierarchical and local labels, wire segments, junctions, power symbols;
crossings (two wires of different groups meeting inside both), wires over a pin point or body,
junctions with four or more directions, T joints without a junction, and overlaps between the boxes of
texts, labels, power symbols and bodies of different owners (text extents estimated: one character
height per character, 2 mm per line).

## Risks

- Dense IC sides: columns grow tall and some nets fall back to labels. Measured on the authored designs;
  the fallbacks are counted in `GeneratedSchematic.fallbacks`.
- Runtime: the router is bounded by expansions per terminal and by `ROUTE_REACH`; a large flat sheet
  degrades to labels, never to a timeout.
- `build_bytes.json`: every example's schematic changes; the table is measured again in this change.
