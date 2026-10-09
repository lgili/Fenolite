## Why

`fenolite build --target altium --copper-from BOARD.kicad_pcb` refuses a KiCad board whose bottom-side footprint has a pad off its X axis, with or without a `pad_map`: `altium.copper-board-mismatch`, "the pads of … differ from the footprint the design resolves". The board is right. A KiCad board stores the pads of a bottom footprint mirrored about the footprint's X axis (`docs/formats/kicad/board.md`, `H-G-BOTTOM-STORE`, `KICAD-VERIFIED (9.0.x, 10.0.x)`), and the check compared those stored positions with the library definition as they are, so every such pad differs in the sign of Y. The blink's bottom LED has both pads on the axis, so no test met it; change c0123 found it on the way (its `design.md`, "Found on the way, not fixed here", item 2).

The same check runs on script copper (a source of origin `script`), whose model holds the stored, mirrored pads as well: a script with copper and a bottom part with pads off its axis could not be built for Altium either.

The reverse also held: a board whose bottom footprint was stored unmirrored, which KiCad reports as a library mismatch, was accepted.

## What Changes

- The check of a copper source reads the pads of each footprint in the frame of its library definition: for a bottom footprint the stored Y is negated (`lens.altium_copper.library_pad_positions`). The footprint's rotation does not enter, because the stored pad positions are footprint-local and unrotated on both sides (`board.md`, "Pad frame").
- Top-side footprints are compared as before. No file that a build writes changes: the check decides only whether the build is refused.
- Tests: the blink with its controller (a QFP-32 of the authored mini library) on the bottom at 0 and 90 degrees, with and without a `pad_map`, its KiCad board written by Fenolite's own build; a board of the other map refused by its nets; a negative control stored unmirrored; script copper on the bottom part. A KiCad oracle (`needs_kicad`, 10.x) imports the written document back and compares every pad.

Size: 0.25 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-build`: ADDED "Bottom-side footprints of a copper source".

## Non-goals

- Any change to how a bottom footprint is written, in KiCad or Altium.
- The other item that c0123 found on the way (`schlayout.pin_point`, change c0137).
