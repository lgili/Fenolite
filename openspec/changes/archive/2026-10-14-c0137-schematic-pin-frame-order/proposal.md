## Why

`schlayout.pin_point` maps the library position of a symbol pin to the sheet by mirroring first and rotating second. Change c0123 found two demo sheets of the corpus where KiCad connects the pins of instances that are mirrored and turned by 90 or 270 degrees where "rotate, then mirror" puts them (its `design.md`, "Found on the way, not fixed here", item 1), and its corpus test of stacked pins leaves such instances out.

For 0 and 180 degrees the two orders agree; for 90 and 270 degrees mirroring first about one axis equals rotating first and mirroring about the other. So every reader of a KiCad sheet that holds such an instance (the own netlist, `fenolite netlist`, the parity inputs, the ERC helpers of the tests) puts its pins on the wrong points, and a build whose placements file asks for such a pair sets the labels of that unit where KiCad does not connect its pins.

The probes `sch-pin-frame-*` (`H-K-SCH-PINFRAME`, `KICAD-VERIFIED`) did not see it: their 32-pin symbol is mapped onto itself by both mirrors, and they count open pins only, so any order and any mirror axis pass.

## What Changes

- Measure the order on the demo sheets of the corpus: for every pin of a mirrored and turned instance, compare the point of each order with the wire ends, labels, no-connect flags and symbol origins of its sheet. Record the result in `docs/formats/kicad/schematic.md` as a `CORPUS-VERIFIED` fact with the corpus rows as source, and register `H-K-SCH-PINFRAME-ORDER`.
- `schlayout.turned` (and so `pin_point`, `label_angle`, the cell and text boxes of the layout) rotates first and mirrors the turned vector. Every place that maps a pin's library offset to the sheet goes through these two functions; no copy exists.
- A sheet with an instance mirrored and turned by 90 or 270 degrees adds `FRAME_ORDER_EVIDENCE` (`CORPUS-VERIFIED`, `H-K-SCH-PINFRAME-ORDER`) to the evidence of its own netlist and of a build; any other sheet keeps its evidence.
- The statement of `H-K-SCH-PINFRAME` and its row in `schematic.md` are corrected: they said the mirror comes first, which their probes cannot tell.
- Tests: the twelve frames by hand (`pin_point`, `label_angle`), an authored sheet of an asymmetric three-pin symbol in the twelve frames read back through the own netlist, its control with the old order, the corpus stacked-pin test with the left-out instances back, and a `kicad-cli` oracle (`needs_kicad`) that asks the netlist export of the same sheet which net each pin is on.

Size: 0.5 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-schematic`: MODIFIED "Pin connection points".
- `kicad-oracle`: ADDED "Order of mirror and rotation is asked of the netlist export"; MODIFIED "Stacked pins of corpus sheets" (added by the active change c0123).

## Non-goals

- New frames: the twelve pairs of `PROVED_FRAMES` stay the only ones; angles other than multiples of 90 degrees stay refused.
- A new probe id. The oracle test is a plain `needs_kicad` test, so `test_probe_results` and the committed probe files do not change; the probes `sch-pin-frame-*` keep their meaning and outcomes.
- The other item c0123 found on the way (`--copper-from` on a bottom footprint, change c0142).
