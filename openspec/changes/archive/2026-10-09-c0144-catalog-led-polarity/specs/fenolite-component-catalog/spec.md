## ADDED Requirements

### Requirement: Lands numbered against the generic diode symbols are documented
The generic symbols `Diode`, `Zener_Diode` and `LED` SHALL keep pin 1 `A` and pin 2 `K`. A two-pad catalog land that keeps a manufacturer's numbering with pad 1 at the cathode SHALL be documented as needing an explicit pin-to-pad map with these symbols, and SHALL keep its pad numbers.
- The lands of this kind are `LED0603_Kingbright_APT1608SURCK`, `LED0805_Kingbright_APT2012SURCK` and `SOD128_Nexperia_CFP5`. Each MUST have its fabrication-layer cathode mark on the side of pad 1.
- The row of each in `docs/catalog/sources.md` and its entry in `docs/catalog/coverage.md` MUST say that pad 1 is the cathode and that an explicit pin-to-pad map is needed with the generic symbol.
- The catalog MUST NOT apply a pin-to-pad map by itself: a part without a `pad_map` keeps the identity map, on these lands as on every other.
- A sample script that Fenolite ships and that puts one of the three symbols on one of these lands MUST give the part a `pad_map` that puts pin 2 `K` on pad 1 and pin 1 `A` on pad 2, and MUST connect the part by pin name.

#### Scenario: Warning beside each land
- **WHEN** `uv run pytest tests/unit/catalog/test_polarity_notes.py` reads the two pages
- **THEN** the row and the entry of each of the three lands hold the word "cathode" and name the pin-to-pad map

#### Scenario: A new land of this kind
- **WHEN** a two-pad land is added to the catalog whose pad 1 lies on the side of its cathode mark
- **THEN** `test_the_cathode_first_lands_are_the_known_ones` fails until the land is named in the test and documented

#### Scenario: Kit LED
- **WHEN** each of the kit samples `board6`, `flat`, `libs` and `routed` is loaded
- **THEN** `D1` has the map `{"1": "2", "2": "1"}`, its pin `K` is on `GND` and its pin `A` on `LED_A`
