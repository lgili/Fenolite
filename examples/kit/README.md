# examples/kit

The five sample scripts of the Altium verification kit (`docs/altium-kit.md`). `fenolite kit build --out DIR
--confirm` builds each into an Altium project of the kit; nothing that it builds is committed here.

| sample | what it holds |
|---|---|
| `flat/` | a controller, a resistor, an LED and a connector on one sheet, with the generic drawing sheet and a title block; built in the binary and in the ASCII form |
| `tree/` | a supply, a sensing stage and four LEDs in the modules `power`, `io` and `io/leds`, with the bus `D`; four sheets, no board |
| `routed/` | the circuit of `flat` with tracks, vias, one polygon, five rules and two planted violations |
| `board6/` | the circuit of `flat` on six copper layers with a plane, blind and buried vias, texts, graphics, a keep-out and a hole |
| `libs/` | seven catalog parts, for the schematic library and the PCB library that the build writes |

Every script is authored for Fenolite (CC0-1.0) and takes its symbols and footprints from Fenolite's own
catalog, so a build reads no library and gives the same bytes on every machine.

A sample script is a design script. It may also bind `KIT`, a mapping with the keys `sheets`, `forms`,
`copper`, `planes` and `drawing_sheet`, and a function `kit_model(model)` that returns the model with what
the DSL cannot declare (a bus, six copper layers, board items). Both are read by `fenolite kit build` only:
`fenolite build` builds the same script without them.
