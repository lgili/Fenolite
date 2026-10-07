# Board analyses

How much current does this track carry, and how far apart are these two nets through air and along the
board surface? This page describes the analyses of `fenolite.analysis` and the command `fenolite analyze`:
what each one measures, where every constant comes from, what is left out, and how you state your own
requirements. The normative text is in `openspec/specs/board-analyses/spec.md`; the command contract is in
`docs/cli-contract.md` ("`analyze`").

**Fenolite measures; you decide.** No analysis claims conformance to a safety or design standard.
Fenolite ships no requirement value: no table from voltage to distance, no default temperature rise, no
default copper, plating or board thickness. A finding exists only against a requirement that you give.
Every reply carries `evidence.level` `INFERRED` or lower.

## Current capacity

One row is one track, one arc or one via. Its capacity is the current of one published fit:

```text
I = K · ΔT^b · A^c
```

`I` is the current in amperes, `ΔT` the temperature rise in kelvin and `A` the cross-section in square
mils. Fenolite states the fit as its public source, S-0269, publishes it. That source attributes the fit
to a standard. Fenolite did not consult that standard, reproduces none of its charts, tables or figures,
and claims no conformance to it.

### Capacity fit

Every constant of `fenolite.analysis.current` is in this table; `tests/unit/analysis/test_facts_page.py`
keeps the table and the code equal.

| constant | value | unit | fact, in Fenolite's words | source | level | hypothesis |
|---|---|---|---|---|---|---|
| `FIT_K_EXTERNAL` | 0.048 | — | the factor `K` for a conductor on an outer layer | S-0269 | INFERRED | H-G-AN-FIT |
| `FIT_K_INTERNAL` | 0.024 | — | the factor `K` for a conductor on an inner layer, half the outer one | S-0269 | INFERRED | H-G-AN-FIT |
| `FIT_EXP_RISE` | 0.44 | — | the exponent `b` of the temperature rise | S-0269 | INFERRED | H-G-AN-FIT |
| `FIT_EXP_AREA` | 0.725 | — | the exponent `c` of the cross-section | S-0269 | INFERRED | H-G-AN-FIT |
| `MIL_NM` | 25400 | nm | the fit takes the cross-section in square mils; one mil is 25 400 nm | S-0269 | INFERRED | H-G-AN-FIT |
| `FIT_MAX_EXTERNAL_MA` | 35000 | mA | the source calls the fit valid up to this current on an outer layer | S-0269 | INFERRED | H-G-AN-FIT |
| `FIT_MAX_INTERNAL_MA` | 17500 | mA | the same limit on an inner layer | S-0269 | INFERRED | H-G-AN-FIT |
| `FIT_MAX_RISE_MK` | 100000 | mK | the source calls the fit valid up to this temperature rise | S-0269 | INFERRED | H-G-AN-FIT |
| `FIT_MAX_WIDTH_NM` | 10160000 | nm | the source calls the fit valid up to this width (400 mils) | S-0269 | INFERRED | H-G-AN-FIT |
| `barrel_area_nm2` | π · (drill + plating) · plating | nm² | a via is judged by the cross-section of its plated barrel, with the outer factor; the drill is the finished hole | S-0270 | INFERRED | H-G-AN-VIA |

### What is computed

- **Cross-section.** A track or an arc has `width × copper thickness`. A via has its barrel,
  `π · (drill + plating) · plating`, rounded down.
- **Outer and inner.** The first and the last copper layer of the board's layer table are outer; the
  others are inner. A via always takes the outer factor.
- **Arithmetic.** The value is computed with `decimal` at 40 digits, the same on every platform (S-0012),
  and rounded **down** to whole milliamperes, so a capacity is never overstated by rounding.
- **Range.** A row outside the range the source states (width, rise or current) is still computed. It
  carries `in_range: false`, and the net gets one `analysis.fit-out-of-range` warning.
- **Nothing is assumed.** A track whose layer has no copper thickness, a via without a plating thickness
  and any item without a temperature rise are left out and counted (`analysis.input-missing`). The
  reply is then `UNVERIFIED`.
- **Per item.** `summary.nets` names the weakest item of each net. Parallel tracks, zones and planes are
  not combined: that would be an analysis of current flow.

