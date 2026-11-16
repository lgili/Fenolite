# Design: c0488

## D1 Reproduce first

A quick run on the authored 6-layer fixture `tests/data/kicad/layers/l6_t9_filled.kicad_pcb`, and on a
4-layer cut of it with signal or `power` inner layers, gave no `convert.unexplained`. So the failure needs
something those boards lack. Task 1.1 builds a small authored matrix and records which case fails:

- inner layers as signal layers, and as planes carried from an Altium source (`plane_net` in the layer's
  `altium` bag, c0466);
- carried Altium signal ids that skip Mid-Layer 1 (`lower._signal_ids`);
- pads written as `*.Cu`, and as the explicit list `F.Cu In1.Cu In2.Cu B.Cu`;
- `convert --to altium` and `build --target altium`.

The fix goes where the inner layers are lost: the writer's stack or the reader's chain. Neither is guessed
here. A new format fact goes in `docs/formats/altium/pcb-copper.md` with its source and evidence label.

## D2 The span `all`

`copper_span` returns `frozenset({"all"})` for a plated pad with a hole whose `layers`, expanded against the
board's copper layers, are all of them. A wildcard (`*.Cu`) counts. A non-plated pad keeps the c0433 rule
(empty when no larger than its hole). Any other pad keeps today's subset of `top`, `inner`, `bottom`.

`all` makes level 3 independent of the layer count for a through-hole pad. It also catches a pad that skips
one inner layer of a 4-layer board, which today compares equal to a pad on all four.

The stack itself is not compared by `pad-copper`. A lost inner layer still shows as the writer's
`altium.not-lowered` row for `stackup`, or as a level 5 `via-span` difference, so `all` hides no loss.

## D3 No new carrier

A converted board needs no new property: the layers are in the model. If task 1.1 shows the writer drops
them, the fix is in `lower`, not in a carrier.

## Found by task 1.1 (2026-11-16)

The authored board `tests/data/kicad/convert/four_layer_tht.kicad_pcb` (pads on `*.Cu` and on the explicit
list) was run through `fenolite.api.conversion.convert` (the verified `convert --to altium`) as signal inner
layers, with KiCad `power` rows, with KiCad 8 layer ids, with a `GND` plane carried on `In1.Cu` (c0466
carrier), and with carried signal ids 3 and 5 that skip Mid-Layer 1; and the blink example on
`copper=4` was built with `build --target altium`. Every case wrote four copper layers (chains
`(1, 2, 3, 32)`, `(1, 39, 3, 32)`, `(1, 3, 5, 32)`), read every Multi-Layer pad back on `F.Cu, In1.Cu,
In2.Cu, B.Cu`, and gave no `convert.unexplained`, before and after task 2.1. None of `lower._stack`,
`lower._built_stack` or `adapter.layers.LayerMap` loses an inner layer on an authored board.

Decision (maintainer, 2026-11-16): no change to the writer or the reader (D3). The failure on the
maintainer's board is a span comparison across different copper counts, which D2's `all` removes; a
stack that the writer does refuse keeps its `altium.not-lowered` row. Task 4.2 on the private board
confirms it.

Decision (maintainer, 2026-11-16): `all` is given by the pad's kind `thru_hole`, not by `drill is not
None` as D2 says. A test of level 3 removes a pad's drill and expects `pad-drill` and `pad-size` alone; a
span that followed the drill would add a third difference for the same change, which `pad-drill`
already reports.
