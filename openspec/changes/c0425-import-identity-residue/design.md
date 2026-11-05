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