Worked example: a 0.25 mm track on `F.Cu`, 35 µm of copper, 20 K of rise. The cross-section is
8 750 000 000 nm², and the fit gives 1187 mA. The same 1 mm track gives 2391 mA on an outer layer and
1195 mA on an inner one at 10 K.

## Clearance

The clearance of two nets is their distance **through air**.

- **On a layer.** The gap of two nets on one copper layer is the smallest exact gap between a shape of one
  net and a shape of the other (`docs/geometry.md`, "Thick shapes"). The shapes are those of the copper
  check (`docs/copper.md`): tracks, arcs, vias, pads in the board frame and zone fills.
- **Through air.** The clearance is the smallest gap on the two outer layers. A cut-out between two
  conductors does not lengthen it: air crosses a slot.
- **Inside the laminate.** A gap on an inner layer is a distance inside the board, a different
  insulation. It is listed in `gaps` and never enters `clearance`; you judge it with `embedded_nm`.
- **Across the board edge.** For copper on opposite faces, a path through air leaves one face at the
  boundary, descends the board thickness and reaches the other face. So the distance is at least
  `dA + dB + thickness` (the two distances to the boundary) and at most the path along the surface.
  Fenolite reports that interval (`H-G-AN-EDGE`); the exact path around a concave edge is a
  three-dimensional problem that it does not solve.

Worked example: two round conductors of 1 mm, 10 mm apart, have a clearance of 9 mm, with or without a
slot between them.

## Creepage

The creepage of two nets is the shortest path **along the board surface** between their copper on the
two outer faces.

- **The surface.** The two outer faces inside the outline, less every cut-out, joined by a wall of the
  board thickness along every boundary edge.
- **The path.** A chain of straight legs on a face that stay on the board, wall drops at boundary
  vertices, and wall crossings through the interior of one boundary edge, straight in the plane that
  unfolds the two faces and the wall. Paths bend only at boundary vertices and meet a conductor at the
  point of its core nearest to the other end of the leg (`H-G-AN-PATH`).
- **What is exact.** Whether a leg stays on the board is decided with the kernel's exact predicates.
- **What is bounded.** A length is a sum of square roots. The reported integer is below the length of the
  path by less than 2 nm; curved outline edges add their polygonisation band per bend.

Worked examples, both authored for Fenolite:

- Two round conductors of 1 mm at (0, 0) and (10 mm, 0), with a slot from (4 mm, −3 mm) to (6 mm, 3 mm)
  between them. The path runs 4.5 mm to a corner of the slot, 2 mm along the slot and 4.5 mm from the
  next corner: 11 mm. The clearance is still 9 mm.
- A 0.5 mm track on the top face and one below it on the bottom face of a 1.6 mm board, both 2 mm from
  the edge. The path runs 1.75 mm to the edge, 1.6 mm down the wall and 1.75 mm back: 5.1 mm, which is
  also the clearance across the edge.

## Open connections

`fenolite.analysis.connectivity.connectivity(design, *, pads, nets=None)` says, per net, which copper
islands it has and which connections are still open. `fenolite route` selects nets by it and takes its
verdict from it, and `fenolite net` shows it (`islands`, `open`). It reads the board model and runs no
tool; `pads` are the board-frame pad records of the backend, as for every analysis.

- **Copper joins where it touches.** Two shapes of a net on one copper layer are joined when they share
  a point: crossing tracks, a track that runs across a pad, two tracks side by side that overlap, an end
  cap that overlaps another track. The shapes of one via, and of one pad, are one item across their
  layers. The shapes are those of the copper check, and the test is exact on integers. Every stored fill
  polygon is an item of its own, so two islands of one zone stay apart.
- **What counts as an island.** An island counts when it holds a pad, a track, an arc or a via. A
  floating track and a lone via are islands; an island of zone fill alone is not: it is counted in
  `fill_islands` and joins nothing.
- **Open connections.** A net with `n` counted islands has `n − 1` open connections: the shortest tree
  that would join the islands, each connection between the nearest **anchors** of two islands. Anchors
  are a pad's position, the two ends of a track or an arc, and a via's position; fills have none. Each
  connection holds its two ends (`kind`, `where`, `position`, `layers`) and `length`, the straight
  distance in nanometres. A missing via shows as two tracks 0 nm apart on two layers. The result does not
  depend on the order of the board's items.
- **A net of one pad** has one island and nothing open; so has each net `unconnected-(…)` that a built
  board holds for a pin on no net.

