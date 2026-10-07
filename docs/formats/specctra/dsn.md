# Specctra design file (`.dsn`)

This page states, in Fenolite's own words, what the codec `fenolite.backends.specctra` (change c0023)
relies on to write a Specctra design file for an external router. It covers only what the writer emits.

- Sources are listed in `docs/evidence/sources.md`. The format facts come from S-0224, a reference whose
  notice forbids copying: it was read on line for facts, and no sentence, table, grammar production or
  example of it is reproduced here (ADR-0006).
- No source code of Freerouting, KiCad or any other reader or writer of this format was read.
- The writer was built before the probes ran (the maintainer's decision of 2026-10-04), so **every row is
  `INFERRED`**. A row rises only when the probe named in its last column is recorded in
  `docs/evidence/routing.md`; a probe that refutes a row changes this page first and the code second.

## Syntax

| fact | source | label | hypothesis |
|---|---|---|---|
| A design file is text made of nested lists in parentheses; a list starts with a keyword, and its other members are words or further lists | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A word is a run of letters, digits and other printable ASCII characters; a blank, a parenthesis, a semicolon, a single quote and a line end cannot be part of one | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `parser` list may declare a quote character with `string_quote`; the single quote, the double quote and the dollar sign are valid, and there is no default. A quoted string may hold parentheses | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| By default a blank ends a string even inside quotes; `(space_in_quoted_tokens on)` in the `parser` list lets a quoted string hold blanks, and the closing quote then ends it | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The reference describes no escape inside a quoted string, so a name that holds the quote character or a line end cannot be written | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `parser` list may also name the layout system (`host_cad`, `host_version`) | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| Numbers are written in decimal, with an optional sign and an optional fraction part; exponents are not supported | S-0224 | INFERRED | H-G-DSN-UNITS |

Fenolite's choices: the writer always declares `(string_quote ")` and `(space_in_quoted_tokens on)` and
quotes every name that is not a word. The lexer starts with `"` as the quote character, so that a name
quoted before the declaration still reads; that is leniency of the reader, not a fact of the format.

## Order of a design file

| fact | source | label | hypothesis |
|---|---|---|---|
| The file is one list `pcb` with an identifier, followed, in this order, by `parser`, `resolution`, `unit`, `structure`, `placement`, `library`, `network` and `wiring`; other sections exist and are optional | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| `structure`, `placement`, `library` and `network` must be present; `wiring` holds the wires and vias that exist before routing and may be absent | S-0224 | INFERRED | H-G-DSN-ACCEPT |

## Units

| fact | source | label | hypothesis |
|---|---|---|---|
| `(resolution <unit> <n>)` names the unit of every length in the file (`inch`, `mil`, `cm`, `mm` or `um`) and how many database units one unit holds: with `um 10` the lengths are micrometres and the smallest step is 0.1 µm | S-0224 | INFERRED | H-G-DSN-UNITS |
| The resolution value does not change the unit of the numbers in a design file: they stay in the named unit and may carry decimals down to the resolution | S-0224 | INFERRED | H-G-DSN-UNITS |
| `(unit <unit>)` sets the unit of the section it opens, overriding the one of `resolution` | S-0224 | INFERRED | H-G-DSN-UNITS |
| A coordinate pair is an X value followed by a Y value | S-0224 | INFERRED | H-G-DSN-UNITS |
| Rotation is in degrees, counter-clockwise from the positive X axis; Fenolite infers from it that Y grows upwards, the opposite of the model's frame, which no sentence of the reference states | S-0224 | INFERRED | H-G-DSN-UNITS |
| The product of the resolution and the largest board dimension must stay below 2³¹ | S-0224 | INFERRED | H-G-DSN-UNITS |

Fenolite writes `(resolution um 10)` and `(unit um)`: a length of `nm` nanometres becomes
`u = round_half_even(nm / 100)` database units, written as `u / 10` micrometres with at most one decimal.
Y is negated. A board of 2 m is 2·10⁷ units, far below the limit.

## Structure

| fact | source | label | hypothesis |
|---|---|---|---|
| A `layer` list gives a layer name and a `type`, one of `signal`, `power`, `mixed` and `jumper`; the layers are listed from the top of the board to the bottom | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The layer names `pcb`, `signal` and `power` are reserved: `pcb` is only for the board's boundary, `signal` stands for every signal layer and `power` for every power layer | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A `boundary` list holds a path or a rectangle, and a path closes itself. A boundary on the layer `pcb` is the bounding box of the whole design and should be a rectangle; a boundary on the layer `signal` is the area open to routing and holds no arcs | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The keep-out lists are `keepout` (everything), `wire_keepout` (wires) and `via_keepout` (vias); each holds one shape, which names its layer | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `via` list of the structure names the padstacks the router may use as vias | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `rule` list of the structure holds the default rules, among them `(width <length>)` and `(clearance <length>)`; a clearance without a `type` applies to every pair of objects | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| Wires are not routed on a layer of type `power`: Freerouting 2.4.1 puts no wire on a layer written `(type power)` (20 tracks of the plane bench, all on the outer layers) | S-0224 | ORACLE-VERIFIED | H-G-DSN-LAYERS (Freerouting 2.4.1, local run of 2026-10-08) |
| A `plane` list names a net and a shape, `(plane <net> (polygon <layer> 0 <points>))`, after the boundaries. On a `power` layer Freerouting 2.4.1 counts as joined every pin of the net that a protected via or a through-hole pad brings to the plane, and adds no copper to the net; it brings no SMD pin to the plane by itself (2 open connections per plane net of the bench without fan-out) | S-0224 | ORACLE-VERIFIED | H-G-DSN-PLANE (Freerouting 2.4.1, local run of 2026-10-08) |
| Freerouting 2.4.1 keeps its wires out of a `wire_keepout` polygon and the larger of the default and class clearance away from it | S-0224 | INFERRED | H-G-DSN-CLEARANCE |
| No clearance type applies to the boundary. Keep-out paths of half width `E − d` along every edge keep Freerouting 2.4.1's wires the edge clearance `E` from the edge where the board leaves room (a 4 mm passage), and lose the route in a 2 mm passage that the file without them routes; the writer writes none | S-0224 | ORACLE-VERIFIED | H-G-DSN-EDGE-2 (it supersedes H-G-DSN-EDGE; Freerouting 2.4.1 and `kicad-cli` 10.0.6, 2026-10-08) |

## Shapes

| fact | source | label | hypothesis |
|---|---|---|---|
| A `circle` is a layer, a diameter and an optional centre, which defaults to the origin | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A `path` is a layer, an aperture width and a list of points: the area swept by a round aperture of that width moved along the points in straight lines. Round is the default aperture | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A `polygon` is a layer, an aperture width and a list of points; polygons and circles are closed, filled shapes | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A `rect` is a layer and two opposite corners | S-0224 | INFERRED | H-G-DSN-ACCEPT |

## Placement and library

| fact | source | label | hypothesis |
|---|---|---|---|
| The `placement` section holds `component` lists, each naming an image and holding one `place` list per placed instance | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A `place` list is the component's reference, its position, its side (`front` or `back`) and its rotation; `front` is the side of the first layer. `(lock_type position)` inside it fixes the component in place | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `library` section holds the `image` lists and then the `padstack` lists | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| An `image` is a name and its pins, seen from the top; a `pin` list is a padstack name, the pin's identifier and its position in the image | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A pin identifier holds no hyphen, because a pin of a component is referred to as `<reference>-<pin>` | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A `padstack` is a name and one `shape` list per shape, each shape on its own layer, relative to the padstack's origin; the origin lies inside at least one of its shapes | S-0224 | INFERRED | H-G-DSN-ACCEPT |

Fenolite writes one image per placed footprint, placed on the front with rotation 0, and puts each pad's
board-frame copper into its padstack, on the layers the copper is on. So nothing depends on how a reader
rotates or mirrors an image. A pad whose origin lies outside its own copper (a custom pad with an offset
anchor) is written as it is; whether a router objects is part of `H-G-DSN-ACCEPT`.

## Network

| fact | source | label | hypothesis |
|---|---|---|---|
| A `net` list is a net name and a `pins` list of pin references `<reference>-<pin>`; every pin of the net is listed | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A `class` list is a class name, the names of its nets, and optional `circuit` and `rule` lists; `(circuit (use_via <padstack>))` names the via of the class, and the `rule` list holds its width and clearance | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| A net of one pad whose name starts with `unconnected-(`, the name KiCad gives a pin on no net, is not declared: its pad is a pin on no net, so a router gets the same board with and without those names (`tests/unit/backends/specctra/test_dsn.py -k unconnected`; the writer does this since c0061) | S-0224 | INFERRED | H-G-DSN-ACCEPT |
| The `circuit` list of a class may hold `use_via` and `(use_layer <layers>)`; Freerouting 2.4.1 keeps the wires of such a class on the named layers (18 tracks of the class `SIG`, all on `F.Cu`) | S-0224 | ORACLE-VERIFIED | H-G-DSN-LAYERS (Freerouting 2.4.1, local run of 2026-10-08) |
| `(class_class (classes <a> <b>) (rule (clearance <length>)))` in the network gives a clearance to the pair of the two classes; with it Freerouting 2.4.1 leaves no clearance violation between the two classes under KiCad's check, where the same file without it leaves 2 | S-0224 | INFERRED | H-G-DSN-CLEARANCE |
| A class may hold `(layer_rule <layer> (rule (width <length>)))`. Freerouting 2.4.1 routes most of the class's wire at that width on the layer (14 of 20 segments) and narrows 6 segments to 262.4 µm, 5 of them at a pad; no segment keeps the class width | S-0224 | INFERRED | H-G-DSN-CLEARANCE |

## Wiring

| fact | source | label | hypothesis |
|---|---|---|---|
| A `wire` list holds one shape, usually a path, and may name its net with `(net <name>)` | S-0224 | INFERRED | H-G-DSN-PROTECT |
| A `via` list in the wiring holds a padstack name and a position, and may name its net | S-0224 | INFERRED | H-G-DSN-PROTECT |
| `(type <t>)` in a wire or via is `fix`, `route`, `normal` or `protect`. A `normal` item may be ripped up and rerouted; a `protect` item is not altered unless the user unprotects it; a `route` item is not altered and the router may connect to it; a `fix` item is not altered and is not routed to. Whether a router connects to a `protect` item is not stated | S-0224 | INFERRED | H-G-DSN-PROTECT |

## What the tool states

| fact | source | label | hypothesis |
|---|---|---|---|
| Freerouting loads a design file named with `-de` and writes its result to the file named with `-do` | S-0221 | INFERRED | H-G-DSN-ACCEPT |
| `kicad-cli` 9.0 and 10.0 export no Specctra design file; KiCad's editor does | S-0022, S-0037, S-0225 | INFERRED | H-G-DSN-ACCEPT |
| Freerouting 2.4.1 routes no wire on a net that the network section does not declare; pins on no net and wiring without a net stay obstacles, kept clear of by the default rule and no more, whatever class the model gives their net. A class named with `-inc` is still routed | S-0221 | ORACLE-VERIFIED | H-G-DSN-NETLESS-2 (it supersedes H-G-DSN-NETLESS; Freerouting 2.4.1, 2026-10-08) |

## Planes, routing layers and rules (c0107)

What `write_dsn` writes from `plane_layers`, `net_layers` and `design.rules`; each construct is a fact row
above. A call without the two arguments, for a design without a rule, writes the text of the writer before
the change (`tests/data/specctra/c0107_before_*.dsn`).

- **Plane layers.** A copper layer named in `plane_layers` is written `(type power)`. Each zone with a net
  that has pins in the file, on each plane layer it covers, gives one `plane` after the boundaries, in zone
  order then stack order. A zone without an outline of three points gives `specctra.plane-skipped`. Via
  padstacks keep a shape on every copper layer, so a protected via touches the plane. With
  `others="netless"` (c0109) the net of a plane stays declared.
- **Routing layers.** The nets of one class are grouped by their layer set in `net_layers`. The group that
  may use every signal layer keeps the class's name (without one, the group of the class's first net in
  name order); each other group is a class named `<class>@<n>` by the writer's namer, with
  `(use_layer <layers in stack order>)` in its circuit and the class's values. A net without a class that
  has a set is written in a class named from `CLASS`, one per layer set, with the default rule's values.
