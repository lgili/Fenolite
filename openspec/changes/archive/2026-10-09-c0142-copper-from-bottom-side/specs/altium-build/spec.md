## ADDED Requirements

### Requirement: Bottom-side footprints of a copper source
The check of a copper source SHALL compare the pads of a footprint with its definition in the definition's frame: for a bottom footprint, stored mirrored about local X (`H-G-BOTTOM-STORE`), with each stored Y negated (`library_pad_positions`), at any rotation; for a top one as stored. A bottom footprint stored unmirrored MUST give `altium.copper-board-mismatch`. No written byte changes. This extends "Copper from a routed KiCad board" and "Script copper in an Altium build".

#### Scenario: Bottom part with pads off its axis
- **GIVEN** the blink with `U1` (`Mini:Mini_QFP-32_7x7mm_P0.8mm`) placed on the bottom at 0° or at 90°, with or without `pad_map={"1": "2", "2": "1"}`, and the KiCad board of the same script written by `fenolite build`
- **WHEN** `fenolite build design.py --out A --target altium --copper-from <that board> --confirm --json` runs
- **THEN** the exit code is 0, no error is given, and every pad of `A/blink.PcbDoc` is where the KiCad board has it, up to one shift of the frame, within 2 nm

#### Scenario: Board of the other map
- **GIVEN** the bottom `U1` at 90° and a board built with the other choice of the map
- **WHEN** the build runs with `--copper-from`
- **THEN** the exit code is 5 and the errors are `altium.copper-board-mismatch` at `U1.1` and `U1.2`, none about the pad positions

#### Scenario: Bottom part stored unmirrored
- **GIVEN** the board of the bottom `U1` with its pads written as the library has them
- **WHEN** the build runs with `--copper-from`
- **THEN** the exit code is 5 and the one error is `altium.copper-board-mismatch` at `U1`, "the pads of Mini:Mini_QFP-32_7x7mm_P0.8mm differ from the footprint the design resolves"

#### Scenario: Script copper on a bottom part
- **GIVEN** the bottom `U1` at 90° and a track from its pad 1 on `B.Cu` through a via to `R1`'s pad 1
- **WHEN** the script is built for Altium without and with `--copper-from` its own KiCad board
- **THEN** both builds exit 0 and their `PcbDoc` files are equal byte for byte

#### Scenario: Back from Altium
- **GIVEN** `kicad-cli` 10.x
- **WHEN** `tests/kicad/altium/test_copper_from_bottom_oracle.py` imports the document of the first scenario at 0° and 90° with `kicad-cli pcb import --format altium`
- **THEN** every pad of the imported board is where the source board has it relative to the outline corner within 10 nm, `U1` is on the bottom at the source's rotation, and its stored pads with Y negated are the definition's
