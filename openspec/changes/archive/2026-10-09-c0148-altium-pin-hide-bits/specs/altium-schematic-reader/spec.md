## ADDED Requirements

### Requirement: Pin visibility bits
`Pin.name_shown` and `Pin.designator_shown` SHALL read bits 0x08 and 0x10 of `PINCONGLOMERATE` as show flags when bit 0x20 is set and as hide flags when it is clear (`records.SHOW_FLAGS`; `schematic-library.md`, "Binary pin record"; `H-A-SCHLIB-PINBITS`).
- The 0x20-set reading rests on S-0613, S-0614, S-0130 and S-0131; the 0x20-clear reading on S-0612 alone.
- `direction` and `hidden` MUST NOT depend on 0x20.

#### Scenario: A pin as Altium saves it
- **WHEN** a pin with `PINCONGLOMERATE=58` (0x20, 0x10, 0x08 and leftwards) is read
- **THEN** `name_shown` and `designator_shown` are true and `direction` is 2

#### Scenario: A pin that Fenolite wrote before 0.3.0
- **WHEN** a pin with `PINCONGLOMERATE=18` (0x10 and leftwards, no 0x20) is read
- **THEN** `name_shown` is true, `designator_shown` is false and `direction` is 2

#### Scenario: The check project
- **WHEN** the sheet `tests/data/altium/pinbits/pinbits.SchDoc` is read
- **THEN** the pins of `LED_V1` show neither text, those of `LED_V2` only the number, those of `LED_V3` only the name and those of `LED_V4` both