**Where it differs from KiCad.** The number of open connections per net is the number of
`unconnected_items` that `kicad-cli pcb drc` reports for that net (`H-K-CONN-PARITY`): on 19 bench cases
and on the readable corpus boards (`docs/evidence/routing.md`, "Open connections"). Three things differ:

- A **copper drawing that holds a net** (a filled rectangle on a copper layer with a `net`) is copper of
  that net for KiCad and not for the model, which keeps the drawing's net as an opaque child. Such a net
  can read open here and closed in KiCad. One corpus board does.
- **The two ends** of a connection are Fenolite's rule. KiCad may name other items for the same
  connection, a zone among them.
- An **arc** is a polyline within 1 µm, a pad that its backend approximates is a superset, and **fills**
  are judged as stored: a board whose zones were not refilled is judged on the old fill.

`fenolite check` stays the gate, with KiCad's DRC. KiCad's report stops at 499 unconnected items; this
query has no cap. An item that cannot be shaped is counted per net in `unsupported`, gives one
`analysis.item-unsupported` warning per kind, and lowers the reply to `UNVERIFIED`.

## Power paths

A `[[current]]` row says that every item of a net carries the row's current, a branch to a capacitor
included. For a power net, name a **path** instead: the pads where the current enters, the pads where it
leaves, the current, the rise you accept and, if you want, the largest drop. A power path is not the
surface path of a creepage (`H-G-AN-PATH`); the two share only the word.

- **Network.** The net's tracks and arcs, vias, pads and fills are joined where their copper touches on a
  layer. A track is cut where it enters a fill of its net (the part inside is the fill's copper), at a pad
  or a via on its body, at the end of another track on its body and where two tracks cross. Vias joined to
  the same copper on each of their layers are one via group. A stored fill is one ring whose holes join
  it by slits of no width; the slits are removed to get the fill's outline and its holes.
- **Active copper.** An element is active when it lies on a path from a start pad to an end pad that
  passes each element once, and in series when every such path passes it. Copper that is not active
  carries no direct current and is not judged.
- **Narrowest section.** For a fill between two ports (the pads, tracks and via groups that touch it), the
  smallest length inside the copper of a closed curve that separates the two ports: the whole current
  crosses it. It is exact on the integer geometry (`H-G-AN-SECTION`). Its capacity is the fit of "Current
  capacity" at that width, an estimate: the fit is stated for a long isolated conductor
  (`H-G-AN-NECKFIT`).
- **Judging.** Where the topology says the whole current flows (a part of a track in series, a via group
  in series, a fill in series between exactly two ports), a capacity below the current is an error,
  `analysis.path-exceeded`. Anywhere else it is `analysis.path-undecided`: Fenolite computes no share of
  the current between parallel copper. A via group fails when the sum of its barrels is below the current,
  whatever the split.
- **Resistance and drop.** With a resistivity that you give (`--resistivity`, in nanoohm-metres; Fenolite
  ships none, and every resistivity in this guide is illustrative), each path gets an interval of its
  resistance. A part of a track is `ρ·L/(w·t)`. A via group is its barrels in parallel, `ρ·h/ΣA`, with
  `h` between the middles of its two copper layers by the stack-up. A fill between two ports lies between
  two bounds, with `R_s = ρ/t` the sheet resistance, `ℓ` the shortest path inside the fill between the two
  ports, `w` their narrowest section and `A` the fill's area outside the ports:

  | bound | value | why |
  |---|---|---|
  | lower | `R_s · ℓ² / A` | the potential that rises evenly along the distance from one port is a trial function, and by Dirichlet's principle (S-0682) a trial function bounds the energy, hence the conductance, from above |
  | upper | `R_s · A / w²` | every line of equal potential separates the two ports, so it is at least `w` long; with the Cauchy–Schwarz inequality the conductance is at least `w² / (R_s · A)` |

  The two bounds are **Fenolite's own derivation** (`H-G-AN-POUR`, `INFERRED`, checked against a
  finite-difference solution in the tests). The sources give the two facts it starts from, not the bounds:
  the solution of the boundary problem minimises the Dirichlet energy (S-0682), and one metric bounds the
  extremal length of a family of curves from below by its squared length over its area (S-0681). Neither
  page, as read, states a bound of the resistance of a conductor. On a strip between two plates both equal `R_s · L / W`; on a pour with a neck they lie far
  apart, and the interval is reported as it is. The path's low end is the network at its low values, a fill
  of more than two ports shorted; its high end is the network at its high values, or the best single chain
  (`H-G-AN-POUR`, `H-G-AN-NETWORK`). The drop is the current times the resistance. It is a measure against
  your limit, **not a simulation**: no current density, no temperature and no share of parallel copper is
  computed.

