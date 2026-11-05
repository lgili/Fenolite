## MODIFIED Requirements

### Requirement: Names of unconnected-pin nets
`fenolite.backends.kicad.netnames.unconnected_name(ref, *, unit, unit_count, pin_name, pad_number) -> str` SHALL return the net name KiCad derives for a pin on no net: `unconnected-(<ref><letter>-<pin text>-Pad<pad number>)` for a pin with a name, and `unconnected-(<ref>-Pad<pad number>)` for a pin whose name is empty or equals `pad_number` (S-1490; probe `sch-unconnected-samename`; change c0408).
- `<letter>` MUST be `netnames.unit_letter(unit, unit_count)`: empty for a symbol of one unit, and `A` to `Z` for units 1 to 26 otherwise. A unit above 26 MUST raise `ValueError`.
- `<pin text>` MUST be `netnames.pin_text(pin_name)`: the name with each blank replaced by `_` and each `/` by `{slash}`.
- `netnames.PROVED_PIN_CHARS` MUST hold the characters whose probe gave `equal` on both majors. The generator MUST leave out of `pad_nets` every pin whose name holds another character, with one `kicad.sch.unconnected-name-unproven` warning naming the pin.

#### Scenario: Named and unnamed pins
- **WHEN** `unconnected_name` is called for `U1`, one unit, pin name `PA1`, pad `2`, and for pin name `""`, pad `16`
- **THEN** it returns `unconnected-(U1-PA1-Pad2)` and `unconnected-(U1-Pad16)`

#### Scenario: Unit letter only with a name
- **WHEN** it is called for `U2`, unit 3 of 3, pin name `GND`, pad `7`, and for unit 1 of 3, pin name `""`, pad `1`
- **THEN** it returns `unconnected-(U2C-GND-Pad7)` and `unconnected-(U2-Pad1)`

#### Scenario: A pin named like its number
- **WHEN** it is called for `J1`, unit 2 of 2, pin name `1`, pad `1`, and for one unit, pin name `P2`, pad `2`
- **THEN** it returns `unconnected-(J1-Pad1)` and `unconnected-(J1-P2-Pad2)`, which are KiCad's names for the pins of probe `sch-unconnected-samename` on 9.0.9 and 10.0.6

#### Scenario: Slash and blank in a pin name
- **WHEN** it is called with pin names `A/B` and `X 1`
- **THEN** the names hold `A{slash}B` and `X_1`

#### Scenario: Unproved character
- **GIVEN** a symbol with an unconnected pin whose name holds a character outside `PROVED_PIN_CHARS`
- **WHEN** the sheet is generated
- **THEN** `pad_nets` has no entry for that pin, and the issues hold one `kicad.sch.unconnected-name-unproven` warning
