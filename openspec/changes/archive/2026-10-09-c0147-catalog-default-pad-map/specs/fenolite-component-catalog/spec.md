## MODIFIED Requirements

### Requirement: Lands numbered against the generic diode symbols are documented
The generic symbols `Diode`, `Zener_Diode` and `LED` SHALL keep pin 1 `A` and pin 2 `K`. A two-pad catalog land that keeps a manufacturer's numbering with pad 1 at the cathode SHALL be documented as needing a pin-to-pad map with these symbols, and SHALL keep its pad numbers.
- The lands of this kind are `LED0603_Kingbright_APT1608SURCK`, `LED0805_Kingbright_APT2012SURCK` and `SOD128_Nexperia_CFP5`. Each MUST have its fabrication-layer cathode mark on the side of pad 1.
- The row of each in `docs/catalog/sources.md` and its entry in `docs/catalog/coverage.md` MUST say that pad 1 is the cathode, that a build applies the pin-to-pad map by default ("Default pin-to-pad map of the cathode-first lands"), and that an explicit `pad_map` wins.
- A sample script that Fenolite ships and that puts one of the three symbols on one of these lands MUST give the part a `pad_map` that puts pin 2 `K` on pad 1 and pin 1 `A` on pad 2, and MUST connect the part by pin name.

#### Scenario: Warning beside each land
- **WHEN** `uv run pytest tests/unit/catalog/test_polarity_notes.py` reads the two pages
- **THEN** the row and the entry of each of the three lands hold the word "cathode" and name the pin-to-pad map

#### Scenario: A new land of this kind
- **WHEN** a two-pad land is added to the catalog whose pad 1 lies on the side of its cathode mark
- **THEN** `test_the_cathode_first_lands_are_the_known_ones` fails until the land is named in the test and in `catalog.CATHODE_FIRST_LANDS`, and documented

#### Scenario: Kit LED
- **WHEN** each of the kit samples `board6`, `flat`, `libs` and `routed` is loaded
- **THEN** `D1` has the map `{"1": "2", "2": "1"}`, its pin `K` is on `GND` and its pin `A` on `LED_A`

## ADDED Requirements

### Requirement: Default pin-to-pad map of the cathode-first lands
A build SHALL give a part of an anode-first catalog symbol on a cathode-first catalog land, when the part gives no `pad_map`, the map `{"1": "2", "2": "1"}`: the anode pin on the anode pad and the cathode pin on pad 1, the cathode. The maintainer decided this on 2026-10-08 (change c0147).
- The anode-first symbols are the two-pin catalog symbols with pin 1 `A` and pin 2 `K` (`catalog.ANODE_FIRST_SYMBOLS`: `Diode`, `LED`, `Photodiode`, `Schottky_Diode`, `Zener_Diode`); the cathode-first lands are those of "Lands numbered against the generic diode symbols are documented" (`catalog.CATHODE_FIRST_LANDS`). `catalog.default_pad_map(symbol_id, footprint_id)` MUST return the map for each such pair and `()` for every other pair.
- The map MUST be applied to the model that the KiCad and the Altium targets share, so both targets put the same net on each pad; `fenolite kit build` and `fenolite sync` MUST apply it as `fenolite build` does.
- A part that gives a `pad_map` MUST keep it as written. A part whose symbol or footprint the design authors under the same lib id MUST get no default.
- Every part that gets the default MUST be reported ("Default pin-to-pad map is reported", `design-dsl`).

#### Scenario: Part without a map
- **GIVEN** a script with `Fenolite:LED` on `Fenolite:LED0603_Kingbright_APT1608SURCK` and `Fenolite:Schottky_Diode` on `Fenolite:SOD128_Nexperia_CFP5`, each without a map, their pin `A` on `VA` and their pin `K` on `GND`
- **WHEN** it is built with `--target kicad` and with `--target altium`
- **THEN** in both written boards pad 1 of each part is on `GND` and pad 2 on `VA`

#### Scenario: Explicit map
- **WHEN** the LED of that script gives `pad_map={"1": "1", "2": "2"}`
- **THEN** its pad 1 is on `VA` and its pad 2 on `GND` in both targets, and the build reports no `build.pad-map-default` for it

#### Scenario: Other lands and symbols
- **WHEN** a part of `Fenolite:Diode` on `Fenolite:SOD123_Diodes` or on `Fenolite:DO41_P10.16_Diodes`, of `Fenolite:LED` on `Fenolite:Chip_0603`, or of `Fenolite:Capacitor_Polarized` on `Fenolite:SOD128_Nexperia_CFP5` gives no map
- **THEN** it keeps the identity map and is not reported

#### Scenario: Pairs read from the catalog
- **WHEN** `uv run pytest tests/unit/catalog/test_polarity_notes.py` reads every catalog symbol and land
- **THEN** `ANODE_FIRST_SYMBOLS` is the set of symbols with pin 1 `A` and pin 2 `K`, `CATHODE_FIRST_LANDS` the set of lands with pad 1 at the cathode mark, and `default_pad_map` maps exactly their pairs