Limits of the power paths:

- Ports are ideal contacts, and the vias of a group share the current equally; crowding at the edge of a
  via array is not modelled.
- A port is taken by the convex hull of its copper. When a hole lies inside that hull between the port's
  shapes, the section is only an upper bound and is judged as undecided.
- A section wider than the width its source states for the fit is outside the fit's range.
- A fill with more than 400 boundary points takes the gap of its two ports in plan view as `ℓ`, which is
  never longer than the path inside it, so the lower bound stays a lower bound.
- Two fills of one net that touch only each other are not joined; a track whose side overlaps a fill
  without its centre line or an end reaching it is not joined to it.
- **An imported Altium board** is read like any other: its pours are fills. Copper of an inner plane that
  the import does not hold as a fill is not in the model, so a path through it is reported as
  `analysis.path-open`. A via counts at one diameter on every layer of its span, also where the document
  holds no pad shape for it.
- **Copper graphics**, those of a footprint included, are counted and not used.

## Insulation between layers

With the kind `insulation`, each pair of nets gets the shortest distance through the laminate between
copper of one net on a layer and copper of the other on another layer: `√(g² + h²)`, with `g` their
smallest gap in plan view and `h` the depth of the top face of the lower layer less the depth of the
bottom face of the upper one (`H-G-AN-INSUL`). `sheets` counts the dielectric entries of the stack-up
between those two layers; it is data, and Fenolite judges no sheet count. `insulation_nm` is judged
against the measure as every distance is.

- The depths come from the stack-up of the board. Fenolite assumes no thickness: without a depth for a
  layer the value is absent and `analysis.input-missing` names `stack-up`.
- Copper of any net on a layer between the two is not considered.
- No KiCad check measures a distance between layers (`H-K-AN-LAYERS`).

## Grooves

Without a groove width every cut-out and every notch lengthens a creepage, whatever its width. With a
width (`--groove-width`, or `groove_nm` of a distance row) a creepage path crosses a groove narrower than
that width as if it were not there (`H-G-AN-GROOVE`):

- a **cut-out** is bridged whole when it has a double normal shorter than the width: a chord inside it
  that meets its boundary at right angles at both ends. For a slot that is its width;
- a **pocket** of the outline, the region between an edge of the outline's convex hull and the outline,
  is filled when its mouth is shorter than the width.

Bridging only removes obstacles, so it can only shorten a creepage. The clearance does not change.

- A pair that is judged for creepage, whose path bends at a groove or crosses its wall, and for which no
  width is given, is counted in `analysis.input-missing` (`groove width`).
- A cut-out is bridged whole: a wide cut-out with one narrow arm is bridged when the arm is narrow.
- A notch in the floor of a wide bay is not a pocket of its own: the bay is decided by its mouth.
- A V-shaped groove is not cut at the groove width.
- KiCad 10.0.6 applies no groove width to a cut-out (`H-K-AN-GROOVE`), so nothing brackets this value.

## Conductors on the path

Copper on an outer layer that belongs to neither net of a pair conducts: a creepage path and a clearance
chain reach such a conductor and leave it from any point of its copper at no length, and a via or a pad
with copper on both outer layers joins the two faces (`H-G-AN-OVER`). The measure names the conductors it
crosses in `over`.

- When a conductor belongs to a **third net**, an info (`analysis.creepage-over`) names it: the distances
  from each net of the pair to that net are the ones its voltage acts across, and the hint names those
  pairs.
- KiCad stops a creepage at a track of another net and judges the two halves only under rules for them
  (`H-K-AN-SPLIT`); Fenolite gives the pair the conservative value and names the conductor.
- Between two nets that lie far apart among thousands of conductors the search stops at a budget; such a
  pair is counted in `analysis.item-unsupported` (`conductors`) and its values are upper bounds.

## Measures and judging

A distance is an interval `low ≤ d ≤ high` in nanometres, with the layer, the points of the path and the
two items. A requirement `r` is judged the same way for every measure:

