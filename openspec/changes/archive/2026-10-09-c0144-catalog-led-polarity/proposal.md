## Why

The catalog lands `LED0603_Kingbright_APT1608SURCK` and `LED0805_Kingbright_APT2012SURCK` number their pads as the manufacturer numbers the terminals: pad 1 is the cathode. The catalog symbol `LED` (with `Diode` and `Zener_Diode`) has pin 1 `A` and pin 2 `K`. A part of `Fenolite:LED` on one of these lands without a `pad_map` therefore has the anode's net on the cathode's pad. The land `SOD128_Nexperia_CFP5` is the same case and says so in the catalog pages; the two LED lands did not. Both lands and the symbol are in the releases 0.2.0 and 0.2.1.

The four kit samples `examples/kit/{board6,flat,libs,routed}` used this pair without a map and connected the LED by pin number, `GND` to `d1[1]`: the board was right (`GND` on the cathode's pad) and the schematic drew the LED backwards (`GND` on the pin named `A`).

Read on 2026-10-08 in the two public datasheets (design, Context): which of the three things was wrong. The land's numbering and its summary are right; what is missing is the map.

## What Changes

- **The warning is written where `SOD128_Nexperia_CFP5` has it**: the rows of the two LED lands in `docs/catalog/sources.md` and their entry in `docs/catalog/coverage.md` say that pad 1 is the cathode and that `Fenolite:LED` needs an explicit pin-to-pad map (`pad_map={"1": "2", "2": "1"}`). The footprints' summary text does not change (design, Decision 1).
- **The four kit samples map their LED and connect it by pin name**: `d1["K"]` to `GND`, `d1["A"]` to `LED_A`. Their boards keep every pad's net; their schematics now draw the LED the right way round.
- **No default map.** A map that the catalog applies by itself would move the nets of a released user's board; that is put to the maintainer as an open question (design, Open question).
- A test names the lands whose pad 1 is at the cathode mark and holds each to its warning, and holds the four kit samples to the map.

Size: 0.25 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `fenolite-component-catalog`: ADDED "Lands numbered against the generic diode symbols are documented".

## Non-goals

- A default pin-to-pad map between a catalog symbol and a catalog footprint: the maintainer's decision (design, Open question).
- A cathode mark on `DO214AC`: a known gap, not closed here (design, Known gaps).
- Renumbering the pads of the two LED lands: nowhere, because the numbering is the manufacturer's and released boards hold it.
- The kit sample `tree`: it authors its own LED symbol and footprint.
