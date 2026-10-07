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

## Limits

Read these before you rely on a value.

- **Holes** are not obstacles of the surface path. Ignoring a hole can only shorten the reported path.
- **Every cut-out counts**, whatever its width. Fenolite has no rule for a groove too narrow to count.
- **Solder mask, coatings, components and their leads** are ignored.
- **Copper of a third net** between two conductors is ignored. A floating conductor can shorten the real
  leakage path.
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

## The command

```console
fenolite analyze board.kicad_pcb --kinds current --temp-rise 10 --copper-thickness 35um
fenolite analyze board.kicad_pcb --kinds clearance,creepage --pair L N --board-thickness 1.6mm
fenolite analyze board.kicad_pcb --requirements requirements.toml --via-plating 25um --board-thickness 1.6mm
fenolite analyze board.kicad_pcb --kinds clearance --within 0.5mm
```

The command is read-only: it runs no tool and writes no file. An error finding gives exit code 5. The
options and the result keys are in `docs/cli-contract.md`.