| case | result |
|---|---|
| `high < r` | an error (`…-below`) |
| `low < r ≤ high` | a warning (`…-undecided`): the measure does not decide |
| `low ≥ r` | nothing |

A search stops at the largest requirement of the pair. When it finds no shorter path, the measure is
`bounded`: `low` is that limit and `high` is absent, which is enough to pass.

## Length

How long is this net, and how far does a signal travel from one pad to another? `fenolite analyze
--kinds length --net GLOB [--from REF]` gives two lengths per net (change c0106). It judges nothing: the
limits are the length and skew rules of the design.

- **The total** is the length KiCad's DRC judges, counted as the KiCad major of `--kicad-version` counts
  it (10 by default): the centre lines of all tracks and arcs of the net, stubs and dangling copper
  included (`routed`), plus one height per via (`vias`), plus the die length of each pad (`die`). A track
  counts from its end inside a pad, not from the pad edge. A through-hole pad adds no height. A zone fill
  adds no length and is not copper a via joins.
- **The path** is the shortest length along the copper from a start pad to each other pad of the net
  (`paths`): the start pad is the one `--from REF` or `--from REF-PIN` names, else the first pad by
  reference and number. A path adds the die lengths of its two end pads. `off_path` is the copper that lies
  on no path: a stub, a branch end. The total counts it, so the total is longer than any path of a net
  with a stub or a second load, and an info (`analysis.length-stub`) says by how much.
- `routed` equals the `length` of `fenolite net`: every arc and every track is measured by the kernel
  functions `arc_length` and `segment_length` (`docs/geometry.md`, "Path lengths"), which also measure the
  spans of `equivalent --level 5`.

**The two majors count a via apart** (`docs/formats/kicad/length.md`):

| | KiCad 10 | KiCad 9 |
|---|---|---|
| depth of a copper layer | first layer 0, last layer the sum of all copper and dielectric, an inner layer the thickness above it plus half its own | every layer the thickness above it plus half its own |
| height of a via | the depth difference of the outermost two layers on which a track, an arc or a pad of the net touches the via; 0 below two | the depth difference of the via's own two end layers when the net touches it on both; else 0 |

So a through via that joins `F.Cu` and `In1.Cu` adds the depth of `In1.Cu` on 10 and nothing on 9. With
the facts of 10 the path of an unbranched net equals its total. With the facts of 9 a path through such a
via is longer than the total: the path weighs the layer change, and KiCad 9 counts no height there. The
reply states both. `summary.length.major` names the major.

**The stack-up.** The depths come from the board's stack-up (`summary.length.stackup` is `board`). A
KiCad file without a stack-up is counted on the default stack-up KiCad itself assumes for it, copper
layers of 35 µm and equal dielectrics in the board thickness less 20 µm, with one
`kicad.length.default-stackup` info (`stackup` is `default`): that is what KiCad's DRC judges for the
file, not a property of a real board. A file whose stack-up node Fenolite does not read
(`kicad.board.stackup-unused`) gets no depth (`stackup` is `none`): KiCad 10.0.6 still counts that node,
so neither it nor the default is claimed, the via heights count 0 and the reply is `UNVERIFIED`. A project
that sets `use_height_for_length_calcs` to `false` counts no via height (`summary.length.count_vias`).

**Limits of the length kind.**

- Zones add no length, and a layer change inside a through-hole pad adds none, as in KiCad.
- Tracks and arcs that cross without an end inside each other are not joined in a path, while KiCad
  joins any overlap. The total does not depend on joins; a path does, and a pad the copper does not reach
  this way has no length (`analysis.length-open`).
- A pad or a via on the body of a track joins it at the point of the centre line nearest to its own
  position.
- On KiCad 9 a path can exceed the total (above).
- The default stack-up is measured for 2, 4, 6 and 8 copper layers on KiCad 10.0.6.
- Pair skew (`result.pairs`) needs the pair names of change c0104 and is empty until that change is in.
- An Altium PCB document has no length facts: no public source recorded here says how Altium counts a
  via or a die length. The kind then gives routed lengths and paths whose layer changes weigh 0, one
  `analysis.input-missing` warning and the level `UNVERIFIED`.

## Limits

Read these before you rely on a value.