- **Rules.** A closed table, combined by maximum, so the router keeps at least what any rule asks:

  | model rule (severity not `ignore`) | written as |
  |---|---|
  | `clearance`, one side `all` or absent, the other `all` or absent | the default rule's clearance and every class clearance raised to at least `min` |
  | `clearance`, one side a class or an `or` of classes, the other `all` or absent | those classes' clearances raised to at least `min` (`netclass Default` without such a class: the default rule) |
  | `clearance`, both sides classes or `or`s of classes | one `class_class` per pair of written classes and of their groups; a class with itself raises its own clearance |
  | `track_width`, A `all` or classes, with `opt` | their width becomes `opt`; with a layer clause, `layer_rule` per layer instead |
  | `track_width`, A `all` or classes, without `opt` | each of those widths clamped into `[min, max]` |
  | `no_tracks` | nothing here: `net_layers` carries it |
  | a layer clause on a `clearance` rule | dropped, the rule written for every layer, `specctra.rule-widened` |
  | `edge_clearance`; any other selector (`net`, `ref`, `item_kind`, a glob, `not`) or kind | not written, `specctra.rule-not-sent` naming the rule and why |

- **Edge clearance.** Not sent (`H-G-DSN-EDGE-2`): the format has no clearance from the boundary, and
  keep-out bands lost a route. KiCad's check judges the routed board; the plane fan-out keeps the edge
  clearance by its own test.
- **Nets outside the job.** With `others="netless"` a net stays declared when its clearance as written
  (its class, raised by the rules) is above the default rule's, or when a `class_class` list pairs its
  class with the class of a selected net.
