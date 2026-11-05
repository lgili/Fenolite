# Schematic drafting rules of the wired layout

The `"wired"` layout of `fenolite build` (change c0406, `src/fenolite/backends/kicad/schwired.py`) draws
a sheet the way a schematic is usually drawn by hand. This page lists the rules it follows, each with
its public source (`docs/evidence/sources.md`), and keeps apart the choices that are Fenolite's own. No
rule, constant or layout here comes from any private or employer design: the rules come from the public
pages below, the constants were set on the designs authored for the tests (`tests/_wireddesigns.py`).

## Rules from public sources

| rule | how the wired layout applies it | source |
|---|---|---|
| Signals run from left to right: inputs on the left, outputs on the right | clusters are placed in columns by the direction of their pins: a cluster that drives a net (`output`, `power_out`, `open_collector`) lies left of the clusters that read it (`input`, `power_in`); connectors face the parts they serve | S-1700 (section "Organization"), S-1701 ("Identify Blocks") |
| Positive supplies at the top, ground and negative returns at the bottom | rail power symbols point up, ground and negative symbols point down, wherever the pin allows it | S-1700 ("Organization") |
| A dot marks a joint; wires that cross without a dot are not joined | a junction at every point where three wire directions meet, or where a pin holds two wires; crossings only where both wires run straight, and never at a junction | S-1700 ("Symbols"), S-1701 ("Junctions and Nodes"), S-0046 |
| Stagger a four-way joint into two T joints | no point holds four wire directions (the router refuses a fourth direction) | S-1700 ("Symbols") |
| Wires join only at their ends | each wire is cut at its joints, so no wire end and no pin lies on the inside of another wire | S-0046, S-0020 |
| Nets of one name are connected without a drawn wire; names keep a busy sheet readable | labels only where a net leaves a cluster that it cannot reach by a wire: a net on another sheet, a bus member between clusters, two clusters more than 101.6 mm apart, or a join the router cannot find; each drawn group carries exactly one label | S-1701 ("Net Names"), S-0046 |
| Supply nodes are drawn as power and ground symbols, which join every pin of their name | every pin on a supply net ends on a power symbol whose Value is the net name; supplies carry no label | S-1701 ("Recognize Voltage Nodes"), S-0046, S-0020 |
| Split a large schematic into functional blocks | one cluster per part with three pins or more, its passives around it; a sheet per module, block sheets as before (c0269) | S-1701 ("Identify Blocks") |
| A child sheet joins its parent through hierarchical labels and sheet pins | unchanged: the port nets of a block sheet keep their hierarchical labels and sheet pins (c0269) | S-0046 |
| Shortest paths on a grid | an A* search over cells of 1.27 mm with costs for steps, bends and crossings | S-1309 |

## Fenolite's own choices

These are not taken from a source; they were chosen for Fenolite and tuned on the authored test designs.

- **Glyphs.** The `GND` symbol is a stem with three bars of falling width and `RAIL` a stem with one bar,
  both drawn by Fenolite (`symembed.power_symbol`). The shapes are Fenolite's; they copy no library.
- **Decoupling.** A part between two supplies stands under the first anchor that has a pin on its
  non-ground supply, in a row under that anchor. This puts the capacitor beside the IC it serves on the
  sheet; the board placement is a separate step.
- **Clusters.** Two-pin parts attach to the best-ranked node over both of their pins (anchors with pins on
  several sides before connectors, more pins first); a part between two signal pins of one anchor (a
  feedback resistor) lies level above it; loose parts form chains.
- **Followers.** A connector, or a small part without inputs or outputs, stands beside the cluster it shares
  most nets with, mirrored to face it, instead of taking a column of its own.
- **Constants.** Channel width (4 × 2.54 mm), gaps between clusters (15.24 mm) and columns (20.32 mm), the
  wrap height of a column (152.4 mm), the reach of a wire (101.6 mm) and the search window and budget
  (`schwired.CHANNEL`, `CLUSTER_GAP`, `COLUMN_GAP`, `COLUMN_HEIGHT`, `ROUTE_REACH`, `WINDOW`, `BUDGET`).
- **Supply names.** The name patterns of `schwired.SUPPLY_NAMES` (`GND`, `AGND`, `0V`, `VSS…`, `+5V`,
  `3V3`, `VCC…`, `VDD…`, `VIN`, `VBUS`, `-12V`, `VEE…`); a name such as `VIN_RAW` or `PWR_LED` stays a
  signal. Interface kinds `power` and `ground` and power pins decide first.

## Measures

`fenolite.backends.kicad.schreadability.measure_sheet` counts what the rules above ask a sheet to avoid: labels
per kind, wires, junctions, power symbols, crossings, wires over a pin or a body, four-way points, T joints
without a junction and overlapping texts. The measures of the authored designs, readable against wired,
are in `docs/renders/c0406/README.md`.