- **Holes** are not obstacles of the surface path. Ignoring a hole can only shorten the reported path.
- **Every cut-out counts** unless you give a groove width ("Grooves"). Fenolite ships no width below
  which a groove does not count.
- **Solder mask, coatings, components and their leads** are ignored.
- **Copper of a third net**, or of none, on the path is crossed at no length and named ("Conductors on
  the path"). Graphics on a copper layer are not read as copper: they are counted, and the reply is then
  `UNVERIFIED`.
- **Without a board thickness** no path crosses a wall. A pair with copper only on opposite faces then has
  no clearance and no creepage (`analysis.input-missing`). A pair that shares a face is measured on each
  face alone, and `summary.faces_alone` counts such pairs: a shorter path around the edge or through a
  slot's wall may exist.
- **Approximated shapes.** An arc is a polyline within a band of 1 µm + 1 nm, which widens its interval.
  A pad that its backend marks as approximated is a conservative superset: its gaps are lower bounds.
- **Pads need a backend that gives them in the board frame.** Otherwise they are counted in
  `analysis.item-unsupported` and the reply is `UNVERIFIED`.
- **Capacity** is that of one isolated conductor by one fit. It knows no neighbouring track, no pour, no
  ambient and no board material.

**Thicknesses from a KiCad stack-up (c0101).** A KiCad board whose `setup` holds a stack-up that KiCad
uses now gives the copper thickness per layer and the board thickness, as an Altium board already did;
an option still wins. The reply says where the board thickness came from
(`inputs.board_thickness_source`: `option`, `stackup` or `null`) and shows the stack-up it read
(`inputs.stackup`). Fenolite still assumes no thickness: a board without a stack-up and without options
gets `analysis.input-missing`.

## Oracles

Which independent tool could check each analysis, and what was done instead:

| analysis | level | check today | oracle that could exist |
|---|---|---|---|
| arithmetic of the fit | mechanical | a second computation in the test, within 1 mA | none needed |
| capacity of tracks, arcs and vias | `INFERRED` (`H-G-AN-FIT`, `H-G-AN-VIA`) | the arithmetic only | KiCad's calculator computes the same fit, in its GUI only; no command |
| clearance on a layer | `INFERRED` (`H-G-AN-GAP`) | authored cases by hand | the `clearance` rule canaries of the copper check, for the gap primitive |
| creepage | `INFERRED` (`H-G-AN-PATH`) | hand-computed cases; a grid search | KiCad's `creepage` rule as a bracket, recorded (`H-K-AN-CREEP`) |
| clearance across the edge | `INFERRED` (`H-G-AN-EDGE`) | hand-computed cases | none |
| narrowest section of a fill | `INFERRED` (`H-G-AN-SECTION`) | hand-computed cases; a grid cut | KiCad's connection width, on plain necks only (`H-K-AN-NECK`) |
| capacity of path elements and sections | `INFERRED` (`H-G-AN-FIT`, `H-G-AN-VIA`, `H-G-AN-NECKFIT`) | the arithmetic only | KiCad's calculator, in its GUI only |
| resistance and drop of a path | `INFERRED` (`H-G-AN-POUR`, `H-G-AN-NETWORK`) | a finite-difference solution in the test | a field solver run as a subprocess; none chosen |
| insulation between layers | `INFERRED` (`H-G-AN-INSUL`) | hand-computed cases | none; KiCad judges no distance between layers (`H-K-AN-LAYERS`) |
| grooves | `INFERRED` (`H-G-AN-GROOVE`) | hand-computed cases; generated boards | KiCad's groove setting, if a later version applies it to cut-outs (`H-K-AN-GROOVE`) |
| conductors on the path | `INFERRED` (`H-G-AN-OVER`) | hand-computed cases; a grid search | none; KiCad stops the path at the conductor (`H-K-AN-SPLIT`) |
| net totals (tracks, arcs, via heights, die lengths, the project switch, the default stack-up) | `INFERRED` (`H-K-NETLEN-TOTAL`, `H-K-NETLEN-VIA10`, `H-K-NETLEN-VIA9`, `H-K-NETLEN-STACKUP`) | bench values by hand | KiCad's `length` rule as a bracket 1 µm below and above each total: the canaries `length-total-*` and `length-via-*` (`docs/evidence/length.md`) |
| pin-to-pin paths and stubs | `INFERRED` (`H-G-NETLEN-PATH`) | hand-computed cases; the path equals the total on unbranched nets | none; no tool prints a pin-to-pin length |

The KiCad bracket is supporting data. It never gates and never raises a label.

## The requirements file

Your requirements go into a TOML file of schema `fenolite.requirements.v0`. Units are in the key names,
so every number is an integer. This example is authored for Fenolite; its values are illustrative, not
requirements:

```toml
# authored for Fenolite; illustrative values, not requirements
schema = "fenolite.requirements.v0"

[[current]]
select = { net = "VBUS" }
milliamps = 2000
temp_rise_mk = 20000

[[distance]]
a = { netclass = "Mains" }
b = { netclass = "Default" }
millivolts = 230000

[[distance]]
a = { net = "L" }
b = { net = "N" }
clearance_nm = 2000000
creepage_nm = 3000000

[[step]]
up_to_mv = 50000
clearance_nm = 500000
creepage_nm = 1000000

[[step]]
up_to_mv = 300000
clearance_nm = 2000000
creepage_nm = 3000000
```

- **Selectors.** A table with exactly one of `net` and `netclass`, whose value is a glob. A net without a
  class has the class `Default`.
- **`[[current]]`.** The current a net must carry and the temperature rise you accept. When several rows
  match a net, the largest current governs.
- **`[[distance]]`.** Two selectors and either distances (`clearance_nm`, `creepage_nm`, `embedded_nm`)
  or a voltage in `millivolts`. When several rows match a pair, the largest value of each quantity
  governs.
- **`[[step]]`.** Your own table from voltage to distance. A voltage takes the first step at or above it.
  Fenolite does **not** interpolate between steps: whether and how to interpolate is a rule of the
  standard you follow. A voltage above every step gives no requirement and a warning.
- **Voltages.** The voltage of a pair is the number you write. Fenolite derives none from net names and
  does not choose between peak, RMS or working voltage.
- A float, an unknown key or a missing key is an error that names the key.

Three additions of change c0115 use the same schema name. They are optional, so every earlier file loads
unchanged; the other direction does not hold: **Fenolite 0.2.x and 0.3.0 refuse a requirements file that
holds a `[[path]]` row, `insulation_nm` or `groove_nm`**, because their key sets are closed. This example
is authored for Fenolite; its values are illustrative, not requirements:

```toml
# authored for Fenolite; illustrative values, not requirements
schema = "fenolite.requirements.v0"

[[path]]
from = ["J1-1"]
to = ["Q1-2", "Q2-2"]
milliamps = 20000
temp_rise_mk = 10000
drop_mv = 50

[[distance]]
a = { net = "HV" }
b = { net = "LV" }
creepage_nm = 3000000
insulation_nm = 400000
groove_nm = 1000000
```

- **`[[path]]`.** `from` and `to` are non-empty arrays of pad names `REF-PIN`: where the current enters
  and where it leaves. `milliamps` is the current, `temp_rise_mk` the rise you accept and `drop_mv`,
  optional, the largest voltage drop ("Power paths").
- **`insulation_nm`**, on a distance row or a step: the distance through the laminate you require between
  copper of the pair on two layers ("Insulation between layers").
- **`groove_nm`**, on a distance row beside its distances: the width below which a groove is bridged on
  the creepage path of the pair ("Grooves"). The largest of the matching rows and of `--groove-width`
  governs.

## The command

```console
fenolite analyze board.kicad_pcb --kinds current --temp-rise 10 --copper-thickness 35um
fenolite analyze board.kicad_pcb --kinds clearance,creepage --pair L N --board-thickness 1.6mm
fenolite analyze board.kicad_pcb --requirements requirements.toml --via-plating 25um --board-thickness 1.6mm
fenolite analyze board.kicad_pcb --kinds clearance --within 0.5mm
fenolite analyze board.kicad_pcb --kinds power --path J1-1 U1-1 --temp-rise 10 --copper-thickness 35um
fenolite analyze board.kicad_pcb --kinds creepage,insulation --pair HV LV --groove-width 1mm
fenolite analyze board.kicad_pcb --kinds length --net 'USB_*' --from U1
```

The kinds `power`, `insulation` and `length` run only when you name them.

The command is read-only: it runs no tool and writes no file. An error finding gives exit code 5. The
options and the result keys are in `docs/cli-contract.md`.
