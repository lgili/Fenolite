# Design: c0425

## 1. Several labels of one element

Before, `compare` put every element with more than one label in `double` and always reported it. Net ids
differ between sides, so the labels cannot be compared directly. The single-labelled elements already
give the correspondence: for each label of `a`, the label of `b` whose block holds most of that label's
single elements (a tie maps nothing; `NO_NET` maps to `NO_NET`, so it works with and without
`joined_no_net`). A double element differs when one of its labels maps to nothing, which keeps the old
behaviour for a label that only double elements carry, or when the mapped set is not its set of `b`.

## 2. Pad on no net beside a netted pad

The DSL has no per-pad net: `connect(net, part["1"])` reaches every pad `1`. A source pad `1` on no net
beside a netted pad `1` therefore changes copper in the rebuilt board, and the honest outcome is a declared
loss, not a silent rebuild. The existing kind `pad-net-conflict` (a pad number on two nets) has exactly
that meaning and already explains level 2 and level 5 in `importer.coverage.EXPLAINS`, so the ledger
now also counts a number whose pads are on a net and on no net. An `unconnected-(…)` net counts as no net,
as the existing check does for two such nets.

## 3. Designators used twice

The Altium to KiCad direction drops the schematic when the circuit has duplicate designators
(`the imported circuit has duplicate designators`) and keeps the board. The converted project then holds
each such designator once, or not at all when its footprint was lost with an embedded board array. The
`schematic` row's places now include every designator the source circuit holds more than once, and
`EXPLAINS` lets that row explain `ref-ambiguous` there.

## 4. Variant names

`derive_from_model` named the second variant of `S` as `S_2` without looking at the board's other names.
A pre-pass collects the source names of the nickname, and a variant takes the first `S_k`, `k >= len+1`,
that no source name and no earlier variant holds.

## 5. Copper on a net with a slash

A KiCad 10 board references a net by name, in the spelling it stores: `{slash}` for a slash
(`pcb.stored_net_name`). The reader names the net with the slash and keeps the stored spelling in the net's
`kicad` bag (`stored`). Tracks, vias and zones are resolved through the reader's net table, but a board
graphic keeps its `(net …)` slot opaque (c0277), and `fpitems.with_graphic_nets` matched the slot against
the model names only. A netted copper graphic on a net named `A1/GND` therefore read back without a net:
level 5 saw a `copper-no-net` piece, and a conversion refused the board. The copies of an Altium embedded
board array name their nets `B<k>/<net>`, so every copy of a netted free region did so (the private sweep:
6 copies × 23 regions). The importer's `graphic_net` read the same slot as a net of its own and declared
it. Both now accept the stored spelling: `with_graphic_nets` maps it to the net's id, and `graphic_net`
takes the map `net_spellings(design)` from stored spelling to name. Tracks and zones on such nets were
already right (the authored board holds one of each).
